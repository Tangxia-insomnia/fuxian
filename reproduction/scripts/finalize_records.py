"""Summarize actual saved evidence; do not manufacture experiment results."""
import csv
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import statistics
import subprocess

ROOT = Path(__file__).resolve().parents[1]
rows = json.loads((ROOT / 'results/processed/smoke_results.json').read_text(encoding='utf-8'))
environment = json.loads((ROOT / 'results/raw/environment/environment_checks.json').read_text(encoding='utf-8'))
now = datetime.now(timezone(timedelta(hours=8), 'Asia/Shanghai')).isoformat()
assert all(r['prediction'] is None and not r['end_to_end_attempted'] for r in rows)
component_passed = sum(r['component_status'] == 'extraction_and_prompt_passed' for r in rows)
mean_component = statistics.mean(r['component_duration_seconds'] for r in rows)

stage4 = '''# 阶段 4：小规模实验

状态：未运行（先决条件不满足）。

阶段 3 只完成 5 条样本的离线组件诊断，没有端到端成功运行。依照“先最小样本成功，再 20 条”的门槛，本阶段不抽取或调用 20 条模型实验，也不将 5 条组件诊断混作 pilot。

- 计划数量：约 20；实际选定 pilot 数量：0；端到端尝试：0；成功：0；运行失败：0；阶段阻塞：是。
- 预测分布、平均端到端耗时：不可计算。
- API 调用：0；费用：0 元，预算上限 10 元。
- 阻塞：原始内部工具模块/运行缓存不全；原始模块加载失败；当前进程无 DEEPSEEK_APIkey；用户模型未做接口与定价核验。
- `results/processed/pilot_status.json` 保存机器可读状态；不存在伪造的 20 条预测。

继续条件：取得缺失官方模块或其可核验的官方替代文件、补齐必要上下文和解引用数据；验证 3–5 条真实端到端运行成功；然后配置本地模型凭据、核实模型/价格并确保累计费用不超过 10 元。若需重写核心分析逻辑，不在此次简单复现范围内。
'''
(ROOT / 'logs/stage_04_pilot.md').write_text(stage4, encoding='utf-8')
pilot = {'status': 'not_run_blocked', 'planned_count': 20, 'selected_count': 0, 'attempted': 0, 'successful': 0, 'execution_failed': 0, 'api_calls': 0, 'cost_cny': 0, 'reason': 'No end-to-end smoke test has passed; do not advance to pilot.'}
(ROOT / 'results/processed/pilot_status.json').write_text(json.dumps(pilot, indent=2), encoding='utf-8')
assert (ROOT / 'logs/stage_04_pilot.md').is_file()

metrics = {'timestamp': now, 'status': 'not_computable_no_predictions', 'origin': 'this_reproduction', 'positive_class': 'false_alarm_to_filter', 'selected_smoke_records': len(rows), 'raw_labels': {'0': 3, '1': 2}, 'label_interpretation_status': 'group-level consistent with paper Table 5 and author real_bug_num; not independently verified per record; no supervised evaluation', 'component_diagnostics': {'successful': component_passed, 'failed': len(rows)-component_passed, 'mean_seconds': mean_component}, 'end_to_end': {'attempted': 0, 'successful': 0, 'failed_during_run': 0, 'blocked_before_run': len(rows), 'successful_over_selected': 0.0, 'success_rate_among_attempts': None, 'mean_seconds': None}, 'confusion_matrix': {'row_labels': ['actual_false_alarm', 'actual_real_bug'], 'column_labels': ['predicted_filter', 'predicted_keep'], 'values': [[None, None], [None, None]], 'evaluated_count': 0}, 'false_positive_filter_rate': None, 'real_bug_retention_rate': None, 'real_bug_deletion_rate': None, 'precision_false_alarm_positive': None, 'recall_false_alarm_positive': None, 'f1_false_alarm_positive': None, 'api_calls': 0, 'cost_cny': 0, 'budget_cny': 10, 'full_evaluation_completed': False}
(ROOT / 'results/metrics/reproduction_metrics.json').write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding='utf-8')
with (ROOT / 'results/metrics/confusion_matrix.csv').open('w', newline='', encoding='utf-8-sig') as f:
    writer = csv.writer(f)
    writer.writerows([['actual_label', 'predicted_filter', 'predicted_keep'], ['false_alarm', 'NA', 'NA'], ['real_bug', 'NA', 'NA']])
