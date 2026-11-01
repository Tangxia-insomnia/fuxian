# 初始状态 P 专项审计

审计日期：2026-11-01。论文固定为 arXiv:2506.10322v1；官方代码固定为 `4efb4b9bf7e845e180451b43ba29a25e3edaa0e3`。本文件只记录文献、源码和既存数据的静态检查，没有构造或执行新的路径判定。

## 1. 论文明确公开了什么

[论文 PDF](https://arxiv.org/pdf/2506.10322v1) 第 5 页 §3.2.2 定义：

> “P denotes the required initial states of the program.”
>
> “The initial states P are the post-conditions following the execution of Sf. These conditions encompass both the pre-conditions required by Sf and the post-conditions of the Sf statement.”

同页说明：首个函数使用 Source（Sf）之后的状态；后续函数还纳入前一函数中与传入参数有关的可行路径约束；P 随缺陷类型变化，NPD 示例传播目标指针的 NULL 状态。可核对 [arXiv 源码](https://arxiv.org/src/2506.10322v1) 中 `section/app/constraints_complementation.tex:8–15`。

因此，P 是分析的前提，不是数据集真值标签，也不是 LLM 可以自由生成的结论。告警提供目标、Source/Sink 和调用轨迹，源码提供语义证据，LLM 在给定 P 下推理变量或返回值范围。论文第 4 页 §3.1 将目标变量、Source、Sink 和 Source-to-Sink 调用轨迹列为输入。

**待确认：**论文正文、附录 C（第 11 页）及本次检查的公开源码材料，没有完整给出将告警转换成 P 的算法、统一数据结构、类型/别名规则、赋值版本规则或每类缺陷的构造器。不能将“传播 NULL”扩展解释为作者已公开完整的 C 初始状态恢复算法。附录 P01/P02 只出现 `[P]` 占位符。

## 2. 冻结官方代码实际做了什么

| 代码证据 | 实际行为 | 与论文定义的差距 |
| --- | --- | --- |
| [pipeline:454–461][pipeline] | 读取变量、Sink 文本、文件行号和函数体，传入已有条件 | 没有读取一个完整、类型化的 P；没有独立 Source 状态对象 |
| pipeline:159–162 | 调用 `extract_conditions(var_name, None, loc_text, code_snippet)`，重新提取并覆盖传入的目标/提前退出条件 | 没有显式传入 Source 赋值语句；跨函数传来的条件可能被覆盖 |
| pipeline:174–178 | 拼接 `var_name + " == 0"` 并交给 U02 | 是 NPD 的 NULL 假设，不是完整 P；变量名 `non_null_value` 与实际表达式相反，但实际加入的是 `== 0` |
| [Prompt U04:71–89、U05:92–107][prompt] | 在自然语言中假设指针 NULL；U05 的 `bug_text` 参数未插入模板 | 无通用 P 参数，也无逐条前提的来源绑定 |
| pipeline:398、420–433 → 159–162 | 映射目标参数，再尝试按其他实参筛选条件递归传递 | 原版从裸函数名提取实参、检查字典键；下一层又重新覆盖，不能证明论文所述完整状态传播 |

官方 pipeline 的 Prompt 实际导入路径是缺失的内部包 `LLM4Detection.agent_simple.prompt_template`（第 13 行）；以上 U 编号沿用前阶段审计，指公开的 `prompt_templates.py`。不能证明作者未公开的运行环境加载了与公开文件逐字相同的模板。

## 3. 当前公开数据能支持到哪里

只读解析 MCP 白名单所列 8 个 NPD JSON；路径见 [harness_bridge/tools.py:22–31](../../harness_bridge/tools.py#L22)。这里是原始文件行数，**不是本阶段实验样本数，也不是论文评测规模**。

| dataset_id | JSON 条数 | 与 P 有关的显式顶层信息 |
| --- | ---: | --- |
| codeql_linux | 70 | 变量、位置、函数源码；70 条均有 `var_assign_conditions`、`pointer_null_postconditions`、`bug_line_constraints`、`early_jump_constraints` |
| codeql_libav | 57 | 变量、位置、函数源码；只有 3 条另有 `source_not_null`，无统一 P 字段 |
| codeql_openssl | 50 | 变量、位置、函数源码，无统一 P 字段 |
| cppcheck_linux | 594 | 变量、位置、函数源码；17 条有 `loop_assign`；仅 68 条存在 `result` 字段，存在不等于标签已核实 |
| cppcheck_libav | 10 | 变量、位置、函数源码；2 条有 `define_in_function_body` |
| cppcheck_openssl | 5 | 变量、位置、函数源码 |
| infer_libav | 6 | 变量、位置、源码在 `func_info`，适配器重命名使用 |
| infer_openssl | 16 | 变量、位置、函数源码 |
| 合计 | 808 | 不提供通用、完整、类型化的 P |

不能仅凭字段名称把 `pointer_null_postconditions` 当成形式化 P。例如 codeql_linux / position=10 中它保存的是 `if (skb)` 及条件/代码片段，`var_assign_conditions` 是空列表；这不能直接说明 Source 的实际赋值及到 Sink 的完整状态。pipeline 还会重新提取条件，而不是原样消费全部这些派生字段（159–162）。数据文件 SHA-256 见[总报告](smt_z3_audit_report.md)。

历史 `29ca96e0d5f860d1f4ce07cd3e54e5e25732d1a1:baseline/NPD-*.json` 提供 `prt`、`sink`、`function_call`、`final_sink` 等上下文。当前 [ContextRepository.prepare:141–181](../../completion/context.py#L141) 用变量、Sink 和首函数文本匹配恢复调用链，校验直接传参，返回函数体哈希。它没有恢复原始 CodeQL 数据库、编译配置、完整 CFG、预处理宏或跨过程别名状态。

## 4. 补全版及 Harness 的边界

[completion/engine.py:64–65](../../completion/engine.py#L64) 修正实参提取入口和字典文本匹配，但没有修复下一层覆盖 P 的逻辑，也没有新增 P 构造器。[context.py:86–100](../../completion/context.py#L86) 只支持可唯一映射的直接实参与形参关系，不能当作完整符号状态传递。

用户报告的第四阶段真实 Harness 检索基线证明了获取更多函数源码的能力；它尚未产生经核实的 P。`avio_rb32` 检索失败必须作为上下文边界保留，不能靠函数名猜测补齐状态。此点是通用要求，不是 position=54 特判。

当前结论：数据足以支持部分上下文恢复和受限的 NULL 假设分析；不足以声称普遍、忠实地构建了论文 P。后续若设计结构化 P，必须标记为复现适配方案，逐项标明证据和缺失项，而不是宣称找回了作者未公开方法。

[pipeline]: https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/4efb4b9bf7e845e180451b43ba29a25e3edaa0e3/llm4pfa/feasibility_analysis_pipeline.py#L155
[prompt]: https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/4efb4b9bf7e845e180451b43ba29a25e3edaa0e3/llm4pfa/prompt_templates.py#L71
