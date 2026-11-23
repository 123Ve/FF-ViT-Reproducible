# 原始位宽 HLS C 仿真副本

`src/` 仅包含 `block0.cpp` 的必要头文件依赖与本实验生成的
`fixed_patch_head_rom.h`。除 ROM 参数外，所有复制文件保持与原目录逐字节一致，
`source_manifest.json` 记录原文件、复制文件、exact artifact 与 fixture 身份。

入口为 `testbench.cpp`。它在单个编译单元中包含原始 `src/block0.cpp`，使用宏仅重命名
其中自带的旧 `main`，然后提供严格检查文件长度和输出流的新 `main`；不修改架构函数。
`run_csim.tcl` 专用于 C simulation，未运行综合或 RTL cosimulation。

从实验根目录执行：

```bash
/home/user/anaconda3/envs/vlm_token/bin/python scripts/run_hls_csim.py
/home/user/anaconda3/envs/vlm_token/bin/python scripts/verify_hls_report.py --prepare-reference
```

脚本调用本机 `/opt/vivado/2025.1/Vitis/bin/vitis-run`，干净编译第一个样本，然后
同一 `csim.exe` 在另外三个独立目录运行。不要通过 GUI 的旧工程缓存判断本次结果。
首次完整编译与四图仿真约数分钟，以机器实际速度为准。

- `data/sample_NNN/input.bin`：小端 int16[196,768]，逻辑 patch 行主序。
- `data/sample_NNN/weights.bin`：12×231008 = 2772096 bytes，原生 BlockLayerWeights。
- `data/sample_NNN/output.bin`：1000 个小端 int32 exact logits。
- TB 将输入转换为 TP=2/CAP=1 的 [98,768,2] AXIS 顺序。
- FM dump 逆转换 [98,192,2] → [196,192] 后，与 exact trace 逐整数比较。

运行日志和原始 dump 保存在 `results/hls/<UTC-run-id>/`；汇总见
`reports/hls_csim.json`。Patch、12 个 block 输出和 logits 共 14 个边界，每图均须
零 mismatch。四张图是固定仿真样本，不能将通过率当作 ImageNet-1K 准确率。

首次归档后，`data/sample_NNN/expected_*.bin` 包含紧凑的 14 边界 exact 参考值；
`data/reference_manifest.json` 记录其 SHA-256。后续可独立执行
`python scripts/verify_hls_report.py` 重算比较，不依赖原来 396MB 的全算子 trace NPZ。

正式准确率由 `reports/exact_50k.json` 的 50k 整数模型结果单独给出。查阅
`paper/METHODOLOGY_CN.md` 了解源代码实际 fused Softmax 位宽、QAT 与物理 MAC scale
差异以及选模统计口径。
