# ZCU102 E06 物理网络测试操作手册

本手册只用于 `E06_PHYSICAL` 阶段。当前镜像运行 E06 模型，不是
PlantVillage 模型，因此 GUI 中 PlantVillage 准确率必须显示 `N/A`。
`BOOT_E06_NET.BIN`、主机冒烟或 GUI 可启动都不能单独证明 FPGA 物理测试
通过；Task 10 只有采集到真实 UART 与 TCP 证据后才算通过。

## 1. 文件身份和 SD 卡

工作目录：`/home/user/Desktop/ff_vit_re`。

先在电脑上核对发布镜像：

```bash
sha256sum Cloud_test/boot/BOOT_E06_NET.BIN
```

必须得到：

```text
6e02ba90a6fbee3140537145c5236443b26aa3c3ef7f8380e146224578ddf37f
```

准备一张 FAT/FAT32 分区的 SD 卡。将下列四个文件放到 FAT 分区根目录，
文件名和大小写必须完全一致：

| SD 根目录文件 | Cloud_test 来源 | SHA-256 |
|---|---|---|
| `BOOT.BIN` | `boot/BOOT_E06_NET.BIN` | `6e02ba90a6fbee3140537145c5236443b26aa3c3ef7f8380e146224578ddf37f` |
| `weights.bin` | `vendor/e06_base/data/weights.bin` | `0fac7e4cd09ae8367e5c8dfd5cb469473780055feccf9569a8376419028e2cd7` |
| `input.bin` | `vendor/e06_base/data/input.bin` | `f7fa33c31113271173effc4fb684c432378b85c2f15a6681aa682aacf2ba3a2c` |
| `output.bin` | `vendor/e06_base/data/output.bin` | `f2da31d910ab48a49c5a803f836478e2b54e0cd9fdd1081cc2eabc1d36afe842` |

示例（将 `/media/$USER/SDCARD` 替换成真实挂载点；这些 `cp` 命令会修改
SD 卡内容）：

```bash
cp Cloud_test/boot/BOOT_E06_NET.BIN /media/$USER/SDCARD/BOOT.BIN
cp Cloud_test/vendor/e06_base/data/{weights.bin,input.bin,output.bin} /media/$USER/SDCARD/
sync
sha256sum /media/$USER/SDCARD/{BOOT.BIN,weights.bin,input.bin,output.bin}
```

不要直接复制整套数据集，也不要把 PlantVillage 权重改名后替换
`weights.bin`；E06 和 PlantVillage 权重不是同一文件。

## 2. 板卡、串口和启动模式

1. ZCU102 断电。
2. 插入 SD 卡；用网线直连板卡 GEM3 口和电脑的专用有线网口。
3. 将 USB-UART（J83）连接电脑。串口设置为 `115200 8N1`：115200 baud、
   8 data bits、无校验、1 stop bit、无流控。
