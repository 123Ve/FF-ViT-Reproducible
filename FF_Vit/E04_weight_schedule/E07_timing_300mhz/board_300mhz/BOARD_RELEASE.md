# E07 上板文件与实现结果

E07 的 300 MHz 级实现已完成时序验收、BIT/XSA 导出、FSBL/PMU/PS 程序编译及启动镜像打包。构建于 2026 年 10 月 3 日 12:09:32 完成，返回码为 0。E06 工程及其 HLS 源码保持冻结。E07 尚未收到板级运行记录，本文不报告实测 FPS 或功耗。

## 使用哪个镜像

| 镜像 | 测试内容 | 主要输出 |
| --- | --- | --- |
| `deploy/BOOT.BIN` | 2 帧预热与参考 logits 检查，100 帧串行计时 | UART 原始 timer ticks 与平均 ns/frame |
| `deploy_power/BOOT.BIN` | 2 帧预热，10 次各 100 帧纯帧率计时，10 次各三个 30 秒功耗阶段 | UART FPS、`FPS_SUM.CSV`、`PWR_RAW.CSV`、`PWR_PHS.CSV` |

优先使用功耗版可以在同一次启动中获取纯帧率和匹配负载窗口的功耗。先备份 SD 卡旧 BOOT.BIN 和同名结果 CSV，再把所选部署目录的 `BOOT.BIN`、`input.bin`、`weights.bin`、`output.bin` 放到 FAT32 根目录。不要同时复制两个目录的 BOOT.BIN，不要改名成 BOOT_POWER.BIN。功耗测量约需 15 分钟，另加文件写入时间。

两个镜像的 FSBL、PMU 和 PL bitstream 相同，只有 A53 测试程序不同。GEM3/MDIO 的硬件配置保留，但这两个程序不包含云端或以太网吞吐测量软件。详细协议见 [POWER_MEASUREMENT_README.md](POWER_MEASUREMENT_README.md)。

## 最终硬件验收结果

以下为 Vivado 2025.1 完成布线后物理优化的结果，不是 HLS 估计，也不是板级频率实测。目标器件为 `xczu9eg-ffvb1156-2-e`。

| 指标 | 最终结果 |
| --- | ---: |
| 配置 PL 输出频率 | 300.21509875 MHz |
| 核心生成时钟约束周期 | 3.331 ns |
| Setup WNS / TNS | +0.023 ns / 0 ns |
| Hold WHS / THS | +0.010 ns / 0 ns |
| Pulse width 最差裕量 / 总负裕量 | +0.165 ns / 0 ns |
| Setup、hold、pulse width 失败端点 | 均为 0 |
| 未约束内部端点及无时钟端点 | 均为 0 |
| 完整布线的可路由网络 | 362,869 / 362,869 |
| 布线错误 | 0 |
| LUT | 218,759，79.82% |
| FF | 188,403，34.37% |
| DSP | 736，29.21% |
| BRAM36 等效 tile | 505，55.37% |

时钟来源为 PS PL0 的 249.975021 MHz，经 MMCM 的 M=30.625、D=6、O=4.25 得到配置输出频率。Setup 裕量为 23 ps，较紧，不能据此宣称有较大的超频空间。DRC 无 Error/Critical Warning；保留了 DSP 流水线和 RAM 等原生警告。Vitis 的生成 BSP/PMU 编译也有警告，但全部构建阶段返回 0，未修改 E06 或为消除警告重新综合硬件。

## 数值与版本身份

HLS C 回归包含 3 次完整 12 层推理，每次检查 1000 个 logits，与既有参考完全一致。该证据不是 E07 RTL co-simulation 或板级验证；最终还需收到上板 UART 的一致性检查及 CSV。测试保持 196 tokens、原整数运算和量化语义，未增加逻辑 MAC 通道数。

E06 冻结清单的 1063 项文件哈希通过检查；E07 复用 HLS 源码/IP 身份检查通过；22 项发布验收测试和 10 项 PS/部署测试通过。两个部署目录中的输入、权重、参考输出与 `inputs` 相同，PL bitstream 与验收后的 XSA 内 bitstream 相同，部署 `manifest.csv` 的所有大小及 SHA-256 通过校验。

| 文件 | SHA-256 |
| --- | --- |
| `deploy/BOOT.BIN` | `7a52f3370ba076a97e18b3d833da0d108a5ed7d5f656e52c39f53817f35913dc` |
| `deploy_power/BOOT.BIN` | `08ed5689b4bde53b4d7580ff77e46535f7be8a720e5e11e98096dd8294060983` |
| 共同 PL bitstream | `2fedb6d70a0916fc9aebfdf3141008690685c0dbd1b5bab0ae58821564ef1037` |

实现报告与构建记录位于 `../results/candidate05/board_release`：`clock.txt`、`timing.rpt`、`route.rpt`、`utilization.rpt`、`drc.rpt`、`build_status.log`、`build.exit` 和各阶段日志。原先频率解析误判及第一次 XSA 文件关联失败的日志保留，不以删除失败记录的方式整理证据。

## 上板后保存的数据

请保存完整 UART 和三份 CSV。帧率是重复串行完整帧的端到端速率，没有跨帧重叠；SD 文件读取不包含在计时窗口内。功耗是 18 路 INA226 受监测电源轨的总和，不是墙插总板功耗。只有实际上板数据才能确定本版本的 FPS、延迟、功耗及相对 E06 的收益。
