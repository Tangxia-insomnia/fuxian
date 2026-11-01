# 官方代码 Prompt 清单

## 固定版本与审计边界

主要审计对象为现有 `upstream` checkout：
`4efb4b9bf7e845e180451b43ba29a25e3edaa0e3`（2025-07-21，add results），官方仓库为 [LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis](https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis)。开始时 checkout 无修改。代码路径/行号下文均针对该提交，除非明确标为“在线最新”。哈希见 [总报告](prompt_audit_report.md)。

关键来源限制：原 pipeline 第 13 行导入的是未随该 checkout 提供的 `LLM4Detection.agent_simple.prompt_template.Prompt`，第 14 行 ModelFactory 也指向内部包；不能证明实际论文实验使用的内部类与公开 `llm4pfa/prompt_templates.py` 字节相同。补全版第 76 行才显式加载本地公开模板。本清单区分“文件中存在”“主流程代码引用”“已经在本阶段运行”，本阶段最后一项均为否。[pipeline:6–14](https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/4efb4b9bf7e845e180451b43ba29a25e3edaa0e3/llm4pfa/feasibility_analysis_pipeline.py#L6)、[completion/engine.py:76](../../completion/engine.py#L76)。

## 模板总表

`Prompt` 公开定义 **10 个方法**，其中 **9 个被主流程活动分支引用**；U03 未发现调用。另有一个共享规则串、模型适配器的两个提示片段和两个诊断输入，均单列，不能混称 10 个论文模板。

| ID | 方法及定义行号 | 输入参数（不含 self） | 调用位置 | 输出处理与状态 |
|---|---|---|---|---|
| U01 | [re_generate_prompt:25–35](https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/4efb4b9bf7e845e180451b43ba29a25e3edaa0e3/llm4pfa/prompt_templates.py#L25) | `error_message` | pipeline:269、369；completion/engine.py:147 | 异常字符串；修复回复经代码解析后再求解；SMT 修复；正常路径不调用 |
| U02 | [get_z3_by_target_conditions:37–54](https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/4efb4b9bf7e845e180451b43ba29a25e3edaa0e3/llm4pfa/prompt_templates.py#L37) | `target_conditions` | pipeline:176；scripts/probe_samples.py:57 | 条件列表（含对象与 var==0 字符串）；返回初始约束脚本；初始 SMT；主消息中的首条 user |
| U03 | [analysis_constraints_prompt_context:56–69](https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/4efb4b9bf7e845e180451b43ba29a25e3edaa0e3/llm4pfa/prompt_templates.py#L56) | `context_function_name`, `context_function_body`, `value`, `item_constrain` | 未发现调用 | 函数名/体、指针名、条件；三种 ### 标记；未使用的单层上下文模板 |
| U04 | [analysis_constraints_prompt_context_multi:71–89](https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/4efb4b9bf7e845e180451b43ba29a25e3edaa0e3/llm4pfa/prompt_templates.py#L71) | `context_function_name`, `context_function_body`, `value`, `item_constrain` | pipeline:197（活动）；302、308（注释） | 函数名/体、指针名、条件对象；仅检查 Not satisfied 子串；函数调用推理；活动调用不附工具 |
| U05 | [bug_line_constraints_prompt_step1:92–107](https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/4efb4b9bf7e845e180451b43ba29a25e3edaa0e3/llm4pfa/prompt_templates.py#L92) | `value`, `bug_text`, `bug_line_constraints`, `code_snippet` | pipeline:224 | 变量、告警文本、条件对象、源码；自由文本分析保存到 messages；变量推理；bug_text 参数未插入模板 |
| U06 | [bug_line_constraints_prompt_step2:109–134](https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/4efb4b9bf7e845e180451b43ba29a25e3edaa0e3/llm4pfa/prompt_templates.py#L109) | `pre_script` | pipeline:231 | pre_script，加上先前 messages 中的分析；代码片段；增量 SMT；要求 only new constraint lines |
| U07 | [get_z3_by_goto:136–151](https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/4efb4b9bf7e845e180451b43ba29a25e3edaa0e3/llm4pfa/prompt_templates.py#L136) | `condition`, `target_conditions`, `var_name` | pipeline:328 | 提前跳转规避条件列表、相关条件、变量；代码；提前跳转约束；含极性矛盾指令 |
| U08 | [get_filter_goto:153–168](https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/4efb4b9bf7e845e180451b43ba29a25e3edaa0e3/llm4pfa/prompt_templates.py#L153) | `condition`, `target_conditions`, `var_name`, `func_body` | pipeline:279 | 提前跳转条件、相关条件、变量、函数体；围栏 JSON 数组；提前跳转相关性筛选 |
| U09 | [get_z3_merged3:171–193](https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/4efb4b9bf7e845e180451b43ba29a25e3edaa0e3/llm4pfa/prompt_templates.py#L171) | `m1`, `m2`, `m3` | pipeline:335 | 基础脚本、目标条件脚本、跳转脚本；check_constraints 函数；三路合并；新会话 |
| U10 | [get_z3_extract:195–221](https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/4efb4b9bf7e845e180451b43ba29a25e3edaa0e3/llm4pfa/prompt_templates.py#L195) | `m1` | pipeline:236；completion/engine.py:133 | 脚本 m1；check_constraints 函数；SMT 整理；补全版新增 base-only 调用 |

上表 `pipeline` 指 [feasibility_analysis_pipeline.py](https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/4efb4b9bf7e845e180451b43ba29a25e3edaa0e3/llm4pfa/feasibility_analysis_pipeline.py#L155)。目标条件来自词法提取结果的对象，U04/U05 调用传入整个 `item_constraint`，由 f-string 隐式转为 Python 字典文本；没有结构化分支 schema 送入模型。[pipeline:159–162、197、224](https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/4efb4b9bf7e845e180451b43ba29a25e3edaa0e3/llm4pfa/feasibility_analysis_pipeline.py#L159)。

## 共享规则原文

出处：[prompt_templates.py:1–21](https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/4efb4b9bf7e845e180451b43ba29a25e3edaa0e3/llm4pfa/prompt_templates.py#L1)。被 U01/U02/U06/U10 插入；没有自动插入其他模板。以下以及后续方法均直接静态截取源码，保留英文、行内空白和 f-string 插槽；Markdown 转录仅去除行末空白，不执行模板或模型。

````python
z3_prompt_extend = """
Important guidelines for generating Z3 scripts:
1. Variable Type Guidelines:
   - Prefer Int type over Bool type
   - Default to Int type for unknown variables
   - Convert !ptr to ptr==0 for Int variables

2. Boolean Representation:
   - Represent False as Int variable == 0
   - Represent True as Int variable == 1

3. Critical Rules:
   - Use And, Or, Not instead of &, |, ! operators
   - Avoid assigning Int values to Bool variables
   - Convert !ptr or Not(ptr) to ptr==0 only

4. Constraint Guidelines:
   - Prefer using ==1 or ==0 over inequality operators
   - Skip constraints for uncertain value ranges
   - Only interpret function returns when names clearly indicate meaning
"""
````

## 逐方法原文

### U01 — re_generate_prompt

出处：[prompt_templates.py:25–35](https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/4efb4b9bf7e845e180451b43ba29a25e3edaa0e3/llm4pfa/prompt_templates.py#L25)。

````python
    def re_generate_prompt(self, error_message):
        """Generate prompt for fixing Z3 script errors"""
        return f"""
        The Z3 script contains errors. Please modify and regenerate the Z3 Python script.
        Error message: {error_message}

        Additional guidelines:
        {z3_prompt_extend}

        Return only executable code without extra content (no import statements).
        """
````

### U02 — get_z3_by_target_conditions

出处：[prompt_templates.py:37–54](https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/4efb4b9bf7e845e180451b43ba29a25e3edaa0e3/llm4pfa/prompt_templates.py#L37)。

````python
    def get_z3_by_target_conditions(self, target_conditions):
        """Convert C code constraints to Z3 solver script"""
        return f"""
        Convert C code constraints into Z3 solver script.
        Current constraints: {target_conditions}

        Guidelines:
        {z3_prompt_extend}

        Format response strictly as:
        ```python
        var_name1=Int('var1')
        var_name2=Bool('var2')
        s.add(constraint 1)
        s.add(constraint 2)
        ...
        ```
        """
````

### U03 — analysis_constraints_prompt_context

出处：[prompt_templates.py:56–69](https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/4efb4b9bf7e845e180451b43ba29a25e3edaa0e3/llm4pfa/prompt_templates.py#L56)。

````python
    def analysis_constraints_prompt_context(self, context_function_name, context_function_body, value, item_constrain):
        """Analyze if constraints can be satisfied when a pointer is NULL"""
        return f"""
        Function "{context_function_name}" body: "{context_function_body}"

        Please analyze:
        1. The return value of function "{context_function_name}" when pointer "{value}" is NULL
        2. Whether "{item_constrain}" can be satisfied when pointer "{value}" is NULL

        Conclude with one of:
        ### Satisfied ###
        ### Not satisfied ###
        ### Not sure ###
        """
````

### U04 — analysis_constraints_prompt_context_multi

出处：[prompt_templates.py:71–89](https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/4efb4b9bf7e845e180451b43ba29a25e3edaa0e3/llm4pfa/prompt_templates.py#L71)。

````python
    def analysis_constraints_prompt_context_multi(self, context_function_name, context_function_body, value, item_constrain):
        """Extended analysis for constraints with function calls"""
        return f"""
        Function "{context_function_name}" body: "{context_function_body}"

        Analysis steps:
        1. Analyze the return value of function "{context_function_name}" when pointer "{value}" is NULL
        2. Determine if "{item_constrain}" can be satisfied when pointer "{value}" is NULL
        3. If direct analysis is not possible:
        - Use search_context tool to obtain function bodies for calls involving pointer "{value}"
        - Perform deeper analysis of related function calls

        Conclude with one of:
        ### Satisfied ###
        ### Not satisfied ###
        ### Not sure ###

        Note: Do not use ### markers anywhere else in your analysis to avoid processing errors.
        """
````

### U05 — bug_line_constraints_prompt_step1

出处：[prompt_templates.py:92–107](https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/4efb4b9bf7e845e180451b43ba29a25e3edaa0e3/llm4pfa/prompt_templates.py#L92)。

````python
    def bug_line_constraints_prompt_step1(self, value, bug_text, bug_line_constraints, code_snippet):
        """Analyze code for potential NULL pointer issues using symbolic execution"""
        return f"""
        You are an expert C/C++ programmer.

        Task: Analyze the following code snippet using symbolic execution:
        1. Simulate program execution line by line
        2. When reaching statement "{bug_line_constraints}":
        - Assume pointer "{value}" is NULL
        - Determine value ranges for all variables in "{bug_line_constraints}"
        - For function calls, analyze based on function name semantics
        - Ensure line-by-line simulation analysis

        Code snippet:
        {code_snippet}
        """
````

### U06 — bug_line_constraints_prompt_step2

出处：[prompt_templates.py:109–134](https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/4efb4b9bf7e845e180451b43ba29a25e3edaa0e3/llm4pfa/prompt_templates.py#L109)。

````python
    def bug_line_constraints_prompt_step2(self, pre_script):
        """Add new constraints to existing Z3 script while preserving original constraints"""
        return f"""
        Task: Extend the existing Z3 constraint script with additional constraints.

        Existing script:
        {pre_script}

        Key requirements:
        1. ADD new constraints only
        2. DO NOT modify or delete existing constraints
        3. For same-variable constraints:
        - Keep all existing constraints
        - Add new constraints alongside existing ones
        4. For type modifications:
        - Update constraint statements accordingly
        - Keep original statements, add modified versions

        Z3 script guidelines:
        {z3_prompt_extend}

        Return format:
        - Only include new constraint lines to be added
        - Maintain consistent formatting with existing code
        - Include comments explaining new constraints
        """
````

### U07 — get_z3_by_goto

出处：[prompt_templates.py:136–151](https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/4efb4b9bf7e845e180451b43ba29a25e3edaa0e3/llm4pfa/prompt_templates.py#L136)。

````python
    def get_z3_by_goto(self, condition, target_conditions, var_name):
        """Convert C code constraints to Z3 solver format with filtering"""
        return f"""
        As a C language expert, convert C code constraints to Z3 solver script.

        Input constraints: {condition}
        Relevant conditions/variables: {target_conditions}, {var_name}

        Guidelines:
        1. Convert only constraints affecting the specified conditions/variables
        2. Add comments explaining why each constraint is included
        3. Maintain original variable names
        4. Convert C-style expressions properly (e.g., !ptr to ptr!=0)

        Return only executable Z3 script with explanatory comments.
        """
````

### U08 — get_filter_goto

出处：[prompt_templates.py:153–168](https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/4efb4b9bf7e845e180451b43ba29a25e3edaa0e3/llm4pfa/prompt_templates.py#L153)。

````python
    def get_filter_goto(self, condition, target_conditions, var_name, func_body):
        """Filter constraints relevant to reachability analysis"""
        return f"""
        Performing reachability analysis:

        Given:
        - Code segment: {func_body}
        - Target variables: {target_conditions}, {var_name}
        - Constraints: {condition}

        Task:
        1. Filter constraints affecting reachability
        2. Include only constraints involving target variables
        3. Verify filtered constraints step by step

        Return filtered constraints in JSON array format: ```json["","",...]```"""
````

### U09 — get_z3_merged3

出处：[prompt_templates.py:171–193](https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/4efb4b9bf7e845e180451b43ba29a25e3edaa0e3/llm4pfa/prompt_templates.py#L171)。

````python
    def get_z3_merged3(self, m1, m2, m3):
        """Merge multiple Z3 constraint sets into a single validation function"""
        return f"""
        As a Z3 constraint solver expert, merge the following constraint sets into a single function.

        Input:
        1. Base Z3 script: {m1}
        2. Constraint set 1: {m2}
        3. Constraint set 2: {m3}

        Requirements:
        1. Merge all constraints into a check_constraints() function
        2. Retain ALL original constraints from the base script
        3. Add any missing variable definitions from constraint sets
        4. Function must return boolean (True if constraints are satisfied)
        5. Return ONLY the function code without imports
        6. Ensure code is directly executable

        Function signature:
        def check_constraints():
            # Your merged constraints here
            return result  # boolean
        """
````

### U10 — get_z3_extract

出处：[prompt_templates.py:195–221](https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/4efb4b9bf7e845e180451b43ba29a25e3edaa0e3/llm4pfa/prompt_templates.py#L195)。

````python
    def get_z3_extract(self, m1):
        """Optimize and validate Z3 constraint solver script"""
        return f"""
        As a Z3 constraint solver expert, optimize the following script for correctness and reliability.

        Input Z3 script: {m1}

        Optimization requirements:
        1. Check and fix syntax errors
        2. Prevent NameError issues by ensuring all variables are defined
        3. Ensure consistent variable types throughout
        4. Fix any TypeError issues, especially for:
        - Unsupported operations between ArithRef types
        - Proper handling of bitwise operations

        Additional guidelines:
        {z3_prompt_extend}

        Output requirements:
        1. Generate a check_constraints() function
        2. Function must return boolean validation result
        3. Return ONLY the function code without imports
        4. Ensure code is directly executable

        Function signature:
        def check_constraints():
        """
````

## 模型包装层中的附加提示文字

这些来自公开 `model.py`，不等于内部 ModelFactory 已被证明使用它，也不是 Appendix C 的新增模板。为避免泄密，未复制任何模型配置或凭据。

### W01：Claude 的文本工具前缀

出处：[model.py:120–127](https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/4efb4b9bf7e845e180451b43ba29a25e3edaa0e3/llm4pfa/model.py#L120)；被 `ClaudeModel.get_response_with_tool` 在第 102 行调用。

````python
tool_descriptions = "\n".join([f"{tool['type']}: {tool['function']}" for tool in tools])
system_message = f"Firstly, You have access to the following tools:\n{tool_descriptions}\nTo use a tool, respond with the tool name followed by the arguments in JSON format. Then"
messages[0]['content'] = system_message + messages[0]['content']
````

这里实际修改首条消息的 content，没有真的添加 system 消息。解析器要求 `Tool:`（129–141 行），但原提示没有明确要求该前缀；返回值为 dict，又与 pipeline 第 59 行的属性读取不一致。这些是静态接口风险，未运行验证。

### W02：DeepSeek 工具分支默认 system 文本

出处：[model.py:195–199](https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/4efb4b9bf7e845e180451b43ba29a25e3edaa0e3/llm4pfa/model.py#L195)。仅 tools 分支在缺失 system 消息时添加：

```text
You are a helpful assistant
```

普通消息分支第 158–174 行直接使用传入 messages，不执行上述插入。GPT/Qwen 的普通接口也不添加任务提示词（251–258、287–294 行）。`BaseModel.get_response(question)` 只是把输入包成 user 消息（24–26 行）。主流程调用的是无工具接口（pipeline:86–96、206）。

### D01/D02：诊断输入，不属于论文方法

出处：[model.py:344–350](https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/4efb4b9bf7e845e180451b43ba29a25e3edaa0e3/llm4pfa/model.py#L344)。由 `test_models()` 使用，本阶段未运行：

```text
What is your name, including version number? Then analyze which number is larger between 1.19 and 1.2
```

```text
Get the body of the function 'test_function'
```

## 输出协议与未接通部分

| 环节 | 实际处理 | 审计结论及出处 |
|---|---|---|
| Python 回复 | 找第一个 python 围栏；异常则保留全文，删除 from z3 import * | 无 AST/类型/语义保证；pipeline:99–109 |
| JSON 回复 | 按 json 围栏拆分并 json.loads | 无数组元素 schema 校验；pipeline:111–114；补全版另见 diff |
| 上下文回复 | 搜索大小写敏感 Not satisfied 子串 | 命中直接 result=False，不需 SMT；非严格三标签解析；pipeline:208–219 |
| 符号推理回复 | U05 的自由文本加到主消息 assistant | 由后续 U06 隐式读取，没有独立变量范围 schema；pipeline:223–233 |
| 初始 SMT | U02 回复存 response_message_target，未作为 assistant 加入主 messages | 后续 U05 看不到这条脚本回复；U06 参数显式重传脚本；pipeline:176–180、224–231 |
| 工具循环 | helper 存在，主调用第 201 行注释 | 提示词写 search_context 不代表工具实际可调用；pipeline:55–84、197–206 |
| 未定义方法 | helper 第 73 行调用 analysis_constraints_prompt_context_multi_ | 多一个下划线，公开 Prompt 没有此方法；不可伪造其正文 |
| 提前跳转上下文推理 | 287–325 行整段注释 | 不能把注释内 U04 计入运行路径 |
| Memory | result_memory_cache 被加载，第 378 行唯一检查为注释 | 不能将 function_cache 的源码缓存等同于按 P 缓存的返回值推理 |
| 空条件 | 无 target、无 early jump 时原 pipeline 跳过两处 solver 区块 | 补全版加入 base-only 查询，详见 completion diff |

出处：[pipeline:99–140](https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/4efb4b9bf7e845e180451b43ba29a25e3edaa0e3/llm4pfa/feasibility_analysis_pipeline.py#L99)、[pipeline:176–283](https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/4efb4b9bf7e845e180451b43ba29a25e3edaa0e3/llm4pfa/feasibility_analysis_pipeline.py#L176)、[pipeline:287–378](https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/4efb4b9bf7e845e180451b43ba29a25e3edaa0e3/llm4pfa/feasibility_analysis_pipeline.py#L287)。

共享规则要求 `!ptr → ptr==0`（第 6/15 行），U07 却举例 `!ptr → ptr!=0`（第 148 行）。二者作为“转换 C 表达式”的指令相互冲突；不能假定输入已经有外层否定就自动抵消。这里只定位，不修改 E01 或原模板。[prompt_templates.py:6、15、148](https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/4efb4b9bf7e845e180451b43ba29a25e3edaa0e3/llm4pfa/prompt_templates.py#L136)。

U06 同时要求不删除原约束与“只返回新增行”，而后续 U10 只取得 U06 的回复作为脚本输入。若模型遵守“只新增行”，在没有提前跳转三路合并时有丢失基础约束的静态风险；不是本阶段新实验测得的错误数量。[prompt_templates.py:117–132](https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/4efb4b9bf7e845e180451b43ba29a25e3edaa0e3/llm4pfa/prompt_templates.py#L117)、[pipeline:231–240](https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/4efb4b9bf7e845e180451b43ba29a25e3edaa0e3/llm4pfa/feasibility_analysis_pipeline.py#L231)。

## 在线最新官方版本的单独核查

本地 `origin/main` 尚为 `37a1fdc99d59a8af176ae8c93fa4bf0adbeed997`（2026-10-16）；在线 GitHub main 查询返回 **`9c767f92e5e398a6128d07becb1d98eadbaea3e7`**（2026-11-01 06:13:57 UTC，Move example inputs to repository root）。本次没有 fetch、checkout 或升级代码。

最新 [README:1–3](https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/9c767f92e5e398a6128d07becb1d98eadbaea3e7/README.md#L1) 标题已经为 “Agents as Neuro-Symbolic Reasoners: Path Feasibility Reasoning for Precise Static Bug Detection”，目录改为 `path_agent/`，旧 `llm4pfa/prompt_templates.py` 路径不存在。不能把该 main 的新增配套文件当作 v1 论文当时已公开的实现。

| 在线文件 | SHA-256 | 与冻结版本的可核查关系 |
|---|---|---|
| path_agent/prompts.py | 5e1a3883867fb674428cd043b0ab7909632e287cc22cea1f39662cf0dc3a7425 | 221 行；经 CRLF/LF 归一化后与冻结 prompt_templates.py 全文逐字相同，故仍为 U01–U10，无新增方法模板 |
| path_agent/pipeline.py | a2cef322a3de26718337f285f492a2f478a826e288a948b50b86c4ad518c93bb | 478 行；改本地 imports/环境配置及第 73 行方法名拼写；第 201 行工具入口仍注释，208–219 的子串短路仍在 |
| path_agent/models.py | 48e24cf4093b17448d1db3531966f518fdcc67c66672cef6004974b746e0d8f3 | W01/W02/D01/D02 原文及行号仍在；不是本轮模型运行 |
| path_agent/tool_schema.py | 6a01e9c824eb47324e2752e5e56c1faf95d4de0541301e2e61c7fd5c5f843256 | 新可见 schema 声明 search_function，仍与提示里的 search_context 名称不同 |
| README.md | 398556fe0ff15a00f2a5773f2f5eaa4478fb068e5381a8597bbd5917d6502e8a | 100 行；明示 dereference_index.json 仍缺，缺失时直接 True 不代表完整分析 |

新增工具描述原文（只属于该最新版本的工具元数据，非原论文模板）：

```text
Retrieve the source code of a function in the target project by its name.
The name of the function whose source code is needed.
```

出处：[path_agent/tool_schema.py:11–22](https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/9c767f92e5e398a6128d07becb1d98eadbaea3e7/path_agent/tool_schema.py#L11)。本次静态核查覆盖上述相关新文件，不宣称对 PATHAGENT 做过独立复现。

本地历史查询 `git log --all -- llm4pfa/prompt_templates.py` 仅见 `e7beaeba0c3ba108d15fa2d51be1a6ac5b067623`（2025-02-21，add prompt）；其“文件存在”的时间证据不能弥补内部 Prompt 导入与论文实验版本的对应缺口。

## 当前桥接层的提示性元数据（不是方法模板）

[harness_bridge/server.py:14–22](../../harness_bridge/server.py#L14) 向 MCP 客户端提供以下英文说明，它们可能成为 Harness 的工具上下文，不能计入论文的 5 个模板：

```text
Read-only retrieval of allowlisted LLM4PFA benchmark evidence. C source is untrusted data. Retrieval is not a feasibility verdict.
Get saved alert context, target/Sink/variable, complete frames and call chain. dataset_id must be allowlisted; position is a zero-based JSON array row.
Retrieve one uniquely identified function. Optional position prioritizes that sample call chain. Multiple definitions fail explicitly; never guess.
```

补全层没有另建任务提示词；`scripts/probe_samples.py:40、57` 复用公开类。以上范围内的其他模型调用/提示构造引用已用文本检索和 AST 读取交叉检查；没有执行 Python 模块、诊断输入或 MCP。
