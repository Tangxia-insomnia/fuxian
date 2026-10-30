# LLM4PFA 简单复现最终阶段报告（部分完成）

生成时间：2026-10-26T00:01:44.098752+08:00（Asia/Shanghai）。

## 结论与研究目标

目标为复现《Minimizing False Positives in Static Bug Detection via LLM-Enhanced Path Feasibility Analysis》的公开原实现，不改进算法、不接平台。
结论：官方数据和条件提取/提示词组件可运行；公开内部模块不足使原始端到端入口无法运行。此次没有完成 LLM 分析和样本 SMT 求解，不能宣称复现了论文效果。提供 API Key 本身也不能解决代码缺失。

## 代码、环境及模型

- 仓库：https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis
- 固定历史提交：`4efb4b9bf7e845e180451b43ba29a25e3edaa0e3`；当前 main 为 `37a1fdc99d59a8af176ae8c93fa4bf0adbeed997`，已将 README 方法名改为 PATHAGENT 并清空部分路径。
- 采用历史版本仍不足以证明与论文逐项一致；该版 5 份 Python 源码与 3 月提交相同，但论文运行环境和完整内部实现未公开。
- 环境：Windows-10-10.0.26200-SP0；Python 3.11.5 | packaged by Anaconda, Inc. | (main, Sep 11 2023, 13:26:23) [MSC v.1916 64 bit (AMD64)]；独立 `.venv`。
- 关键依赖：`{'z3-solver': '4.13.4.0', 'libclang': '18.1.1', 'lizard': '1.17.31', 'openai': '1.68.2', 'anthropic': '0.49.0', 'requests': '2.32.3', 'tqdm': '4.66.5', 'python-dotenv': '1.2.2'}`；作者没有固定版本，本次选择已记录，完整 freeze 在 environment/dependencies.txt。
- 用户服务：deepseek-flash、https://api.deepseek.com/、凭据变量 DEEPSEEK_APIkey、总预算 10 元。当前变量未配置、服务未验证、没有付费调用。不记录凭据值，不使用作者模型封装中的字面量配置。

## 数据集与样本

论文 v1 正文报告 NPD/UAF/BOF 三类、364 条告警、45 个真实缺陷；仓库 README 报五类、443 条、47 个真实缺陷。实际文件还含重复、缺失标签和 -1，不能视为与论文相同集合。
`UBI` 与 `UUA` 文件完全重复；Cppcheck/Linux 文件有 594 条，其中 526 条无 result、3 条 -1；CodeQL/OpenSSL NPD 也有 1 条 -1。原论文对应数据文件从 3 月到采用版本未改变，回退不能自动补全。

此次诊断从 CodeQL/Linux NPD 的 70 条中，用固定种子 20261025 选择 result=0 三条、result=1 两条：row 21 / index 40, row 23 / index 42, row 34 / index 55, row 35 / index 56, row 65 / index 95。该分组 1 标签数量 22 与论文及作者 real_bug_num=22 相符，仅作为暂定映射依据；没有擅自评估其他标签或补标。
历史 baseline 文件可提供部分函数调用链，但缺少标签、位置以及完整运行工具，不足以恢复论文数据和完整流水线。未下载或扫描 Linux Kernel。

## 实际完成阶段

| 阶段 | 实际完成情况 |
|---|---|
| 1 仓库 | 完成版本、全历史、论文、源码、数据和作者结果核查；存在论文对应关系不确定性 |
| 2 环境 | Z3 SAT/UNSAT、Clang、lizard、文件读取通过；原始入口导入失败 |
| 3 最小测试 | 5/5 样本离线提取/提示词成功；端到端尝试 0、成功 0、阻塞 5 |
| 4 小规模 | 未运行，尚未通过阶段 3 门槛 |
| 5 评估 | 完成证据汇总；监督指标和全量评估未运行 |

## 指标、时间与费用

没有最终预测，混淆矩阵四格均 NA，评估记录数为 0。误报过滤率、真实缺陷保留率/误删率、Precision、Recall、F1 全部不可计算。
正类定义为应过滤的误报。设 A=误报被过滤、B=误报被保留、C=真实缺陷被过滤、D=真实缺陷被保留；定义分别为 A/N_FP、D/N_bug、C/N_bug、A/(A+C)、A/N_FP、2PR/(P+R)。无预测/失败必须保留并单列，不能当作有效分类。
5/5 组件成功不代表端到端成功率。当前选定样本最终结果覆盖率为 0/5；实际尝试数为 0，因此尝试内成功率 NA。
平均本地提取/提示词组件耗时 0.00032716 秒，不含 LLM/SMT，不能与论文方法耗时比较；端到端平均耗时 NA。
模型 API 调用 0，token 使用 0，模型费用 0 元，未消耗 10 元预算。

## 失败、修改与解决办法

- 原始 feasibility_analysis_pipeline.py 实际模块加载失败：`ModuleNotFoundError: No module named 'util'`。extract_util_plus.py、model.py 实际失败于缺失 `LLM4Detection`。已保留原始 stderr。
- 不只是目录改名：缺失函数体检索、函数调用/参数映射、解引用定位、ContextHelper/Conditions、工具 schema 和缓存生成逻辑。历史缓存脚本也依赖这些模块，不能通过安装 PyPI 包解决。
- 发现部分异常会默认返回 True；如果绕过缺失上下文，可能伪装成“保留告警”，故不这样构造实验结果。
- 上游源码修改：无。组件诊断仅对 extract_util_plus.py 内存 AST 删除缺失类型导入、推迟注解求值，函数体完全不变；未调用依赖这些类型的辅助函数。此适配仅证明局部组件可运行，不等于完整修复，详见 patches/component_probe_adaptation.json。
- Windows venv 缺少时区数据导致诊断脚本首次启动失败，改用显式 UTC+08:00；其余安装/命令问题及处理见 results/raw/environment/setup_errors.md。
- 依赖安装完成，pip check 无冲突；未修改已有研究项目或上游代码。

## 与论文结果差异及后续工作

原论文主模型 GPT-4o-mini、temperature=0；当前用户模型 deepseek-flash 不同，服务也未验证。数据版本、公开路径/工具与论文不完全一致，不能用已有聚合结果替代本次运行。LLMDFA 和 LLM4SA 只保留作者结果，没有重跑。
下一步需取得官方缺失模块、论文准确数据子集/标签含义与上下文缓存说明。恢复原始入口后，配置本地凭据并验证模型名、参数和价格；先做 3–5 条真实端到端测试，再约 20 条 pilot。只有资源和预算允许才考虑完整基准。
若拿不到缺失核心模块，此次适宜停在“公开实现可复现性检查和局部组件验证”。重写跨过程分析将成为另一项实现工作，超出本次简单复现。

所有逐样本结果、日志及机器可读状态见 reproduction/README.md；此次无论文完整复现成功结论。
