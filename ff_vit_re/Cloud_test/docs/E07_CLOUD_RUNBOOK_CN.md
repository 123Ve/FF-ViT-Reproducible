# E07 云端持续上传与英文 GUI 操作手册

## 发布内容与真实性边界

所有新增文件位于 `Cloud_test`，原 E07 工程不改动。

- 当前网络镜像：`Cloud_test/e07/boot/BOOT_E07_NET_V2_2_FINAL.BIN`，哈希见同名 manifest。
- 原网络镜像和 ZIP 保留作历史证据；V2 客户端默认拒绝旧固件身份。
- 复用 E07 candidate05 的 bitstream、XSA、FSBL、PMUFW 和数据；不修改 HLS/PL。
- 网络应用源码：`Cloud_test/e07/firmware/`；内部 E06 文件名是复用代码名称，运行身份是 E07。
- 当前 Windows 源码及 SD 包：`Cloud_test/dist/E07_Cloud_GUI_Win11_Source_V2_2.zip`。
- V2.2 修复无 tick BSP 导致 TCP 重传定时器不运行的问题，并删除 GUI 的 PlantVillage Top-1 卡片。
- V2.2 必须同时更新 SD 的 BOOT.BIN 和 Windows 源码/重新打包的 exe；旧 V2/V2.1 发布件保留。
- V2.2 物理测试状态：**NOT_RUN**。真实 lwIP 离线尾部丢失回归不能证明已上板通过。

实验使用 602,112 字节的已预处理固定输入 tensor，不是摄像头 JPEG。
主机回放输入，板卡核对其与 SD 上的已验证输入逐字节相同：

1. `replay_full`：PC → Edge → PC/Cloud，转发完整 tensor，不执行 FPGA 推理。
2. `replay_compact`：PC → Edge → FPGA → PC/Cloud，只返回推理与时序元数据。

完整模式不是“云端分类推理”基线，不能报告云端分类准确率或云端模型执行时延。
输入被严格限制为已验证固定样本，不能用未知图片套用该样本的参考输出。
1/2/4 流为同一板卡、同一 TCP 链路的多源时分复用，不是多摄像头实拍或多 FPGA 并行。
独立的并发 socket 多流压力测试仍可通过旧 `run_stream_measurements --mode simulation` 运行；其结果必须标为 host simulation。

V2 将接收窗口由 2048 增至 32768 字节，负载校验按 pbuf 分块 `memcmp`，
PS 应用采用 `-O2`。Full 使用最大 1460 字节的发送块，并在 `ERR_MEM` 时缩小申请；
保留 ACK 回调与主循环重试。超过 2 秒无入队进展输出 `BULK_STALL` 诊断。
这些是源码修订和构建配置，不代表新版板级吞吐已测量。详见 `E07_V2_OFFLINE_AUDIT_CN.md`。

V2.1 的最新上传记录中，2 流 Full 第 422 次尝试缺最后 1,044 字节后超时。
已确认实际 BSP 定义 `XTIMER_NO_TICK_TIMER=1`，旧平台的定时中断没有启动，
因此 TCP 超时重传无法推进。V2.2 使用 XTime 单调计数，每 250 ms 调用一次 `tcp_tmr()`，
即使 Full 已全部入队，仍继续驱动最后未确认片段的重传。没有简单加长客户端超时。
首发片段丢失的具体位置尚无抓包证据；该修复针对已确认的重传失效机制。

## 1. SD 卡与连接

下载并解压新 ZIP。将其中 `SD_CARD` 内的四个文件复制到 FAT/FAT32 SD 卡根目录：

```text
BOOT.BIN
weights.bin
input.bin
output.bin
```

`BOOT.BIN` 已是新 E07 网络版本，不能换回原 `deploy` 或 `deploy_power` 的串口版本。
也不能使用旧 E06 网络镜像与新的 E07 manifest 混搭。

保持板卡断电，插入 SD，网线直连板卡 GEM3 和电脑专用以太网。
启动开关设置沿用已验证的 ZCU102 SD 启动设置。
推荐连接 USB-UART 保存日志；没有 UART 时不能宣称已满足原 E06 UART/TCP 物理门禁。

## 2. Windows 11 打包或直接运行源码

