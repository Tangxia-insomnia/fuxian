# 第五阶段：SMT/Z3 恢复前置审计报告

日期：2026-11-01（Asia/Shanghai）。本阶段只增加本目录 8 份审计文档；读取论文、源码、数据 schema、历史模型响应、历史 SMT2/执行日志和 E01 保存结果。没有导入/执行项目模块，没有运行 Z3、模型、Harness、实验或新裁决。发布操作仅提交并推送这些文档。

## 1. 结论与研究边界

当前尚不具备直接把 Harness 检索结果接到 SMT 后宣称完整恢复 LLM4PFA 的依据。最主要的三个问题是：

1. **P 的语义有定义，完整构造方法未公开。**论文第 5 页 §3.2.2 定义 Source 后状态和参数相关约束传播；公开代码主要使用 `目标指针 == 0`，数据没有统一、完整、类型化的 P。不能补写作者未公开的算法后冒称原方法。
2. **条件极性缺少统一契约。**共享规则把 `!ptr` 转成 `ptr==0`，U07:148 却写 `ptr!=0`；历史 A01 在 U02 已把 `if (!copied)` 真分支反向编码。E01 仅覆盖 1/603 个保存条件，不能代表问题已全面解决。
3. **基础约束保留与符号身份不可靠。**U06 返回增量，U10 的新会话只收到增量。A04 历史中已发生基础断言中间丢失、无实际 Solver.check，修复又产生新符号；后续 U09 重引入基础断言仍未统一对象身份。

这些是静态代码缺口和有定位的历史证据，不是本阶段新实验指标。Z3 对公式的结果正确，也不能弥补错误/不完整的 C 语义编码。

## 2. 固定技术基线与第四阶段真实检索基线

