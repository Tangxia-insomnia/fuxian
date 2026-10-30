# 通用算法修复计划（尚未实施）

第一目标为真实缺陷保留，第二目标为误报过滤。基线和 real-bugs-first-v1 六条件门槛均保留，任何新增检查只提供诊断或拒绝不可靠候选，不能自签过滤批准。以下样本 ID 仅用于测试夹具与报告，不得进入生产条件、白名单、例外分支或符号转换逻辑。

当前代码是基于 2025 旧实现的 documented completion，并非新增 restore 分支。审查发现 restore 分支近期补齐部分模块，但仍标明候选来源且缺 dereferences；此阶段不切换代码、不把它当原论文完整实现。未来若比较新分支，必须另设版本与实验，不与本轮单问题修复混合。

## P0-1 / R01：条件极性与合并完整性

代码位置：

- [upstream/llm4pfa/prompt_templates.py](<E:/codexconversation/课题研究/reproduction/upstream/llm4pfa/prompt_templates.py:136>)；相关行 136-148,171-187。
- [upstream/llm4pfa/feasibility_analysis_pipeline.py](<E:/codexconversation/课题研究/reproduction/upstream/llm4pfa/feasibility_analysis_pipeline.py:174>)；相关行 174-179,276-282。
- [completion/engine.py](<E:/codexconversation/课题研究/reproduction/completion/engine.py:110>)；相关行 110-130。

既有案例：A01: copied!=0 与 copied==0 同时进入最终查询，UNSAT 导致标签1被过滤；A10: 双重否定和合并正确的局部逻辑对照，不代表可批准过滤。

证据边界：A01 的翻译极性与合并错误已由原日志和既有诊断确认；不是证明其完整C路径一定可行。

最小修改：为已知类型的简单标量空值/零值条件保存原表达式、分支方向、符号和来源；用确定性规则核对生成原子；与来源不一致则拒绝该候选，保持UNKNOWN。不自动删除任意矛盾断言。

验证：不含样本ID的参数化合成条件与A01/A10缓存输出；验证正确否定、错误极性可定位、合并不改名/不丢失。原提示词!ptr→ptr!=0另行纠错但不能以离线缓存证明提示词效果。

## P0-2 / R02：目标定位及提前退出的控制范围

代码位置：

- [completion/context.py](<E:/codexconversation/课题研究/reproduction/completion/context.py:141>)；相关行 141-161。
- [completion/engine.py](<E:/codexconversation/课题研究/reproduction/completion/engine.py:158>)；相关行 158-170。
- [upstream/llm4pfa/extract_util_plus.py](<E:/codexconversation/课题研究/reproduction/upstream/llm4pfa/extract_util_plus.py:1139>)；相关行 1139-1152,164-174,640-801。
- [upstream/llm4pfa/feasibility_analysis_pipeline.py](<E:/codexconversation/课题研究/reproduction/upstream/llm4pfa/feasibility_analysis_pipeline.py:159>)；相关行 159-170。

既有案例：A03: 同文目标两处，循环覆盖为最后一处；空格缩进遗漏case/while；A06: 空格缩进丢失switch分支；A02: 分配分支内!skb保护未证明支配所有进入路径。

证据边界：重复目标和Tab依赖已确认；A02控制范围与原标签冲突仍未裁决。

最小修改：分两次：先要求位置/源码身份唯一，重复且无法绑定行号时UNKNOWN；再修空格/Tab和无歧义块结构。提前return/goto必须具有可证明的路径范围，不能把向上扫描得到的局部guard当全局支配条件；复杂跳转先拒绝。

验证：重复同文语句在不同分支、不可识别绝对行、混合缩进、多行条件、switch穿透、循环和goto绕过的合成片段；A03/A06结构结果只与已核验位置比较，不猜枚举值。

## P0-3 / R03：符号身份、类型与赋值版本

代码位置：

- [completion/solver_worker.py](<E:/codexconversation/课题研究/reproduction/completion/solver_worker.py:35>)；相关行 35-46,63-72。
- [upstream/llm4pfa/prompt_templates.py](<E:/codexconversation/课题研究/reproduction/upstream/llm4pfa/prompt_templates.py:145>)；相关行 145-148,183-187。
- [completion/context.py](<E:/codexconversation/课题研究/reproduction/completion/context.py:86>)；相关行 86-100。

既有案例：A04: object:Int/object_ptr:Int/object_bv:BitVec64被建成独立符号；A02: 多次skb赋值未区分版本；既有same_symbol_sort_audit记录: dev同名Bool/Int。

证据边界：A04身份拆分已确认；没有足够证据为所有指针强加64位或任意别名等式。

最小修改：先增加符号清单核对，按作用域/声明/赋值版本登记；同一实体多个独立表示、同名异sort或未绑定重赋值先UNKNOWN。别名关系只由具体赋值/参数证据引入，缺位宽不擅自Int2BV。完整SSA不在首轮范围。

验证：相同变量不能无依据拆分；不同作用域同名变量不能强行合并；重赋值产生新版本；未知类型保持UNKNOWN。A04仅允许诊断连接，不因此批准FILTER。

## P1-1 / R04：赋值提取的函数头占位与缺失状态

代码位置：

- [completion/engine.py](<E:/codexconversation/课题研究/reproduction/completion/engine.py:83>)；相关行 83-86。
- [upstream/llm4pfa/feasibility_analysis_pipeline.py](<E:/codexconversation/课题研究/reproduction/upstream/llm4pfa/feasibility_analysis_pipeline.py:159>)；相关行 159。
- [upstream/llm4pfa/extract_util_plus.py](<E:/codexconversation/课题研究/reproduction/upstream/llm4pfa/extract_util_plus.py:1137>)；相关行 1137-1154,1165,1183。

