"""Run original extraction/prompt components on five official NPD samples.

This is an offline diagnostic, NOT an end-to-end LLM4PFA reproduction.
No model response, constraint, label or prediction is fabricated.
"""
import __future__
import ast
import csv
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import random
import runpy
import time
import traceback
from datetime import timedelta, timezone

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'results/raw/smoke'
RAW.mkdir(parents=True, exist_ok=True)
SOURCE = ROOT / 'upstream/llm4pfa/extract_util_plus.py'
DATASET = 'benchmark/NPD/codeql/codeql_kernel69_nullpointer.json'
data_path = ROOT / 'upstream' / DATASET
data = json.loads(data_path.read_text(encoding='utf-8'))
SEED = 20261025
rng = random.Random(SEED)
selected = sorted(rng.sample([i for i, r in enumerate(data) if r.get('result') == 1], 2) + rng.sample([i for i, r in enumerate(data) if r.get('result') == 0], 3))
manifest = {'timestamp': datetime.now(timezone(timedelta(hours=8), 'Asia/Shanghai')).isoformat(), 'seed': SEED, 'dataset': DATASET, 'dataset_sha256': sha256(data_path.read_bytes()).hexdigest(), 'selection_policy': '2 records result=1 + 3 records result=0; sorted original row positions; no selection based on extraction outcomes', 'row_positions_zero_based': selected, 'label_interpretation': 'Tentative 1=real bug, 0=false alarm; source metrics/group counts consistent for this subset; no per-label evaluation performed.'}
(ROOT / 'configs/smoke_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')

# Remove only the unavailable type-only import and postpone annotations.
# Every function body stays exactly as published; repository files are untouched.
tree = ast.parse(SOURCE.read_text(encoding='utf-8'))
removed = [n for n in tree.body if isinstance(n, ast.ImportFrom) and n.module == 'LLM4Detection.m_agent.conditions_info']
assert len(removed) == 1
tree.body = [n for n in tree.body if n not in removed]
namespace = {'__name__': '__component_probe__', '__file__': str(SOURCE)}
exec(compile(tree, str(SOURCE), 'exec', flags=__future__.annotations.compiler_flag), namespace)
prompt = runpy.run_path(str(ROOT / 'upstream/llm4pfa/prompt_templates.py'), run_name='__component_probe__')['Prompt']()
adaptation = {'kind': 'diagnostic_only_in_memory_import_adaptation', 'source': 'llm4pfa/extract_util_plus.py', 'source_sha256': sha256(SOURCE.read_bytes()).hexdigest(), 'removed_import': 'from LLM4Detection.m_agent.conditions_info import ContextHelper,Conditions', 'postponed_annotations': True, 'reason': 'ContextHelper is used only in an uncalled helper annotation; selected extract_conditions path has no dependency on either missing type.', 'function_bodies_changed': False, 'upstream_files_changed': False, 'not_a_repaired_full_pipeline': True}
(ROOT / 'patches/component_probe_adaptation.json').write_text(json.dumps(adaptation, ensure_ascii=False, indent=2), encoding='utf-8')
rows = []
for position in selected:
    item = data[position]
    sid = f'NPD/codeql/kernel69:row={position}:index={item.get("index", "none")}'
    start = time.perf_counter()
    row = {'sample_id': sid, 'dataset': DATASET, 'row_position': position, 'original_index': item.get('index'), 'original_label': item['result'], 'prediction': None, 'end_to_end_status': 'not_run_blocked', 'end_to_end_attempted': False, 'official_entry_error': "ModuleNotFoundError: No module named 'util'", 'llm_status': 'not_run', 'solver_status': 'not_run_on_sample', 'api_calls': 0, 'cost_cny': 0}
    detail = {'sample': row, 'location': item['location'], 'var_name': item['var_name'], 'function_name': item.get('function_name'), 'function_code_sha256': sha256(item['function_code'].encode()).hexdigest(), 'source_adaptation': adaptation}
    try:
        loc = item['location']['context']['snippet']['text']
        extracted = json.loads(namespace['extract_conditions'](item['var_name'], None, loc, item['function_code']))
        detail['extracted_conditions'] = extracted
        if 'bug_line_constraints' not in extracted:
            raise ValueError('Original extract_conditions did not return bug_line_constraints; inspect target matching.')
        conditions = extracted['bug_line_constraints'][0]['condition']
        detail['generated_initial_prompt'] = prompt.get_z3_by_target_conditions(conditions + [item['var_name'] + ' == 0'])
        row['component_status'] = 'extraction_and_prompt_passed'
        row['target_condition_count'] = len(conditions)
        row['early_jump_count'] = len(extracted['early_jump_constraints'])
        row['component_error'] = None
    except Exception as exc:
        row['component_status'] = 'failed'
        row['component_error'] = f'{type(exc).__name__}: {exc}'
        row['target_condition_count'] = None
        row['early_jump_count'] = None
        detail['traceback'] = traceback.format_exc()
    row['component_duration_seconds'] = time.perf_counter() - start
    detail['sample'] = dict(row)
    path = RAW / f'row_{position:03d}.json'
    path.write_text(json.dumps(detail, ensure_ascii=False, indent=2), encoding='utf-8')
    row['raw_output'] = path.relative_to(ROOT).as_posix()
    rows.append(row)
