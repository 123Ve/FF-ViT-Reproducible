E07 双核 PS 测量镜像　2026-11-22

当前交付 r10：诊断采集不再等待热稳态最多10分钟。
diagnostic16/17 每阶段至少预热30秒，并验证该段温度有效、新鲜、范围正常及时间跨度，随后采集。
真实温度全部保存，单独输出 warmup_thermal_stable 与 thermal_qualification；未证明稳定时，
平均功率只是该诊断时间窗的平均值，不宣称稳态功耗、匹配热状态节能或完整18路正式验收。
严格18路仍保留原热稳态判据及600秒等待上限；所有模式的温度无效、陈旧、超范围以及其他故障仍拒绝。
原来的负值完整记录、数据覆盖、双核时钟握手规则保持。30秒是每阶段预热，验收其他条件不变。

本次只更新主机程序，r9的全部BOOT/ELF/SD文件逐字节复用，无需重新烧录或换SD镜像。
把 $Pkg 改为r10解压目录。由于主机源码更新，按原 -PrepareSD 流程对同一张卡生成新的
card_diag16_r10.json，再 -Acceptance -Diagnostic16，输出到 acceptance_diag16_r10 新目录。
保留r9失败日志。下面共用命令继续适用，收据/输出名称换成r10。
THERMAL_CAPTURE_NOTES_CN.txt / THERMAL_CAPTURE.diff 为本次说明与改动，r10主机实物验收尚未执行。

----- r9固件说明（r10继续使用同一固件） -----

当前交付 r9：修复 r8 的 startup readiness deadline expired / clock_checks反复0、1。
Core1固定同一ping编号的首次观察时戳，心跳独立更新；Core0在读完一致性快照后才记录接收时刻，
避免把快照读取期间的真实应答误判为“未来”。仍须三次有效时钟握手，仍保留250ms时限、
真实时钟倒退/应答早于发送/晚于接收的拒绝，不降低时钟标准。新增last_clock_sent、
last_clock_sampler、last_clock_received、last_clock_flags、clock_rejections供故障解释。
启动加载期间可能出现历史拒绝计数；就绪仍以之后三次有效握手及所有其他条件为准。

本次继续用 SD_CARD_DIAG16 / -Diagnostic16。必须复制新镜像的全部5个文件，不能只换主机脚本。
重新生成card_diag16_r9.json收据，并使用新的acceptance_diag16_r9结果目录，不覆盖r8失败日志。
将下方示例中r8/旧输出目录换成r9即可；r8的16路负值采满、质量独立判断规则全部保留。
三套PS固件重新编译，PL/模型/输入/权重不变。仅做本次针对性回归及必要构建/打包。
CLOCK_HANDSHAKE_NOTES_CN.txt / CLOCK_HANDSHAKE.diff为本次说明和改动，实物r9验收尚未执行。

----- r8采集模式与通用命令 -----

当前版本 r8：先完整采集，再分别判断采集完整性和功率质量。
推荐本次使用 16 路诊断：排除 Rail7(VCCOPS)、Rail15(VADJ_FMC)。复制
SD_CARD_DIAG16 中全部5个文件到SD根目录；所有采集/分析命令加 -Diagnostic16。
17 路诊断仍为 -Diagnostic17 / SD_CARD_DIAG17，只排除Rail7。默认仍为严格18路。
三套镜像和身份必须与参数一致；PL、XSA、模型、输入和权重均不改变。

  .\Run-PowerRetest.ps1 -CheckOnly -Diagnostic16
  .\Run-PowerRetest.ps1 -PrepareSD -Diagnostic16 -SDRoot E:\ -SDReceipt 'D:\E07 results\diag16-card.json'
  .\Run-PowerRetest.ps1 -Acceptance -Diagnostic16 -SDReceipt 'D:\E07 results\diag16-card.json' -Controls 'D:\E07 results\controls.json' -BoardId '实际板卡标签' -Output 'D:\E07 results\diag16-accept'
  .\Run-PowerRetest.ps1 -Formal -Diagnostic16 -Target120Only -Seconds 120 -Repetitions 5 -SDReceipt 'D:\E07 results\diag16-card.json' -Controls 'D:\E07 results\controls.json' -BoardId '实际板卡标签' -AcceptanceSession 'D:\E07 results\diag16-accept\session.json' -Output 'D:\E07 results\diag16-target120'
  .\Run-PowerRetest.ps1 -Analyze -Diagnostic16 -Session 'D:\E07 results\diag16-target120' -AcceptanceSession 'D:\E07 results\diag16-accept\session.json' -Output 'D:\E07 results\diag16-analysis'

