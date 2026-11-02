# E06-R01-RF：固定回归运行器空上下文修复报告

日期：2026-11-02。**结论：运行器修复及原 R01 规定的离线验收通过；新候选从头一次完成 20/20，未修改 R01 核心。**

本轮只修复运行器/必要测试，未进入 R02，没有模型、Harness、Z3、生成代码执行或告警裁决。原 R01 第一次不完整运行全部保留。

## 1. context=null 的真实语义

本项目 bundle 导出器 `safety/replay.py:59` 在没有 `context.json` 时明确写入 null。因此它在**此历史导出格式**中表示“没有保存好的恢复上下文”，不是“样本无需检查”、不是“没有函数源码”，也不是空对象。

两条实际 null 均通过原绑定及来源验证：

| 固定序号 | sample_id | 历史错误 | 本轮状态 |
| --- | --- | --- | --- |
| 13 | NPD/cppcheck/linux:row=13:index=None | Function kvm_for_each_vcpu: 0 distinct available definitions | UNKNOWN，保留原错误 |
| 16 | NPD/codeql/kernel69:row=26:index=45 | Expected one function definition, found 0 | UNKNOWN，保留原错误 |

原 raw sample_result 状态都是 blocked_context；原 context.json 确实不存在；原绑定中的规范 bundle 摘要和文件哈希一致。每条新结果均保存 null_context_provenance，包括原结果路径/hash、导出器路径/hash、缺文件位置和原始错误。

字段缺失没有导出器约定支持；context={} 缺 frames；context=[]、字符串等类型错误，均为数据错误。context={"frames":[]} 是明确空数组，仍按原规则缺证据 UNKNOWN，与 null 保持不同结构状态。完整分析见 [runner_issue_analysis.md](runner_issue_analysis.md)。

## 2. 问题定位与最小修复

旧运行器在第 66 行直接下标 `bundle['context']['frames']`，在原空 frames 分支之前就对 null 抛 TypeError。该错误属于运行器的输入结构遗漏；mapper 接受源码路径，不消费 bundle.context，因此不涉及实参/形参算法。

只在新目录新增运行器副本；原 R01 文件保持不变。实际差异见 [runner_patch.diff](runner_patch.diff)：

- `run_regression.py:30` context_state：区分字段缺失、显式 null、空对象、数组、正常 frames，并验证 frame/code/hash。错误抛 DataShapeError，不能变成 UNKNOWN/N/A。
- `run_regression.py:64` null_context_provenance：仅对显式 null 核对原 exporter/绑定、blocked_context 状态、原错误及缺文件证据；不重新恢复函数、不补代码。
- `run_regression.py:137` check_sample：原正常逻辑前增加结构检查；合法缺上下文保留 UNKNOWN、frame_count=null 和原错误；单帧 N/A、多帧缺构建 UNKNOWN 的规则不变。
- `run_regression.py:206` execute_specs：异常保存类型、消息和完整 traceback，原样重新抛出并停止；不将运行异常映射为 UNKNOWN/N/A。
- 其他差异仅为新目录、冻结清单及第二次独立运行标识/逐样本和统计输出。

没有样本 ID 特判。样本 ID 只用于正常证据绑定，未读取标签作判断。

## 3. R01 核心及配置不变

新运行器直接导入旧目录的原 mapper、配置和离线边界工具，没有复制修改核心。

| 对象 | SHA-256 |
| --- | --- |
| 原 R01 mapper.py | 53101591c9980f06d9cb6717a9905ad806028d6a27541a71bf70c3d216cb140d |
| 原 R01 config.json | 771f89a418283742c2d7a1105261b0060f9bf6c04a6372412a15b7810263b207 |
| 原运行器，完整保留 | d42ea0184fd7daad07da1178b73e38918cc44fb472a27e0469ec1d65e9f6ce3d |
| 新 RF 运行器 | fa109cd9f0efdb9eaded2d499ce48e0bde11b83f00436d3d71ca5484b9c99c2a |

