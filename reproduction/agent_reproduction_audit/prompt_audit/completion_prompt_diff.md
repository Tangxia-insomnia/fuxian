# 补全版与官方代码的 Prompt 差异

结论：**补全版没有另写这 10 个方法的英文模板，但更改了模板来源绑定、调用路径、输入、回复处理和模型环境。** 这些差异足以影响结果，不能声称与论文实验完全一致。

本次仅阅读/AST 解析文件，不导入 `completion.engine`、不构造 CompletedEngine、不调用 completed_source，避免它重写 patches。证据为冻结上游源码与本地现有文件，不是新端到端运行。[engine.py:26–69、76–77](../../completion/engine.py#L26)。

## 模板文本层面

| 项目 | 冻结上游 | 补全版 | 判定 |
|---|---|---|---|
| Prompt 的来源 | pipeline:13 导入 LLM4Detection.agent_simple.prompt_template | engine:76 用 runpy 加载 upstream/llm4pfa/prompt_templates.py | 明确的来源替换；缺失内部文件无法逐字比较 |
| 公开 Prompt 10 方法与共享规则 | prompt_templates.py:1–221 | 直接复用同一文件；engine 无替换这些返回模板的代码 | 对公开文件是文本复用；不等于能证明内部实验 Prompt 相同 |
| 新增手写任务模板 | 无另一套可见方法文件 | engine 无新增英文任务模板；solve_base 调用 U10/U01 | 新调用，非新模板 |
| 脚本补丁中的 Prompt 调用 | 9 个已定义方法用于主流程，helper 有未定义 _multi_ | 现有 completed_function_bodies.py 保持方法名与相对顺序 | 原 helper 的 _multi_ 拼写仍保留，但主流程工具入口仍注释 |
| 诊断 prompt | scripts/probe_samples.py:57 生成 U02 | 非 CompletedEngine 主执行路径 | 诊断不能充当完整实验 |

出处：[pipeline:13、176–369](https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/4efb4b9bf7e845e180451b43ba29a25e3edaa0e3/llm4pfa/feasibility_analysis_pipeline.py#L13)、[engine:76、132–147](../../completion/engine.py#L76)、[已保存补丁:140–333](../../patches/completed_function_bodies.py#L140)、[probe_samples:40–57](../../scripts/probe_samples.py#L40)。英文原文不再重复，见 [代码清单](upstream_prompt_inventory.md)。

补全版继承的模板问题包括：NULL 假设、按名字解释函数、未规范化变量身份/类型、U07 的 !ptr 极性示例、U06 only-new-lines 与基础约束保留的张力，以及 Not satisfied 的非结构化输出。它们不能被“回复是可执行 Python”自动消除。[Prompt:1–21、71–151](https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/4efb4b9bf7e845e180451b43ba29a25e3edaa0e3/llm4pfa/prompt_templates.py#L1)。

## 调用与输入层面

| 代码位置 | 相对冻结上游的修改 | 可能影响及边界 |
|---|---|---|
| engine:17–23 | 删除 extractor 的缺失内部导入后静态编译函数 | 能加载条件提取器，不代表提取语义被证明正确；未在本次调用 |
| engine:28 | 只载入上游 helper/main 的源码区间 | 原 imports、缓存配置、batch 入口均由适配器替代 |
| engine:29–40 | goto/return 遍历移除修复、while 检测改查条件文本 | 传给模板的条件集合可能与原代码不同；不是英文模板差异 |
| engine:41 | 替换 exec/check_constraints 为 solve_z3 | 生成函数的执行环境/超时/错误发生点不同 |
| engine:43–45 | 最后一次求解失败直接抛出耗尽错误 | 去掉原循环最后一次未验证修复请求 |
| engine:48–61 | 空条件路径调用 base solver；按恢复函数链判断结束 | 新增 U10/U01 调用；不再将缺失上下文异常默认为 True |
| engine:64–65 | 从 loc_text 提取实参、查询 condition 文本 | 跨帧约束输入可能变化；不能据此保证完整 P 已传播 |
| engine:99–108 | 用 regex 提取代码/JSON；验证 JSON 为字符串数组 | 比原 JSON 接口更严格，但 regex 首围栏仍有格式歧义；无 C 语义保证 |
| engine:132–147 | solve_base 路径用 U10(base_source)，最多三次 U01 修复 | 原 main 在没有目标/跳转时不会走两处 solver；这是实质调用差异 |
| engine:156–169 | 注入 model、per-sample cache、lookup、frame helpers | 提供可运行上下文，不启用模型自主工具检索或函数返回值 Memory |

出处：[engine.py:17–69](../../completion/engine.py#L17)、[99–169](../../completion/engine.py#L99)。本次不重新生成补丁、不对这些修改的实验效果作新断言。

## 消息协议及模型替换

- 原公开 U04 活动分支调用 without_tool；补全版复用此分支，客户端也仅有普通 messages 调用。不存在“已经把 search_context 接到 MCP”的隐含变更。[pipeline:197–206](https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/4efb4b9bf7e845e180451b43ba29a25e3edaa0e3/llm4pfa/feasibility_analysis_pipeline.py#L197)、[completion/model.py:59–91](../../completion/model.py#L59)。
- 模型接口中的 model_name 字符串在注入 namespace 中改为 deepseek（engine:156），真正请求模型由 config['model'] 指定，不能仅凭 Python 变量断定返回服务的精确模型版本。已保存请求/返回模型名才是运行证据；本阶段不调用服务确认型号。[completion/model.py:75–82](../../completion/model.py#L75)。
- 论文主比较为 GPT-4o-mini、temperature=0（PDF p7 §4.2），还比较 Claude Sonnet 3.5、Qwen2.5-Coder-32B-Instruct、DeepSeek-V2-Instruct（p7 §4.3）。补全客户端 temperature=0.0000001、thinking disabled、max_tokens 限制并带预算控制；不能把用户使用的 DeepSeek 服务称为论文 DeepSeek-V2-Instruct。[PDF p7](https://arxiv.org/pdf/2506.10322v1#page=7)、[completion/model.py:60–77](../../completion/model.py#L60)。
- 未见补全客户端插入新的 system 任务提示词或 tools schema。用户消息仍包含原公开模板角色文字；这与论文框中的 System Role 不是同一层协议。[completion/model.py:75–77](../../completion/model.py#L75)、[pipeline:177、198](https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/4efb4b9bf7e845e180451b43ba29a25e3edaa0e3/llm4pfa/feasibility_analysis_pipeline.py#L177)。
- finish_reason 非 stop/空内容被拒绝（model:89–90），与原包装层返回字符串/对象的宽松路径不同；全部消息与回复会经脱敏记录（99–104）。本次没有生成或改动任何调用记录。[completion/model.py:89–104](../../completion/model.py#L89)。

## SMT 与最终判定不能混为 Prompt 复用

补全版 worker 运行生成函数，保存 solver event，并施加 15 秒超时；这是执行控制，不能证明 LLM 的断言忠实表达代码。[engine.py:110–130](../../completion/engine.py#L110)。

U04 的 Not satisfied 短路仍可形成原始 False 候选，且未必包含 SMT 证据。[pipeline:208–219](https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/4efb4b9bf7e845e180451b43ba29a25e3edaa0e3/llm4pfa/feasibility_analysis_pipeline.py#L208)。必须与冻结安全 v1 的三态裁决分开：六条件证据不完整不得 FILTER；UNKNOWN 的操作是 KEEP。复用模板、SMT 可执行或 UNSAT 都不单独授权过滤。[safety/policy.py:13–17、228–242](../../safety/policy.py#L13)。

E01 和安全 v1 是现有独立候选核查/裁决层，本次不接线、不修改，也不将其约束检查描述成作者原提示词。

## 静态比对记录

通过 AST 读取（不执行）确认冻结上游与现有持久化补丁的 Prompt 引用对应：

| 方法 | 上游行号 | 已保存补丁行号 |
|---|---|---|
| analysis_constraints_prompt_context_multi_（未定义 helper 引用） | 73 | 36 |
| get_z3_by_target_conditions | 176 | 140 |
| analysis_constraints_prompt_context_multi | 197 | 161 |
| bug_line_constraints_prompt_step1 | 224 | 188 |
| bug_line_constraints_prompt_step2 | 231 | 195 |
| get_z3_extract | 236 | 200 |
| re_generate_prompt | 269、369 | 234、333 |
| get_filter_goto | 279 | 244 |
| get_z3_by_goto | 328 | 293 |
| get_z3_merged3 | 335 | 300 |

另有 engine:133、147 的 base-only U10/U01 调用。表中 helper 方法虽能被 AST 找到，主入口仍注释，不能计作真实工具运行。

起始 SHA-256：

| 文件 | SHA-256 |
|---|---|
| upstream/llm4pfa/prompt_templates.py | 43fa105beb98fd40e7214dd321521ec1085ef8c9c557fa4863eaa9b502417a4c |
| completion/engine.py | c2b33783874a778717819a96943f4b646f4c09af7a1d032acc82106381005194 |
| completion/model.py | ae96626f29e53c092478c4a529d4c09771029bccf26fd0781e92d25ff79386f4 |
| patches/completed_function_bodies.py | 081b63a4caba0236734263119041a61bbcd0c3b37c1f048f9d79c47b3c977b3f |

这些哈希用于约束审计范围，不是对模型效果的测试。结束时完整性核对见 [总报告](prompt_audit_report.md)。
