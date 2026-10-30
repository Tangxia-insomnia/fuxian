"""Offline-only regression on 10 audit cases and a sealed 20-case holdout.

Run from reproduction/: python -B -m safety.replay
This is the new guarded replay entry; historical run_* scripts remain baseline.
"""
from collections import Counter
from datetime import datetime, timedelta, timezone
import csv
import hashlib
import json
from pathlib import Path
import sys
import time

from .metrics import evaluate
from .policy import decide, digest, text_digest, VERSION

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / 'safety_runs/20261029_v1'
AUDIT = ROOT / 'audit/failure_audit_20261029'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def file_sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_new(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)


def baseline_unchanged():
    frozen = read(AUDIT / 'frozen_state.json')
    changed = [n for n, v in frozen['files'].items()
               if not (ROOT/n).is_file() or file_sha(ROOT/n) != v['sha256']]
    if changed:
        raise ValueError('Frozen baseline changed: ' + ','.join(changed))
    ref = read(RUN/'baseline_reference.json')
    if file_sha(RUN/'fixed_holdout.json') != ref['holdout_manifest_sha256']:
        raise ValueError('Holdout manifest changed')
    return len(frozen['files'])


def load_bundle(row, audit_id=None):
    """Drop evaluation labels before the decision; copy saved evidence only."""
    alert = read(ROOT/'upstream'/row['dataset'])[row['row_position']]
    alert = {k: v for k, v in alert.items() if k not in ('result', 'label')}
    folder = ROOT/row['raw_output']
    context_file, answer_file = folder/'context.json', folder/'author_pipeline_output.json'
    bundle = {
        'scope': 'benchmark',
        'candidate': {k: row.get(k) for k in ('sample_id', 'status', 'prediction', 'error', 'decision_basis')},
        'alert': alert,
        'context': read(context_file) if context_file.exists() else None,
        'recorded_answer': read(answer_file) if answer_file.exists() else None,
        'solver_events': [read(p) for p in sorted(folder.glob('solver_*.json'))],
        'issues': [],
    }
    if audit_id:
        findings = read(AUDIT/'review_findings.json')[audit_id]
        # Data-label suspicions must never influence a model-side decision.
        categories = [x for x in findings['confirmed'] + findings['suspected'] if x != '数据或标签错误']
        bundle['issues'] = [{'code': 'unresolved_prior_audit:' + x,
                             'evidence_ref': f'audit/failure_audit_20261029/samples/{audit_id}/audit.md'}
                            for x in sorted(set(categories))]
    files = [ROOT/'upstream'/row['dataset']] + sorted(p for p in folder.iterdir() if p.is_file())
    binding = {'sample_id': row['sample_id'], 'evidence_sha256': digest(bundle),
               'artifact_sha256': {p.relative_to(ROOT).as_posix(): file_sha(p) for p in files}}
    return bundle, binding


def baseline_summary(rows):
    matrix = [[0, 0, 0], [0, 0, 0]]
    for r in rows:
        column = {'filter': 0, 'keep': 1}.get(r['prediction'], 2) if r['status'] == 'success' else 2
        matrix[r['label']][column] += 1
    fp, bug = matrix
    return {'confusion_matrix': matrix, 'columns': ['filter', 'keep', 'unclassified'],
            'sample_count': len(rows), 'false_alarm_count': sum(fp), 'real_bug_count': sum(bug),
            'real_bug_deletion_cases': [r['sample_id'] for r in rows if r['label'] == 1 and r['status'] == 'success' and r['prediction'] == 'filter'],
            'note': 'Historical unclassified did not define a deletion action. Do not equate missing prediction with deleted bug.'}


