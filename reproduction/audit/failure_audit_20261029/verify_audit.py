"""Validate audit delivery and baseline immutability without network calls."""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess
import zipfile
from datetime import datetime, timezone, timedelta

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    frozen=read(HERE/'frozen_state.json')
    changed=[name for name,item in frozen['files'].items() if not (ROOT/name).is_file() or sha(ROOT/name)!=item['sha256']]
    assert not changed,'Baseline file changed; see local audit state'
    assert sha(HERE/'frozen_snapshot.zip')==frozen['snapshot_sha256']
    with zipfile.ZipFile(HERE/'frozen_snapshot.zip') as archive:
        assert archive.testzip() is None
        assert len(archive.namelist())==frozen['file_count']
        assert all(not Path(name).name.startswith('.env') for name in archive.namelist())
        assert all(hashlib.sha256(archive.read(name)).hexdigest()==item['sha256'] for name,item in frozen['files'].items())
    status=subprocess.check_output(['git','-C',str(ROOT/'upstream'),'status','--porcelain'],text=True).strip()
    commit=subprocess.check_output(['git','-C',str(ROOT/'upstream'),'rev-parse','HEAD'],text=True).strip()
    assert not status and commit==frozen['upstream_commit']
    rows=read(HERE/'audit_samples.json');assert len(rows)==10
    call_count=0
    for row in rows:
        base=HERE/'samples'/row['audit_id']
        for filename in ['audit.md','original_alert.json','recorded_result.json','parsed_model_outputs.json','argument_parameter_mapping.json','evidence_index.json']:
            assert (base/filename).is_file(),filename
        assert row['sample_id']==read(base/'original_alert.json').get('sample_id',row['sample_id'])
        saved=read(base/'recorded_result.json')
        assert saved['sample_id']==row['sample_id']
        original_source=read(ROOT/'upstream'/saved['dataset'])[saved['row_position']]
        assert original_source==read(base/'original_alert.json')
        for p in (base/'recorded_raw').rglob('*'):
            if p.is_file():assert sha(p)==sha(ROOT/saved['raw_output']/p.relative_to(base/'recorded_raw'))
        assert len(row['final_attempt_call_ids'])==saved['api_calls']
        for cid in row['final_attempt_call_ids']:
            p=base/'calls'/f'{cid:04d}.json'
            assert sha(p)==sha(ROOT/'results/raw/completed/calls'/f'{cid:04d}.json')
            call_count+=1
    ledger=read(ROOT/'results/raw/completed/budget_ledger.json')
    assert len(ledger['calls'])==1187 and abs(ledger['cost_upper_bound_cny']-4.49133)<1e-8
    assert not any(c['status']=='reserved' for c in ledger['calls'])
    metrics=read(HERE/'independent_metrics_check.json');assert all(metrics['matches_existing'].values())
    assert read(HERE/'data_version_check.json')['data_manifest_hashes_match']
    pop=read(HERE/'population_diagnostics.json')
    assert len(pop['solver_query_replays'])==310
    assert sum(x['matches'] is True for x in pop['solver_query_replays'])==303
    mixed=read(HERE/'same_symbol_sort_audit.json')
    assert len(mixed)==7 and all(x['matches_recorded_feasible'] for x in mixed)
    assert len(read(HERE/'format_failures_audit.json'))==5
    assert all(x['valid_explicit_json_array_later'] for x in read(HERE/'format_failures_audit.json'))
    assert (ROOT/'failure_audit.md').is_file() and (ROOT/'logs/stage_08_failure_audit.md').is_file()
    # Inspect only the locally configured key in memory to check the NEW delivery.
    # Never print it, its length, a hash, or an excerpt. No environment mutation.
    from dotenv import dotenv_values
    key=os.environ.get('DEEPSEEK_APIkey') or dotenv_values(ROOT/'.env').get('DEEPSEEK_APIkey')
    assert key,'Local key unavailable for non-disclosure verification'
    inspected=0
    for p in list(HERE.rglob('*'))+[ROOT/'failure_audit.md',ROOT/'logs/stage_08_failure_audit.md']:
        if p.is_file() and p.suffix!='.zip':
            assert key.encode() not in p.read_bytes(),'Credential match in new delivery; value suppressed'
            inspected+=1
    with zipfile.ZipFile(HERE/'frozen_snapshot.zip') as archive:
        assert all(key.encode() not in archive.read(name) for name in archive.namelist()),'Credential match in snapshot; value suppressed'
    # Check local links written into the standalone audit report.
    broken=[]
    for target in re.findall(r'\]\(([^)]+)\)',(ROOT/'failure_audit.md').read_text(encoding='utf-8')):
        if not target.startswith('http') and not Path(target).exists():broken.append(target)
    assert not broken,'Broken local report link'
    result={'time':datetime.now(timezone(timedelta(hours=8))).isoformat(),'passed':True,
        'baseline_files_verified_unchanged':len(frozen['files']),'upstream_commit':commit,'upstream_clean':True,
        'snapshot_files_verified':frozen['file_count'],'selected_samples':len(rows),'final_attempt_call_copies':call_count,
        'independent_metrics_match':True,'data_hashes_match':True,
        'saved_solver_queries':310,'direct_SMT2_replays_match':303,'mixed_sort_original_worker_replays_match':7,
        'model_calls_before':1187,'model_calls_after':len(ledger['calls']),'model_calls_added':0,
        'baseline_predictions_modified':False,'production_code_modified':False,'local_report_links_valid':True,
        'local_user_key_matches_in_new_delivery':0,'new_non_zip_files_scanned':inspected,
        'snapshot_credential_scan_passed':True,'api_cost_added_cny':0}
    (HERE/'audit_verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=True,indent=2))

if __name__=='__main__':main()
