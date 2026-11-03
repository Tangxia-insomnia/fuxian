# 原论文数据集清点与字段说明

审计日期：2026-11-03。只读内容审计，不运行分析器、测试、模型或求解器。冻结官方仓库 `E:/codexconversation/课题研究/reproduction/upstream` 的 HEAD 为 `4efb4b9bf7e845e180451b43ba29a25e3edaa0e3`；发布克隆 HEAD 为 `fb8e98e0771304ef97682a57f5fcf4969abb216b`，开始工作区干净。前者是论文实现仓库提交，不能作为 Linux/OpenSSL/Libav 的扫描源码提交。

## 1. 找到了什么“完整数据集”

官方 README 将 benchmark 称为 SAFP-Bench-C，声称 443 条告警、47 真缺陷、396 误报，项目版本为 Linux v6.9.6、OpenSSL v3.4.0、Libav v12.3。定位依据为 `E:/codexconversation/课题研究/reproduction/upstream/README.md` 及实际查看的 `Data statistics.jpg`。这属于论文/作者公布口径。

本轮完整解析冻结 benchmark 目录的 **14 个 JSON**；它们均为顶层数组，共 **1,017 条保存记录**。UBI 与 UUA 文件 SHA 完全相同，若仅将这一个文件级重复视为别名，剩 **954 条记录出现**：`result=0:385`、`result=1:39`、`result=-1:4`、缺 result 526。因此共有 **424 条带原始二元标签的记录出现**。954 和424都不是经过告警身份去重后的样本数量，不冒称官方443条的精确替代集。

无法在冻结材料中确认一个行级 manifest，能把正式443条告警及47个真缺陷无歧义地定位到这些JSON。当前找齐的是**公开冻结目录的全部文件**，不是已核验的全部论文实验输入/标签/构建证据。没有重新抽样、删数据或更改标签。

| benchmark 相对路径 | 记录 | result=0 | result=1 | result=-1 | 缺 result |
|---|---:|---:|---:|---:|---:|
| `BOF/codeql_openssl_cwe122.json` | 42 | 42 | 0 | 0 | 0 |
| `DBZ/all_cwe369.json` | 16 | 14 | 2 | 0 | 0 |
| `NPD/codeql/codeql_kernel69_nullpointer.json` | 70 | 48 | 22 | 0 | 0 |
| `NPD/codeql/codeql_libav_nullpointer.json` | 57 | 55 | 2 | 0 | 0 |
| `NPD/codeql/codeql_openssl_nullpointer.json` | 50 | 41 | 8 | 1 | 0 |
| `NPD/cppcheck/cppcheck_libav_nullpointer.json` | 10 | 8 | 2 | 0 | 0 |
| `NPD/cppcheck/cppcheck_linux_nullpointer.json` | 594 | 65 | 0 | 3 | 526 |
| `NPD/cppcheck/cppcheck_openssl_nullpointer.json` | 5 | 5 | 0 | 0 | 0 |
| `NPD/infer/infer_libav_nullpointer.json` | 6 | 6 | 0 | 0 | 0 |
| `NPD/infer/infer_openssl_nullpointer.json` | 16 | 13 | 3 | 0 | 0 |
| `UAF/codeql_kernel69_cwe416.json` | 16 | 16 | 0 | 0 | 0 |
| `UAF/codeql_openssl_cwe416.json` | 9 | 9 | 0 | 0 | 0 |
| `UBI/all_cwe457.json` | 63 | 63 | 0 | 0 | 0 |
| `UUA/all_cwe457.json` | 63 | 63 | 0 | 0 | 0 |

关键口径差异：

- `NPD/cppcheck/cppcheck_linux_nullpointer.json` 有594条，只有零基行0–67带 result；其中65个0、3个-1，**没有 result=1**，其他526行未标注。作者统计图为83(8)，官方 NPD metrics 为68条、real_bug_num=3。不能把-1改成1，也不能默认前83条即原正式集；前83条仍有15个缺标签。该文件还存在9条完全相同JSON记录的重复出现，本轮只记录，不删除。
- `NPD/codeql/codeql_openssl_nullpointer.json` 为50条：41个0、8个1、1个-1；-1在零基行24、index25、next_protos_parse。图中50(8)，metrics却写real_bug_num=9。均保留来源，不重标注。
- 统计图的 Infer NPD 项目格为16与6，但行Total印为24；本地实数22。图的数值也不能自动修复输入。
- DBZ为16行，但原index为0–10、12–16，缺11，不能用index作数组下标；其他分组也存在行号/index差异。
- 没有 BAD/GOOD 成对测试；实际标签是 result。NPD 0/1与旧项目的误报/真实缺陷解释、部分官方组级metrics相符，但不是独立人工复标；其他类型沿用作者字段而不推断更强可信度。-1与缺标签不得参与二元准确率分母，必须单列。

