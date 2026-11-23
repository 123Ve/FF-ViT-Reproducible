# ImageNet-1K 原始 HLS 位宽实验数据

| 阶段 | Top-1 (%) | Top-5 (%) | 样本数 | 评价类型 |
|---|---:|---:|---:|---|
| FP32 197-token | 72.164 | 91.110 | 50000 | historical_software_50k |
| FP32 HLS-196 | 72.140 | 91.090 | 50000 | historical_software_50k |
| W3 PTQ HLS-196 | 6.392 | 17.102 | 50000 | historical_software_50k |
| W3 QAT HLS-196 | 70.020 | 89.870 | 50000 | software_surrogate_50k |
| MLP LN2 s3 / GELU u3 QAT | 69.088 | 89.448 | 50000 | software_surrogate_50k_model_selection |
| Attention + MLP strict QAT | 66.954 | 87.986 | 50000 | software_surrogate_50k_model_selection |

HLS 固定样本：4；逐位比较状态：PASS。
数据完整性：尚缺 exact50k。

所有软件正式结果采用 resize 248 / center crop 224 / bicubic / ImageNet mean/std。
FP32 与 W3 PTQ 复用已归档的同协议 50k 报告，来源及 SHA-256 见 completeness.json。
69% 是目标；surrogate QAT 精度不等于整数部署精度，HLS 少量样本也不是 50k 准确率。
MLP/Attention 使用完整 50k 验证精度选择 epoch，因此该验证集不是选模后的独立无偏测试集。
敏感度正式论文数据应使用 v2：修正 Attention residual 必须同时进入 LN2 与 MLP skip 的语义。
现有 QAT 的渐进层次顺序来源于 v1 排名；修正后的 v2 结果另行保存，不能宣称训练使用 v2 排名。
