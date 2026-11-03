# SMT/Z3 约束可用性审计

日期：2026-11-03。结论：**已有材料支持研究小规模、明确假设的标量片段 SMT 接入；不足以直接认证真实完整程序或 R01–R05 跨帧路径。现有 B/Δ 不能直接作为可靠程序约束求解。** 本轮没有转换、执行或求解任何约束。

## 1. 约束的四种来源不能混用

| 层次 | 实际来源、字段 | 当前可信范围 |
|---|---|---|
| 原始保存条件 | `E:/codexconversation/课题研究/reproduction/upstream/benchmark/NPD/codeql/codeql_kernel69_nullpointer.json` 的 `bug_line_constraints`、`var_assign_conditions`、`pointer_null_postconditions`、`early_jump_constraints`；其他组的源码、source、sink等 | C/控制流文本和材料位置；不是已类型化、已绑定的SMT，也未证明来自完整可靠CFG |
| 官方算法运行时 B/Δ | `upstream/llm4pfa/feasibility_analysis_pipeline.py:173` 起模型生成 `response_message_target`（B）；`:231` 起生成 `bug_line_constraints_response`（Δ） | B是路径相关模型脚本，含临时添加的`var_name == 0`缺陷查询；不是单纯guard集合。冻结benchmark未直接提供完整每样本B/Δ库 |
| 项目补全的结构转换 | `completion/constraint_bundle.py:103` 的 `assemble_base_delta()`；E03保存`bundle.base/delta`、`merged_script`及区间 | 去传输围栏、保留原代码并确定性拼接；结构来源可追溯。**没有因此完成C语义转换** |
| 项目旧模型公式 | E02 `bundle.solver_events[*].source`、E03 `sources.*.raw_text`、历史调用响应 | 可能是可解析的Z3 Python或SMT文本，但变量/类型/极性/路径绑定不可靠；仍是未认证公式。禁止本轮执行 |

没有在原benchmark中发现名为B、Δ、SMT-LIB断言表或可靠`ConstraintBinding`的字段。官方代码引用的旧context/constraints/cache路径并不等于相应文件全部随冻结提交发布。后续恢复constraints文件是候选C文本结构，也不是typed SMT。`bug_report`和baseline自然语言解释均不能被直接变成程序前提。

## 2. 已有 B/Δ 的来源能力

保存实例：`E:/codexconversation/课题研究/reproduction/safety_runs/E03_base_delta_explicit_transfer_fix/engine_traces/A04/constraint_transfer_e03/001.json`。

它实际含 `event_id`、`sample_position`、`frame_level`、`dataset`、`sample_id`，以及 `bundle.base/delta`：

- `stage/reference/raw_text/raw_sha256`：U02或U06原响应及来源字符串；
- `code_text/code_sha256`：传输解码后的代码；
- `merged_span.start/end/unit`：合并脚本中的**Python字符半开区间**，不是UTF-8字节区间，更不是C源码范围；
- `assembly_audit/check_contract`：声明/断言结构保留状态；
- E02 IR中 `assertions[].origin` 或 `declarations[].origin`：脚本reference、脚本行/命令序号和脚本hash；Python bindings表示Python名称到Z3符号，不是C声明到版本。

`completion/constraint_bundle.py:90` 明确保留 `semantic_correctness=NOT_ASSESSED`、`polarity_correctness=NOT_ASSESSED`、`alert_safety_decision=null`、`solver_executed=false`。实例的`contract_status=PASS`只证明所声明的结构合同，不证明原C路径不可行。

缺少逐断言的：原C文件与AST范围、原TU/build身份、canonical声明/slot、当前ValueVersion/MemoryVersion、call context/path、转换与分支极性证明。`frame_level`也不能直接当R05的调用实例ID。

因此：**可以完整保留原字节和已有脚本来源，不能完整保留尚未存在的C状态语义来源。** 字符串reference非空或hash匹配不补足语义。原公式及重复断言必须保留，不自动改名、去重、删除“矛盾”条件或弱化类型。

## 3. 九项可用性回答

| 审计问题 | 实际判断 |
|---|---|
| 1. 存在能写成SMT的表达式吗？ | 有。源码中的常量、比较、简单条件赋值/整数除法等有有限编码可能；旧脚本已有SMT/Z3语法。**语法可编码不等于已有可靠转换**。 |
| 2. 有明确变量身份吗？ | 通常没有。`var_name/prt`可能是`buf.bn`、`*oldref`等表达式；同名/同成员文本不能确定同声明、同值或同内存。原公式的`Int('object')`不是C身份认证。 |
| 3. 有类型和范围吗？ | 有部分声明拼写/常量后缀，缺可信canonical类型、ABI位宽、typedef/宏、转换和范围合同。`long`不能默认64位，指针不能默认Int。 |
| 4. 能追溯具体C位置吗？ | 所有原记录有告警位置和snippet；原条件项大多没有逐项AST范围/版本。函数片段行号、原工程行号、Python脚本行是不同坐标系。 |
| 5. 有路径条件吗？ | kernel CodeQL70行有结构化文本，其他可见if/循环/return源码；无可信path_id、覆盖全集或极性证明。不能把所有early jump条件直接AND。 |
| 6. 能区分signed/unsigned吗？ | 部分原类型拼写可读，但不足以建立所有转换后的操作数类型。需证据绑定；未知时UNKNOWN。 |
| 7. 涉及指针、数组、内存、位运算吗？ | 大量涉及。NPD/BOF/UAF依赖对象、别名、生命周期和调用效果；DBZ亦可能有宏、位移、截断、溢出。当前数据未提供统一模型。 |
| 8. 什么能安全转换？ | 在声明/版本、类型/范围、极性/到达路径与来源已验证的条件下，有限常量、复制等式、比较和明确布尔组合可由确定性编码器转换。这里是**未来准入规则**，本次没有产出满足全部规则的新约束。 |
| 9. 什么必须UNKNOWN？ | 未绑定脚本符号、宏/typedef/ABI不明、未知调用效果、指针/成员错绑、旧值与新值混淆、分支覆盖不足、未定义行为不明，及所有以自然语言结论补足的事实。 |

