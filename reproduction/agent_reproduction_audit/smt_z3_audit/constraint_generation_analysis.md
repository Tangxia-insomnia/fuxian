# 路径条件与 SMT 生成审计

范围、版本和禁止执行事项见[总报告](smt_z3_audit_report.md)。U01–U10/P01–P05 编号沿用[提示词映射](../prompt_audit/prompt_mapping.md)，不是作者源码中的编号。

## 1. 论文方法与公开材料

[论文](https://arxiv.org/pdf/2506.10322v1) 第 4–5 页 §3.2.1 描述先从 CFG 提取关键控制条件：到达 Sink 的外层条件应满足；导致提前跳转的条件不能完整满足。第 5–6 页 §3.2.2 再在给定 P 下逐条推理变量和条件相关函数返回值范围。此处应区分：确定控制条件、推理变量状态、转换为 SMT 是三个不同环节。

第 6 页 §3.3 的生成过程是：LLM 生成含导入/求解器的 Python 模板 → 将条件和范围转为 `z3.add()` 约束 → 合并脚本。第 11 页附录 C 公开的 SMT 生成原文为：

> “Convert the following C/C++ conditional expressions into Z3 SMT solver constraints: [Conditional Expressions]”
>
> “[SMT Query Script Generation Rules]”

该规则占位符没有展开；不能自行补写成作者原始规则。附录也没有完整独立的“模板生成”提示词。公开 Prompt 与代码差异见前阶段 [paper_prompt_inventory.md](../prompt_audit/paper_prompt_inventory.md)。

## 2. 冻结官方实现的实际顺序

| 顺序 | 输入 → 输出 | 代码位置与限制 |
| --- | --- | --- |
| 1 | 变量、Sink、函数源码 → 条件字典 | [pipeline:159–162][pipeline]，调用 `extract_util_plus.extract_conditions` |
| 2 | 目标条件 + `目标变量 == 0` → 基础约束片段 B | pipeline:174–180；[U02:37–54][prompt] 的输出示例是声明与 `s.add`，本身未必是可运行模板 |
| 3a | 条件内相关调用的函数体、NULL 前提 → 自然语言分析 | pipeline:190–219，U04:71–89；实际工具调用行 201 被注释，走无工具调用；出现字符串 `Not satisfied` 可直接返回 False |
| 3b | 单条条件对象、函数源码、NULL 前提 → 变量范围分析 | pipeline:224–227，U05:92–107；`bug_text` 没有插入模板；传入的是条件字典的字符串表示 |
| 4 | B + 当前消息历史 → 新增约束片段 Δ | pipeline:231–233，U06:109–134；只返回新增行的要求与下游接口有冲突 |
| 5 | **仅 Δ** → `check_constraints()` | pipeline:236–240，U10:195–221；消息历史重置，不显式传 B |
| 6 | 执行生成的函数；错误走 U01 | pipeline:244–274；这是模型生成的 Python/Z3 程序，不是直接返回一个受校验的 SMT2 AST |
| 7 | 提前退出条件 → U08 筛选 → U07 转换 → U09 合并 | pipeline:276–282、328–339；提前退出分析的另一段上下文循环 287–325 被注释 |

U04 的单独 `message_context` 响应写入展示用 `response_list`，没有追加到主 `messages`（198–209）；U06 不因此自动获得上下文返回值范围。自然语言判定还可能绕过后续 SMT。不能把这些步骤描述为冻结代码已经完整实现了论文的 Agent、Memory 和逐条范围传播。

## 3. 条件提取实现不等于论文中的完整 CFG

[extract_util_plus.py:115–257][extractor] 中活动的目标提取器通过文本、括号和缩进恢复外层条件，目标周围缩进判断主要计数制表符（166–174）；`&&` 直接按字符串切分（121–122），else 条件由字符串否定拼接（196–211），记录的 `line_number` 是函数片段内零基行号。

提前退出使用该文件后定义的同名 `extract_return_goto_conditions2:640–801`，不是 378–385 的旧定义。其条件扫描也是词法/缩进方法。文件中虽然有其他 v2、旧版和 `extract_conditions_s` 函数，活动 pipeline 调用的是 `extract_conditions:1116–1188`；不能因为文件包含另一套函数就声称当前运行使用了完整 C CFG。

`extract_conditions` 的 `assignment_line_index` 默认 0（1140），pipeline 又传 `None`（159）；1183 将函数第 1 行写入 `variable_assignments.text`，可出现 `static void ...` 被当成赋值元数据的历史问题。这与 P 缺失和状态推理可信度有关，但本阶段没有修复 R02。

## 4. 补全版保留与替换

[completion/engine.py:26–69](../../completion/engine.py#L26) 截取上游函数并做运行时字符串适配；76 行加载公开 Prompt，未修改原始英文模板。83–97 行为每个恢复 frame 保存原提取器结果；99–108 行解析代码/JSON；110–147 行替换求解执行与空条件基础查询。它没有新增逐断言源码追溯、完整 P 或确定性约束合并。

因此，补全版保留了 U02/U06/U10 的接口风险和 U07 的极性冲突。它的代码格式解析验证只说明“拿到了代码/字符串数组”，不说明约束正确对应 C 代码。

## 5. 恢复前需要的证据

需要分别保存原始条件、true/false 分支、Source 与 Sink、函数体哈希、变量声明/作用域身份、赋值版本、范围分析原文、约束候选和断言来源。缺一项不能由“模型生成代码可执行”替代。这里只提出未来验收资料，不新增算法或工具。

[pipeline]: https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/4efb4b9bf7e845e180451b43ba29a25e3edaa0e3/llm4pfa/feasibility_analysis_pipeline.py#L159
[prompt]: https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/4efb4b9bf7e845e180451b43ba29a25e3edaa0e3/llm4pfa/prompt_templates.py#L37
[extractor]: https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/4efb4b9bf7e845e180451b43ba29a25e3edaa0e3/llm4pfa/extract_util_plus.py#L115
