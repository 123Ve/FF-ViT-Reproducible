# E06 云端持续上传与多流测量

当前镜像为 E06，使用 SD 固定输入。实验为边缘端发送完整输入与发送推理结果的比较，
不是摄像头采集或云端模型推理实验。使用现有 BOOT 和 HLS，无需重新烧写。

## Windows 物理测量

更新源码包后，在包含 `Cloud_test` 的源码根目录运行。沿用已经建好的 Python 3.13 环境。
先停止 GUI 的 collector（Ctrl-C），本工具独占 TCP 5001。保持板卡断电，电脑专用网卡
192.168.10.1/24 配置正确后执行以下单行命令，再给板卡上电：

```powershell
.\Cloud_test\windows\.venv-build-win\Scripts\python.exe -m Cloud_test.run_stream_measurements --mode physical --duration 60 --fps 10
```

完整上传模式和紧凑结果模式分别至少运行 60 秒（帧可能在截止时间后完成）。改为
`--duration 300` 可做各 5 分钟实验。建议至少独立重复三次，用 `--order compact-first`
交换模式顺序，以控制热状态/时间漂移；实际顺序需在论文披露。
`--fps` 是每模式目标发送速率；报告实际每模式 FPS。只有两模式实际 FPS 接近时，
才可将入口带宽差归因于上传方式。最大速率测试可提高 fps，但不要将不同帧率的
带宽差写为固定摄像头帧率下的节省。

结果在 `Cloud_test/results/stream_measurements/<时间>/`：

- `frames.jsonl`：命令发送/接收时间戳、请求号、板卡计时与实际应用 socket 接收字节。
- `report.json`：每模式帧数、总字节、字节/帧、平均入口带宽、FPS、平均/P95
  命令往返时延、缺失响应、重复响应、阶段能量与失败信息；包含原始日志 SHA-256。
- `metrics.csv`：可直接用 Excel 打开或用于论文绘图。

每帧证据先写缓冲文件，在阶段边界刷新，避免 GUI 旧采集器的逐事件 fsync 污染速率。
命令通过缓冲流整帧刷新，主机 socket 设置 TCP_NODELAY，并在报告披露。
异常阶段标 FAIL，保留已收到的结果和已发出命令计数。

## 1/2/4 流主机模拟

```powershell
.\Cloud_test\windows\.venv-build-win\Scripts\python.exe -m Cloud_test.run_stream_measurements --mode simulation --duration 60 --fps 10
```

依次运行 1、2、4 流，每种流数分别 full 和 compact。总计约 6 分钟。使用真实本机 TCP
socket 和合成 payload，标签为 HOST_LOOPBACK_SYNTHETIC。报告每流 FPS、接收字节、
P95 发送到接收时延、序号完整性和总入口带宽。默认 full payload 为 602112 B，compact
为仅携带合成元数据的协议消息，不能声称它等于真实固件结果大小；论文主机实验应
用 `--compact-bytes` 调整 payload 并披露模拟协议开销。此实验验证主机接收可扩展性，
不证明一块 FPGA 同时处理四个摄像头，或真实以太网交换机/云服务器网络性能。

## 指标口径与缺测项

如需论文图，可在安装 matplotlib 的 Python 环境运行：

```powershell
python -m Cloud_test.tools.export_stream_plots Cloud_test/results/stream_measurements/<实际时间>/report.json
```

导出 PNG/PDF。模拟图会明确标注 HOST LOOPBACK SYNTHETIC，不能删除来源标签后当作
实际多摄像头/多 FPGA 网络测量图使用。

节省率用平均每帧字节：`1 - mean_compact_bytes / mean_full_bytes`。不能用一帧完整
输入的字节除以数百帧紧凑结果累计字节。GUI 已按每帧均值修正。以截图
602183 B/1 full 和 34224 B/多帧 compact 为例，原先 94.32% 是累计量不匹配的结果，
不能作为论文数字；应以日志中准确模式帧数重算。

socket 字节包含 FVIT header、JSON 和 payload，不包含 TCP/IP/Ethernet header、ACK 或
重传字节。帧序号验证的是应用响应完整性，不等价于链路无丢包；TCP 会重传补偿。
TCP 重传数和 packet loss 留空，需另用 Windows pktmon/Wireshark 的连接级抓包证据。

命令发送到响应接收使用同一电脑 monotonic clock。板卡 `total_ticks` 来自 PS timer，
不是 PL 时钟周期。现有固件不提供摄像头发送、Edge 接收、结果发送各时间戳，因而
不能分离单向上行、结果上传时间，也不提供云端模型推理 baseline。不要将“往返减
board inference”全部解释为网络传播时延，其中还有 PS 解析、Cache、输出校验等开销。

功耗每秒从现有 telemetry 命令采样，以相邻有效样本梯形积分。不跨越 unavailable
区间。结果是监测轨在采样覆盖期间的系统能量，包括空闲/推理/传输；不是 PHY-only
能量，也不是墙插功耗。不用字节节省率推算能耗节省率。报告阶段能量、每帧能量及
覆盖时长时，应额外检查样本时间是否覆盖完整阶段；当前报告同时给出有效区间数。

GUI 可打开查看旧会话，本工具的阶段报告当前通过 JSON 交付，不伪装成原 collector
session。物理通过仍需实际 UART、身份和 TCP 证据；本机模拟不能替代物理门禁。