metric_definitions = '''# 指标定义与本次可计算性

正类定义：应过滤的误报（false alarm）。设：

- A = 真实为误报且预测过滤；B = 真实为误报且预测保留。
- C = 真实为真实缺陷且预测过滤；D = 真实为真实缺陷且预测保留。
- N_FP、N_bug 是当前实验集合内全部已核实标签的误报、真实缺陷数，不因运行失败而删除。

完整预测下：误报过滤率 = A/N_FP；真实缺陷保留率 = D/N_bug；真实缺陷误删率 = C/N_bug。
误报过滤任务 Precision = A/(A+C)，Recall = A/N_FP，F1 = 2PR/(P+R)。分母为 0 时为 NA。
若有未处理/失败/无预测记录，单独报告这些记录及其类别数；不能把它们默认为“保留”或“过滤”，也不能只删掉失败记录后声称完整集合表现。必要时另报明确标注的已成功样本指标及全体覆盖率。

本次 5 条只有组件输出，没有最终预测。因此混淆矩阵各格、过滤率、保留率、误删率、Precision/Recall/F1 全部为 NA（JSON null），并非 0%。混淆矩阵评估记录数为 0。
“0/5 选定样本产生端到端结果”是结果覆盖率，不是精度。实际端到端尝试为 0，尝试内成功率同样不可计算。
作者已发布聚合指标只保存在 author_published_metrics_not_reexecuted.json，不作为本次预测或指标。
'''
(ROOT / 'results/metrics/metric_definitions.md').write_text(metric_definitions, encoding='utf-8')
stage5 = f'''# 阶段 5：评估与汇总

状态：已汇总实际证据；监督评估和完整基准实验未运行。
时间：{now}（Asia/Shanghai）。

## 标签核查

- 原始字段 `result` 不能与流水线新生成的同名预测字段混淆。
- 选用的 CodeQL/Linux NPD 数据 70 条中，result=1 有 22 条，result=0 有 48 条，与论文表 5 和作者聚合结果 real_bug_num=22 一致，支持在此分组暂按 1=真实缺陷、0=误报理解。
- 缺少逐条标注规范；其他分组有 -1、缺失值及与论文数量不一致情况，不能全局套用标签映射。此次没有基于尚未完全核验的标签计算监督指标。

## 本次结果

| 项目 | 实际结果 |
|---|---|
| 离线组件样本 | 5（原始 0 标签 3 条、1 标签 2 条） |
| 条件提取及提示词生成 | {component_passed}/5 成功 |
| 平均本地组件耗时 | {mean_component:.8f} 秒；不含模型/SMT，非方法耗时 |
| 端到端尝试 / 成功 / 运行中失败 | 0 / 0 / 0 |
| 选定样本先决条件阻塞 | 5 |
| 选定样本最终结果覆盖率 | 0/5；不等同模型准确率 |
| 小规模 / 全量实验 | 均未运行 |
| API 调用 / 费用 | 0 / 0 元 |
| 混淆矩阵、误报过滤率、真实缺陷保留率/误删率 | 不可计算，无预测 |
| Precision / Recall / F1 | 不可计算，无预测；正类定义为误报 |

指标公式及失败样本处理规则见 `results/metrics/metric_definitions.md`。混淆矩阵保存为 NA，避免用全零矩阵误导；机器可读汇总见 `results/metrics/reproduction_metrics.json`。

## 与论文的可比性

论文主模型 GPT-4o-mini、364 条/45 个真实缺陷、三类缺陷；当前公开 README/数据不同，用户指定 deepseek-flash 也不同。当前无新模型结果，不能比较论文指标，更不能宣称论文完整复现成功。作者已有结果保留为参考，未运行基线。

## 后续

优先获取缺失官方模块与数据标签/运行缓存说明。公开入口恢复后再补本地 API 凭据，验证模型可用性和费用、完成最小端到端测试，之后才开展 pilot。此次不编写替代核心算法。
'''
(ROOT / 'logs/stage_05_evaluation.md').write_text(stage5, encoding='utf-8')
assert (ROOT / 'logs/stage_05_evaluation.md').is_file()

