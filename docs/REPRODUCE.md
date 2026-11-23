# 构建与复现 / Build and reproduction

## 1. 冻结快照与工作区 / Snapshot and workspace

Linux + Python 3.11+。HLS/Vivado/Vitis 使用 **2025.1**，器件
`xczu9eg-ffvb1156-2-e`，ZCU102。保留的构建脚本使用
`/opt/vivado/2025.1/{Vitis,Vivado}`；迁移工具安装位置时需在新工作区调整工具路径。

```bash
python3 -B tools/verify_repository.py
python3 tools/create_workspace.py --output "$PWD/work/reproduction"
export FFVIT_WORK="$PWD/work/reproduction"
export PATH=/opt/vivado/2025.1/Vitis/bin:/opt/vivado/2025.1/Vivado/bin:$PATH
```

Do not build inside the frozen archive. `create_workspace.py` creates a copy,
rewrites historical executable/configuration path strings, unpacks the reusable
E07 IP and installs the archived BSPs into the paths expected by firmware builds.
No numeric file or archived FPGA image is rewritten. `WORKSPACE.json` records
all path-only modifications. A new build naturally has a new source identity.

## 2. 无图像数据集的 HLS 样例 / HLS fixture without datasets

ImageNet 严格 S3 的完整 C-sim 源码闭包和四个样例已保留。单样例运行：

```bash
cd "$FFVIT_WORK/ff_vit_re/image1k_hls_s3_original"
export FVIT_HLS_ROOT="$PWD/hls"
export FVIT_HLS_SAMPLE="$PWD/hls/data/sample_000"
vitis-run --mode hls --tcl hls/run_csim.tcl
```

The C-sim harness includes the unmodified arithmetic source and the task's
generated ROM. This is C simulation, not RTL or board verification. The same
binary can be executed in the other three fixture directories. Read the
preserved `hls/README.md` for all 14 boundary comparisons.

PlantVillage/NWPU 对应 HLS、ROM、testbench 和四个输入样例位于：

```text
ff_vit_re/validation/u3_full_board_test_20261014/outputs/<plantvillage|nwpu>/hardware/
```

Its historical `build_hardware.py` also orchestrates dataset preparation and
implementation. The external datasets must be supplied before running the full
pipeline; the minimal repository deliberately omits full input shards.

## 3. E07 HLS 与 Vivado / E07 HLS and implementation

原 E07 算法源码、HLS 配置、BD 与 candidate05 时钟/实现 Tcl 成套保留。
工作区已解包原 IP，可先直接复现 Vivado：

```bash
cd "$FFVIT_WORK/FF_Vit/E04_weight_schedule/E07_timing_300mhz"
export E07_CANDIDATE=candidate05
vivado -mode batch -notrace -source scripts/prepare_candidate04.tcl
vivado -mode batch -notrace -source scripts/run_candidate04.tcl
```

These scripts enforce the original PS/MMCM configuration and timing checks.
An implementation on another machine may differ in placement, timing and
bitstream hash; successful reproduction must be assessed from its own reports.
The historical all-in-one `build_candidate05.sh` additionally checks an old
E06 freeze manifest. That discarded baseline is not needed for this selected
source/IP reproduction, so invoke the stages above rather than the old wrapper.

重新生成 HLS IP 可执行原配置对应的工具阶段：

```bash
v++ -c --mode hls --config hls/hls_config.cfg --work_dir hls/new_work
vitis-run --mode hls --package --config hls/hls_config.cfg --work_dir hls/new_work
```

The package output path is relocated in the writable configuration. To use
the newly generated IP for implementation, unpack that output into the working
IP repository referenced by `prepare_candidate04.tcl` before creating a new
Vivado project. Keep the original reusable-IP ZIP unchanged in the archive.

## 4. 裸机 Vitis / Standalone Vitis

E07 的 `board_300mhz/src`、`power_src`、DDR 测量与 ImageNet 50k 测试源码均保留。
原始 FSBL/PMUFW、已编译 ELF、BOOT/BIF 与来源清单也保留。