在新解压的 **E07_Cloud_GUI_Win11_Source_V2_2 根目录** 打开 PowerShell（不要启动旧目录的 exe）：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\Cloud_test\windows\build_e07_windows.ps1
```

需要已安装 Python 3.13 x64，或复用此前可工作的 `.venv-build-win`。
脚本在 Windows 本机生成 `Cloud_test\dist\E07_Cloud_GUI\E07_Cloud_GUI.exe`。
本 Linux 发布包提供源码与打包脚本，不声称已经生成 Windows 原生 exe。

## 3. 配置专用以太网

必须在 Windows 本地操作，而不是依赖将被断开的远程连接。
此前 WLAN 默认网关是 `192.168.10.1`，与板卡实验地址冲突：测试时关闭 Wi-Fi。
如果实验地址与其他活动路由冲突，也应先解决该冲突。

管理员 PowerShell 先检查，确认 `以太网` 是只连接板卡的专用网卡：

```powershell
Get-NetAdapter
Get-NetRoute -InterfaceAlias 以太网 -AddressFamily IPv4
```

只有专用网卡无默认路由时才设置。以下为临时 ActiveStore 设置，可避免此前
PersistentStore 与 DHCP 配置不一致的错误。先记录原配置以便恢复；不要删除或改动其他接口：

```powershell
Get-NetIPInterface -InterfaceAlias 以太网 -AddressFamily IPv4
Get-NetIPAddress -InterfaceAlias 以太网 -AddressFamily IPv4
Set-NetIPInterface -InterfaceAlias 以太网 -AddressFamily IPv4 -Dhcp Disabled -PolicyStore ActiveStore
```

如果尚无实验地址，执行：

```powershell
New-NetIPAddress -InterfaceAlias 以太网 -IPAddress 192.168.10.1 -PrefixLength 24 -AddressFamily IPv4 -PolicyStore ActiveStore
```

检查，等待 `192.168.10.1` 的 `AddressState` 变为 `Preferred`：

```powershell
Get-NetIPAddress -InterfaceAlias 以太网 -AddressFamily IPv4
```

若为 `Tentative`/`Duplicate`，不要启动测量；检查链路和重复地址。
不要设置实验默认网关，不要全局关闭防火墙。
若防火墙拦截，只放行专用接口上从 `192.168.10.2` 到 `192.168.10.1` 的 TCP 5001，测试后删除这条规则。

## 4. 启动英文 GUI 和六阶段测量

进入生成的 `Cloud_test\dist\E07_Cloud_GUI` 目录。板卡仍断电：

```powershell
.\E07_Cloud_GUI.exe --duration 60 --fps 10 --streams 1 2 4 --gui-port 18082
```

或在源码包根目录，不打包直接运行：

```powershell
.\Cloud_test\windows\.venv-build-win\Scripts\python.exe -m Cloud_test.windows_e07_launcher --duration 60 --fps 10 --streams 1 2 4 --gui-port 18082
```

预期：

```text
E07_DASHBOARD=http://127.0.0.1:18082
E07_COLLECTOR_LISTENING=192.168.10.1:5001
```

此时给板卡上电，浏览器打开 `http://127.0.0.1:18082`。
不要同时运行旧 E06 exe、`run_cloud.py` 或其他 collector，它们会争用 5001。

默认依次运行 1/2/4 流，每种流数 full 和 compact 各 60 秒，总测量约 6 分钟，另加初始化与同步。
`--duration 300` 为每阶段 5 分钟，总测量约 30 分钟。
`--fps` 是每流目标频率：1/2/4 流时总目标为 10/20/40 FPS。
若板卡/网络饱和，实际 FPS 会低于目标；应报告实际结果，不能把目标 FPS 当成实测值。
建议再做一次 `--order compact-first`，减少阶段顺序/热状态偏差。

测量表每阶段结束后更新。完成后 GUI 保持运行，Ctrl+C 退出。
顶部旧会话卡片不等同于六阶段汇总，以 **Sustained cloud ingress** 表和 report.json 为正式数据来源。
V2 的 `--timeout` 是每次完整事务（发送加接收）的截止时间；少量数据到达不会续期。
发生超时会记录 `transaction_failure`，包括请求 ID、实际收到的字节数、预计总字节数和已收到负载数。
终端输出 `E07_STATUS=FAIL`；负载或时间戳校验失败也写入事务失败日志，不记为成功帧。
V2.1 配对要求两模式完整完成、无缺失/重复、相同 offered FPS，实际 FPS 和持续时间差不超过 5%。
不满足时 `observed_bandwidth_saved_percent` 为 null；原始 observed difference 只作描述性数据。
不同采样时窗的总 J 不相减，`system_energy_difference_J` 始终为 null。
匹配运行且两阶段各有至少 90% 功耗覆盖时，可报告 coverage-normalized mean monitored power difference，
但顺序阶段不等同于因果能耗收益实验，5%/90% 是明确的质量门槛，不是硬件误差上界。

## 4a. 三项 PS 优化的历史配置（不是 V2.2 消融结果）

V2.2 仅发布修复定时器的 FINAL（32768 窗口、分块 memcmp、`-O2`）。
旧 V2 ZIP 的 `ABLATION` 镜像没有这次定时器修复，不能与 V2.2 manifest 或源码混用。
下表仅记录历史构建配置，不能用于宣称 V2.2 三项优化的独立板级收益：

| 配置 | TCP_WND | 负载校验 | PS 应用编译 |
|---|---:|---|---|
| FIX | 2048 | 逐字节 | -O0 |
| WINDOW | 32768 | 批量前的逐字节 | -O0 |
| BATCH | 32768 | 分块 memcmp | -O0 |
| FINAL | 32768 | 分块 memcmp | -O2 |

未来需要单因素对照时，须基于同一新版定时器重新构建、绑定各自身份并采用相同实验协议。
当前没有启动新的板卡任务，也没有给未测的配置补填结果。

