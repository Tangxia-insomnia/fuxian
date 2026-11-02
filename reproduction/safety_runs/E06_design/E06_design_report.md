# E06 第一阶段设计报告

日期：2026-11-02。状态：**审查与设计已完成，正式 E06 开发未开始，所有新测试均未执行。** 本阶段只在 `safety_runs/E06_design/` 新增文档与只读统计/完整性材料，没有修改核心代码、Prompt、MCP、安全门槛或历史数据，没有模型、Z3、Harness 或生成代码执行。

## 1. 基线和本阶段实际工作

发布基线：E05 `6452442e492293f42b6b0cf4930dca6685d0c6d7`，main 起始干净；官方冻结 `4efb4b9bf7e845e180451b43ba29a25e3edaa0e3`；论文 arXiv:2506.10322v1。

已只读核对 E05 输出清单及其前置历史保护，保存 4456 个原有文件的起始哈希。阅读了官方 pipeline/Prompt/提取器、completion context/engine/constraint_bundle、MCP 工具、论文缓存与既有专项审计，并审查 A01、A04、E04-ND 及固定 20 条保存上下文。共登记 60 个主要来源文件的 SHA-256。

阶段边界需要继续区分：真实 Harness 单 Agent 实验验证了源码检索；原 E04 A04 frame=1 和 E04-ND frame=0 是隔离目标帧的真实模型约束传递实验，都没有证明完整跨函数状态传播。本阶段没有重跑这些实验，也没有将其升格为完整 LLM4PFA 复现。

本次只进行了现有 JSON 的读取、函数/帧/位置/哈希统计及环境包/PATH 元数据查询；没有导入运行 engine、调用模型或执行 Clang/Z3 分析。固定集的审查不是一轮新传播回归。

## 2. 为什么当前系统不能可靠传播状态

当前完成的是部分上下文检索、文本参数序号对应和同帧 B+Δ 结构保留，缺少统一的、带执行点的传播环境：

1. `context.py` 按实参文本和参数序号得到名字映射，缺少完整声明/类型/链接以及当前值版本。caller p 与 callee item 的入口值关系，不能被当成两个局部变量是同一个对象。
2. 每层 pipeline 在第 159–162 行重新覆盖传入条件，之后又拼接当前变量名的 `==0`；调用方已有 P 不能被证明完整保留或正确实例化。
3. 缺少赋值前后版本、return/out-effect、别名/内存和路径上下文。简单相与所有帧约束可能制造旧值/新值的伪矛盾；各帧单独求解也不能证明同一个跨帧状态可行。
4. 真实项目的构建/宏/typedef/成员定义仍缺证据。LLM 文本不能代替这些事实；结构 PASS 无法排除 E04-ND 的语义错误。

完整证据路径和行号见 [E06_source_audit.md](E06_source_audit.md)。论文公开描述要求后续函数承接与参数有关的可行路径约束，但没有完整公开本文拟设计的版本/别名/效果实现，E06 属于明确标注的复现适配。

## 3. 最优先修什么，SSA/Clang 如何使用

优先修“**具体调用点上的声明、类型及入口值对应**”，同时把 caller 前提作为不可覆盖的独立记录。不要先扩大字符串合并或依赖模型自行解释跨函数对象同一性。

需要简化 SSA 式的变量版本，但放在第二轮；先支持直线 def-use 与受限分支，不实现完整 SSA、循环 phi 或 whole-program 指针分析。相同变量的旧版本约束继续存在，新值使用自己的版本，不通过删 B 消除冲突。

推荐使用已有 libclang 提供可靠 AST/类型/声明信息。环境已存在 libclang 18.1.1；PATH 未发现 clang 系列可执行文件。本阶段未测试库加载/解析。自包含合成输入可先验证前端；真实库/内核语义仍需要相应版本头文件、TU/构建参数和宏配置。不能自动补 stub/默认类型后宣称恢复原扫描语义。Clang 本身也不会自动解决别名、状态或路径传播。

详细比较与 sidecar/IR 合同见 [E06_technical_design.md](E06_technical_design.md)。

## 4. 哪些真实样本适合验证

固定 20 条中有 **3 条多帧、15 条单帧、2 条无已保存帧，共 23 帧、5 条相邻调用边**。这是数据审查统计，不是 5 条传播已验证成功。没有样本被本阶段认证为完整传播正向案例。