```bash
cd "$FFVIT_WORK/FF_Vit/E04_weight_schedule/E07_timing_300mhz"
export E07_XSA="$PWD/results/candidate05/board_release/e07_300mhz_wrapper.xsa"
export E07_CLOCK_FILE="$PWD/results/candidate05/board_release/clock.txt"
vitis -s board_300mhz/build_vitis.py
vitis -s board_300mhz/build_pmufw.py
python3 board_300mhz/make_boot_image.py
```

For an XSA from a new Vivado run, set those environment variables to the new
`results/candidate05/` files instead. The scripts refuse to overwrite an
existing application workspace; use a fresh reproduction workspace for retries.
The exact archived images remain available for identity comparison, separately
from newly built outputs.

## 5. 独立采样固件 / Independent sampler firmware

Power r10 is preserved byte for byte at
`ff_vit_re/validation/cloud_power_retest_20261121/independent_sampler`.
It includes the original three BOOT profiles, both ELF/map files, CPU partition
logs, protocol and full Windows commands. Its `package.py --check-only` must run
in the original frozen package, not a workspace augmented with BSPs/build outputs.

```bash
python3 -B ff_vit_re/validation/cloud_power_retest_20261121/independent_sampler/package.py --check-only
```

重新编译在生成的工作区执行，使用随仓库保存的 A53-0/A53-1 BSP：

```bash
cd "$FFVIT_WORK/ff_vit_re/validation/cloud_power_retest_20261121/independent_sampler"
python3 -B build_firmware.py --diagnostic16
# strict18: omit the flag; diagnostic17: use --diagnostic17
```

This is a PS-only build with the frozen PL bitstream. It creates new build
identities and boot images. Do not present a fresh build as physically accepted.
The original README explains packaging and the required new SD receipt.

## 6. 训练、量化、导出 / Training, quantization and export

完整依赖版本记录：`provenance/python_snapshot/ENVIRONMENT_SNAPSHOT.json`。
`requirements-training.txt` 是观测版本，不是跨 GPU/CUDA 系统保证可安装的 lockfile。
先按自己的驱动安装匹配的 PyTorch/CUDA，再安装其余训练依赖。

External datasets can be linked while creating a new workspace:

```bash
python3 tools/create_workspace.py --output "$PWD/work/training" \
  --plantvillage-root /data/PlantVillage \
  --nwpu-root /data/NWPU-RESISC45 \
  --imagenet-train /data/ImageNet/train \
  --imagenet-val /data/ImageNet/val
```

PlantVillage 的目录需要原协议的 `splits/train,val,test`；NWPU 使用保存的类别顺序
和 metadata 清单；ImageNet 采用冻结协议里的 248 短边、224 裁剪和成员顺序。
类别文件和样本清单不是图像负载；缺少外部图像时无法重新训练或评测全测试集。

| Task | Mainline |
| --- | --- |
| PlantVillage | `train_plantvillage.py` → `make_hls196_plantvillage.py` → `qat_weight3_hls196.py` → progressive U3 QAT → integer exporter |
| NWPU | `archive/nwpu_resisc45_ffvit/scripts/` FP32/HLS196/W3 → same progressive U3 QAT and exporter |
| ImageNet | `image_lianghu` preserved W3 initialization → `image1k_hls_s3_original/scripts/train_strict_{mlp,attention}.py` → `task4_calibrate.py` → `build_exact.py` |

The PlantVillage/NWPU common final entrypoints are
`validation/e07_u3_progressive_qat_20261010/{progressive.py,exporter.py}`.
Read their `--help` and saved `outputs/<dataset>/<stage>/recipe.json` before
starting a fresh long run. Existing checkpoints must not be overwritten.
ImageNet's selected checkpoint restores both EMA model and EMA controller.

历史源码的只读哈希与路径在 `provenance/`，工作区路径重写不会修改这些原始证据。
A new training run is not a guarantee of byte-identical checkpoints or accuracy.
