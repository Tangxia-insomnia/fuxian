# 第三阶段实验与验收报告

日期：2026-11-01。结果：**独立工作流设计和离线参考候选通过最终 25/25 项验收；Harness 单 Agent 自主多轮检索尚未运行、尚未验收。** 本阶段没有模型调用、实际 MCP 工具调用或费用，没有接入 SMT/Z3 或告警裁决。

## 基线与交付范围

- 论文固定 arXiv:2506.10322v1，p6 §3.2.2/Figure 3 的按需上下文检索、p11 C.1 的 P02。官方固定 `4efb4b9bf7e845e180451b43ba29a25e3edaa0e3`，未升级 PATHAGENT。
- 发布起点为 `68eaa6f6396aa66a6ffaf4c3e7a4af0e4f79ab54`。既有 Harness 两个工具成功、18/18 测试通过属于用户所述第一阶段状态，本次不重跑。
- 仅在本目录新增：工作流/映射/消息/终止文档、独立 Harness 适配指令、P02/U04 原文副本与出处、标准库离线状态机及测试、固定缓存 fixture、任务示例、阶段基线/校验和测试结果。
- 没有修改原 Prompt、pipeline、completion、MCP、E01、安全 v1、历史实验或任何 Harness 配置。没有开发多 Agent。
- 参考 [第二阶段对应表](../prompt_audit/prompt_mapping.md) 的差异：不能把单纯多轮消息或本阶段脚本重放称为自主 Agent。

## 实际做了什么

