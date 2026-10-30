"""Publish final evidence for the completed implementation, preserving originals."""
import csv
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from completion.metrics import evaluate
from completion.model import save


def load(name, default):
    p = ROOT / name
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else default


def pct(value):
    return 'NA' if value is None else f'{100*value:.2f}%'


now = datetime.now(timezone(timedelta(hours=8))).isoformat()
ledger = load('results/raw/completed/budget_ledger.json', {'calls': [], 'cost_upper_bound_cny': 0})
all_metrics = {'timestamp': now, 'implementation': 'author_pipeline_with_documented_completion_v1', 'phases': {}, 'api_calls_all_attempts': len(ledger['calls']), 'cost_upper_bound_cny_all_attempts': ledger['cost_upper_bound_cny'], 'exact_account_billing_known': False}
all_rows, all_history = {}, {}
for phase in ['smoke', 'pilot']:
    rows = load(f'results/processed/completed_{phase}.json', [])
    history = load(f'results/processed/completed_{phase}_attempt_history.json', [])
    all_rows[phase], all_history[phase] = rows, history
    metrics = evaluate(rows)
    metrics['prior_failed_attempts'] = len(history)
    metrics['api_calls_including_prior_attempts'] = metrics['api_calls_final_attempts'] + sum(r['api_calls'] for r in history)
    metrics['wall_seconds_including_prior_attempts'] = sum(r['duration_seconds'] for r in rows+history)
    all_metrics['phases'][phase] = metrics
    save(ROOT / f'results/metrics/completed_{phase}_metrics.json', metrics)
    with (ROOT / f'results/metrics/completed_{phase}_confusion_matrix.csv').open('w', newline='', encoding='utf-8-sig') as f:
        w=csv.writer(f);w.writerow(['actual_label','predicted_filter','predicted_keep','unclassified'])
        for category, values in zip(['false_alarm','real_bug'], metrics['confusion_matrix']['values']):
            w.writerow([category,*values,metrics['missing_prediction_by_label'][category]])
save(ROOT / 'results/metrics/completed_metrics.json', all_metrics)
sm, pm = [all_metrics['phases'][p] for p in ['smoke','pilot']]
gate = load('results/processed/completed_pilot_gate.json', {})
stage_summary = f'''## 补全版实际评估更新

时间：{now}。以下是补全实现结果，原始审计阶段及旧 NA 指标保留在 archive 和原文件中，不相互替代。

| 项目 | 5 条 smoke | 20 条 pilot |
|---|---:|---:|
| 已记录样本 | {sm['sample_count']} | {pm['sample_count']} |
| 最终成功 | {sm['successful']} | {pm['successful']} |
| 最终运行失败 | {sm['failed']} | {pm['failed']} |
| 上下文阻塞 | {sm['blocked']} | {pm['blocked']} |
| 成功处理率 | {pct(sm['success_rate'])} | {pct(pm['success_rate'])} |
| 误报过滤率 | {pct(sm['false_positive_filter_rate'])} | {pct(pm['false_positive_filter_rate'])} |
| 真实缺陷保留率 | {pct(sm['real_bug_retention_rate'])} | {pct(pm['real_bug_retention_rate'])} |
| 真实缺陷误删率 | {pct(sm['real_bug_deletion_rate'])} | {pct(pm['real_bug_deletion_rate'])} |
| 误报正类 Precision | {pct(sm['precision'])} | {pct(pm['precision'])} |
| 误报正类 Recall | {pct(sm['recall'])} | {pct(pm['recall'])} |
| 误报正类 F1 | {pct(sm['f1'])} | {pct(pm['f1'])} |
| 平均当前尝试耗时（所有选定样本，秒） | {sm['mean_wall_seconds_all_selected']} | {pm['mean_wall_seconds_all_selected']} |

所有实际模型请求（包括早期失败及重跑）：{len(ledger['calls'])} 次；按官方较高费率和 usage 得到的费用保守上界：{ledger['cost_upper_bound_cny']:.6f} 元，低于 10 元。不是账户账单数值。
首轮执行器问题产生的失败尝试：smoke {len(all_history['smoke'])} 次、pilot {len(all_history['pilot'])} 次，全部在 attempt_history 和 raw 中保留；没有为了提高指标删除样本。上表预测用实现修复后的最终尝试，费用统计包括所有尝试。

标签使用官方 Linux NPD 分组 result=0 为误报、1 为真实缺陷，其 22 个 1 标签与论文表 5/作者 real_bug_num=22 一致；未对 -1 或缺失标签进行推断，未声称人工独立复核每条缺陷。
正类为误报。混淆矩阵行是真实误报/真实缺陷，列为过滤/保留；失败另列未分类。设 A/B/C/D 为这四格，过滤率=A/N_FP，保留率=D/N_bug，误删率=C/N_bug，Precision=A/(A+C)，Recall=A/N_FP，F1=2PR/(P+R)。无预测行仍留在全体分母中；有缺失时比例只表示已确认结果并同时报告覆盖率/上下界。
pilot 有 {pm['missing_prediction_by_label']['false_alarm']} 条误报和 {pm['missing_prediction_by_label']['real_bug']} 条真实缺陷未分类。考虑这些未知结果后，全部选定样本的误报过滤率可能范围为 {pct(pm['false_positive_filter_rate_bounds'][0])}–{pct(pm['false_positive_filter_rate_bounds'][1])}，真实缺陷保留率为 {pct(pm['real_bug_retention_rate_bounds'][0])}–{pct(pm['real_bug_retention_rate_bounds'][1])}；表中数值仅计已确认的过滤/保留，未把阻塞默认判为保留。
本次仅为单一项目、单一工具、单一缺陷类型的分层小样本测试，类别比例不是原论文自然分布，不能外推总体表现。模型为 DeepSeek-V4.1-Flash-1017，公开实现有补全及错误处理修复，也不等同 GPT-4o-mini 论文设置。
'''
with (ROOT / 'logs/stage_05_evaluation.md').open('a',encoding='utf-8') as f:f.write('\n\n'+stage_summary)
for phase, logname in [('smoke','stage_03_smoke_test.md'),('pilot','stage_04_pilot.md')]:
    m=all_metrics['phases'][phase]
    with (ROOT/'logs'/logname).open('a',encoding='utf-8') as f:f.write(f"\n\n## 补全版阶段汇总\n\n已记录 {m['sample_count']} 条；最终成功 {m['successful']}、失败 {m['failed']}、阻塞 {m['blocked']}；先前失败尝试 {m['prior_failed_attempts']}，保留在 attempt_history。机器可读结果见 results/processed/completed_{phase}.json。\n")