## 2. 实际结构与含义

所有14文件都有 `location.file_path`、`region.startLine/startColumn/endColumn`、`context.startLine/endLine/snippet.text`。全量记录的startLine均为整数，但这是保存的元数据，未据原工程核验。region没有endLine字段；不能将context起点或告警变量位置直接当成整段函数的坐标起点。

| 形态 | 实际内容和可用价值 | 不能声称 |
|---|---|---|
| NPD/UAF/BOF | var_name、function_name、function_code；Infer Libav用func_info保存代码 | 函数名不是声明ID；代码片段不是完整TU |
| DBZ/UBI/UUA | prt、function_call、source、sink/final_sink、baseline_context | 全部16条DBZ和63条UBI的function_call长度实际都是1，字段名称不证明调用链 |
| baseline_context | text数组中的file_path/function_body，部分为带显示行号的函数/宏文本 | 没有原include图、宏选择和构建绑定；可能含多个同名min等候选，不可任选一个当活动定义 |
| kernel CodeQL 条件扩展 | bug_line_constraints:70项；var_assign_conditions:30项；pointer_null_postconditions:17项；early_jump_constraints:307项 | 这是C/控制流文本；没有每项可靠极性、CFG支配关系、声明/版本ID |
| BOF bug_report | 42条自然语言告警解释，如数组负下标报告 | 不是类型化约束，也不是原查询/rule ID |
| explain、source_not_null、define_in_function_body、loop_assign | 少量注记/整数标记，实际分布见下方 | 注记不等于已证明函数效果、非空前提或路径执行 |

条件扩展的condition元素实际为字符串，可含 if、while、goto 等，不能假设全部是可直接求解的布尔式。function_list也只是保存名称列表。UBI.source在61行是list、2行是str，必须保留原类型再适配；不能无条件拼接。

警告类型/分析器的分组可结合统计图、文件来源及实际告警内容登记，但**所有原记录都没有 checker/rule_id/ruleId/message 等规范字段**；DBZ/UBI混合项目/工具的逐条扫描规则身份未给出。应使用“作者声明分组/未认证”来源，不能仅按目录名构造已认证rule ID。

没有原扫描数据库、完整SARIF codeFlow、原工程Git commit、compile_commands、生成配置或typed ValueVersion/MemoryVersion字段。已有源码具有重要文本研究价值，但不能认定全是完整函数：例如 CodeQL Libav零基行39的get_video_buffer片段缺结束大括号；字符串括号计数只提示进一步审查，不能作为C解析判决。

## 3. 相关文件分层

官方冻结目录实际有70份结果JSON：

- `upstream/results/llmpfa_result`：32份NPD聚合metrics，实际含accuracy、true/false counts、real_bug_num、total_num、failed_num。不是逐条程序语义证据，文件中没有原始B/Δ或原模型请求链。
- `upstream/results/llmdfa_result`：30份prop/vali JSON（含.old/.time副本），保存index、output解释、result、少量error。这里result是方法输出，不是benchmark标签。Libav CodeQL结果有61行而benchmark57，DBZ结果17行而benchmark16；禁止按同一数组下标直接join。
- `upstream/results/llmsa_result`：8份baseline结果，内有模型解释/判断。不能将baseline预测作ground truth或确定性约束。

官方流水线 `upstream/llm4pfa/feasibility_analysis_pipeline.py:15` 起引用原context/constraints/function-cache等外部路径，但其依赖与完整缓存没有出现在冻结目录。读取代码可确认预期契约，不能当作已提供数据。

