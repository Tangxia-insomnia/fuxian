# 论文—官方代码—补全版 Prompt 对应表

审计对象和英文原文见 [论文清单](paper_prompt_inventory.md) 与 [代码清单](upstream_prompt_inventory.md)。P/B/U 编号仅为本审计索引，不是作者原有编号。代码默认指冻结上游 `4efb4b9bf7e845e180451b43ba29a25e3edaa0e3`；最新 PATHAGENT 的单独差异见代码清单。

## 逐模板对应

| 论文公开块 | 冻结公开代码对应 | 变化/缺失 | 当前补全版 |
|---|---|---|---|
| P01 变量符号范围（p11 C.1） | U05 bug_line_constraints_prompt_step1，prompt_templates.py:92–107 | 论文 P 为通用初始状态；代码写死目标指针 NULL，使用名字推断函数语义；论文逐行/范围分析意图保留，英文并非逐字相同；没有公开 few-shot 例子 | engine.py:76 原样加载 U05；继承 NULL 假设与自由文本输出 |
| P02 上下文/返回值（p11 C.1） | U04 analysis_constraints_prompt_context_multi:71–89；U03:56–69 为未调用变体 | 论文要返回值范围，代码加 Satisfied/Not satisfied/Not sure；代码将整个条件对象插入；公开 Important 省略不能由代码反向补齐 | 主分支仍无工具调用；无自动深层 planning |
| P03 SMT constraints（p11 C.2） | U02 get_z3_by_target_conditions:37–54；部分功能由 U06:109–134、U07:136–151 分担 | 论文规则为占位；代码有具体共享规则；U07 的 !ptr 极性示例与共享规则冲突；不能把规则串称为已公开论文原文 | 共享规则与所有方法文本未改 |
| P04 script merging（p11 C.2） | U09 get_z3_merged3:171–193；U06:109–134 是另一种增量添加方式 | 论文合并一个旧脚本+新增集；U09 合并三份；U06 要保留旧约束却只返回新行；U10:195–221 整理函数，论文无同名单独公开模板 | 保留两种合并路径；没有把“文本未改”当作调用语义未改 |
| P05 script fix（p11 C.2） | U01 re_generate_prompt:25–35 | 具体规则来自代码，正文最多 3 轮修复；原循环可能产生第 4 次未被再次验证的修复回复 | engine.py:43–45 限制耗尽；132–147 新增 base-only 修复路径 |
| Script template generation（p6 §3.3，有描述、无完整块） | pipeline.py:173–178 标为 generate z3 template，却实际调用 U02 | 代码 U02 只有声明/断言示例，无显式完整 imports/solver 模板；不能视作缺失论文模板的原文 | 仍复用 U02；另以 U10 转成 base-only 可执行函数 |
| Memory 读写（p6 §3.2.2/Figure 3，有描述、无完整块） | result_memory_cache:23、27、378（使用处注释） | 无独立模板，也无已接通按 P 复用返回值范围的实现 | engine.py:156 每样本 function_cache={}；这是源码缓存 |
| B01 LLM4SA（p10 B） | 本冻结 llm4pfa 目录无该模板或执行入口 | 上游 results 可有基线结果，但不能用结果文件反推实际提示词 | 无实现；本次不补写 |
| B02/B03 LLMDFA（pp10–11 B） | 本冻结 llm4pfa 目录无这两个基线模板 | Appendix B 有公开框但规则/例子有占位；未发现代码接线 | 无实现；不以方法模板替代 |

