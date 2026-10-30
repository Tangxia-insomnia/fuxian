# A10 原始构建证据限时查找与通用算法修复准备

结论：**未找到新的A10原始扫描构建证据，继续UNKNOWN / KEEP**。新找到官方仓库 `reproducibility-restore` 分支及论文v1源码包，增加了可追溯公开材料，但没有补齐原CodeQL数据库、完整SARIF路径、扫描checkout与实际构建/预处理身份。查找已停止，后续优先处理通用条件极性与约束合并问题，不为A10放宽门槛。

本阶段只读查找、代码审查和计划编制；没有实施算法修复，没有模型调用、求解器重放、单元测试重跑或全量实验。所有旧结果与留出集保留；3103个既有文件在开始固定，结束完整性校验另存。费用账本仍为1187次调用、估算上界4.491330元，本阶段新增0。

## 1. 限时查找范围与停止记录

查找窗口：`2026-10-29T13:33:52+00:00` 至 `2026-10-29T13:40:26.854715+00:00`，实际 **394.9秒，约6分35秒**，上限900秒。有限来源清单完成后提前结束，未反复访问同一失败来源；查找结束后只进行代码审查与文档整理。见 [search_conclusion.json](<E:/codexconversation/课题研究/reproduction/safety_runs/20261029_build_search_repair_plan/search/search_conclusion.json>)。

| 来源 | 实际完成的检查 | 结果与证据边界 |
|---|---|---|
| 本地官方Git历史 | 19个可达提交、155个历史路径；逐提交文件树和安全的非模型文本关键字检查 | 无CodeQL DB/SARIF/编译配置/tdls.i文件；README和代码路径文字不能证明扫描构建 |
| 当前远端main | `37a1fdc99d59a8af176ae8c93fa4bf0adbeed997`，完整非截断树114个文件 | 仍为PATHAGENT README；没有原构建材料 |
| 远端分支 | 公开返回main和reproducibility-restore；后者21提交中新增的两个提交及其完整文件树均查 | 新增恢复实现和候选缓存，未发现原构建数据库或预处理证据 |
| 标签与发布 | GitHub tags/releases列表 | 均为空，没有可下载的release资产；仅限本次公开返回，不能推断私有或外部材料不存在 |
| 官方benchmark/现有项目文件 | 文件树、已存告警和A10历史上下文身份对比；本地项目文件名清点 | 只有已有告警/片段/缓存；发现的ZIP是本项目先前冻结备份，不是作者数据库 |
| 论文v1 HTML与源码包 | 缓存HTML外链；新取得固定v1源码包并列49成员，检查TeX/Bib相关文本与三个appendix | 有数据集/基线/提示词附录和静态分析查询名称，无实际CodeQL构建命令、配置或A10路径 |

公开只读GET共17次，均为HTTP200；来源是GitHub源码/元数据与arXiv，未连接模型服务。未下载整个内核、创建新CodeQL数据库、生成新构建配置或预处理文件。仓库工作区未fetch/checkout或切换分支。

查找不是全互联网穷举，没有作者私有磁盘或未公开扫描数据库的访问权；未找到不等于作者从未保留。本阶段没有向作者或任何人发送消息。完整下载URL、路径、行范围和SHA-256见 [evidence_index.md](<E:/codexconversation/课题研究/reproduction/safety_runs/20261029_build_search_repair_plan/evidence_index.md>) / [evidence_index.json](<E:/codexconversation/课题研究/reproduction/safety_runs/20261029_build_search_repair_plan/evidence_index.json>)，原响应与同名metadata保留在search/。

## 2. 新公开分支的对应关系

分支 `reproducibility-restore`，头提交 `7fd55480e756db90080ac364105ed835ed30b0f2`，上一新增提交 `b209d667204750e8f3585abc259d9cff00b66597`，日期2026-10-28。远端读取不改变本地采用的旧提交 `4efb4b9bf7e845e180451b43ba29a25e3edaa0e3`。

新增README给出安装/运行入口，明确 `dereferences.json` 缺失，并说明允许空索引可能直接返回True。新配置 [linux-codeql-npd.json](<E:/codexconversation/课题研究/reproduction/safety_runs/20261029_build_search_repair_plan/search/restore_branch/llm4pfa/configs/linux-codeql-npd.json>) 指定source_version=6.9.6、可配置source_root，且将context/constraints标为 **identity-aligned-candidate**，tools为interface-adapter。它描述恢复工程的输入契约，不能证明2025论文实验使用了这些新文件或某次扫描的实际checkout/config。

A10对应关系已具体核对：

- 原benchmark零基行65、index95；新context零基行65、index96。
- 变量sta、完整第一层函数和Sink文本与原告警一致，不能只靠index对齐。
- 新context的这条记录与历史 `29ca96e0d5f860d1f4ce07cd3e54e5e25732d1a1:baseline/NPD-codeql-linux.json` 第95个零基行、index96 **整个记录相同**。因此它恢复了已有历史候选，不是新发现的原扫描数据库。
- `source`内容仅为 `for_each_sta_info(local, addr, sta, tmp)` 与 `sta = sta_info_get(sdata, peer)` 两条代码提示，无绝对Source位置、codeFlow或构建ID。
- 新constraints第65行仍记录 `variable_assignments.text="static void"`；新conditions.py也仍将未提供赋值的索引默认为0。

