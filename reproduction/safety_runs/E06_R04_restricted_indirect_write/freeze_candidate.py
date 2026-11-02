"""Freeze a single R04 candidate only after all offline prerequisites."""
from datetime import datetime,timezone
import json
from r03_adapter import ROOT,REPRO,r01,offline_boundary
from run_r04 import save,verify_baseline
from r04_protection import preservation,environment


def main():
    offline_boundary.install();baseline=verify_baseline()
    assert not (ROOT/'candidate_manifest.json').exists() and not (ROOT/'fixed_20').exists()
    requirements=[('synthetic_runs/final_candidate_01/synthetic_test_results.json',257),('r01_core_recheck/test_results.json',41),
        ('r02_core_recheck/synthetic_test_results.json',110),('r03_core_recheck/synthetic_test_results.json',201),('r03_boundary_recheck/test_results.json',15)]
    for rel,n in requirements:
        data=json.loads((ROOT/rel).read_text('utf-8'));assert data['all_passed'] and data['total']==data['passed']==n and not data['external_operations']
    audit=json.loads((ROOT/'pre_freeze_evidence_check.json').read_text('utf-8'));assert audit['all_passed']
    hist=json.loads((ROOT/'historical_results.json').read_text('utf-8'))
    assert len(hist['rows'])==4 and hist['metrics']['runtime_errors']==0 and all(r['status']=='UNKNOWN' for r in hist['rows'])
    protected=preservation();assert protected['status']=='PASS';save(ROOT/'pre_freeze_preservation_check.json',protected)
    env=environment()
    with (ROOT/'synthetic_test_results.json').open('xb') as f:f.write((ROOT/'synthetic_runs/final_candidate_01/synthetic_test_results.json').read_bytes())
    hashes=dict(baseline['protected_files_sha256'])
    hashes.update({p.relative_to(REPRO).as_posix():r01.digest(p.read_bytes()) for p in ROOT.rglob('*')
        if p.is_file() and '__pycache__' not in p.parts and p.name!='execution_log.md'})
    manifest={'candidate':'E06-R04-restricted-indirect-write-01','frozen_at':datetime.now(timezone.utc).isoformat(),
        'publication_baseline':baseline['publication_head'],'upstream_frozen_commit':'4efb4b9bf7e845e180451b43ba29a25e3edaa0e3',
        'frozen_files_sha256':dict(sorted(hashes.items())),'environment':env,
        'fixed20_is_blind':False,'fixed20_attempts_before_freeze':0,'fixed20_allowed_attempts':1,
        'preconditions':{'synthetic_scenarios':68,'synthetic_checks':257,'R01_checks':41,'R02_checks':110,'R03_checks':201,'R03_boundary_checks':15,
            'historical_unknown':4,'all_existing_files_unchanged':True,'protected_existing_files':len(baseline['protected_files_sha256'])},
        'summary_cache':False,'R05_started':False,'safety_integration':False,'filter_authority':False}
    save(ROOT/'candidate_manifest.json',manifest)
    print(json.dumps({'candidate_manifest_sha256':r01.digest((ROOT/'candidate_manifest.json').read_bytes()),'frozen_files':len(hashes),
        'protected_files':len(baseline['protected_files_sha256']),'fixed20_attempts':0}))


if __name__=='__main__':main()