## 4. 首轮编码需要的语义边界

以下为研究设计，不是实现或已经通过的证明：

1. 符号以来源、声明、值版本、frame/path命名；展示名称单独存储。一次赋值不能覆盖旧SMT符号，R04内存变化不能只改局部变量名。
2. C整数需明确位宽、符号和提升/转换。无界Z3 Int仅能在有范围/无溢出证明的子集中使用；unsigned算术应考虑模运算，signed溢出不能默认wrap。
3. C除法向零截断；Z3 Int除法在负数情形不能直接照搬。位向量除法通常对除零有总化定义，不能让求解器的总化行为抹掉C错误。查询应表达“执行到除法前分母为零”等故障条件，并分别处理正常执行的definedness，不能一边断言分母非零一边误称已排除告警。
4. 移位需检查次数、符号/位宽及未定义行为；数组需对象边界，指针需对象/offset/有效期。首轮不做一般内存SMT模型；现有R04有限对象关系可复用，不能等同于已实现完整指针语义。
5. 布尔短路和分支独立保留。不同return/if替代路径用独立查询或可追溯的选择，不将兄弟guard相与。未知前提不作为“为了求解”而加入的约束。
6. 明确查询范围：局部片段、已知路径的可行性、完整告警的排除不是同一命题。SAT只说明当前抽象存在模型；UNSAT也只说明给定公式矛盾。两者均不能绕过证据门槛授权FILTER。

旧模型脚本不应通过任意Python执行作为确定性接入方式。可复用E02静态允许语法检查和E03保存机制；未来如做公式诊断重放，也要单独标“公式级、未绑定C语义”，不能和真实程序覆盖混计。本轮未导入checker/旧脚本，也未执行solver_worker。

## 5. 候选筛选结果：只保留两条

见 `candidate_samples.json`。完整解析所有原JSON，并检查DBZ16条目标/函数体及短NPD例子；选择依据是依赖简洁程度，不使用标签或期待的SAT/UNSAT结果。没有为凑10条加入宏/内存复杂样本。

**第一优先：DBZ零基行4，原index4，stb0899_calc_derot_time。**

`E:/codexconversation/课题研究/reproduction/upstream/benchmark/DBZ/all_cwe369.json:/4/function_call/0` 保存7行函数，参数`long srate`，单if，目标为`100000 / (srate / 1000)`，没有外部调用、宏或成员。它适合研究“guard不等于分母非零”及C整数除法编码。缺原TU/ABI/调用者范围，因此只能在**显式片段合同**下研究局部性质。原标签0不变；局部可达不等于完整项目真缺陷，也不能据此声称标签错误。R02目前不覆盖除法，不能说它已提供可直接导出的算术证据。

**备选：DBZ零基行2，原index2，dss_pll_hsdiv_calc_a。**

参数`unsigned long out_min`，保存`out_min = out_min ? out_min : 1`及后续除法位置，可研究纯标量赋值切片。完整函数还有min/max/DIV_ROUND_UP/ULONG_MAX、结构体、循环和回调，不能直接全函数编码或假定无副作用。需先认证切片范围和赋值到使用之间的关系；否则UNKNOWN。

这两条都没有可直接投入真实R01–R05→SMT整链的认证材料；**无条件就绪的完整程序样本为0**。这不否定局部语义实验价值，也不将局部实验包装成原论文结果复现。

## 6. 与已有R模块的接合限制

R01 `mapper.py:180`、R02 `config.json`、R03 `return_transfer.py:187`、R04 `indirect_write.py:243` 的既有门槛只支持`synthetic-self-contained`，真实保存材料为`saved-source-only`。当前入口也不是任意compile_commands导入器。即使以后拿到完整工程，**直接封装文件不能让旧接口自动批准真实构建**。不得把真实片段改标合成TU获得PASS。

当前R05已有嵌套、路径隔离、正常返回/内存桥协议，参见 `E:/codexconversation/课题研究/reproduction/safety_runs/E06_R05_cross_frame_ledger/protocol/execution_v2_spec.md`；无需重新开发这些算法。但 `src/protocol/evidence_runtime.py:29` 对所有非`fixture-explicit`生产者固定附加`non_fixture_source_semantics_not_certified`。独立Adapter可以提供文件和引用并保留UNKNOWN，不能仅凭适配得到真实PASS。

若研究后续要求真实证据获准，需另行确认来源认证的兼容入口；这属于准入边界扩展，不是重写R01–R05，也不是本轮可以擅自修复的缺陷。首轮局部SMT实验应诚实保留这层UNKNOWN。

## 7. 当前可以决定什么

可以决定继续保留原论文数据为主告警来源，新增只读来源封装和有限标量编码的研究任务；不必重建整个数据集。当前不能决定直接启用全量SMT过滤、真实跨帧PASS或多Agent最终裁决。所有外部语义缺口需独立证据解决，不能由模型一致意见补成事实。

本轮SMT生成/求解、LLM、Harness、旧回归、R05 Builder/Validator、原分析器执行均为0。