fp_examples = [r for r in all_rows['pilot'] if r['label']==0 and r['prediction']=='keep' and r['status']=='success']
bug_examples = [r for r in all_rows['pilot'] if r['label']==1 and r['prediction']=='filter' and r['status']=='success']
failures = [r for r in all_rows['pilot'] if r['status']!='success']
examples = '\n'.join(f"- `{r['sample_id']}`：label={r['label']}，输出={r['prediction']}，状态={r['status']}；错误={r.get('error')}；详见 `{r['raw_output']}`。" for r in (fp_examples+bug_examples+failures)) or '- pilot 未发现上述失败类型；这不表示总体无错误。'
report = f'''# LLM4PFA 补全版简单复现报告

时间：{now}。

## 结论

已按用户授权补写缺失支撑，运行真实模型及 SMT 流程：smoke 成功 {sm['successful']}/{sm['sample_count']}，pilot 成功 {pm['successful']}/{pm['sample_count']}，阻塞 {pm['blocked']}，最终运行失败 {pm['failed']}。
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

{stage_summary}

## 混淆矩阵

pilot（行=真实类别，列=过滤/保留）：

| 真实类别 | 过滤 | 保留 | 未分类 |
|---|---:|---:|---:|
| 误报 | {pm['confusion_matrix']['values'][0][0]} | {pm['confusion_matrix']['values'][0][1]} | {pm['missing_prediction_by_label']['false_alarm']} |
| 真实缺陷 | {pm['confusion_matrix']['values'][1][0]} | {pm['confusion_matrix']['values'][1][1]} | {pm['missing_prediction_by_label']['real_bug']} |

## 错误与未完成部分

{examples}

早期 4 条 smoke 因我补写的执行器不兼容函数内 z3 导入而失败；修复并新增测试后重跑，所有失败记录、实际模型响应与费用保留。未根据标签修改算法或调整预测。
其他运行错误/阻塞以逐样本记录为准。全量数据、跨类型适配、与作者原程序一致性验证均未完成。
pilot 中另 1 条因补全执行器漏列标准 Z3 Function 接口失败；新增接口和未解释谓词 UNSAT 测试后只重跑该失败样本，未修改模型生成约束。先前 {len(all_history['smoke'])+len(all_history['pilot'])} 次失败尝试全部存档并计入费用。
真实缺陷误删例 row 11 的实际 SMT 同时加入 skb == 0 和 skb != 0，得到 UNSAT。其原函数含循环、多次赋值及 goto；尚未人工证明这两个约束对应同一执行时刻，需检查约束提取和模型编码的语义，不能因求解器成功运行就认定过滤正确。
未进入全量评测：{pm['sample_count']} 条中仍有 {pm['blocked']} 条不能可靠定位上下文，处理覆盖率为 {pct(pm['success_rate'])}；本次有界补全的适用范围尚不足以支撑完整基准。

## 后续

优先人工检查误删真实缺陷的路径、LLM 约束中的赋值时序和宏语义，向作者获取缺失官方模块/准确论文数据集合（本次未发送外部消息）。如继续扩大实验，应先确认上述误差和补全实现的有效性；不能仅凭小样本指标宣称论文效果复现。
'''
(ROOT / 'results/final_report.md').write_text(report,encoding='utf-8')