本地另有后来的恢复材料 `safety_runs/20261029_build_search_repair_plan/search/restore_branch/llm4pfa/data/linux-codeql-npd/{context,constraints}.json`，各70条：context字段为prt/function_call/sink/final_sink/source/index；constraints包括bug_line_constraints、target_conditions、variable_assignments、variable_non_empty、early_jump_constraints、filter_function_code、code_snippet、var_name、loc_text。它们是**后续公开恢复候选**，不是冻结提交中的原扫描认证材料；配置明确标为identity-aligned-candidate。例如所选E07样本原index43而恢复context行24的index44，名称/文本吻合仍不能只按index绑定。恢复constraints里的variable_assignments还可能只是函数签名。

项目补全/实验结果包括：

| 层次 | 本地来源 | 实际用途与边界 |
|---|---|---|
| 项目模型实验快照 | results/raw/completed下的context/calls/solver等 | 可保留调用原文与来源；模型结论不变成AST事实 |
| E02保存包 | safety_runs/E02_base_constraint_preservation_static/evidence | 实际50份bundle：audit_10、audit_10_candidate_v1、audit_10_frozen_candidate各10，fixed_20_frozen_candidate20；包含重复阶段快照，不是50个独立样本 |
| E03 B/Δ | completion/constraint_bundle.py及safety_runs/E03_base_delta_explicit_transfer_fix/engine_traces | raw/code/hash/合并区间及结构来源可复用；非官方原始typed语义约束 |
| R01 RF | safety_runs/E06_R01_runner_fix/{historical,fixed_20}/results.json | 保存调用点候选，历史3 UNKNOWN；fixed20为5 UNKNOWN、15 N/A，批准映射0 |
| R02 | safety_runs/E06_R02_local_value_versions/{historical,fixed_20}/results.json | 历史3 UNKNOWN；fixed20全部UNKNOWN，版本/读取批准0 |
| R03/R04 | safety_runs/E06_R03_return_value_transfer与E06_R04_restricted_indirect_write | 各历史4及fixed20全部UNKNOWN，无可靠返回/写入传播；它们不是完整benchmark全量结果 |
| R05初轮与扩展 | safety_runs/E06_R05_cross_frame_ledger/reports/R05_historical_audit.json、R05_extended_metrics.json | 历史30 UNKNOWN，完整/部分已验证路径0；初轮结构validator的PASS可能伴随ledger_program_status=UNKNOWN，不代表程序PASS |
| E07/E08 | safety_runs/E07_real_evidence_extraction、E08_compile_context_precheck | 单样本来源提取/编译上下文预检均未形成完整真实跨帧证据；当前R05非fixture准入保持UNKNOWN |

R05_interface_audit.md是实施前历史审计，不能用其中“尚未实现”概括当前扩展功能。当前依据为src/protocol/evidence_runtime.py及protocol/execution_v2_spec.md：已有MemoryVersion→ValueVersion桥和嵌套组合，但输入生产与C语义认证没有自动完成。

## 4. 全量原字段清单

“非空内容数”按JSON值的布尔非空统计；result=0和index=0的0只是数值，不能将该列当成缺失计数。所有路径均相对 `E:/codexconversation/课题研究/reproduction/upstream/benchmark`。

### BOF/codeql_openssl_cwe122.json

SHA-256：`60cfaccbc67034b168a407b47148bef246b4ec775ed6c93fcdf81c506748b625`；163222 字节。所有记录已用 JSON 解析检查。

| 原字段 | 出现数 | 实际类型 | 非空内容数 |
|---|---:|---|---:|
| `var_name` | 42 | str:42 | 42 |
| `function_name` | 42 | str:42 | 42 |
| `location` | 42 | dict:42 | 42 |
| `function_code` | 42 | str:42 | 42 |
| `result` | 42 | int:42 | 0 |
| `bug_report` | 42 | str:42 | 42 |

### DBZ/all_cwe369.json

SHA-256：`0275cd83a4c1cf617f0049d6dbb191dcc3d232e5545ca0139bab3aa45f747fd8`；334081 字节。所有记录已用 JSON 解析检查。

| 原字段 | 出现数 | 实际类型 | 非空内容数 |
|---|---:|---|---:|
| `prt` | 16 | str:16 | 16 |
| `function_call` | 16 | list:16 | 16 |
| `source` | 16 | list:16 | 16 |
| `index` | 16 | int:16 | 15 |
| `location` | 16 | dict:16 | 16 |
| `result` | 16 | int:16 | 2 |
| `baseline_context` | 16 | list:16 | 16 |
| `sink` | 16 | str:16 | 16 |
| `final_sink` | 16 | str:16 | 16 |

