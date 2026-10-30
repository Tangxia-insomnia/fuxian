"""Evaluate every selected NPD row, retaining blocked/errors and cached provenance."""
import csv
from collections import Counter
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from completion.metrics import evaluate
from completion.model import save
from scripts.run_expanded import GROUPS


def load(path):
    return json.loads((ROOT/path).read_text(encoding='utf-8'))


def pct(value):
    return 'NA' if value is None else f'{value*100:.2f}%'


def write_csv(path, rows):
    keys=sorted(set().union(*(r.keys() for r in rows)))
    with (ROOT/path).open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=keys)
        writer.writeheader(); writer.writerows(rows)


def main():
    now=datetime.now(timezone(timedelta(hours=8))).isoformat()
    ledger=load('results/raw/completed/budget_ledger.json')
    all_rows=[]; group_metrics={}; manifests={}
    for group in GROUPS:
        manifest=load(f'configs/expanded_{group}_manifest.json')
        manifests[group]=manifest
        rows=load(f'results/processed/completed_expanded_{group}.json')
        assert set(manifest['row_positions_zero_based'])=={r['row_position'] for r in rows}, 'Group not finished: '+group
        all_rows.extend(rows)
        group_metrics[group]=evaluate(rows)
        save(ROOT/f'results/metrics/expanded_{group}_metrics.json',group_metrics[group])
    assert len(all_rows)==len({r['sample_id'] for r in all_rows})==278, 'Missing or duplicate NPD sample'
    metrics=evaluate(all_rows)
    prior=load('results/archive/before_expanded_experiment/results/metrics/completed_metrics.json')
    error_counts=Counter(r['error'] for r in all_rows if r['status']!='success')
    bundle={'timestamp':now,'scope':'all existing integer 0/1 labeled NPD records in eight official files',
            'not_full_paper_reproduction':True,'overall':metrics,'groups':group_metrics,
            'all_attempts_api_calls':len(ledger['calls']),'all_attempts_cost_upper_bound_cny':ledger['cost_upper_bound_cny'],
            'additional_api_calls':len(ledger['calls'])-prior['api_calls_all_attempts'],
            'additional_cost_upper_bound_cny':ledger['cost_upper_bound_cny']-prior['cost_upper_bound_cny_all_attempts'],
            'prior_results_reused':sum('reused_from_phase' in r for r in all_rows),
            'successful_with_real_smt':sum(r['status']=='success' and r.get('solver_successful',0)>0 for r in all_rows),
            'error_counts':dict(error_counts),'exact_account_billing_known':False}
    save(ROOT/'results/metrics/expanded_metrics.json',bundle)
    save(ROOT/'results/processed/expanded_all_npd.json',all_rows)
    write_csv('results/processed/expanded_all_npd.csv',all_rows)
    with (ROOT/'results/metrics/expanded_confusion_matrix.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.writer(f);writer.writerow(['actual_label','predicted_filter','predicted_keep','unclassified'])
        for category,values in zip(['false_alarm','real_bug'],metrics['confusion_matrix']['values']):
            writer.writerow([category,*values,metrics['missing_prediction_by_label'][category]])
    lines=[]
    for group,m in group_metrics.items():
        lines.append(f"| {group} | {m['sample_count']} | {m['successful']} | {m['blocked']} | {m['failed']} | {pct(m['false_positive_filter_rate'])} | {pct(m['real_bug_retention_rate'])} |")
    table='\n'.join(lines)
    a,b=metrics['confusion_matrix']['values'][0]; c,d=metrics['confusion_matrix']['values'][1]
    matrix=f'''| 实际类别 | 过滤 | 保留 | 未分类 |
|---|---:|---:|---:|
| 误报 | {a} | {b} | {metrics['missing_prediction_by_label']['false_alarm']} |
| 真实缺陷 | {c} | {d} | {metrics['missing_prediction_by_label']['real_bug']} |'''
    summary=f'''## 扩展实验实际结果（{now}）

本次覆盖 8 组 NPD 文件的全部 278 条现有 0/1 标签记录。最终成功执行 {metrics['successful']} 条、阻塞 {metrics['blocked']} 条、执行失败 {metrics['failed']} 条，处理成功率 {pct(metrics['success_rate'])}。复用原先 25 条最终记录，其余新增结果均单独保存；没有按可运行性或预测正确性筛选记录。

| 分组 | 已选定 | 成功执行 | 阻塞 | 运行失败 | 误报过滤率 | 真实缺陷保留率 |
|---|---:|---:|---:|---:|---:|---:|
{table}

{matrix}

正类定义为“应过滤的误报”。全体选定样本含误报 {metrics['false_alarm_count']} 条、真实缺陷 {metrics['real_bug_count']} 条。
误报过滤率={a}/{metrics['false_alarm_count']}={pct(metrics['false_positive_filter_rate'])}；真实缺陷保留率={d}/{metrics['real_bug_count']}={pct(metrics['real_bug_retention_rate'])}；真实缺陷误删率={c}/{metrics['real_bug_count']}={pct(metrics['real_bug_deletion_rate'])}。
Precision=A/(A+C)={pct(metrics['precision'])}，Recall=A/N_FP={pct(metrics['recall'])}，F1=2PR/(P+R)={pct(metrics['f1'])}。
未分类记录保持未知、未当作过滤或保留，且不从分母中删除。未知结果使过滤率可能范围为 {pct(metrics['false_positive_filter_rate_bounds'][0])}–{pct(metrics['false_positive_filter_rate_bounds'][1])}，真实缺陷保留率为 {pct(metrics['real_bug_retention_rate_bounds'][0])}–{pct(metrics['real_bug_retention_rate_bounds'][1])}；当前比例只统计已确认结果。

最终尝试平均耗时（含上下文阻塞）：{metrics['mean_wall_seconds_all_selected']:.3f} 秒/条；成功执行样本平均 {metrics['mean_wall_seconds_successful']:.3f} 秒/条。复用样本使用其原实际耗时，并非本轮复用读取耗时。逐样本耗时与费用在 CSV/JSON 中。
本轮新增实际模型调用 {bundle['additional_api_calls']} 次，新增费用保守上界 {bundle['additional_cost_upper_bound_cny']:.6f} 元；全部阶段和早期失败累计 {len(ledger['calls'])} 次，费用上界 {ledger['cost_upper_bound_cny']:.6f} 元，未超过原累计 10 元限制。这是使用官方较高费率计算的估算上界，不是账户账单。
'''
    failure_lines='\n'.join(f"- {count} 条：`{error}`" for error,count in error_counts.most_common())
    bug_lines='\n'.join(f"- `{r['sample_id']}`：误删真实缺陷；原始证据 `{r['raw_output']}`。" for r in all_rows if r['label']==1 and r['prediction']=='filter' and r['status']=='success') or '- 未观察到误删；仍受覆盖率限制。'
    report=f'''# LLM4PFA 补全版扩展实验报告

时间：{now}。当前实验范围是公开 NPD 数据中全部有有效标签的记录，尚非论文所有缺陷类型的完整复现。

## 版本、环境和方法

官方仓库：https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis 。固定 commit `4efb4b9bf7e845e180451b43ba29a25e3edaa0e3`；历史上下文取自 `29ca96e0d5f860d1f4ce07cd3e54e5e25732d1a1`。
最新 main 已改为 PATHAGENT 描述，版本选择和论文 v1 差异见 logs/stage_01_repository.md。上游源码和原始 JSON 保持不变。
Windows / Python 3.11.5 / Z3 4.13.4.0 / libclang 18.1.1；依赖固定于 environment/requirements-reproduction.txt，实际 freeze 见 environment/dependencies.txt。
使用 deepseek-flash（现有官方文档对应 DeepSeek-V4.1-Flash-1017），API https://api.deepseek.com/，非思考模式，temperature=0.0000001，输出上限 3072 token、每样本最多 24 次请求。密钥仅从本地 .env 或指定环境变量读取，不写入报告。

复用作者提示词、条件提取和迭代分析函数；缺失的上下文/调用/参数等支撑采用有界补全，详见 logs/stage_06_completion.md 与 patches/completed_pipeline.diff。扩展只为同一 NPD 实现增加数据路径、历史缓存路径、func_info 字段映射和批量入口；无算法或模型优化。每次真实 SMT 查询记录源码、SAT/UNSAT 与 SMT2。
上下文缺失或歧义保留阻塞。宏/调用形式的历史 sink 沿用作者边界，未实现完整宏展开、任意别名及函数指针语义。模型成功生成可运行的 SMT 不代表约束忠实表达 C 代码。

## 数据范围与标签

清点全部 14 个 JSON，共 1017 行；剔除 UBI/UUA 完全重复文件的 63 行后，唯一文件记录数为 954。
8 份 NPD 文件共 808 行，其中 278 行具有原始整数 0/1 标签，530 行为缺失标签或 -1，后者全部记录排除原因且不补标。其他缺陷类型共 146 行：现有执行流程是空指针 `var == 0` 分析，缺少相应类型的可运行流水线，因此记录为未运行，未强行套用空指针约束。
原始 result=0 沿用为误报、1 为真实缺陷。与作者各 NPD 分组 gpt4omini_metrics 的 real_bug_num、总数交叉核对；不是独立人工重新标注。CodeQL/OpenSSL 有 1 条 -1，作者聚合记真实缺陷 9 条而现有 1 标签仅 8 条；Cppcheck/Linux 有 3 条 -1 和大量缺失标签，作者聚合与论文数量也存在差异。无法确认这些特殊值的逐条含义，不把它们改成真实缺陷或误报，不能重建精确论文集合。各组路径、数据 SHA、原始行号和标签数见 configs/expanded_*_manifest.json；完整范围清单见 results/processed/expanded_benchmark_scope.json。
没有重新扫描 Linux Kernel 或下载整工程。未运行 LLM4SA/LLMDFA 基线；不同模型、补全实现和基准版本的结果不能直接视为论文效果复现。

{summary}

## 失败与错误案例

{failure_lines}

{bug_lines}

smoke 早期 4 次失败来自补全执行器未兼容函数内 z3 导入，pilot 另 1 次失败来自漏列标准 Function 接口；修复后重跑且原始记录和费用全部保留。扩展阶段的原始失败也保留，不根据标签修正模型输出或移除记录。

诊断例：CodeQL/Libav row 3 的脚本将 TYPE_END、TYPE_DSE 建模为没有固定取值的整数符号，得到 SAT 并输出保留；CodeQL/OpenSSL row 4 的实际查询仅含 alg == 0，也得到 SAT。这些记录说明“约束可运行”和“原 C 路径已被忠实还原”不同；宏、枚举值及数据流关系不充分时，很多误报可能仍被保留。本次没有为提高指标而补猜这些语义或按标签修改约束。

## 与论文的差异及后续

论文 v1 主实验模型 GPT-4o-mini，三类缺陷共 364 条/45 个真实缺陷。本次为公开 NPD 文件中 278 条可评估记录的补全版扩展，未恢复原始私有模块、精确论文数据集或其他类型流水线；因此只报告实际覆盖，不能声称完整论文复现成功。
原 5 条最小样本、20 条 pilot 报告已保存在 results/archive/before_expanded_experiment/，原始逐样本文件保持保留。汇总指标不会将这 25 条与 278 条再重复计数。
下一步优先人工检查被误删真实缺陷的赋值时序、goto/循环条件和宏语义，再向作者获取缺失模块及准确数据版本。扩大缺陷类型需要相应原始约束定义和可核验实现；本次未开展算法改进。

## 证据位置

- 全部逐样本 CSV/JSON：results/processed/expanded_all_npd.*；分组结果：completed_expanded_*。
- 混淆矩阵与完整指标：results/metrics/expanded_metrics.json、expanded_confusion_matrix.csv。
- 原始调用、使用量、模型响应、SMT、错误及费用账本：results/raw/completed/。
- 扩展阶段日志：logs/stage_07_expanded.md；汇总核验：results/raw/completed/expanded_verification.json。
'''
    (ROOT/'results/final_report.md').write_text(report,encoding='utf-8')
    for log in ['logs/stage_07_expanded.md','logs/stage_05_evaluation.md']:
        with (ROOT/log).open('a',encoding='utf-8') as f:f.write('\n\n'+summary+'\n\n'+failure_lines+'\n')
    readme=f'''# LLM4PFA 补全版复现与扩展实验

已从 5 条 smoke、20 条 pilot 扩展到 8 组 NPD 全部 278 条有效标签记录。成功执行 {metrics['successful']}，阻塞 {metrics['blocked']}，执行失败 {metrics['failed']}。这是补全版 NPD 扩展，非论文所有类型完整复现。

最终报告：results/final_report.md；逐样本：results/processed/expanded_all_npd.csv；指标：results/metrics/expanded_metrics.json。小样本旧报告在 results/archive/before_expanded_experiment/。

## 当前环境与运行

Windows PowerShell，在本目录执行；.venv 和固定 upstream 已就绪：

```powershell
.\\.venv\\Scripts\\python.exe -B -m unittest completion.test_completion -v
.\\.venv\\Scripts\\python.exe -B scripts/run_expanded.py --all-npd --preflight
.\\.venv\\Scripts\\python.exe -B scripts/run_expanded.py --all-npd
.\\.venv\\Scripts\\python.exe -B scripts/report_expanded.py
.\\.venv\\Scripts\\python.exe -B scripts/validate_expanded.py
```

默认续跑复用已有结果，含阻塞和失败，避免重复扣费。CodeQL/Linux 原先 25 条最终结果复用，汇总不重复计数。原脚本 run_completed.py 仍可单独检查 smoke/pilot；report_completed.py 和 finalize_records.py 属于旧阶段，会覆盖当前报告，勿用于本次扩展汇总。

新目录安装：

```powershell
py -3.11 -m venv .venv
.\\.venv\\Scripts\\python.exe -m pip install -r environment/requirements-reproduction.txt
git clone https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis.git upstream
git -C upstream checkout --detach 4efb4b9bf7e845e180451b43ba29a25e3edaa0e3
```

模型 deepseek-flash，接口 https://api.deepseek.com/，本地 .env 配置 DEEPSEEK_APIkey。.gitignore 忽略凭据文件，禁止把密钥发聊天或提交。累计预算保持 10 元，所有阶段调用共 {len(ledger['calls'])} 次，费用估算上界 {ledger['cost_upper_bound_cny']:.6f} 元，包含失败，不是账户账单；账本不会因续跑清零。

## 记录和限制

configs/expanded_experiment.json 保存配置，expanded_*_manifest.json 保存固定全集与数据 SHA；results/raw/completed 保存真实模型/SMT及错误；logs/stage_01 至 stage_07 保存各阶段。
仅使用已有官方数据和历史上下文，无整工程扫描。530 条 NPD 标签未知/无效记录不补标；其他类型和重复文件排除原因详见 expanded_benchmark_scope.json。补全解析有界，无法恢复的代码关系保留阻塞。所有未分类保留在分母、另列数量，不能把成功执行等同判定正确。
'''
    (ROOT/'README.md').write_text(readme,encoding='utf-8')
    status=load('results/processed/stage_status.json')
    status.update({'timestamp':now,'stage_07_expanded':bundle,'paper_full_reproduction_success':False})
    save(ROOT/'results/processed/stage_status.json',status)
    print(json.dumps({'overall':metrics,'calls_total':len(ledger['calls']),'cost_cny_upper':ledger['cost_upper_bound_cny']},ensure_ascii=True))


if __name__=='__main__':
    main()
