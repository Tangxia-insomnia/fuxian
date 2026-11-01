# 条件极性一致性审计

风险 A 的结论：冻结公开 Prompt 存在直接冲突，历史 A01 也确实发生过局部条件反向编码。E01 能发现这一小子集错误，但没有证明全部控制流、宏或跨函数合并正确。本阶段只读取这些既有材料，没有重跑 E01 或 Z3。

## 1. 必须区分的三种否定

对已知类型、同一状态版本的简单标量/空指针判定，局部语义如下。此表用于解释，未作为新实验执行。

| 原表达式 | true 分支要求 | false 分支要求 |
| --- | --- | --- |
| `ptr` | `ptr != 0` | `ptr == 0` |
| `!ptr` | `ptr == 0` | `ptr != 0` |
| `!!ptr` | `ptr != 0` | `ptr == 0` |

表达式自带的 `!`、选择 false 分支的否定、为了避免提前退出而否定退出条件，是不同来源。对于共同构成一次退出的条件 `c1 && c2`，避免它应为 `!(c1 && c2)`，等价于 `!c1 || !c2`；不能将否定分别合并成 AND，也不能在已经取反后再次无依据取反。含副作用、宏、重赋值或复杂类型时不能直接套此表。

[论文](https://arxiv.org/pdf/2506.10322v1) 第 4–5 页 §3.2.1 区分到达 Sink 条件和提前退出条件的否定；附录 C 第 11 页没有展开 `[SMT Query Script Generation Rules]`，所以不能认定作者公开了一套覆盖这些情况的确定性规范。

## 2. 官方 Prompt 和代码的冲突

| 位置 | 原文/行为 | 风险 |
| --- | --- | --- |
| [共享规则:6、15][prompt] | `Convert !ptr to ptr==0 for Int variables`；`Convert !ptr or Not(ptr) to ptr==0 only` | 局部 `!ptr` 的零判定与此一致，但缺少分支方向和断言角色 |
| U07:148 | `Convert C-style expressions properly (e.g., !ptr to ptr!=0)` | 与共享规则及简单表达式语义直接相反；不能无依据理解成“隐含 false 分支” |
| 共享规则:9–10、18 | False 用 `==0`，True 用 `==1`，偏好 `==1/==0` | 任意 C 非零值为真，不能普遍收窄成数值恰好 1 |
| [extractor:196–211][extractor] | else 分支拼接前面条件的否定 | 已带分支含义，但输出没有独立 edge 字段，LLM 可能重复取反 |
| [pipeline:116–125、276][pipeline] | 将一次提前退出的条件列表拼成多个否定的 OR | 只有列表确实表达同一次退出的合取时才正确；输入可能含 `if (...)` 字符串，不能只看拼接符证明语义 |
| pipeline:328–335 | 已处理的提前退出条件再交 U07，随后 U09 重新合并 | U07 的冲突示例、语义筛选和合并都可引入错误；没有确定性极性检查 |

不能将所有 UNSAT 都归因于 U07。A01 的错误来自 U02，即使 U07 未参与也会出现。

## 3. 历史 A01：可定位的实际错误

原函数片段 [frame_00_tcp_sendmsg_locked.c:234](../../audit/failure_audit_20261029/samples/A01/frame_00_tcp_sendmsg_locked.c#L234) 为 `if (!copied)`；保存提取结果中的 `line_number=233` 是零基，不能误当文件绝对行号。E01 保存的声明证据在函数片段第 7 行，`copied` 是 int；函数体 SHA-256 为 `0a179a0178f81a9211efd84d9baa3efce16afafb9dd8dbe54c47eb63e5064590`。

历史响应链：

- [0224.json:9、37](../../audit/failure_audit_20261029/samples/A01/calls/0224.json#L9)：U02 输入 `if (!copied)`，输出 `s.add(Not(copied == 0))`，即相反方向。
- [0226.json](../../audit/failure_audit_20261029/samples/A01/calls/0226.json)：U06 返回 `s.add(copied == 0)`，同时注释复述旧的相反断言。
- [0227.json:37](../../audit/failure_audit_20261029/samples/A01/calls/0227.json#L37)：U10 把 `Not(copied == 0)`、`skb == 0`、`copied == 0` 一起写入函数。
- [solver_01_query_01.smt2](../../audit/failure_audit_20261029/samples/A01/solver_01_query_01.smt2) 保存上述矛盾；[recorded_raw/solver_01.json](../../audit/failure_audit_20261029/samples/A01/recorded_raw/solver_01.json) 记录历史 `unsat`。本阶段没有重放此公式。

这里不需要删除矛盾断言来“修好”结果；错误候选应先被拒绝并保留证据。局部错误检出不等于独立证明整条 C 路径。

## 4. E01 已保存结果及覆盖局限

只读来源：[test_results.json](../../safety_runs/E01_predicate_polarity_consistency/test_results.json)、[audit_results.json](../../safety_runs/E01_predicate_polarity_consistency/audit_results.json)、[holdout_results.json](../../safety_runs/E01_predicate_polarity_consistency/holdout_results.json)、[metrics.json](../../safety_runs/E01_predicate_polarity_consistency/metrics.json)。

| 历史项目 | 已保存结果 |
| --- | --- |
| 参数化合成测试 | 156/156 通过；本阶段未重跑 |
| 10 条审计集 | 291 条记录条件，局部检查 1 条；A01 检出 1 个条件冲突、3 次错误原子出现 |
| 固定 20 条回归集 | 312 条记录条件，局部检查 0 条，未检出冲突不等于没有错误 |
| 合计 | 1/603 条可局部核对，覆盖率约 0.1658%；整样本支持数 0 |
| 历史安全 v1 → E01 结果 | 合计从 0 FILTER / 15 KEEP / 15 UNKNOWN 变为 0 / 0 / 30；这是旧日志，不是本阶段裁决 |

[predicate_check.py:79–112、119–175](../../safety_runs/E01_predicate_polarity_consistency/predicate_check.py#L79) 对简单零比较、重复否定、分支和符号证据做检查；[offline_adapter.py:187–221](../../safety_runs/E01_predicate_polarity_consistency/offline_adapter.py#L187) 明确不捏造断言角色/来源，`whole_sample_supported=False`。历史 R01 叠加层只降级、不批准过滤（`run_e01.py:70–79`）。

A02、A04、A10 在保存结果中都是 unsupported。A10 的宏表达式没有被错误报成简单标量极性冲突，**也没有因此通过宏语义验证**；A04 变量身份问题仍在。E01 没有覆盖完整跨函数 P、类型变化、宏展开和合并过程。

## 5. 仍待核查的跨函数风险

官方 pipeline:420–433 的条件筛选及 159–162 的覆盖会丢状态关系；这与“明确发现极性翻转”是不同问题。本次没有发现足以证明跨函数每一跳极性均保持的证据，也不把状态丢失自动统计成新增极性错误。恢复时须保留每次否定的原因和变量身份，不改原始 Prompt，不绕开安全 v1。

[prompt]: https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/4efb4b9bf7e845e180451b43ba29a25e3edaa0e3/llm4pfa/prompt_templates.py#L1
[extractor]: https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/4efb4b9bf7e845e180451b43ba29a25e3edaa0e3/llm4pfa/extract_util_plus.py#L196
[pipeline]: https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/4efb4b9bf7e845e180451b43ba29a25e3edaa0e3/llm4pfa/feasibility_analysis_pipeline.py#L116
