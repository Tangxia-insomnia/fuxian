"""Offline E01 phases. Run synthetic/audit, freeze, then fixed regression once."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import difflib
import hashlib
import json
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
from offline_guard import install
VIOLATIONS = install(HERE)
from predicate_check import VERSION
from offline_adapter import inspect_bundle
from safety.policy import decide
from safety.metrics import evaluate

AUDIT = 'audit/failure_audit_20261029/audit_samples.json'
HOLDOUT = 'safety_runs/20261029_v1/fixed_holdout.json'
EVIDENCE = ROOT / 'safety_runs/20261029_v1/offline_regression/evidence'
DECISIONS = ROOT / 'safety_runs/20261029_v1/offline_regression/decisions.json'


def now():
    return datetime.now(timezone.utc).astimezone().isoformat()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(name, value):
    with (HERE / name).open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + '\n' if not isinstance(value, str) else value)


def log(text):
    with (HERE / 'execution_log.md').open('a', encoding='utf-8') as stream:
        stream.write('\n' + now() + '：' + text + '\n')


def verify_protected():
    baseline = read(HERE / 'baseline_state.json')
    changes = []
    for rel, expected in baseline['protected_sha256'].items():
        path = ROOT / rel
        if not path.is_file() or sha(path) != expected:
            changes.append(rel)
    if changes:
        raise RuntimeError('STOP: protected_files_changed:' + repr(changes))
    for rel, expected in baseline['fixed_input_sha256'].items():
        if sha(ROOT / rel) != expected:
            raise RuntimeError('STOP: fixed_manifest_changed:' + rel)
    if VIOLATIONS:
        raise RuntimeError('STOP: offline_guard_violation')
    return {'checked_at': now(), 'protected_file_count': len(baseline['protected_sha256']),
            'changed_files': changes, 'fixed_inputs_match': True,
            'guard_violations': list(VIOLATIONS), 'new_model_calls': 0, 'new_api_cost_cny': 0}


def overlay(gate, check):
    """R01 can only reject/degrade. It can never promote a verdict to FILTER."""
    row = dict(gate)
    if check['status'] != 'consistent' or not check['whole_sample_supported']:
        row.update(verdict='UNKNOWN', action='KEEP', filter_evidence_complete=False)
        row['reason_codes'] = sorted(set(row['reason_codes'] + ['e01_' + check['status']]))
    if row['verdict'] == 'FILTER' and not gate['filter_evidence_complete']:
        raise RuntimeError('STOP: incomplete_evidence_filter')
    row['e01_version'] = VERSION
    return row


def run_cohort(cohort):
    verify_protected()
    if cohort == 'holdout':
        verify_freeze()
    manifest = read(ROOT / (AUDIT if cohort == 'audit' else HOLDOUT))
    samples = manifest if cohort == 'audit' else manifest['samples']
    assert len(samples) == (10 if cohort == 'audit' else 20)
    baseline = read(DECISIONS)
    offset = 0 if cohort == 'audit' else 10
    rows = []
    started = time.perf_counter()
    for n, item in enumerate(samples, offset + 1):
        path = EVIDENCE / f'{n:02}.json'
        bundle = read(path)
        old = baseline[n - 1]
        if item['sample_id'] != old['sample_id'] or old['sample_id'] != bundle['candidate']['sample_id']:
            raise RuntimeError('STOP: fixed_sample_order_or_identity_mismatch')
        label = item['label'] if cohort == 'audit' else item['dataset_label']
        if old['dataset_label'] != label:
            raise RuntimeError('STOP: fixed_label_mismatch')
        sample_start = time.perf_counter()
        gate = decide(bundle)  # original real-bugs-first-v1, no fabricated review
        if gate['verdict'] != old['verdict']:
            raise RuntimeError('STOP: frozen_v1_replay_verdict_changed')
        check_start = time.perf_counter()
        check = inspect_bundle(bundle)  # no labels/IDs used to select algorithm behavior
        check_seconds = time.perf_counter() - check_start
        decision = overlay(gate, check)
        decision.update({k: old[k] for k in ('cohort', 'audit_id', 'dataset_label', 'label_confidence',
                        'original_prediction', 'original_status', 'original_duration_seconds',
                        'original_api_calls', 'original_cost_upper_cny') if k in old})
        decision.update(baseline_v1_verdict=old['verdict'], baseline_v1_action=old['action'],
                        unchanged_v1_gate=gate, r01=check, r01_seconds=check_seconds,
                        offline_total_seconds=time.perf_counter() - sample_start,
                        input_evidence_path=str(path.relative_to(ROOT)), input_evidence_sha256=sha(path))
        rows.append(decision)
        if decision['verdict'] == 'FILTER' and (label == 1 or not decision['filter_evidence_complete']):
            write(cohort + '_stopped_results.json', rows)
            raise RuntimeError('STOP: real_bug_or_incomplete_evidence_filtered')
    checks = []
    if cohort == 'audit':
        by_id = {r['audit_id']: r for r in rows}
        copied = [c for c in by_id['A01']['r01']['checks'] if c['original_expression'] == '!copied']
        checks = [
            {'test': 'A01_saved_wrong_polarity_detected', 'passed': any(c['local_status'] == 'mismatch' for c in copied)},
            {'test': 'A10_macro_not_falsely_flagged', 'passed': by_id['A10']['r01']['conflicting_condition_count'] == 0},
            {'test': 'A10_stays_UNKNOWN', 'passed': by_id['A10']['verdict'] == 'UNKNOWN'},
            {'test': 'A02_real_bug_not_filtered', 'passed': by_id['A02']['verdict'] != 'FILTER'},
            {'test': 'A04_identity_not_bypassed', 'passed': by_id['A04']['verdict'] == 'UNKNOWN'},
        ]
    preservation = verify_protected()
    if cohort == 'holdout':
        verify_freeze()
    output = {'cohort': cohort, 'completed_at': now(), 'sample_count': len(rows), 'rows': rows,
              'acceptance_checks': checks, 'passed': all(c['passed'] for c in checks),
              'offline_seconds': time.perf_counter() - started, 'preservation': preservation,
              'network_guard_violations': list(VIOLATIONS), 'new_model_calls': 0, 'new_api_cost_cny': 0,
              'experiment_kind': 'cached-response offline diagnostic + saved SMT replay, not new E2E inference'}
    write(cohort + '_results.json', output)
    log(f'{cohort} 完成：{len(rows)} 条；判定 {dict(Counter(r["verdict"] for r in rows))}；'
        f'局部冲突样本 {sum(r["r01"]["conflicting_condition_count"] > 0 for r in rows)}；'
        f'验收检查 {checks}；API 0。')
    if not output['passed']:
        raise RuntimeError('STOP: audit_expectation_failed')
    return {'sample_count': len(rows), 'verdicts': dict(Counter(r['verdict'] for r in rows))}


def synthetic():
    verify_protected()
    from test_synthetic import run_tests
    result = run_tests()
    # Ensure a locally passing predicate cannot bypass the unchanged six gates.
    code = 'int x;\nif (x) {\n sink();\n}\n'
    code_sha = hashlib.sha256(code.encode()).hexdigest()
    bundle = {'scope': 'synthetic_fixture', 'candidate': {'sample_id': 'synthetic/no_review',
              'status': 'success', 'prediction': 'filter', 'error': None},
              'alert': {'var_name': 'x', 'function_code': code,
                        'location': {'context': {'snippet': {'text': 'sink();'}}}},
              'context': {'frames': [{'code': code, 'target': 'sink();', 'var_name': 'x',
                                     'body_sha256': code_sha, 'extracted': {}}]},
              'recorded_answer': {'result': False}, 'issues': [],
              'solver_events': [{'ok': True, 'feasible': False, 'queries': [
                  {'smt2': '(declare-const x Int) (assert (= x 0)) (assert (not (= x 0)))', 'result': 'unsat'}]}]}
    gate = decide(bundle)
    no_bypass = overlay(gate, {'status': 'consistent', 'whole_sample_supported': True})
    result['tests'].append({'test': 'local_pass_cannot_authorize_filter_without_semantic_review',
                            'expected': 'UNKNOWN', 'actual': no_bypass['verdict'],
                            'passed': no_bypass['verdict'] == 'UNKNOWN'})
    result['test_count'] = len(result['tests'])
    result['pass_count'] = sum(t['passed'] for t in result['tests'])
    result['fail_count'] = result['test_count'] - result['pass_count']
    result['passed'] = result['fail_count'] == 0
    result['preservation'] = verify_protected()
    # Preserve a failed development attempt without replacing any historical file.
    name = 'test_results.json' if result['passed'] else f'test_failure_{time.time_ns()}.json'
    write(name, result)
    log(f'合成测试：{result["pass_count"]}/{result["test_count"]}；文件 {name}；API 0。')
    if not result['passed']:
        raise RuntimeError('STOP before holdout: synthetic_test_failure')
    return {k: result[k] for k in ('test_count', 'pass_count', 'fail_count', 'seconds')}


def freeze():
    verify_protected()
    assert read(HERE / 'test_results.json')['passed']
    assert read(HERE / 'audit_results.json')['passed']
    code_files = sorted(HERE.glob('*.py'))
    patch = ''.join(''.join(difflib.unified_diff([], p.read_text('utf-8').splitlines(True),
                        fromfile='/dev/null', tofile='b/' + str(p.relative_to(ROOT)).replace('\\', '/')))
                    for p in code_files)
    write('patch.diff', patch)
    files = code_files + [HERE / x for x in ('baseline_state.json', 'test_results.json', 'audit_results.json',
                                            'source_review.md', 'patch.diff')]
    frozen = {'frozen_at': now(), 'candidate_version': VERSION, 'files_sha256':
              {p.name: sha(p) for p in files}, 'must_not_tune_after_holdout': True,
              'fixed_manifest_sha256': read(HERE / 'baseline_state.json')['fixed_input_sha256'],
              'regression_scope': 'fixed 20, previously executed benchmark, not a blind test',
              'preservation': verify_protected()}
    write('candidate_freeze.json', frozen)
    log('候选代码、合成测试及审计结果已冻结；随后才运行固定20条回归集，不根据回归结果调参。')
    return {'frozen_at': frozen['frozen_at'], 'file_count': len(files)}


def verify_freeze():
    frozen = read(HERE / 'candidate_freeze.json')
    changes = [name for name, digest in frozen['files_sha256'].items() if sha(HERE / name) != digest]
    if changes:
        raise RuntimeError('STOP: frozen_candidate_changed:' + repr(changes))
    if sorted(p.name for p in HERE.glob('*.py')) != sorted(n for n in frozen['files_sha256'] if n.endswith('.py')):
        raise RuntimeError('STOP: candidate_code_added_after_freeze')
    return True


def cohort_metrics(rows):
    current = evaluate(rows)
    baseline = evaluate([dict(r, verdict=r['baseline_v1_verdict'], action=r['baseline_v1_action'],
                             filter_evidence_complete=False) for r in rows])
    conditions = sum(r['r01']['source_condition_count'] for r in rows)
    checked = sum(r['r01']['locally_checked_condition_count'] for r in rows)
    current.update(verdict_counts={v: sum(r['verdict'] == v for r in rows) for v in ('FILTER', 'KEEP', 'UNKNOWN')},
                   explicit_keep_real_bug_count=sum(r['dataset_label'] == 1 and r['verdict'] == 'KEEP' for r in rows),
                   polarity_conflict_sample_count=sum(r['r01']['conflicting_condition_count'] > 0 for r in rows),
                   polarity_conflict_condition_count=sum(r['r01']['conflicting_condition_count'] for r in rows),
                   polarity_conflict_atom_occurrences=sum(r['r01']['conflicting_atom_occurrences'] for r in rows),
                   recorded_condition_count=conditions, locally_checked_condition_count=checked,
                   local_support_subset_coverage=checked / conditions if conditions else None,
                   whole_sample_supported_count=sum(r['r01']['whole_sample_supported'] for r in rows),
                   whole_sample_supported_rate=sum(r['r01']['whole_sample_supported'] for r in rows) / len(rows),
                   r01_seconds=sum(r['r01_seconds'] for r in rows),
                   offline_processing_seconds=sum(r['offline_total_seconds'] for r in rows),
                   atoms_removed=sum(r['r01']['atoms_removed'] for r in rows),
                   rejected_or_unsupported_reasons=dict(sum((Counter(r['r01']['unsupported_reasons']) for r in rows), Counter())))
    baseline.update(verdict_counts={v: sum(r['baseline_v1_verdict'] == v for r in rows) for v in ('FILTER', 'KEEP', 'UNKNOWN')},
                    explicit_keep_real_bug_count=sum(r['dataset_label'] == 1 and r['baseline_v1_verdict'] == 'KEEP' for r in rows))
    return {'frozen_safety_v1': baseline, 'e01': current}


def finalize():
    verify_freeze()
    preservation = verify_protected()
    audit, holdout = read(HERE / 'audit_results.json'), read(HERE / 'holdout_results.json')
    metrics = {name: cohort_metrics(rows) for name, rows in
               [('audit', audit['rows']), ('holdout', holdout['rows']), ('combined', audit['rows'] + holdout['rows'])]}
    metrics['new_model_calls'] = 0
    metrics['new_api_cost_cny'] = 0
    metrics['scope'] = 'published label 1=real bug, 0=false alarm; labels not independently established truth'
    write('metrics.json', metrics)
    write('preservation_check.json', preservation)
    from report_e01 import report
    write('e01_report.md', report(read(HERE / 'baseline_state.json'), audit, holdout, metrics, read(HERE / 'test_results.json')))
    log('E01 完成并停止：所有保护文件逐字节哈希未变；固定清单未变；候选冻结校验通过；API 0；未进入R02/R03。')
    files = [p for p in HERE.rglob('*') if p.is_file() and p.name != 'hashes.json']
    write('hashes.json', {'created_at': now(), 'algorithm': 'SHA-256',
                         'self_excluded': 'hashes.json cannot contain its own digest',
                         'fixed_inputs': read(HERE / 'baseline_state.json')['fixed_input_sha256'],
                         'protected_inputs_and_original_code': 'baseline_state.json:protected_sha256',
                         'experiment_files': {str(p.relative_to(HERE)).replace('\\', '/'): sha(p) for p in sorted(files)}})
    return {'acceptance': 'bounded E01 offline safety/diagnostic pass; no evidence of filtering improvement',
            'combined_verdicts': metrics['combined']['e01']['verdict_counts'], 'preservation': preservation}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=['synthetic', 'audit', 'freeze', 'holdout', 'finalize'])
    phase = parser.parse_args().phase
    try:
        if phase in ('audit', 'holdout'):
            result = run_cohort(phase)
        else:
            result = {'synthetic': synthetic, 'freeze': freeze, 'finalize': finalize}[phase]()
        print(json.dumps(result, ensure_ascii=False))
    except Exception as exc:
        log('阶段失败/停止：' + phase + '；' + type(exc).__name__ + '；' + str(exc))
        write(f'stop_{phase}_{time.time_ns()}.json', {'phase': phase, 'error_type': type(exc).__name__,
              'error': str(exc), 'at': now(), 'guard_violations': list(VIOLATIONS)})
        raise


if __name__ == '__main__':
    main()
