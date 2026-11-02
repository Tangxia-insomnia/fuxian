# E06-R01：直接调用与入口实参/形参映射实验报告

日期：2026-11-02。**最终状态：候选未通过完整验收，已停止，未提交/推送。**

已有 libclang 环境验证通过；独立 AST 模块及八类合成场景已实现，最终合成断言 41/41 符合预期；三个历史案例均 UNKNOWN。冻结后的固定 20 条首次检查在第 13 条出现运行器异常，因此没有完成整轮验收。没有修改冻结代码、没有补跑剩余样本，也没有进入 R02。

## 1. 目标、授权与基线

本轮只实现独立、确定性的直接调用入口传值证据层。不实现 SSA、返回值/指针写/副作用/路径传播，不接入生产 Engine，不更改安全策略。

- E06 设计/起始 publication main：`82f01f772c45d8216e41194055f076e4fe9d9945`。
- E05：`6452442e492293f42b6b0cf4930dca6685d0c6d7`。
- 原官方冻结提交：`4efb4b9bf7e845e180451b43ba29a25e3edaa0e3`。
- 开始前 publication 工作区干净；E06_design 及 E05 输出哈希清单全部核对，设计的前序 4,456 份保护文件也全部核对。
- 本轮起始保护基线为 4,468 份非凭据文件，详见 `baseline_state.json`。
- 所有新增材料都在本独立目录。没有读取/输出密钥，没有安装/升级依赖。

审计 10 条 manifest SHA-256：`6980a64dd1d499188ccc83002bfdf3255196f1c17e462eaab44d83db67aa366b`。

固定 20 条 manifest SHA-256：`c4ef793abe5f00437f52c27b6fe545dfa613ed661eb441362e1315f1ed98243d`。顺序、身份及样本未修改；这是已接触的回归集，不是盲测。

## 2. libclang 先行环境门槛：PASS

先执行 `environment_probe.py`，成功后才开发 mapper。

- 实际环境：Windows 10.0.26200，Python 3.11.5，libclang Python 包 18.1.1。
- 实际加载已有 `clang/native/libclang.dll`，库 SHA-256：`b13ec96d9a036d6c6c36dd09e00415ead7acc7fcfd40e721bf33ea86b3490f9d`。
- 自包含 `environment/probe.c` 成功识别 CallExpr、FunctionDecl、ParmDecl、DeclRefExpr、声明引用、类型和源码位置；没有诊断。
- 相同输入解析两次，排除时间因素的语义输出逐项一致。
- `environment/diagnostic_probe.c` 的语法错误真实返回 severity=3、`expected expression`、第 1 行第 30 列；这些恢复节点未被用作语义证据。
- 原始 C、输入哈希、两次完整节点输出及诊断保存在 `environment/result.json`。

环境探针没有编译/执行 C。本机平台元信息收集与离线 AST 加载不等于启动外部 Clang 工具链或恢复历史项目构建。

## 3. 已实现的独立模块

| 文件/位置 | 实际能力 |
| --- | --- |
| `mapper.py:49` declaration | USR、canonical 声明位置、源范围/链接身份与源/构建命名空间 |
| `mapper.py:60` type_info | canonical 类型、大小、限定符、pointee/record 声明证据 |
| `mapper.py:80` conversion | 受限类型相容和可证明转换检查 |
| `mapper.py:123` parse | 固定字节快照解析、详细预处理记录及诊断；显式加载已验证现有 DLL |
| `mapper.py:144` identifier_reference | AST 绑定的标识符实参，拒绝复杂成员/显式 cast 等 |
| `mapper.py:165` analyze | 唯一直接 callee、CallExpr/参数序号、slot 与 transfer 证据 |
| `mapper.py:301` verify_proposal | 对候选序号/slot/转换的确定性冲突检查 |
| `test_mapper.py` | 八类合成测试及不变量 |
| `run_regression.py` | 历史源码复制/保护/回归记录适配；null 上下文处理有缺陷，未获整体验收 |
| `offline_boundary.py` | 测试进程的网络/子进程 Python audit 防护；非 OS 沙箱 |

精确合同见 `mapping_contract.md`。没有修改或调用原 MCP/Engine/Prompt，没有生成 SMT 关系。

## 4. AST 识别与批准边界

CallExpr 必须引用唯一 FunctionDecl，实际书写为普通函数名调用，同 TU 存在唯一可见定义，实参和形参个数一致。额外定义候选 TU 只用于否定唯一性，不能为主 TU 自动补定义。

只支持自包含、无预处理、无相关诊断的合成 C 环境。宏、函数指针/回调、定义歧义、varargs、缺定义、未知构建都 UNKNOWN。warning/error 阻断语义批准，错误恢复 AST 不提供已验证映射。

位置采用 UTF-8 字节范围及一基行/列；保留完整调用原文、源码与函数哈希、diagnostics 引用。历史源码按原始 frame 分别解析，没有把多个片段拼成伪造的完整 TU。

