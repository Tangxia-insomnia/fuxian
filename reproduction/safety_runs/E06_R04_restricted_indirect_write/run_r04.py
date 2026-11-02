"""Fresh R04 saved-source checks. Never reuse prior-stage semantic results."""
import argparse
from datetime import datetime,timezone
import json
import time
import traceback
from collections import Counter
from pathlib import Path
from r03_adapter import ROOT,REPRO,r01,counts,offline_boundary
from indirect_write import analyze
from run_r03 import RF,fixed_specs
import source_locator as lexical


def save(path,obj):
    with path.open('x',encoding='utf-8',newline='\n') as f:json.dump(obj,f,indent=2,ensure_ascii=False);f.write('\n')


def checked(rel,baseline):
    p=REPRO/rel
    if r01.digest(p.read_bytes())!=baseline['protected_files_sha256'][rel]:raise RuntimeError('Protected input changed: '+rel)
    return json.loads(p.read_text('utf-8'))


def verify_baseline():
    b=json.loads((ROOT/'baseline_state.json').read_text('utf-8'))
    bad=[n for n,h in b['protected_files_sha256'].items() if not (REPRO/n).is_file() or r01.digest((REPRO/n).read_bytes())!=h]
    if bad:raise RuntimeError('Original file changed: '+repr(bad))
    for n,h in [(RF.FIXED,RF.FIXED_HASH),(RF.AUDIT,RF.AUDIT_HASH)]:
        if r01.digest((REPRO/n).read_bytes())!=h:raise RuntimeError('Fixed input changed')
    return b


def address_candidates(code):
    ts=lexical.tokens(code);out=[]
    for i,t in enumerate(ts):
        if t.group()!='&' or (i>0 and ts[i-1].group()=='&') or (i+1<len(ts) and ts[i+1].group()=='&'):continue
        end=code.find('\n',t.start());end=len(code) if end<0 else end
        out.append({'source_location':lexical.location(code,t.start(),end),'expression_tail':code[t.start():end],
            'status':'UNKNOWN','method':'ampersand_source_locator_not_address_or_type_proof',
            'memory_object_id':None,'pointer_target_id':None,'caller_post_version':None,
            'reason':'original_build_declaration_and_effect_evidence_not_verified'})
    return out


def check_sample(spec,output,baseline):
    start=time.perf_counter();output.mkdir(parents=True,exist_ok=False)
    if 'bundle' in spec:
        b=checked(spec['bundle'],baseline)
        if b['candidate']['sample_id']!=spec['sample_id']:raise ValueError('Sample identity mismatch')
        provenance=RF.null_context_provenance(spec,b,baseline) if b.get('context',False) is None else None
        state,frames=RF.context_state(b,provenance);ref=spec['bundle']
        old_error=b['candidate'].get('error') if frames is None else None
    else:
        b=checked(spec['manifest'],baseline)
        for k in ['sample_id','dataset_id','position','dataset']:
            if b[k]!=spec[k]:raise ValueError('Historical manifest mismatch')
        state,frames=RF.context_state({'context':{'frames':b['frames']}})
        if (REPRO/spec['source']).read_bytes()!=frames[0]['code'].encode():raise ValueError('Historical source mismatch')
        provenance=None;ref=spec['manifest'];old_error=None
    dataset_rel='upstream/'+spec['dataset'];dataset_sha=r01.digest((REPRO/dataset_rel).read_bytes())
    if dataset_sha!=baseline['protected_files_sha256'][dataset_rel]:raise ValueError('Dataset bytes changed')
    row={'sample_id':spec['sample_id'],'dataset_id':spec['dataset_id'],'position':spec['position'],
        'input_ref':ref,'input_sha256':r01.digest((REPRO/ref).read_bytes()),'dataset':spec['dataset'],'dataset_sha256':dataset_sha,
        'status':'UNKNOWN','execution_status':'COMPLETED','context_state':state,'null_context_provenance':provenance,
        'historical_context_error':old_error,'reasons':['missing_original_build_evidence'],
        'frames':[],'edges':[],'risk_locators':[],'prior_diagnoses_preserved':[],
        'verified_objects':0,'verified_pointer_targets':0,'verified_indirect_writes':0,'verified_caller_new_versions':0,
        'old_semantic_results_reused':False,'labels_used':False,'safety_decisions_produced':False}
    if frames is None:row['reasons'].append('historical_saved_context_unavailable')
    elif not frames:row['reasons'].append('missing_saved_frames')
    for i,frame in enumerate(frames or []):
        blob=frame['code'].encode();assert r01.digest(blob)==frame['body_sha256']
        p=output/f'frame_{i}.c';p.write_bytes(blob)
        report=analyze(p,dataset_id=spec['dataset_id'],position=spec['position'],build_status='saved-source-only',caller=frame['function'])
        if report['status']!='UNKNOWN' or report['memory_objects'] or report['effect_transfers'] or report['caller'] is not None:
            raise RuntimeError('Historical recovery approval attempted')
        save(output/f'frame_{i}_r04.json',report)
        row['frames'].append({'frame':i,'function':frame['function'],'body_sha256':frame['body_sha256'],
            'source_ref':ref+('#/context/frames/' if 'bundle' in spec else '#/frames/')+str(i),
            'source_copy':p.name,'report_file':f'frame_{i}_r04.json','status':'UNKNOWN','reasons':report['reasons'],
            'diagnostic_count':len(report['diagnostics']),'address_source_candidates':address_candidates(frame['code']),
            'return_source_candidates':lexical.returns(frame['code']),'verified_indirect_writes':0})
    for i,(caller,callee) in enumerate(zip(frames or [],(frames or [])[1:])):
        row['edges'].append({'caller_frame':i,'callee_frame':i+1,'caller':caller['function'],'callee':callee['function'],
            'status':'UNKNOWN','callsite_candidates':lexical.calls_to(caller['code'],callee['function']),
            'pointer_target_proved':False,'caller_state_updated':False,'R05_composition_performed':False})
    for loc in spec.get('locators',[]):
        lo,hi=loc['lines_1based'];frame=frames[loc['frame']];text='\n'.join(frame['code'].splitlines()[lo-1:hi])
        if loc['required_text'] not in text:raise ValueError('Historical source locator mismatch')
        row['risk_locators'].append({**loc,'text':text,'body_sha256':frame['body_sha256'],'status':'UNKNOWN','type_or_effect_proof':False})
    for rel in spec.get('prior_diagnoses',[]):
        if r01.digest((REPRO/rel).read_bytes())!=baseline['protected_files_sha256'][rel]:raise RuntimeError('Prior diagnosis changed')
        row['prior_diagnoses_preserved'].append({'path':rel,'sha256':baseline['protected_files_sha256'][rel],
            'recomputed_or_promoted_by_R04':False})
    row['elapsed_seconds']=time.perf_counter()-start;save(output/'sample_result.json',row);return row


