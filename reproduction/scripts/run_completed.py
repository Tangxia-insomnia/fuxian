"""Run documented completion: service check, smoke, then gated 20-row pilot."""
import argparse
import contextlib
import csv
from datetime import datetime, timedelta, timezone
import io
import json
from pathlib import Path
import random
import shutil
import subprocess
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from completion.context import ContextRepository, ContextUnavailable, DATASET
from completion.engine import CompletedEngine
from completion.model import DeepSeekModel, ModelFailure, save


def append_log(name, text):
    with (ROOT / 'logs' / name).open('a', encoding='utf-8') as f:
        f.write('\n\n' + text + '\n')


def preserve_initial():
    dest = ROOT / 'results/archive/before_authorized_completion'
    if dest.exists():
        return
    for name in ['README.md', 'reproduction_plan.md', 'results/final_report.md', 'results/processed/stage_status.json', 'results/metrics/reproduction_metrics.json'] + ['logs/' + p.name for p in (ROOT / 'logs').glob('stage_*.md')]:
        source = ROOT / name
        if source.is_file():
            target = dest / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)


def persist_rows(phase, rows):
    save(ROOT / f'results/processed/completed_{phase}.json', rows)
    if rows:
        keys = sorted(set().union(*(r.keys() for r in rows)))
        with (ROOT / f'results/processed/completed_{phase}.csv').open('w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader(); writer.writerows(rows)


def archive_failed_attempts(phase):
    path = ROOT / f'results/processed/completed_{phase}.json'
    if not path.exists():
        return
    rows = json.loads(path.read_text(encoding='utf-8'))
    history_path = ROOT / f'results/processed/completed_{phase}_attempt_history.json'
    history = json.loads(history_path.read_text(encoding='utf-8')) if history_path.exists() else []
    for row in rows:
        if row['status'] != 'failed':
            continue
        folder = ROOT / row['raw_output']
        attempt = 1 + sum(h['row_position'] == row['row_position'] for h in history)
        archived = folder.with_name(folder.name + f'_attempt_{attempt:02d}')
        assert folder.resolve().is_relative_to((ROOT/'results/raw/completed').resolve())
        assert archived.resolve().is_relative_to((ROOT/'results/raw/completed').resolve())
        folder.rename(archived)
        history.append({**row, 'attempt': attempt, 'raw_output': archived.relative_to(ROOT).as_posix()})
    save(history_path, history)
    persist_rows(phase, [r for r in rows if r['status'] != 'failed'])


def run_phase(phase, positions, repository, engine, model):
    result_path = ROOT / f'results/processed/completed_{phase}.json'
    rows = json.loads(result_path.read_text(encoding='utf-8')) if result_path.exists() else []
    complete = {r['row_position'] for r in rows}
    stage_log = {'smoke': 'stage_03_smoke_test.md', 'pilot': 'stage_04_pilot.md'}.get(phase, 'stage_07_expanded.md')
    append_log(stage_log, f'## 补全版 {phase} 开始\n\n时间：{datetime.now(timezone(timedelta(hours=8))).isoformat()}。样本原始行号：{positions}。下列运行属于补全实现，原始实现诊断记录保留。')
    for position in positions:
        if position in complete:
            continue
        sample = repository.data[position]
        sample_id = f'{repository.sample_prefix}:row={position}:index={sample.get("index")}'
        row = {'sample_id': sample_id, 'dataset': repository.dataset, 'row_position': position, 'original_index': sample.get('index'), 'label': sample['result'], 'prediction': None, 'implementation': 'author_pipeline_with_documented_completion_v1', 'phase': phase, 'status': 'started', 'error': None}
        folder = ROOT / 'results/raw/completed' / phase / f'row_{position:03d}'
        folder.mkdir(parents=True, exist_ok=True)
        start = time.perf_counter()
        before_calls = len(model.ledger['calls']); before_cost = model.ledger['cost_upper_bound_cny']
        model.begin_sample(sample_id)
        engine.solver_events = []
        output = io.StringIO()
        print(json.dumps({'phase': phase, 'row': position, 'event': 'started'}), flush=True)
        try:
            context = engine.prepare(position)
            row['context_frames'] = len(context['frames'])
            row['sink_kind'] = context['frames'][-1]['sink_kind']
            row['end_to_end_attempted'] = True
            with contextlib.redirect_stdout(output):
                answer = engine.run(position, folder, context)
            save(folder / 'author_pipeline_output.json', answer)
            value = answer.get('result')
            if type(value) is not bool:
                raise RuntimeError('Author pipeline returned a non-boolean result: ' + str(value))
            row['prediction'] = 'keep' if value else 'filter'
            row['status'] = 'success'
            row['decision_basis'] = 'z3' if engine.solver_events else 'author_llm_context_early_exit'
            if value and not any(e.get('ok') for e in engine.solver_events):
                raise RuntimeError('Feasible result has no completed SMT query')
        except ContextUnavailable as exc:
            row.update({'status': 'blocked_context', 'error': str(exc), 'end_to_end_attempted': len(model.ledger['calls']) > before_calls})
        except ModelFailure as exc:
            budget_block = 'cumulative budget guard' in str(exc)
            row.update({'status': 'blocked_budget' if budget_block else 'failed', 'prediction': None, 'error': model.redact(str(exc)), 'end_to_end_attempted': len(model.ledger['calls']) > before_calls})
            (folder / 'traceback.txt').write_text(model.redact(traceback.format_exc()), encoding='utf-8')
        except Exception as exc:
            row.update({'status': 'failed', 'prediction': None, 'error': model.redact(f'{type(exc).__name__}: {exc}'), 'end_to_end_attempted': len(model.ledger['calls']) > before_calls})
            (folder / 'traceback.txt').write_text(model.redact(traceback.format_exc()), encoding='utf-8')
        row.update({'duration_seconds': time.perf_counter()-start, 'api_calls': len(model.ledger['calls'])-before_calls, 'cost_upper_bound_cny': model.ledger['cost_upper_bound_cny']-before_cost, 'solver_attempts': len(engine.solver_events), 'solver_successful': sum(e.get('ok') is True for e in engine.solver_events), 'raw_output': folder.relative_to(ROOT).as_posix()})
        (folder / 'stdout.txt').write_text(model.redact(output.getvalue()), encoding='utf-8')
        save(folder / 'sample_result.json', row)
        rows.append(row)
        persist_rows(phase, rows)
        append_log(stage_log, f"- 样本 `{sample_id}`：{row['status']}；预测={row['prediction']}；调用={row['api_calls']}；Z3 成功={row['solver_successful']}；耗时={row['duration_seconds']:.3f}s；费用保守上界={row['cost_upper_bound_cny']:.6f} 元；错误={row['error']}。")
        print(json.dumps({'phase': phase, 'row': position, 'status': row['status'], 'prediction': row['prediction'], 'calls': row['api_calls'], 'solver_successful': row['solver_successful'], 'cost_upper_bound_cny_total': model.ledger['cost_upper_bound_cny']}, ensure_ascii=True), flush=True)
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--phase', choices=['preflight', 'smoke', 'all'], default='all')
    parser.add_argument('--retry-failed', action='store_true', help='Archive failed attempts and rerun after a documented implementation fix')
    args = parser.parse_args()
    preserve_initial()
    config = json.loads((ROOT / 'configs/completed_experiment.json').read_text(encoding='utf-8'))
    model = DeepSeekModel(config)
    repository = ContextRepository()
    engine = CompletedEngine(repository, model)
    smoke = json.loads((ROOT / 'configs/smoke_manifest.json').read_text(encoding='utf-8'))['row_positions_zero_based']
    preflight = []
    for p in smoke:
        try:
            ctx = engine.prepare(p)
            preflight.append({'row': p, 'status': 'ready', 'frames': len(ctx['frames']), 'sink_kind': ctx['frames'][-1]['sink_kind']})
        except Exception as exc:
            preflight.append({'row': p, 'status': 'blocked', 'error': str(exc)})
    service = model.verify_service()
    save(ROOT / 'results/raw/completed/preflight.json', {'samples': preflight, 'service': service, 'upstream_git_status': subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT/'upstream', text=True)})
    print(json.dumps({'preflight': preflight, 'service': service}, ensure_ascii=True), flush=True)
    if args.phase == 'preflight':
        return
    if args.retry_failed:
        archive_failed_attempts('smoke')
    smoke_rows = run_phase('smoke', smoke, repository, engine, model)
    # Explicit gate: >=3 complete smoke results, both labels covered, at least
    # one real SMT query, and no execution failures. Context blocks stay visible.
    successes = [r for r in smoke_rows if r['status'] == 'success']
    stable = len(successes) >= 3 and {r['label'] for r in successes} == {0, 1} and any(r['solver_successful'] for r in successes) and not any(r['status'] == 'failed' for r in smoke_rows)
    save(ROOT / 'results/processed/completed_pilot_gate.json', {'stable': stable, 'smoke_successful': len(successes), 'smoke_total': len(smoke_rows), 'rule': 'At least 3 successes, both labels, actual SMT, no execution failures; retain all context blocks'})
    if args.phase == 'smoke' or not stable:
        print(json.dumps({'pilot_gate_passed': stable, 'pilot_started': False}), flush=True)
        return
    rng = random.Random(config['seed'])
    selected = sorted(rng.sample([i for i, r in enumerate(repository.data) if r['result'] == 0 and i not in smoke], 10) + rng.sample([i for i, r in enumerate(repository.data) if r['result'] == 1 and i not in smoke], 10))
    save(ROOT / 'configs/completed_pilot_manifest.json', {'seed': config['seed'], 'dataset': DATASET, 'row_positions_zero_based': selected, 'label_counts': {'0': 10, '1': 10}, 'selection': 'stratified random, excludes smoke, no filtering by preflight outcome'})
    if args.retry_failed:
        archive_failed_attempts('pilot')
    run_phase('pilot', selected, repository, engine, model)


if __name__ == '__main__':
    main()