E:\ 仅为示例，请核实实际盘符；收据和结果都放包外新目录。需全部条件时去掉 -Target120Only，
即可采集 Idle、Full40/Compact40、Full120/Compact120、饱和和 PLContinuous，每条件120秒、5轮。
Target120 仍为4×30FPS输入目标；实际完成FPS另记。先启动监听，再给使用匹配SD卡的板上电。

诊断模式：仅 NEGATIVE 不再中断。CVRF证明真实ADC更新，负原码/NEGATIVE/时间戳保持不变，
power_uW 的无效哨兵仍为 INT64_MIN，不清零/取绝对值。排除轨不积分；若未排除轨也出现负值，
原始数据照常采满设定时长，capture_valid可为true，但power_quality_valid为false，完整功耗/能量为空。
这不是18路正式功耗通过。I2C、溢出、饱和、陈旧、时钟、配置、覆盖或推理错误仍按原规则拒绝。
observed_mask/adc_observed_mask 表示真实CVRF已经观察到；conversion_ready_mask/power_qualified_mask
仅表示曾出现合格功率。负值本身不会把已更新的ADC记成从未转换。
RECORD_COMPLETE_NOTES_CN.txt 和 RECORD_COMPLETE.diff 为本次说明/改动；以下内容保留为旧版详细操作参考，
其中“诊断负值立即拒绝”已由上述r8规则替代。硬件实物验收与正式测量仍为 NOT_RUN。

----- 以下为旧版操作与历史说明 -----

strict18 默认积分全部18轨。diagnostic17 固定排除编号7（VCCOPS），结果名称为
17-rail diagnostic。两套镜像均读取、配置和保存全部18轨，PL、模型与冻结数据相同。
每次更换模式均需复制对应目录的全部5个文件、核对新收据、重新上电并完成匹配的实物验收。

选用 strict18 时，复制 SD_CARD 中的文件到已备份的 SD 卡根目录。选用 diagnostic17 时，
复制 SD_CARD_DIAG17 中的文件到卡根目录，包括该目录自己的 BOOT.BIN 和 FIRMWARE_IDENTITY.json。
请在包外保存收据、controls.json、验收、正式结果和分析。下面假定已进入新解压目录，
$ctl 和 $board 分别指向已填好实物条件的 controls.json 和板卡实际标签。先确认 E:\ 是目标卡。
Formal 默认执行全部条件。仅测 Target120 时加 -Target120Only，默认每条件120秒、五轮。

  $board = '实际板卡标签'
  $ctl = 'D:\E07 results\controls.json'
  python -B -S .\package.py --check-only
  .\Run-PowerRetest.ps1 -CheckOnly
  .\Run-PowerRetest.ps1 -PrepareSD -SDRoot E:\ -SDReceipt 'D:\E07 results\strict-card.json'
  .\Run-PowerRetest.ps1 -Acceptance -SDReceipt 'D:\E07 results\strict-card.json' -Controls $ctl -BoardId $board -Output 'D:\E07 results\strict-accept'
  .\Run-PowerRetest.ps1 -Formal -SDReceipt 'D:\E07 results\strict-card.json' -Controls $ctl -BoardId $board -AcceptanceSession 'D:\E07 results\strict-accept\session.json' -Output 'D:\E07 results\strict-formal'
  .\Run-PowerRetest.ps1 -Analyze -Session 'D:\E07 results\strict-formal' -AcceptanceSession 'D:\E07 results\strict-accept\session.json' -Output 'D:\E07 results\strict-analysis'

  .\Run-PowerRetest.ps1 -CheckOnly -Diagnostic17
  .\Run-PowerRetest.ps1 -PrepareSD -Diagnostic17 -SDRoot E:\ -SDReceipt 'D:\E07 results\diag-card.json'
  .\Run-PowerRetest.ps1 -Acceptance -Diagnostic17 -SDReceipt 'D:\E07 results\diag-card.json' -Controls $ctl -BoardId $board -Output 'D:\E07 results\diag-accept'
  .\Run-PowerRetest.ps1 -Formal -Diagnostic17 -SDReceipt 'D:\E07 results\diag-card.json' -Controls $ctl -BoardId $board -AcceptanceSession 'D:\E07 results\diag-accept\session.json' -Output 'D:\E07 results\diag-formal'
  .\Run-PowerRetest.ps1 -Analyze -Diagnostic17 -Session 'D:\E07 results\diag-formal' -AcceptanceSession 'D:\E07 results\diag-accept\session.json' -Output 'D:\E07 results\diag-analysis'