核心和原配置哈希同时与旧 R01 冻结清单核对。原 libclang 加载/类型/位置/重复解析验证仍有完整证据；本轮核心合成复查再次通过。没有改变 PASS/REJECT/UNKNOWN 的映射判定、类型转换或身份规则。

## 4. 新运行器测试：20/20

[runner_tests.json](runner_tests.json) 保存每项原始输入、来源条件、期望、实际结果、是否保持输入不变及异常 traceback；耗时约 0.041 秒。

| 输入/情况 | 预期及实际处理 |
| --- | --- |
| null + 经核验来源 | EXPLICIT_NULL_SAVED_CONTEXT_UNAVAILABLE；不转为空对象/空数组 |
| null 无来源/来源冲突/状态冲突 | DataShapeError |
| context 字段缺失 | DataShapeError: CONTEXT_FIELD_MISSING |
| context={} | DataShapeError: FRAMES_FIELD_MISSING |
| context=[] / string / number / boolean | DataShapeError |
| frames=[] | 明确 EMPTY_FRAMES_ARRAY |
| frames=null / {} | DataShapeError |
| frame 类型错误、code 非文本、hash 冲突 | DataShapeError |
| 正常有效上下文 | FRAMES_PRESENT，原输入不改动 |
| 旧错误表达式的合成重现 | 得到原 TypeError 类型/消息，保存新 traceback |
| 注入真正 RuntimeError / DataShapeError | 保存完整错误并重抛，在第一个样本停止，不访问第二个，不生成映射状态 |

旧 failure.json 没有单独保存当时完整 stderr 文件。本轮保留原记录，并明确区分新合成重现 traceback；没有将新 traceback 冒充旧原始日志。

原 R01 核心 M01–M08 及附加不变量复查 **41/41**，约 0.429 秒。结果见 `core_synthetic_recheck/test_results.json`。正例/负例符合预期不等于真实样本传播已获证明。

## 5. 三个历史案例仍然保守

新运行器在冻结前重新进行三个指定历史案例的只读源码检查，全部 UNKNOWN，运行异常 0，批准映射 0；约 1.177 秒。

| sample_id | 本轮状态 | 原因 |
| --- | --- | --- |
| NPD/codeql/kernel69:row=24:index=43 | UNKNOWN | 保存片段缺原始 TU/类型/构建，宏与解析诊断未消失 |
| NPD/codeql/libav:row=51:index=84 | UNKNOWN | 缺 typedef/原构建；两个 read_index 调用点不能靠文本证明类型 |
| A04：NPD/codeql/kernel69:row=12:index=24 | UNKNOWN | 缺原始上下文证据及转换模型，未放宽 char*→const void* 边界 |

详细结果和每帧 AST 诊断见 `historical/results.json` 及子目录。没有执行旧生成 Python，也没有重跑旧 solver 或安全策略。

## 6. 冻结后完整固定回归：20/20，一次新运行

候选清单：[candidate_manifest.json](candidate_manifest.json)。冻结 SHA-256：`87415bc09f2065283de4b9859861338c2dccb02628615ecbab3855d8d0ccefca`，记录 114 份代码/配置/输入和已完成证据哈希。冻结时本候选固定集运行数为 0。

固定 20 manifest SHA-256 仍为 `c4ef793abe5f00437f52c27b6fe545dfa613ed661eb441362e1315f1ed98243d`。从第一条开始重新处理，20 个独立 sample_result.json 全部生成；本候选只执行一次，没有根据结果改代码/重试，没有复用第一次输出。它是已接触的固定回归集，不是盲测。

| 状态/项目 | 数量 |
| --- | ---: |
| PASS | 0 |
| REJECT | 0 |
| UNKNOWN | 5 |
| N/A（NOT_APPLICABLE） | 15 |
| 处理记录完成数 | 20/20 |
| 运行异常 / 未执行 | 0 / 0 |
| 缺已保存恢复 frames | 2 |
| 缺原始构建证据 | 20 |
| 类型证据缺失/未验证 | 5 |
| 类型检查未请求（单帧无跨帧对） | 15 |
| 获批参数映射 | 0 |

