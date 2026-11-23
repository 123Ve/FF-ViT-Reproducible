# 仓库整理计划 / Repository assembly plan

2026-11-23。目标：保存一个可审查的 E07 主线源码及部署快照；原目录只读。

1. 以 2026-10-22 严格 S3/U3 源码依赖闭包为 Python 主线；保留原层级，补齐最终检查点、整数参数、配方和最小二进制样例。
2. 保存 FF_Vit 的 E07 candidate05 HLS 源码、IP、BD、Vivado Tcl、Vitis 应用及最终 BIT/XSA/BOOT；单列 PlantVillage/NWPU 任务专用硬件。
3. 保留 Cloud_test GUI/网络业务源码，以及完整、未经修改的 r10 独立功耗采样发布包。正式与诊断采样范围保持区分。
4. 不复制原始图像数据集、批量测试图像 BIN、试验分支、缓存与重复工作区。保留配方/类别/样本顺序与生成脚本。
5. 增加迁移入口、清单、中英 README、环境说明和 Git LFS；检查源码闭包、BIN 哈希、GUI 导入和包内完整性。
6. 初始化本地 main 分支。远端账号、名称、可见性和登录确认后再创建/推送 GitHub。

The archive preserves original model identities and implementation reports.
Task directories use their dataset names; deployment scope and input formats
are recorded in deploy/tasks.json. Offered load and completed throughput are
recorded separately by the measurement software.
