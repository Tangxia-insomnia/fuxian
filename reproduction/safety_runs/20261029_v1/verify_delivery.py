"""Independent checks of saved regression outputs; never runs model or predictor."""
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    frozen = read(ROOT/'audit/failure_audit_20261029/frozen_state.json')
    for name, item in frozen['files'].items():
        assert sha(ROOT/name) == item['sha256'], name
    ref = read(HERE/'baseline_reference.json')
    assert sha(ROOT/ref['baseline_snapshot']) == ref['baseline_snapshot_sha256']
    holdout = read(HERE/'fixed_holdout.json')
    assert sha(HERE/'fixed_holdout.json') == ref['holdout_manifest_sha256']
    locked = holdout['samples']
    assert len(locked) == 20
    assert Counter(x['dataset_label'] for x in locked) == {0: 12, 1: 8}
    assert len({x['function_group_sha256'] for x in locked}) == 20
    assert not set(x['function_group_sha256'] for x in locked) & set(holdout['excluded_function_groups'])
    assert not set(x['sample_id'] for x in locked) & set(holdout['excluded_sample_ids'])
    target = HERE/'offline_regression'
    rows = read(target/'decisions.json')
    assert len(rows) == 30 and len({x['sample_id'] for x in rows}) == 30
    metrics = read(target/'metrics.json')
    binding = read(target/'evidence_bindings.json')
    for i, (row, original) in enumerate(zip(rows, binding), 1):
        assert row['sample_id'] == original['sample_id']
        for name, checksum in original['artifact_sha256'].items():
            assert sha(ROOT/name) == checksum
        evidence = read(target/'evidence'/f'{i:02d}.json')
        canonical = json.dumps(evidence, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()
        assert hashlib.sha256(canonical).hexdigest() == row['evidence_sha256'] == original['evidence_sha256']
        assert 'label' not in evidence['candidate'] and 'result' not in evidence['alert']
        assert row['action'] == ('FILTER' if row['verdict'] == 'FILTER' else 'KEEP')
        assert row['new_model_calls'] == 0 and row['new_api_cost_cny'] == 0
    for group in ['audit', 'holdout', 'combined']:
        selected = [x for x in rows if group == 'combined' or x['cohort'] == group]
        matrix = [[sum(x['dataset_label'] == y and x['verdict'] == v for x in selected)
                   for v in ['FILTER', 'KEEP', 'UNKNOWN']] for y in [0, 1]]
        recorded = metrics[group]['guarded']
        assert matrix == recorded['confusion_matrix']['values']
        assert sum(matrix[1]) > 0
        assert (matrix[1][1] + matrix[1][2])/sum(matrix[1]) == recorded['operational_real_bug_retention_rate']
        assert matrix[1][0]/sum(matrix[1]) == recorded['real_bug_deletion_rate']
        assert matrix[0][0]/sum(matrix[0]) == recorded['false_positive_filter_rate']
        assert sum(x['verdict'] == 'UNKNOWN' for x in selected) == recorded['unknown_count']
    with (target/'decisions.csv').open(encoding='utf-8-sig', newline='') as handle:
        csv_rows = list(csv.DictReader(handle))
    assert [(x['sample_id'], x['verdict'], x['action']) for x in rows] == [
        (x['sample_id'], x['verdict'], x['action']) for x in csv_rows]
    verification = read(target/'verification.json')
    for name, checksum in verification['policy_source_sha256'].items():
        assert sha(ROOT/name) == checksum
    ledger = read(ROOT/'results/raw/completed/budget_ledger.json')
    assert len(ledger['calls']) == ref['model_calls_before'] == 1187
    assert ledger['cost_upper_bound_cny'] == ref['cost_upper_bound_cny_before']
    result = {'passed': True, 'baseline_files_unchanged': len(frozen['files']),
              'selected_records_verified': len(rows), 'fixed_holdout': 20,
              'independent_metrics_and_csv_consistent': True,
              'evidence_bindings_consistent': True, 'new_api_calls': 0,
              'new_api_cost_cny': 0, 'full_benchmark_rerun': False}
    output = HERE/'delivery_verification.json'
    if not output.exists():
        with output.open('x', encoding='utf-8') as handle:
            json.dump(result, handle, ensure_ascii=False, indent=2)
    else:
        assert read(output) == result
    print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == '__main__':
    main()
