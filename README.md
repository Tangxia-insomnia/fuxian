# LLM4PFA 复现记录

本仓库保存论文 **Minimizing False Positives in Static Bug Detection via LLM-Enhanced Path Feasibility Analysis** 的简单复现、补全代码、真实运行输出、失败审计及安全策略实验。公开快照日期：2026-10-30。

这不是原论文全部类型的完整复现。作者旧公开实现缺少部分内部模块，本项目使用有记录的补全实现与 DeepSeek 模型；基准版本、模型和处理口径均有差异。

## 当前结果与状态

- NPD 扩展基线：278 条有效标签样本，224 条执行成功，39 条上下文阻塞，15 条执行失败。
- 相对公开标签，误报过滤 64/241（26.56%），真实缺陷标签误删 2/37（5.41%）。原始基线完整保留。
- 后续 `real-bugs-first-v1` 策略优先保留真实缺陷：在 10 条审计样本和固定 20 条回归样本的既有日志上，结果为 0 FILTER、15 KEEP、15 UNKNOWN；UNKNOWN 始终保留，不能计为过滤成功。这不是全量安全策略评测，也不代表完成语义证明。
- A10 已进行历史源码和宏语义核查；原扫描构建证据仍不齐，保持 UNKNOWN / KEEP。
- 最近阶段只完成限时证据查找和通用修复计划，尚未执行计划中的条件极性修复实验。
- 历史模型调用共 1187 次，费用估算上界约 4.491330 元，非账户账单；审计、源码核查和修复计划未增加模型调用。

## 阅读入口

| 材料 | 路径 |
|---|---|
| 复现环境、运行方法 | [reproduction/README.md](reproduction/README.md) |
| 原始实验最终报告 | [final_report.md](reproduction/results/final_report.md) |
| 逐样本基线预测 | [expanded_all_npd.csv](reproduction/results/processed/expanded_all_npd.csv) |
| 各阶段记录 | [logs/](reproduction/logs/) |
| 失败定位审计 | [failure_audit.md](reproduction/failure_audit.md) |
| 安全策略及回归报告 | [safety_policy_report.md](reproduction/safety_runs/20261029_v1/safety_policy_report.md) |
| A10 过滤证据核查 | [a10_evidence_review.md](reproduction/safety_runs/20261029_a10_review/a10_evidence_review.md) |
| 最新证据查找与修复准备报告 | [build_evidence_and_repair_report.md](reproduction/safety_runs/20261029_build_search_repair_plan/build_evidence_and_repair_report.md) |
| 通用修复优先级 | [repair_plan.md](reproduction/safety_runs/20261029_build_search_repair_plan/repair_plan.md) |
| 下一次最小离线实验计划 | [experiment_plan.md](reproduction/safety_runs/20261029_build_search_repair_plan/experiment_plan.md) |
| 原始模型、SMT 和错误输出 | [results/raw/](reproduction/results/raw/) |

## 克隆与离线检查

官方源码和基准数据通过 `reproduction/upstream` 子模块提供，固定提交为 `4efb4b9bf7e845e180451b43ba29a25e3edaa0e3`。保留 Git 历史是为了读取代码使用的历史上下文；不要用最新 main 直接替换该版本。

```powershell
git clone --recurse-submodules https://github.com/Tangxia-insomnia/fuxian.git
cd fuxian/reproduction
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r environment/requirements-reproduction.txt
.\.venv\Scripts\python.exe -B -m unittest completion.test_completion safety.test_policy -v
```

如果已经普通克隆，请在仓库根目录执行 `git submodule update --init --recursive`。离线单元测试不需要模型密钥；上述命令是运行说明，不是本次上传重新完成实验的声明。

需要新增模型实验时，在 `reproduction/` 将 `.env.example` 复制为 `.env` 并在本机填写密钥。密钥、虚拟环境、缓存及嵌套 Git 元数据不随本快照上传。原脚本可能续跑或更新结果，应在新的实验副本/目录中使用，保留本次基线；完整实验仍需单独决定。

## 文件与证据说明

`reproduction/` 中的源码、逐阶段原始输出、指标、源码证据和失败记录按原字节复制。[upload_manifest.json](upload_manifest.json) 记录原文件 SHA-256 和公开归档的处理；[publication_check.json](publication_check.json) 记录发布前的文件与凭据模式检查。原本地复现目录没有改动。

审计冻结 ZIP 的公开副本移除了作者的两个旧编译缓存文件，其中含有疑似凭据；其余归档成员保留。历史报告中的原 ZIP 哈希对应未改动的本地原件，**不等于此公开脱敏 ZIP 的哈希**。原哈希、公开副本哈希和移除成员清单均在 upload_manifest.json 中单独记录，不将公开副本冒称为逐字节原件。

作者子模块的提交与文件另见 [upstream_manifest.json](upstream_manifest.json)。它引用作者现有的公开历史，不把其 Git 对象重新上传为本仓库文件。旧版中的编译缓存不属于运行本复现所需的源码，可在子模块执行 `git sparse-checkout set --no-cone '/*' '!**/__pycache__/' '!*.pyc' '!*.pyo'` 排除检出。原环境使用 Windows 换行，子模块在不同系统上的检出字节可能不同；清单同时记录原工作区与规范 Git blob 的 SHA-256，不把仅换行差异误当算法变化。

历史报告内的本机绝对路径和时间点哈希保留原貌，部分链接在 GitHub 上无法直接打开；请通过上方目录入口或相同相对路径查阅。历史脚本中的绝对路径证据用于追溯当时运行，不保证在另一台电脑上直接执行所有一次性归档脚本。

论文：[arXiv:2506.10322v1](https://arxiv.org/abs/2506.10322v1)。官方仓库：[LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis](https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis)。官方代码、基准、论文材料和目标项目片段均保留各自来源与权利归属；本仓库未为第三方内容重新授予许可。
