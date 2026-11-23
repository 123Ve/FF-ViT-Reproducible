严格 E07 U3：完整留出测试集板级精度与输出码一致性测试

每套包只对应其 dataset.json 指定的数据集/检查点，不能混用另一套
BOOT.BIN、weights.bin 或输入/Golden 文件，也不能使用此前 Local4 BOOT.BIN。
PlantVillage：5459 张 / 38 类；NWPU-RESISC45：4500 张 / 45 类。
原始权重、量化尺度、LUT 和算术位宽未修改；每套包重新生成匹配的 Patch/Head ROM。
发布前完成所列 C-sim 向量、全量软件重放和布局布线资格检查。
这些检查不是板卡实测，也不是全测试集 RTL cosimulation。

1. 使用 FAT32 SD 卡（建议 8 GB 以上），先备份已有内容。
   将该 ZIP 解压后的所有文件放在 SD 卡根目录，不要额外套一层目录。
   BOOT.BIN、INDEX.BIN、weights.bin、WARMUP.I/G 和所有 Ixxx/Gxxx.BIN 必须完整。
   每个输入分块最多 1000 张，单文件不超过 FAT32 的 4 GB 限制。
2. ZCU102 设置 SD 启动，连接 UART（115200 baud，8N1），插卡重新上电。
   程序检查参数及整个索引的 CRC、两次暖启动输出码，然后逐帧串行推理。
   每帧核对输入/Golden CRC、全部 1000 个 S19 logits，统计有效类的 Top-1/Top-5。
   相同分数按类编号升序；该规则的软件预期结果见 dataset.json。
3. 完成后应出现 ACCURACY_RUN_COMPLETE，保留串口完整日志。
   SD 上新增 RESULT.CSV、LOGITS.BIN 和 ACCSUM.TXT。
   出现 FAIL/TIMEOUT/CRC 错误或完成帧数不足时，不能报告完整测试集精度。
   输出码不一致会记录在 CSV/汇总中，即使 Top-1 相同也不算 bit-exact 通过。
4. 关机后将结果与整套 SD 文件一起复制回主机，在包目录运行：
       python summarize_board.py . --output board_report.json
   需要 Python 3.11+ 和 NumPy；脚本会逐码复核并拒绝缺帧/错模型/错误汇总。
   inference_window_fps 只统计 PS/cache/DMA/PL/完成确认窗口，不含 SD、CRC、
   Golden 比对、输出日志和串口；dataset_wall_fps 包含上述测试辅助开销。
   不应把含 SD 文件读写的测试吞吐当作之前裸机常驻 DDR 的持续 FPS。
5. 再次测试前备份并移走上述三个结果文件以及 board_report.json；
   如果失败留下 ACCTMP.TXT，也需备份并移走该临时结果。
   程序拒绝覆盖已有结果。不要删除模型或输入文件。

输出含义：BIT_EXACT_PASS=YES、LOGIT_MISMATCHES=0 且全量帧完成，才可报告
该次物理板卡端到端 logits 与冻结整数软件 Golden 一致。
它不表示逐层内部节点都经过板级采样，不替代与原始 FP32 整网的比较。
dataset.json 内的软件准确率是上板预期值，未上板前不能标成 FPGA 实测精度。
