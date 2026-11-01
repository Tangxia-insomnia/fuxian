# 约束合并与跨函数传播审计

本阶段只静态追踪字符串、消息与既存脚本，没有执行任何生成代码或 Z3。版本见[总报告](smt_z3_audit_report.md)。

## 1. 论文要求的保留关系

[论文](https://arxiv.org/pdf/2506.10322v1) 第 6 页 §3.3 要求每组新推理范围立即转为约束并合并进当前脚本，再求解；第 11 页附录 C 的合并提示词明确写道：

> “Please combine them into a single script and keeping all existing constraints (both from the original script and the new constraint sets).”

第 5 页 §3.2.2 要求后续函数的 P 包含前一函数与传入参数有关的路径约束。二者分别是同一函数内的增量保留和跨函数的状态传播，不能混为“拼接几个字符串”。

## 2. 同一函数内的真实数据流

以 B 表示 U02 基础片段，Δ 表示 U06 新增片段，T 表示 U10 输出，G 表示 U07 提前退出约束，M 表示 U09 最终输出：

```text
目标条件 + NULL 假设 ─U02→ B
B + 范围分析消息 ─U06→ Δ
Δ（新会话，未附 B） ─U10→ T ─执行→ bool
若有提前退出条件：B + T + G ─U09→ M ─执行→ bool
```

来源：[pipeline:174–178、231–240、274、328–349][pipeline]；模板 [U06:109–134、U09:171–193、U10:195–221][prompt]。

关键问题如下：

1. U06 要求保留旧约束，同时要求“Only include new constraint lines to be added”（131）。返回值按增量设计，但调用方按完整脚本处理。
2. U10 只有一个 `m1` 参数；236 行传入 Δ，237 行清空会话。没有确定性 `B + Δ` 合并，也没有保存断言 ID/集合的程序检查。
3. U09 的第一个参数确实是 B，要求保留全部基础约束（183）。这只能使存在提前退出分支的后续合并**有机会**重新引入 B，不能修复早于此处的错误短路，也不能保证每条路径都会运行 U09。
4. U10/U09/U01 都可以重新声明变量或重写断言；没有统一符号表和变更审计。语法修复可能改变语义，即使返回 bool 与最后一次 solver.check 相符也无法发现。

历史上发生过的中间丢失与最终重引入，见[基础约束专项](base_constraint_preservation_audit.md)；不把静态风险泛化为“每个最终脚本都丢约束”。

现存生成快照 [patches/completed_function_bodies.py:195–205、293–311](../../patches/completed_function_bodies.py#L195) 也保留上述 U10 单输入及 U09 三输入调用，仅把执行换成 `solve_z3`；其 SHA-256 为 `081b63a4caba0236734263119041a61bbcd0c3b37c1f048f9d79c47b3c977b3f`。本阶段直接读取快照，没有运行 `completed_source()` 重新生成或覆盖它。

## 3. 跨函数状态传递

| 层次 | 实现与证据 | 审计结论 |
| --- | --- | --- |
| 官方参数映射 | pipeline:398 调 `get_param_name`；依赖未公开内部工具导入 11–12 | 缺失组件的原始语义无法确认 |
| 官方条件筛选 | 420 从裸函数名提取实参；427 对字典做成员判断 | 无法可靠筛出应传播的条件 |
| 官方递归入口 | 433 传入筛选结果；159–162 立即用当前函数重新提取结果覆盖 | 参数相关前提未得到可验证的保留 |
| 补全版映射 | [context.py:86–100](../../completion/context.py#L86) 检查唯一直接实参/形参 | 能恢复有限名字映射；没有类型、别名、状态版本和完整约束重命名 |
| 补全版修补 | [engine.py:64–65](../../completion/engine.py#L64) 修正实参入口和字典条件文本 | 不修复递归入口覆盖，也不传播一个类型化 P |

每个 frame 会重新建立 `var_name == 0`，但这不能代替调用前的赋值关系、其他参数条件以及同一对象的身份一致性。历史 A04 的 `object`、`object_ptr`、`object_bv` 分离，证明“保留断言文字”仍可能丢掉同一对象关系，见 `samples/A04/calls/0235.json`、`0238.json`，详细定位在[基础约束专项](base_constraint_preservation_audit.md)。

## 4. Memory 与 Harness 的界限

论文第 6 页的 Memory 缓存“同一函数调用在不同 P 下的返回值范围”。冻结 pipeline:378 的 `result_memory_cache` 检查被注释；127–138 的 `function_cache` 主要缓存函数体，不能当作 P 敏感的范围记忆。补全版 `engine.py:156` 初始化 `function_cache={}`，也没有恢复论文 Memory。

现有 MCP 仅检索函数源码；第三阶段 `workflow.py:1–5` 明确是离线参考状态机。用户报告的第四阶段真实 Agent 检索能力与上述 SMT 状态传递是两条证据链，当前没有把检索轨迹直接转换为经校验的约束集合的现成连接。

## 5. 后续最小改动方向（尚未实施）

优先隔离 B、Δ、T，记录不可变基础断言和声明，任何重写必须能追溯；先做不执行 Z3 的结构保留测试，再另行审批求解测试。跨函数 P、别名和类型传播应作为独立后续问题，不能夹在一次合并修复中，也不能用改名规避矛盾。保留不正确的基础约束仍会出错，因此须与极性检查分别验证。

[pipeline]: https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/4efb4b9bf7e845e180451b43ba29a25e3edaa0e3/llm4pfa/feasibility_analysis_pipeline.py#L231
[prompt]: https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/4efb4b9bf7e845e180451b43ba29a25e3edaa0e3/llm4pfa/prompt_templates.py#L109