Python 等效参数为 --diagnostic17，可用于 host/collect.py 或 host/analyze.py。先启动采集器，
待出现 Listening 后再给装有对应卡的板上电。功耗条件、网络和回传目录详见下文。
如需保存终端输出，可在包外用 Start-Transcript -Path 'D:\E07 results\run1.txt' 记录，
运行结束用 Stop-Transcript 停止记录。返回完整验收、正式目录、收据、控制文件和终端日志。

Rail7 在两种模式下均保留原始 shunt/current/Power、CVRF、时戳、flags。诊断模式中，
该轨已观察到及时的真实转换，且唯一异常为 NEGATIVE（256或258）时，累计
excluded_negative_samples。该次记录的 power_uW 为 INT64_MIN，VALID 位为0。
Rail7 的正值同样不积分。原始数据在 exports/rails-*.bin、rails-records.json，
逐条对应的 Rail7 副本在 exports/rail7-records.json。Rail7 的 I2C、溢出、饱和、时钟、
过期、缺测及组合错误，或其余17轨的任何错误，仍会阻止有效结果。没有设置噪声阈值。
两个镜像均要求18轨完成配置和及时的首次转换观察；诊断模式要求 included_mask=262015
覆盖的17轨取得合格功率。每一轨的后续 CVRF 新鲜度与真实数据覆盖继续验证。

报告中的 measurement_profile、scope、included_mask、included_count、excluded_rails
标明计量范围。诊断模式能量取17轨同一板端窗口积分之和，P17mean_W=E/T，
实际 FPS=N_ok/T，mJ/完成帧=1000E/N_ok。Idle 或零完成帧时该项为空。
Rail7 的积分能量、均值、每帧能量均为空。诊断指标仅描述这17轨，不能代表完整18轨或外部输入功率。

实物 ZCU102、Windows PowerShell、实际 SD 卡、本次两套镜像实物验收及正式 Target120 均为 NOT_RUN。
离线夹具中的数值只验证计算；历史失败记录保持原判定。两个独立构建的依赖分别见
BUILD_DEPENDENCIES.json 和 BUILD_DEPENDENCIES_DIAG17.json。DIAGNOSTIC17.diff 以 r2 ZIP 源码为基线。

r7 分析前逐条核对 session.json 中的阶段摘要与所选计量模式，COMPLETE 会话的摘要数必须等于计划阶段数。
缺少或多出摘要均拒绝；未完成会话仍支持部分诊断。r7 仅运行该项定向回归，结果见 r7-green.log。
包内 full-suite.log 的 111 项完整测试对应 r5。

