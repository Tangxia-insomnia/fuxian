"""Verify expanded evidence without model calls or credential disclosure."""
from collections import Counter
from datetime import datetime, timedelta, timezone
import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from dotenv import dotenv_values

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from completion.metrics import evaluate
from completion.model import save
from scripts.run_expanded import GROUPS


def load(path):
    return json.loads((ROOT/path).read_text(encoding='utf-8'))


def main():
    now=datetime.now(timezone(timedelta(hours=8))).isoformat()
    ledger=load('results/raw/completed/budget_ledger.json')
    bundle=load('results/metrics/expanded_metrics.json')
    combined=load('results/processed/expanded_all_npd.json')
    attempts={}; ids=set(); summaries={}; all_rows=[]
    for group,(dataset,_,_) in GROUPS.items():
        source=load('upstream/'+dataset)
        rows=load(f'results/processed/completed_expanded_{group}.json')
        manifest=load(f'configs/expanded_{group}_manifest.json')
        expected={i for i,r in enumerate(source) if type(r.get('result')) is int and r['result'] in (0,1)}
        assert expected==set(manifest['row_positions_zero_based'])=={r['row_position'] for r in rows}, 'Incomplete selection: '+group
        assert len(expected)==len(rows), 'Duplicate row: '+group
        assert manifest['dataset_sha256']==hashlib.sha256((ROOT/'upstream'/dataset).read_bytes()).hexdigest(), 'Data hash mismatch'
        with (ROOT/f'results/processed/completed_expanded_{group}.csv').open(encoding='utf-8-sig',newline='') as f:
            csv_rows=list(csv.DictReader(f))
        assert len(csv_rows)==len(rows), 'Group CSV length mismatch'
        for row in rows:
            assert row['sample_id'] not in ids, 'Repeated sample across groups'
            ids.add(row['sample_id'])
            assert row['label']==source[row['row_position']]['result'], 'Original label mismatch'
            assert row['original_index']==source[row['row_position']].get('index'), 'Index mismatch'
            csv_row=next(r for r in csv_rows if r['sample_id']==row['sample_id'])
            assert csv_row['prediction']==(row['prediction'] or '') and csv_row['status']==row['status'], 'CSV classification mismatch'
            assert row in combined, 'Combined JSON differs from group result'
            folder=ROOT/row['raw_output']
            raw=json.loads((folder/'sample_result.json').read_text(encoding='utf-8'))
            assert all(raw[k]==row[k] for k in ['sample_id','label','status','prediction','api_calls']), 'Raw result mismatch'
            attempts[row['raw_output']]=row
            if row['status']=='success':
                assert row['prediction'] in {'keep','filter'} and row['api_calls']>0, 'Invalid success'
                good=[json.loads(p.read_text(encoding='utf-8')) for p in sorted(folder.glob('solver_*.json'))]
                good=[r for r in good if r.get('ok')]
                if good:
                    assert all(e['queries'] and all(q['result'] in {'sat','unsat'} for q in e['queries']) for e in good), 'Invalid SMT evidence'
                    assert good[-1]['feasible']==(row['prediction']=='keep'), 'SMT/decision mismatch'
                else:
                    assert row['prediction']=='filter' and row.get('decision_basis')=='author_llm_context_early_exit', 'Unrecorded non-SMT classification'
            else:
                assert row['prediction'] is None and row['error'], 'Failure lost or counted as prediction'
        metrics=evaluate(rows)
        assert metrics==bundle['groups'][group], 'Group metric mismatch'
        summaries[group]={'selected':len(rows),'successful':metrics['successful'],'blocked':metrics['blocked'],'failed':metrics['failed']}
        all_rows+=rows
    for path in (ROOT/'results/processed').glob('completed_*_attempt_history.json'):
        for row in json.loads(path.read_text(encoding='utf-8')):
            attempts[row['raw_output']]=row
    assert len(ids)==len(combined)==278, 'Expanded count mismatch'
    with (ROOT/'results/processed/expanded_all_npd.csv').open(encoding='utf-8-sig',newline='') as f:
        combined_csv=list(csv.DictReader(f))
    assert {r['sample_id'] for r in combined_csv}==ids and len(combined_csv)==278, 'Combined CSV mismatch'
    assert evaluate(all_rows)==bundle['overall'], 'Overall metric mismatch'
    assert sum(r['api_calls'] for r in attempts.values())==len(ledger['calls']), 'Attempt/API count mismatch'
    for sid in ids:
        assert sum(r['api_calls'] for r in attempts.values() if r['sample_id']==sid)==sum(c['sample_id']==sid for c in ledger['calls']), 'Per-sample call mismatch'
    assert not any(c['status']=='reserved' for c in ledger['calls']), 'Unresolved request reservation'
    assert abs(sum(c['cost_upper_bound_cny'] for c in ledger['calls'])-ledger['cost_upper_bound_cny'])<1e-8, 'Budget ledger mismatch'
    assert 0<=ledger['cost_upper_bound_cny']<=10, 'Cumulative budget exceeded'
    files=sorted((ROOT/'results/raw/completed/calls').glob('*.json'))
    assert len(files)==len(ledger['calls']), 'Missing raw API call'
    returned=Counter()
    for call,path in zip(ledger['calls'],files):
        raw=json.loads(path.read_text(encoding='utf-8'))
        assert raw['call_id']==call['call_id'] and raw['sample_id']==call['sample_id'], 'Raw API identity mismatch'
        assert raw.get('usage')==call.get('usage'), 'Usage mismatch'
        returned[str(raw.get('model_returned'))]+=1
    key=os.environ.get('DEEPSEEK_APIkey') or dotenv_values(ROOT/'.env').get('DEEPSEEK_APIkey')
    assert key, 'No key available for local leak check'
    matches=[]; scanned=0
    for directory,folders,names in os.walk(ROOT):
        folders[:]=[f for f in folders if f not in {'.venv','upstream','.git','pip-cache','__pycache__'}]
        for name in names:
            if name=='.env' or name.startswith('.env.') and name!='.env.example':
                continue
            path=Path(directory)/name; scanned+=1
            if key.encode('utf-8') in path.read_bytes():matches.append(path.relative_to(ROOT).as_posix())
    assert not matches, 'Local credential detected; value not printed'
    sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT/'upstream',text=True).strip()
    status=subprocess.check_output(['git','status','--porcelain'],cwd=ROOT/'upstream',text=True)
    assert sha=='4efb4b9bf7e845e180451b43ba29a25e3edaa0e3' and not status, 'Wrong upstream or modified sources'
    hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in list((ROOT/'completion').glob('*.py'))+list((ROOT/'scripts').glob('*.py'))+[ROOT/'configs/expanded_experiment.json']}
    save(ROOT/'configs/expanded_run_identity.json',{'timestamp':now,'upstream_commit':sha,'source_sha256':hashes,'returned_models':returned,'data_manifests':{g:load(f'configs/expanded_{g}_manifest.json') for g in GROUPS}})
    result={'timestamp':now,'passed':True,'groups':summaries,'unique_selected':len(ids),'unique_attempts_including_history':len(attempts),'api_calls':len(ledger['calls']),'cost_upper_bound_cny':ledger['cost_upper_bound_cny'],'credential_scan_files':scanned,'credential_match_count':len(matches),'upstream_clean':True,'metrics_recomputed':True,'original_25_not_double_counted':True}
    save(ROOT/'results/raw/completed/expanded_verification.json',result)
    print(json.dumps(result,ensure_ascii=True))


if __name__=='__main__':
    main()
