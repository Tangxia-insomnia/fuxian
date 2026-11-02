# E05 源码审查（实施前）

基线为发布 main `b425ec2bf143ae74a3764e6a4a5f242099d10d68`，上游冻结 `4efb4b9bf7e845e180451b43ba29a25e3edaa0e3`。`baseline_state.json` 保存 4415 个原有文件的 SHA-256，核对了 E04-ND 原始保护清单、候选冻结清单和结果哈希。发布副本历史上存在换行规范化及脱敏账本/快照差异，本轮不替换这些历史文件；本地保护以原有本地字节为准。

## 三层区别

| 层 | 位置 | 本轮审查结论 |
| --- | --- | --- |
| 官方 U02 类型规则 | `upstream/llm4pfa/prompt_templates.py:1–20,37–54` | 要求未知变量默认 Int，倾向 0/1；没有 C 声明、成员身份和分支方向验证。保持原文。 |
| 官方 U05/U06 | 同文件 `92–134` | U05 按源码分析；U06 只返回新增约束。不是语义验证器。 |
| 官方 U10 | 同文件 `195–221` | LLM 优化/补声明，无法据此证明变量身份或极性正确。 |
| 官方 pipeline | `upstream/llm4pfa/feasibility_analysis_pipeline.py:173–180,223–249` | 人工加入目标空指针假设，与路径条件必须区分；旧路径会把 Δ 单独送 U10。 |
| E03 补全 | `completion/engine.py:69–86,227–247`；`completion/constraint_bundle.py` | 显式合并 B+Δ，在求解异常捕获之外进行结构门控；不验证 C 语义。 |
| E01 | `safety_runs/E01_predicate_polarity_consistency/predicate_check.py` | 只支持单个 zero-test 原子，不能直接识别 Or 恒真式；源码身份和上下文证据要求保留。 |
| E02 | `safety_runs/E02_base_constraint_preservation_static/checker.py:487–579` | 结构成员、字面符号和 sort 保留检查；不执行代码、不证明极性。 |

本轮只新增 E05 静态模块，不把它接入生产 engine，也不修改提示词或六条件安全门槛。

## 原始问题依据（只读检查，不计冻结后回放结果）

- A01：E02 `evidence/audit_10_frozen_candidate/01/bundle.json#/context/frames/0`，函数体第 234 行 `if (!copied)`，第 235 行目标。`calls/0224.json` U02 为 `Not(copied == 0)`。这是局部方向冲突；函数中的循环、goto 和赋值尚无完整状态证明。
- A04：E02 `evidence/audit_10_frozen_candidate/04/calls/0231,0234,0235,0238.json`，`object` → `object_ptr`，后续 `object_bv`，原有契约的类型/身份缺口须保留，不能推测为同一对象。
- E04-ND：`safety_runs/E04_nonempty_delta_validation/selected_source.c` SHA-256 `4f652c2800b05d4fab8cf926af60a66c348cbdd8e5cc95f2620555feaf1e20a9`。170 行声明 unsigned fraggap，176 行 `fraggap = skb->len - maxfraglen;`，271 行 `if (fraggap)`，275 行目标。1192 U02 为 `Or(fraggap == 0, fraggap != 0)`；1194 U06 为 `fraggap == skb - maxfraglen`。模型注释的 270 行和实际一基 271 行必须分别保留。
- E04-ND 的 `skb->len` 成员定义不在保存的函数体中；可以识别表达式被换成指针，不能伪造成员声明/类型。`skb` 多次赋值、`maxfraglen` 的地址传参、unsigned 运算都不属于本轮完整支持范围。

参考已读材料：E01 报告、E02/E03/E04 README 和实验报告、E04-ND 报告、`agent_reproduction_audit/prompt_audit/` 与 `agent_reproduction_audit/smt_z3_audit/`。历史输出始终作为数据读取，不执行。
