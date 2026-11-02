# E06-R03 受限函数返回值与跨帧值关系报告

日期：2026-11-02（Asia/Shanghai）。状态：**验收通过，允许按用户指令仅发布本目录**。

本轮新增独立确定性返回证据层：CallerPre → ArgumentTransfer → CalleeEntry → CalleeReturn → CallerPost。这是项目补全和新增安全检查，不是作者公开的完整实现，也不宣称严格复现论文全部结果。论文固定 arXiv:2506.10322v1，官方提交 `4efb4b9bf7e845e180451b43ba29a25e3edaa0e3`；起始 publication main 为 `8d03eae13a7ea835e61877fc351703eb69b06da4`。没有升级 PATHAGENT。

## 已实现的范围

只读复用 R01 的直接调用、声明和类型转换证据，以及 R02 的局部 def-use 和路径环境；独立 ReturnTrace/CallerTrace 处理调用实例和返回。所有 R01/R02 文件原样。每次调用重新分析 callee，无摘要缓存；call_context_id 绑定数据位置、caller path/pre 环境、两端词法声明、body SHA、调用点和参数映射。callee 的 slot/version 使用实例 namespace，词法声明与实例声明通过同源 USR、声明位置和 body SHA 显式核对（pre_freeze_evidence_check.json）。

支持受控无诊断 C11 TU 中的局部/形参当前值、简单定型 literal、受支持转换、单个 if 和提前 return；按 return 路径创建 caller 新版本，不做 phi 或可满足性证明。形参按值重绑只影响 callee。忽略返回值时保存 callee 返回路径，不创建 caller 接收版本，也不注入 callee guard；void 正常返回另作记录。caller 接收后再次赋值，读取绑定后续新版本。

任何未支持效果/路径均阻断整次调用：caller 当前环境失效并停止，局部返回证据可单独保留。未实现通用副作用/指针别名/间接写入分析、递归、循环、一般 CFG 或 R04/R05。`call_effect_coverage=PASS` 仅表示可见受限语法全部覆盖，没有未处理外部效果；不证明内存对象、生命周期或完整 C 语义。

## 测试与统计口径

最终返回机制测试：**66 个源码场景，201/201 检查符合预期**，另有 **15/15** 输入结构/源码定位边界检查。原 R01 **41/41**、原 R02 **110/110** 保持通过。201 是期望符合数，不是 201 条成功传播；9 个明确错误候选均为 REJECT（错误上下文、终止 caller、按值参数写回、丢返回路径、错误/旧版本和类型）。UNKNOWN 不计成功。

66 场景由清单 65 场景加不同 caller 的 1 个场景构成；后者含两次 caller 分析。下表关系统计覆盖 **67 次场景分析**，不累加重复解析、数据位置隔离检查或任何开发轮次。参数入口、caller 接收、类型和忽略结果以 PathReturn 对应的 transfer 为单位；返回绑定以非 void ReturnValueRecord 为单位；效果/路径完整性/完整调用以调用上下文为单位。分母不同，不能横向当作同一成功率。

| 指标 | PASS | REJECT | UNKNOWN | N/A |
| --- | ---: | ---: | ---: | ---: |
| 合成源码场景 | 29 | 0 | 36 | 1 |
| argument_entry | 53 | 0 | 4 | 6 |
| return_binding | 37 | 0 | 5 | 0 |
| caller_result | 33 | 0 | 23 | 7 |
| call_effect_coverage | 37 | 0 | 21 | 0 |
| return_path_completeness | 37 | 0 | 21 | 0 |
| complete_call | 36 | 0 | 22 | 0 |
| ignored_results | 2 | 0 | 0 | 0 |
| void_returns | 5 | 0 | 0 | 0 |
| type_compatibility | 54 | 0 | 2 | 7 |
| 调用上下文隔离 | 58 | 0 | 0 | 0 |
| 历史样本 | 0 | 0 | 4 | 0 |
| 固定20样本 | 0 | 0 | 20 | 0 |

局部返回绑定 PASS/全部记录为 37/42；caller 接收项 PASS/全部请求（包括不适用）为 33/63，接收适用项为 33/56；完整受限调用为 36/58。它们均来自合成输入。未知或不适用项没有并入 PASS。调用上下文隔离已检查 58 个实例、50 个实际入口版本；按值形参重新赋值的整数/指针场景均保留 caller 原参数版本。两返回路径、提前返回和 void 路径单独保存；遗漏真实返回路径的候选 REJECT。未知效果负向场景阻断断言全部符合预期，其源码整体结论仍为 UNKNOWN。

