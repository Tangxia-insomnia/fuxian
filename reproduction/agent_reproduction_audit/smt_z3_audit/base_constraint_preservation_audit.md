# 基础约束保留专项审计

风险 B 的结论：**存在确定的接口缺口，并有历史 A04 中间脚本的实际丢失证据。**不能据此声称所有样本的最终脚本均丢基础约束；A04 后续 U09 又显式传入并重引入部分基础断言，A01 则保留了错误的基础断言。保留完整性与语义正确性必须分别检查。

## 1. 基础脚本来自哪里

[pipeline:174–180][pipeline] 将当前目标条件与 `var_name == 0` 交给 [U02:37–54][prompt]，得到 `response_message_target`。这是 LLM 输出的基础声明/断言片段，不是数据集提供的既有 SMT2，也不是已经由静态分析器证明正确的公式。

官方没有保证此时片段已含 Solver 和 `check_constraints()`，也没有立即统一执行基础查询；补全版仅修补了空条件路径（[engine.py:48–50、132–147](../../completion/engine.py#L48)）。

## 2. U06 → U10 接口核验

U06 原文同时要求：

> “DO NOT modify or delete existing constraints”
>
> “Only include new constraint lines to be added”

来源 `prompt_templates.py:119、131`。它把 B 放在输入里，但按 Δ 输出。pipeline:233 解析 Δ，236 仅把 Δ 交给 U10，237 重置消息列表；U10 的 `m1` 即为这一个输入（195–200），没有第二个基础脚本参数。**调用方没有真正完成 B 与 Δ 的确定性合并。**

U09 的输入包含 `response_message_target`（335），原文要求 “Retain ALL original constraints from the base script”（183）。但 U09 只在相关提前退出流程运行，且前面的 T 求解可能已短路，无法作为通用修复。

## 3. A04 的实际历史证据链

以下文件都在 `audit/failure_audit_20261029/samples/A04/`，本次仅解析 JSON 和文本，未执行脚本。

| 步骤 | 保存证据 | 检查到的事实 |
| --- | --- | --- |
| U02 基础 B | [calls/0231.json](../../audit/failure_audit_20261029/samples/A04/calls/0231.json) 的 `/choices/0/message/content` | 声明 `folio_test_slab`、`object` 为 Int，断言二者 `== 0` |
| U06 增量 Δ | [calls/0233.json:21、49](../../audit/failure_audit_20261029/samples/A04/calls/0233.json#L21)；`/messages/3/content` 与 `/choices/0/message/content` | 输入含 B，输出只有注释，称无须新增约束，没有保留基础断言代码 |
| U10 输入 | [calls/0234.json:9](../../audit/failure_audit_20261029/samples/A04/calls/0234.json#L9)，`/messages/0/content` | 仅一条 user 消息；`Input Z3 script` 段只有 Δ 的注释，B 不在输入中 |
| U10 输出 | 同文件第 37 行，`/choices/0/message/content` | 用 Python 常量 `object_ptr = 0` 和列表代替原 Z3 符号/断言，没有实际 solver.check |
| 执行失败 | [recorded_raw/solver_02.json](../../audit/failure_audit_20261029/samples/A04/recorded_raw/solver_02.json) | 旧 worker 记录 `ValueError: ValueError: No actual Solver.check executed` |
| U01 修复输出 | [calls/0235.json:45](../../audit/failure_audit_20261029/samples/A04/calls/0235.json#L45)；[solver_03.py](../../audit/failure_audit_20261029/samples/A04/solver_03.py) | 只建 `object_ptr = Int('object_ptr')` 和 `object_ptr == 0`；基础 `object`、`folio_test_slab` 的声明/断言均未保留 |
| 修复后历史查询 | [solver_03_query_01.smt2](../../audit/failure_audit_20261029/samples/A04/solver_03_query_01.smt2)；`recorded_raw/solver_03.json` | 保存公式只有 `object_ptr` 的零断言，旧结果 sat；本次未重放 |
| 后续 U09 | [calls/0238.json:9、37](../../audit/failure_audit_20261029/samples/A04/calls/0238.json#L9)；[solver_04_query_01.smt2](../../audit/failure_audit_20261029/samples/A04/solver_04_query_01.smt2) | 输入重新包含 B；输出恢复 `object == 0`、`folio_test_slab == 0`，同时保留独立 `object_ptr == 0`、另建 `object_bv != 0` |

这里可确认“原始声明和断言没有被原样保留”，不是仅凭字符串差异猜测语义等价：新公式根本没有旧符号。也不能声称已证明两份公式之间的逻辑蕴含或完整 C 语义，因为本阶段未求解，也没有对象身份映射证据。U09 最终的不同符号/不同 sort 并未建立等式关系，仍然无法据此确认同一对象状态一致。

## 4. 对照 A01：不能盲目保留错误公式

A01 的 U06 注释复述了错误基础断言，U10 因而重新生成它；[0227.json:37](../../audit/failure_audit_20261029/samples/A01/calls/0227.json#L37) 中 `Not(copied == 0)` 与 `copied == 0` 并存。此例说明 U10 即使看不到完整 B，也可能靠注释猜回旧约束；偶然猜回不是保留机制，而且会保留错误极性。详见[极性专项](polarity_consistency_audit.md)。

不能为得到 SAT 删除矛盾断言；也不能把“所有旧断言都保留了”当作 C 编码已经正确。应拒绝不一致候选、保留变更与来源证据，再分别解决语义和保留问题。

## 5. SHA-256 与复核边界

| 历史文件 | SHA-256 |
| --- | --- |
| A04/calls/0233.json | `ec1ea050b7d75f76683a320c6df8e47abcf54918a89712f236618c141275f6a7` |
| A04/calls/0234.json | `93a3486c9c2f43c8670b8846df0f524949186a13e70afb9e3a69f153209e4197` |
| A04/calls/0235.json | `87ce47e1eca4426c04c2520c9c56037ea232da499b3cbabdcf676ccb04a26076` |
| A04/calls/0238.json | `3744ad74644fb70a9f07d719f54b6346ffda4674ef91de970841233b7fd4b21d` |
| A01/calls/0224.json | `08bfcf5e3253fed0d007755212bf00d1fb2993ae2628f6c3e3f4e5a302710cb4` |
| A01/calls/0227.json | `9845a065258bbf613e9cbf8c662d2364c2a4284d0cd80f775f3164bc80a891ea` |

这些是已保存的补全版 DeepSeek 调用证据，不能冒充作者原始实验响应。本次没有对全体历史调用计算基础约束丢失率；只提交能够逐步追踪的具体案例和通用代码缺口。

[pipeline]: https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/4efb4b9bf7e845e180451b43ba29a25e3edaa0e3/llm4pfa/feasibility_analysis_pipeline.py#L174
[prompt]: https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/4efb4b9bf7e845e180451b43ba29a25e3edaa0e3/llm4pfa/prompt_templates.py#L109