### NPD/codeql/codeql_kernel69_nullpointer.json

SHA-256：`5385ae52f09cc927dbc5e29f17229ccaaa68467e1614cbf73d219fd1f46713a3`；427983 字节。所有记录已用 JSON 解析检查。

| 原字段 | 出现数 | 实际类型 | 非空内容数 |
|---|---:|---|---:|
| `var_name` | 70 | str:70 | 70 |
| `function_name` | 70 | str:70 | 70 |
| `location` | 70 | dict:70 | 70 |
| `function_code` | 70 | str:70 | 70 |
| `result` | 70 | int:70 | 22 |
| `bug_line_constraints` | 70 | list:70 | 70 |
| `var_assign_conditions` | 70 | list:70 | 29 |
| `pointer_null_postconditions` | 70 | list:70 | 16 |
| `early_jump_constraints` | 70 | list:70 | 60 |
| `index` | 70 | int:70 | 69 |
| `function_list` | 45 | list:45 | 45 |
| `explain` | 5 | str:5 | 5 |

### NPD/codeql/codeql_libav_nullpointer.json

SHA-256：`a5683aa98e8a50efbb430913b25b65528076dfc6e81de6c4bb1fac6bb6a86ed2`；299900 字节。所有记录已用 JSON 解析检查。

| 原字段 | 出现数 | 实际类型 | 非空内容数 |
|---|---:|---|---:|
| `var_name` | 57 | str:57 | 57 |
| `function_name` | 57 | str:57 | 57 |
| `location` | 57 | dict:57 | 57 |
| `function_code` | 57 | str:57 | 57 |
| `result` | 57 | int:57 | 2 |
| `index` | 57 | int:57 | 57 |
| `source_not_null` | 3 | int:3 | 3 |
| `function_list` | 1 | list:1 | 1 |

### NPD/codeql/codeql_openssl_nullpointer.json

SHA-256：`4664bb6b80e8a18ab2e19b1489c4ca9ce7fb4f2c720dd0f402d1762356112882`；1175473 字节。所有记录已用 JSON 解析检查。

| 原字段 | 出现数 | 实际类型 | 非空内容数 |
|---|---:|---|---:|
| `var_name` | 50 | str:50 | 50 |
| `function_name` | 50 | str:50 | 50 |
| `location` | 50 | dict:50 | 50 |
| `function_code` | 50 | str:50 | 50 |
| `result` | 50 | int:50 | 9 |
| `index` | 50 | int:50 | 49 |
| `function_list` | 4 | list:4 | 4 |
| `explain` | 4 | str:4 | 4 |

### NPD/cppcheck/cppcheck_libav_nullpointer.json

SHA-256：`1f6c2d513b5ac6b8d5910b9b82e3eeb96a6701ca8d84f0b9dd90077e2564c347`；33833 字节。所有记录已用 JSON 解析检查。

| 原字段 | 出现数 | 实际类型 | 非空内容数 |
|---|---:|---|---:|
| `var_name` | 10 | str:10 | 10 |
| `function_name` | 10 | str:10 | 10 |
| `location` | 10 | dict:10 | 10 |
| `function_code` | 10 | str:10 | 10 |
| `result` | 10 | int:10 | 2 |
| `define_in_function_body` | 2 | int:2 | 2 |

### NPD/cppcheck/cppcheck_linux_nullpointer.json

SHA-256：`bc1fcdd59756e855c0ee7987e6b788d408a5b0815f207e9f4ef272bf1ca234b6`；1297699 字节。所有记录已用 JSON 解析检查。

| 原字段 | 出现数 | 实际类型 | 非空内容数 |
|---|---:|---|---:|
| `var_name` | 594 | str:551, NoneType:43 | 551 |
| `function_name` | 594 | str:594 | 594 |
| `location` | 594 | dict:594 | 594 |
| `function_code` | 594 | str:594 | 594 |
| `result` | 68 | int:68 | 3 |
| `loop_assign` | 17 | int:17 | 17 |

### NPD/cppcheck/cppcheck_openssl_nullpointer.json

SHA-256：`5a7e89ffb017ece94403f862a5cc8d33f478fc92360d4e957648d66aeee12d29`；157455 字节。所有记录已用 JSON 解析检查。

