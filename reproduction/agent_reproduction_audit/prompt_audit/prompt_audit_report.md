# LLM4PFA 原论文 Prompt Templates 专项审计报告

日期：2026-11-01。结论：**公开材料足以还原提示词职责和主要调用图，但不足以证明原论文完整 Prompt、工具规划与返回值 Memory 已在当前补全版实现。** 本阶段仅新增 7 份审计文档，没有修复算法、修改模板或执行模型实验。

## 主要发现

| 优先级 | 发现 | 证据 | 对下一阶段的含义 |
|---|---|---|---|
| 高 | 论文公开 5 个方法模板块，另有 3 个基线块；规则、示例、部分上下文指导仍有省略 | PDF pp10–11 Appendix B/C；[论文原文清单](paper_prompt_inventory.md) | 保留全部原文和占位；不能补造作者未公开模板 |
| 高 | 冻结上游导入的是未公开内部 Prompt，补全版改为显式加载公开文件 | [pipeline:13–14](https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/4efb4b9bf7e845e180451b43ba29a25e3edaa0e3/llm4pfa/feasibility_analysis_pipeline.py#L13)、[engine:76](../../completion/engine.py#L76) | 公开文本可追溯，不等于能证实与论文内部实验字节相同 |
| 高 | 上下文提示写 search_context，但主流程实际上无工具调用；返回 Not satisfied 可在 SMT 前直接 False | [Prompt:71–89](https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/4efb4b9bf7e845e180451b43ba29a25e3edaa0e3/llm4pfa/prompt_templates.py#L71)、[pipeline:197–219](https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/4efb4b9bf7e845e180451b43ba29a25e3edaa0e3/llm4pfa/feasibility_analysis_pipeline.py#L197) | Harness 已接 MCP 不代表原模型自主检索已经接通；不得直接将原 False 当作 FILTER |
| 高 | 按 P 的返回值 Memory 未接通；函数体缓存不能替代它 | PDF p6 §3.2.2/Figure 3；[pipeline:23–28、378](https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/4efb4b9bf7e845e180451b43ba29a25e3edaa0e3/llm4pfa/feasibility_analysis_pipeline.py#L23) | 下一阶段如做 Memory，须明确函数定义、初始状态和推理证据绑定 |
| 高 | 模板存在极性矛盾和合并完整性风险 | [Prompt:6、15、148](https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/4efb4b9bf7e845e180451b43ba29a25e3edaa0e3/llm4pfa/prompt_templates.py#L136)、[Prompt:117–132](https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/4efb4b9bf7e845e180451b43ba29a25e3edaa0e3/llm4pfa/prompt_templates.py#L117)、[pipeline:231–240](https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/4efb4b9bf7e845e180451b43ba29a25e3edaa0e3/llm4pfa/feasibility_analysis_pipeline.py#L231) | 这些是静态证据，未测定各自错误率；不在本轮更改 E01、模板或删约束 |
| 中 | 补全版保留公开模板文本，但改变基础查询、修复次数、输入恢复、解析与执行环境 | [engine:26–69、99–169](../../completion/engine.py#L26)、[差异清单](completion_prompt_diff.md) | 文本相同不代表完整调用语义相同 |
| 中 | 在线 main 今天已重组为 PATHAGENT；本地 origin/main 落后 | 最新提交 [9c767f9](https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/commit/9c767f92e5e398a6128d07becb1d98eadbaea3e7)、[版本核查](upstream_prompt_inventory.md) | 冻结历史版本继续作为主审计对象；不升级、不把新配套代码倒记为原论文公开内容 |

上游共享规则的字面要求是 `!ptr → ptr==0`，U07 却写 `!ptr → ptr!=0`。U06 要保留旧约束但只返回新增行，U10 接收时不单独携带基础脚本。两点都可能破坏源码与 SMT 对应；本审计只定位，不重新解释条件来消除矛盾。

## 固定材料与版本

| 材料 | 本次采用版本/状态 |
|---|---|
| 原论文 | arXiv:2506.10322v1；2025-06-12；11 页；[PDF](https://arxiv.org/pdf/2506.10322v1) |
| 方法代码基线 | upstream HEAD = 4efb4b9bf7e845e180451b43ba29a25e3edaa0e3；起始 git status 为空 |
| 本地缓存 origin/main | 37a1fdc99d59a8af176ae8c93fa4bf0adbeed997（2026-10-16） |
| 只读查询的在线 main | 9c767f92e5e398a6128d07becb1d98eadbaea3e7；2026-11-01 06:13:57 UTC |
| 补全实现 | 当前 completion/engine.py、completion/model.py 及已有 patches；不重新生成 |
| 发布仓库审计前状态 | Tangxia-insomnia/fuxian，main，96f7aaf1c9a6fd422210855963a3816bf5c89b3e；起始工作区干净 |
| 现有架构材料 | 实际找到 reproduction/LLM4PFA_architecture_analysis.md（460 行）；未找到名为 agent_architecture_analysis.md 的文件，未重命名或重建 |
| 第一阶段状态 | Harness 两个检索调用与 18/18 测试成功由用户本轮说明；本次不重测 |

当前本地 `agent_reproduction_audit/mcp_integration_report.md` 只有 1 字节，本次不以它作为阶段验收证据，也不覆盖/恢复它。桥接能力判断依据实际 server/tools 源码及用户所述阶段状态。[server:27–40](../../harness_bridge/server.py#L27)、[tools:169–211](../../harness_bridge/tools.py#L169)。

在线最新 README 标题已改为 PATHAGENT；latest prompts.py 与冻结 prompt_templates.py 经换行归一化后逐字相同，但最新 pipeline 已有本地导入/schema 和方法名拼写修复。旧内部包缺失的结论只针对冻结版本，不泛指最新仓库。最新工具入口第 201 行仍为注释，方法调用和语义 Memory 问题没有因为重组而自动消失。[最新 pipeline:13、73、197–219、378](https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/9c767f92e5e398a6128d07becb1d98eadbaea3e7/path_agent/pipeline.py#L197)。

## 实际执行的审计工作

1. 记录上游/发布 checkout 的提交与状态；对现有复现文件计算完整性摘要，排除 .git、.venv、__pycache__、node_modules 以及文件名以 .env 开头的凭据文件。
2. 只读核查论文版本记录，在内存中获取 v1 PDF 与 TeX 源归档；检查 27 个 TeX 文件，对照 PDF 的真实页码及图表，逐块提取 Appendix B/C。现有附录源码缓存与新读取文本一致；没有保存新 PDF/源码文件。
3. 用文本检索与 AST 阅读公开模板、pipeline、模型包装、补全引擎、已有持久化补丁、诊断脚本和 MCP 元数据。没有执行被审计项目模块，没有运行 test_models/probe/CompletedEngine，也没有重生成 patches。
4. 只读查询在线官方提交及相关新文件，将最新 PATHAGENT 和冻结 LLM4PFA 分开记录。
5. 新增本目录 7 个 Markdown，检查原文完整、路径/行号和文件存在性；只将这 7 个文件同步至已有发布仓库。

本阶段没有运行单元测试、离线回归、SMT 求解或完整实验。“校验通过”仅指文档完整性与源文件保持检查，不冒充算法测试。

## 模板与调用审计结果

| 项目 | 结果/口径 |
|---|---|
| 论文公开可见块 | 8 = 方法 5 + 基线 3；完整转录原始 TeX 中英文、占位与排版（转录仅去除行末空白） |
| 公开 Prompt 方法 | 10；全部保留原始方法源码及参数、调用位置、输出处理 |
| 活动主流程引用 | 9 个已定义方法；U03 无调用；未定义 _multi_ helper 名称另列 |
| 包装层文字 | W01 工具前缀、W02 默认 system、D01/D02 诊断输入另列 |
| 模型原生自主工具调用 | 冻结主分支未启用；普通多轮调用不当作自主 Agent |
| Function Call Memory | 未见活动的按 P 返回值缓存读写；源码缓存单独列出 |
| 补全版新增任务模板 | 未发现；存在新增调用与协议/输入变化 |
| 本阶段模型调用/费用 | 0 次 / 0 元 |
| 本阶段求解/实验 | 0 次；不更新任何过滤率或保留率 |
| 安全策略 | real-bugs-first-v1 与 E01 保持原状，未放宽 FILTER 条件 |

论文正文逐项范围→立即 SMT 求解的描述与当前先累计多条变量分析、再转 SMT 的活动代码也存在差别。函数上下文回复没有始终进入可追溯范围结构，而可直接以子串短路。这些限制使“提示词原文保留”不足以保证“论文完整流程复现”。[论文 p6 §3.3](https://arxiv.org/pdf/2506.10322v1#page=6)、[pipeline:208–249](https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/4efb4b9bf7e845e180451b43ba29a25e3edaa0e3/llm4pfa/feasibility_analysis_pipeline.py#L208)。

## 哈希与保护范围

| 证据 | SHA-256 |
|---|---|
| v1 PDF | 03eba4d55590bd67228b37e10eda3662d604e708f112f5d9d973efbcc02feacd |
| v1 TeX 源归档 | c02abf4e361ac111cae8f003ea353e2ca1427a75b80720ecdea7bf45f3151457 |
| upstream/llm4pfa/prompt_templates.py | 43fa105beb98fd40e7214dd321521ec1085ef8c9c557fa4863eaa9b502417a4c |
| upstream/llm4pfa/feasibility_analysis_pipeline.py | c903f6de291ad4dc0e29ffbfefa7c287d4b92c50d1a7b3febf2661e1a51fb8e3 |
| upstream/llm4pfa/model.py | 84a5c24721a7013b8a1ac489105a7d925306dda627a11b7926503c63b3ff6f33 |
| completion/engine.py | c2b33783874a778717819a96943f4b646f4c09af7a1d032acc82106381005194 |
| completion/model.py | ae96626f29e53c092478c4a529d4c09771029bccf26fd0781e92d25ff79386f4 |
| patches/completed_function_bodies.py | 081b63a4caba0236734263119041a61bbcd0c3b37c1f048f9d79c47b3c977b3f |
| results/raw/completed/budget_ledger.json | a0b6957098e905700133acbcbae5c77a529b07e4b04c9743cd164fea80f0201b |

原有 **3,463 个文件**（上述排除规则，不含本次 prompt_audit 新目录）的 `相对路径→文件SHA-256` 映射，按键排序，以 UTF-8 JSON（ensure_ascii=False，分隔符为逗号/冒号、无额外空白）序列化后计算 SHA-256：

`1722dfb87ae9f612c87b25b1a6b902ed7d3c44eebc6cd79b52b64d5188b34239`

文档校验确认 8 个论文框、10 个代码方法和共享规则均完整保留（仅去除转录行末空白），所有本地链接存在且行号有效；上游引用使用固定提交的 GitHub 链接，适配发布仓库的 submodule 结构。

新增文档后的复查得到相同数量和摘要，表明受检原文件内容未变；原有安全/E01/结果与预算账本在范围内。排除缓存/环境/凭据不代表证明这些排除项内容的完整性；本阶段没有向它们写入。发布 checkout 只接收本次 7 个文档。

## 七份交付物

| 文档 | 内容 |
|---|---|
| [paper_prompt_inventory.md](paper_prompt_inventory.md) | 论文全部公开块英文原文、页码、输入/输出、缺失占位 |
| [upstream_prompt_inventory.md](upstream_prompt_inventory.md) | 10 方法原文、共享规则、包装层文本、参数/调用/解析、最新版本差异 |
| [prompt_mapping.md](prompt_mapping.md) | 论文/代码/补全版逐项映射、六项功能关系 |
| [prompt_call_sequence.md](prompt_call_sequence.md) | 论文逻辑、活动分支、注释工具循环、消息边界、补全版新增调用 |
| [completion_prompt_diff.md](completion_prompt_diff.md) | 模板来源、英文复用与调用/输入/模型/执行差异 |
| [harness_prompt_integration_plan.md](harness_prompt_integration_plan.md) | 单推理主体接入方案、命名兼容、Memory/solver 边界、后续验收建议 |
| [prompt_audit_report.md](prompt_audit_report.md) | 本总报告、固定材料、主要问题、执行与完整性记录 |

## 下一阶段建议及停止状态

先确定原文参考模式和公开代码兼容模式的边界，再处理 `search_context → 真实 MCP 工具` 的显式映射与消息状态；保持一个推理主体、Python 检索层无模型调用。对没有公开的规则/示例保持缺失标记，对类型/初始状态/分支不确定性保持 UNKNOWN。

在引入 Agent 调度前，应明确 U06/U10 合并如何保留每条断言，以及函数返回值推理如何绑定到源码/状态；不能靠同一个模型自我声明来满足安全 v1 的独立复核要求。[调用链与风险](prompt_call_sequence.md)、[接入计划](harness_prompt_integration_plan.md)、[safety/policy.py:1–5、13–17](../../safety/policy.py#L1)。

本阶段完成文档审计后停止。没有提前开发 Agent/多 Agent，没有改动 MCP、Python、原模板、E01、安全 v1 或历史结果，没有调用模型 API，也没有启动或重启 Harness。后续开发/修复需用户下一阶段指令。