## 5. 导出数据与论文口径

exe 下：`results\stream_measurements\<时间戳>\`；源码运行时默认在 `Cloud_test/results/stream_measurements/`。

- `frames.jsonl`：每次源端尝试、接收时间、请求序号、流内序号、实际读取字节数、板端时间戳、同步信息、telemetry。
- `report.json`：每阶段及每流统计，包含原始证据 SHA-256。
- `metrics.csv`：六阶段总表。

核心指标：

```text
Bytes_received/frame = socket_received_bytes / frames_received
R_save = 1 - compact_bytes_per_frame / full_bytes_per_frame
BW = socket_received_bytes * 8 / elapsed_s
```

字节来自 socket 实际读取，含 FVIT 帧头、JSON 和 payload，不含 Ethernet/IP/TCP 头和重传字节。
`socket_total_received_bytes_including_control` 另计时间同步/telemetry 等控制开销。
单帧 saving 和 observed bandwidth saving 是不同指标；两模式实际 FPS 不同时，不能把带宽差全部归因为压缩。

主机 send/receive 共享 monotonic clock，E2E 直接实测。
板端给出 input 接收起止、推理起止与结果排队时刻。
用 7 次同步最小 RTT 估计跨时钟偏移，每 10 秒刷新；报告 half-RTT 和无漂移边界的限制。
单向 uplink/result-upload 是 **estimated**，不是硬件同步后的精确单向时延。

```text
E2E = uplink_estimated + inference + edge_processing + result_upload_estimated
```

结果排队时间在 tcp_write 之前，不是 PHY 发出时间；result-upload 包含排队。
端点摄像头未接入，论文写“PC-originated fixed-tensor replay”而不是实时摄像头病害检测。
原始帧是否丢失与 TCP 包是否丢失是两层概念；missing_responses、duplicate_responses、sequence_continuous 是应用层证据。

绘图（需要 matplotlib）：

```powershell
.\Cloud_test\windows\.venv-build-win\Scripts\python.exe -m pip install matplotlib
.\Cloud_test\windows\.venv-build-win\Scripts\python.exe -m Cloud_test.tools.export_stream_plots .\实际路径\report.json
```

## 6. 独立采集 TCP 重传证据

安装 Wireshark/Npcap，在 **专用以太网** 上抓包，必须在板卡上电前开始。
捕获过滤器：`host 192.168.10.2 and tcp port 5001`。保存完整 `.pcapng`，包括结束时统计的 capture drops。
不要把缺少抓包的 TCP retransmissions / packet loss 的 `null` 改成 0。

分析命令（在源码包根目录；替换实际文件路径）。tshark 路径包含空格，必须保留参数两端引号：

```powershell
.\Cloud_test\windows\.venv-build-win\Scripts\python.exe -m Cloud_test.tools.analyze_e07_tcp_capture .\e07.pcapng --report .\实际路径\report.json --tshark 'C:\Program Files\Wireshark\tshark.exe'
```

生成 `network_quality.json`，保留 pcap 和应用 report 的哈希，不修改原 report。
统计 edge→cloud 方向的 captured bytes、重传包、reset、疑似缺失 segment；按各阶段 wall-clock 时间筛选。
Wireshark 的 TCP sequence 分析可能受抓包丢包或乱序影响，不能据此声称精确物理链路丢包率。
字段依据 [Wireshark TCP Analysis](https://www.wireshark.org/docs/wsug_html_chunked/ChAdvTCPAnalysis.html)。

## 7. 停止、恢复与归档

Ctrl+C 停止测量/GUI。归档完整会话、report、CSV、JSONL、pcapng 和 UART 日志，并保留哈希。
如果此前用旧配置脚本备份过网络，先审核其 `network-backup.json` 再按原流程恢复。
若按本手册仅临时启用地址且原本 DHCP 开启，可只移除本次实验地址，再恢复该专用接口的 DHCP：

```powershell
Remove-NetIPAddress -InterfaceAlias 以太网 -IPAddress 192.168.10.1 -Confirm
Set-NetIPInterface -InterfaceAlias 以太网 -AddressFamily IPv4 -Dhcp Enabled -PolicyStore ActiveStore
```

若原本使用静态地址，恢复记录的原配置，不能一概改成 DHCP。最后再启用 Wi-Fi。

## 本地重建

`prepare_e07_cloud.py` 只用于首次复制种子；当前 `e07/firmware` 是已增强的正式源代码，不要重新用种子覆盖。
BSP 已存在时，使用 `build_scripts/rebuild_e07_net.py` 在 Vitis 2025.1 的 `-s` 模式重编译，
环境变量 `FVIT_E07_PROFILE` 选择 FIX/WINDOW/BATCH/FINAL，默认 FINAL。
脚本会构建 BOOT，并将实际编译命令、lwipopts、ELF 与身份保存至 `e07/build/variants/<配置>/`。
发布物已存在时拒绝覆盖，不要重新生成旧版 `make_e07_net_boot.py` 的镜像。
Vitis 本地 gRPC 构建需要移除影响 localhost 的代理环境变量。
