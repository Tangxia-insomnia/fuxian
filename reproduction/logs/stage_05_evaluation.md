# 阶段 5：评估与汇总

当前更新（2026-10-26）：已从小样本扩展到 8 组 NPD 的全部 278 条有效标签记录，224 条产生判定、39 条上下文阻塞、15 条运行失败。当前指标见 results/metrics/expanded_metrics.json，核验已通过。后文保留原小样本记录与新扩展结果；其他缺陷类型和未知标签仍未评估。

初始状态（补写前）：已汇总实际证据；监督评估和完整基准实验未运行。
时间：2026-10-26T00:01:44.098752+08:00（Asia/Shanghai）。

## 标签核查

- 原始字段 `result` 不能与流水线新生成的同名预测字段混淆。
- 选用的 CodeQL/Linux NPD 数据 70 条中，result=1 有 22 条，result=0 有 48 条，与论文表 5 和作者聚合结果 real_bug_num=22 一致，支持在此分组暂按 1=真实缺陷、0=误报理解。
- 缺少逐条标注规范；其他分组有 -1、缺失值及与论文数量不一致情况，不能全局套用标签映射。此次没有基于尚未完全核验的标签计算监督指标。

## 本次结果

| 项目 | 实际结果 |
|---|---|
| 离线组件样本 | 5（原始 0 标签 3 条、1 标签 2 条） |
| 条件提取及提示词生成 | 5/5 成功 |
| 平均本地组件耗时 | 0.00032716 秒；不含模型/SMT，非方法耗时 |
| 端到端尝试 / 成功 / 运行中失败 | 0 / 0 / 0 |
| 选定样本先决条件阻塞 | 5 |
| 选定样本最终结果覆盖率 | 0/5；不等同模型准确率 |
| 小规模 / 全量实验 | 均未运行 |
| API 调用 / 费用 | 0 / 0 元 |
| 混淆矩阵、误报过滤率、真实缺陷保留率/误删率 | 不可计算，无预测 |
| Precision / Recall / F1 | 不可计算，无预测；正类定义为误报 |

指标公式及失败样本处理规则见 `results/metrics/metric_definitions.md`。混淆矩阵保存为 NA，避免用全零矩阵误导；机器可读汇总见 `results/metrics/reproduction_metrics.json`。

## 与论文的可比性

论文主模型 GPT-4o-mini、364 条/45 个真实缺陷、三类缺陷；当前公开 README/数据不同，用户指定 deepseek-flash 也不同。当前无新模型结果，不能比较论文指标，更不能宣称论文完整复现成功。作者已有结果保留为参考，未运行基线。

## 后续

优先获取缺失官方模块与数据标签/运行缓存说明。公开入口恢复后再补本地 API 凭据，验证模型可用性和费用、完成最小端到端测试，之后才开展 pilot。此次不编写替代核心算法。


## 补全版实际评估更新

时间：2026-10-26T00:36:59.303117+08:00。以下是补全实现结果，原始审计阶段及旧 NA 指标保留在 archive 和原文件中，不相互替代。

| 项目 | 5 条 smoke | 20 条 pilot |
|---|---:|---:|
| 已记录样本 | 5 | 20 |
| 最终成功 | 5 | 16 |
| 最终运行失败 | 0 | 0 |
| 上下文阻塞 | 0 | 4 |
| 成功处理率 | 100.00% | 80.00% |
| 误报过滤率 | 66.67% | 50.00% |
| 真实缺陷保留率 | 100.00% | 70.00% |
| 真实缺陷误删率 | 0.00% | 10.00% |
| 误报正类 Precision | 100.00% | 83.33% |
| 误报正类 Recall | 66.67% | 50.00% |
| 误报正类 F1 | 80.00% | 62.50% |
| 平均当前尝试耗时（所有选定样本，秒） | 12.12122300000001 | 9.882719404999921 |

所有实际模型请求（包括早期失败及重跑）：191 次；按官方较高费率和 usage 得到的费用保守上界：0.905162 元，低于 10 元。不是账户账单数值。
首轮执行器问题产生的失败尝试：smoke 4 次、pilot 1 次，全部在 attempt_history 和 raw 中保留；没有为了提高指标删除样本。上表预测用实现修复后的最终尝试，费用统计包括所有尝试。

标签使用官方 Linux NPD 分组 result=0 为误报、1 为真实缺陷，其 22 个 1 标签与论文表 5/作者 real_bug_num=22 一致；未对 -1 或缺失标签进行推断，未声称人工独立复核每条缺陷。
正类为误报。混淆矩阵行是真实误报/真实缺陷，列为过滤/保留；失败另列未分类。设 A/B/C/D 为这四格，过滤率=A/N_FP，保留率=D/N_bug，误删率=C/N_bug，Precision=A/(A+C)，Recall=A/N_FP，F1=2PR/(P+R)。无预测行仍留在全体分母中；有缺失时比例只表示已确认结果并同时报告覆盖率/上下界。
pilot 有 2 条误报和 2 条真实缺陷未分类。考虑这些未知结果后，全部选定样本的误报过滤率可能范围为 50.00%–70.00%，真实缺陷保留率为 70.00%–90.00%；表中数值仅计已确认的过滤/保留，未把阻塞默认判为保留。
本次仅为单一项目、单一工具、单一缺陷类型的分层小样本测试，类别比例不是原论文自然分布，不能外推总体表现。模型为 DeepSeek-V4.1-Flash-1017，公开实现有补全及错误处理修复，也不等同 GPT-4o-mini 论文设置。


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


## 扩展交付核验完成（2026-10-26T01:12:21.446086+08:00）

278 个样本均有结果记录，224 成功、39 上下文阻塞、15 运行失败。实际核验通过：原始数据标签/索引、CSV/JSON、逐样本模型和 SMT 证据、每次调用与费用账本、指标重算均一致；原先 25 条无重复累计。1187 次调用累计保守费用上界 4.491330 元，无未完成预留；上游 Git clean；扫描 2797 个交付文件未发现本地用户密钥。详细核验输出见 results/raw/completed/expanded_verification.json；源码/配置/数据哈希见 configs/expanded_run_identity.json。10 项本地测试输出见 results/raw/completed/expansion_regression_tests.txt。