既有案例：A10: variable_assignments.text=static void；A01/A02/A04: variable_assignments.text也是函数签名。

证据边界：上游None输入+assignment_line_index=0直接制造占位；当前主流程并未消费variable_assignments字段，不能把仅修占位说成效果修复。

最小修改：先将未提供/未找到赋值表示成显式missing/空结果及原因，禁止函数头冒充赋值；另一次变更再提取目标前已定位的简单赋值（含声明初始化），多候选/链式赋值未建模时UNKNOWN，不盲取最近文本。

验证：None、未找到、目标后赋值、声明、初始化、重复赋值、链式赋值及遮蔽；A10可见lookup位置应作为候选附来源，不冒称扫描Source。原始JSON不改写。

## P1-2 / R05：跨函数状态传递与条件中的调用识别

代码位置：

- [completion/context.py](<E:/codexconversation/课题研究/reproduction/completion/context.py:75>)；相关行 75-100,163-180。
- [completion/engine.py](<E:/codexconversation/课题研究/reproduction/completion/engine.py:88>)；相关行 88-97。
- [upstream/llm4pfa/feasibility_analysis_pipeline.py](<E:/codexconversation/课题研究/reproduction/upstream/llm4pfa/feasibility_analysis_pipeline.py:159>)；相关行 159-162,420-433。

既有案例：A08: 形参名映射正确但两帧只留下各自的空指针假设；A05: !WARN_ON(!sta)被当作不支持的复合实参阻塞。

证据边界：参数位置映射成功不等于值/路径状态已传递；原函数入口重提取覆盖传入条件，未绑定caller/callee符号环境。

最小修改：先显式记录跨帧输入/输出与实际参数等式，仅支持已确认的直接实参；未绑定则UNKNOWN。区分布尔条件包装与真实指针参数调用，不将!sta当sta，不随意略过宏。

验证：两函数简单指针传递、同名/异名、遮蔽、调用前重赋值、无支持宏/复合实参的合成案例；A08检查状态是否缺失，A05只消除误识别而不自动放行宏语义。

## P1-3 / R06：SMT断言与源码的语义来源绑定

代码位置：

- [safety/policy.py](<E:/codexconversation/课题研究/reproduction/safety/policy.py:38>)；相关行 38-69,117-177,198-215。
- [completion/solver_worker.py](<E:/codexconversation/课题研究/reproduction/completion/solver_worker.py:43>)；相关行 43-46。
- [safety/metrics.py](<E:/codexconversation/课题研究/reproduction/safety/metrics.py:22>)；相关行 22-43,52-63。

既有案例：A10: UNSAT可重放但原始构建身份不齐；A01: 可解的生成脚本可表达错误断言；A02/A04: 作用域/变量状态证据未闭合。

证据边界：求解重放只证明公式；现有安全门槛有效阻止无完整复核的FILTER。

最小修改：补充逐断言来源清单：代码哈希/范围、角色、分支方向、符号版本/类型、宏证据、模型输出及查询哈希；保留六条件门槛与独立复核要求。UNSAT core只能辅助定位，不自动成为证明或批准。

验证：缺任一关键来源/源码变化/类型冲突/模型输出截断/UNSAT无来源均UNKNOWN；继续验证UNKNOWN不算过滤。诊断层不得自签manual_source_review。

## P2 / R07：输出解析及可执行性问题

代码位置：

- [completion/engine.py](<E:/codexconversation/课题研究/reproduction/completion/engine.py:99>)；相关行 99-108。
- [completion/model.py](<E:/codexconversation/课题研究/reproduction/completion/model.py:88>)；相关行 88-90。

既有案例：A06: JSON解析抓取前面的C代码块；A07: 输出截断。

证据边界：旧审计已有5条合法JSON解析失败的证据；不重新统计或调用模型。

最小修改：明确JSON块标签与schema，歧义或截断继续失败/UNKNOWN；单独修复，不同极性、状态传播一起修改。

验证：只用已保存混合C/JSON/解释文本和截断输出；解析成功不能直接变成FILTER。

## 实施顺序与避免混杂

先做 R01 的通用极性一致性检查，解决已见真实缺陷误删的直接错误来源。R02 必须拆成定位唯一性和控制范围/缩进两轮；R03 拆成本地符号身份与后续赋值版本；R04 拆成去掉假占位和真正赋值恢复；R05 拆成状态绑定与宏/调用识别。每轮只变一个主要问题。

R04 去占位是小而确定的真实性修复，可在其单独轮次执行，不能和 R01 同时改后把指标变化归给某一个。当前主流程只读取 bug_line_constraints、target_conditions 和 early_jump_constraints；未消费 variable_assignments。故只把 static void 换成 missing 会改善证据契约，不会自动补出别名关系或改变旧最终预测。

R02 不应仅把空格全改Tab就宣布C控制流正确；该做法仅为旧审计的诊断探针。R03 不应把所有同名变量绑定，也不应把所有指针硬编码64位。R06不修改既有FILTER门槛，完整来源也不能代替真实语义复核。R07解析成功只代表格式通过，仍须走相同安全门槛。

下一轮先实现 R01 的小范围一致性核对，暂不重建整套C前端、完整SSA或代理框架。修复代码允许识别语法、类型和来源；禁止识别样本ID、标签或项目中的某个函数名来决定例外。