校验更新（r5）：验收授权与离线分析共用完整阶段复核，重验板端时钟、全部输出/错误事件、
主机已验证响应和 ACK 完成数。诊断 Rail7 的累计告警从预热、ARM 前、ARM 回执至冻结结束必须单调；
ARM 前到结束的增量至少涵盖导出的负值告警行，可包含额外未导出的扫描。嵌套的档位/身份冲突会中止分析。
阶段或会话门失败时，逐轨有效性为 false，完整能量、平均功率和每帧能耗为空；partial_energy_J
及覆盖率用于故障复核。两种时钟分别报告：dropped_frames 按独立主机半开窗口内产生、最终被淘汰的帧计数；
missed_slots 按同一主机窗口内的计划时刻计数。whole_run_evicted_frames 与 whole_run_missed_slots
保留含预热/排空的全程计数。未建立主机与板卡时钟映射，board_window_dropped_frames 为空。

补充说明（strict18 的详细示例和共用操作）

本次修复：先观察真实CVRF再读取数据；每轨首次转换完成前不标有效、不积分。
configured_mask只证明配置读回；conversion_ready_mask=262143才证明18轨均有过
合格的首次转换。initializing_samples记录正常等待，不冒充ADC转换数。
首次CVRF观察本身也必须在该轨配置后150ms内；超时后才看到CVRF不能补成通过。
首次转换等待超过150ms、I2C/溢出/时钟错误或合格转换后的负读数仍会失败。
M_NEGATIVE=256保留；新增NOT_READY=512，原始负码不裁零、不扣未知偏置。
如果VCCOPS在合格转换后仍为负，新包仍会拒绝验收；本次没有证明它只是噪声。
失败时回传diagnostics/fault-summary.json及完整原始目录，不要仅回传摘要。
REPAIR_NOTES_CN.txt说明实测根因、修复边界；REPAIR.diff是完整源码改动。
本包不提供新的正式功耗值，不能引用旧约9.100W/5.855W/9.506W替代新测量。

交付边界：新固件物理启动、独立采样验收、功耗测量均为 NOT_RUN。
本机只完成离线构建/测试/ZIP 校验；未运行 Windows PowerShell，未连接板卡。
BOOT/BIF/ELF map/Bootgen 通过只证明离线构建，不证明双核已在实物启动。
固件清单/hello 的 physical_status=NOT_RUN 是交付资格字段，后续用户真实会话仍
须另外记录 physical 来源并通过验收；该不可变字段不把未来真实数据变成模拟。

一、准备与备份
1. 需要 Windows 自带 PowerShell 和已安装 Python3.11 或更新版本。只用标准库，
   无需 pip、第三方解释器封装、GUI、旧 EXE。包不附带 Python 解释器。
   解压到新目录，允许空格。不要直接在 ZIP 中运行，不要覆盖旧测试包。
2. 关闭全部旧采集器/旧 EXE/占用5001端口的程序。保持相同风扇、供电、CPU/PL
   时钟、网线和环境；记录这些真实条件，不要照抄示例中的占位值。
3. 在改动 SD 前完整备份原 SD 的全部文件，包括原 BOOT.BIN，并保留可恢复副本。
   仅在用户手动操作时，把本包 SD_CARD 的5个文件复制到 SD 根目录；不要执行
   任何自动刷写。确认盘符无误，保留原 SD 副本。
4. 主机有线网卡设为192.168.10.1（与板卡192.168.10.2同网段），TCP5001。
   板卡主动连接主机。必要时允许本 Python 的此有线网络入站连接。

以下 PowerShell 示例假定解压目录 D:\E07 independent package，结果写到包外。
若有多个 Python，用启动器 -Python 'C:\...\python.exe' 指定3.11+解释器。

  python -B -S 'D:\E07 independent package\package.py' --check-only
  & 'D:\E07 independent package\Run-PowerRetest.ps1' -CheckOnly
  & 'D:\E07 independent package\Run-PowerRetest.ps1' -PrepareSD -SDRoot 'E:\' -SDReceipt 'D:\E07 results\card1.json'

