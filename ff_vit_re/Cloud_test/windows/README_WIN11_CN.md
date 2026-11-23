# E06 Cloud GUI — Windows 11 x64 打包与运行

本目录用于在 Windows 11 x64 上将 E06 collector 和本地 GUI 打包为一个程序。
Windows 可执行文件必须在 Windows 上构建；Linux 生成的文件不能冒充已验证的
Windows EXE。

## 1. 构建

要求：Windows 11 x64、Python 3.11–3.13、可联网安装 Python 包。

以普通 PowerShell 进入 `Cloud_test` 目录：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\windows\build_windows.ps1
```

输出：

```text
Cloud_test\dist\E06_Cloud_GUI\E06_Cloud_GUI.exe
Cloud_test\dist\E06_Cloud_GUI_Win11_x64.zip
```

EXE 已包含 Flask、E06 BOOT identity manifest、dashboard templates、CSS、JavaScript
和离线 `plotly.min.js`。目标电脑运行 EXE 时不需要另外安装 Python。

## 2. 配置专用有线网卡

ZCU102 使用 `192.168.10.2`，电脑专用有线网卡必须配置为
`192.168.10.1/24`。先运行：

```powershell
Get-NetAdapter
Get-NetRoute -AddressFamily IPv4 | Where-Object DestinationPrefix -eq "0.0.0.0/0"
```

确认网卡名称，例如 `Ethernet 2`。以管理员 PowerShell 执行，并把同一个名称输入两次：

```powershell
.\Configure-ZCU102-Network.ps1 `
  -InterfaceAlias "Ethernet 2" `
  -ConfirmInterfaceAlias "Ethernet 2"
```

脚本始终拒绝带默认路由的网卡，不提供绕过开关。不要选择 Wi-Fi、远程桌面或当前
互联网连接所用网卡。确认执行后，原 IPv4 配置保存在 `network-backup.json`；脚本
不会修改 DNS，因此恢复时也不会猜测或重置 DNS。

恢复配置：

```powershell
.\Restore-ZCU102-Network.ps1 `
  -InterfaceAlias "Ethernet 2" `
  -ConfirmInterfaceAlias "Ethernet 2"
```

## 3. 启动

双击 `Start_E06_Cloud_GUI.bat`，或在命令行运行：

```powershell
.\E06_Cloud_GUI.exe
```

默认端点：

- ZCU102 collector：`192.168.10.1:5001`
- GUI：`http://127.0.0.1:8080`
- 会话：EXE 同级 `results\sessions\`

程序会自动打开浏览器。禁用自动打开：

```powershell
.\E06_Cloud_GUI.exe --no-browser
```

正式命令序列：

```powershell
.\E06_Cloud_GUI.exe --physical-gate-plan
```

按 `Ctrl-C` 会同时停止 collector 和 GUI。若 Windows 防火墙提示，只允许专用/私有网络
上的 TCP 5001；GUI 默认仅绑定本机回环地址。

## 4. 证据边界

当前 BOOT 运行 **E06** 模型，不是 PlantVillage 模型。GUI 中 PlantVillage 准确率必须为
`N/A`。该程序可以采集连接、推理输出、延迟、FPS、传输、功耗、温度和 mismatch，不能
把 E06 会话写成 PlantVillage 病害识别准确率。

## 5. 校验

构建脚本在发布目录生成 `SHA256SUMS.txt`。PowerShell 校验示例：

```powershell
Get-FileHash -Algorithm SHA256 .\E06_Cloud_GUI.exe
```

完整物理门禁仍应依据原工程的 `Cloud_test/docs/E06_BOARD_RUNBOOK_CN.md` 执行。

## 6. 持续上传、每帧带宽与多流实验

在源码包根目录使用 Python 执行 `Cloud_test.run_stream_measurements`。
具体命令与物理/模拟证据边界见 `Cloud_test/docs/CLOUD_STREAM_MEASUREMENTS_CN.md`。
本次修正 GUI 的 uplink reduction 为平均每帧字节比；原累计字节比不适合不同模式帧数
不同的实验。新版 GUI 需重新构建 EXE；持续测量工具可以直接运行源码，无需重新构建。