def main():
    # No user-provided list/full-dataset switch: this run is bounded to 30 IDs.
    if len(sys.argv) != 1:
        raise SystemExit('This entry accepts no arguments and only replays the sealed 30 cases')
    target = RUN/'offline_regression'
    if target.exists():
        raise SystemExit('Output already exists; refusing overwrite. Use saved regression results.')
    baseline_count = baseline_unchanged()
    all_rows = read(ROOT/'results/processed/expanded_all_npd.json')
    by_id = {r['sample_id']: r for r in all_rows}
    audited = read(AUDIT/'audit_samples.json')
    holdout = read(RUN/'fixed_holdout.json')
    selections = [('audit', r['sample_id'], r['audit_id']) for r in audited]
    selections += [('holdout', r['sample_id'], None) for r in holdout['samples']]
    assert len(selections) == 30 and len({s[1] for s in selections}) == 30
    target.mkdir()
    started = time.perf_counter()
    output, bindings = [], []
    for group, sid, aid in selections:
        row = by_id[sid]
        if group == 'holdout':
            locked = next(x for x in holdout['samples'] if x['sample_id'] == sid)
            assert file_sha(ROOT/'upstream'/row['dataset']) == locked['dataset_sha256']
            assert row['label'] == locked['dataset_label']
        bundle, binding = load_bundle(row, aid)
        result = decide(bundle)  # No semantic approvals are fabricated for historical logs.
        item = {**result, 'cohort': group, 'audit_id': aid, 'dataset_label': row['label'],
                'label_confidence': 'published_label_unverified_individually',
                'original_prediction': row['prediction'], 'original_status': row['status'],
                'original_duration_seconds': row['duration_seconds'],
                'original_api_calls': row['api_calls'],
                'original_cost_upper_cny': row['cost_upper_bound_cny']}
        output.append(item)
        bindings.append(binding)
        save_new(target/'evidence'/f'{len(output):02d}.json', bundle)
    save_new(target/'decisions.json', output)
    save_new(target/'evidence_bindings.json', bindings)
    with (target/'decisions.csv').open('x', encoding='utf-8-sig', newline='') as handle:
        fields = ['sample_id', 'cohort', 'audit_id', 'dataset_label', 'label_confidence',
                  'original_status', 'original_prediction', 'verdict', 'action',
                  'filter_evidence_complete', 'evidence_sha256', 'review_sha256',
                  'decision_seconds', 'original_duration_seconds', 'original_api_calls',
                  'original_cost_upper_cny', 'new_model_calls', 'new_api_cost_cny', 'reason_codes']
        writer = csv.DictWriter(handle, fields, extrasaction='ignore')
        writer.writeheader()
        for row in output:
            writer.writerow({**row, 'reason_codes': json.dumps(row['reason_codes'], ensure_ascii=False)})
    metrics = {}
    for group in ('audit', 'holdout', 'combined'):
        subset = [r for r in output if group == 'combined' or r['cohort'] == group]
        metrics[group] = {'guarded': evaluate(subset),
                          'baseline': baseline_summary([by_id[r['sample_id']] for r in subset]),
                          'verdict_counts': dict(Counter(r['verdict'] for r in subset))}
    save_new(target/'metrics.json', metrics)
    assert baseline_unchanged() == baseline_count
    ledger = read(ROOT/'results/raw/completed/budget_ledger.json')
    ref = read(RUN/'baseline_reference.json')
    assert len(ledger['calls']) == ref['model_calls_before']
    assert ledger['cost_upper_bound_cny'] == ref['cost_upper_bound_cny_before']
    save_new(target/'verification.json', {
        'time': datetime.now(timezone(timedelta(hours=8))).isoformat(),
        'policy_version': VERSION, 'baseline_files_unchanged': baseline_count,
        'sample_count': len(output), 'full_benchmark_rerun': False,
        'model_calls_before': ref['model_calls_before'], 'model_calls_after': len(ledger['calls']),
        'api_calls_added': 0, 'api_cost_added_cny': 0,
        'holdout_manifest_sha256': file_sha(RUN/'fixed_holdout.json'),
        'elapsed_seconds': time.perf_counter() - started,
        'policy_source_sha256': {p.relative_to(ROOT).as_posix(): file_sha(p) for p in sorted((ROOT/'safety').glob('*.py'))},
    })
    print(json.dumps({g: {'verdicts': v['verdict_counts'],
                         'retention': v['guarded']['operational_real_bug_retention_rate'],
                         'deletion': v['guarded']['real_bug_deletion_rate'],
                         'filtering': v['guarded']['false_positive_filter_rate']}
                      for g, v in metrics.items()}, ensure_ascii=True, indent=2))


if __name__ == '__main__':
    main()