代码出处：[Prompt 全部定义](https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/4efb4b9bf7e845e180451b43ba29a25e3edaa0e3/llm4pfa/prompt_templates.py#L25)、[pipeline:173–240](https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/4efb4b9bf7e845e180451b43ba29a25e3edaa0e3/llm4pfa/feasibility_analysis_pipeline.py#L173)、[pipeline:23–27、378](https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/4efb4b9bf7e845e180451b43ba29a25e3edaa0e3/llm4pfa/feasibility_analysis_pipeline.py#L23)、[engine:43–76、132–156](../../completion/engine.py#L43)。论文出处：[PDF pp5–6 §3.2.2/3.3](https://arxiv.org/pdf/2506.10322v1#page=5)、[PDF pp10–11 B/C](https://arxiv.org/pdf/2506.10322v1#page=10)。

## 功能关系矩阵

“参与”表示描述/代码职责，并不表示该功能已经可靠完成。

| 功能 | 论文角色与对应模板 | 冻结代码活动实现 | 补全版/MCP 状态 |
|---|---|---|---|
| Function Retrieval | P02 需要 deeper functions 时调用 search_context；p6 Figure 3 | pipeline:194 程序主动检索一个函数体，U04 收到结果；55–84 工具循环未被主分支调用 | engine:160 绑定 repository.lookup；MCP 两个只读工具不调用模型 |
| Function Call Memory | p6 按不同 P 记录返回值符号范围；未公开专门模板 | function_cache 保存名字→函数体；result_memory_cache 未接通 | 每样本缓存与函数链不是语义推理 Memory；未新增 Memory |
| Variable Reasoning | P01 分析条件中变量在初始状态 P 下的范围 | U05 接变量、条件对象和源码，假设指针 NULL，输出自然语言 | 原 U05 文本；没有新的本地 C 语义执行器 |
| Function Call Reasoning | P02，按相关实参、初始状态、深层函数迭代（最多 5） | U04 对一个已取函数体做无工具分析；Not satisfied 可直接 False | 仍走普通 messages；不能因函数名含 multi 就称多 Agent 或多层已接通 |
| SMT 生成/合并/修复 | P03/P04/P05；脚本模板阶段正文单列 | U02、U06、U07、U09、U10、U01；并含 U08 相关性筛选 | 原文复用；执行隔离、解析器和 base-only 调度有修改 |
| Z3 | p6 §3.3，外部求解器检查 SMT 查询；不是 LLM 提示词 | pipeline:248–249、346–349 执行模型生成函数 | engine:110–130 子进程求解；MCP 未暴露 solver；安全规则仍另行裁决 |

出处：[pipeline:55–96、127–140、190–219、231–372](https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/4efb4b9bf7e845e180451b43ba29a25e3edaa0e3/llm4pfa/feasibility_analysis_pipeline.py#L55)、[engine:110–160](../../completion/engine.py#L110)、[bridge/server:27–40](../../harness_bridge/server.py#L27)。Matrix 中 Memory、5 次上下文迭代来自 [PDF p6 §3.2.2](https://arxiv.org/pdf/2506.10322v1#page=6)。

## 应明确标注的差异与证据级别

1. **公开文本并非实验内部类的可证实镜像。** 公开 pipeline 导入未提供的内部 Prompt；本地补全版显式换为公开文件。这是来源不确定性，不能仅看英文相似就称精确复现。[pipeline:13](https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/4efb4b9bf7e845e180451b43ba29a25e3edaa0e3/llm4pfa/feasibility_analysis_pipeline.py#L13)、[engine:76](../../completion/engine.py#L76)。
2. **P 的语义被收窄。** 论文初始状态包括 Source 后置条件及前帧相关参数约束（p5 §3.2.2），模板代码却只显式注入 NULL。跨帧传参/条件虽有程序代码，当前没有一个包含完整 P 的结构化模板参数，不能据参数名自行推断实现了论文状态传播。[Prompt:56–107](https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/4efb4b9bf7e845e180451b43ba29a25e3edaa0e3/llm4pfa/prompt_templates.py#L56)、[pipeline:398–433](https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/4efb4b9bf7e845e180451b43ba29a25e3edaa0e3/llm4pfa/feasibility_analysis_pipeline.py#L398)。
3. **原文“工具”“多轮”“Memory”各自是不同能力。** 工具循环的主调用为注释、Memory 使用也为注释；普通 messages 累积并不能证明自主工具规划。该结论是活动调用图的静态事实，不是本阶段新的运行结果。[pipeline:201、206、378](https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/4efb4b9bf7e845e180451b43ba29a25e3edaa0e3/llm4pfa/feasibility_analysis_pipeline.py#L197)。
4. **判断粒度不同。** 论文主张逐项范围生成并立即解 SMT（p6 §3.3）；代码把 U05 多条分析累计后才统一 U06/U10，函数上下文还可直接返回 False。最终安全 v1 的 FILTER/KEEP/UNKNOWN 与原代码布尔输出不能混称同一标签。[pipeline:211–249](https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/4efb4b9bf7e845e180451b43ba29a25e3edaa0e3/llm4pfa/feasibility_analysis_pipeline.py#L211)、[safety/policy.py:13–17、228](../../safety/policy.py#L13)。
5. **不把最新重组版补充内容倒记为原论文公开材料。** 2026-11-01 PATHAGENT main 新提供的 tool_schema 是 search_function，Prompt 文本仍说 search_context；详见 [最新版本核查](upstream_prompt_inventory.md)。这是版本比较，不是升级或运行该版本。

## 未实际调用清单

- U03：在扫描的活动 Python 调用中无引用。
- helper 中 `analysis_constraints_prompt_context_multi_`：名字不存在，不是第 11 个模板。
- U04 在提前跳转段的两处引用（302、308）和工具入口（201、311）为注释。
- W01/W02 只在特定模型工具接口触发；不能记入当前普通无工具主流程。
- B01–B03 仅作为论文基线公开文本记录；本次既不补基线实现，也不执行基线。

依据：[完整代码清单与调用点](upstream_prompt_inventory.md)、[pipeline:55–84、197–206、287–325](https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis/blob/4efb4b9bf7e845e180451b43ba29a25e3edaa0e3/llm4pfa/feasibility_analysis_pipeline.py#L55)。
