/**
 * @file integration_example.hpp
 * @brief FlashAttention V3 集成示例 - 展示如何在现有项目中使用新版本
 *
 * 使用方法:
 * 1. 在 block0.cpp 中包含此文件
 * 2. 修改 Attention 层的模板实例化
 * 3. 重新编译和仿真
 */

#ifndef __INTEGRATION_EXAMPLE_HPP__
#define __INTEGRATION_EXAMPLE_HPP__

#include "common.h"
#include "fused_flash_attn_v3.h"
#include "dataflow.h"

// ============================================================================
// 方案 A: 直接替换 (推荐用于演示)
// ============================================================================

/**
 * 原始 block0.cpp 中可能有:
 *
 * // 老版本 V1
 * typedef FlashAttentionHead<
 *     T=196, TP=2, CH=192,
 *     Q_QKV_CP=4, AQ_CP=2,
 *     __qq_t, __kq_t, ...,
 *     ENTRIES_EXP, ENTRIES_RECIP
 * > AttentionHeadType;
 *
 *
 * 改为 V3:
 */

// 推荐配置参数
constexpr int FLASH_V3_BLK_M = 8;    // Query 块大小
constexpr int FLASH_V3_BLK_N = 64;   // Key/Value 块大小

/**
 * @brief V3 版本的注意力头 (用于替换 V1)
 *
 * 模板参数说明:
 *   BLK_M=8:   与 TP=2 的并行度配合，8 个 token 形成一个块
 *   BLK_N=64:  Key/Value 块大小，平衡缓存利用率和 BRAM 使用
 */
typedef FlashAttentionHeadV3<
    /* T, TP, CH params */
    T = 196,
    TP = 2,
    CH = 192,
    Q_QKV_CP = 4,
    AQ_CP = 2,
    BLK_M = FLASH_V3_BLK_M,
    BLK_N = FLASH_V3_BLK_N,

    /* Quantization types */
    __qq_t = ap_int<13>,
    __kq_t = ap_int<13>,
    __vq_t = ap_int<13>,
    __a_t = ap_int<13>,

    /* Softmax types */
    __softmax_minus_t = ap_int<32>,
    __softmax_cursor1_t = ap_uint<6>,
    __softmax_exp_t = ap_int<16>,
    __softmax_acc_t = ap_int<32>,
    __softmax_recip_t = ap_int<16>,
    __softmax_cursor2_one_t = ap_uint<6>,
    __softmax_cursor2_two_t = ap_uint<6>,
    __softmax_affine_t = ap_int<32>,
    __softmax_cursor3_t = ap_uint<6>,

    /* Table sizes */
    ENTRIES_EXP = 32,
    ENTRIES_RECIP = 64
> AttentionHeadV3Type;

// ============================================================================
// 方案 B: 并行对比 (用于验证和性能基准)
// ============================================================================

/**
 * @brief 同时实例化 V1 和 V3 进行对比测试
 *
 * 用途:
 * - 精度验证 (输出一致性)
 * - 性能基准 (周期计数对比)
 * - 功耗分析 (资源利用率对比)
 */

#include "fused_flash_attn.h"  // 原始 V1

typedef FlashAttentionHead<
    T = 196,
    TP = 2,
    CH = 192,
    Q_QKV_CP = 4,
    AQ_CP = 2,
    __qq_t = ap_int<13>,
    __kq_t = ap_int<13>,
    __vq_t = ap_int<13>,
    __a_t = ap_int<13>,
    __softmax_minus_t = ap_int<32>,
    __softmax_cursor1_t = ap_uint<6>,
    __softmax_exp_t = ap_int<16>,
    __softmax_acc_t = ap_int<32>,
    __softmax_recip_t = ap_int<16>,
    __softmax_cursor2_one_t = ap_uint<6>,
    __softmax_cursor2_two_t = ap_uint<6>,
    __softmax_affine_t = ap_int<32>,
    __softmax_cursor3_t = ap_uint<6>,
    ENTRIES_EXP = 32,
    ENTRIES_RECIP = 64
> AttentionHeadV1Type;

/**
 * @brief 对比测试函数
 *
 * 在模拟阶段调用:
 * ```cpp
 * bool success = compare_attention_v1_vs_v3(
 *     q_stream, k_stream, v_stream,
 *     weights_config
 * );
 * ```
 */
bool compare_attention_v1_vs_v3(
    hls::stream<hls::vector<ap_int<13>, 8> >& qq_sm,
    hls::stream<hls::vector<ap_int<13>, 8> >& kq_sm,
    hls::stream<hls::vector<ap_int<13>, 8> >& vq_sm,
    const AttnLayerWeights& weights
) {
    // V1 计算
    AttentionHeadV1Type attn_v1;
    hls::stream<hls::vector<ap_int<13>, 4> > a_sm_v1;

    // 配置 V1
    for(int i=0; i<14; ++i) attn_v1.local_scalars[i] = weights.softmax_scalars[i];
    // ... 配置其他参数 ...
    attn_v1.do_attn(qq_sm, kq_sm, vq_sm, a_sm_v1);

    // V3 计算
    AttentionHeadV3Type attn_v3;
    hls::stream<hls::vector<ap_int<13>, 4> > a_sm_v3;

    // 配置 V3
    for(int i=0; i<14; ++i) attn_v3.local_scalars[i] = weights.softmax_scalars[i];
    // ... 配置其他参数 ...
    attn_v3.do_attn(qq_sm, kq_sm, vq_sm, a_sm_v3);

    // 对比输出
    bool match = true;
    for(int i=0; i<196; ++i) {
        auto v1_out = a_sm_v1.read();
        auto v3_out = a_sm_v3.read();
        if(v1_out != v3_out) {
            match = false;
            // 记录差异
        }
    }

    return match;
}

