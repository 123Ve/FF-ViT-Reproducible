# ImageNet-1K 原始 HLS 位宽敏感度与严格 QAT 设计

## 目标

在不修改现有 `image_lianghu`、PlantVillage 量化目录和 HLS 工程的前提下，建立一套独立、可复现的 ImageNet-1K 实验。实验复刻 PlantVillage 的主量化顺序，严格保持最初 HLS 位宽，生成论文可用的算子敏感度、逐层敏感度、阶段精度、严格低位宽 QAT、exact 整数模型及 HLS C 仿真证据。

Top-1 `69%` 是优化目标，不是通过改变位宽强行满足的门槛。若严格位宽的真实结果低于 69%，必须保留并报告真实结果，不得用 s8/u8 分支替代主结果。

## 隔离和输入

- 新实验根目录：`/home/user/Desktop/ff_vit_re/image1k_hls_s3_original`。
- ImageNet-1K 训练集只读引用：`/home/user/Desktop/ff_vit_re/image_train/ILSVRC2012_img_train`，1,281,167 张。
- ImageNet-1K 验证集只读引用：`/home/user/Desktop/ff_vit_re/imagenet_val/data`，50,000 张。
- FP32 输入 checkpoint：`image_1k/deit_tiny_patch16_224-a1311bcf.pth`。
- HLS-196 FP32 checkpoint：`image_lianghu/checkpoints/fp32_hls196.pth`。
- W3 QAT 父 checkpoint：`image_lianghu/checkpoints/w3_qat_500k_headrefit/best.pth`。
- 既有严格 S3 checkpoint 仅作为对照或 warm-start 候选；正式运行必须记录父 checkpoint 哈希，不得覆盖原文件。
- Python 环境：`/home/user/anaconda3/envs/vlm_token`。

## 不可改变的 HLS 数值契约

该契约以 `/home/user/Desktop/FF_Vit/flash_vit_2/src/block0.cpp` 的最初 PlantVillage 类型定义为权威：

| 边界/对象 | 固定位宽 |
|---|---|
| Q/K/V/O、FC1/FC2 权重 | signed 3-bit |
| LN1 输出 | signed 3-bit |
| Q、K、V 输出 | signed 3-bit |
| Attention A / projection 输入 | signed 3-bit |
| Softmax 输出 | unsigned 3-bit |
| LN2 输出 | signed 3-bit |
| GELU 输出 | unsigned 3-bit |
| Attention Q/K/V/R/A/O 中间结果 | s12/s11/s11/s10/s11/s13 |
| Attention residual 输出 | signed 15-bit |
| MLP1、MLP2 中间结果 | signed 11-bit、signed 13-bit |
| block feature map | signed 13-bit |
| Head LayerNorm、head weight | signed 8-bit |
| Head bias/MAC | signed 19-bit |

所有主线配置启动时必须通过 contract validator；出现 GELU >3 bit、LN1/LN2 >3 bit、Q/K/V/A >3 bit 或权重 >3 bit时立即失败。宽位宽实验只能标记为非主线 ablation，不能进入主结果。

## 评价协议

- 标准 ImageNet-1K crop09：bicubic resize 到 248、center crop 224、ImageNet mean/std。
- FP32 标准 197-token结果和 HLS-196 结果分开记录。
- 激活敏感度的直接基线为已接受 W3 QAT HLS-196 checkpoint，因为 PlantVillage 的激活敏感度同样是在 W3 权重恢复后进行。
- 快速开发使用确定性的每类等量 stratified probe；论文表格使用完整 50,000 张验证集。
- 每条结果记录 Top-1、Top-5、相对基线下降百分点、样本数、checkpoint/config/data 哈希、运行时长及设备。

## 敏感度实验

### 算子敏感度

在其他边界保持浮点/父模型状态时分别启用：LN1、Q、K、V、A、Softmax、LN2、GELU、FC1 W3、FC2 W3、Attention residual、MLP residual。另运行与 PlantVillage 对齐的组合：QKV、Attention-all、MLP-all、All-A3。

每个实验除分类精度外，还采集量化前后张量 MSE、MAE、cosine similarity、SQNR、clip/saturation rate、零值比例和观测范围。量化 scale 先由固定校准集上的直方图 MSE 搜索得到；论文结果不得使用验证标签调 scale。

### 层敏感度

对 12 个 transformer block 分别执行三种单层扰动：Attention-only、MLP-only、whole-block。其余 11 层保持父模型状态。输出 36 个完整 50k 结果、按 Top-1 drop 排名以及层号×扰动类型矩阵。