(ROOT / 'results/processed/smoke_results.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
with (ROOT / 'results/processed/smoke_results.csv').open('w', newline='', encoding='utf-8-sig') as f:
    writer = csv.DictWriter(f, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
passed = sum(r['component_status'] == 'extraction_and_prompt_passed' for r in rows)
table = '\n'.join(f"| `{r['sample_id']}` | {r['original_label']} | {r['component_status']} | {r['component_duration_seconds']:.6f} | 未运行/无预测 |" for r in rows)
log = f'''# 阶段 3：最小样本组件诊断

状态：离线组件诊断完成；端到端最小测试未通过先决条件，不能进入小规模实验。
时间：{manifest['timestamp']}（Asia/Shanghai）。

## 样本与方法

- 官方文件 `{DATASET}`，固定随机种子 {SEED}；选择原始 result=1 的 2 条、result=0 的 3 条，样本 ID、原始位置和文件 SHA-256 已固定于 `configs/smoke_manifest.json`。
- 默认暂将该组的 1/0 理解为真实缺陷/误报：该文件分布 22/48 与论文表 5 和作者聚合指标 real_bug_num=22 一致；尚无逐条独立标注说明，不开展标签指标评估。
- 缺陷类型限定 NPD：公开流水线硬编码空指针判定，不能为了多类型覆盖而套用于 UAF/BOF。
- 官方入口实际加载失败见阶段 2，错误为 `ModuleNotFoundError: No module named 'util'`。以下不是 5 次端到端运行，而是对 5 条真实样本调用原始条件提取函数并生成原始初始提示词。
- 为独立加载提取器，仅在内存 AST 中移除缺失类型导入并推迟注解求值；所有函数体不变、上游文件未修改。详细原因和影响见 `patches/component_probe_adaptation.json`。没有实现缺失核心模块。

## 实际结果

| 样本 ID | 原始 result | 条件提取与提示词生成 | 组件耗时（秒） | 端到端结果 |
|---|---:|---|---:|---|
{table}

- 组件成功 {passed}/5，组件失败 {5-passed}/5。
- 端到端尝试 0、成功 0、先决条件阻塞 5。最终预测均为 null，不得计为真实缺陷或误报。
- 每条样本都保存了实际位置、提取的路径/提前跳转条件、提示词或真实 traceback；无 LLM 响应、无该样本的 SMT 结果。
- API 调用 0，费用 0 元。耗时仅为本地组件耗时，不能作为论文方法平均运行时间。
- 输出：`results/raw/smoke/row_*.json`、`results/processed/smoke_results.csv` 和 `.json`。

## 当前阻塞

原始内部模块和跨过程分析缓存没有完整恢复；凭据环境变量未配置；用户模型与论文不同且服务可用性未验证。不生成虚构模型响应、Z3 约束或预测，也不以缺失上下文触发的 result=True 作为成功。
'''
(ROOT / 'logs/stage_03_smoke_test.md').write_text(log, encoding='utf-8')
print(json.dumps({'stage': 3, 'component_passed': passed, 'component_failed': 5-passed, 'end_to_end_attempted': 0, 'end_to_end_successful': 0, 'api_calls': 0, 'log_exists': (ROOT / 'logs/stage_03_smoke_test.md').is_file()}, ensure_ascii=True))
