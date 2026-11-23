# FF-ViT E07 最小可复现工程归档

[English README](README.md) · [中英文构建指南](docs/REPRODUCE.md) · [工程说明](docs/PROJECT_NOTES.md)

**单独提取的 IP 源码：[IP/](IP/)** — [HLS C++](IP/src/) · [Verilog](IP/vivado_ip/hdl/verilog/) · [VHDL](IP/vivado_ip/hdl/vhdl/) · [Vitis 驱动](IP/vivado_ip/drivers/)。

本仓库从 `ff_vit_re` 和 `FF_Vit` 两个原工程中整理一条可追溯主线，包含微调、
W3/W8 混合精度量化、整数/LUT 导出、HLS、Vivado、Vitis、三个任务的部署 BIN、
Python 前端、云边协同 GUI 和最新独立功耗采样程序。
不包含原始图像数据集、全测试集转换的批量图像 BIN 和临时构建缓存。
模型配方、构建报告与工件身份随源码成套保留。

## 先检查完整性

安装 Git LFS 后克隆，确保下载真实二进制，不能只拿到 LFS 指针：

```bash
git lfs install
git clone https://github.com/123Ve/FF-ViT-Reproducible.git
cd FF-ViT-Reproducible
git lfs pull
python3 -B tools/verify_repository.py
```

本地目录或独立 ZIP 解压后直接执行最后一条即可，只需 Python 标准库。
检查内容为文件清单、SHA-256、原文件身份以及三个任务的 BIN 大小/格式；不操作板卡。

## 目录与入口

| 路径 | 内容 |
| --- | --- |
| `IP/` | 独立展开的 E07 HLS 源码和完整 Vivado IP，可直接浏览或导入 |
| `deploy/plantvillage/` | PlantVillage 权重、单帧 S16 DMA 输入、1000-logit 参考输出、配套 Patch/Head ROM |
| `deploy/nwpu/` | NWPU-RESISC45 对应部署文件 |
| `deploy/imagenet/` | ImageNet 原始严格 S3 对应部署文件，输入为逻辑 patch 顺序，由 testbench 转 DMA 顺序 |
| `deploy/tasks.json` | 三套文件的 SHA、输入格式及任务配置 |
| `FF_Vit/E04_weight_schedule/E07_timing_300mhz/` | E07 candidate05：完整 HLS 源码、BD、Vivado Tcl、Vitis 源码、基准 BIT/XSA/BOOT、实现报告 |
| `ff_vit_re/validation/u3_full_board_test_20261014/` | PlantVillage/NWPU 各自 U3 HLS/ROM、硬件构建脚本和准确率测试固件 |
| `artifacts/tasks/{plantvillage,nwpu}/` | 两个任务对应的启动镜像 |
| `ff_vit_re/validation/e07_u3_progressive_qat_20261010/` | PlantVillage/NWPU 最终 U3 训练、最佳检查点、整数参数、拟合和精度报告 |
| `ff_vit_re/image1k_hls_s3_original/` | ImageNet 原始严格 S3 训练/整数导出、最佳检查点、完整 HLS 测试入口和四个样例 |
| `ff_vit_re/quantization_final/` 等 | 主线实际导入的共享数值实现、父检查点、初始化参数与数据适配器 |
| `ff_vit_re/Cloud_test/` | 云边 TCP 业务、Flask/Plotly GUI、Windows 前端、网络 PS 固件及匹配工件 |
| `ff_vit_re/validation/cloud_power_retest_20261121/independent_sampler/` | 原样保留的 r10 功耗复测发布包，含双核 ELF、三个配置的 BOOT/SD_CARD、PowerShell 与分析程序 |
| `artifacts/bsp/`、`artifacts/ip/` | Vitis 2025.1 原始 BSP/启动源码及 E07 HLS IP |
| `provenance/` | 原目录到仓库的文件映射、哈希、模型来源和环境记录 |
| `tools/` | 完整性检查、可写工作区生成、GitHub 上传入口 |

保留 `ff_vit_re` / `FF_Vit` 两个层级，是为了维持现有 Python 相对导入与硬件文件引用。
Python 主线采用已整理的严格 S3/U3 依赖闭包；少量旧模块是共享依赖，不是要求再跑一套旧流程。

## 版本配套关系