### 累计敏感度

按从低敏感到高敏感和从深层到浅层两种顺序累计启用 block，生成精度随量化层数变化的曲线。该曲线用于选择 QAT progressive schedule，但不得改变固定位宽。

## 严格位宽 QAT

主顺序保持 PlantVillage 流程：FP32/HLS-196 → W3 PTQ → W3 QAT → MLP 激活 QAT → Attention 激活 QAT → LUT/exact → head → HLS。

精度优化仅允许改变训练方法：

- 固定种子 `20260923`，使用完整 1,281,167 张训练集；校准集和 selection set 与训练/正式验证用途隔离。
- FP32/HLS-196 teacher 固定，采用 logits KD；增加 block output、Attention output 和 MLP output feature reconstruction loss。
- 使用直方图 MSE 初始化每 block scale，再用 LSQ 风格梯度学习 scale；scale 仍对应同一 3-bit码域。
- 根据敏感度从低敏感 block 逐步启用严格量化；每次扩展后进行局部恢复，再进行全模型联合 QAT。
- MLP 主线必须同时保持 LN2 s3、GELU u3、M1 s11、M2 s13、feature map s13。
- Attention 主线必须同时保持 LN1/Q/K/V/A s3、Softmax u3、O s13 和 residual s15。
- 使用 EMA checkpoint、cosine scheduler、warmup、gradient clipping 和早停；只根据固定 selection set 选 checkpoint，最终统一跑 50k。
- 若训练停滞，允许在下述固定预算内增加 epoch、调整学习率/KD/feature loss 权重或改变 block 启用顺序；不允许改变主线位宽。MLP 主运行预算为 4 个 progressive 全数据 epoch 加 8 个 joint epoch，最多再运行 3 个两 epoch 恢复分支；Attention 主运行预算为 4 个 progressive 全数据 epoch 加 10 个 joint epoch，最多再运行 3 个两 epoch 恢复分支。每个恢复分支只允许从预先记录的 LR、KD 和 feature-loss 网格中选择，所有尝试都必须进入报告。

阶段目标为 MLP 严格主线尽量达到或超过 69%，最终 Attention+MLP 严格主线尽量恢复到 69%。目标未达到时继续执行预设恢复分支，并在达到预算上限后报告最优真实结果及差距。

## Exact 与 HLS

- 从最终 checkpoint 生成每 block scale、整数 multiplier/shift、LN/GELU/Softmax LUT、权重 bin 和测试 fixture。
- 软件 exact 模型复现 HLS 的 rounding、clamp、wrap、LUT addressing 和 residual requant。
- 固定样本执行逐层 bit comparison；所有层一致后才运行 HLS C 仿真分类样本。
- 软件 surrogate、软件 exact、HLS C 仿真结果分别报告；少量 HLS 样本只能证明逐位一致，不能冒充 50k FPGA 准确率。
- 不修改 `/home/user/Desktop/FF_Vit/flash_vit_2`；需要的 HLS 源文件复制到新实验目录内形成自包含副本。

## 输出

- `config/original_hls_s3.yaml`：冻结位宽和数据协议。
- `metadata/`：输入文件、环境、数据清单和 SHA-256。
- `reports/operator_sensitivity.{json,csv,md}`。
- `reports/layer_sensitivity.{json,csv,md}`。
- `reports/cumulative_sensitivity.{json,csv,md}`。
- `reports/stage_accuracy_summary.md`。
- `checkpoints/`：每阶段 best/latest 与内嵌 recipe。
- `exact/`：LUT、整数参数、exact 评价及逐层一致性证据。
- `hls/`：复制的 HLS 源、bin、fixture、C 仿真日志和报告。
- `paper/`：可直接引用的表格、图表数据和实验方法说明。

## 验收标准

1. contract validator 能拒绝任何主线位宽漂移。
2. 所有敏感度实验使用同一 checkpoint、同一 50k 协议并可断点续跑。
3. 得到完整算子、36 项逐层和累计敏感度结果，无缺项。
4. 得到 FP32、W3 PTQ、W3 QAT、MLP S3/U3 QAT、Attention S3 QAT、exact、HLS 各阶段数据。
5. 最终主线严格保持原 HLS 位宽；如 Top-1 未达到 69%，报告已执行的恢复分支、最佳值和可复核证据。
6. 新目录以外的文件内容不被修改。
