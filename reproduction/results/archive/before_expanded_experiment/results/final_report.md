# LLM4PFA 补全版简单复现报告

时间：2026-10-26T00:36:59.303117+08:00。

## 结论

已按用户授权补写缺失支撑，运行真实模型及 SMT 流程：smoke 成功 5/5，pilot 成功 16/20，阻塞 4，最终运行失败 0。
这是“作者公开流程＋明确补全实现”的运行结果，不能称为作者原版或论文完整复现。没有训练、算法改进或平台接入，也没有扫描整个 Linux Kernel。

## 代码与环境

采用官方提交 `4efb4b9bf7e845e180451b43ba29a25e3edaa0e3`；仓库 https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis ，论文 https://arxiv.org/html/2506.10322v1 。上游代码未修改。
最新 main `37a1fdc…` 已转为 PATHAGENT 描述并清空路径，故固定历史版本。作者源码与论文对应仍存在不确定性。
Windows、Python 3.11.5、独立 .venv；关键依赖 Z3 4.13.4.0、libclang 18.1.1，完整 freeze 见 environment/dependencies.txt。
本地 10 项基础设施测试通过，实际输出见 results/raw/completed/completion_tests_final.txt。这些测试不计入基准实验结果。
最终文件、样本、实际 SMT、调用账本和指标重算核验见 results/raw/completed/final_verification.json；源码及数据 SHA-256 见 configs/completed_run_identity.json。核验脚本不调用模型。
真实模型 deepseek-flash，官方文档对应 DeepSeek-V4.1-Flash-1017；非思考模式，temperature=0.0000001，输出上限 3072 token。实际响应模型名和请求参数逐调用保存。模型不同于论文主实验 GPT-4o-mini。

## 补全与行为差异

复用作者条件提取、提示词、主迭代分析函数；补写历史上下文匹配、函数查找、有限调用/参数识别、目标定位、模型客户端和批量入口。完整范围见 logs/stage_06_completion.md、patches/completed_pipeline.diff。
修复原函数的条件迭代删除、字典条件过滤、goto 标签、基础 SMT 未执行、求解修复耗尽继续、上下文缺失默认返回 True 等问题。错误处理修复会影响输出，未把它们描述为完全无行为影响。
函数检索限于公开样本和历史调用链；并非完整 C 语义解析，不支持任意别名/函数指针/宏展开。作者历史最终 sink 若为宏/调用，按其边界分析并显式标记，不声称已证明宏内部真实解引用。
SMT 子进程记录实际 Solver.check 与 SMT2，拒绝 unknown、无求解和非布尔结果；LLM 生成的约束可能仍有语义错误，成功执行不等于正确表达 C 路径。

## 数据与抽样

论文三类缺陷共 364 条/45 个真实缺陷；当前 README 与实际 JSON 有额外类别、重复文件、缺失标签及 -1，无法直接恢复完整论文集合。
本次只用官方 CodeQL/Linux NPD 的 70 条有 0/1 标签样本。smoke 固定 3 个误报、2 个真实缺陷；pilot 固定 10 个误报、10 个真实缺陷，随机种子 20261025、排除 smoke，不依据模型输出或可运行性筛选。
smoke 和 pilot 的确切行号、原始 index、文件及配置分别保存在 configs/smoke_manifest.json、configs/completed_pilot_manifest.json 和 configs/completed_experiment.json。
先前纯组件阶段和最初失败尝试全部保留。未运行 LLMDFA/LLM4SA 基线或完整基准。

## 补全版实际评估更新

时间：2026-10-26T00:36:59.303117+08:00。以下是补全实现结果，原始审计阶段及旧 NA 指标保留在 archive 和原文件中，不相互替代。

| 项目 | 5 条 smoke | 20 条 pilot |
|---|---:|---:|
| 已记录样本 | 5 | 20 |
| 最终成功 | 5 | 16 |
| 最终运行失败 | 0 | 0 |
| 上下文阻塞 | 0 | 4 |
| 成功处理率 | 100.00% | 80.00% |
| 误报过滤率 | 66.67% | 50.00% |
| 真实缺陷保留率 | 100.00% | 70.00% |
| 真实缺陷误删率 | 0.00% | 10.00% |
| 误报正类 Precision | 100.00% | 83.33% |
| 误报正类 Recall | 66.67% | 50.00% |
| 误报正类 F1 | 80.00% | 62.50% |
| 平均当前尝试耗时（所有选定样本，秒） | 12.12122300000001 | 9.882719404999921 |

