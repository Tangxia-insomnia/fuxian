"""New historical/fixed R03 checks over immutable saved source inputs."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import time
import traceback

from adapter import ROOT, REPRO, r01, rf_inputs, offline_boundary, counts
from return_transfer import analyze
import source_locator

RF=rf_inputs()


def save(path,obj):
    with path.open('x',encoding='utf-8',newline='\n') as f:
        json.dump(obj,f,indent=2,ensure_ascii=False);f.write('\n')


def checked(rel, baseline):
    path=REPRO/rel
    if r01.digest(path.read_bytes())!=baseline['protected_files_sha256'][rel]:
        raise RuntimeError('Protected file changed: '+rel)
    return json.loads(path.read_text('utf-8'))


def verify_baseline():
    baseline=json.loads((ROOT/'baseline_state.json').read_text('utf-8'))
    bad=[n for n,h in baseline['protected_files_sha256'].items()
         if not (REPRO/n).is_file() or r01.digest((REPRO/n).read_bytes())!=h]
    if bad:raise RuntimeError('Protected evidence changed: '+repr(bad))
    for name,h in [(RF.FIXED,RF.FIXED_HASH),(RF.AUDIT,RF.AUDIT_HASH)]:
        if r01.digest((REPRO/name).read_bytes())!=h:raise RuntimeError('Frozen input changed')
    return baseline


def fixed_specs(baseline):
    fixed=checked(RF.FIXED,baseline);inventory=checked(RF.INVENTORY,baseline)
    if len(fixed['samples'])!=20 or len(inventory['rows'])!=20:raise ValueError('Original 20 required')
    specs=[]
    for sample,entry in zip(fixed['samples'],inventory['rows']):
        for k in ['sample_id','row_position','dataset']:
            if sample[k]!=entry[k]:raise ValueError('Fixed order/binding mismatch')
        if r01.digest((REPRO/'upstream'/sample['dataset']).read_bytes())!=sample['dataset_sha256']:
            raise ValueError('Dataset hash mismatch')
        tool,project=sample['sample_id'].split('/')[1:3];project=project.split(':')[0]
        specs.append({'sample_id':sample['sample_id'],'dataset_id':tool+'_'+('linux' if project=='kernel69' else project),
                      'position':sample['row_position'],'dataset':sample['dataset'],'bundle':entry['bundle']})
    return specs


def check_sample(spec,output,baseline):
    start=time.perf_counter();output.mkdir(parents=True,exist_ok=False)
    if 'bundle' in spec:
        obj=checked(spec['bundle'],baseline)
        if obj['candidate']['sample_id']!=spec['sample_id']:raise ValueError('Sample identity mismatch')
        provenance=RF.null_context_provenance(spec,obj,baseline) if obj.get('context',False) is None else None
        state,frames=RF.context_state(obj,provenance)
        ref=spec['bundle'];historical_error=obj['candidate'].get('error') if frames is None else None
    else:
        obj=checked(spec['manifest'],baseline)
        for k in ['sample_id','dataset_id','position','dataset']:
            if obj[k]!=spec[k]:raise ValueError('Historical manifest identity mismatch')
        state,frames=RF.context_state({'context':{'frames':obj['frames']}})
        if (REPRO/spec['source']).read_bytes()!=frames[0]['code'].encode('utf-8'):
            raise ValueError('Historical source binding mismatch')
        provenance=None;historical_error=None;ref=spec['manifest']
    row={'sample_id':spec['sample_id'],'dataset_id':spec['dataset_id'],'position':spec['position'],
         'input_ref':ref,'input_sha256':r01.digest((REPRO/ref).read_bytes()),
         'dataset':spec['dataset'],'dataset_sha256':r01.digest((REPRO/'upstream'/spec['dataset']).read_bytes()),
         'status':'UNKNOWN','execution_status':'COMPLETED','context_state':state,
         'null_context_provenance':provenance,'historical_context_error':historical_error,
         'frames':[],'edges':[],'reasons':['missing_original_build_evidence'],
         'labels_used':False,'prior_R02_results_reused':False,'prior_solver_results_used':False,
         'verified_call_context_count':0,'verified_return_bindings':0,'verified_caller_results':0,
         'alert_action':None,'risk_locators':[],'prior_diagnoses_preserved':[]}
    if frames is None:row['reasons'].append('historical_saved_context_unavailable')
    elif not frames:row['reasons'].append('missing_saved_frames')
    for i,frame in enumerate(frames or []):
        blob=frame['code'].encode('utf-8')
        if r01.digest(blob)!=frame['body_sha256']:raise ValueError('Frame hash mismatch')
        source=output/f'frame_{i}.c';source.write_bytes(blob)
        report=analyze(source,dataset_id=spec['dataset_id'],position=spec['position'],
                       build_status='saved-source-only',caller=frame['function'])
        if report['status']!='UNKNOWN' or report['call_contexts'] or report['return_transfers'] or report['caller'] is not None:
            raise RuntimeError('Historical build gate bypass')
        save(output/f'frame_{i}_r03.json',report)
        row['frames'].append({'frame':i,'function':frame['function'],'body_sha256':frame['body_sha256'],
             'source_ref':ref+('#/context/frames/' if 'bundle' in spec else '#/frames/')+str(i),
             'report_file':f'frame_{i}_r03.json','status':'UNKNOWN','diagnostic_count':len(report['diagnostics']),
             'reasons':report['reasons'],'return_source_candidates':source_locator.returns(frame['code']),
             'verified_return_records':0,'verified_caller_result_versions':0})
    for i,(caller,callee) in enumerate(zip(frames or [],(frames or [])[1:])):
        row['edges'].append({'caller_frame':i,'callee_frame':i+1,'caller':caller['function'],'callee':callee['function'],
             'caller_body_sha256':caller['body_sha256'],'callee_body_sha256':callee['body_sha256'],
             'status':'UNKNOWN','callsite_candidates':source_locator.calls_to(caller['code'],callee['function']),
             'caller_result_versions':[],'return_guard_propagation':False,'callee_return_terminates_caller':False,
             'R05_path_composition_performed':False,'call_effect_coverage':'UNKNOWN','return_path_completeness':'UNKNOWN'})
    for locator in spec.get('locators',[]):
        lo,hi=locator['lines_1based'];frame=frames[locator['frame']]
        text='\n'.join(frame['code'].splitlines()[lo-1:hi])
        if locator['required_text'] not in text:raise ValueError('Historical locator mismatch')
        row['risk_locators'].append({**locator,'text':text,'body_sha256':frame['body_sha256'],
                                     'status':'UNKNOWN','method':'literal_source_locator_only'})
    for prior in spec.get('prior_diagnoses',[]):
        checked_hash=baseline['protected_files_sha256'][prior]
        if r01.digest((REPRO/prior).read_bytes())!=checked_hash:raise RuntimeError('Historical diagnosis modified')
        row['prior_diagnoses_preserved'].append({'path':prior,'sha256':checked_hash,'recomputed_by_R03':False})
    row['elapsed_seconds']=time.perf_counter()-start
    save(output/'sample_result.json',row)
    return row


def verify_frozen():
    manifest=json.loads((ROOT/'candidate_manifest.json').read_text('utf-8'))
    for n,h in manifest['frozen_files_sha256'].items():
        if not (REPRO/n).is_file() or r01.digest((REPRO/n).read_bytes())!=h:
            raise RuntimeError('Frozen candidate changed: '+n)
    for n,h in manifest['environment']['relevant_dependency_files_sha256'].items():
        if r01.digest(__import__('pathlib').Path(n).read_bytes())!=h:
            raise RuntimeError('Frozen dependency changed: '+n)
    return manifest


def main(mode):
    offline_boundary.install();start=time.perf_counter()
    output=ROOT/('historical' if mode=='historical' else 'fixed_20')
    output.mkdir(exist_ok=False)
    save(output/'run_start.json',{'created_at':datetime.now(timezone.utc).isoformat(),'mode':mode,
         'candidate_attempt':1,'is_blind':False,
         'candidate_manifest_sha256':r01.digest((ROOT/'candidate_manifest.json').read_bytes()) if mode=='fixed20' else None})
    rows=[];specs=[]
    try:
        baseline=verify_baseline()
        if mode=='historical':
            specs=json.loads((ROOT/'historical_cases.json').read_text('utf-8'))['cases']
        else:
            verify_frozen();specs=fixed_specs(baseline)
        save(output/'input_binding.json',{'ordered_sample_ids':[s['sample_id'] for s in specs]})
        for i,spec in enumerate(specs,1):rows.append(check_sample(spec,output/f'{i:02d}',baseline))
    except Exception as exc:
        save(output/'failure.json',{'execution_status':'FAILED_STOPPED','exception_type':type(exc).__name__,
             'exception':str(exc),'traceback':traceback.format_exc(),'ordinal_1based':len(rows)+1,
             'completed_rows':rows,'ordered_sample_ids':[s['sample_id'] for s in specs],
             'action':'STOP_NO_RETRY','diagnostic_status':None})
        raise
    metrics={'requested_samples':len(specs),'completed_samples':len(rows),'runtime_errors':0,
         'status_counts':counts(r['status'] for r in rows),'frame_count':sum(len(r['frames']) for r in rows),
         'frame_status_counts':counts(f['status'] for r in rows for f in r['frames']),
         'edge_count':sum(len(r['edges']) for r in rows),
         'context_state_counts':dict(Counter(r['context_state'] for r in rows)),
         'verified_call_contexts':0,'verified_return_bindings':0,'verified_caller_result_versions':0,
         'elapsed_seconds':time.perf_counter()-start,'LLM_calls':0,'Harness_calls':0,'Z3_calls':0,
         'SMT_generated':0,'tokens':0,'API_cost_CNY':0,'generated_code_execution':0,
         'C_runtime_execution':0,'external_operations':offline_boundary.EVENTS}
    result={'mode':mode,'rows':rows,'metrics':metrics,'complete_new_run':True,'old_results_reused':0,
            'is_blind':False,'safety_decisions_produced':False}
    save(output/'results.json',result)
    save(ROOT/('historical_results.json' if mode=='historical' else 'fixed_20_results.json'),result)
    print(json.dumps(metrics))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['historical','fixed20']);main(p.parse_args().mode)