| 原字段 | 出现数 | 实际类型 | 非空内容数 |
|---|---:|---|---:|
| `var_name` | 5 | str:5 | 5 |
| `function_name` | 5 | str:5 | 5 |
| `location` | 5 | dict:5 | 5 |
| `function_code` | 5 | str:5 | 5 |
| `result` | 5 | int:5 | 0 |

### NPD/infer/infer_libav_nullpointer.json

SHA-256：`ed2233c572c81fd05b1407951babe48dccc0a5dc6b59b412ad2705874ab83126`；21586 字节。所有记录已用 JSON 解析检查。

| 原字段 | 出现数 | 实际类型 | 非空内容数 |
|---|---:|---|---:|
| `var_name` | 6 | str:6 | 6 |
| `function_name` | 6 | str:6 | 6 |
| `location` | 6 | dict:6 | 6 |
| `func_info` | 6 | str:6 | 6 |
| `result` | 6 | int:6 | 0 |

### NPD/infer/infer_openssl_nullpointer.json

SHA-256：`8d0828a40f04ede896e19f0fb993e3d5f70c23556208275d913b5a1d6a3cb0d2`；58027 字节。所有记录已用 JSON 解析检查。

| 原字段 | 出现数 | 实际类型 | 非空内容数 |
|---|---:|---|---:|
| `var_name` | 16 | str:16 | 16 |
| `function_name` | 16 | str:16 | 16 |
| `location` | 16 | dict:16 | 16 |
| `function_code` | 16 | str:16 | 16 |
| `result` | 16 | int:16 | 3 |

### UAF/codeql_kernel69_cwe416.json

SHA-256：`dd84d448276a8528f198c308cbbaaf6ea334f71bcbe25cf1033e13b4ce2655f9`；52057 字节。所有记录已用 JSON 解析检查。

| 原字段 | 出现数 | 实际类型 | 非空内容数 |
|---|---:|---|---:|
| `var_name` | 16 | str:16 | 16 |
| `function_name` | 16 | str:16 | 16 |
| `location` | 16 | dict:16 | 16 |
| `function_code` | 16 | str:16 | 16 |
| `result` | 16 | int:16 | 0 |

### UAF/codeql_openssl_cwe416.json

SHA-256：`e17ce67a88c9922dea7cfa24c0094676d8c12406f2c066469eb3c789602a7f88`；16659 字节。所有记录已用 JSON 解析检查。

| 原字段 | 出现数 | 实际类型 | 非空内容数 |
|---|---:|---|---:|
| `var_name` | 9 | str:9 | 9 |
| `function_name` | 9 | str:9 | 9 |
| `location` | 9 | dict:9 | 9 |
| `function_code` | 9 | str:9 | 9 |
| `result` | 9 | int:9 | 0 |

### UBI/all_cwe457.json

SHA-256：`c63dc87ccaa1bc71ee2b28d715fe43d600ea8e6c60b7e58ba6a6e36c7ddefbe4`；1203693 字节。所有记录已用 JSON 解析检查。

| 原字段 | 出现数 | 实际类型 | 非空内容数 |
|---|---:|---|---:|
| `prt` | 63 | str:63 | 63 |
| `function_call` | 63 | list:63 | 63 |
| `source` | 63 | list:61, str:2 | 63 |
| `index` | 63 | int:63 | 62 |
| `location` | 63 | dict:63 | 63 |
| `result` | 63 | int:63 | 0 |
| `baseline_context` | 63 | list:63 | 60 |
| `sink` | 63 | str:63 | 63 |
| `final_sink` | 63 | str:63 | 63 |

### UUA/all_cwe457.json

SHA-256：`c63dc87ccaa1bc71ee2b28d715fe43d600ea8e6c60b7e58ba6a6e36c7ddefbe4`；1203693 字节。所有记录已用 JSON 解析检查。

| 原字段 | 出现数 | 实际类型 | 非空内容数 |
|---|---:|---|---:|
| `prt` | 63 | str:63 | 63 |
| `function_call` | 63 | list:63 | 63 |
| `source` | 63 | list:61, str:2 | 63 |
| `index` | 63 | int:63 | 62 |
| `location` | 63 | dict:63 | 63 |
| `result` | 63 | int:63 | 0 |
| `baseline_context` | 63 | list:63 | 60 |
| `sink` | 63 | str:63 | 63 |
| `final_sink` | 63 | str:63 | 63 |


审计只读取原文件与静态代码，不执行其中的C、Python模型脚本或分析器。

