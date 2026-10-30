"""Read-only experiment checks plus a saved verification/identity record; no API calls."""
import csv
from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from completion.metrics import evaluate
from completion.model import save


def load(path):
    return json.loads((ROOT / path).read_text(encoding='utf-8'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    now = datetime.now(timezone(timedelta(hours=8))).isoformat()
    data_path = 'benchmark/NPD/codeql/codeql_kernel69_nullpointer.json'
    data = load('upstream/' + data_path)
    ledger = load('results/raw/completed/budget_ledger.json')
    required = ['README.md', 'reproduction_plan.md', 'environment/environment.txt',
                'environment/dependencies.txt', 'results/final_report.md',
                'configs/experiment_config.example.yaml']
    required += [f'logs/{name}' for name in ['stage_01_repository.md', 'stage_02_environment.md',
                'stage_03_smoke_test.md', 'stage_04_pilot.md', 'stage_05_evaluation.md', 'stage_06_completion.md']]
    assert all((ROOT / p).is_file() and (ROOT / p).stat().st_size for p in required), 'Missing required deliverable'
    phases, all_attempts, selected_ids = {}, [], set()
    for phase, count, manifest in [('smoke', 5, 'configs/smoke_manifest.json'),
                                   ('pilot', 20, 'configs/completed_pilot_manifest.json')]:
        rows = load(f'results/processed/completed_{phase}.json')
        history = load(f'results/processed/completed_{phase}_attempt_history.json')
        positions = load(manifest)['row_positions_zero_based']
        assert len(rows) == count and len({r['row_position'] for r in rows}) == count, 'Sample count or duplicate mismatch'
        assert set(positions) == {r['row_position'] for r in rows}, 'Manifest mismatch'
        with (ROOT / f'results/processed/completed_{phase}.csv').open(encoding='utf-8-sig', newline='') as f:
            csv_rows = list(csv.DictReader(f))
        assert len(csv_rows) == count, 'CSV count mismatch'
        for row in rows:
            assert row['sample_id'] not in selected_ids, 'Overlap across phases'
            selected_ids.add(row['sample_id'])
            assert data[row['row_position']]['result'] == row['label'], 'Original label mismatch'
            assert data[row['row_position']]['index'] == row['original_index'], 'Original index mismatch'
            csv_row = next(r for r in csv_rows if r['sample_id'] == row['sample_id'])
            assert csv_row['status'] == row['status'] and csv_row['prediction'] == (row['prediction'] or ''), 'CSV prediction mismatch'
        for row in rows + history:
            folder = ROOT / row['raw_output']
            raw = json.loads((folder / 'sample_result.json').read_text(encoding='utf-8'))
            assert all(raw[k] == row[k] for k in ['sample_id', 'label', 'prediction', 'status', 'api_calls']), 'Raw result mismatch'
            call_count = sum(c['sample_id'] == row['sample_id'] for c in ledger['calls'])
            assert call_count >= row['api_calls'], 'Sample calls missing from ledger'
            if row['status'] == 'success':
                events = [json.loads(p.read_text(encoding='utf-8')) for p in folder.glob('solver_*.json')]
                good = [e for e in events if e.get('ok')]
                assert good and all(e['queries'] for e in good), 'Successful sample lacks actual SMT evidence'
                assert good[-1]['feasible'] == (row['prediction'] == 'keep'), 'Final SMT/prediction mismatch'
            else:
                assert row['prediction'] is None and row['error'], 'Failure lost or misclassified'
        actual_metrics = evaluate(rows)
        saved_metrics = load(f'results/metrics/completed_{phase}_metrics.json')
        assert all(saved_metrics[k] == v for k, v in actual_metrics.items()), 'Metric recomputation mismatch'
        phases[phase] = {'selected': count, 'successful': actual_metrics['successful'],
                         'blocked': actual_metrics['blocked'], 'failed': actual_metrics['failed'],
                         'prior_failed_attempts': len(history)}
        all_attempts += rows + history
    assert sum(r['api_calls'] for r in all_attempts) == len(ledger['calls']), 'Attempt call totals mismatch'
    for sid in selected_ids:
        assert sum(r['api_calls'] for r in all_attempts if r['sample_id'] == sid) == sum(c['sample_id'] == sid for c in ledger['calls']), 'Per-sample call totals mismatch'
    assert not any(c['status'] == 'reserved' for c in ledger['calls']), 'Unfinished request reservation'
    assert abs(sum(c['cost_upper_bound_cny'] for c in ledger['calls']) - ledger['cost_upper_bound_cny']) < 1e-9, 'Ledger cost mismatch'
    assert 0 <= ledger['cost_upper_bound_cny'] <= 10, 'Budget exceeded'
    call_files = sorted((ROOT / 'results/raw/completed/calls').glob('*.json'))
    assert len(call_files) == len(ledger['calls']), 'Raw call count mismatch'
    returned_models = Counter()
    for entry, path in zip(ledger['calls'], call_files):
        record = json.loads(path.read_text(encoding='utf-8'))
        assert record['call_id'] == entry['call_id'] and record['sample_id'] == entry['sample_id'], 'Raw call identity mismatch'
        assert record['usage'] == entry['usage'], 'Usage mismatch'
        returned_models[record.get('model_returned')] += 1
    key = os.environ.get('DEEPSEEK_APIkey') or dotenv_values(ROOT / '.env').get('DEEPSEEK_APIkey')
    assert key, 'Credential missing for local leak check'
    secret_bytes = key.encode('utf-8')
    matches, scanned = [], 0
    for directory, folders, files in os.walk(ROOT):
        folders[:] = [f for f in folders if f not in {'.venv', 'upstream', '.git', 'pip-cache', '__pycache__'}]
        for name in files:
            if name == '.env' or name.startswith('.env.') and name != '.env.example':
                continue
            path = Path(directory) / name
            scanned += 1
            if secret_bytes in path.read_bytes():
                matches.append(path.relative_to(ROOT).as_posix())
    assert not matches, 'Credential detected in a deliverable; no secret value printed'
    assert '.env' in (ROOT / '.gitignore').read_text(encoding='utf-8').splitlines(), 'Missing credential ignore rule'
    sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT/'upstream', text=True).strip()
    status = subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT/'upstream', text=True)
    assert sha == '4efb4b9bf7e845e180451b43ba29a25e3edaa0e3' and not status, 'Upstream modified or wrong version'
    identity_files = list((ROOT/'completion').glob('*.py')) + list((ROOT/'scripts').glob('*completed.py'))
    identity_files += [ROOT/'configs/completed_experiment.json', ROOT/'upstream'/data_path]
    save(ROOT/'configs/completed_run_identity.json', {'timestamp': now, 'upstream_commit': sha,
         'historical_context_commit': '29ca96e0d5f860d1f4ce07cd3e54e5e25732d1a1',
         'sha256': {p.relative_to(ROOT).as_posix(): digest(p) for p in identity_files},
         'model_returned_counts': returned_models,
         'samples': {phase: load(f'results/processed/completed_{phase}.json') for phase in phases},
         'label_definition': {'0': 'false_alarm', '1': 'real_bug', 'scope': data_path,
             'evidence': 'Paper v1 Table 5 and upstream/results/llmpfa_result/codeql_linux_gpt4omini_metrics.json: real_bug_num=22, total_num=70, FP_recall=43/48; group-level corroboration, no independent relabeling'}})
    result = {'timestamp': now, 'passed': True, 'phases': phases, 'api_calls': len(ledger['calls']),
              'cost_upper_bound_cny': ledger['cost_upper_bound_cny'], 'credential_scan_files': scanned,
              'credential_matches_outside_excluded_local_files': len(matches), 'upstream_clean': True,
              'dataset_sha256': digest(ROOT/'upstream'/data_path), 'actual_metrics_recomputed': True}
    save(ROOT/'results/raw/completed/final_verification.json', result)
    print(json.dumps(result, ensure_ascii=True))


if __name__ == '__main__':
    main()