5 条 UNKNOWN 为 3 条多帧证据不足 + 2 条经验证的 null；15 条 N/A 为单帧保存链中没有请求跨帧对。UNKNOWN 从未计为成功或 N/A。所谓缺源码是“缺恢复 frames”，原告警自身可能仍有 function_code，未用其重建/替换历史上下文。

保存链共有 5 对相邻帧、6 个字面候选调用点，均不等于已经证明的调用映射。语义 PASS 覆盖率仍为 0，不为此放宽门槛。新运行器全程耗时约 **1.135 秒**；完成率 100% 只是证据记录流程完成，不是语义验证覆盖率。

新完整结果见 [fixed_20_results.json](fixed_20_results.json)，运行启动/冻结绑定见 `fixed_20/run_start.json`。

## 7. 第一次与第二次结果严格分开

| 项目 | 原 R01 第一次 | 本轮 RF 第二次 |
| --- | --- | --- |
| 输出目录 | 原 E06_R01_direct_call_argument_mapping/fixed_20 | 本目录 fixed_20 |
| 完整记录 | 12 | 20 |
| 运行错误 | 第 13 条 TypeError | 0 |
| 未执行 | 后 7 条 | 0 |
| 完整记录状态 | UNKNOWN 2 / N/A 10 | UNKNOWN 5 / N/A 15 |
| 拼接/重用 | 未发生 | 0，全部重新运行 |

前 12 条的最终状态一致，但不是复制结果。旧 160 文件，包括失败 JSON、旧完整报告和前 12 条源码/输出，全部字节不变。逐样本对照见 [comparison.json](comparison.json)。旧报告中“当时未提交”仍作为真实历史记录保留，没有事后改写。

## 8. 文件保护与费用

[preservation_check.json](preservation_check.json) 已核对：原 4,468 文件 + 旧 R01 160 文件，共 **4,628 份现有文件**无修改/丢失；冻结 114 文件无变化；RF 目录外无新增；Prompt、MCP、Engine、E01–E05、设计和安全策略全部不改。

预算账本前后 SHA-256 同为 `41c8081ff9cc7f8953cfd5eb833b5b7fd6ee31d1675099e232764382ca082c36`。没有读取或保存 API 密钥。排除凭据/环境目录的规则与旧基线一致。

新增模型调用 **0**、Token **0**、API 费用 **0 元**、Harness **0**、Z3 **0**、生成代码执行 **0**、C 编译/执行 **0**。执行的是可信运行器/测试 Python 和已有 libclang AST 解析。没有告警动作，真实缺陷保留率、误删率和误报过滤率未测。

## 9. 验收及 Git 发布范围

[acceptance_check.json](acceptance_check.json) 记录原 R01 指定离线子集的逐项验收：原 libclang 门槛、八类核心合成场景、三个保守历史案例、核心不变、冻结后一次完整 20 条、原输入不变、失败材料保留、无越界调用和文件保护均通过。

这满足本轮及原 R01 规定的离线验收要求，允许按用户条件发布。**不代表真实样本跨函数传播已证明成功，也不代表任意 C 类型/表达式已获支持。** 旧报告中的 union/RECORD 等未验证范围边界继续保留，没有在本轮修改核心或扩大支持。

发布基线 main：`82f01f772c45d8216e41194055f076e4fe9d9945`；远端 main 发布前核实相同。仅发布两个此前未提交的独立目录：

1. `reproduction/safety_runs/E06_R01_direct_call_argument_mapping/`：原 160 文件原样，用于保留核心和失败基线；RF 导入依赖此目录。
2. `reproduction/safety_runs/E06_R01_runner_fix/`：本轮运行器、测试、全新 20 条输出及报告。

不修改其他仓库文件、不 force push、不改写历史。报告与材料一起提交；实际提交号和 GitHub 报告地址由最终汇报及包含本文件的 Git 提交给出，避免在文件内伪造自身提交哈希。

## 10. 停止点

R01-RF 到此结束。没有继续修改核心、提高 PASS 数、恢复缺失真实构建或进入 R02。后续开发需另行指令。
