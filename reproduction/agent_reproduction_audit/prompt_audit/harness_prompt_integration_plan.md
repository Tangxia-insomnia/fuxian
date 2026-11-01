# DeepSeek Harness 提示词接入计划（仅设计）

本阶段不开发 Agent、不修改代码/配置、不启动 Harness、不调用模型。以下均为后续候选方案，不是已经实现或验收的能力。第一阶段两个检索工具已在 Harness 调用成功、Python 侧 18/18 通过，属于用户提供的阶段状态；本阶段没有重新验证。

设计继续采用**一个推理主体**，不同提示词是同一主体的不同分析步骤；不创建检索/推理/SMT 多 Agent 团队。论文 p5–6 §3.2.2/Figure 3 支持按需检索的上下文推理，但未公开多角色协作协议，不能据 agents 一词扩写多 Agent 架构。[论文 p6](https://arxiv.org/pdf/2506.10322v1#page=6)。

## 已有能力与待补能力

| 项目 | 已有证据 | 后续接入边界 |
|---|---|---|
| 告警与函数链 | get_alert_context 返回 frames、Sink、variable、body_sha256、来源 | 作为分析输入，不能把检索成功当作路径证明 |
| 函数体检索 | lookup_function_source 优先当前样本链；同层多定义报错 | 模型可提出进一步检索；不得猜选重名函数 |
| 原公开模板文本 | 10 个方法+规则串；论文 5 个块含占位 | 可固定版本/模板哈希；不能补齐缺失规则并标为作者原文 |
| 上下文工具规划 | 论文有描述；冻结 Python 主分支未接通 | 未来由 Harness 承担工具调用循环，必须独立验收 |
| Function Call Memory | 论文描述按 P 缓存返回值范围 | 未来显式保存状态绑定的返回值推理；现无已接通实现 |
| SMT/Z3 | Python 现有 solver 代码与日志；MCP 只有两个检索工具 | 当前 Harness 工具集不能完成 SMT 求解；不在本阶段新增工具 |
| 安全裁决 | real-bugs-first-v1 六条件，缺证据 UNKNOWN/KEEP | 后续仍置于模型控制之外；模型不能自行签署独立语义复核 |

依据：[tools.py:159–211](../../harness_bridge/tools.py#L159)、[server.py:27–40](../../harness_bridge/server.py#L27)、[engine.py:110–147](../../completion/engine.py#L110)、[safety/policy.py:13–17、228–242](../../safety/policy.py#L13)。论文公开缺口见 [论文清单](paper_prompt_inventory.md)。

## 模板保留策略

后续先确定实验模式，不把两者混写为精确复现：

| 模式 | 文本来源 | 可以声称什么 | 不能声称什么 |
|---|---|---|---|
| 论文公开材料参考模式 | Appendix C 的 P01–P05 原文，含省略/规则占位 | 保留并解释已公开材料 | 无法凭不完整模板宣称复现论文实际全部 Prompt |
| 冻结公开代码兼容模式 | 固定提交 Prompt 10 方法与 z3_prompt_extend | 与已公开代码文本可追溯对照 | 不保证等于缺失的内部 Prompt 类或完整论文流程 |
| 未来显式适配实验 | 原文副本+单独记录适配差异 | 清楚报告工具协议、类型/schema、消息状态的变更 | 不把新工具绑定/输出 schema 说成作者公开原文 |

建议优先准备“冻结公开代码兼容”的单主体候选，保留原样模板为独立文本资产；任何工具映射、输出结构化或极性策略应有新版本与 diff。此处不复制出新的可运行模板、不对 Appendix C 的 ... 或规则占位补写内容。

必要的未来记录字段可以包括：模板 ID/来源提交/SHA-256、原始英文、参数值及来源、messages 的角色与顺序、模型实际型号/参数、原始响应与解析结果、工具请求/返回及来源哈希。字段是追溯方案，不是新增作者模板。[Prompt:25–221](https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/4efb4b9bf7e845e180451b43ba29a25e3edaa0e3/llm4pfa/prompt_templates.py#L25)、[completion/model.py:75–103](../../completion/model.py#L75)。

## search_context 与 MCP 名称的兼容问题

原公开 U04 与论文 P02 均写 `search_context`；冻结 helper 的 tool 消息写 `search_function`，而当前已验证桥接工具名为：

- `mcp__llm4pfa__get_alert_context`
- `mcp__llm4pfa__lookup_function_source`

出处：[P02，论文 p11 C.1](https://arxiv.org/pdf/2506.10322v1#page=11)、[Prompt:80](https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/4efb4b9bf7e845e180451b43ba29a25e3edaa0e3/llm4pfa/prompt_templates.py#L71)、[pipeline:71](https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/4efb4b9bf7e845e180451b43ba29a25e3edaa0e3/llm4pfa/feasibility_analysis_pipeline.py#L67)、[bridge/README:70](../../harness_bridge/README.md#L70)。最新 PATHAGENT 的 schema 也命名 search_function，不能自动解决此差异。[最新 tool_schema:11](https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/9c767f92e5e398a6128d07becb1d98eadbaea3e7/path_agent/tool_schema.py#L11)。

后续需要选定并单独验收一种显式兼容层：保留模板英文，在调用层把原有检索意图映射到现有 MCP 工具；若实际 Harness 不支持别名/意图适配，则应记录一份修改工具引用的候选模板，与原模板分开保存。**当前没有证明该 Harness 提供别名能力，不增加猜测配置字段，也不修改原模板。**

映射时还必须补充 dataset_id 和 position；原提示只有函数名，MCP 必须绑定到具体数据集/样本。不得用不受限文件路径替代数据集参数。[tools.py:169–211](../../harness_bridge/tools.py#L169)。这些参数由已核验任务状态提供，不由模型猜测。

## 单主体的未来调度关系

1. 固定告警任务及证据版本，调用 get_alert_context；保留完整 frames 和来源。若工具失败/多义，记录 UNKNOWN 候选原因，不虚构源码。
2. 从证据明确构造 P、目标条件、变量身份、类型与分支方向。输入资料不足时保留缺口，不把 U05 的 NULL 假设泛化到全部缺陷。
3. 由同一主体按 P01/U05 完成变量范围候选；含相关函数时按 P02/U04 发起检索请求，检索更深相关函数并记录调用次序。论文上下文上限为 5，需区分“推理迭代次数”与底层网络重试/工具调用次数，不任意扩大。
4. 独立记录每条范围/约束到源码位置、变量身份和条件极性的映射，再按已选版本的 SMT 生成/合并模板得到候选脚本。先评审 U06/U10 的基础断言保留风险；不删除矛盾断言来追求 SAT。
5. 未来经单独批准的受控求解接口执行 SMT；求解错误按 P05/U01 反馈，最多 3 次修复。当前 MCP 未暴露该工具，本阶段不补。
6. 将推理与 solver 记录提交给独立的现有安全裁决；只有完整证据和所需复核满足原六条件才有 FILTER，局部极性通过或 UNSAT 不单独放行。

这是后续流程建议；不把尚不存在的 P 构造器、条件提取工具、solver MCP 或人工复核写成现成功能。方法依据为 [论文 pp5–6 §3.2.2/3.3](https://arxiv.org/pdf/2506.10322v1#page=5)，当前差距见 [调用顺序](prompt_call_sequence.md)。

## Function Call Memory 与消息隔离

未来 Memory 必须存“函数在给定状态下的返回值范围及其证据”，而不是只存函数体。建议绑定函数定义身份/源码哈希、P、参数映射、调用方状态、变量类型/别名假设、模板/模型版本及分析完整性；这些 key 字段是本审计的工程建议，论文只公开“不同 P”的语义要求。缺失或冲突时不复用。[PDF p6 §3.2.2](https://arxiv.org/pdf/2506.10322v1#page=6)。

单主体不要求所有阶段共享一条无限增长 messages。原代码 U04 独立会话，U05/U06 累积，U10/U09 重置；要复刻或改变这些边界都须记录。不要把原代码分离的 U04 回答自动传播到其他会话而不标注行为变化。[pipeline:197–238、335–337](https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/4efb4b9bf7e845e180451b43ba29a25e3edaa0e3/llm4pfa/feasibility_analysis_pipeline.py#L197)。

禁止把 CompletedEngine.run/ completed_source 整体暴露给 Harness：前者再次调用 Python 模型循环，后者写 patches。也不安装 offline_guard 到 Harness 宿主、不编辑模型提示词、不在此阶段更改 MCP 工具集。[engine:26–69、132–157](../../completion/engine.py#L26)。

## 接入前最小验收建议

这些是下一阶段可讨论的测试，不在本阶段运行：

| 验收项 | 通过证据 | 当前状态 |
|---|---|---|
| 模板来源/文本保持 | 固定 ID/hash、逐字 diff、明确缺失占位 | 本审计已给清单；未实现运行时加载器 |
| 工具命名/参数绑定 | 原检索意图映射到真实 MCP；数据集/样本身份一致 | 第一阶段 MCP 可用由用户报告；Prompt 兼容层未实现 |
| 单主体规划/终止 | 深层检索只涉及 P 相关调用，有迭代上限和明确失败原因 | 未实现、未验证 |
| 约束完整性 | 合并前后断言清单/变量身份核对，原脚本不丢约束 | 发现静态风险，未修复 |
| Memory 复用边界 | 同名异定义、不同 P 不误命中 | 尚无运行实现 |
| 安全与统计 | FILTER/KEEP/UNKNOWN 严格区分，UNKNOWN 不算过滤成功 | 保留现有 safety v1，未改变 |
| 成本与复现 | 先离线、后经授权小样本；独立日志/预算 | 本轮模型调用 0、费用 0；没有重跑 E01/全量 |

当前最先应决定的是“以哪个公开版本及何种兼容模式作为下一阶段基线”，再设计工具命名与消息状态适配。不要从本阶段直接开始开发、并行角色拆分或付费实验。