所有实际模型请求（包括早期失败及重跑）：191 次；按官方较高费率和 usage 得到的费用保守上界：0.905162 元，低于 10 元。不是账户账单数值。
首轮执行器问题产生的失败尝试：smoke 4 次、pilot 1 次，全部在 attempt_history 和 raw 中保留；没有为了提高指标删除样本。上表预测用实现修复后的最终尝试，费用统计包括所有尝试。

标签使用官方 Linux NPD 分组 result=0 为误报、1 为真实缺陷，其 22 个 1 标签与论文表 5/作者 real_bug_num=22 一致；未对 -1 或缺失标签进行推断，未声称人工独立复核每条缺陷。
正类为误报。混淆矩阵行是真实误报/真实缺陷，列为过滤/保留；失败另列未分类。设 A/B/C/D 为这四格，过滤率=A/N_FP，保留率=D/N_bug，误删率=C/N_bug，Precision=A/(A+C)，Recall=A/N_FP，F1=2PR/(P+R)。无预测行仍留在全体分母中；有缺失时比例只表示已确认结果并同时报告覆盖率/上下界。
pilot 有 2 条误报和 2 条真实缺陷未分类。考虑这些未知结果后，全部选定样本的误报过滤率可能范围为 50.00%–70.00%，真实缺陷保留率为 70.00%–90.00%；表中数值仅计已确认的过滤/保留，未把阻塞默认判为保留。
本次仅为单一项目、单一工具、单一缺陷类型的分层小样本测试，类别比例不是原论文自然分布，不能外推总体表现。模型为 DeepSeek-V4.1-Flash-1017，公开实现有补全及错误处理修复，也不等同 GPT-4o-mini 论文设置。


## 混淆矩阵

pilot（行=真实类别，列=过滤/保留）：

| 真实类别 | 过滤 | 保留 | 未分类 |
|---|---:|---:|---:|
| 误报 | 5 | 3 | 2 |
| 真实缺陷 | 1 | 7 | 2 |

## 错误与未完成部分

- `NPD/codeql/kernel69:row=16:index=34`：label=0，输出=keep，状态=success；错误=None；详见 `results/raw/completed/pilot/row_016`。
- `NPD/codeql/kernel69:row=22:index=41`：label=0，输出=keep，状态=success；错误=None；详见 `results/raw/completed/pilot/row_022`。
- `NPD/codeql/kernel69:row=59:index=89`：label=0，输出=keep，状态=success；错误=None；详见 `results/raw/completed/pilot/row_059`。
- `NPD/codeql/kernel69:row=11:index=23`：label=1，输出=filter，状态=success；错误=None；详见 `results/raw/completed/pilot/row_011`。
- `NPD/codeql/kernel69:row=4:index=4`：label=0，输出=None，状态=blocked_context；错误=Expected one function definition, found 0；详见 `results/raw/completed/pilot/row_004`。
- `NPD/codeql/kernel69:row=31:index=51`：label=1，输出=None，状态=blocked_context；错误=Function ip6_route_mpath_should_notify: 0 distinct available definitions；详见 `results/raw/completed/pilot/row_031`。
- `NPD/codeql/kernel69:row=43:index=68`：label=0，输出=None，状态=blocked_context；错误=Cannot uniquely locate intermediate call site；详见 `results/raw/completed/pilot/row_043`。
- `NPD/codeql/kernel69:row=50:index=76`：label=1，输出=None，状态=blocked_context；错误=Cannot uniquely locate intermediate call site；详见 `results/raw/completed/pilot/row_050`。

早期 4 条 smoke 因我补写的执行器不兼容函数内 z3 导入而失败；修复并新增测试后重跑，所有失败记录、实际模型响应与费用保留。未根据标签修改算法或调整预测。
其他运行错误/阻塞以逐样本记录为准。全量数据、跨类型适配、与作者原程序一致性验证均未完成。
pilot 中另 1 条因补全执行器漏列标准 Z3 Function 接口失败；新增接口和未解释谓词 UNSAT 测试后只重跑该失败样本，未修改模型生成约束。先前 5 次失败尝试全部存档并计入费用。
真实缺陷误删例 row 11 的实际 SMT 同时加入 skb == 0 和 skb != 0，得到 UNSAT。其原函数含循环、多次赋值及 goto；尚未人工证明这两个约束对应同一执行时刻，需检查约束提取和模型编码的语义，不能因求解器成功运行就认定过滤正确。
未进入全量评测：20 条中仍有 4 条不能可靠定位上下文，处理覆盖率为 80.00%；本次有界补全的适用范围尚不足以支撑完整基准。

## 后续

优先人工检查误删真实缺陷的路径、LLM 约束中的赋值时序和宏语义，向作者获取缺失官方模块/准确论文数据集合（本次未发送外部消息）。如继续扩大实验，应先确认上述误差和补全实现的有效性；不能仅凭小样本指标宣称论文效果复现。
