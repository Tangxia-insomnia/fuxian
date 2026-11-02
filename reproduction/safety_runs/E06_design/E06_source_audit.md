# E06 现有跨函数处理能力审查

状态：只读审查，2026-11-02。发布基线为 `6452442e492293f42b6b0cf4930dca6685d0c6d7`；官方代码冻结为 `4efb4b9bf7e845e180451b43ba29a25e3edaa0e3`；论文 arXiv:2506.10322v1。4456 个原有非凭据文件的起始哈希见 [baseline_state.json](baseline_state.json)，本次阅读的 60 个主要证据文件哈希见 [evidence_manifest.json](evidence_manifest.json)。以下能力描述不等于本阶段运行了模型、编译器或测试。

## 1. 论文、公开实现与本项目适配应分开

论文 PDF p5 §3.2.2 定义 P 为 Source 语句执行后的初始状态，包含 Source 所需前提和执行后条件；后续函数还应纳入前一函数中与传入参数有关的可行路径约束。NPD 示例沿调用轨迹传播 NULL 状态。原文缓存中可定位：`results/raw/repository/paper_text.txt` 的 “P denotes the required initial states” 段；页码来源为既有 `agent_reproduction_audit/smt_z3_audit/initial_state_p_analysis.md:7–17` 的 PDF 核验。

同节说明按不同 P 缓存函数调用返回值的符号范围，避免重复分析。这是**带前提的函数分析结果缓存**，不是 C 内存模型。论文 p11 Appendix C 的 P01/P02 提示词仍以 `[P]` 占位，未公开完整的参数身份、状态版本、内存别名、调用副作用或路径合流实现。不能把下述 E06 方案说成作者已公开算法。当前单 Agent 检索能力也不能代替这些语义机制。

## 2. 逐项代码证据

所有代码路径相对 `reproduction/`，行号为当前未修改文件的一基行号。

| 位置 | 已具备的能力 | 尚不能证明的事 |
| --- | --- | --- |
| `completion/context.py:34–57` | 按 token/括号拆分调用和实参；保存调用文本与字符区间 | 非 C 类型化 AST；标识符调用可能是宏或函数指针；仅排除成员间接调用不足以证明直接调用 |
| `context.py:60–68` | lizard 识别单个函数定义 | 不提供编译器 DeclRef、链接身份、完整类型/宏展开或 CFG |
| `context.py:75–100` | 以实参文本相等与参数序号映射被跟踪变量；歧义时报错 | 只能得到名字对应；不比较完整签名/类型，也没有调用前后版本；不是两个局部变量是同一存储单元的证明 |
| `context.py:134–139` | 优先在样本调用链内选择唯一函数体，否则用数据集内索引 | “索引内唯一”不等于真实编译单元的被调用定义唯一；未证明链接/宏配置 |
| `context.py:141–181` | 按变量、Sink、首函数源码匹配历史上下文，检查调用链、保存 body SHA-256 和 frame | 不是原 CodeQL codeFlow/CFG；没有统一 Source 状态 P、内存/别名或前后状态对象 |
| `upstream/llm4pfa/feasibility_analysis_pipeline.py:159–162` | 每层重新提取目标条件和提前退出条件 | 会覆盖递归参数传入的 `target_conditions`、`early_jump_constraints`，没有确定性组合调用方 P 与被调方条件 |
| `pipeline.py:174–179` | 每层将 `var_name + " == 0"` 交给 U02 | 没有指出该名字对应哪一次赋值/哪个调用状态；每帧重新作 NULL 假设不等于忠实传播同一个值 |
| `pipeline.py:374–433` | 获取下一函数、目标参数及 Sink，再递归 | 原版从裸函数名取实参、按文本/字典筛条件；没有 typed substitution、调用上下文或状态转移关系 |
| `completion/engine.py:50–68,183–210` | 修正实参提取入口、显式帧链终止和部分文本匹配；验证下一帧变量/Sink 对应 | 没有修复第 159–162 行的覆盖；没有统一传播环境或返回/内存摘要 |
| `completion/engine.py:69–86,227–247` 与 `completion/constraint_bundle.py` | E03 将同帧原始 B+Δ 完整拼接，U10 前后均有结构门控 | 这是同帧结构保留，不是跨帧状态版本或源码语义证明；U07/U09 等旧路径也不能据此被视为统一语义契约已覆盖 |
| `upstream/llm4pfa/extract_util_plus.py:1137–1145,1180–1186` | 记录条件、原文和提前跳转信息 | 调用方传 `None` 时 assignment index 默认 0，可能把函数签名当“赋值”；这是已有占位异常来源，不可当作 Source 或 reaching definition |
| `extract_util_plus.py:4,1202–1212` | 有 `clang.cindex` 导入及另一个 AST 辅助入口 | 当前 engine 调用的是 `extract_conditions` 文本入口。存在 libclang 并不证明主路径使用真实编译参数；另一个入口根据 ifdef 推测 `-D` 也不是原始构建证据 |
| `pipeline.py:23–27,378` | 加载 `result_memory_cache`，有一处注释引用 | 未见活动的、以 P/类型/别名/版本为键的结果摘要查询/写入；函数体缓存 `127–138` 按函数名，不能代替状态摘要 |
| `harness_bridge/tools.py:169–210` | 只读检索告警上下文/函数源码，返回哈希、来源、selection_tier，歧义不选 | 不输出已验证参数映射或状态传播；E06 请求仍须同时带 dataset_id 与 position，不扩大 MCP 权限 |
| `safety_runs/E05_polarity_variable_identity/semantics.py:49,304,346,388` | 局部源码身份、极性和成员混淆静态诊断 | 显式将赋值、地址逃逸、调用效果和复杂 CFG 留为 UNKNOWN；不是状态传播器，也未接入运行中 engine |

