E07 冻结模型：ImageNet-1K 完整 50,000 张验证图像上板测试
=======================================================

本包复用已支持最多 50,000 张图像的 PS 测试程序，重新编译 PS 和打包 BOOT.BIN。
E07 HLS 源码、RTL、ROM、bitstream 和主干 weights.bin 均不修改，未运行 HLS/Vivado。
这是 CURRENT_E07_NOT_OTHER_IMAGENET_QAT_MODEL，不加载另一套 ImageNet QAT 参数。
准确率必须由本次完整板测产生，不沿用软件模型、1000 图子集或其他版本的准确率。

数据按本地 14 个 validation Parquet 分片的文件名及行号顺序导出全部 50,000 张。
导出验证图像身份唯一、标签范围为 0..999，并保存原图/输入 SHA256 和每图输入 CRC32。
类别覆盖与分片哈希见 dataset_identity.json；图像与标签映射见 SAMPLES.CSV。
原图 original_images/ 留在电脑即可，不复制到 SD。

预处理沿用原冻结测试协议：RGB，短边 248 bicubic，中心裁剪 224，float32 /255，
ImageNet mean=[0.485,0.456,0.406]、std=[0.229,0.224,0.225]，乘 64 后 ties-to-even
取整并限制到 int16，patch=16x16，逻辑 [196,768]，DMA [98,768,2]。
输入保留全部 196 个 patch；CLS 替换由未修改的 E07 PL 执行。

SD 卡部署
---------
1. 将旧 BOOT.BIN 和旧结果备份到电脑，断电操作 SD 卡。
2. 使用可写的 FAT32 启动分区，建议 32 GB 或更大的卡。
3. 将 deploy/ 内这些文件放到 SD 根目录：
   BOOT.BIN
   weights.bin
   input.bin
   output.bin
   INDEX.BIN
   I000.BIN 至 I049.BIN（全部 50 个文件，不可漏片）。
   input.bin/output.bin 是基准逐码一致性检查文件，不是验证集分片，不能省略。
4. 输入分片合计 15,052,800,000 B（15.0528 GB，约 14.019 GiB）。
   每片 301,056,000 B，小于 FAT32 单文件限制。
   LOGITS.BIN 最终为 200,000,000 B；另有 CSV 和汇总。复制后建议留至少 1 GB 可写空间。
5. SD 根目录不能有旧 RESULT.CSV、LOGITS.BIN、ACCSUM.TXT（移动到电脑备份）。
   程序采用 FA_CREATE_NEW，不覆盖已有结果；否则可能 LOG_OPEN 失败，或结束汇总失败。
6. 安全弹出 SD，启动板卡并保存完整串口日志。

预期日志和结果
-------------
BASELINE_BIT_EXACT_MISMATCHES=0
DATASET_FRAMES=50000 CHUNK_FRAMES=1000
PROGRESS=100/50000 ...（每 100 张更新）
...
COMPLETED_FRAMES=50000 ...
ACCURACY_RUN_COMPLETE files=RESULT.CSV,LOGITS.BIN,ACCSUM.TXT

只有完整完成标记、50000 条 CSV 记录和 200000000 B logits 全部对账后，才能报告
完整 ImageNet-1K 验证集准确率。基准一致性检查通过不等于验证集准确率高。
中途失败或断电的结果仅为部分结果；当前程序不支持断点续跑。

取回结果与复核
-------------
将 RESULT.CSV、LOGITS.BIN、ACCSUM.TXT 复制到电脑新建 board_results/ 目录，然后执行：
/home/user/anaconda3/envs/vlm_token/bin/python -B summarize_results.py board_results --dataset deploy
也可在 SD 原样保留 INDEX.BIN 与全部数据，电脑只取回上述三个结果文件。
复核工具从 S19 解码 logits 重新计算 Top1/Top5，并核对标签、输入 CRC、数量和计时。

性能计时边界
-----------
INFERENCE_TICKS 包括 PS cache/DMA 调度、PL 推理、权重 DDR 读取和完成轮询，
不包括 SD 输入读取、CRC、argmax、结果写盘和串口。
DATASET_WALL_TICKS 包括上述 SD/CRC/argmax/写盘/进度串口开销；两种 FPS 分开报告。
不采用跨帧流水。按历史 348.655 FPS，50000 次纯推理约 143 秒，但本测试还读取
约 15 GB SD 数据并校验、写盘，整体运行明显更久，不能用 143 秒估算完整测试耗时。

冻结身份
-------
weights.bin SHA256:
0fac7e4cd09ae8367e5c8dfd5cb469473780055feccf9569a8376419028e2cd7
design_1_wrapper.bit SHA256:
2fedb6d70a0916fc9aebfdf3141008690685c0dbd1b5bab0ae58821564ef1037
完整工件哈希见 identity.json 和 manifest.csv。
