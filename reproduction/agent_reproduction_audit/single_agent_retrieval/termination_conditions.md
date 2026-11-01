# 多轮检索终止条件

论文 v1 p6 §3.2.2 规定深层上下文迭代最多 5 次，但公开材料没有完全明确其内部计数细节。本目录使用以下独立工程约定，不声称等价于作者实验时的实现。

## 明确的上限

- `max_context_iterations` 默认 5，必须为 1–5 的整数，不接受 bool、字符串或更大上限。
- 初次 get_alert_context 单独一次，不计入扩展迭代。
- 每次 ready 状态下的 `lookup()` 提议计一次上下文扩展决策，包含源码本地复用、失败/被拒绝提议。真正派发的 lookup 计划次数另记为 lookup_attempts_simulated。
- 第 6 次扩展提议在默认配置下直接 blocked，不生成新请求。重复/循环调用即使全部命中本地 registry，也不能绕过该上限。
- 一次只允许一个 pending 请求；不能批量并发、创建子 Agent 或重开会话规避限制。

实现：[Task:84–96](workflow.py#L84)、[lookup:133–160](workflow.py#L133)。测试 `[5 次查询后第 6 次停止]` 与 `[仅复用缓存也有上限]` 见 [test_workflow.py:140、208](test_workflow.py#L140)。所有查询次数在本阶段都是模拟计数，实际工具调用数为 0。

## 停止原因

| 情况 | 本地状态/原因 | 必须保留的信息 |
|---|---|---|
| 分析需要的源码已具备 | stopped / analysis_need_satisfied | 已有源码/来源、检索需求为何不再需要扩展；仅表示外部提供的停止决定 |
| 宏、函数指针、别名、未知 P 等使进一步检索无法可靠规划 | stopped / unsupported_context | unresolved 中逐项记录；不推测定义 |
| 用户停止该检索任务 | stopped / manual_stop | 当前完整轨迹和未解决项 |
| 扩展次数达到上限 | blocked / context_iteration_limit | 当前次数、尝试目标及已有完整证据；不发第 6 次请求 |
| 函数不存在/多个不同定义 | blocked / tool_error:FUNCTION_NOT_FOUND 或 FUNCTION_AMBIGUOUS | 原错误 envelope；不选候选、不换数据集重试 |
| 初始上下文/样本缺失、worker 失败/超时 | blocked / tool_error:<code> | 工具原始错误对象、请求身份 |
| 错样本、错调用 ID、哈希/来源不一致、帧不完整 | blocked / invalid_response:<reason> 等 | 原始响应、错误原因和取消的 pending request；不提交部分结果 |
| 只有文字名字，无法在已知源码中定位唯一直接调用候选 | blocked / invalid_lookup_proposal:<reason> | 调用方哈希、提议行/名字、原因；不生成查询 |
| pending 时又提议、无 ready context 就 finish | blocked / *_out_of_order 或 finish_without_ready_context | 乱序行为及取消的 pending 请求 |

实现：[workflow.py:113–117、133–160、197–264](workflow.py#L113)。`blocked/stopped` 都不是告警分类；没有从它们导出 FILTER、KEEP 或误报过滤成功。

## 超时与自动化边界

离线参考没有发起请求，因此没有实现真实 pending 工具超时计时器；测试中的 RETRIEVAL_TIMEOUT 是显式合成错误。已有 MCP worker 的 30 秒上限与客户端配置中的 60 秒 toolCallTimeoutMs 是历史基础设施，不在此处修改。[worker.py](../../harness_bridge/worker.py)、[config_example.json:20](../../harness_bridge/config_example.json#L20)。未来 Harness 应在收到明确超时后停止，不能自动多轮重试；宿主断线/卡住没有返回错误时，仍需实际运行验证和宿主终止机制。

本阶段执行时没有 Harness/model 轮次，所以不能根据 25 项测试成功宣称 Agent 一定会自动遵守限制。独立状态机能拒绝越限离线请求；运行时强制接线尚未实现，这是验收报告中的未解决事项。