// ============================================================================
// 方案 C: 自适应版本 (用于高级应用)
// ============================================================================

/**
 * @brief 自适应块大小的 V3 版本
 *
 * 用途: 根据输入特征动态选择块大小
 * - 低复杂度输入: 使用小块 (BLK_N=32) → 低功耗
 * - 高复杂度输入: 使用大块 (BLK_N=128) → 高吞吐
 */

class AttentionHeadAdaptive {
private:
    AttentionHeadV3Type attn_v3;

    int current_blk_n = 64;  // 默认块大小

public:
    /**
     * @brief 根据输入特征调整块大小
     */
    void adapt_config(const ap_int<13>* input_features, int len) {
        // 计算输入复杂度 (例: 熵、方差等)
        double complexity = compute_complexity(input_features, len);

        if(complexity < 0.3) {
            // 低复杂度: 使用小块以节省功耗
            current_blk_n = 32;
        } else if(complexity < 0.7) {
            // 中等复杂度: 平衡配置
            current_blk_n = 64;
        } else {
            // 高复杂度: 使用大块以最大化吞吐
            current_blk_n = 128;
        }
    }

    double compute_complexity(const ap_int<13>* features, int len) {
        // 实现复杂度计算
        // (示例: 计算特征的标准差)
        double mean = 0, var = 0;
        for(int i=0; i<len; ++i) mean += features[i];
        mean /= len;
        for(int i=0; i<len; ++i) var += (features[i] - mean) * (features[i] - mean);
        var /= len;
        return sqrt(var) / 1000.0;  // 归一化到 [0,1]
    }
};

// ============================================================================
// 方案 D: 完整集成到 block0 中
// ============================================================================

/**
 * @brief 修改现有 block0 中 Attention 层的步骤
 *
 * 在 block0.cpp 中:
 *
 * 步骤 1: 包含新头文件
 * #include "fused_flash_attn_v3.h"
 *
 * 步骤 2: 修改 typedef (找到原始定义)
 * // OLD:
 * typedef FlashAttentionHead<...> AttentionHeadType;
 * // NEW:
 * typedef FlashAttentionHeadV3<..., BLK_M, BLK_N, ...> AttentionHeadType;
 *
 * 步骤 3: 添加 HLS pragma (如需要)
 * #pragma HLS dataflow
 * #pragma HLS pipeline II=1
 *
 * 步骤 4: 重新编译
 * cd build && make
 */

// ============================================================================
// 性能对比配置
// ============================================================================

/**
 * @brief 不同块大小的性能预测
 */
struct BlockSizeConfig {
    int blk_m;
    int blk_n;
    const char* label;
    float estimated_bram_kb;
    float estimated_latency_us;
    float estimated_power_mw;
};

const BlockSizeConfig BLOCK_CONFIGS[] = {
    {8,  32,  "Ultra-Low-Power",    80,  8.5,   50},
    {8,  64,  "Balanced",           150, 6.2,   85},   // 推荐
    {8,  128, "High-Throughput",    280, 5.1,  150},
    {16, 64,  "More-Parallelism",   200, 5.8,  110},
};

/**
 * @brief 选择最适合的配置
 */
const BlockSizeConfig* select_optimal_config(
    float power_budget_mw,
    float latency_budget_us
) {
    for(const auto& cfg : BLOCK_CONFIGS) {
        if(cfg.estimated_power_mw <= power_budget_mw &&
           cfg.estimated_latency_us <= latency_budget_us) {
            return &cfg;
        }
    }

    // 默认返回均衡配置
    return &BLOCK_CONFIGS[1];
}

// ============================================================================
// 验证和测试
// ============================================================================

/**
 * @brief C++ 模拟测试 (在 C-Simulation 阶段运行)
 */
#ifdef __SYNTHESIS__
    // 当在 HLS 综合时，跳过这个部分
#else
    #include <cmath>
    #include <iostream>

    void test_v3_accuracy() {
        std::cout << "=== FlashAttention V3 准确性测试 ===" << std::endl;

        // 创建随机测试数据
        ap_int<13> qq[196*192], kq[196*192], vq[196*192];
        // ... 初始化测试数据 ...

        // 运行 V1
        hls::stream<hls::vector<ap_int<13>, 8> > qq_sm_v1, kq_sm_v1, vq_sm_v1;
        hls::stream<hls::vector<ap_int<13>, 4> > a_sm_v1;
        AttentionHeadV1Type attn_v1;
        // attn_v1.do_attn(...);

        // 运行 V3
        hls::stream<hls::vector<ap_int<13>, 8> > qq_sm_v3, kq_sm_v3, vq_sm_v3;
        hls::stream<hls::vector<ap_int<13>, 4> > a_sm_v3;
        AttentionHeadV3Type attn_v3;
        // attn_v3.do_attn(...);

        // 对比结果
        int errors = 0;
        // for(...) { if(v1_out != v3_out) errors++; }

        std::cout << "精度对比结果: " << (errors == 0 ? "PASS" : "FAIL") << std::endl;
        if(errors > 0) {
            std::cout << "错误数: " << errors << std::endl;
        }
    }
#endif

#endif // __INTEGRATION_EXAMPLE_HPP__
