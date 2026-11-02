"""Read-only saved-source checks. Never imports model, Engine, solver or safety."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import time
import traceback

from r01_adapter import ROOT, REPRO, offline_boundary, r01, rf_inputs
from value_version import analyze

RF = rf_inputs()


def save(path, obj):
    with path.open('x', encoding='utf-8', newline='\n') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write('\n')


def checked(rel, baseline):
    path = REPRO/rel
    if r01.digest(path.read_bytes()) != baseline['protected_files_sha256'][rel]:
        raise RuntimeError('Protected evidence changed: '+rel)
    return json.loads(path.read_text('utf-8'))


def verify_baseline():
    baseline = json.loads((ROOT/'baseline_state.json').read_text('utf-8'))
    bad = [n for n,h in baseline['protected_files_sha256'].items()
           if not (REPRO/n).is_file() or r01.digest((REPRO/n).read_bytes()) != h]
    if bad:
        raise RuntimeError('Protected evidence changed: '+repr(bad))
    if r01.digest((REPRO/RF.FIXED).read_bytes()) != RF.FIXED_HASH:
        raise RuntimeError('Fixed manifest changed')
    if r01.digest((REPRO/RF.AUDIT).read_bytes()) != RF.AUDIT_HASH:
        raise RuntimeError('Audit manifest changed')
    return baseline


def verify_frozen():
    freeze = json.loads((ROOT/'candidate_manifest.json').read_text('utf-8'))
    for rel, h in freeze['frozen_files_sha256'].items():
        if r01.digest((REPRO/rel).read_bytes()) != h:
            raise RuntimeError('Frozen file changed: '+rel)
    return freeze


def fixed_specs(baseline):
    fixed = checked(RF.FIXED, baseline)
    inventory = checked(RF.INVENTORY, baseline)
    if len(fixed['samples']) != 20 or len(inventory['rows']) != 20:
        raise ValueError('Fixed manifest must contain original 20 samples')
    specs=[]
    for sample, entry in zip(fixed['samples'], inventory['rows']):
        for a,b in [('sample_id','sample_id'),('row_position','row_position'),('dataset','dataset')]:
            if sample[a] != entry[b]:
                raise ValueError('Fixed input order/binding mismatch')
        actual = r01.digest((REPRO/'upstream'/sample['dataset']).read_bytes())
        if actual != sample['dataset_sha256']:
            raise ValueError('Dataset bytes changed')
        tool, project = sample['sample_id'].split('/')[1:3]
        project = project.split(':')[0]
        specs.append({'sample_id':sample['sample_id'],
                      'dataset_id':tool+'_'+('linux' if project=='kernel69' else project),
                      'position':sample['row_position'], 'dataset':sample['dataset'],
                      'bundle':entry['bundle']})
    return specs


def frame_check(frame, spec, ordinal, source_ref, output):
    code=frame['code'].encode('utf-8')
    if r01.digest(code) != frame['body_sha256']:
        raise ValueError('Frame body hash mismatch')
    source=output/f'frame_{ordinal}.c'
    source.write_bytes(code)
    report=analyze(source,dataset_id=spec['dataset_id'],position=spec['position'],
                   build_status='saved-source-only',function=frame['function'])
    # Historical recovery AST must never become verified local value evidence.
    if report['status']!='UNKNOWN' or report['expression_evidence'] or any(f['versions'] or f['reads'] for f in report['functions']):
        raise RuntimeError('Historical build gate bypassed')
    save(output/f'frame_{ordinal}_trace.json',report)
    return {'frame':ordinal,'function':frame['function'],'body_sha256':frame['body_sha256'],
            'source_ref':source_ref,'source_copy':source.name,
            'trace_file':f'frame_{ordinal}_trace.json','status':report['status'],
            'reasons':report['reasons'],
            'function_reasons':[{'function':f['function']['name'],'reasons':f['reasons']} for f in report['functions']],
            'diagnostic_count':len(report['diagnostics']),'verified_versions':0,'verified_reads':0}


def check_sample(spec, output, baseline):
    started=time.perf_counter()
    output.mkdir(parents=True,exist_ok=False)
    if 'bundle' in spec:
        bundle=checked(spec['bundle'],baseline)
        if bundle['candidate']['sample_id'] != spec['sample_id']:
            raise ValueError('Sample identity mismatch')
        provenance=RF.null_context_provenance(spec,bundle,baseline) if bundle.get('context',False) is None else None
        state,frames=RF.context_state(bundle,provenance)
        input_ref=spec['bundle']; input_hash=r01.digest((REPRO/input_ref).read_bytes())
        historical_error=bundle['candidate'].get('error') if frames is None else None
    else:
        manifest=checked(spec['manifest'],baseline)
        for key in ['sample_id','dataset_id','position','dataset']:
            if manifest[key] != spec[key]:raise ValueError('Historical manifest identity mismatch')
        frames=manifest['frames'];RF.context_state({'context':{'frames':frames}})
        state='FRAMES_PRESENT';provenance=None;historical_error=None
        input_ref=spec['manifest'];input_hash=r01.digest((REPRO/input_ref).read_bytes())
        if (REPRO/spec['source']).read_bytes()!=frames[0]['code'].encode('utf-8'):
            raise ValueError('Historical source/manifest binding mismatch')
    dataset_rel='upstream/'+spec['dataset']
    dataset_hash=r01.digest((REPRO/dataset_rel).read_bytes())
    if dataset_hash!=baseline['protected_files_sha256'][dataset_rel]:
        raise ValueError('Protected dataset changed')
    row={'sample_id':spec['sample_id'],'dataset_id':spec['dataset_id'],'position':spec['position'],
         'dataset':spec['dataset'],'dataset_sha256':dataset_hash,
         'input_ref':input_ref,'input_sha256':input_hash,'context_state':state,
         'null_context_provenance':provenance,'historical_context_error':historical_error,
         'status':'UNKNOWN','execution_status':'COMPLETED','frames':[],
         'reasons':['missing_original_build_evidence'],'labels_used':False,
         'prior_R01_results_reused':False,'prior_solver_results_used':False,
         'whole_function_value_coverage':0.0,'cross_function_state_propagated':False}
    if frames is None:row['reasons'].append('historical_saved_context_unavailable')
    elif not frames:row['reasons'].append('missing_saved_frames')
    else:
        for i,frame in enumerate(frames):
            pointer='/context/frames/' if 'bundle' in spec else '/frames/'
            row['frames'].append(frame_check(frame,spec,i,input_ref+'#'+pointer+str(i),output))
    row['cached_diagnoses']=[]
    for ref in spec.get('prior_diagnoses',[]):
        path=REPRO/ref
        if r01.digest(path.read_bytes())!=baseline['protected_files_sha256'][ref]:
            raise RuntimeError('Prior diagnosis changed')
        row['cached_diagnoses'].append({'path':ref,'sha256':r01.digest(path.read_bytes()),
                                       'recomputed_by_R02':False})
    row['risk_locators']=[]
    for locator in spec.get('locators',[]):
        frame=frames[locator['frame']]
        lines=frame['code'].splitlines()
        lo,hi=locator['lines_1based']
        text='\n'.join(lines[lo-1:hi])
        if locator['required_text'] not in text:
            raise ValueError('Historical source risk locator mismatch')
        row['risk_locators'].append({**locator,'text':text,'body_sha256':frame['body_sha256'],
                                    'method':'literal_source_locator_only',
                                    'reaching_definition_status':'UNKNOWN'})
    row['elapsed_seconds']=time.perf_counter()-started
    save(output/'sample_result.json',row)
    return row


def main(mode):
    offline_boundary.install()
    began=time.perf_counter();baseline=verify_baseline()
    if mode=='historical':
        specs=json.loads((ROOT/'historical_cases.json').read_text('utf-8'))['cases']
        output=ROOT/'historical'
    else:
        freeze=verify_frozen();specs=fixed_specs(baseline);output=ROOT/'fixed_20'
    output.mkdir(exist_ok=False) # one-shot marker, including failed attempts
    save(output/'run_start.json',{'created_at':datetime.now(timezone.utc).isoformat(),
                                 'mode':mode,'candidate_attempt':1,'is_blind':False,
                                 'freeze_sha256':r01.digest((ROOT/'candidate_manifest.json').read_bytes()) if mode=='fixed20' else None,
                                 'ordered_sample_ids':[s['sample_id'] for s in specs],
                                 'old_results_reused':0})
    rows=[]
    for i,spec in enumerate(specs,1):
        try:
            rows.append(check_sample(spec,output/f'{i:02d}',baseline))
        except Exception as exc:
            save(output/'failure.json',{'execution_status':'FAILED_STOPPED','ordinal_1based':i,
                                        'sample_id':spec.get('sample_id'),'completed_rows':rows,
                                        'exception_type':type(exc).__name__,'exception':str(exc),
                                        'traceback':traceback.format_exc(),'diagnostic_status':None,
                                        'action':'STOP_NO_RETRY','error_relabeling':False})
            raise
    counts={s:sum(r['status']==s for r in rows) for s in ['PASS','REJECT','UNKNOWN','NOT_APPLICABLE']}
    stats={'requested_samples':len(specs),'completed_samples':len(rows),'runtime_errors':0,
           'status_counts':counts,'frame_count':sum(len(r['frames']) for r in rows),
           'frame_status_counts':dict(Counter(f['status'] for r in rows for f in r['frames'])),
           'context_state_counts':dict(Counter(r['context_state'] for r in rows)),
           'reason_counts':dict(Counter(x for r in rows for x in r['reasons'])),
           'verified_versions':0,'verified_reads':0,'PASS_over_all_requested_samples':counts['PASS']/len(specs),
           'elapsed_seconds':time.perf_counter()-began,'LLM_calls':0,'tokens':0,'API_cost_CNY':0,
           'Z3_calls':0,'SMT_generated':0,'generated_code_executions':0,'C_runtime_executions':0,
           'external_operations':offline_boundary.EVENTS}
    result={'mode':mode,'rows':rows,'metrics':stats,'complete_new_run':True,'is_blind':False,
            'old_results_reused':0,'safety_decisions_produced':False}
    save(output/'results.json',result)
    save(ROOT/('historical_results.json' if mode=='historical' else 'fixed_20_results.json'),result)
    print(json.dumps(stats))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['historical','fixed20'])
    main(p.parse_args().mode)
