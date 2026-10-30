# LLM4PFA 补全版扩展实验报告

时间：2026-10-26T01:09:38.819214+08:00。当前实验范围是公开 NPD 数据中全部有有效标签的记录，尚非论文所有缺陷类型的完整复现。

## 版本、环境和方法

官方仓库：https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis 。固定 commit `4efb4b9bf7e845e180451b43ba29a25e3edaa0e3`；历史上下文取自 `29ca96e0d5f860d1f4ce07cd3e54e5e25732d1a1`。
最新 main 已改为 PATHAGENT 描述，版本选择和论文 v1 差异见 logs/stage_01_repository.md。上游源码和原始 JSON 保持不变。
Windows / Python 3.11.5 / Z3 4.13.4.0 / libclang 18.1.1；依赖固定于 environment/requirements-reproduction.txt，实际 freeze 见 environment/dependencies.txt。
使用 deepseek-flash（现有官方文档对应 DeepSeek-V4.1-Flash-1017），API https://api.deepseek.com/，非思考模式，temperature=0.0000001，输出上限 3072 token、每样本最多 24 次请求。密钥仅从本地 .env 或指定环境变量读取，不写入报告。

复用作者提示词、条件提取和迭代分析函数；缺失的上下文/调用/参数等支撑采用有界补全，详见 logs/stage_06_completion.md 与 patches/completed_pipeline.diff。扩展只为同一 NPD 实现增加数据路径、历史缓存路径、func_info 字段映射和批量入口；无算法或模型优化。每次真实 SMT 查询记录源码、SAT/UNSAT 与 SMT2。
上下文缺失或歧义保留阻塞。宏/调用形式的历史 sink 沿用作者边界，未实现完整宏展开、任意别名及函数指针语义。模型成功生成可运行的 SMT 不代表约束忠实表达 C 代码。

## 数据范围与标签

清点全部 14 个 JSON，共 1017 行；剔除 UBI/UUA 完全重复文件的 63 行后，唯一文件记录数为 954。
8 份 NPD 文件共 808 行，其中 278 行具有原始整数 0/1 标签，530 行为缺失标签或 -1，后者全部记录排除原因且不补标。其他缺陷类型共 146 行：现有执行流程是空指针 `var == 0` 分析，缺少相应类型的可运行流水线，因此记录为未运行，未强行套用空指针约束。
原始 result=0 沿用为误报、1 为真实缺陷。与作者各 NPD 分组 gpt4omini_metrics 的 real_bug_num、总数交叉核对；不是独立人工重新标注。CodeQL/OpenSSL 有 1 条 -1，作者聚合记真实缺陷 9 条而现有 1 标签仅 8 条；Cppcheck/Linux 有 3 条 -1 和大量缺失标签，作者聚合与论文数量也存在差异。无法确认这些特殊值的逐条含义，不把它们改成真实缺陷或误报，不能重建精确论文集合。各组路径、数据 SHA、原始行号和标签数见 configs/expanded_*_manifest.json；完整范围清单见 results/processed/expanded_benchmark_scope.json。
没有重新扫描 Linux Kernel 或下载整工程。未运行 LLM4SA/LLMDFA 基线；不同模型、补全实现和基准版本的结果不能直接视为论文效果复现。

## 扩展实验实际结果（2026-10-26T01:09:38.819214+08:00）

本次覆盖 8 组 NPD 文件的全部 278 条现有 0/1 标签记录。最终成功执行 224 条、阻塞 39 条、执行失败 15 条，处理成功率 80.58%。复用原先 25 条最终记录，其余新增结果均单独保存；没有按可运行性或预测正确性筛选记录。

| 分组 | 已选定 | 成功执行 | 阻塞 | 运行失败 | 误报过滤率 | 真实缺陷保留率 |
|---|---:|---:|---:|---:|---:|---:|
| codeql_linux | 70 | 53 | 17 | 0 | 39.58% | 72.73% |
| codeql_libav | 57 | 51 | 4 | 2 | 0.00% | 50.00% |
| codeql_openssl | 49 | 42 | 0 | 7 | 14.63% | 100.00% |
| cppcheck_linux | 65 | 46 | 18 | 1 | 60.00% | NA |
| cppcheck_libav | 10 | 10 | 0 | 0 | 0.00% | 100.00% |
| cppcheck_openssl | 5 | 4 | 0 | 1 | 0.00% | NA |
| infer_libav | 6 | 6 | 0 | 0 | 0.00% | NA |
| infer_openssl | 16 | 12 | 0 | 4 | 0.00% | 100.00% |

| 实际类别 | 过滤 | 保留 | 未分类 |
|---|---:|---:|---:|
| 误报 | 64 | 128 | 49 |
| 真实缺陷 | 2 | 30 | 5 |