readme = r'''# LLM4PFA 简单复现记录

当前结论：部分流程可运行，原始端到端实现被公开内部模块缺失阻塞。没有 LLM 预测结果，没有论文完整复现成功结论。

## 固定材料

- 官方仓库：https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis
- 采用提交：`4efb4b9bf7e845e180451b43ba29a25e3edaa0e3`，保存在 `upstream/`，源码未修改。
- 论文：https://arxiv.org/html/2506.10322v1
- 当前远端 main 已改名 PATHAGENT；版本和数据差异见 `logs/stage_01_repository.md`。
- 完整总结：`results/final_report.md`；真实阶段状态：`results/processed/stage_status.json`。

## Windows / PowerShell 运行方法

以下命令在 reproduction 目录执行。若 upstream 和 .venv 已存在，复用即可。

```powershell
git clone https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis.git upstream
git -C upstream switch --detach 4efb4b9bf7e845e180451b43ba29a25e3edaa0e3
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r environment/requirements-reproduction.txt
.\.venv\Scripts\python.exe -B scripts/audit_repository.py
.\.venv\Scripts\python.exe -B scripts/check_environment.py
.\.venv\Scripts\python.exe -B scripts/probe_samples.py
.\.venv\Scripts\python.exe -B scripts/finalize_records.py
```

脚本职责是记录核查和离线诊断，绝不表示原始模型流水线已修复。再次执行会覆盖对应记录；如需保留本次时间测量，先备份 results、configs/smoke_manifest.json 和 logs。

原始入口检查会真实报 `ModuleNotFoundError: No module named 'util'`；不要通过返回固定值的占位模块来伪装成功。

## 已完成与未完成

- 仓库、完整历史、论文与数据清点已保存。
- 独立环境已安装依赖；Z3 SAT/UNSAT、Clang、lizard、数据读取均通过。
- 5 条官方 NPD 样本完成条件提取与提示词生成，包含原始 0/1 标签；预测字段全部为 null。
- LLM 分析、样本 SMT 求解、最终预测、20 条 pilot、全量评测均未执行。API 费用 0 元。
- 离线提取器只做内存导入适配，详见 patches；上游原文件保持不变。

## 模型与凭据

用户配置为 deepseek-flash、https://api.deepseek.com/、密钥环境变量名 DEEPSEEK_APIkey、总预算 10 元，见 configs/experiment_config.example.yaml。
当前进程未配置该变量。请在自己的本地进程环境或 reproduction/.env 中配置，不要发送到聊天中。`.gitignore` 已列出 `.env`、`.env.*`、`.venv/`、`upstream/`。
当前诊断脚本不调用模型，也不自动读取 .env；后续入口修复后才接入读取指定本地变量的模型客户端，并先验证准确模型名、参数和价格。不要执行上游 model.py 自测，它会尝试多个提供商，也不要使用其中任何嵌入式凭据。

## 证据目录

- logs/：五个阶段的真实状态；未运行阶段明确标记阻塞。
- environment/：Python/工具、固定依赖及实际 freeze。
- results/raw/repository/：Git 历史、树、版本差异、论文 HTML/文本、历史上下文清单。
- results/raw/environment/：安装和模块加载输出。
- results/raw/smoke/：5 条样本的实际提取结果及初始提示词。
- results/processed/：数据清单、逐样本 CSV/JSON、阶段状态。
- results/metrics/：本次指标 NA、指标定义，以及单独标记的作者既有指标。

恢复端到端需优先获取 util、LLM4Detection 相关内部模块和必要运行缓存，确认标签映射；本次未重写跨过程分析、未扫描 Linux Kernel、未开展算法改进或平台接入。
'''
# Render normal PowerShell backslashes from the ASCII-safe source literal.
readme = readme.replace(r'\u005c', chr(92))
(ROOT / 'README.md').write_text(readme, encoding='utf-8')
plan = '''# 复现计划与执行门槛

1. 阶段 1：固定公开历史提交，核查论文、代码、数据及已有结果；保存日志并确认文件存在。已完成。
2. 阶段 2：建立独立依赖环境，测试 Z3、Clang、数据和官方入口。环境测试已完成，入口被内部模块缺失阻塞。
3. 阶段 3：固定种子 20261025、5 条 NPD 官方样本；先验证提取/提示词，再验证真实 LLM 和 SMT 及预测。只完成前两项；端到端尚未运行。
4. 阶段 4：只有最小端到端测试成功才选约 20 条运行 pilot，保留失败；当前未达到门槛，未执行。
5. 阶段 5：核实标签后评估并汇总；当前仅汇总实际证据，监督指标为 NA。

核心原则：保持 upstream 未修改，所有必要适配单独记录；不使用 mock LLM、不填补标签、不把缺失上下文触发的默认返回当成预测。公开核心模块不可恢复时，不转为自行重写。
模型为用户指定 deepseek-flash，费用上限 10 元；实际调用前须具备本地 DEEPSEEK_APIkey、核验模型/定价并设置调用上限，无法核实费用时不调用。现阶段模型费用为 0。
'''
(ROOT / 'reproduction_plan.md').write_text(plan, encoding='utf-8')
stages = {'timestamp': now, 'stage_01': 'repository_audit_completed_with_uncertainty', 'stage_02': 'local_environment_passed_upstream_entry_blocked', 'stage_03': 'five_offline_component_diagnostics_completed_end_to_end_blocked', 'stage_04': 'not_run_prerequisite_not_met', 'stage_05': 'evidence_summary_completed_supervised_evaluation_not_run', 'paper_reproduction_success': False}
(ROOT / 'results/processed/stage_status.json').write_text(json.dumps(stages, ensure_ascii=False, indent=2), encoding='utf-8')
sample_ids = ', '.join(f"row {r['row_position']} / index {r['original_index']}" for r in rows)
report = f'''# LLM4PFA 简单复现最终阶段报告（部分完成）

生成时间：{now}（Asia/Shanghai）。

## 结论与研究目标

目标为复现《Minimizing False Positives in Static Bug Detection via LLM-Enhanced Path Feasibility Analysis》的公开原实现，不改进算法、不接平台。
结论：官方数据和条件提取/提示词组件可运行；公开内部模块不足使原始端到端入口无法运行。此次没有完成 LLM 分析和样本 SMT 求解，不能宣称复现了论文效果。提供 API Key 本身也不能解决代码缺失。

## 代码、环境及模型

- 仓库：https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis
- 固定历史提交：`4efb4b9bf7e845e180451b43ba29a25e3edaa0e3`；当前 main 为 `37a1fdc99d59a8af176ae8c93fa4bf0adbeed997`，已将 README 方法名改为 PATHAGENT 并清空部分路径。
- 采用历史版本仍不足以证明与论文逐项一致；该版 5 份 Python 源码与 3 月提交相同，但论文运行环境和完整内部实现未公开。
- 环境：{environment['os']}；Python {environment['python'].splitlines()[0]}；独立 `.venv`。
- 关键依赖：`{environment['packages']}`；作者没有固定版本，本次选择已记录，完整 freeze 在 environment/dependencies.txt。
- 用户服务：deepseek-flash、https://api.deepseek.com/、凭据变量 DEEPSEEK_APIkey、总预算 10 元。当前变量未配置、服务未验证、没有付费调用。不记录凭据值，不使用作者模型封装中的字面量配置。

## 数据集与样本

论文 v1 正文报告 NPD/UAF/BOF 三类、364 条告警、45 个真实缺陷；仓库 README 报五类、443 条、47 个真实缺陷。实际文件还含重复、缺失标签和 -1，不能视为与论文相同集合。
`UBI` 与 `UUA` 文件完全重复；Cppcheck/Linux 文件有 594 条，其中 526 条无 result、3 条 -1；CodeQL/OpenSSL NPD 也有 1 条 -1。原论文对应数据文件从 3 月到采用版本未改变，回退不能自动补全。

此次诊断从 CodeQL/Linux NPD 的 70 条中，用固定种子 20261025 选择 result=0 三条、result=1 两条：{sample_ids}。该分组 1 标签数量 22 与论文及作者 real_bug_num=22 相符，仅作为暂定映射依据；没有擅自评估其他标签或补标。
历史 baseline 文件可提供部分函数调用链，但缺少标签、位置以及完整运行工具，不足以恢复论文数据和完整流水线。未下载或扫描 Linux Kernel。

## 实际完成阶段

| 阶段 | 实际完成情况 |
|---|---|
| 1 仓库 | 完成版本、全历史、论文、源码、数据和作者结果核查；存在论文对应关系不确定性 |
| 2 环境 | Z3 SAT/UNSAT、Clang、lizard、文件读取通过；原始入口导入失败 |
| 3 最小测试 | 5/5 样本离线提取/提示词成功；端到端尝试 0、成功 0、阻塞 5 |
| 4 小规模 | 未运行，尚未通过阶段 3 门槛 |
| 5 评估 | 完成证据汇总；监督指标和全量评估未运行 |

## 指标、时间与费用

没有最终预测，混淆矩阵四格均 NA，评估记录数为 0。误报过滤率、真实缺陷保留率/误删率、Precision、Recall、F1 全部不可计算。
正类定义为应过滤的误报。设 A=误报被过滤、B=误报被保留、C=真实缺陷被过滤、D=真实缺陷被保留；定义分别为 A/N_FP、D/N_bug、C/N_bug、A/(A+C)、A/N_FP、2PR/(P+R)。无预测/失败必须保留并单列，不能当作有效分类。
5/5 组件成功不代表端到端成功率。当前选定样本最终结果覆盖率为 0/5；实际尝试数为 0，因此尝试内成功率 NA。
平均本地提取/提示词组件耗时 {mean_component:.8f} 秒，不含 LLM/SMT，不能与论文方法耗时比较；端到端平均耗时 NA。
模型 API 调用 0，token 使用 0，模型费用 0 元，未消耗 10 元预算。

## 失败、修改与解决办法

- 原始 feasibility_analysis_pipeline.py 实际模块加载失败：`ModuleNotFoundError: No module named 'util'`。extract_util_plus.py、model.py 实际失败于缺失 `LLM4Detection`。已保留原始 stderr。
- 不只是目录改名：缺失函数体检索、函数调用/参数映射、解引用定位、ContextHelper/Conditions、工具 schema 和缓存生成逻辑。历史缓存脚本也依赖这些模块，不能通过安装 PyPI 包解决。
- 发现部分异常会默认返回 True；如果绕过缺失上下文，可能伪装成“保留告警”，故不这样构造实验结果。
- 上游源码修改：无。组件诊断仅对 extract_util_plus.py 内存 AST 删除缺失类型导入、推迟注解求值，函数体完全不变；未调用依赖这些类型的辅助函数。此适配仅证明局部组件可运行，不等于完整修复，详见 patches/component_probe_adaptation.json。
- Windows venv 缺少时区数据导致诊断脚本首次启动失败，改用显式 UTC+08:00；其余安装/命令问题及处理见 results/raw/environment/setup_errors.md。
- 依赖安装完成，pip check 无冲突；未修改已有研究项目或上游代码。

## 与论文结果差异及后续工作

原论文主模型 GPT-4o-mini、temperature=0；当前用户模型 deepseek-flash 不同，服务也未验证。数据版本、公开路径/工具与论文不完全一致，不能用已有聚合结果替代本次运行。LLMDFA 和 LLM4SA 只保留作者结果，没有重跑。
下一步需取得官方缺失模块、论文准确数据子集/标签含义与上下文缓存说明。恢复原始入口后，配置本地凭据并验证模型名、参数和价格；先做 3–5 条真实端到端测试，再约 20 条 pilot。只有资源和预算允许才考虑完整基准。
若拿不到缺失核心模块，此次适宜停在“公开实现可复现性检查和局部组件验证”。重写跨过程分析将成为另一项实现工作，超出本次简单复现。

所有逐样本结果、日志及机器可读状态见 reproduction/README.md；此次无论文完整复现成功结论。
'''
(ROOT / 'results/final_report.md').write_text(report, encoding='utf-8')
print(json.dumps({'logs': {str(i): (ROOT / f'logs/stage_0{i}_{name}.md').is_file() for i, name in [(1, 'repository'), (2, 'environment'), (3, 'smoke_test'), (4, 'pilot'), (5, 'evaluation')]}, 'final_report_exists': (ROOT / 'results/final_report.md').is_file(), 'predictions': 0, 'api_calls': 0, 'cost_cny': 0}, ensure_ascii=True))