第一个命令逐文件检查 PACKAGE_SHA256SUMS.json 全包清单；第二个检查 BOOT、
两核 ELF、身份及 SD 冻结数据；两者均不启动监听、不产生测量结果。SHA256SUMS.json
仅为 SD5文件清单，不要把它称为全包清单。清单是完整性检查，不是签名/设备认证。
PrepareSD 只读实际盘上文件并生成新收据，不复制文件；必须在复制后执行。
卸载 SD 后直至上板须保证该卡未再改变；固件不会运行时计算 SD 的密码学哈希。
路径/收据/结果目录应是新的，避免覆盖证据。每次换镜像或改采集器都重做收据与验收。
controls.json、SD收据、结果及终端日志一律放在解压目录外。采集器会拒绝包内的
controls/收据/结果路径。不要把新的ZIP、旧BOOT副本或测试日志混入解压目录。
若全包校验报package file inventory differs from manifest，新版会列出missing和
unexpected的准确相对路径：不要改清单或忽略报错，保留现场后重新解压到空目录。
没有__pycache__目录豁免；其中任何未列入清单的文件也会失败。交付入口抑制
Python字节码写入，PowerShell以-B -S运行Python，避免校验程序自身污染包目录。
该校验适用于交付ZIP的完整解压目录，不适用于包含多个构建/日志的开发源目录。

二、先短验收，再正式测量
创建包外 controls.json，字段均填实测/实际设置的非空字符串：
  {"cpu_clock":"实际值","pl_clock":"实际值","power_supply":"实际电源",
   "fan":"实际风扇状态","network":"实际链路","environment":"实际室温及环境"}
必须填实际值；本次失败记录中的“待核实/待测/待确认”尚不足以支撑正式实验条件。
BoardId 填同一块实物板可辨识标签；协议没有不可变设备序列号，该标签由操作者保证。

先启动以下采集器，看到 Listening on192.168.10.1:5001 后才给已装新 SD 的板卡
断电重上电。不要先开板再等待采集器。每个新采集会话均重复这个顺序。

  & 'D:\E07 independent package\Run-PowerRetest.ps1' -Acceptance -SDReceipt 'D:\E07 results\card1.json' -BoardId '实际板卡标签' -Controls 'D:\E07 results\controls.json' -Output 'D:\E07 results\acceptance1'

验收包含采样开/关各5秒吞吐对照，10秒 Idle/Full40/Compact120/PLContinuous，
再做17ms/23ms扫描、两个起始偏移下各60秒的 Compact120和PLContinuous。
采样关闭状态只能由命令后心跳推进且扫描计数稳定来推断，不是采样核直接状态证明。
开启状态另需 ready 和扫描实际推进。对照只报告主机吞吐，不用于功耗积分。
TCP greeting 不代表采样握手已就绪；主机会记录 readiness-observations.jsonl，
最多等待5秒初始化，再要求3次健康且推进的快照。致命身份/传感器错误立即失败并留诊断。
正式门限必需重读两组 sampling0/1-observations.jsonl 和 throughput-sampling0/1.jsonl，
核验心跳/扫描/控制/错误、逐帧输出校验、计数及 interval_start/end 真实主机区间；
仅有汇总 PASS 或重新计算 inventory.json 不能替代这些原始证据。
严格18路每阶段在同一实际负载下预热至少30秒；最后30秒温度极差<=1°C、首尾10秒均值差
<=0.2°C，最长600秒。不满足则失败。诊断16/17路按r10固定最低30秒预热，不等待稳态门限，
保留温度健康检查和独立稳态资格。验收仍有原来的多个条件，最低约15分钟，加导出/网络时间；
只有严格18路额外等待温稳时可能更长。