`workflow.py` 是可执行的离线合同验证器：固定 dataset_id/position，先校验完整 context，再接受来自外部的“为何需要哪个函数”提议，返回已验证工具名称的请求记录；检查同一样本、来源/hash、响应 ID 与内容一致性；重复源码复用、同名多义/缺失拒绝，最后导出完整轨迹。[workflow.py](workflow.py#L99)。

它**不执行返回的 request，不产生检索决策，不调用工具或模型**。原生 Harness 工具调用仍需要未来由实际单会话执行并另行留痕。当前适配提示词只是独立文本，没有安装到 Harness，更未把 Python 状态机接成宿主级强制门槛。

初始 frames 全部保留。每次扩展提议引用已有调用方源码 hash、体内行号/原文、函数名和分析需求；只核对可见的词法直接调用候选，并标记为未证明 C 语义。源码中的注释/字符串不当作指令或新的调用证据。进一步类型、宏展开、别名和参数传播不在本阶段恢复。

迭代规则是本项目的显式适配：初始 context 请求以外最多 5 次扩展决策，包含源码复用。实际 lookup 请求记录次数单列，不得借缓存循环无限追加。论文的上限为 5，但没有以此声称两者计数细节精确等价。

## 输入证据和回放性质

| 输入 | 实际来源与作用 |
|---|---|
| [recorded_responses.json](fixtures/recorded_responses.json) | 摘取既有 Python MCP stdio 验收的第 3、4 号记录（从 0 计），保留 request/output；不是本轮 Harness 响应 |
| 原文件 | `harness_bridge/results/stdio_isolation_validation/tool_calls.json`，SHA-256 `38217880f1b92a782ce19476e6090c515393eb32ef6942bf82200f1b663562dd` |
| 已保存真实告警上下文 | `codeql_linux`，position=12；函数链 tcp_set_allowed_congestion_control → kfree |
| 已保存 lookup | 同一任务的 kfree，源码/hash 与已在 frames 中的定义相同；当前工作流记录复用，0 次新增 lookup 计划 |
| 多轮、异常、注入等场景 | 测试代码明确构造的 synthetic 函数/错误响应；不是官方新增样本、真实模型分析或 Harness 多轮实验 |
| 原始 P02/U04 | [prompts/provenance.json](prompts/provenance.json) 记录原文件/片段 SHA-256 与行号；英文/省略/行尾保持原样，未填补规则 |
| 新适配内容 | [harness_adapter_prompt.md](harness_adapter_prompt.md) 独立标记为本复现编写；映射 search_context 意图到真实 MCP 名，不建立伪别名 |

原 P02 来源为 `appendix/prompt.tex:36–54`（PDF p11）；U04 来源为冻结 `prompt_templates.py:71–89`。P02 原文仍含 ...，U04 的 NULL 假设不被本阶段推成任务真值。原文副本仅作文本，不执行 U04 源码。

## 已运行的离线验收

环境：Windows，已有 Anaconda Python 3.11.5，标准库；没有安装依赖。测试进程局部拒绝 socket 连接与 subprocess.Popen，没有安装 offline_guard。

| 轮次 | 测试数 | 失败/错误 | 耗时（秒） | 变化说明 |
|---|---:|---:|---:|---|
| [offline_acceptance_01](results/offline_acceptance_01/test_results.json) | 23 | 0/0 | 0.074790 | 初始离线候选；23 项通过，后续人工检查仍发现边界需补强 |
| [offline_acceptance_02](results/offline_acceptance_02/test_results.json) | 25 | 0/0 | 0.030221 | 加入缓存循环上限与空白/换行成员调用检查，改明确上下文计数 |
| [offline_acceptance_03](results/offline_acceptance_04/test_results.json) | 25 | 0/0 | 0.033911 | 保留错调用 ID 的原始响应，并自动保存测试源码快照 |
| [offline_acceptance_04](results/offline_acceptance_04/test_results.json) | 25 | 0/0 | 0.031334 | 补齐被拒绝检索提议的输入轨迹；最终冻结候选 |

没有发生失败的测试用例；多义、缺失、越限等场景中的 blocked 是预期行为，不能算作“模型错误”或“告警被过滤”。开发中发现的边界问题通过新增检查/测试补强，并保留前轮结果与源码快照；不是根据真实留出样本优化。

最终运行命令（从 reproduction 目录；已有目录不可重跑覆盖）：

```powershell
& C:\Users\22803\anaconda3\python.exe -B agent_reproduction_audit/single_agent_retrieval/test_workflow.py --output-dir agent_reproduction_audit/single_agent_retrieval/results/offline_acceptance_04
```

最终输出：[test_results.json](results/offline_acceptance_04/test_results.json)、[test_output.txt](results/offline_acceptance_04/test_output.txt)、[retrieval_traces.json](results/offline_acceptance_04/retrieval_traces.json)。轨迹含所有提议、请求记录、完整响应对象/规范 JSON hash、证据节点/候选调用边、复用和停止原因；这是 JSON 对象回放，不是新的线路抓包。

### 最终逐项结果

| 测试 | 验收范围 | 结果 |
|---|---|---|
| [test_bad_task_parameters](test_workflow.py#L169) | 数据集路径、位置类型/范围、迭代上限、缺失任务说明 | passed |
| [test_cache_only_cycle_is_also_bounded](test_workflow.py#L210) | 反复命中本地源码也不能绕过迭代上限 | passed |
| [test_comments_literals_and_indirect_calls_are_not_lookup_evidence](test_workflow.py#L186) | 注释、字面量、间接成员/指针、同一行多处候选 | passed |
| [test_cross_sample_response_is_rejected](test_workflow.py#L229) | 错误数据集、位置、bool 位置被拒绝 | passed |
| [test_cycle_reuses_known_source](test_workflow.py#L197) | 递归回已有定义时复用，不重复查询 | passed |
| [test_dataset_and_history_evidence_changes_are_rejected](test_workflow.py#L238) | 数据集/历史/context 模块身份变化被拒绝 | passed |
| [test_five_lookup_attempts_then_sixth_is_blocked](test_workflow.py#L140) | 5 次请求后拒绝第 6 次，保留被拒提议 | passed |
| [test_initial_alert_error_is_not_partial_context_success](test_workflow.py#L164) | 初始样本错误不产生部分成功 | passed |
| [test_invalid_frame_does_not_commit_partial_context](test_workflow.py#L255) | 后续帧失败，初始上下文不部分提交 | passed |
| [test_invalid_or_guessed_callsite_is_not_dispatched](test_workflow.py#L176) | 未知名字、伪造行/行号、非法函数名不发请求 | passed |
| [test_mcp_structured_text_or_error_flag_disagreement](test_workflow.py#L265) | 结构化/文字 JSON 或错误标志不一致 | passed |
| [test_member_calls_with_whitespace_or_newline_are_rejected](test_workflow.py#L220) | 带空白/换行的成员调用拒绝为直接调用 | passed |
| [test_missing_provenance_and_tampered_source_are_rejected](test_workflow.py#L246) | 缺源码来源、哈希错误、返回函数名不符 | passed |
| [test_no_classification_in_export_and_no_cross_session_mutation](test_workflow.py#L301) | 导出无裁决字段，深拷贝与会话隔离 | passed |
| [test_no_extra_lookup_when_context_is_sufficient](test_workflow.py#L135) | 无需扩展时明确停止 | passed |
| [test_only_standard_library_workflow_imports](test_workflow.py#L334) | 状态机仅标准库，无模型/引擎/solver/guard 导入 | passed |
| [test_original_prompts_preserved_and_bridge_contract_unchanged](test_workflow.py#L309) | 原文副本/源哈希、工具名/白名单一致 | passed |
| [test_response_call_id_and_pending_order](test_workflow.py#L275) | 错调用 ID、pending 时终止；记录错位响应 | passed |
| [test_saved_context_replay_and_complete_evidence](test_workflow.py#L101) | 重放既有 context，完整保留两帧与来源 | passed |
| [test_saved_fixture_matches_original_artifact_and_records](test_workflow.py#L327) | 缓存输入文件与选中记录逐字节/对象核对 | passed |
| [test_saved_lookup_matches_context_and_reuses_without_dispatch](test_workflow.py#L112) | 既有 kfree 响应与已持有源码一致，复用而非再查询 | passed |
| [test_three_round_context_extension](test_workflow.py#L124) | 合成 root→step1→step2→step3，连续三轮请求/返回 | passed |
| [test_tool_errors_fail_explicitly_without_definition_selection](test_workflow.py#L153) | 缺失/多义/上下文缺失/超时/worker 错误，均停止 | passed |
| [test_unsupported_context_stops_with_unresolved_items](test_workflow.py#L284) | 不支持的上下文保持未解决项 | passed |
| [test_untrusted_source_never_becomes_tool_instructions](test_workflow.py#L290) | 源码中的指令性注释不触发任何执行 | passed |

### 可重复定位的轨迹

最终 `retrieval_traces.json` 的 `__main__.WorkflowTests.test_three_round_context_extension`：合成 root → step1 → step2 → step3；3 个模拟 lookup 请求，4 个源码节点、3 条词法候选边。所有输入和选择来自测试脚本。

`test_saved_lookup_matches_context_and_reuses_without_dispatch`：重放告警 context 后发现 kfree 已有，检查历史 lookup 结果相同并记录复用；不新增工具请求。这不是“模型自主发现无需检索”的实测。

`test_five_lookup_attempts_then_sixth_is_blocked`：模拟 5 次 lookup 成功，第 6 次提议明确停止且未产生第 6 次 lookup 请求；初始 context 的模拟请求另计一次。`test_cache_only_cycle_is_also_bounded` 验证只复用本地源码也会停止。

## 本阶段数量、成本与范围

| 指标 | 实际值/口径 |
|---|---|
| 最终验收 | 25/25，失败 0、错误 0、跳过 0；不是 25 条真实告警模型实验 |
| 新 Harness Agent 运行 | 0 |
| 新模型调用/API 费用 | 0 次 / 0 元 |
| 本轮实际 MCP 工具调用 | 0；只有缓存读取和合成 request/response |
| 最终测试禁止操作触发次数 | 0；测试进程的网络/子进程拒绝钩子没有被调用 |
| 新增依赖/模型/数据库 | 0 |
| SMT/Z3 求解、全量实验 | 0 |
| FILTER/KEEP/告警预测、过滤率 | 不提供、不计算；检索状态不等于告警类别 |
| 受保护旧文件 | 3,470 个，内容汇总哈希未变；包括第二阶段 7 文档、原安全/E01 和预算账本 |

## 冻结和完整性

最终代码 SHA-256：

- workflow.py：`cb9b1f42a45afb7ed5a542be13b0ac7c5851a5756f51a8b4b315e58342e454c1`
- test_workflow.py：`f0f269a1ba0f2ab0aa6f64d01884cd334af6baea38ab9f88dd113f2bc940b129`

起始快照：[baseline_snapshot.json](baseline_snapshot.json)。结束核对：[integrity_check.json](integrity_check.json)。

旧文件 `相对路径→SHA-256` 映射按键排序、UTF-8 紧凑 JSON、ensure_ascii=False 后的 SHA-256：

`e6bc33c2ebea691d46d56bc3377ee726627205e00eae979e6326b1aca10e6a01`

排除 .git/.venv/__pycache__/node_modules、文件名以 .env 开头的文件以及本阶段新目录；没有将凭据写入报告/结果。该摘要证明受检文件内容保持，不证明被排除项的内容完整性。最终交付哈希见 `hashes.json`；它不包含自己的哈希，避免自引用。

## 未解决的问题

1. **Harness 真实自主性未验收。** 还不知道模型能否按 P 和问题自行提出恰当检索、正确停止、遵守映射/上限；所有本轮选择均为脚本输入。
2. **状态门尚未宿主接线。** 独立 Python 验证器能拒绝离线越限/串样本响应，但当前 MCP 未改、Harness 配置未改；适配提示词本身不能保证强制执行。模型上下文预算、挂起请求的实际取消/整任务超时也未验证。
3. **源代码覆盖仍受既有数据边界限制。** 函数体只有固定 benchmark/历史缓存可检索，缺失/重名不补造；宏、间接调用、类型/别名/实参状态、原始构建证据未恢复。
4. **源码 registry 不是返回值 Memory。** 尚未实现按 P 绑定的函数返回值推理缓存，也没有 SMT/安全裁决；不宣称完整论文算法恢复。
5. **词法边与来源元数据不是独立语义证明。** 唯一检索结果可能仍需调用绑定核查；本阶段不据此讨论真实缺陷误删率或误报过滤率。对源码提示注入的离线测试不代表模型安全证明。

## 验收结论与下一步建议

本轮通过“独立单 Agent 检索工作流设计、原文/适配分离、离线轨迹与状态约束”验收；**不将其写成 Harness 实际 Agent 调用成功**。

下一阶段建议先讨论一种真实单样本 Harness 验证：固定任务、单会话、最多 5 次扩展，保存原生工具轨迹和模型实际输出，核对检索需要和停止原因；需要模型调用时须另行授权并明确预算。本阶段到此停止，不自动启动该实验，不修改原方法、安全门或已有工具。
