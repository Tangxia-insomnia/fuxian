# E03：B/Δ 显式传递修复报告

日期：2026-11-02。实验：`E03_base_delta_explicit_transfer_fix`。

本轮完成补全版正常 U06→U10 路径的确定性 B+Δ 传递及前后置静态检查。23/23 合成场景、18/18 接入检查、2/2 指定缓存案例验收通过。没有真实调用 U10、模型、Harness 或 Z3；没有运行完整 10 条审计集或固定 20 条回归集。本结论限于静态结构契约，不代表路径可行性或完整 LLM4PFA 已恢复。

## 1. 固定基线和问题确认

- 发布仓库 main 基线：`aff6fe9d46bf6b20ff02be7218aba4386653cd7e`。
- 官方上游：`4efb4b9bf7e845e180451b43ba29a25e3edaa0e3`，未修改。
- 开始时发布仓库和官方上游均干净；本地 reproduction 是独立工作目录，不将其冒充 Git 仓库。
- [baseline_state.json](baseline_state.json) 保存原始 4133 个非凭据文件的 SHA-256、Git 状态及允许修改范围；原 engine 字节另存 [engine.before.py.txt](engine.before.py.txt)。
- 官方 [pipeline](../../upstream/llm4pfa/feasibility_analysis_pipeline.py#L178) 在 178 行获得 U02 原始 `response_message_target`，232 行获得 U06 原始响应；236 行只将解析后的 Δ 传入 U10。目标语句只有一处，与任务描述一致。
- 先前依据：[基础约束审计](../../agent_reproduction_audit/smt_z3_audit/base_constraint_preservation_audit.md)、[合并审计](../../agent_reproduction_audit/smt_z3_audit/smt_merge_analysis.md)、[E02 报告](../E02_base_constraint_preservation_static/E02_report.md)。

## 2. 实际修改

1. 新增 [constraint_bundle.py](../../completion/constraint_bundle.py#L103)：保留 U02/U06 原始字符串、来源、原始哈希、解码代码哈希及合并内字符区间。只解码单一 Markdown 代码围栏，逐字拼接两段代码，并插入来源注释。不改名、不推断类型、不简化、不删除矛盾或重复断言。
2. 修改 [engine.py](../../completion/engine.py#L70)：精确替换正常路径目标一次；使用原始 B 和原始 Δ 生成 bundle，只有静态检查接受时才把 `merged_script` 交给原 `get_z3_extract`。目标出现 0 次或多次立即停止。
3. 在 [engine.py](../../completion/engine.py#L86) 中，将输出检查放在求解 `try/except` 之前，每次均用同一份原始 B/Δ 检查当前输出。FAIL/UNKNOWN 直接抛出并保存证据，不进入求解和模型修复分支；已有求解错误触发的 U01 修复输出也不能绕过检查。
4. [run](../../completion/engine.py#L174) 显式注入两个绑定方法；[record_transfer](../../completion/engine.py#L214) 排他创建逐事件 JSON，包含 dataset、position、sample_id、frame、阶段、三份哈希及结构计数。
5. 新增 [test_constraint_bundle.py](../../completion/test_constraint_bundle.py)。

唯一额外的存档行为调整：`completed_source()` 原先覆盖 `patches/` 的快照，现在排他写入 E03 新目录（或测试显式给定的新目录）。这是保护历史文件所必需的改动，不改变算法。U07/U09、原 `solve`、`solve_base`、上下文准备及响应解析方法的 AST 与基线一致。

适配器只读动态加载原 E02 `check_contract`；固定 SHA-256 为 `5a0d6532e73af8485113541fd3982f491ddeef0b6b44c7f856ad61d649a1916a`，每次使用前核对。没有复制或放宽 E02 解析器。除 `contract_status == PASS` 外，还拒绝重复声明、类型/身份冲突、解析错误及缺少原始证据。空 Δ 字符串表示真实的空输出，与缺失 Δ（None）严格区分。

## 3. 验证结果与口径

| 验证 | 实际结果 | 结论范围 |
| --- | --- | --- |
| 通用合成场景 | 23/23 符合预期 | 包含全部 T01–T14；“通过”包含按预期拒绝，不等于 23 次约束准入 |
| 接入及停止位置检查 | 18/18 通过 | 源码渲染/AST、精确补丁、绑定方法、离线观察器；未执行完整 pipeline |
| A04 缓存重放 | 旧输入 FAIL；新输入 PASS；旧输出 UNKNOWN，被拒绝 | 新输入保留 2 个原始声明和 2 个原始断言；没有新的 U10 输出 |
| A01 缓存对照 | 旧输入 FAIL；新输入 PASS；旧输出结构 PASS | 相反条件均保留；语义与极性 NOT_ASSESSED |
| 模型调用 / Z3 / 历史代码执行 | 0 / 0 / 0 | API 费用 0 元；不含历史实验原有费用 |

合成与接入检查耗时约 0.352 秒；指定历史检查约 0.103 秒，均为检查脚本计时，不是端到端模型耗时。计数、拒绝原因及重复断言口径见 [metrics.json](metrics.json)、[synthetic_test_results.json](synthetic_test_results.json)。

A04 的旧 U10 输出基于旧 Δ-only 输入生成，不能冒充修复后模型响应。E02 在其 List 表达式处返回 UNKNOWN；适配器拒绝并保留原文。旧 U01 仍缺失 2 个基础声明、2 个基础断言，报告 2 个身份缺口；U09 后续虽恢复部分 B，仍存在额外输入集合缺失/类型及身份冲突。见 [A04_replay_report.md](A04_replay_report.md)。

A01 的 `Not(copied == 0)` 与 `copied == 0` 均原样保留，结构 PASS 不会设置语义正确或安全裁决。E01 与安全 v1 未改，也未被本次检查自动代替。见 [A01_replay_report.md](A01_replay_report.md)。

## 4. 八项问题的直接回答

1. **是否确定性合并？** 是。代码实施 `B_code + 来源注释 + Δ_code`，原始响应与精确区间可追溯。
2. **U10 是否真正收到完整约束？** 已验证代码接线和离线参数载荷是完整 B+Δ；本轮禁止真实模型调用，故不能声称线上 U10 已收到或成功生成新输出。
3. **A04 原始传递问题是否修复？** 在补全版正常路径的输入层已修复，并由缓存输入替换验证；尚无新模型输出或端到端求解结果。
4. **U10 输出能否通过？** 取决于输出。A04 旧输出 UNKNOWN 被拒绝；A01 旧输出结构 PASS 可进入后续阶段，但本轮没有实际求解，也不表示语义正确。
5. **哪些 UNKNOWN 被拒绝？** 复杂控制流/List 等不支持表达式、未绑定符号、代码围栏外说明、多代码块、未知/冲突类型、无法解释的额外声明/断言或缺失原始证据等。重复声明即使 E02 结构 PASS 也被适配器拒绝；具体结果见逐项 JSON。
6. **A01 极性风险是否独立保留？** 是。两条相反条件不删不改，`semantic_correctness`、`polarity_correctness` 始终 `NOT_ASSESSED`，由独立 E01/语义证据处理。
7. **是否影响原 Prompt 和上游？** 没有。只改补全版 engine 并增加独立适配器、测试和 E03 材料；保护核验见 [preservation_check.json](preservation_check.json)。
8. **能否进入真实单样本验证？** 可准备下一轮独立授权的有限单样本实验，但不能保证现有受限解析器接受真实输出。必须同时检查 E01、源码证据与安全 v1，设置调用/费用上限，并保留结构拒绝。此次停止，不自行启动。

## 5. 限制和未完成事项

E02 检查的是受限 Python-Z3 构造的结构成员保留，不证明公式等价、C 语义、宏、别名、跨函数 P 或路径极性正确。重复断言在合并文本中全部保留并计数；复用检查器的成员契约不要求 U10 重复输出逻辑相同的每次断言。哈希与调用来源建立可追溯性，不是独立语义证明。

开发中发生的缺依赖及循环引用错误已修正并保留 [失败记录](development_failures.json) 和局部输出。首次缓存检查与增加显式验收断言后的指定二案例检查均留档，未覆盖历史结果。没有执行模型生成的 Python，也没有产生 FILTER/KEEP/UNKNOWN 安全裁决；本文的 UNKNOWN 仅是静态契约状态。

下一步最小方案是在新的实验目录对一条预先指定样本观察真实 U02/U06/U10 的输入输出和双门检查，先验证结构传递，不据此放宽过滤条件。不进入其他算法修复。