检查会话 COMPLETE 与所有阶段验收：两核心跳、同频时钟、18轨身份/0x4527/2048
配置及conversion_ready_mask=262143、读数/推理时间重叠、输出逐码校验、温度、
覆盖和无错误计数增长。
这些只是行为/覆盖证据；35.2ms ADC平均、读取区间、采样偏置/绝对精度仍待解释。
任何负电流/分流读数（flag256）、OVF、I2C错、缺轨、长缺口、输出错或缓冲满均失败。
若出现负值，不要裁成零或换旧固件数值；回传冻结 diagnostic latest 原始记录。

通过上述真实验收后，首选 Target120 的五轮配对、每条件120秒：

  & 'D:\E07 independent package\Run-PowerRetest.ps1' -Formal -Target120Only -Seconds 120 -Repetitions 5 -SDReceipt 'D:\E07 results\card1.json' -BoardId '实际板卡标签' -Controls 'D:\E07 results\controls.json' -AcceptanceSession 'D:\E07 results\acceptance1\session.json' -Output 'D:\E07 results\target120_1'

每轮 Full/Compact 交替顺序，4个独立30FPS输入源，总 offered120FPS，FIFO各深3，
满时丢最旧等待帧。实际 produced/submitted/completed、missed slots、drops、
失败、正式窗口与 drain 分别记录。120是输入目标，不代表两种模式均完成120FPS。
此配置最低约26分钟，加导出/温稳/链路时间。Full回传原始输入，不执行分类；
Compact做 FPGA推理与紧凑结果，业务功能不同，不能直接称同服务性能节能。

可选完整套件：去掉 -Target120Only 即保留原默认全部8条件×5轮：Idle、Target40
Full/Compact、Target120 Full/Compact、AppSaturation Full/Compact、PLContinuous。
完整套件最低约103分钟，加导出/温稳时间。饱和是闭环请求，无固定输入FPS；
PLContinuous是DDR驻留数据连续串行推理，不经逐帧网络，不等于120FPS云负载。
每阶段至少1秒前后保护期，不在正式窗口同步导出。长时间稳定性需由实物数据判断。

Python 等效（可从任意当前目录调用绝对路径）：
  python -B -S 'D:\E07 independent package\host\collect.py' --help
  python -B -S 'D:\E07 independent package\host\collect.py' --check-only
  python -B -S 'D:\E07 independent package\host\collect.py' --formal --target120-only --seconds 120 --repetitions 5 --sd-receipt 'D:\E07 results\card1.json' --board-id '实际板卡标签' --controls 'D:\E07 results\controls.json' --acceptance-session 'D:\E07 results\acceptance1\session.json' --output 'D:\E07 results\target120_1'

三、失败与回传
失败即停止正常结果判定。不要删除记录、强制写 PASS、重选窗口或立即重启。
采集器会尝试等待已武装阶段结束并冻结/导出恢复数据；原失败会话仍是 INCOMPLETE，
恢复失败会保留明确错误且不 release。采样心跳永久停止时可能无法导出。
先保存包外全部会话目录及控制文件/SD收据，再决定重新启动新会话。
回传 acceptance1 和正式会话的完整原始目录，不能只发 CSV/截图/摘要。包括：
session-start/session.json、inventory.json、hello/身份/manifest、raw-wire、protocol
events、采样开关观察/吞吐记录；每阶段全部 phase/start/end/arm/status/warmup、
frame-events、host-counts、温度、exports 的 .bin/.json 和所有 recovery/diagnostics。
原始收据、controls 和本包ZIP的SHA也一并保留。原始目录不得放入分析输出。

四、分析
  python -B -S 'D:\E07 independent package\host\analyze.py' 'D:\E07 results\target120_1' --output 'D:\E07 results\target120_analysis1'
