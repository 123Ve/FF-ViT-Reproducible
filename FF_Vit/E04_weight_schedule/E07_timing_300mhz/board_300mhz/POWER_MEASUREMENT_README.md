# E07 帧率与功耗上板测量说明

本目录为独立 E07 版本的 PS 测量程序和部署工具，E06 源码、RTL、权重及已有上板文件保持冻结。只有布局布线、时序、数值回归和版本身份检查通过后，构建流程才生成部署文件。本文说明测量协议，不代表 E07 已经通过板级验证。

## 时钟与部署文件

时钟配置为 PS PL0 输入 249.975021 MHz，经 MMCM 的 M=30.625、D=6、O=4.25 得到约 300.215099 MHz。该数值来自时钟配置，不是示波器测量。最终实现约束和报告在 `../results/candidate05/clock.txt` 与 `timing.rpt`；后续导出阶段的重新验收及构建日志保存在 `../results/candidate05/board_release`。`board_resume` 保留第一次独立 BIT 导出及 XSA 文件关联失败的日志。不能用旧版本 WNS 代替本次结果。

验收通过后的部署目录分别为：

| 目录 | 用途 |
| --- | --- |
| `deploy` | 纯推理测试，预热后计时 100 个串行完整帧 |
| `deploy_power` | 10 次纯帧率批次测量及 10 次功耗测量 |

使用 FAT32 SD 卡，将所选目录中的 `BOOT.BIN`、`input.bin`、`weights.bin`、`output.bin` 放入卡的根目录，不要将整个目录嵌套放入卡中。功耗版也必须命名为 `BOOT.BIN`，不能命名为 `BOOT_POWER.BIN`。沿用已成功运行 E06 的 SD 启动模式和串口设置。

每次运行功耗版会创建或覆盖 `FPS_SUM.CSV`、`PWR_RAW.CSV`、`PWR_PHS.CSV`。上电前先备份同名旧结果和旧 BOOT.BIN；不要混用 E06 的 BIN 与 E07 的版本身份记录。`manifest.csv` 保存部署文件大小、来源与 SHA-256。

## 测试流程和耗时

程序读取同一份输入、12 层权重和 1000 类参考输出，保持 196-token 模型及原整数语义。执行两个预热帧后检查输出，然后进行下列测试：

1. 纯帧率测试执行 10 个批次，每批次 100 帧。计时窗口内不读 INA226、不写 SD、不输出串口；批次结束后保存结果和检查最后一帧的 1000 个 logits。
2. 功耗测试执行 10 次，每次依次测量 `PL_CONFIGURED_IDLE`、`PS_ACTIVE_NO_PL`、`FFVIT_SUSTAINED_LOAD`，每阶段约 30 秒。每个持续负载阶段结束后检查最后一帧输出。
3. 功耗样本先存在 RAM 中，在阶段计时结束后写入 SD。完成后打印 `POWER_TEST_PASS files=FPS_SUM.CSV,PWR_RAW.CSV,PWR_PHS.CSV`。

功耗阶段合计约 15 分钟，加上输入读取、预热、纯帧率测试和 SD 写入时间。功耗阶段主要在每次 90 秒测量及相应文件写入完成后打印 `POWER_REPEAT`，这一期间串口无新输出不必然表示卡死。若出现 `INIT_FAIL`、`POWER_MONITOR_UNAVAILABLE`、`INPUT_OR_LOG_INIT_FAIL`、`FPS_MEASUREMENT_FAIL` 或 `POWER_MEASUREMENT_FAIL`，保留完整 UART 和已有 CSV，不作为成功结果使用。

输出一致性检查覆盖预热结束、每个 100 帧批次的最后一帧、每个持续负载阶段的最后一帧，不能表述为所有运行帧均逐帧检查。

## 帧率和延迟口径

所有帧串行执行，一帧输入 DMA、PL 推理、输出 DMA 和完成确认结束后才启动下一帧，`FRAME_OVERLAP=NO`。纯帧率计时包含 cache 操作、PS 调度、DDR 到 PL 输入传输、推理计算、输出到 DDR 和完成确认；不包含 SD 文件读取、输入重新排布、UART/SD 日志写入、INA226 采样。

对每批次，用原始定时器记录计算：

`FPS = frames × TIMER_HZ / ticks`

`平均延迟 ns/frame = ticks × 10^9 / (frames × TIMER_HZ)`

总吞吐量用全部批次的总帧数除以总计时时间，不简单平均单帧延迟倒数。`TIMER_HZ` 使用该镜像 UART 输出值，不把 PL 时钟误用为 PS 定时器频率。批次均值的标准差不等于逐图像延迟标准差。

功耗负载窗口每帧启动后读取一条 INA226 电源轨，因此其 FPS 与纯帧率批次分开报告；计算能量/帧和 GOPS/W 时使用与功耗匹配的负载窗口 FPS，不能混用纯帧率结果。固定输入重复推理不是整个验证集的精度或图像解码吞吐测试。

## 功耗范围和采样

功耗范围是 `zcu102_ina226_rails.csv` 所列 18 路 INA226 受监测电源轨之和，不是墙插总功耗。轨道轮询分组名称 PS 和 PL 不能直接等同于 PS/PL 逻辑功耗，因为其中还包含 DDR、I/O 和收发器供电。

| 轮询分组 | 电源轨 |
| --- | --- |
| PS 10 路 | VCCPSINTFP、VCCPSINTLP、VCCPSAUX、VCCPSPLL、MGTRAVCC、MGTRAVTT、VCCO_PSDDR_504、VCCOPS、VCCOPS3、VCCPSDDRPLL |
| PL 8 路 | VCCINT、VCCBRAM、VCCAUX、VCC1V2、VCC3V3、VADJ_FMC、MGTAVCC、MGTAVTT |

每条记录包含电源轨、采样时间、分流电阻、电压、电流、功率和温度。空闲及 PS 活跃阶段约每 5 ms 轮询一条轨，18 路一轮名义上约 90 ms；负载阶段每个完整帧读取一条轨。18 路不是同时采样，应从原始时间戳计算各轨实际采样间隔。主机轮询频率不是 INA226 内部 ADC 转换频率，本测试不声称测量了后者。

`PL_CONFIGURED_IDLE` 保留配置后的 PL 时钟和 PS 轮询开销；`PS_ACTIVE_NO_PL` 是不启动推理、PS 执行固定输入校验遍历的工作状态；它们均不代表关机功耗。各重复中先对每条轨求均值，再求 18 路均值之和。负载减空闲是整组受监测电源轨的增量，不能命名为纯 PL 动态功耗。

## 结果文件和汇总

完成后保存三份 CSV、完整 UART、部署 `manifest.csv` 与对应的时序/资源报告。使用本目录脚本：

```bash
python3 scripts/summarize_fps.py /path/to/FPS_SUM.CSV /path/to/FPS_SUMMARY.json
python3 scripts/summarize_power_measurement.py /path/to/PWR_RAW.CSV /path/to/PWR_PHS.CSV /path/to/POWER_SUMMARY.json UART中的TIMER_HZ
```

功耗汇总前确认每次三个阶段完整、各阶段均包含同样的 18 路电源轨、无漏采或数值失败。现有功耗汇总工具不替代完整性检查。10 次重复的功耗置信区间采用 t 分布；能量/帧用受监测负载功耗除以匹配的 FPS。每帧有效工作量为 1,246,416,384 MAC，若按每 MAC 两次操作换算 GOPS，必须明确此约定。

只有收到本版本上板成功的 UART 与 CSV 后，才能报告实测 FPS、延迟、功耗和能效；构建通过不等于板级测试通过。