正类定义为“应过滤的误报”。全体选定样本含误报 241 条、真实缺陷 37 条。
误报过滤率=64/241=26.56%；真实缺陷保留率=30/37=81.08%；真实缺陷误删率=2/37=5.41%。
Precision=A/(A+C)=96.97%，Recall=A/N_FP=26.56%，F1=2PR/(P+R)=41.69%。
未分类记录保持未知、未当作过滤或保留，且不从分母中删除。未知结果使过滤率可能范围为 26.56%–46.89%，真实缺陷保留率为 81.08%–94.59%；当前比例只统计已确认结果。

最终尝试平均耗时（含上下文阻塞）：5.805 秒/条；成功执行样本平均 6.425 秒/条。复用样本使用其原实际耗时，并非本轮复用读取耗时。逐样本耗时与费用在 CSV/JSON 中。
本轮新增实际模型调用 996 次，新增费用保守上界 3.586168 元；全部阶段和早期失败累计 1187 次，费用上界 4.491330 元，未超过原累计 10 元限制。这是使用官方较高费率计算的估算上界，不是账户账单。


## 失败与错误案例

- 13 条：`Function kvm_for_each_vcpu: 0 distinct available definitions`
- 11 条：`Expected one function definition, found 0`
- 5 条：`JSONDecodeError: Expecting value: line 1 column 1 (char 0)`
- 4 条：`Cannot uniquely locate intermediate call site`
- 4 条：`ModelFailure: Response incomplete: finish_reason=length`
- 2 条：`Function IS_ERR_OR_NULL: 0 distinct available definitions`
- 2 条：`RuntimeError: Z3 repair attempts exhausted: ValueError: Unsupported generated-code operation`
- 2 条：`Function for_each_node_by_name: 0 distinct available definitions`
- 2 条：`Function list_for_each_entry_reverse: 0 distinct available definitions`
- 1 条：`Function ip6_route_mpath_should_notify: 0 distinct available definitions`
- 1 条：`Function skb_zcopy_pure: 0 distinct available definitions`
- 1 条：`Function rt6_is_dead: 0 distinct available definitions`
- 1 条：`Tracked value passed via an unsupported compound argument`
- 1 条：`RuntimeError: Z3 repair attempts exhausted: Z3Exception: Z3 sort expected`
- 1 条：`RuntimeError: Z3 repair attempts exhausted: ValueError: Returned boolean disagrees with last solver result`
- 1 条：`RuntimeError: Z3 repair attempts exhausted: TypeError: unsupported operand type(s) for &: 'ArithRef' and 'ArithRef'`
- 1 条：`Function for_each_pci_dev: 0 distinct available definitions`
- 1 条：`ReadTimeout: HTTPSConnectionPool(host='api.deepseek.com', port=443): Read timed out. (read timeout=10)`

- `NPD/codeql/kernel69:row=11:index=23`：误删真实缺陷；原始证据 `results/raw/completed/pilot/row_011`。
- `NPD/codeql/kernel69:row=10:index=22`：误删真实缺陷；原始证据 `results/raw/completed/expanded_codeql_linux/row_010`。

smoke 早期 4 次失败来自补全执行器未兼容函数内 z3 导入，pilot 另 1 次失败来自漏列标准 Function 接口；修复后重跑且原始记录和费用全部保留。扩展阶段的原始失败也保留，不根据标签修正模型输出或移除记录。

诊断例：CodeQL/Libav row 3 的脚本将 TYPE_END、TYPE_DSE 建模为没有固定取值的整数符号，得到 SAT 并输出保留；CodeQL/OpenSSL row 4 的实际查询仅含 alg == 0，也得到 SAT。这些记录说明“约束可运行”和“原 C 路径已被忠实还原”不同；宏、枚举值及数据流关系不充分时，很多误报可能仍被保留。本次没有为提高指标而补猜这些语义或按标签修改约束。

## 与论文的差异及后续

论文 v1 主实验模型 GPT-4o-mini，三类缺陷共 364 条/45 个真实缺陷。本次为公开 NPD 文件中 278 条可评估记录的补全版扩展，未恢复原始私有模块、精确论文数据集或其他类型流水线；因此只报告实际覆盖，不能声称完整论文复现成功。
原 5 条最小样本、20 条 pilot 报告已保存在 results/archive/before_expanded_experiment/，原始逐样本文件保持保留。汇总指标不会将这 25 条与 278 条再重复计数。
下一步优先人工检查被误删真实缺陷的赋值时序、goto/循环条件和宏语义，再向作者获取缺失模块及准确数据版本。扩大缺陷类型需要相应原始约束定义和可核验实现；本次未开展算法改进。

## 证据位置

- 全部逐样本 CSV/JSON：results/processed/expanded_all_npd.*；分组结果：completed_expanded_*。
- 混淆矩阵与完整指标：results/metrics/expanded_metrics.json、expanded_confusion_matrix.csv。
- 原始调用、使用量、模型响应、SMT、错误及费用账本：results/raw/completed/。
- 扩展阶段日志：logs/stage_07_expanded.md；汇总核验：results/raw/completed/expanded_verification.json。
