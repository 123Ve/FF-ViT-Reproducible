# 工程说明 / Project notes

| 项目 / Item | 配套关系 / Configuration |
| --- | --- |
| E07 主线 / Mainline | HLS 源码、原 IP、BD、Vivado Tcl、Vitis 应用与 BIT/XSA/BOOT 成套保存。Sources, build inputs and deployment artifacts are archived together. |
| 三个任务 / Three tasks | `deploy/` 提供各任务权重、单帧输入、参考输出及 Patch/Head ROM。Task-specific parameters and reference fixtures. |
| 模型记录 / Model records | 配方、检查点身份、精度及原始实现报告保存在相应源码目录与 `provenance/`。Recipes, checkpoint identities and original reports remain beside their sources. |
| GUI 与采样 / GUI and sampling | 网络 GUI 与双核采样程序分别使用配套固件和主机入口。Each host program uses its corresponding firmware. |
| 功耗范围 / Power scope | 严格 18 路、17 路诊断、16 路诊断分别统计；全部 18 路原始记录保留。Measurement profiles define the integration scope while retaining all raw rails. |
| Target120 | 四路各 30 FPS 目标输入；输出另记实际完成帧率和丢帧。Four sources at 30 FPS offered load, with completed throughput and drops recorded separately. |
| 构建路径 / Build paths | 用 `tools/create_workspace.py` 生成重定位的可写工作区。Create a writable relocated workspace before building. |
| 数据集 / Datasets | 原始图像与全量图像 BIN 在仓库外提供，类别顺序和准备脚本随工程保存。External datasets use the archived class mapping and preparation scripts. |
| GitHub | `https://github.com/123Ve/FF-ViT-Reproducible`；部署二进制通过 Git LFS 保存。Deployment binaries are tracked with Git LFS. |
