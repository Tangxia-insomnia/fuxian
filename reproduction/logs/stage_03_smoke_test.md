# 阶段 3：最小样本组件诊断

当前更新（2026-10-26）：授权补写并配置密钥后，5/5 条完成真实 LLM 与 SMT 流程，已通过进入 pilot 的门槛。详细逐样本记录与汇总在本文后半部分；结果见 results/processed/completed_smoke.json。

初始状态（补写前）：离线组件诊断完成；端到端最小测试未通过先决条件，不能进入小规模实验。
时间：2026-10-25T23:58:18.249627+08:00（Asia/Shanghai）。

## 样本与方法

- 官方文件 `benchmark/NPD/codeql/codeql_kernel69_nullpointer.json`，固定随机种子 20261025；选择原始 result=1 的 2 条、result=0 的 3 条，样本 ID、原始位置和文件 SHA-256 已固定于 `configs/smoke_manifest.json`。
- 默认暂将该组的 1/0 理解为真实缺陷/误报：该文件分布 22/48 与论文表 5 和作者聚合指标 real_bug_num=22 一致；尚无逐条独立标注说明，不开展标签指标评估。
- 缺陷类型限定 NPD：公开流水线硬编码空指针判定，不能为了多类型覆盖而套用于 UAF/BOF。
- 官方入口实际加载失败见阶段 2，错误为 `ModuleNotFoundError: No module named 'util'`。以下不是 5 次端到端运行，而是对 5 条真实样本调用原始条件提取函数并生成原始初始提示词。
- 为独立加载提取器，仅在内存 AST 中移除缺失类型导入并推迟注解求值；所有函数体不变、上游文件未修改。详细原因和影响见 `patches/component_probe_adaptation.json`。没有实现缺失核心模块。

## 实际结果

| 样本 ID | 原始 result | 条件提取与提示词生成 | 组件耗时（秒） | 端到端结果 |
|---|---:|---|---:|---|
| `NPD/codeql/kernel69:row=21:index=40` | 0 | extraction_and_prompt_passed | 0.000132 | 未运行/无预测 |
| `NPD/codeql/kernel69:row=23:index=42` | 0 | extraction_and_prompt_passed | 0.000636 | 未运行/无预测 |
| `NPD/codeql/kernel69:row=34:index=55` | 1 | extraction_and_prompt_passed | 0.000370 | 未运行/无预测 |
| `NPD/codeql/kernel69:row=35:index=56` | 1 | extraction_and_prompt_passed | 0.000364 | 未运行/无预测 |
| `NPD/codeql/kernel69:row=65:index=95` | 0 | extraction_and_prompt_passed | 0.000134 | 未运行/无预测 |

- 组件成功 5/5，组件失败 0/5。
- 端到端尝试 0、成功 0、先决条件阻塞 5。最终预测均为 null，不得计为真实缺陷或误报。
- 每条样本都保存了实际位置、提取的路径/提前跳转条件、提示词或真实 traceback；无 LLM 响应、无该样本的 SMT 结果。
- API 调用 0，费用 0 元。耗时仅为本地组件耗时，不能作为论文方法平均运行时间。
- 输出：`results/raw/smoke/row_*.json`、`results/processed/smoke_results.csv` 和 `.json`。

## 当前阻塞

原始内部模块和跨过程分析缓存没有完整恢复；凭据环境变量未配置；用户模型与论文不同且服务可用性未验证。不生成虚构模型响应、Z3 约束或预测，也不以缺失上下文触发的 result=True 作为成功。


## 补全版 smoke 开始

时间：2026-10-26T00:25:27.377495+08:00。样本原始行号：[21, 23, 34, 35, 65]。下列运行属于补全实现，原始实现诊断记录保留。


- 样本 `NPD/codeql/kernel69:row=21:index=40`：failed；预测=None；调用=9；Z3 成功=0；耗时=23.044s；费用保守上界=0.073778 元；错误=RuntimeError: Z3 repair attempts exhausted: ValueError: Generated code may only import z3。


- 样本 `NPD/codeql/kernel69:row=23:index=42`：success；预测=filter；调用=10；Z3 成功=2；耗时=13.092s；费用保守上界=0.052534 元；错误=None。


- 样本 `NPD/codeql/kernel69:row=34:index=55`：failed；预测=None；调用=7；Z3 成功=0；耗时=11.120s；费用保守上界=0.029540 元；错误=RuntimeError: Z3 repair attempts exhausted: ValueError: Unsupported generated-code operation。


- 样本 `NPD/codeql/kernel69:row=35:index=56`：failed；预测=None；调用=7；Z3 成功=0；耗时=14.682s；费用保守上界=0.045306 元；错误=RuntimeError: Z3 repair attempts exhausted: ValueError: Unsupported generated-code operation。


- 样本 `NPD/codeql/kernel69:row=65:index=95`：failed；预测=None；调用=7；Z3 成功=0；耗时=8.815s；费用保守上界=0.019154 元；错误=RuntimeError: Z3 repair attempts exhausted: ValueError: Generated code may only import z3。


## 补全版 smoke 开始

时间：2026-10-26T00:28:12.652071+08:00。样本原始行号：[21, 23, 34, 35, 65]。下列运行属于补全实现，原始实现诊断记录保留。


- 样本 `NPD/codeql/kernel69:row=21:index=40`：success；预测=keep；调用=8；Z3 成功=2；耗时=24.602s；费用保守上界=0.071652 元；错误=None。


- 样本 `NPD/codeql/kernel69:row=34:index=55`：success；预测=keep；调用=6；Z3 成功=1；耗时=8.634s；费用保守上界=0.021550 元；错误=None。


- 样本 `NPD/codeql/kernel69:row=35:index=56`：success；预测=keep；调用=4；Z3 成功=1；耗时=8.175s；费用保守上界=0.020892 元；错误=None。


- 样本 `NPD/codeql/kernel69:row=65:index=95`：success；预测=filter；调用=4；Z3 成功=1；耗时=6.103s；费用保守上界=0.009494 元；错误=None。


## 补全版 smoke 开始

时间：2026-10-26T00:34:01.223908+08:00。样本原始行号：[21, 23, 34, 35, 65]。下列运行属于补全实现，原始实现诊断记录保留。


## 补全版阶段汇总

已记录 5 条；最终成功 5、失败 0、阻塞 0；先前失败尝试 4，保留在 attempt_history。机器可读结果见 results/processed/completed_smoke.json。
