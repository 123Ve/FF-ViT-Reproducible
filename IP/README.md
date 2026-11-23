# FF-ViT E07 IP

[HLS C++ 源码 / HLS C++ sources](src/) · [Vivado IP 源码 / Vivado IP sources](vivado_ip/)

本目录将 E07 主线 IP 单独展开，便于直接在 GitHub 查看或独立取用。

| 路径 / Path | 内容 / Contents |
| --- | --- |
| `src/block0.cpp` | HLS 顶层 `vit_block_top` / HLS top-level implementation |
| `src/attn.h`, `src/fused_flash_attn.h` | Attention 与融合数据流 / attention and fused dataflow |
| `src/mlp.h`, `src/matmul.h` | MLP 与矩阵运算 / MLP and matrix operators |
| `src/layernorm.h`, `src/softmax.h`, `src/gelu.h` | 非线性算子 / nonlinear operators |
| `src/fixed_patch_head_rom.h` | Patch/Head ROM 参数 / Patch/Head ROM parameters |
| `hls_config.cfg` | 可从本目录使用的 HLS 综合与 IP 导出配置 / local synthesis and export configuration |
| `tests/multi_call.inc` | 原 C-sim 测试辅助源码 / original C-sim test helper |
| `vivado_ip/component.xml` | 可导入的 Vivado IP 描述 / importable Vivado IP descriptor |
| `vivado_ip/hdl/verilog/` | 已生成的 Verilog 源码 / generated Verilog sources |
| `vivado_ip/hdl/vhdl/` | 已生成的 VHDL 源码 / generated VHDL sources |
| `vivado_ip/drivers/` | Vitis 驱动源码 / Vitis driver sources |
| `vivado_ip/constraints/`, `vivado_ip/xgui/` | IP 约束及界面 / IP constraints and customization interface |

## Vivado

将 `IP/vivado_ip` 加入 **Settings → IP → Repository**，刷新 IP Catalog 后查找：

```text
xilinx.com:hls:vit_block_top:1.0
```

Add `IP/vivado_ip` to the IP repository paths, refresh the catalog and select
`vit_block_top`. Generated HDL and packaging files are extracted byte for byte
from the archived E07 IP.

## HLS

使用 Vitis 2025.1，在本目录执行 / Run from this directory with Vitis 2025.1:

```bash
v++ -c --mode hls --config hls_config.cfg --work_dir build
vitis-run --mode hls --package --config hls_config.cfg --work_dir build
```

目标器件 / Part: `xczu9eg-ffvb1156-2-e`; top: `vit_block_top`;
HLS 时钟约束 / synthesis clock constraint: `3 ns`.

`src/block0.cpp` 为 GitHub 可读副本，移除了原文件中的 7 个 NUL 字节，并调整测试辅助文件的相对路径；
原始字节版本仍保存在
`FF_Vit/E04_weight_schedule/E07_timing_300mhz/src/block0.cpp`。
其余 HLS 文件及展开的 Vivado IP 均与归档源逐字节相同。
文件来源和 SHA-256 记录于 `SOURCE_MANIFEST.json`。

The top-level C++ browsing copy removes seven embedded NUL bytes and relocates
the relative path to the test helper. The original
byte-identical file remains in the full project path above. All other HLS
sources and packaged IP files retain their original bytes. See
`SOURCE_MANIFEST.json` for provenance.