若数据移到另一台主机，接受验收原始目录的路径参数见 --help。须同时回传验收，
不能以一个 PASS 标志替代它。--synthetic 仅供数学/软件测试，输出永久标记模拟，
不用于实物结论。原始文件损坏/哈希不符时退出2且不创建派生目录。
原始目录可从 Windows 返回 Linux 分析：新清单/阶段/原始哈希键统一使用正斜杠。
旧清单反斜杠仅在内存比较时规范化，拒绝绝对路径、盘符、遍历及规范化冲突；
不会重写原 inventory.json，验收绑定仍校验其原始文件字节哈希。
输出 analysis.json、per-stage.csv（逐阶段/逐重复）、per-repeat.csv（条件均值及样本SD）。
两种模式均要求18轨原始数据完整覆盖且所有语义/验收门通过，使用板端实际[t0,t1)积分：逐轨Power
实际读取区间中点、有效相邻样本梯形积分；边界只插值，不外推。>150ms逐轨间隙、
无效记录、缺轨或无边界任一项使整阶段功率/能量为空；部分覆盖另列诊断。
总能量E先逐轨积分后求和，平均功率E/T；FPS=N_ok/T；完成帧能耗1000E/N_ok。
N_ok是同一板端窗口内 ACK完成（连续推理为成功推理结束），不是主机接收计数、
result_queue时间或累计推理耗时。Idle或零完成帧的每帧能耗为空。
主机完成FPS/E2E仅用主机时钟。五次重复不是宣称五次独立上电；样本SD不代替
仪表精度。报告18轨受监测电源轨总功率，不称整板外部输入功率。不要混入旧9.506W
或旧5.855W，也不预设节能为正、不自动声称采样无偏或毫瓦级实物精度。
新A53-1采样核活动本身计入候选镜像18轨功耗，所有比较条件用同一镜像/配置；
没有把它校准扣除，不能反推出旧单核流式业务的功耗。

五、构建来源与离线复现
固件/两核ELF/BOOT来自 FIRMWARE_IDENTITY.json 的 build_directory；包内保留源码、
链接脚本、命令/编译日志、maps、反汇编、BIF、Bootgen分区检查、provenance及采样
BSP启动关键源/config。BUILD_DEPENDENCIES.json 明列外部工具/冻结输入/BSP库头
哈希。冻结bit/XSA在固件构建时逐一校验并绑定BOOT；包未单独附带原bit或XSA，
解压预检不声称重新读取它们。构建不重新综合PL。
复现需要原工程的独立副本，并在 validation/cloud_power_retest_20261121/independent_sampler
保持相对路径，取得原 Cloud_test/e07/vendor/e07_base 的同哈希bit/XSA/fsbl/pmufw
及原service BSP，安装 AMD Vitis2025.1（Linux /opt/vivado/2025.1/Vitis）。
sampler BSP须用 build_platform.py 的明确64位EL3/USE_AMP配置在新工作区生成。
浅层解压可导入纯固件地址验证器；实际重新构建仍必须具备上述原工程布局及依赖。
严格模式运行 python -B build_firmware.py，诊断模式运行 python -B build_firmware.py --diagnostic17；检查新身份的每个BSP库/头、完整commands与原身份的差异。
工具版本/依赖不同导致新身份时，不能仍把它冒认为本包固件；重新生成收据与上板验收。
本包没有独立解释器或GUI构建依赖；普通采集/分析无需Vitis，仅重新编译才需要它。
离线Python测试：python -B -S -m unittest discover -s '...\tests' -p test_host.py -v
分析测试：python -B -S -m unittest discover -s '...\tests' -p test_analysis.py -v
固件测试含C/AArch64编译器依赖，仅在上述Linux工具环境运行；Windows未运行。
package.py --build 创建新命名ZIP，不覆盖既有包；PACKAGE_SHA256SUMS不含自身。
包内 execution/diagnostic17_20261122/full-suite.log 保存完整离线测试输出。最终ZIP哈希及交付核对报告保留在ZIP外，避免自引用清单。最终资格仍以实物验收为准。