机器可读映射见 [a10_restore_correspondence.json](<E:/codexconversation/课题研究/reproduction/safety_runs/20261029_build_search_repair_plan/search/a10_restore_correspondence.json>)，原记录副本与下载文件SHA均已保存。index差异作为来源/对齐风险记录，不擅自改正标签或认定候选函数错误。

## 3. 论文补充材料带来的信息

固定URL `https://arxiv.org/src/2506.10322v1` 实际返回gzip源码包，8,539,773字节，SHA-256 **`c02abf4e361ac111cae8f003ea353e2ca1427a75b80720ecdea7bf45f3151457`**。保留原包和49成员清单；只从包内读取指定文本成员，没有执行内容或解压整个工程。

`appendix/dataset.tex`、`appendix/baselines.tex`、`appendix/prompt.tex`提供论文统计/基线设置/提示词。`table/command.tex:10`列NPD的CodeQL `MissingNullTest.ql`，是查询名称，不是数据库创建或编译命令；`ref.bib:2552–2553`指向Linux v6.9.6浏览页面，只能佐证版本名称。没有在所查材料中发现把A10绑定到某个CodeQL库、源码SHA、架构、.config或编译flags的记录。

## 4. 仍然缺失的原始构建证据

1. 原始CodeQL数据库元数据/完整SARIF规则与Source→Sink codeFlow。
2. 原扫描源码checkout commit或源码归档身份；已匹配的v6.9.6函数不能代表整个原构建的提交证明。
3. 原架构、`.config`、编译器版本、include/宏定义/编译参数、compile_commands。
4. 原生成头文件、实际预处理后的tdls翻译单元及与该告警的绑定。

截至本次有限查找，这些缺口无法通过新分支或论文附录补齐。不得用新生成数据库、默认构建或当前源码倒填。维持前阶段A10报告的UNKNOWN/KEEP、未获人工复核批准和filter_evidence_complete=false。本轮不会继续追查该样本；若以后取得真正新材料，再作为独立补充。

## 5. 现有实现中最值得优先修复的内容

完整逐项位置、案例、最小方案和验证方法见 [repair_plan.md](<E:/codexconversation/课题研究/reproduction/safety_runs/20261029_build_search_repair_plan/repair_plan.md>)；结构化清单见 [priority_repairs.json](<E:/codexconversation/课题研究/reproduction/safety_runs/20261029_build_search_repair_plan/priority_repairs.json>)，只读代码摘录和SHA见 [code_review_evidence.md](<E:/codexconversation/课题研究/reproduction/safety_runs/20261029_build_search_repair_plan/code_review_evidence.md>)。

优先级按真实缺陷风险与证据强弱排序：

1. **P0-1 条件极性与合并一致性**：A01的同一分支条件被译成互相冲突的两条断言，再因UNSAT过滤标签1告警。这是已确认的直接错误来源；不是Z3算错。
2. **P0-2 目标与控制范围**：A03重复Sink选最后文本、空格缩进丢条件已有证据；A02局部分配guard未证明覆盖所有路径，不能据此全局过滤。
3. **P0-3 符号身份/类型/赋值版本**：A04把同一指针拆成独立Int/BitVec；A02多次赋值没有版本。先核对并拒绝不一致，再逐步建立有来源的关系。
4. **P1 赋值缺失状态、跨帧状态、逐断言来源**：static void根因明确，但只改占位不会改变当前未消费该字段的推理。跨函数参数名正确不代表状态已传递；SMT重放也不代表源码语义已验证。

没有把A01/A02的原标签冒称独立重标注结论；A02还存在数据/路径不确定性。所有建议是语法、作用域、状态与证据的通用逻辑，不以样本ID或标签设置例外。

## 6. 下一次最小实验

建议 **E01：简单标量条件的极性一致性核对**，只处理R01。使用不含ID特判的合成条件与缓存中的A01/A10响应，定位错误极性并保留正确局部翻译；未知宏/类型/复杂流输出UNKNOWN。保留原SMT和模型输出，不自动删除冲突断言或把诊断公式当新端到端预测。

先用原10条审计集调试，冻结代码后检查原20条固定回归集；manifest SHA **`c4ef793abe5f00437f52c27b6fe545dfa613ed661eb441362e1315f1ed98243d`**保持不变。分别报告FILTER/KEEP/UNKNOWN、真实缺陷操作保留率和误删率、误报过滤率、UNKNOWN率、证据完整性、时间和0模型费用。计划的分母、缓存适用性、单因素控制与停止条件见 [experiment_plan.md](<E:/codexconversation/课题研究/reproduction/safety_runs/20261029_build_search_repair_plan/experiment_plan.md>) / [experiment_plan.json](<E:/codexconversation/课题研究/reproduction/safety_runs/20261029_build_search_repair_plan/experiment_plan.json>)。

原安全v1这30条为0 FILTER、15 KEEP、15 UNKNOWN；标签1操作保留11/11、误删0/11、误报过滤0/19。这只是引用既有结果，非本阶段新实验；零过滤不证明算法判断正确。没有新完整复核证据时，E01也可能保持零FILTER，不能为了抬高过滤率绕开安全门槛。

本阶段至此停止：未修改核心、安全门槛、提示词、样本集或原始结果，未执行E01，也未启动全量实验。