4. 将启动模式开关 `SW6` 设为 SD：`1=ON, 2=OFF, 3=OFF, 4=OFF`。
   这是 [AMD UG1209 的 ZCU102 SD 启动配置](https://docs.amd.com/r/2024.1-English/ug1209-embedded-design-tutorial/Running-the-Image-on-the-ZCU102-Board)；
   拨动前务必断电，并以板上 SW6 编号/丝印为准。
5. 打开串口终端，再通过 SW1 上电。若已经上电，完整断电后等待数秒再上电，
   不要只重新插 SD 卡。

Linux 串口示例（将 `/dev/ttyUSB0` 换成实际 APU UART 设备）：

```bash
python -m serial.tools.miniterm /dev/ttyUSB0 115200
```

预期依次看到的关键行：

```text
FVIT_BUILD_PHASE=E06_PHYSICAL
FVIT_MODEL=E06
FVIT_FIRMWARE_SHA256=bf59538ed3922b39391517a1e829ad6ee7853f8af05903ca5a49f322eac95be6
FVIT_WEIGHTS_SHA256=0fac7e4cd09ae8367e5c8dfd5cb469473780055feccf9569a8376419028e2cd7
NETWORK_READY IP=192.168.10.2 PORT=5001
NETWORK_CONNECTED=192.168.10.1:5001
```

如果出现 `INFERENCE_INIT_FAIL=...`，优先检查 SD 文件名、大小和哈希；
`NETWORK_INIT_FAIL=...`、`NETWORK_CONNECT_START_FAIL=...` 或持续重连则检查
网线、电脑地址和 collector；`TELEMETRY_PARTIAL=...` 表示传感器数据部分不可用，
不能把缺失值记为 0。任何 `NETWORK_ABORT`、DMA timeout 或 mismatch 都必须保留
到证据中，不能当作成功。

## 3. 电脑直连网络

下面命令会修改电脑网络配置。先用 `ip -br link` 找到只连接 ZCU102 的真实
网卡接口，再把示例变量 `IFACE` 改成该接口（例如 `enp4s0`）。绝不能照抄到
SSH、默认路由或办公网络所使用的接口，否则可能断网。

NetworkManager 方式（这些 `nmcli` 命令会新建/修改主机连接配置）：

```bash
ip -br link
IFACE=enp4s0
sudo nmcli connection add type ethernet ifname "$IFACE" con-name zcu102-direct \
  ipv4.method manual ipv4.addresses 192.168.10.1/24 ipv4.never-default yes \
  ipv6.method disabled
sudo nmcli connection up zcu102-direct
ip -4 address show dev "$IFACE"
```

临时 `ip` 方式（这些命令会修改所选网卡地址和链路状态，重启后通常失效）：

```bash
IFACE=enp4s0
sudo ip link set dev "$IFACE" up
sudo ip address replace 192.168.10.1/24 dev "$IFACE"
ip -4 address show dev "$IFACE"
```

先确认物理链路，再测试板卡地址：

```bash
ethtool "$IFACE" | grep 'Link detected'
ping -c 4 192.168.10.2
```

由于板卡主动连接电脑，collector 必须先监听 `192.168.10.1:5001`。如果主机
防火墙阻止入站 TCP，可选地添加一条受限规则。**不要把接口加入 `trusted`
zone**：该 zone 会信任接口上的全部流量，`--add-port` 并不能重新收紧它。

以下命令只修改 firewalld 运行时状态（没有 `--permanent`）：先记住接口原来的
zone，在限制性 `drop` zone 中仅允许来源 `192.168.10.2/32`、目标
`192.168.10.1/32`、TCP 目标端口 `5001`，然后才把专用接口切换到该 zone。
仍须先确认 `$IFACE` 是板卡专用接口；选错 SSH/默认路由接口会立即中断其他
入站连接：

```bash
OLD_ZONE=$(sudo firewall-cmd --get-zone-of-interface="$IFACE")
RULE='rule family="ipv4" source address="192.168.10.2/32" destination address="192.168.10.1/32" port port="5001" protocol="tcp" accept'
sudo firewall-cmd --zone=drop --add-rich-rule="$RULE"
sudo firewall-cmd --zone=drop --change-interface="$IFACE"
sudo firewall-cmd --zone=drop --query-interface="$IFACE"
sudo firewall-cmd --zone=drop --query-rich-rule="$RULE"
```

测试完按相反顺序恢复原 zone，再删除该唯一 rich rule（这些命令同样会修改
防火墙）。若原接口没有 zone，`--get-zone-of-interface` 通常返回 `no zone`，
则移除临时绑定：

```bash
if [[ -n "$OLD_ZONE" && "$OLD_ZONE" != "no zone" ]]; then
  sudo firewall-cmd --zone="$OLD_ZONE" --change-interface="$IFACE"
else
  sudo firewall-cmd --zone=drop --remove-interface="$IFACE"
fi
sudo firewall-cmd --zone=drop --remove-rich-rule="$RULE"
```

保持同一个终端直到完成清理，避免丢失 `OLD_ZONE` 和 `RULE`。不要执行全局关闭
防火墙、把接口加入 trusted zone 或开放 `5001/tcp` 给任意来源的命令。若系统
使用 `ufw`/`nftables`，只建立同时约束专用接口、来源/目标地址和 TCP 5001 的
临时规则，记录实际命令并准备精确逆向清理命令。

## 4. 启动 collector 和 GUI

在第一个终端启动 collector：

```bash
cd /home/user/Desktop/ff_vit_re
python Cloud_test/run_cloud.py
```

预期电脑端显示：

```text
E06_COLLECTOR_LISTENING=192.168.10.1:5001
E06_SESSION_ROOT=/home/user/Desktop/ff_vit_re/Cloud_test/results/sessions
```

在第二个终端启动 GUI：

```bash
cd /home/user/Desktop/ff_vit_re
python Cloud_test/run_dashboard.py
```

浏览器打开 `http://127.0.0.1:8080`。collector 收到并验证 HELLO 后创建
`Cloud_test/results/sessions/<session-id>/`。若板卡已先启动，等其有界重连；也可
保持 collector 运行并重新给板卡断电/上电。

## 5. 推理触发和物理门禁

E06 固件接受 `health`、`run_once`、`telemetry`、`repeat_latency`、
`full_payload` 和 `compact_result` 六种有界 FVIT 命令。Task 10 的采集工具负责在
同一条已验证的板卡 TCP 连接上发送这些命令并归档请求/响应；不要用
HOST_LOOPBACK 报告代替。正式序列为：

1. `health` 验证身份；
2. `run_once`，要求 `mismatch_count == 0`，并收到 telemetry 或明确的
   sensor-unavailable 标志；
3. `full_payload` 与 `compact_result` 各一次；
4. warm-up 后执行 10 组、每组 100 帧的有界测量。

如果当前尚未运行 Task 10 采集工具，能够看到 HELLO/GUI 只说明链路已建立，
不能手工把门禁改成通过。最终的 `results/e06_physical_gate.json` 必须由原始
UART/TCP 证据重新分析产生。

先执行只读就绪检查（替换真实接口与 APU UART；该命令不配置网卡、不改防火墙、
不写 SD 卡）：

```bash
python Cloud_test/tools/capture_e06_physical.py readiness \
  --interface "$IFACE" --uart-device /dev/ttyUSB0
```

然后保持板卡断电，启动 GUI（可选）以及统一采集命令。统一采集命令会先打开 UART
并监听 `192.168.10.1:5001`，看到 `E06_CAPTURE_READY` 后再给板卡上电：

```bash
# 可选，另一个终端运行
python Cloud_test/run_dashboard.py

# 当前终端运行；只有明确给出 --confirm-physical 才采集
python Cloud_test/tools/capture_e06_physical.py run \
  --interface "$IFACE" --uart-device /dev/ttyUSB0 \
  --timeout 900 --confirm-physical
```

不要同时运行 `run_cloud.py`，因为统一采集工具本身就是本次测试的 collector。
工具成功后会打印 `E06_PHYSICAL_SESSION=...`。将该真实目录交给独立分析器，连续
执行两次并确认生成文件字节不变：

```bash
SESSION_DIR=Cloud_test/results/sessions/<实际-session-id>
python Cloud_test/run_physical_gate.py --session-dir "$SESSION_DIR"
sha256sum Cloud_test/results/e06_physical_gate.json
python Cloud_test/run_physical_gate.py --session-dir "$SESSION_DIR"
sha256sum Cloud_test/results/e06_physical_gate.json
```

只有 `status` 为 `PASS` 且 `passed` 为 `true` 才表示物理门禁通过。当前没有连接
板卡时，发布文件必须保持 `NOT_RUN`、`passed: false` 和
`BLOCKED_PHYSICAL_INPUT`；禁止手工修改为通过。

## 6. 故障定位

- collector 无法绑定：确认 `ip -4 address show dev "$IFACE"` 中确有
  `192.168.10.1/24`，并确认没有其他程序占用 `5001`（`ss -ltnp`）。
- ping 不通：先看 `ethtool "$IFACE"` 的 carrier，再核对网口、SW6 和 UART；
  ping 不通不一定代表 TCP 必然失败，但必须记录。
- HELLO 被拒绝：核对 `config/e06_physical.json`、BOOT manifest 和 SD 文件哈希；
  不要绕过 identity 检查。
- GUI 无数据：先访问 `http://127.0.0.1:8080/api/health`，确认 collector 与 GUI
  的 `--sessions-dir` 完全相同。
- mismatch 非零、DMA/加速器超时：停止测量并保留日志，不能继续生成成功结论。
- 温度/功耗为空：保留有效推理，但显示 unavailable；功耗是 INA226 监测轨之和，
  不是墙上插座、PHY-only 或无线能耗。

## 7. 安全停止和归档

collector 与 GUI 都用 `Ctrl-C` 停止；collector 也处理 `SIGTERM` 并关闭监听
socket。随后导出本次目录（替换真实 session ID）：

```bash
SESSION_ID=20260928T000000.000000Z-xxxxxxxxxxxx
test -d "Cloud_test/results/sessions/$SESSION_ID"
tar --create --gzip \
  --file "Cloud_test/results/${SESSION_ID}.tar.gz" \
  -C Cloud_test/results/sessions "$SESSION_ID"
sha256sum "Cloud_test/results/${SESSION_ID}.tar.gz" \
  > "Cloud_test/results/${SESSION_ID}.tar.gz.sha256"
sha256sum --check "Cloud_test/results/${SESSION_ID}.tar.gz.sha256"
```

归档前同时保存 UART 日志、`date --iso-8601=ns`、`ip address show dev "$IFACE"`
和 `ethtool "$IFACE"` 输出。运行时证据位于 `results/`，按设计不进入软件发布
哈希；它必须由独立的会话归档哈希保护。
