# 已知问题 / Known issues

| 问题 / Issue | 状态与边界 / Status and boundary |
| --- | --- |
| 最新采样流程约 64 FPS / current power-test path ~64 FPS | 用户报告；尚无对应完整阶段日志完成定位。本次归档没有修复或重测吞吐。User-reported and unresolved; no new throughput measurement here. |
| Target120 | 输入目标 4×30 FPS；不得替代实际完成 FPS。Offered load only; report completed throughput separately. |
| PlantVillage U3 setup | WNS −0.115 ns、TNS −31.367 ns、781 个 setup 违例；实验 BOOT 有明确原始标记。Existing experimental BOOT is not timing-qualified. |
| NWPU U3 setup | 原实现 WNS +0.002 ns；本次不重新综合或板测。Existing timing evidence is preserved, not re-measured. |
| ImageNet 模型与 E07 BOOT | 原始严格 S3 软件模型与冻结 E07 板测模型分开保留，不互换 ROM/权重。Separate identities; no cross-model BOOT compatibility claim. |
| GUI 网络固件 / r10 采样固件 | 协议不同，主机和 BOOT 必须配套。Separate host/firmware pairs. |
| 当前诊断功耗 | 16/17 路均不代表完整 18 路或整板外部输入功率；全部 18 路原始记录仍保留。Diagnostic scope excludes selected rails, while raw capture retains all rails. |
| 构建路径 | 冻结快照保留原绝对路径；使用 create_workspace.py 重定位并记录源码路径变更。Use the writable relocated workspace for execution. |
| 全测试集板测 | 最小样例不包含批量 I*.BIN；须从外部数据集重新生成。Full accuracy firmware needs regenerated index/input/golden shards. |
| GitHub | 需账号、仓库名/可见性及本地登录；本地归档不等于已推送。Remote creation/push requires an authenticated owner-selected destination. |

历史 9.506 W、5.855 W、诊断约 9.100 W 都不能替代新的 Target120 正式测量。
Historical power numbers must not be substituted for a new matched-load test.
