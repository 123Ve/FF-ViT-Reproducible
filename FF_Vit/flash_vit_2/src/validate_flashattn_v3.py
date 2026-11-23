#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证脚本: FlashAttention V3 在软件中的参考实现

功能:
1. 模拟 V1 和 V3 的 Attention 计算
2. 验证精度一致性
3. 对比性能指标 (访问次数、内存占用)
4. 生成可视化报告

使用:
  python validate_flashattn_v3.py --mode simulate
  python validate_flashattn_v3.py --mode compare_memory
  python validate_flashattn_v3.py --mode profile
"""

import numpy as np
import argparse
import json
from typing import Tuple, Dict, List
import matplotlib.pyplot as plt
from pathlib import Path
import time


# ============================================================================
# FlashAttention V1 参考实现 (软件版本)
# ============================================================================

class FlashAttentionV1:
    """原始 FlashAttention - 行级 Softmax"""

    def __init__(self, T=196, CH=192, quantize_bits=13):
        self.T = T
        self.CH = CH
        self.quantize_bits = quantize_bits
        self.stats = {}

    def attention(self, Q, K, V, softmax_params):
        """
        Q, K, V: (T, CH) 矩阵
        softmax_params: 量化参数 dict
        返回: (T, CH) attention 输出
        """

        # 初始化统计
        self.stats['bram_peak'] = self.CH * 3 * 4  # 3个缓存 × CH × 4字节
        self.stats['bram_reads'] = self.T * self.CH * 3  # 读 Q,K,V
        self.stats['bram_writes'] = self.T * self.CH  # 写输出

        O = np.zeros((self.T, self.CH), dtype=np.float32)

        # 标准 Attention: softmax(QK^T / sqrt(d)) @ V
        S = Q @ K.T  # T × T 点乘

        # 行级 softmax
        for i in range(self.T):
            # 数值稳定 softmax
            S_i = S[i, :]
            S_i_max = np.max(S_i)
            exp_S = np.exp(S_i - S_i_max)
            softmax_weights = exp_S / np.sum(exp_S)

            # 累加加权 Value
            O[i, :] = softmax_weights @ V  # (T,) × (T, CH) = (CH,)

        return O

    def memory_analysis(self):
        """返回内存访问分析"""
        if not self.stats:
            # 未执行 attention, 使用估计值
            self.stats['bram_peak'] = self.CH * 3 * 4
            self.stats['bram_reads'] = self.T * self.CH * 3
            self.stats['bram_writes'] = self.T * self.CH

        return {
            'bram_peak_kb': self.stats['bram_peak'] / 1024,
            'total_reads_kb': self.stats['bram_reads'] * 4 / 1024,
            'total_writes_kb': self.stats['bram_writes'] * 4 / 1024,
            's_buf_size_kb': self.T * self.T * 4 / 1024,
        }


# ============================================================================
# FlashAttention V3 参考实现 (软件版本)
# ============================================================================

class FlashAttentionV3:
    """改进版 FlashAttention - 块级计算"""

    def __init__(self, T=196, CH=192, BLK_M=8, BLK_N=64, quantize_bits=13):
        self.T = T
        self.CH = CH
        self.BLK_M = BLK_M
        self.BLK_N = BLK_N
        self.quantize_bits = quantize_bits

        self.num_blocks_m = (T + BLK_M - 1) // BLK_M
        self.num_blocks_n = (T + BLK_N - 1) // BLK_N

        self.stats = {}

    def attention(self, Q, K, V, softmax_params):
        """
        块级 Attention 计算

        关键优化:
        1. 分块处理 K/V (减少缓存)
        2. 块内并行计算
        3. 融合 Softmax·V
        """

        # 初始化统计
        self.stats['bram_peak'] = self.BLK_N * self.CH * 2 * 4  # K, V 块
        self.stats['bram_reads'] = self.T * self.CH * 3
        self.stats['bram_writes'] = self.T * self.CH
        self.stats['block_loads'] = self.num_blocks_n  # K/V 块加载次数

        O = np.zeros((self.T, self.CH), dtype=np.float32)
        max_val = np.full(self.T, -np.inf, dtype=np.float32)
        sum_exp = np.zeros(self.T, dtype=np.float32)

        # 块级计算
        for blk_n in range(self.num_blocks_n):
            j_start = blk_n * self.BLK_N
            j_end = min(j_start + self.BLK_N, self.T)

            K_blk = K[j_start:j_end, :]  # (j_len, CH)
            V_blk = V[j_start:j_end, :]

            # 块内对每个 Query 块处理
            for blk_m in range(self.num_blocks_m):
                i_start = blk_m * self.BLK_M
                i_end = min(i_start + self.BLK_M, self.T)

                Q_blk = Q[i_start:i_end, :]  # (i_len, CH)

                # Pass 1: QK^T 和找 max
                S_blk = Q_blk @ K_blk.T  # (i_len, j_len)

                for i_off, i in enumerate(range(i_start, i_end)):
                    for j_off, j in enumerate(range(j_start, j_end)):
                        s_val = S_blk[i_off, j_off]
                        if s_val > max_val[i]:
                            max_val[i] = s_val

                # Pass 2 & 3: exp + softmax·V (融合)
                for i_off, i in enumerate(range(i_start, i_end)):
                    for j_off, j in enumerate(range(j_start, j_end)):
                        s_val = S_blk[i_off, j_off]
                        exp_val = np.exp(s_val - max_val[i])
                        sum_exp[i] += exp_val
                        O[i, :] += exp_val * V_blk[j_off, :]

        # 后处理: 除以求和
        for i in range(self.T):
            if sum_exp[i] > 0:
                O[i, :] /= sum_exp[i]

        return O

    def memory_analysis(self):
        """返回内存访问分析"""
        if not self.stats:
            # 未执行 attention, 使用估计值
            self.stats['bram_peak'] = self.BLK_N * self.CH * 2 * 4
            self.stats['bram_reads'] = self.T * self.CH * 3
            self.stats['bram_writes'] = self.T * self.CH
            self.stats['block_loads'] = self.num_blocks_n

        return {
            'bram_peak_kb': self.stats['bram_peak'] / 1024,
            'total_reads_kb': self.stats['bram_reads'] * 4 / 1024,
            'total_writes_kb': self.stats['bram_writes'] * 4 / 1024,
            's_buf_size_kb': self.BLK_M * self.BLK_N * 4 / 1024,
            'block_loads': self.stats['block_loads'],
        }


# ============================================================================
# 测试和对比
# ============================================================================

class AttentionComparison:
    """对比 V1 和 V3"""

    def __init__(self, T=196, CH=192):
        self.T = T
        self.CH = CH

    def test_accuracy(self, num_tests=5):
        """精度一致性测试"""
        print("\n" + "="*70)
        print(" 精度一致性测试")
        print("="*70)

        results = []

        for test_id in range(num_tests):
            # 生成随机数据
            np.random.seed(test_id)
            Q = np.random.randn(self.T, self.CH).astype(np.float32) * 10
            K = np.random.randn(self.T, self.CH).astype(np.float32) * 10
            V = np.random.randn(self.T, self.CH).astype(np.float32) * 10

            # 运行 V1 和 V3
            attn_v1 = FlashAttentionV1(self.T, self.CH)
            attn_v3 = FlashAttentionV3(self.T, self.CH, BLK_M=8, BLK_N=64)

            softmax_params = {}  # 简化版本

            out_v1 = attn_v1.attention(Q, K, V, softmax_params)
            out_v3 = attn_v3.attention(Q, K, V, softmax_params)

            # 对比输出
            mae = np.mean(np.abs(out_v1 - out_v3))
            max_err = np.max(np.abs(out_v1 - out_v3))
            mse = np.mean((out_v1 - out_v3) ** 2)

            results.append({
                'test_id': test_id,
                'mae': mae,
                'max_error': max_err,
                'mse': mse,
            })

            print(f"Test {test_id+1}:")
            print(f"  MAE: {mae:.2e}")
            print(f"  Max Error: {max_err:.2e}")
            print(f"  MSE: {mse:.2e}")

        return results

    def test_memory_efficiency(self):
        """内存效率对比"""
        print("\n" + "="*70)
        print(" 内存效率分析")
        print("="*70)

        attn_v1 = FlashAttentionV1(self.T, self.CH)
        attn_v3_configs = [
            (8, 32, "Ultra-Low-Power"),
            (8, 64, "Balanced (推荐)"),
            (8, 128, "High-Throughput"),
            (16, 64, "More-Parallelism"),
        ]

        # 运行一次以获取统计
        Q = np.random.randn(self.T, self.CH).astype(np.float32)
        K = np.random.randn(self.T, self.CH).astype(np.float32)
        V = np.random.randn(self.T, self.CH).astype(np.float32)

        out_v1 = attn_v1.attention(Q, K, V, {})
        mem_v1 = attn_v1.memory_analysis()

        results = []

        print("\nV1 (原始版本):")
        for key, val in mem_v1.items():
            print(f"  {key}: {val:.2f}")

        print("\nV3 不同配置对比:")
        for blk_m, blk_n, label in attn_v3_configs:
            attn_v3 = FlashAttentionV3(self.T, self.CH, blk_m, blk_n)
            out_v3 = attn_v3.attention(Q, K, V, {})
            mem_v3 = attn_v3.memory_analysis()

            bram_save = (1 - mem_v3['bram_peak_kb'] / mem_v1['bram_peak_kb']) * 100

            print(f"\n  {label} (BLK_M={blk_m}, BLK_N={blk_n}):")
            print(f"    BRAM 峰值: {mem_v3['bram_peak_kb']:.1f}KB (节省 {bram_save:.1f}%)")
            print(f"    临时缓存: {mem_v3['s_buf_size_kb']:.1f}KB")
            print(f"    块加载次数: {mem_v3['block_loads']}")

            results.append({
                'config': label,
                'blk_m': blk_m,
                'blk_n': blk_n,
                'bram_kb': mem_v3['bram_peak_kb'],
                'savings_pct': bram_save,
            })

        return mem_v1, results

    def test_block_size_sensitivity(self):
        """块大小敏感性分析"""
        print("\n" + "="*70)
        print(" 块大小敏感性分析")
        print("="*70)

        block_configs = [
            (4, 32), (4, 64), (8, 32), (8, 64), (8, 128), (16, 64),
        ]

        results = []

        for blk_m, blk_n in block_configs:
            attn = FlashAttentionV3(self.T, self.CH, blk_m, blk_n)
            mem = attn.memory_analysis()

            results.append({
                'blk_m': blk_m,
                'blk_n': blk_n,
                'bram_kb': mem['bram_peak_kb'],
                'temp_buf_kb': mem['s_buf_size_kb'],
                'block_loads': mem['block_loads'],
                'efficiency': (self.T ** 2 * self.CH) / mem['bram_peak_kb'],
            })

            print(f"BLK_M={blk_m:2d}, BLK_N={blk_n:3d}: "
                  f"BRAM={mem['bram_peak_kb']:6.1f}KB, "
                  f"Eff={results[-1]['efficiency']:.1f}")

        return results


# ============================================================================
# 可视化和报告生成
# ============================================================================

def generate_report(comp: AttentionComparison, output_dir="./results"):
    """生成完整的对比报告"""

    Path(output_dir).mkdir(exist_ok=True)

    print("\n" + "="*70)
    print("生成报告...")
    print("="*70)

    # 精度测试
    accuracy_results = comp.test_accuracy(num_tests=5)

    # 内存测试
    mem_v1, mem_v3_results = comp.test_memory_efficiency()

    # 块大小敏感性
    block_sensitivity = comp.test_block_size_sensitivity()

    # 保存为 JSON (转换为 Python 原生类型)
    def convert_to_native(obj):
        """递归转换 numpy 类型为 Python 原生类型"""
        if isinstance(obj, dict):
            return {k: convert_to_native(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert_to_native(v) for v in obj]
        elif isinstance(obj, (np.integer, np.floating)):
            return float(obj)
        else:
            return obj

    report = {
        'accuracy': accuracy_results,
        'memory_v1': mem_v1,
        'memory_v3_configs': mem_v3_results,
        'block_size_sensitivity': block_sensitivity,
    }

    report_path = Path(output_dir) / "flashattn_v3_report.json"
    with open(report_path, 'w') as f:
        json.dump(convert_to_native(report), f, indent=2)

    print(f"\n[OK] 报告已保存: {report_path}")

    # 生成可视化图表
    generate_plots(mem_v1, mem_v3_results, block_sensitivity, output_dir)


def generate_plots(mem_v1, mem_v3_results, block_sensitivity, output_dir):
    """生成可视化图表"""

    try:
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))

        # 图 1: BRAM 峰值对比
        configs = [r['config'] for r in mem_v3_results]
        bram_values = [r['bram_kb'] for r in mem_v3_results]

        ax1 = axes[0, 0]
        ax1.bar(range(len(configs)), bram_values, color='skyblue')
        ax1.axhline(mem_v1['bram_peak_kb'], color='red', linestyle='--', label='V1')
        ax1.set_xticks(range(len(configs)))
        ax1.set_xticklabels(configs, rotation=45, ha='right')
        ax1.set_ylabel('BRAM 使用 (KB)')
        ax1.set_title('BRAM 峰值对比')
        ax1.legend()
        ax1.grid(True, alpha=0.3)

        # 图 2: 节省百分比
        savings = [r['savings_pct'] for r in mem_v3_results]
        ax2 = axes[0, 1]
        ax2.bar(range(len(configs)), savings, color='lightgreen')
        ax2.set_xticks(range(len(configs)))
        ax2.set_xticklabels(configs, rotation=45, ha='right')
        ax2.set_ylabel('节省百分比 (%)')
        ax2.set_title('相比 V1 的 BRAM 节省')
        ax2.grid(True, alpha=0.3)

        # 图 3: 块大小敏感性
        ax3 = axes[1, 0]
        blk_ns = [r['blk_n'] for r in block_sensitivity]
        bramsizes = [r['bram_kb'] for r in block_sensitivity]
        ax3.plot(blk_ns, bramsizes, 'o-', linewidth=2, markersize=8)
        ax3.set_xlabel('Block Size (BLK_N)')
        ax3.set_ylabel('BRAM 使用 (KB)')
        ax3.set_title('块大小与内存的关系')
        ax3.grid(True, alpha=0.3)

        # 图 4: 效率指标
        ax4 = axes[1, 1]
        configs_str = [f"({r['blk_m']},{r['blk_n']})" for r in block_sensitivity]
        efficiency = [r['efficiency'] for r in block_sensitivity]
        ax4.bar(range(len(configs_str)), efficiency, color='lightsalmon')
        ax4.set_xticks(range(len(configs_str)))
        ax4.set_xticklabels(configs_str, rotation=45, ha='right')
        ax4.set_ylabel('计算效率 (操作数/KB)')
        ax4.set_title('不同块大小配置的计算效率')
        ax4.grid(True, alpha=0.3)

        plt.tight_layout()
        plot_path = Path(output_dir) / "flashattn_v3_analysis.png"
        plt.savefig(plot_path, dpi=150)
        print(f"[OK] 图表已保存: {plot_path}")

    except Exception as e:
        print(f"[WARN] 生成图表失败: {e}")


# ============================================================================
# 主程序
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="FlashAttention V3 验证脚本")
    parser.add_argument(
        '--mode',
        choices=['simulate', 'compare_memory', 'profile', 'full'],
        default='full',
        help='运行模式'
    )
    parser.add_argument(
        '--output',
        default='./flashattn_v3_results',
        help='输出目录'
    )

    args = parser.parse_args()

    print("\n" + "="*70)
    print("FlashAttention V3 验证工具")
    print("="*70)

    comp = AttentionComparison(T=196, CH=192)

    if args.mode in ['simulate', 'full']:
        comp.test_accuracy(num_tests=5)

    if args.mode in ['compare_memory', 'full']:
        comp.test_memory_efficiency()
        comp.test_block_size_sensitivity()

    if args.mode == 'full':
        generate_report(comp, args.output)

    print("\n" + "="*70)
    print("验证完成!")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
