# 原论文 Prompt Templates 清单

审计日期：2026-11-01。论文固定为 **arXiv:2506.10322v1**（提交时间 2025-06-12 03:11:38 UTC），PDF 共 11 页。以下页码均指 PDF 物理页码。仅转录公开材料；省略号和占位符保持原样，不补写。

## 证据与范围

- [论文 PDF v1](https://arxiv.org/pdf/2506.10322v1)，SHA-256：`03eba4d55590bd67228b37e10eda3662d604e708f112f5d9d973efbcc02feacd`，1,790,475 字节。
- [论文 TeX 源归档 v1](https://arxiv.org/src/2506.10322v1)，SHA-256：`c02abf4e361ac111cae8f003ea353e2ca1427a75b80720ecdea7bf45f3151457`，8,539,773 字节。只在内存中读取，没有新增 PDF、归档或代码文件。
- 全文检查了归档中的 27 个 TeX 文件，并核对 PDF 正文、Appendix B/C 与 Figure 3。文内 `main.tex:59–61` 将 dataset、baselines、prompt 三个附录纳入同一论文。所检查的 arXiv 版本记录仅列 v1；本次材料中没有找到另一份包含完整提示词的独立补充附件。这是本次检索边界，不代表证明任何其他渠道均不存在附件。
- 本地既有 [appendix/prompt.tex](../../safety_runs/20261029_build_search_repair_plan/search/paper_source_excerpts/appendix/prompt.tex#L1) 与重新取得的归档文本逐字一致，文件 SHA-256：`972e1e89b20027f108c6cf4e79fa8d85b6e82682c026b42444afceb6addd0df0`。
- 本地既有 [appendix/baselines.tex](../../safety_runs/20261029_build_search_repair_plan/search/paper_source_excerpts/appendix/baselines.tex#L1) 同样一致，SHA-256：`8b2b3529d7c622238dfebf5cf23a13e9da9dbff94f5665d66ea7c2825cdcb25a`。

公开可见的模板块共 **8 个：LLM4PFA 方法 5 个、比较基线 3 个**。LLMDFA Dataflow Validation 的 Synthesis/Fixing 是同一个公开框内的两项任务，不额外计数。[PDF pp10–11, Appendix B/C](https://arxiv.org/pdf/2506.10322v1#page=10)。

## 总表

| ID | 作者标题 | PDF 页/节 | 输入 | 功能与公开输出 |
|---|---|---|---|---|
| P01 | Prompt for variable symbolic range reasoning | p11, C.1 | conditional statement、P、Code Snippet | 推断条件执行时变量范围；分步自然语言分析，无公开 JSON schema |
| P02 | Prompt for contextual analysis | p11, C.1 | function name/body、P、Code Snippet | 推断返回值范围；需要更深上下文时请求 search_context；Important 段公开为 ... |
| P03 | Prompt in SMT constraints generation | p11, C.2 | Conditional Expressions、规则占位 | 返回 Python 围栏中的 Z3 声明和 s.add 约束 |
| P04 | Prompt in script merging | p11, C.2 | SMT Query Script、SMT Format Constraints | 保留全部约束，形成返回布尔值的 check_constraints() |
| P05 | Prompt in script fix | p11, C.2 | 上轮脚本对话、Error Message、规则占位 | 根据错误重新生成可执行 Z3 Python 脚本 |
| B01 | LLM4SA | p10, B | Bug Report、Code Snippet | 行为解释，最后输出 @@@ real bug / false alarm / unknown @@@ |
| B02 | LLMDFA Dataflow Summarization | p10, B | FUNCTION、VAR1/2、LINE1/2、规则/示例占位 | 指针值是否相同，Yes/No 加解释；仅公开 NPD 版本 |
| B03 | LLMDFA Dataflow Validation | pp10–11, B | path、variable、branch info、early jump info、skeleton、script、error message | Z3 脚本合成及错误修复 |

## 作者原文

以下从 TeX 逐块提取原文，保留英文、拼写、标点、占位符、排版命令与行序；Markdown 转录仅去除行末空白，不修订正文。代码框中的 LaTeX 命令只用于保留出处，不是新增提示词。源码行号均针对归档成员，且 Appendix B/C 对应上述本地缓存文件。

### P01：变量符号范围

出处：PDF p11 / C.1；`appendix/prompt.tex:8–32`。Variable Reasoning；不负责检索函数或调用 Z3。

````latex
\begin{mdframed}
[linecolor=myblue!50,linewidth=2pt,roundcorner=10pt,backgroundcolor=myyellow!20]
\small

\hspace{3.5mm} \textbf{System Role}: You are an expert C/C++ programmer.

\textbf{Task Description:} Your goal is to determine the possible value ranges for each variable in [conditional statement] assuming the [P] when [conditional statement]  is executed.

Important:

- Analyze each line sequentially through symbolic execution.

- Consider function semantics based on their names.

- Pay special attention to pointer operations and conditions.

- Track how variable ranges change through the execution path.

After the analysis, conclude your answer.

\textbf{Code Snippet:} [Code Snippet]

Please provide your analysis in clear steps, explaining how you arrived at the value ranges.

\end{mdframed}
````

### P02：上下文及函数返回值

出处：PDF p11 / C.1；`appendix/prompt.tex:36–54`。Function Call Reasoning；明确提到 search_context；未给出工具 schema 和独立 Memory 提示词。

````latex
\begin{mdframed}
[linecolor=myblue!50,linewidth=2pt,roundcorner=10pt,backgroundcolor=myyellow!20]
\small

\hspace{3.5mm} \textbf{System Role}: You are an expert C/C++ programmer.

\textbf{Task Description:}
Given the function [function name] with body [function body],
your goal is to determine the possible value ranges for the function return value when [P]. If the value range cannot be directly determined and further investigation in deeper function is required, please use the search\_context tool to retrieve the function body for further analysis.

Important:

...

\textbf{Code Snippet:} [Code Snippet]

Please provide your analysis in clear steps, explaining how you arrived at the value ranges.

\end{mdframed}
````

### P03：SMT 约束生成

出处：PDF p11 / C.2；`appendix/prompt.tex:63–94`。把条件转为 Z3 Python 约束；不是求解器本身。

````latex
\begin{mdframed}
[linecolor=myblue!50,linewidth=2pt,roundcorner=10pt,backgroundcolor=myyellow!20]
\small

\hspace{3.5mm} \textbf{System Role}: You are an SMT constraint expert.

\textbf{Task Description:}
Convert the following C/C++ conditional expressions into Z3 SMT solver constraints:
[Conditional Expressions]

When generating Z3 SMT solver scripts, follow these critical guidelines:

[SMT Query Script Generation Rules]


Return only the executable Z3 constraints in the following format:

\verb|```|\textit{python}

\textit{var\_name1 = Int(`var 1')}

\textit{var\_name2 = Bool(`var 2')}

\textit{s.add(constraint 1)}

\textit{s.add(constraint 2)}

...

\verb|```|

\end{mdframed}
````

### P04：SMT 脚本合并

出处：PDF p11 / C.2；`appendix/prompt.tex:98–113`。保留原始与新增约束；返回 check_constraints()。

````latex
\begin{mdframed}
[linecolor=myblue!50,linewidth=2pt,roundcorner=10pt,backgroundcolor=myyellow!20]
\small

\hspace{3.5mm} \textbf{System Role}: You are an expert Z3 constraint solver.

\textbf{Task Description:}
I'll provide a Z3 constraint script and a set of additional constraints. Please combine them into a single script and keeping all existing constraints (both from the original script and the new constraint sets). If any new constraints are missing variable definitions, make sure to add or modify the necessary declarations.
Return your solution as a function named \textit{check\_constraints()} that returns a boolean indicating whether the constraints are satisfiable. The function should be ready to execute and no imports or extra content needed.

\textbf{Original Z3 script:} [SMT Query Script]

\textbf{Additional Constraint Set:} [SMT Format Constraints]


\end{mdframed}
````

### P05：SMT 脚本修复

出处：PDF p11 / C.2；`appendix/prompt.tex:117–128`。错误反馈提示；最多 3 轮是正文 p6 §3.3 的调度规则，并非此框内实现。

````latex
\begin{mdframed}
[linecolor=myblue!50,linewidth=2pt,roundcorner=10pt,backgroundcolor=myyellow!20]
\small

\hspace{3.5mm} \textbf{Task Description:}
The Z3 script you generated contains errors. Please fix and regenerate the Z3 Python script.  The script should be directly executable.

\textbf{Error details:} [Error Message]

\textbf{Additional Requirements:} [SMT Query Script Generation Rules]

\end{mdframed}
````

### B01：LLM4SA 基线

出处：PDF p10 / B；`appendix/baselines.tex:7–22`。直接告警分类；不能当作 LLM4PFA 的最终判定模板。

````latex
\begin{mdframed}
[linecolor=myblue!50,linewidth=2pt,roundcorner=10pt,backgroundcolor=myyellow!20]
\small

\hspace{3.5mm} You are an expert C/C++ programmer.

\textbf{\# Task Description:}

The code snippet and the bug report will be provided to you for the purpose of examining the presence of the bug within the code snippet. Initially, you need to explain the behavior of the code. Subsequently, you can determine whether the bug is a true positive or a false positive based on the explanation.  To conclude your answer, you will provide one of the following labels: @@@ real bug @@@, @@@ false alarm @@@, or @@@ unknown @@@.

\textbf{\# Bug Report:} \textit{[Bug Report]}

\textbf{\# Code Snippet:} \textit{[Code Snippet]}


\end{mdframed}
````

### B02：LLMDFA 数据流概括基线

出处：PDF p10 / B；`appendix/baselines.tex:28–60`。同值关系，含未公开 Other Rules/Examples；原文 Dose 保留。

````latex
\begin{mdframed}
[linecolor=myblue!50,linewidth=2pt,roundcorner=10pt,backgroundcolor=myyellow!20]
\small

\hspace{3.5mm}
\textbf{System Role}: You are a C programmer and very good at analyzing C code.

\textbf{Task Description}: Determine whether two pointer variables at two lines have the same value (i.e., both pointing to the same address or both NULL).

\textbf{Analysis Rules}:

If they are the same pointer variable and not overwritten between two lines, the answer should be yes.

If the pointer variable a is assigned to the variable b, and there is no overwrite upon them between two lines, the answer should be yes.

[Other Rules]

\textbf{Examples}:

Example 1: User: [Program] [Question]

System: [Answer: Yes][Explanation: y is assigned with x at line 2 and not overwritten between line 2 and line 3, so the value of y before line 3 and x after line 1 are the same]

[Other Examples]

\textbf{Question}: Now I give you a function: [FUNCTION]

Please answer: Dose [VAR1] used at line [LINE1] have the same value as [VAR2] defined at line [LINE2]

Please think it step by step. Return Yes/No with the explanation.


\end{mdframed}
````

### B03：LLMDFA 路径验证基线

出处：PDF pp10–11 / B；`appendix/baselines.tex:65–84`。脚本合成及修复；不是 LLM4PFA P03–P05 的完整替代。

````latex
\begin{mdframed}
[linecolor=myblue!50,linewidth=2pt,roundcorner=10pt,backgroundcolor=myyellow!20]
\small

\hspace{3.5mm} \textbf{System Role}: You are a good programmer and familiar with Z3 Python binding.

\textbf{Description}: Please write a Python program using Z3 Python binding to encode the path condition.

\textbf{Path Info}: Here is the path: [path]. Note that the value of [variable] is 0.

The branch information is as follows: [branch info].

The early jump information is as follows: [early jump info].

\textbf{Synthesis Task}: Please write a Python script to solve the path condition using Z3 Python binding. You can refer to the skeleton: [skeleton]

\textbf{Fixing Task}: Here is the synthesized result of the last round: [script]. When executing the synthesized script, we encounter the following error: [error message]. Please fix the bug and return a runnable script.


\end{mdframed}
````

## 尚未公开或不能据此还原的部分

| 项目 | 公开证据 | 本次结论 |
|---|---|---|
| P02 的 Important 详细规则 | p11 C.1；appendix/prompt.tex:46–48 | 原文为 ...；不能从其他模板推造 |
| SMT 生成/修复规则全文 | p11 C.2；appendix/prompt.tex:76、126 | 仅 [SMT Query Script Generation Rules] 占位；代码规则须单独归为代码证据 |
| LLM4PFA few-shot 分析实例 | p5 §3.2.2；section/app/constraints_complementation.tex:15；p6 §3.3 | 正文称有 few-shot，但 Appendix C 未列完整实例；没有将 Appendix B 基线示例移作方法示例 |
| Script template generation 独立完整模板 | p6 §3.3；section/app/constraints_solving.tex:10；appendix/prompt.tex:59 | 正文有该阶段；源码只有被注释的标题，没有模板正文 |
| Function Call Memory 的读写/检索提示词 | p6 §3.2.2、Figure 3；section/app/constraints_complementation.tex:36 | 描述按不同 P 缓存返回值范围，未公开独立提示词或 key schema |
| 提前跳转条件筛选、跨函数实参传播独立模板 | pp4–6 §3；Appendix C | 没有独立公开块；其存在不能由代码函数名反推为论文原文 |
| BOF/UAF 等缺陷专用完整模板 | p6 §4.1、p11 C | 本文覆盖 NPD/UAF/BOF，但没有完整列出每种缺陷专用模板 |
| 独立多 Agent 角色/通信提示词 | pp5–6 §3.2.2、Figure 3 | 论文使用 LLM agents/agent-based 字样，未公开多角色协作协议；本次按用户要求保留单推理主体方案 |

`System Role:` 是作者框内的文本标签，不足以证明实际 API 使用了 system role。公开代码把主要提示词放入 user messages，见 [pipeline:177、198、225](https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/4efb4b9bf7e845e180451b43ba29a25e3edaa0e3/llm4pfa/feasibility_analysis_pipeline.py#L177)。

本清单是公开材料的完整转录，不是论文全部实验时实际提示词已完全公开的证明。
