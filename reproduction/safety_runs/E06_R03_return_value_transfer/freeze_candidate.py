"""One freeze after prerequisites; fixed regression has a one-shot output marker."""
from datetime import datetime, timezone
import json
from adapter import ROOT, REPRO, r01, offline_boundary
from run_r03 import save, verify_baseline
from protection import preservation, environment


def main():
    offline_boundary.install();baseline=verify_baseline()
    assert not (ROOT/'fixed_20').exists() and not (ROOT/'candidate_manifest.json').exists()
    for rel,n in [('synthetic_runs/final_candidate_02/synthetic_test_results.json',201),
                  ('input_boundary_final/test_results.json',15),('r01_core_recheck/test_results.json',41),
                  ('r02_core_recheck/synthetic_test_results.json',110)]:
        obj=json.loads((ROOT/rel).read_text('utf-8'))
        assert obj['all_passed'] and obj['passed']==obj['total']==n and not obj['external_operations']
    audit=json.loads((ROOT/'pre_freeze_evidence_check.json').read_text('utf-8'));assert audit['all_passed']
    hist=json.loads((ROOT/'historical_results.json').read_text('utf-8'))
    assert hist['metrics']['runtime_errors']==0 and len(hist['rows'])==4 and all(r['status']=='UNKNOWN' for r in hist['rows'])
    check=preservation();assert check['status']=='PASS'
    save(ROOT/'pre_freeze_preservation_check.json',check)
    env=environment()
    summary=(ROOT/'synthetic_runs/final_candidate_02/synthetic_test_results.json').read_bytes()
    with (ROOT/'synthetic_test_results.json').open('xb') as f:f.write(summary)
    hashes=dict(baseline['protected_files_sha256'])
    hashes.update({p.relative_to(REPRO).as_posix():r01.digest(p.read_bytes()) for p in ROOT.rglob('*')
                   if p.is_file() and '__pycache__' not in p.parts and p.name!='execution_log.md'})
    manifest={'candidate':'E06-R03-return-value-transfer-01','frozen_at':datetime.now(timezone.utc).isoformat(),
         'publication_baseline':baseline['publication_head'],
         'upstream_frozen_commit':'4efb4b9bf7e845e180451b43ba29a25e3edaa0e3',
         'frozen_files_sha256':dict(sorted(hashes.items())),'environment':env,
         'fixed20_is_blind':False,'fixed20_attempts_before_freeze':0,'fixed20_allowed_attempts':1,
         'preconditions':{'R03_scenarios':66,'R03_checks':201,'input_checks':15,'R01_checks':41,'R02_checks':110,
                          'historical_unknown':4,'protected_existing_files':len(baseline['protected_files_sha256']),
                          'evidence_check_passed':True,'outside_scope_operations':[]},
         'filter_authority':False,'summary_cache':False,'R04_R05_started':False}
    save(ROOT/'candidate_manifest.json',manifest)
    print(json.dumps({'frozen_files':len(hashes),'candidate_manifest_sha256':r01.digest((ROOT/'candidate_manifest.json').read_bytes()),
                      'protected_existing_files':len(baseline['protected_files_sha256']),'fixed20_attempts':0}))


if __name__=='__main__':main()