## 5. 参数、类型与身份

实参和形参按 CallExpr 参数序号对应，不按名称对应。每条关系记录 dataset_id、position、callsite、实际表达式、声明身份、两端类型、AST 转换后类型、转换种类和源码证据。

caller-slot 与 callee-slot 始终分离；入口值关系单独使用 transfer_id。`f(p,p)` 保留两个参数序号、两个独立形参 slot 和两条 transfer。同名不同函数/嵌套作用域的实参以不同声明位置区分。形参 slot 是词法声明，跨调用点的入口关系由 callsite/transfer 隔离；本轮没有动态调用实例或值版本模型。

已测试类型包括基本标量、单层标量指针、同一声明身份的 struct 指针；转换包括 identity、带符号整数严格拓宽及 pointee const 添加。void* 转换、复杂 casts、多级指针、volatile/restrict、聚合体按值等不批准。没有默认类型或自动补 cast。

这里的入口值相等不证明指针对象身份、可达性、状态保持、别名或对象存活。不能导出跨函数路径结论。

## 6. 合成测试：最终 41/41

最终结果：`synthetic_runs/attempt_05_freeze_candidate/test_results.json`，运行时间约 **0.446 秒**。八类必需场景及输入 C/SHA-256 都有逐项记录。

| 场景 | 实际结果 |
| --- | --- |
| M01 正常直接调用 | PASS；另验证 struct 指针、带符号拓宽、const 添加，caller/formal slot 分离 |
| M02 两个不同类型参数交换序号 | 正确 AST 参考关系 PASS；错误序号候选 REJECT |
| M03 同名不同函数/作用域 | 三个实参 slot 不合并；错误作用域候选 REJECT |
| M04 `f(p,p)` | 两个独立形参/transfer；强行合并候选 REJECT |
| M05 错转换/缺证据 | 窄化、显式 cast、错误指针、void*、不同 struct 声明 UNKNOWN；虚假转换候选 REJECT；缺证据 UNKNOWN |
| M06 缺定义/多定义 | UNKNOWN；两个独立、干净解析的定义候选被记录为歧义 |
| M07 指针/回调/宏 | UNKNOWN；宏展开证据保留，未批准映射 |
| M08 聚合体/成员/取址 | UNKNOWN |

附加断言验证输入校验、无构建证据的强制 UNKNOWN、重复解析一致性、恢复 AST 不批准及精确转换种类。这里“测试通过”指正负例都符合预期，绝不是 41 个 PASS 调用或真实漏洞验证。

开发中两次启动失败已保留：attempt_01 的保护器拦截本机 gethostname，attempt_02 拦截 Python platform 的 Windows 版本 shell fallback，均在首个 mapper AST 分析前停止，没有启动所拦截进程。随后以现有安装目录明确指定 DLL，保留子进程禁止规则。attempt_03/04 为较早 35/35；未将多次运行累加为最终测试数。

## 7. 历史案例：3 UNKNOWN，0 获批映射

详细来源/哈希/诊断见 `historical_report.md`、`historical/results.json` 和对应 frame 输出。

1. `NPD/codeql/kernel69:row=24:index=43`：第 77 行 `sock_confirm_neigh(skb, neigh)`，下一帧第 8 行 `neigh_confirm(n)`；三帧诊断 78/9/6。
2. `NPD/codeql/libav:row=51:index=84`：第 119/122 行两次 read_index；两帧诊断 148/15。
3. A04 `NPD/codeql/kernel69:row=12:index=24`：第 34 行 `kfree(saved_clone)`；两帧诊断 22/13；char*→const void* 不在首轮批准范围。

三个样本均 `saved-source-only`，缺少原始构建/完整 TU/可核验类型身份。4 对相邻帧、5 个字面调用候选不等于 5 条 AST 传播验证。没有补头文件、宏、typedef，也未篡改旧 B/Δ 或模型输出。

## 8. 冻结与固定 20 条首次运行：失败停止

合成测试、历史检查完成后冻结，`freeze_manifest.json` SHA-256：`15c583c0bc879f214eb7dfcc07813157d33740db4871548208b2aebbd4977990`。清单包含 29 份代码/配置/输入、30 份历史输入和 86 份已完成证据。运行前固定集检查次数为 0，运行后为 1。

固定集运行在 `2026-11-02T05:27:53.362046+00:00` 开始。第 13 条历史 bundle 的 context 为 null；`run_regression.py:66` 执行 `bundle['context']['frames']`，触发 **TypeError: 'NoneType' object is not subscriptable**。空 frames 分支存在，但没有覆盖 null context，这属于本轮适配器错误。

| 执行口径 | 数量 |
| --- | ---: |
| 原始固定样本总数 | 20 |
| 完成离线检查记录 | 12 |
| 完成记录：PASS / REJECT / UNKNOWN | 0 / 0 / 2 |
| 完成记录：NOT_APPLICABLE（单帧无请求跨帧对） | 10 |
| 第 13 条运行器异常，未形成静态结果 | 1 |
| 第 14–20 条未执行 | 7 |