| 优先用途 | sample_id | 原保存链/关键问题 |
| --- | --- | --- |
| R01 首选局部边 | `NPD/codeql/kernel69:row=24:index=43` | ip6_finish_output2 → sock_confirm_neigh → neigh_confirm；第 2 实参 neigh→n，再第 1 实参 n→n；仍需精确声明/构建证据，宏/共享状态不自动判断 |
| R01/R05 备用 | `NPD/codeql/libav:row=51:index=84` | mv_read_header → read_index；ast→st 与同一 callee 的 vst 调用点必须分开；分配、分支、typedef/循环缺口保留 |
| R03–R05 边界 | `NPD/codeql/openssl:row=30:index=31` | make_ocsp_response → OCSP_copy_nonce → OCSP_BASICRESP_add_ext；早退、返回值被忽略、成员地址参数/副作用 |
| 身份/状态负例 | A04 `NPD/codeql/kernel69:row=12:index=24` | saved_clone/clone 值复制后地址副作用；object 系列符号冲突、B 丢失与宏 |
| 状态负例 | E04-ND `NPD/codeql/kernel69:row=23:index=42` | skb_prev 保留赋值点的 skb 值，不能绑定到后来新 skb；&maxfraglen、成员/unsigned/路径问题 |
| 极性/构建哨兵 | A01 `NPD/codeql/kernel69:row=10:index=22` | copied 多次更新、预处理、旧极性冲突；本样本单帧，不充当跨函数正例 |

逐样本原文、body SHA-256、准确行号、证据缺口及原 20 条完整名单见 [E06_historical_cases.md](E06_historical_cases.md) 和 [candidate_inventory.json](candidate_inventory.json)。所有规则都应基于通用 AST/状态/证据逻辑，不能针对这些 ID 特判。

## 5. 建议分五轮，每轮怎样验收

| 轮次 | 拟实现内容 | 最低验收标准 |
| --- | --- | --- |
| R01 | 唯一直接调用、声明/类型与入口参数映射 | 实参序号、转换、callee、源码位置可追溯；slot 不合并；缺定义/类型/间接调用显式 UNKNOWN |
| R02 | 局部赋值与值版本 | 旧/新值不串用；复制后独立更新；未知写、分支合流/循环不猜 reaching definition |
| R03 | 完整受限 callee 的 return/按值状态 | return 值与 caller 接收点对应；callee return 不当 caller return；不同调用上下文不串用；未知效果阻断完整摘要 |
| R04 | 唯一 local slot 的地址传递和可见间接写 | 区分改形参本身与写 caller slot；显式 read/write footprint；未证别名/逃逸/外部效果 UNKNOWN |
| R05 | 已验证状态上的跨帧路径 IR 组合 | CallerPre 不覆盖，B/Δ 不丢；不同路径分离；超预算 UNKNOWN；派生表示逐 atom 版本/来源核验；无 FILTER 权限 |

每轮先做通用合成测试和历史风险检查，冻结后对原固定 20 条只检查一次，全部结果保留。当前设计了 **40 项合成测试规格，执行数为 0**；不能写为已通过测试或漏洞验证成功。详见 [E06_experiment_plan.md](E06_experiment_plan.md)、[E06_acceptance_criteria.md](E06_acceptance_criteria.md)。五轮默认离线，不预授权真实模型、Z3 或生产接入。

## 6. 保留原始约束与安全优先级

新机制先产生独立传播证据/IR，不修改原作者 Prompt 和 U02/U06/U10。原 E02/E03 同帧合同保留。跨帧版本命名需要来源映射，不能拿改名后公式绕过原始字面保留检查，或把无法绑定版本的历史输出强行“修好”。

诊断 PASS 只说明请求的受限关系证据充分；REJECT 表示候选传播有明确冲突；UNKNOWN 表示缺口。任何局部 PASS、结构 PASS 或未来 UNSAT 都不能直接过滤告警；UNKNOWN 不计成功。E05 的完整语义覆盖率 0% 不是本轮需要通过放松规则改善的指标。

本阶段无告警动作，真实缺陷保留率/误删率/误报过滤率均未测，不报告成 100%/0%。

## 7. 短期明确不自动判断的内容

未知宏/构建、未知 typedef/成员布局、一般指针别名/逃逸、任意多级间接写、重分配与生命周期、未知库/全局/并发副作用、函数指针/回调、复杂循环/递归/longjmp/inline asm，以及没有模型的整数溢出/UB。遇到这些情况保留证据并 UNKNOWN，不按函数名、样本标签或模型自信补全。具体风险及解除条件见 [E06_risk_register.md](E06_risk_register.md)。

## 8. 交付和停止点

七份请求文档均已新增；辅助材料为起始保护清单、20 条候选统计、60 项来源哈希以及最终保护/输出哈希清单。没有新增 Python/修复代码，没有生成适配 Prompt，没有安装依赖。新增模型调用、Token、费用、Z3、Harness、编译器分析和实验测试均为 0。

最终原文件保护结果见 `preservation_check.json`，输出校验见 `hashes.json`。文档可供审核；建议下次若获批准，只开始 R01 的独立离线实现与前端证据门槛实验，不同时开发 R02–R05。当前到此停止，等待审核，不进入正式 E06 开发。
