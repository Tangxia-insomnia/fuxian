# 消息状态与上下文管理

本文件区分未来单 Harness 会话设计和当前可执行的离线参考。没有修改 Harness 配置、原模型消息、提示词或 MCP Server。

## 单会话消息关系（未来使用）

| 顺序 | 内容/来源 | 管理规则 |
|---|---|---|
| 1 | 本项目 Harness 适配指令 | 作为新增指令资产单独加载；不伪称作者原文，不猜测 Harness 配置字段 |
| 2 | 不可变任务身份、analysis_question、P/未知状态、迭代上限 | dataset_id/position 每次工具请求固定；不输入数据集标签以指导检索结论 |
| 3 | P02/U04 原文参考 | 保持独立原文/hash；U04 的 NULL 假设不自动变成任务事实 |
| 4 | Harness 原生 get_alert_context 请求与工具结果 | 原生请求 ID 由 Harness 管理，不手工伪造 assistant/tool 协议消息 |
| 5 | 同一 Agent 对现有证据的简短检索需求说明 | 给出已持有的 caller/hash、原调用行、callee、缺失事实，不编造函数体 |
| 6 | 若需要：原生 lookup 请求/结果；回到步骤 5 | 原始结果、来源和错误保留；没有定义或多义即终止 |
| 7 | 检索记录与未解决项 | 输出来源/调用关系/停止原因；不作路径或告警最终判断 |

这是显式适配的单主体流程。原官方 U04 使用独立无工具 message_context，深层工具入口被注释；现在的设计并不假装原代码已经具有上述流程。[第二阶段审计](../prompt_audit/prompt_call_sequence.md)、[冻结 pipeline:197–219](https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/4efb4b9bf7e845e180451b43ba29a25e3edaa0e3/llm4pfa/feasibility_analysis_pipeline.py#L197)。

## 当前离线状态机

| 状态 | 允许操作 | 后继/错误 |
|---|---|---|
| new | begin | awaiting_context；第二次 begin 是错误 |
| awaiting_context | accept 对应响应 | 完整 context → ready；错误/缺证据 → blocked |
| ready | lookup 或 finish | 已有定义 → reuse 后 ready；新定义 → awaiting_lookup；主动停止 → stopped |
| awaiting_lookup | accept 对应响应 | 合格结果 → ready；错误/乱序/多义 → blocked |
| stopped / blocked | 导出记录 | 不再发请求；后续非法动作仍停止，不会重开任务 |

源码：[workflow.py:99–160、197–281](workflow.py#L99)。没有 background loop 或模型规划器；每个 lookup 的理由和函数选择都由离线测试输入。`Task` 为 frozen dataclass，导出值和请求为深拷贝；不同 session 不共享 registry。

## 保存的数据

| 区域 | 字段/语义 |
|---|---|
| task | dataset_id、position、analysis_question、initial_states、max_context_iterations |
| alert_context | 原始成功 get_alert_context 的全部 data，不截断 frames/function_call/function_chain |
| evidence_binding | dataset_path/hash、historical_path/ref/artifact hash、context_module_sha256；后续响应必须一致 |
| source_nodes | function、code、body_sha256、source_locations；以源码哈希区分定义，同名冲突停止 |
| call_edges | caller/callee 身份、调用方原行、检索需求、获取或复用方式、绑定证据级别 |
| events | 有序 event_id；request、原始 response 对象及规范 JSON 哈希、accepted、reuse、stop |
| terminal | state、stop_reason、unresolved、被取消的 pending 请求、迭代/lookup 计数 |
| execution facts | execution_mode=offline_replay_only；actual_tool_calls_this_run=0、模型调用/费用=0 |

`raw_sha256` 是对已解析 JSON 对象排序、紧凑序列化后的哈希，不是 MCP 线路字节流哈希。历史输入文件本身的字节 SHA-256 另列于 fixture 元数据；原对象中的 key/value 保留。[workflow.py:46–62、195–226](workflow.py#L46)。

## 证据保留与可信边界

- 初始函数链边标记为 `repository_recovered_not_independently_reproved`；新增检索边标记为 `lexical_candidate_not_semantic_proof`。不会把“唯一名字检索结果”升级成 C 语言绑定证明。
- 调用位置按函数体文本从 1 开始计行，和 benchmark 全文件行号不是同一概念。原工具位置保存在 source_locations 中，多为 JSON pointer；不得冒充原构建的文件/行证据。
- 对每帧检查 code/hash、source locator 与绑定 artifact 元数据；先完整验证再提交，以免部分失败留下“已成功上下文”。本地验证器没有重构完整 C 项目，也没有读取原构建数据库。
- 第一份有效 context 是本会话的证据锚点，后续只校验一致性。其元数据真实性依赖已有只读 MCP 工具和固定基线；哈希一致不是服务器真实性、历史构建一致性或程序语义证明。
- 当前 registry 只缓存本任务的源码与检索轨迹，不缓存 P 下的函数返回值范围，不能称为论文 Function Call Memory 已完成。不同 P 的语义缓存不在本阶段。

实现：[workflow.py:162–254](workflow.py#L162)。原桥接工具也明确源码位置是保存 JSON 的位置而非完整构建证据：[tools.py:159–167](../../harness_bridge/tools.py#L159)。

## 上下文不足、大小和运行时限制

没有静默截断源码、用摘要替换原始证据或从函数名猜测定义。未知 P、类型、宏展开和间接调用均保存为未解决项或停止原因。若未来模型上下文预算装不下完整证据，应明确停止或另行设计引用管理；**本阶段没有实现/验证 Harness 的 token 预算控制或宿主级强制状态门。**

测试中的网络/子进程拒绝钩子仅在独立测试进程中存在，不是 `offline_guard.install`，不影响 Harness、MCP 或原项目进程。[test_workflow.py 主入口](test_workflow.py#L360)。源码中的指令性注释仍作为数据，离线状态机不执行它；这不等于证明未来大模型能够抵抗全部提示注入。