| 项目 | 固定值/来源 |
| --- | --- |
| 论文 | [arXiv:2506.10322v1](https://arxiv.org/abs/2506.10322v1)，PDF 11 页，不使用后续 PATHAGENT |
| PDF SHA-256 | `03eba4d55590bd67228b37e10eda3662d604e708f112f5d9d973efbcc02feacd` |
| arXiv v1 源码归档 SHA-256 | `c02abf4e361ac111cae8f003ea353e2ca1427a75b80720ecdea7bf45f3151457` |
| 官方代码 | `upstream` detached HEAD `4efb4b9bf7e845e180451b43ba29a25e3edaa0e3`，检查前工作区干净 |
| 发布仓库 | [Tangxia-insomnia/fuxian](https://github.com/Tangxia-insomnia/fuxian)，main；审计前提交 `ce0193de3b4bb6f8a3592c2faadf0f04f2851c1e`，工作区干净 |
| 第二阶段 Prompt 审计 | `68eaa6f6396aa66a6ffaf4c3e7a4af0e4f79ab54`，本次只引用、不修改 |
| 上下文恢复的历史来源 | `29ca96e0d5f860d1f4ce07cd3e54e5e25732d1a1:baseline/NPD-*.json`，与官方算法冻结版本分开记录 |
| 安全策略 | `real-bugs-first-v1`，原六条件与独立语义复核要求不变 |

第四阶段的真实 Harness 单 Agent 检索实验按用户本次提供的实际运行结果登记：`codeql_libav / position=54`，get_alert_context 成功 1 次；lookup_function_source 实际调用 4 次，成功获取 `avio_rl32`、`avio_rl16`、`avio_r8`，`avio_rb32` 返回 `FUNCTION_NOT_FOUND`；完成三层连续检索，遵守最多五次扩展决策；未运行 SMT/Z3，也未判断缺陷真假。

这是后续研究的**真实 Agent 检索实验基线（用户提供实际运行结果）**，不是完整 LLM4PFA 复现。本次可见本地材料没有提供该轮完整原始 Harness 消息/调用轨迹供独立逐条哈希核验；记录其来源边界，不将旧离线夹具当成这次真实运行日志，也不把失败函数误写成别的名称。本阶段不针对 position=54 增加规则。

## 3. 十个审计问题的回答

| 问题 | 回答与证据 |
| --- | --- |
| P 如何定义？ | Source 后的初始状态，包含 Source 所需前提、语句后置状态，后续函数纳入参数相关路径约束；论文 p5 §3.2.2 |
| P 从哪里获得？ | 方法上由告警的目标/Source/Sink/轨迹与代码语义确定，LLM 在其前提下推理；完整构造算法/统一格式未公开，不能认定自由生成；见[初始状态分析](initial_state_p_analysis.md) |
| 数据足够吗？ | 部分告警/函数片段/派生条件可用；不普遍提供 Source、类型/别名、赋值版本、构建宏和完整 P。8 个 NPD 原始文件共 808 行，不是新增实验数或论文全基准 |
| Agent 如何提取条件？ | 论文先基于 CFG 提取关键分支，再由 Agent 推理范围；冻结活动代码用文本/缩进提取，工具调用入口被注释，不能等同论文完整 CFG/Agent；见[约束生成](constraint_generation_analysis.md) |
| Prompt 如何生成 SMT？ | U02 基础声明/断言；U04/U05 范围分析；U06 新增；U07 提前退出转换；U09/U10 合并整理；U01 修复。论文附录规则和模板生成 Prompt 不完整 |
| 不同函数如何传递合并？ | 论文要求 P 相关约束随参数传播；官方实参筛选有误且递归入口覆盖条件，补全版只修部分入口；缺类型化状态与统一符号映射；见[合并分析](smt_merge_analysis.md) |
| 基础 SMT 是否完整保留？ | 不保证；U06→U10 只传增量，A04 有实际中间丢失；U09 明确传 B 但非所有路径都走到它；见[基础约束专项](base_constraint_preservation_audit.md) |
| SAT/UNSAT/UNKNOWN 如何解释？ | 官方委托模型返回 bool，有 unknown 被错误折成 False 的静态风险；补全版严格 bool、检查实际查询并拒绝 unknown，但错误证据保留仍不完整；见[求解审计](z3_solver_analysis.md) |
| 论文如何判路径？ | p4 §3.1 True 为存在可行路径，False 为不可行；p6 §3.3 UNSAT 短路。没有公开完整 unknown 协议；公式正确性仍依赖编码 |
| 安全层如何衔接？ | 独立离线 bundle → 公式重放 → 六条件/独立语义复核，不是现有 Harness 自动钩子；本次未调用。局部极性通过和 UNSAT 均不能自动批准 FILTER |

## 4. 分层核对

| 层次 | 已确认 | 不应宣称 |
| --- | --- | --- |
| 原论文 | CFG 关键条件、给定 P 的范围推理、函数检索、P 敏感 Memory、增量 SMT、UNSAT 早停、最多 3 轮修复 | 已公开完整 P 构造器、全部 SMT 规则和 robust unknown 协议 |
| 公开冻结代码 | 可审阅 Prompt 和 pipeline；有极性冲突、增量接口问题、状态覆盖、部分跳过求解路径 | 在当前环境原封不动可运行；内部缺失包的 Prompt 与公开文件必然相同 |
| 当前补全版 | 公开模板不改；上下文恢复、受限解析、独立 solver worker、真实查询记录、部分运行错误修补 | 已补全 C 语义、完整 P、跨函数符号表或确定性合并 |
| 本项目安全保护 | 六项门槛、绑定语义复核、失败保留；E01 是受限局部检查 | 哈希/重放即独立 C 证明；E01 通过即可批准过滤 |
| Harness 检索 | 用户报告的真实单 Agent 多轮检索已成功 | 已完成变量状态推理、SMT 求解或误报过滤复现 |

## 5. 历史 E01 结果引用

[保存的 test_results.json](../../safety_runs/E01_predicate_polarity_consistency/test_results.json) 显示合成测试 156/156 通过；[metrics.json](../../safety_runs/E01_predicate_polarity_consistency/metrics.json) 显示 10 条审计 + 20 条固定回归合计 603 个条件，仅 1 个可局部检查，冲突 1 条/错误原子 3 次；整个样本可支持数为 0。E01 历史最终为 0 FILTER / 0 KEEP / 30 UNKNOWN；安全 v1 历史为 0 / 15 / 15。未知不计过滤成功；操作上保留全部告警不等于证明了全部真实缺陷。

这些结果来自已保存文件，未重跑。20 条是固定回归集，不是盲测。E01 的边界与逐样本说明见[极性专项](polarity_consistency_audit.md)。

## 6. 关键文件 SHA-256

| 文件（相对 reproduction/） | SHA-256 |
| --- | --- |
| upstream/llm4pfa/prompt_templates.py | `43fa105beb98fd40e7214dd321521ec1085ef8c9c557fa4863eaa9b502417a4c` |
| upstream/llm4pfa/feasibility_analysis_pipeline.py | `c903f6de291ad4dc0e29ffbfefa7c287d4b92c50d1a7b3febf2661e1a51fb8e3` |
| completion/engine.py | `c2b33783874a778717819a96943f4b646f4c09af7a1d032acc82106381005194` |
| completion/context.py | `ceef443e7de3c47579696fa8e67ec1b7efb495dac9c380f47138f48833c3c046` |
| completion/solver_worker.py | `cff88c483595615584c3a339d11edabd78e5f20ee3c950fc86793f74fd6cde62` |
| safety/policy.py | `eadc92a551aa1f1844b9b0fa8316950c5823a21bab77c2f4a4979ac76811c946` |
| safety/replay.py | `2f33021b667ae1ad8d88f8250170fb9bc0393b3d68380ea58e533651d1865d5c` |
| safety_runs/E01_predicate_polarity_consistency/predicate_check.py | `0d41c1142adee9a3047ce2014daad1ef6e6ea85eee674d9d4534e15cf63880e4` |
| safety_runs/E01_predicate_polarity_consistency/metrics.json | `a29a0723d06c92e40929c25a1246c0fc2e471b7d25ffb4ad2a13217a60d5e2fa` |
| safety_runs/E01_predicate_polarity_consistency/test_results.json | `029c25d0f4e6ac497d5f5f9fdaaeeb46eb841d63ac1ae1dce79b37a703cd04ac` |
| audit/failure_audit_20261029/audit_samples.json | `6980a64dd1d499188ccc83002bfdf3255196f1c17e462eaab44d83db67aa366b` |
| safety_runs/20261029_v1/fixed_holdout.json | `c4ef793abe5f00437f52c27b6fe545dfa613ed661eb441362e1315f1ed98243d` |
| results/raw/completed/budget_ledger.json | `a0b6957098e905700133acbcbae5c77a529b07e4b04c9743cd164fea80f0201b` |

数据文件均位于 `upstream/benchmark/NPD/`：

| 文件 | SHA-256 |
| --- | --- |
| codeql/codeql_kernel69_nullpointer.json | `5385ae52f09cc927dbc5e29f17229ccaaa68467e1614cbf73d219fd1f46713a3` |
| codeql/codeql_libav_nullpointer.json | `a5683aa98e8a50efbb430913b25b65528076dfc6e81de6c4bb1fac6bb6a86ed2` |
| codeql/codeql_openssl_nullpointer.json | `4664bb6b80e8a18ab2e19b1489c4ca9ce7fb4f2c720dd0f402d1762356112882` |
| cppcheck/cppcheck_linux_nullpointer.json | `bc1fcdd59756e855c0ee7987e6b788d408a5b0815f207e9f4ef272bf1ca234b6` |
| cppcheck/cppcheck_libav_nullpointer.json | `1f6c2d513b5ac6b8d5910b9b82e3eeb96a6701ca8d84f0b9dd90077e2564c347` |
| cppcheck/cppcheck_openssl_nullpointer.json | `5a7e89ffb017ece94403f862a5cc8d33f478fc92360d4e957648d66aeee12d29` |
| infer/infer_libav_nullpointer.json | `ed2233c572c81fd05b1407951babe48dccc0a5dc6b59b412ad2705874ab83126` |
| infer/infer_openssl_nullpointer.json | `8d0828a40f04ede896e19f0fb993e3d5f70c23556208275d913b5a1d6a3cb0d2` |

历史调用证据哈希另见[基础约束专项](base_constraint_preservation_audit.md)。PDF 与 TeX 的页码/源码对应沿用第二阶段已取得的 v1 文献证据；没有将后续版本内容混入。

## 7. 本阶段交付、验证和下一步

本目录包含 8 份非空文档：本报告、初始状态、约束生成、合并、求解、极性、基础保留、[恢复计划](smt_z3_recovery_plan.md)。所有结论区分论文、公开代码、补全版与新增保护；案例只用于解释现有证据，不含样本 ID 特判实现。

保护检查覆盖本阶段开始时 3508 个非凭据项目文件，排除 `.git`、`.venv`、`__pycache__`、`node_modules` 及 `.env*`；按相对路径→SHA-256 排序 JSON 的聚合基线为 `4b459d0cafca0c027788acd4bd370207bc3ceeefb7183dac4d25d0233bc1d0c8`。文档完成后重新计算：仍为 3508 个文件、同一聚合哈希，原文件无变更。8 份文档的非空/UTF-8、本地链接存在性、哈希长度和明显凭据模式检查通过；这是文件检查，不是算法测试。不访问或输出密钥。

下一步优先建议一个单独的基础约束保留静态契约实验，先不运行 Z3 或模型；并保留 E01 检查边界。P 构造、Source/赋值定位、符号身份和求解三态分别作为独立问题推进。本次审计完成后停止，不自动进入任何修复或实验。