def verify_frozen():
    f=json.loads((ROOT/'candidate_manifest.json').read_text('utf-8'))
    for n,h in f['frozen_files_sha256'].items():
        if r01.digest((REPRO/n).read_bytes())!=h:raise RuntimeError('Frozen candidate changed: '+n)
    for n,h in f['environment']['relevant_dependency_files_sha256'].items():
        if r01.digest(Path(n).read_bytes())!=h:raise RuntimeError('Frozen dependency changed: '+n)
    return f


def main(mode):
    offline_boundary.install();start=time.perf_counter();out=ROOT/('historical' if mode=='historical' else 'fixed_20')
    out.mkdir(exist_ok=False);rows=[];specs=[]
    save(out/'run_start.json',{'created_at':datetime.now(timezone.utc).isoformat(),'mode':mode,'attempt':1,'is_blind':False,
        'candidate_manifest_sha256':r01.digest((ROOT/'candidate_manifest.json').read_bytes()) if (ROOT/'candidate_manifest.json').exists() else None})
    try:
        baseline=verify_baseline()
        if mode=='historical':specs=json.loads((ROOT/'historical_cases.json').read_text('utf-8'))['cases']
        else:verify_frozen();specs=fixed_specs(baseline)
        save(out/'input_binding.json',{'ordered_sample_ids':[s['sample_id'] for s in specs]})
        for i,spec in enumerate(specs,1):rows.append(check_sample(spec,out/f'{i:02d}',baseline))
    except Exception as exc:
        save(out/'failure.json',{'execution_status':'FAILED_STOPPED','type':type(exc).__name__,'exception':str(exc),
            'traceback':traceback.format_exc(),'completed_rows':rows,'ordinal_1based':len(rows)+1,
            'ordered_sample_ids':[s['sample_id'] for s in specs],'action':'STOP_NO_RETRY','diagnostic_status':None})
        raise
    metrics={'requested_samples':len(specs),'completed_samples':len(rows),'runtime_errors':0,
        'status_counts':counts(r['status'] for r in rows),'frame_count':sum(len(r['frames']) for r in rows),
        'frame_status_counts':counts(f['status'] for r in rows for f in r['frames']),
        'edge_count':sum(len(r['edges']) for r in rows),'context_state_counts':dict(Counter(r['context_state'] for r in rows)),
        'address_text_candidate_count':sum(len(f['address_source_candidates']) for r in rows for f in r['frames']),
        'verified_objects':0,'verified_pointer_entries':0,'verified_unique_targets':0,'verified_indirect_writes':0,'verified_caller_post_versions':0,
        'LLM_calls':0,'Harness_calls':0,'Z3_calls':0,'SMT_generated':0,'tokens':0,'API_cost_CNY':0,
        'historical_or_model_generated_script_executions':0,'C_program_execution':0,'external_operations':offline_boundary.EVENTS,
        'elapsed_seconds':time.perf_counter()-start}
    result={'mode':mode,'rows':rows,'metrics':metrics,'complete_new_run':True,'is_blind':False,'old_results_reused':0,'safety_decisions_produced':False}
    save(out/'results.json',result);save(ROOT/('historical_results.json' if mode=='historical' else 'fixed_20_results.json'),result)
    print(json.dumps(metrics))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['historical','fixed20']);main(p.parse_args().mode)
