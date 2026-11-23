FF-ViT 严格 S3/U3 源码包
=======================

本包仅针对三个数据集的严格 S3/U3 主线路径：
  PlantVillage / NWPU-RESISC45：E07 U3 渐进 QAT + 有限位宽整数/LUT 导出。
  ImageNet-1K：image1k_hls_s3_original 原始严格 S3 路线。
不包含 Local4、Local8、Core4 或独立 S8 训练/部署实验入口及其结果目录。
S3 指主干关键有符号边界，Softmax/GELU 输出为 U3；Patch/Head、累加器、
残差及统计中间量仍按原合同保留较宽位宽，并非全网每个量都是 3 bit。

一、建议阅读/执行顺序（以下路径相对 ff_vit_re/）

PlantVillage：
  train_plantvillage.py                         浮点任务微调
  make_hls196_plantvillage.py                   HLS196 转换/微调
  ptq_stage1_weight3.py                         W3 PTQ 基线
  qat_weight3_hls196.py                         W3 QAT

NWPU-RESISC45：
  archive/nwpu_resisc45_ffvit/scripts/prepare_dataset.py
  archive/nwpu_resisc45_ffvit/scripts/train_fp32.py
  archive/nwpu_resisc45_ffvit/scripts/make_hls196.py
  archive/nwpu_resisc45_ffvit/scripts/quant/w3_ptq.py
  archive/nwpu_resisc45_ffvit/scripts/quant/canonical/qat_weight3_hls196.py
  quant/run_stage.py、manifest_adapter.py 用于对接 NWPU 数据清单。

这两套模型的严格 U3 主入口：
  validation/e07_u3_progressive_qat_20261010/progressive.py
    --dataset plantvillage 或 nwpu；--stage mlp / attention / both。
    先 MLP，再 Attention；原 progressive 配置分阶段启用 Block 6--11、
    3--11、0--11。真实超参数见 outputs/{dataset}/{mlp,attention}/recipe.json。
  validation/e07_u3_progressive_qat_20261010/exporter.py
    重新拟合整数倍率/移位、GELU、LN、Softmax 的 LUT，导出 E07 整数模型，
    并执行软件整网与局部误差评价。保持原 unsigned Head 合同。
  validation/e07_u3_progressive_qat_20261010/run_all.py
    两数据集串行训练/导出驱动；运行会实际训练，不是安装或校验命令。

ImageNet-1K 原始严格 S3：
  image_lianghu/scripts/evaluate_fp32.py        加载/评价外部预训练模型
  image_lianghu/scripts/run_w3_ptq.py           W3 PTQ
  image_lianghu/scripts/train_w3_qat*.py        W3 QAT、扩样与恢复训练
  image1k_hls_s3_original/scripts/train_strict_mlp.py
  image1k_hls_s3_original/scripts/train_strict_attention.py
  image1k_hls_s3_original/scripts/task4_calibrate.py
  image1k_hls_s3_original/scripts/build_exact.py
  image1k_hls_s3_original/scripts/evaluate_exact.py
  image1k_hls_s3_original/config/              严格位宽合同与训练配置
  image1k_hls_s3_original/src/exact.py          整数执行/拟合组合
  image1k_hls_s3_original/src/exact_fit.py      定点倍率、移位等参数拟合
  image1k_hls_s3_original/src/exact_head_fit.py Head 拟合
  image_lianghu/src/legacy_s3_lut.py           原始 S3 LUT 拟合公共实现

二、为什么仍保留少量旧目录代码

严格 U3 脚本实际导入 quantization_final/scripts、NWPU canonical、
validation/e07_u3_qat_20261010、softmax_u3_hls_20261010 等模块。
其中包含原模型控制器、整数包装、数据适配器、统计函数和拟合工具；这些是
依赖，不代表本包另提供一套 U8 主路线。部分公共模块仍含多个位宽选项，
原样保留以维持源码和哈希身份。没有修改算法或删除函数来伪装成纯 S3。

NWPU quant/pipeline.py 是 run_stage.py 的阶段表和解析器依赖，也含历史阶段。
不要把其完整默认流程或旧 stage4l 的 U8 默认入口当成最终 U3 导出流程。
最终两数据集请使用 progressive.py -> exporter.py；ImageNet 请使用
image1k_hls_s3_original/scripts 中的严格入口。

DEPENDENCY_ROLES.csv 标注主路线、初始化/公共依赖、配置与 HLS 参考源码。
ImageNet 上游只保留 W3 训练与严格 S3 动态导入所需的模块闭包，未打包独立
S8/Local4/Local8 实验入口。HLS 参考源码在 external_sources/FF_Vit/。

三、运行前提与证据边界

这是前一份源码快照的 S3 筛选包，所有选中的原工程文件逐字节不变。
包含微调/量化/LUT 源码及相应小型配方；不含原始图像、模型检查点、参数
数组、权重 bin 或 FPGA 构建产物。源码中原有 ROM 头文件常量随源码保留。
部分初始化依赖旧训练产生的检查点、范围统计和导出数组，需另行提供或生成。
ImageNet FP32 为外部预训练权重的加载/转换，不包含从零预训练的承诺。

保留项目层级。绝对路径、原检查点/工件绑定见 ABSOLUTE_PATHS.csv、
EXTERNAL_INPUTS.csv 及配置；迁移机器时需处理路径和数据依赖，不能直接
将历史哈希改成新文件哈希冒充原实验。EXTERNAL_INPUTS 为静态检出清单，
不保证涵盖运行时动态拼接的所有输入。大型生成清单未打包，见
EXCLUDED_METADATA.csv；相关清单生成脚本随 W3 初始化代码保留。

环境版本见 ENVIRONMENT_SNAPSHOT.json；主要需要 torch、torchvision、timm、
numpy、Pillow、pyarrow、PyYAML、pytest。HLS 检查另需相应 Vitis 工具。
这不是已备齐数据与权重的一键离线复现包。

解压后可运行：python verify_package.py
它只做包内哈希与静态语法检查，不训练、不推理、不写模型。
本次打包没有重新训练或测量精度，没有增加 HLS/RTL/FPGA 一致性证据。