## 3. 最主要的失效链

1. 名称/位置映射没有绑定“调用前当前值”。即使 `p` 正确对应 `item`，也没有区分 p 在初始化、重新分配、检查后的值。
2. 跨帧递归传入的条件在下层被覆盖，随后再次按参数名字建立 NULL 假设。缺少单独保存的 caller pre-state 与调用边映射。
3. 同名 SMT 变量没有函数/调用/赋值版本命名空间。把所有帧约束简单相与会产生不存在的矛盾，也可能漏掉真正的关系。
4. 没有内存、返回值和副作用摘要：按值参数的局部赋值与通过 `&p` 修改 caller slot 没有统一的区分。
5. LLM 的自然语言推理/生成文本并非上述关系的确定性证据。E03 可以完整保留一组语义错误的约束，E04-ND 已说明这一点。

优先级应是“调用点—声明—类型—当前值版本”的证据契约，而不是先把更多字符串约束拼接进下一帧。

## 4. 当前数据和工具边界

- 固定 20 条保存 23 帧：3 条多帧、15 条单帧、2 条无可用帧；多帧共有 5 条相邻调用边。见 [candidate_inventory.json](candidate_inventory.json)。这些是源码材料统计，没有执行传播测试。
- 现有非凭据文件清单中未找到 `compile_commands.json`、SARIF、`.i`、`.bc` 等精确文件标记；仅说明当前本地证据范围，不证明作者其他位置不存在。
- 当前 `.venv` 已安装 `libclang==18.1.1`、`lizard==1.17.31`，clang Python 包可发现。PATH 未发现 clang/clang++/clang-cl/llvm-config。本阶段没有加载 libclang 库或进行 AST parse 测试，不把包可见性写成可编译/可解析成功。
- 对真实 Linux/OpenSSL/Libav 的宏、typedef、成员布局和链接绑定，需要对应版本头文件、构建参数和配置。新建的自包含合成 TU 可以测试设计，但不能代替原始扫描构建。

## 5. 本阶段结论

已有代码足以提供部分文本调用链和源码证据，不足以提供可靠的跨函数状态转移。E06 应先做独立、可拒绝的传播诊断侧层；保持旧 Prompt、MCP、E01–E05 和安全门槛不变。正式代码开发与原 pipeline 接入均尚未开始。
