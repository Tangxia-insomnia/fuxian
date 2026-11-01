# 原论文检索意图与现有 MCP 工具映射

本映射由本复现项目新增，不修改作者提示词或 MCP 工具/schema。不存在名为 `search_context` 的新增工具或自动别名。

| 需求 | 原材料 | 真正使用的 MCP 方法 | Harness 展示名 | 本工作流必填参数 |
|---|---|---|---|---|
| 取得一条告警及原函数链 | 原论文输入：目标变量、Source/Sink、函数调用链，pp4–5 §3 | get_alert_context | mcp__llm4pfa__get_alert_context | dataset_id、position |
| 按需获取相关函数体 | P02/U04 的 search_context 意图 | lookup_function_source | mcp__llm4pfa__lookup_function_source | dataset_id、position、name |

论文出处：[v1 pp4–6 §3、p11 C.1](https://arxiv.org/pdf/2506.10322v1#page=4)；代码出处：[冻结 U04:71–89](https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/4efb4b9bf7e845e180451b43ba29a25e3edaa0e3/llm4pfa/prompt_templates.py#L71)。冻结 helper 写的是 `search_function`（pipeline:71），主工具调用入口却被注释（201）；本次不更改这段历史代码，详见 [第二阶段调用审计](../prompt_audit/prompt_call_sequence.md)。

## 请求合同

以已知样本 `codeql_linux` 的 JSON 数组第 12 行为例，原始字段 `index` 不是 position：

```json
{"dataset_id":"codeql_linux","position":12}
```

若已知源码中的调用确实需要检索 `kfree`，lookup 参数为：

```json
{"dataset_id":"codeql_linux","position":12,"name":"kfree"}
```

以上是请求形状示例，不是本轮真实调用。该样本的既有响应实际上已经含有 kfree 函数体，所以本目录的重放测试选择复用，不会为示例再发一次 lookup。

虽然现有 lookup schema 允许不传 position，本阶段独立工作流一律从不可变 Task 注入 dataset_id/position。模型提议只提供函数名、已有调用方哈希/调用位置和分析需求，不能传新数据集、路径或自造 local_chain。[workflow.py:119–158](workflow.py#L119)、[既有 schema 与校验](../../harness_bridge/tools.py#L38)。

函数名限制为最多 128 个 ASCII C 标识符字符。允许的数据集沿用已有桥接工具的 8 项白名单；独立工作流的白名单通过静态 AST 与原工具常量比对测试，未 import 或修改原工具。[workflow.py:21–29](workflow.py#L21)、[test_workflow.py:309–325](test_workflow.py#L309)。

## 响应与失败处理

现有工具成功返回 `{"ok":true,"data":...,"bridge_version":"llm4pfa-mcp-bridge-v1"}`，错误返回 `ok=false` 及明确 error.code；MCP 又同时携带 structuredContent、JSON text content 和 isError。[server.py:36–40](../../harness_bridge/server.py#L36)。离线验证器检查这两种内容视图相同，错误标志一致，避免把相互矛盾的包装层当作成功。[workflow.py:50–62](workflow.py#L50)。

| 响应/问题 | 当前独立工作流的处理 |
|---|---|
| 正常 context | 验证完整 frames、函数链多视图、target/Sink/变量一致性、源码哈希与每帧来源；全部成功后再提交状态 |
| 正常 lookup | 名称必须等于请求；dataset/position、数据集哈希/历史 ref/历史 artifact/上下文模块身份保持一致；有完整源码位置 |
| FUNCTION_AMBIGUOUS | blocked；不选择候选、不改函数名或数据集重试 |
| FUNCTION_NOT_FOUND / CONTEXT_UNAVAILABLE / SAMPLE_NOT_FOUND | blocked，保留原始错误结构；不伪造定义 |
| RETRIEVAL_TIMEOUT / WORKER_FAILED 等 | blocked；不自动重试 |
| 源码哈希、来源 artifact、跨样本/跨版本不一致 | blocked，不把未验证结果加入可用节点 |
| 调用 ID 错误、乱序、尚有请求时继续发请求 | blocked；记录原始响应/错误及取消的 pending 请求 |

实现出处：[workflow.py:162–254](workflow.py#L162)。`blocked` 只是检索工作流状态，不能解释为告警的正负标签或 FILTER/KEEP 裁决。

原工具按当前样本链优先找定义，其次在固定数据集中找；同层出现多个不同源码哈希时明确失败。[tools.py:190–211](../../harness_bridge/tools.py#L190)。模型不得自行挑选。唯一的检索结果也不保证调用语义一定绑定到该定义，特别是宏、别名、函数指针和同名作用域；本阶段记录词法候选，不做独立 C 语义证明。

## 执行边界

`workflow.py` 中的 request 是带真实工具名称的离线计划对象，无 MCP client、网络传输、模型 SDK、shell 或线程执行。已完成验收证明了参数/响应合同和状态约束；没有证明这些约束在 Harness 运行时已经被强制执行。未来使用时仍由 Harness 原生工具调用设施执行，并保存真实工具轨迹，不能将本地 request 记录称为已执行工具调用。