输入边界的 15 项包含 8 个应停止的损坏结构、显式空 frames、经过来源合同验证的 null context，以及 5 项源码定位语义边界。结构错误是操作停止，不伪装成语义 REJECT/UNKNOWN。其语义观察四分类为 PASS 4、REJECT 0、UNKNOWN 1、N/A 0；其余 10 项结构结果单列于 metrics.json。

## 历史风险：4 UNKNOWN

OpenSSL `make_ocsp_response → OCSP_copy_nonce → OCSP_BASICRESP_add_ext`：第112行独立调用未接收结果；第二帧第8–9行原文保存条件及常量2，第11行嵌套调用返回未解析；第三帧成员取址作为潜在间接修改缺口保存。所有定位记录为 literal_source_locator_only/UNKNOWN，没有验证类型、路径可满足性、入口或返回版本。没有虚构 caller 接收版本，没有把 callee 早退当作 caller 退出，没有向 caller 后续条件传播返回 guard，也没有完成三帧路径组合。

A01 原 E01 copied 极性冲突、A04 object/object_ptr/object_bv 与 B/Δ 风险、E04-ND 成员替换及 skb_prev/后续 skb 风险，均保留原诊断文件哈希及准确源码定位。R03 没有重算或修复原 SMT/极性/成员诊断，未将旧 skb 绑定到后续新 skb。四个样本共7份保存函数体，全部因原始构建/TU/类型或效果证据不足保持 UNKNOWN。

## 冻结与原固定20单次执行

候选冻结时间 `2026-11-02T06:57:39.770804+00:00`；manifest SHA-256 `2cbc99af6e23e44141bb112599b22589657f53183c5a2affff4785c76ad48bb6`。冻结 5447 份源码/依赖引用/输入/证据，并独立冻结 Python、libclang DLL 和绑定文件哈希。libclang 18.1.1 的 native DLL 与 R01 原环境哈希一致，未安装或升级依赖。

冻结后原固定20仅执行一次，**20/20 完成，异常 0**；状态 PASS 0、REJECT 0、UNKNOWN 20、N/A 0。保持原顺序与全部20条，共 23 份保存函数体、5 条保存相邻边；没有重抽、删 UNKNOWN、拼接 R02 结果或补齐 TU。已接触回归集，**不是盲测**。固定集耗时约 6.243 秒，仅为本机离线证据检查耗时。

固定20和四个历史案例的可靠完整调用传播覆盖率仍为 **0%**。原始构建证据不足时即 UNKNOWN，包括单帧和缺上下文样本；不将无对应返回关系的历史片段当成受控空函数 N/A。没有真实缺陷保留率、误删率或误报过滤率测量。

固定 manifest SHA-256 `c4ef793abe5f00437f52c27b6fe545dfa613ed661eb441362e1315f1ed98243d`；审计10 manifest SHA-256 `6980a64dd1d499188ccc83002bfdf3255196f1c17e462eaab44d83db67aa366b`。

## 保护、调用及发布边界

4,999 份原有非凭据文件及预算账本保持字节不变，目录外新增为0；冻结候选和相关依赖哈希检查通过。E01–E05、R01/RF、R02、Engine、原 Prompt、U02/U06/U10、MCP、安全v1及数据均未修改。没有读取或输出凭据。Python audit 防护无越界记录；它不是 OS 沙箱。

模型/Harness/Z3 调用、新 SMT、Token、费用、历史/模型生成脚本执行和 C 程序执行均为 **0**。运行的是本目录受控离线 Python 分析与测试，不是“没有执行代码”。没有告警过滤、没有安全裁决接口。

开发记录原样留存：development_01 的分类计数遗漏已在冻结前修正；final_candidate_01 的入口指标和附加场景聚合已在冻结前收紧。最终只采用 final_candidate_02；没有冻结后修补或重跑固定20。见 development_notes.md。

验收检查详见 acceptance_check.json。发布仅复制本目录到独立克隆，核对差异后提交、推送 main；Git commit 本身提供发布身份，报告不事后改写自引用提交号。**R03 到此停止，未进入 R04/R05。** 局部 PASS、结构保留或未来 UNSAT 均不授权 FILTER。

## 发布前补充审查

冻结后对代码审查提出的 VLA 形参界限副作用风险，另存1个合成输入核查。实际结果 UNKNOWN，R01 的类型转换门槛在建立 callee 状态前阻断；未发现该输入上的错误 PASS。源码、AST及解析输出位于 post_freeze_review/，resolution.json 区分最初假设与实际观察。此补充检查不并入冻结的66场景/201项统计；没有修改冻结代码或重跑固定20。
