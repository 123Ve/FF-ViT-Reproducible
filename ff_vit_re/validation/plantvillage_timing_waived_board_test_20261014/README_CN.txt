PlantVillage 严格 E07 U3 全测试集：时序未收敛实验包

重要：本包按用户明确要求忽略当前 setup 时序失败，仅用于物理板卡实验。
不是时序合格发布版。原正式发布门槛未修改，原权重、LUT、运算源码和时钟未修改。
PL 时钟 300.21509875 MHz；WNS=-0.115 ns，TNS=-31.367 ns，781 个 setup 违例端点。
因此可能出现输出错误、运行不稳定或超时；即使本次板测通过，也不能证明时序闭合。
此包不是 BRAM INIT 局部替换试验的混合模型；它使用完整 PlantVillage 固定 ROM。

测试集：5459 张、38 类，与冻结的完整软件测试集成员/顺序/预处理一致。
软件整数/LUT预期 Top-1：5381/5459 = 98.57116688%，不是本包的板级实测值。
复用已编译的 PlantVillage 全量精度测试程序，不复用 NWPU 或 Local4 的 BOOT.BIN。
两次暖启动、每帧输入/Golden CRC 和全部 1000-logit 逐码核对均保留。

使用：
1. 先备份 SD 卡已有内容，将 SD_CARD/ 下全部文件复制到 FAT32 SD 卡根目录。
   必须同时复制 BOOT.BIN、weights.bin、INDEX.BIN、WARMUP.I/G、所有 Ixxx/Gxxx.BIN。
2. ZCU102 选择 SD 启动，连接 UART：115200 baud、8N1，然后上电。
3. 保留完整串口日志。正常全量完成应出现 ACCURACY_RUN_COMPLETE。
   SD 卡生成 RESULT.CSV、LOGITS.BIN、ACCSUM.TXT。
   暖启动失败、超时、CRC 错误、帧数不足或输出不匹配均应如实保留，不能视为成功。
4. 测试后将三个结果文件和串口日志返回，结合本包 identity.json 与 Golden 复核。
   原正式包的 summarize_board.py 会拒绝本实验状态；不要把 identity 改成正式合格状态。
5. 再次测试前备份并移走旧 RESULT.CSV、LOGITS.BIN、ACCSUM.TXT，以及可能存在的
   ACCTMP.TXT；程序拒绝覆盖旧结果。不要删除模型和输入文件。

计时边界：ACCSUM.TXT 的 INFERENCE_TICKS 覆盖 PS/cache/DMA/PL/完成确认，
不含 SD、CRC、Golden 比对、输出日志和串口。DATASET_WALL_TICKS 包含辅助开销。
这是全量精度测试程序，不是 10x100 帧常驻 DDR 的独立持续吞吐基准。
实际板级精度、吞吐、稳定性均需物理板卡运行；生成 BOOT.BIN 不表示已经测量。