readme = f'''# LLM4PFA 简单复现：补全实现

已在保留作者原代码的前提下补写缺失支撑，并真实运行模型和 SMT。当前 smoke {sm['successful']}/{sm['sample_count']}、pilot {pm['successful']}/{pm['sample_count']}；最终报告见 results/final_report.md。此为补全版小样本实验，不是作者原版或完整论文复现。

## 运行

Windows / PowerShell，在本目录运行：

```powershell
.\\.venv\\Scripts\\python.exe -B -m unittest completion.test_completion -v
.\\.venv\\Scripts\\python.exe -B scripts/run_completed.py --phase preflight
.\\.venv\\Scripts\\python.exe -B scripts/run_completed.py --phase all
.\\.venv\\Scripts\\python.exe -B scripts/report_completed.py
.\\.venv\\Scripts\\python.exe -B scripts/validate_completed.py
```

`all` 先完成固定 smoke，达到门槛才运行 20 条 pilot；已有结果会复用，不重复扣费。只有在明确修复实现错误后，使用 `--retry-failed` 归档失败尝试并重跑；原始记录不会删除。
新机器先按 environment/requirements-reproduction.txt 建立 Python 环境，克隆 upstream 并固定 4efb4b9bf7e845e180451b43ba29a25e3edaa0e3；未升级系统环境。作者缺少版本固定，本次版本选择见环境日志。

```powershell
py -3.11 -m venv .venv
.\\.venv\\Scripts\\python.exe -m pip install -r environment/requirements-reproduction.txt
git clone https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis.git upstream
git -C upstream checkout --detach 4efb4b9bf7e845e180451b43ba29a25e3edaa0e3
```

上面的安装/克隆步骤只适用于新目录；本机环境和 upstream 已就绪。模型密钥写入本地 .env 的 DEEPSEEK_APIkey 变量，配置后按前述运行命令执行。

## 凭据与费用

模型 deepseek-flash，API https://api.deepseek.com/，本地 .env 变量 DEEPSEEK_APIkey；禁止把密钥发聊天、日志或提交 Git。.gitignore 已忽略 .env；客户端不使用作者内嵌凭据。
预算累计上限 10 元，目前所有尝试调用 {len(ledger['calls'])} 次，保守费用上界 {ledger['cost_upper_bound_cny']:.6f} 元。配置见 configs/completed_experiment.json，ledger 持续记录，不因重跑清零；这不是账户账单。

## 记录与实现边界

- 上游：upstream/，原始代码未修改；复用提示词及主分析函数。
- 补全代码：completion/；逐项说明 logs/stage_06_completion.md，差异 patches/completed_pipeline.diff。
- 当前数据：官方 CodeQL/Linux NPD；上下文来自官方基准和历史 baseline，歧义/缺失保留阻塞。
- 样本清单：configs/*manifest.json；逐样本 CSV/JSON：results/processed/completed_*。
- 原始模型调用、usage、SMT2、耗时及失败：results/raw/completed/。
- 当前指标：results/metrics/completed_metrics.json；报告：results/final_report.md。
- 阶段日志：logs/stage_01 至 stage_06；补全前结论快照：results/archive/before_authorized_completion/。
- 旧 smoke_results 和 reproduction_metrics 是先前离线组件阶段数据；当前真实实验使用 completed_ 前缀。scripts/finalize_records.py 只用于旧阶段，不要用它覆盖当前报告。

仅支持有界的 NPD 上下文，未实现任意工程的完整跨过程分析、宏展开或函数指针解析；不能把运行成功当作约束语义正确，也不能把当前模型结果直接等同论文 GPT-4o-mini 效果。未运行全基准或基线。
'''
(ROOT/'README.md').write_text(readme,encoding='utf-8')
save(ROOT/'results/processed/stage_status.json', {'timestamp':now,'implementation':'documented_completion','stage_01':'audit_completed','stage_02':'environment_and_model_service_verified','stage_03':sm,'stage_04':pm,'stage_05':'small_sample_evaluation_completed','stage_06':'completion_implemented_and_tested','paper_full_reproduction_success':False,'pilot_gate':gate})
with (ROOT/'reproduction_plan.md').open('a',encoding='utf-8') as f:f.write(f'\n\n## 2026-10-26 授权后的补全执行\n\n用户授权补写后，按独立补全实现运行真实 smoke 和 pilot；当前成功数分别 {sm["successful"]}、{pm["successful"]}。旧“核心模块缺失即停”边界已由用户授权扩大为有界补全，不表示原版恢复。全量实验仍未开展。\n')
print(json.dumps({'smoke':sm,'pilot':pm,'calls_all_attempts':len(ledger['calls']),'cost_upper_bound_cny':ledger['cost_upper_bound_cny']},ensure_ascii=True))