| 模型/镜像 | 模型与工程文件 |
| --- | --- |
| PlantVillage U3 | 整数软件 Top-1 98.5712%；任务专用 QAT 检查点、整数参数、HLS/ROM 与启动文件 |
| NWPU U3 | 整数软件 Top-1 88.8222%；任务专用 QAT 检查点、整数参数、HLS/ROM 与启动文件 |
| ImageNet 原始严格 S3 | 整数软件 Top-1 68.156%；最佳检查点、整数参数、HLS 测试入口及参考样例 |
| E07 基准 | 实现频率 300.215 MHz、历史裸机基准 348.655 FPS；BIT/XSA/ROM/权重成套保存 |

`board_300mhz/imagenet_frozen_50k_test/` 保存 E07 的完整测试源码与启动镜像；
ImageNet 严格 S3 软件模型有独立的参数和 HLS 目录。使用时按模型配套选择
权重、ROM、启动镜像和主机配置。

`deploy/` 是最小模型样例，不是全测试集准确率固件的完整 SD 卡。
全量测试固件还需 INDEX、分片输入和 Golden 数据；使用归档的 prepare 脚本，
从你另外提供的数据集生成。本仓库没有复制整套图像。

## Python 与 GUI

GUI 使用独立的小环境，不需要为它安装 PyTorch：

```bash
python3 -m venv .venv-gui
source .venv-gui/bin/activate
pip install -r requirements-gui.txt
cd ff_vit_re
python -m Cloud_test.run_e07_measurements --help
python -m Cloud_test.run_e07_measurements --gui --duration 15 --streams 1
```

采集器监听 `192.168.10.1:5001`，GUI 位于本机 `127.0.0.1:18082`。
运行前按 runbook 配置专用网卡并准备匹配 SD 镜像。GUI 默认使用 V2.5 网络固件，
Windows 启动/打包脚本与说明一并保存。GUI 网络固件和 r10 双核采样固件
分别使用各自配套的主机程序。

## Windows 独立功耗采样

```powershell
$Pkg = (Resolve-Path '.\ff_vit_re\validation\cloud_power_retest_20261121\independent_sampler').Path
& "$Pkg\Run-PowerRetest.ps1" -CheckOnly -Diagnostic16
```

后续 `-PrepareSD`、`-Acceptance`、`-Formal`、`-Target120Only`、`-Analyze` 的具体参数，
按该目录原 `README_CN.txt` 执行。该发布包内部不增加文件，以保留原清单校验。

严格 18 路、排除 Rail 7 的 17 路诊断、排除 Rail 7/15 的 16 路诊断保持分离；
三种模式都记录全部 18 路原始值和质量标志。Target120 是 **4 路 × 30 FPS 输入目标**，
每条件 120 秒、5 次重复；实际完成 FPS、完成帧数和丢帧仍需实测。

## 构建与训练

先生成独立可写工作区，避免覆盖冻结工件：

```bash
python3 tools/create_workspace.py --output "$PWD/work/reproduction"
```

该入口复制工程、重定位历史绝对路径、解包 E07 IP，并放入原始 BSP。
路径修改逐项记录在 `WORKSPACE.json`；不修改算法、数值数组、权重或归档 BOOT。
可通过 `--plantvillage-root`、`--nwpu-root`、`--imagenet-train`、`--imagenet-val`
接入外部数据集。具体 HLS/Vivado/Vitis 命令和训练主线见 [构建指南](docs/REPRODUCE.md)。

## 上传 GitHub

仓库地址：[123Ve/FF-ViT-Reproducible](https://github.com/123Ve/FF-ViT-Reproducible)。
如需保存到另一个仓库，可登录后使用上传脚本：

```bash
gh auth login
bash tools/publish_github.sh 你的账号/FF-ViT-Reproducible private
```

如果你选择公开仓库，将 `private` 改为 `public`。不要将访问令牌写进源码或 README。
BIN、BIT、XSA、ELF、检查点等由 Git LFS 管理；普通 Git 大文件限制见
[GitHub 官方说明](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github)，
LFS 额度见 [存储和带宽说明](https://docs.github.com/en/billing/concepts/product-billing/git-lfs)。
源文件版权和授权情况见 [NOTICE.md](NOTICE.md)。
