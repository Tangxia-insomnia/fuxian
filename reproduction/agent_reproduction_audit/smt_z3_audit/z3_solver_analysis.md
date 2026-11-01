# Z3 调用、结果协议与安全层审计

本文件中的求解结果均引用已有日志；**本阶段没有运行 Z3，也没有生成新的 FILTER/KEEP/UNKNOWN 裁决**。

## 1. 三种结果不能混用

| 层次 | 结果 | 能说明什么 |
| --- | --- | --- |
| Z3 原生 | `sat` | 当前编码公式存在模型；不等于发现真实缺陷，也不证明源码路径可执行 |
| Z3 原生 | `unsat` | 当前编码公式无解；只有编码忠实且上下文完整，才能用于路径不可行结论 |
| Z3 原生 | `unknown` | 求解器没有确定答案，可能与资源或理论支持有关；不是 `unsat` |
| 生成的 Python | `True` / `False` | 是脚本自身的返回值；需要核对实际执行过的查询及转换规则 |
| 本项目安全策略 | `FILTER` / `KEEP` / `UNKNOWN` | 是现有告警操作协议；策略 UNKNOWN 的原因远多于 Z3 unknown；其操作是保留告警 |

[论文](https://arxiv.org/pdf/2506.10322v1) 第 4 页 §3.1 返回 True 表示存在可行路径、False 表示不可行；第 6 页 §3.3 将 UNSAT 视为不可行并短路分析，错误最多修复 3 轮。正文与附录没有明确给出完整的 solver unknown、超时和布尔结果冲突协议，故记为未公开，不能补成作者方法。

## 2. 官方冻结代码

[pipeline:248–264、346–364][pipeline] 通过 `exec(final_response, globals())` 调用模型生成的 `check_constraints()`，按 Python truthiness 判断 `if not result`。没有统一捕获原生 Z3 结果、统一布尔转换、断言快照或逐断言来源；模板 U09/U10 只要求返回 boolean。

如果生成脚本写 `return s.check() == sat`，Z3 unknown 会被表达式变成 False；这是**静态协议风险**，不是本阶段新观察到的 unknown 实例。若脚本返回其他对象，官方调用方也没有严格验证类型。

两处 `while cnt <= 3` 在循环开头递增（244–246、342–344），最多执行 4 次；第 4 次失败仍可生成一份不再执行的修复脚本（265–272、365–372）。这个实现与“初次执行 + 最多 3 次经过验证的修复”的清晰协议不同。

此外 pipeline:211–219 可因 U04 自然语言包含 `Not satisfied` 而直接返回 False，未要求求解证据；376–393/409–417 的原版缺上下文路径可能返回 True。不能将所有官方布尔结果统称为经 Z3 验证的结论。

## 3. 当前补全版

[engine.py:41–45](../../completion/engine.py#L41) 把上述执行替换为独立 worker，并在第 4 次执行失败后抛错；48–50、132–147 补充“没有目标/提前退出条件时”的基础查询。它未实现论文所述所有情况下生成初始脚本后立即求解的统一步骤。

[engine.py:110–130](../../completion/engine.py#L110) 为每次执行保存 `source`、事件编号、frame level、结果/异常到 `solver_XX.json`；子进程限制 15 秒，移除凭据相关环境变量。worker 内部每个 Solver 默认超时 5000 ms。这里是现有实现的静态描述，没有执行其入口。

[solver_worker.py:11–72](../../completion/solver_worker.py#L11) 的协议：

1. AST 限制导入和部分危险操作，给生成代码提供受限命名空间；这不是完整操作系统沙箱或 C 语义证明。
2. 用 `TrackedSolver.check` 记录原生结果字符串和当时 `to_smt2()`（43–46）。
3. 强制返回 Python bool，且至少有一次实际 Solver.check（64–67）。
4. 任一已记录结果是 unknown 就报错，拒绝转换成布尔判定（68–69）。
5. 返回 bool 必须等于**最后一次查询**是否 sat（70–72）。

局限：不检查基础断言是否保留，不统一符号身份，不保证最后查询包含前面所有约束；push/pop、多 Solver 等行为需要单独追踪。`check(*args)` 允许额外假设，但记录仅保存 `to_smt2()`，没有单独保存 assumptions 参数，可能不足以重放同一个查询。CLI 的异常分支只返回 `{ok:false,error}`（75–80），可能丢失错误前已记录的查询，也没有 `reason_unknown()` 字段。上述是代码风险，不是新实验结果。

## 4. 现有安全 v1 如何衔接

[safety/replay.py:49–74](../../safety/replay.py#L49) 从历史候选结果、去标签告警、源码 frames、原始回答、solver 事件和既有问题构造 evidence bundle。[policy.py:38–69](../../safety/policy.py#L38) 重放最后一事件的最后一条 SMT2，核对非空断言、sat/unsat 和 bool 一致；注释明确是“formula replay only; source semantics not established”。

[policy.py:14–17、72–114、117–176、180–224](../../safety/policy.py#L14) 保持六项门槛：目标定位、控制条件、变量身份、约束语义、求解有效性、上下文完整性。原始候选不可直接作为 FILTER；该分支还要求独立且绑定具体源码/公式的语义复核。代码检查复核身份、哈希、行号和逐断言覆盖，**不验证复核意见本身的真伪**，不能由同一生成器填一个 review JSON 冒充独立证明。

它目前是独立离线保护入口，不是 CompletedEngine 或 Harness 的自动钩子。MCP [tools.py:35–40](../../harness_bridge/tools.py#L35) 只有两项检索工具，没有求解或裁决工具。E01 `run_e01.py:103–109` 调用安全 v1 后叠加拒绝性极性检查；这些入口都会求解，本阶段均未运行。

## 5. 恢复前建议

未来先定义区分 SAT、UNSAT、solver UNKNOWN、执行错误、超时和证据缺失的记录协议，保留源码/公式/assumptions/修复前后差异，再单独验收求解执行。即使求解成功，也须保持现有六条件和独立语义复核要求；不得让 bool 或 UNSAT 绕过安全层。该建议未修改任何实现或门槛。

[pipeline]: https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/4efb4b9bf7e845e180451b43ba29a25e3edaa0e3/llm4pfa/feasibility_analysis_pipeline.py#L244