`fixed_20/results.json` 保留全部 20 条原身份与顺序。若按报告容器分类，是 UNKNOWN 10、NOT_APPLICABLE 10，其中 **8 条 UNKNOWN 是运行失败/未执行造成的证据缺口，不是已完成的静态结论**。不能写成“20 条均已验证”。

完成记录里 12 条缺原始构建证据；2 条多帧类型身份未验证，10 条单帧类型检查未请求。该次完成记录中缺源码数为 0；设计冻结清单早已记录全部 20 条有 2 条无帧，但不能将此先验统计说成本次检查成功处理了空上下文。

完成记录覆盖 3 对相邻帧、4 个字面候选调用点，批准映射 0。记录完成率 12/20=60%；语义 PASS 数为 0。完成记录耗时合计约 0.216 秒；失败命令整体 wall time 为工具返回约 1.336 秒。全部原 20 条未删除、替换或重新抽样。

发现冻结候选问题后立即停止。未调整 checker/adapter、未重跑固定集，未单独补跑后 7 条；报告汇集既有文件/设计身份，不执行新样本检查。

## 9. 已验证、未验证与剩余风险

- **已实现**：局部调用/声明/类型/入口参数关系模块及独立测试，未生产集成。
- **已测试**：环境真实加载、合成八类场景及附加不变量、三个指定历史案例、固定集前 12 条记录。
- **已验证**：本轮最终 41 项合成断言符合预期、历史证据不足未被晋升 PASS、冻结与历史文件保护。
- **尚未验证**：完整固定 20 条的稳定运行、任何真实历史传播 PASS、真实构建/复杂转换/宏、赋值状态/别名/副作用/路径。

额外静态范围风险：类型代码以 Clang RECORD 类别处理 pointee，没有显式收紧为 StructDecl；只测试了 struct，**union 指针边界尚未验证**，不能宣称支持，也未在冻结后补测/修改。此项应在下一候选先明确收紧或单独审定。

合成构建的默认目标是当前宿主环境，未证明其他平台可重现；没有尝试跨 TU 正向链接。词法 slot/入口 transfer 不是完整变量版本或动态调用实例。纯局部 PASS 不向安全层传递任何过滤权限。

## 10. 保护结果：PASS，不替代功能验收

`preservation_check.json` 已实际核对：

- 原有 4,468 份非凭据文件无修改/丢失；本目录外无越权新增。
- 29 份冻结代码/配置/输入、30 份历史输入、86 份已完成证据哈希全部不变。
- 预算账本前后 SHA-256 均为 `41c8081ff9cc7f8953cfd5eb833b5b7fd6ee31d1675099e232764382ca082c36`，字节不变。
- publication 与 upstream 工作区均干净；E06_design、E05、E01–E04、Prompt、MCP、engine、constraint_bundle 和安全 v1 均未修改。
- 排除范围同原基线：.git、.venv、__pycache__、node_modules、.env*；没有读取/发布凭据内容。

## 11. Git 状态与停止决定

用户要求“**只有全部验收和保护检查通过后，才按项目既有流程提交并推送 main**”。本轮保护通过，但固定回归没有完成，因此不满足条件。

没有创建 R01 commit、没有复制到 publication clone、没有 stage、没有 push、没有改写历史。Git main 仍为 `82f01f772c45d8216e41194055f076e4fe9d9945`。本轮报告和全部失败/成功材料留在本地独立目录。不存在可提供的新 GitHub 报告链接。

## 12. 调用、费用与执行统计

| 项目 | 实际数量 |
| --- | ---: |
| LLM 请求 / Token | 0 / 0 |
| 模型 API 费用 | 0 元 |
| Z3 调用 | 0 |
| Harness 启动 | 0 |
| C 编译 / C 程序执行 | 0 / 0 |
| 模型/历史生成代码执行 | 0 |

执行的是本轮人工编写的环境探针、AST 检查器和测试 Python；不是“没有执行任何代码”。旧审计里的求解输出没有作为本轮求解结果使用。没有告警裁决，真实缺陷保留率/误删率/误报过滤率均未测。

## 13. 下一步最小建议（未执行）

保持本目录和冻结代码原样。下一候选仍属于 R01，先单独修正**历史适配器证据结构校验**：区分 context 缺失/null、非 object、frames 缺失/非 list/空 list、损坏 frame/code/hash；缺证据输出 UNKNOWN，不能补空代码或猜类型。把这些结构边界加入独立合成 fixture，检查既有 41 项不回归，再冻结新的候选。

同时明确 RECORD 的 struct-only 首轮边界。此为范围收紧准备，不引入 SSA/别名等 R02–R05 功能。固定 20 已接触且本轮失败，未来再检查必须明确标注新候选和重复回归，不能继续冒充本轮一次性独立验证。

本阶段到此停止，等待下一步指令；不自动修复运行器、不进入 R02。
