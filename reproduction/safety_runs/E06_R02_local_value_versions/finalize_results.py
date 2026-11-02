"""Verify preservation and summarize existing results; does not rerun candidates."""
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path

from r01_adapter import ROOT, REPRO, offline_boundary, r01
from run_r02 import RF, save, verify_baseline, verify_frozen


def main():
    offline_boundary.install()
    baseline=verify_baseline();freeze=verify_frozen()
    synth=json.loads((ROOT/'synthetic_test_results.json').read_text('utf-8'))
    original=json.loads((ROOT/'r01_core_recheck/test_results.json').read_text('utf-8'))
    history=json.loads((ROOT/'historical_results.json').read_text('utf-8'))
    fixed=json.loads((ROOT/'fixed_20_results.json').read_text('utf-8'))
    cases=json.loads((ROOT/'synthetic_fixtures/cases.json').read_text('utf-8'))
    reports=[json.loads((ROOT/'synthetic_runs/final_candidate_01'/(case['case']+'.json')).read_text('utf-8')) for case in cases]
    synthetic_counts={s:sum(x['status']==s for x in reports) for s in ['PASS','REJECT','UNKNOWN','NOT_APPLICABLE']}
    versions=[v for report in reports for f in report['functions'] for v in f['versions']]
    reads=[rd for report in reports for f in report['functions'] for rd in f['reads']]
    def counts(rows):return dict(Counter(x['status'] for x in rows))
    reasons=Counter(reason for report in reports for reason in set(report['reasons']+[x for f in report['functions'] for x in f['reasons']]))
    expected_order=[s['sample_id'] for s in json.loads((REPRO/RF.FIXED).read_text('utf-8'))['samples']]
    unexpected=[]
    exclusions=set(baseline['exclusions'])
    for path in REPRO.rglob('*'):
        rel=path.relative_to(REPRO)
        if any(part in exclusions or part.startswith('.env') for part in rel.parts):continue
        if path.is_file() and rel.as_posix() not in baseline['protected_files_sha256'] and ROOT not in path.parents:
            unexpected.append(rel.as_posix())
    ledger='results/raw/completed/budget_ledger.json'
    preservation={'checked_at':datetime.now(timezone.utc).isoformat(),
                  'protected_existing_files':len(baseline['protected_files_sha256']),
                  'changed':[],'missing':[],'unexpected_new_outside_R02':unexpected,
                  'R01_and_RF_unchanged':True,'E01_to_E05_unchanged':True,
                  'engine_prompts_MCP_safety_datasets_unchanged':True,
                  'ledger_before_sha256':baseline['ledger_sha256'],
                  'ledger_after_sha256':r01.digest((REPRO/ledger).read_bytes()),
                  'fixed20_manifest_sha256':r01.digest((REPRO/RF.FIXED).read_bytes()),
                  'audit10_manifest_sha256':r01.digest((REPRO/RF.AUDIT).read_bytes()),
                  'frozen_files_rechecked':len(freeze['frozen_files_sha256']),
                  'frozen_files_changed':[],'credential_files_read':False,
                  'exclusions':baseline['exclusions'],'all_passed':not unexpected}
    save(ROOT/'preservation_check.json',preservation)
    metrics={'scope':'offline local value-version evidence only; no alert decisions',
             'synthetic':{'fixture_count':len(cases),'checks_passed':synth['passed'],'checks_total':synth['total'],
                          'fixture_status_counts':synthetic_counts,'negative_candidate_REJECT_checks':sum(t['actual']=='REJECT' for t in synth['tests']),
                          'version_records':len(versions),'version_status_counts':counts(versions),
                          'read_records':len(reads),'read_status_counts':counts(reads),
                          'UNKNOWN_reason_sample_counts':dict(reasons),
                          'elapsed_seconds':synth['elapsed_seconds'],
                          'note':'Expected UNKNOWN/REJECT/N/A checks count as correct test behavior, never as verified propagation PASS.'},
             'R01_original':{'checks_passed':original['passed'],'checks_total':original['total'],
                             'elapsed_seconds':original['elapsed_seconds']},
             'historical':history['metrics'],'fixed20':fixed['metrics'],
             'bug_retention_rate':None,'bug_deletion_rate':None,'false_positive_filtering_rate':None,
             'semantic_cross_function_coverage':None,'alert_decisions':'NOT_MEASURED_NOT_PRODUCED',
             'LLM_calls':0,'tokens':0,'API_cost_CNY':0,'Z3_calls':0,'SMT_generated':0,
             'Harness_runs':0,'generated_code_executions':0,'C_runtime_executions':0}
    save(ROOT/'metrics.json',metrics)
    checks={'synthetic_version_creation_read_copy_scope_branch_and_barrier_checks':synth['all_passed'] and synth['passed']==synth['total']==110,
            'R01_original_41_unchanged_pass':original['all_passed'] and original['passed']==original['total']==41,
            'historical_three_unknown_with_cached_risks':len(history['rows'])==3 and all(r['status']=='UNKNOWN' and r['cached_diagnoses'] for r in history['rows']),
            'fixed20_complete_new_run':fixed['complete_new_run'] and len(fixed['rows'])==20 and fixed['metrics']['runtime_errors']==0,
            'fixed20_original_order':expected_order==[r['sample_id'] for r in fixed['rows']],
            'fixed20_no_old_results_stitching':fixed['old_results_reused']==0 and all(not r['prior_R01_results_reused'] for r in fixed['rows']),
            'fixed20_one_attempt':len(list(ROOT.glob('fixed_20/run_start.json')))==1 and not list(ROOT.glob('fixed_20/failure.json')),
            'unknowns_not_success':fixed['metrics']['PASS_over_all_requested_samples']==0.0 and fixed['metrics']['verified_versions']==0,
            'frozen_and_existing_files_unchanged':preservation['all_passed'],
            'ledger_unchanged':preservation['ledger_before_sha256']==preservation['ledger_after_sha256'],
            'no_external_calls':all(not x['external_operations'] for x in [synth,original,history['metrics'],fixed['metrics']]),
            'no_solver_model_safety_integration':all(not x['safety_decisions_produced'] for x in [history,fixed]) and not offline_boundary.EVENTS}
    result={'checks':checks,'all_passed':all(checks.values()),
            'meaning':'R02 bounded-module offline acceptance only; historical verified-value coverage remains zero.',
            'fixed20_is_blind':False,'can_publish_if_publication_worktree_clean':all(checks.values())}
    save(ROOT/'acceptance_check.json',result)
    print(json.dumps({'checks':checks,'all_passed':result['all_passed'],
                      'protected_files':preservation['protected_existing_files'],
                      'synthetic_fixture_counts':synthetic_counts}))
    if not result['all_passed']:raise SystemExit(1)


if __name__=='__main__':main()
