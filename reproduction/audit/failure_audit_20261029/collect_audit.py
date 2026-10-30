"""Collect frozen evidence and perform independent, offline checks only.

Does not instantiate CompletedEngine/DeepSeekModel or rewrite experiment outputs.
"""
from pathlib import Path
from collections import Counter, defaultdict
import ast
import csv
import hashlib
import json
import re
import shutil
import subprocess
import sys
import statistics
import z3

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from completion.context import ContextRepository, calls, compact, definitions, called_function, parameter_name

SELECT = [
    ('A01','NPD/codeql/kernel69',10,'真实缺陷误删；检查条件极性'),
    ('A02','NPD/codeql/kernel69',11,'另一条真实缺陷误删；检查标签/Source 与多次赋值'),
    ('A03','NPD/codeql/libav',3,'误报保留；switch 分支与枚举关系'),
    ('A04','NPD/codeql/kernel69',12,'误报保留；跨函数映射与类型/符号合并'),
    ('A05','NPD/codeql/kernel69',55,'上下文阻塞；复合实参'),
    ('A06','NPD/infer/openssl',4,'格式解析失败'),
    ('A07','NPD/codeql/openssl',41,'输出截断'),
    ('A08','NPD/codeql/libav',13,'误报保留；正确参数名映射但循环条件丢失'),
    ('A09','NPD/codeql/kernel69',34,'真实缺陷保留对照'),
    ('A10','NPD/codeql/kernel69',65,'误报过滤对照'),
]

def load(p):
    return json.loads((ROOT/p).read_text(encoding='utf-8'))

def save(p,value):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def parse_response(text):
    # Exact code/array extraction behavior from completion/engine.py, copied
    # solely to describe what already happened; not applied to any predictions.
    code_match = re.search(r'```(?:python)?\s*\n?(.*?)```',text,re.S)
    code = (code_match[1] if code_match else text).replace('from z3 import *','').strip()
    array_match = re.search(r'```(?:json)?\s*(.*?)```',text,re.S)
    try:
        array=json.loads(array_match[1] if array_match else text)
        if not isinstance(array,list) or any(not isinstance(x,str) for x in array):
            raise ValueError('Expected JSON array of condition strings')
        parsed={'ok':True,'value':array}
    except Exception as e:
        parsed={'ok':False,'error':type(e).__name__+': '+str(e)}
    return {'code_text_using_original_adapter':code,'array_using_original_adapter':parsed}

def mapping(chain):
    records=[]
    for before,after in zip(chain,chain[1:]):
        body=after['code']; fs=definitions(body)
        candidates=[c for c in calls(before['target']) if fs and c['name']==fs[0].name]
        result={'caller':before['function'],'callee':after['function'],'statement':before['target'],
                'caller_tracked_variable':before['var_name'],'recorded_callee_tracked_variable':after['var_name'],
                'callee_parameters':fs[0].parameters if fs else [],'call_candidates':candidates,
                'audit_note':'Lexical positional check; not a new experiment and not proof of alias/value propagation'}
        try:
            result['recomputed_tracked_parameter']=parameter_name(before['var_name'],before['target'],body)
            result['parameter_name_matches_saved_frame']=result['recomputed_tracked_parameter']==after['var_name']
        except Exception as e:
            result['mapping_error']=type(e).__name__+': '+str(e)
        if len(candidates)==1 and fs:
            result['all_positional_pairs']=[{'position_zero_based':i,'argument':arg,
                'parameter':fs[0].parameters[i] if i<len(fs[0].parameters) else None}
                for i,arg in enumerate(candidates[0]['arguments'])]
        records.append(result)
    return records

def main():
    collected=(HERE/'audit_samples.json').exists()
    rows=load('results/processed/expanded_all_npd.json')
    bundle=load('results/metrics/expanded_metrics.json')
    frozen=load(HERE.relative_to(ROOT)/'frozen_state.json')
    calls_by_id={}
    by_sample=defaultdict(list)
    for p in sorted((ROOT/'results/raw/completed/calls').glob('*.json')):
        c=json.loads(p.read_text(encoding='utf-8')); calls_by_id[c['call_id']]=c; by_sample[c['sample_id']].append(c)
    selected=load(HERE.relative_to(ROOT)/'audit_samples.json') if collected else []
    for aid,prefix,position,reason in ([] if collected else SELECT):
        row=next(r for r in rows if r['sample_id'].startswith(prefix+':') and r['row_position']==position)
        original=load('upstream/'+row['dataset'])[position]
        destination=HERE/'samples'/aid
        destination.mkdir(parents=True,exist_ok=False)
        save(destination/'original_alert.json',original)
        save(destination/'recorded_result.json',row)
        shutil.copytree(ROOT/row['raw_output'],destination/'recorded_raw')
        cs=by_sample[row['sample_id']]
        final_calls=cs[-row['api_calls']:] if row['api_calls'] else []
        historical_calls=cs[:-row['api_calls']] if row['api_calls'] else cs
        parsed=[]
        for c in final_calls:
            save(destination/'calls'/f"{c['call_id']:04d}.json",c)
            choices=c.get('choices') or []
            text=choices[0].get('message',{}).get('content','') if choices else ''
            result=parse_response(text or '')
            result.update({'call_id':c['call_id'],'finish_reason':choices[0].get('finish_reason') if choices else None,
                           'raw_response':text,'last_prompt':(c.get('messages') or [{}])[-1].get('content','')})
            if (text or '').lstrip().startswith('```json') or 'Performing reachability analysis' in result['last_prompt']:
                result['expected_output']='JSON array of strings'
            else:result['expected_output']='Z3 Python code or analysis (see exact prompt)'
            parsed.append(result)
        save(destination/'parsed_model_outputs.json',parsed)
        context_path=destination/'recorded_raw/context.json'
        context=json.loads(context_path.read_text(encoding='utf-8')) if context_path.exists() else None
        if context:
            for frame in context['frames']:
                (destination/f"frame_{frame['level']:02d}_{frame['function']}.c").write_text(frame['code'],encoding='utf-8')
                save(destination/f"frame_{frame['level']:02d}_conditions.json",frame.get('extracted',{}))
            mappings=mapping(context['frames'])
        else:
            # No saved frame was used by the LLM. Reconstruct only diagnostic
            # candidates, explicitly distinguishing them from actual execution.
            manifest=load('configs/'+row['phase']+'_manifest.json')
            repo=ContextRepository(row['dataset'],manifest['historical_path'],prefix)
            sink=original['location']['context']['snippet']['text']
            historical=[x for x in repo.historical if x['prt']==original['var_name'] and x['sink'].strip()==sink.strip()
                        and compact(x['function_call'][0])==compact(original.get('function_code',original.get('func_info','')))]
            save(destination/'historical_candidates_not_executed.json',historical)
            try:diagnostic=repo.prepare(position); replay={'prepared':True,'context':diagnostic}
            except Exception as e:replay={'prepared':False,'error':type(e).__name__+': '+str(e)}
            save(destination/'offline_context_diagnostic.json',replay)
            mappings=[]
            for h in historical:
                for level,body in enumerate(h['function_call']):
                    (destination/f'candidate_NOT_EXECUTED_{level:02d}.c').write_text(body,encoding='utf-8')
                    for call in calls(body):
                        if any('sta' in a for a in call['arguments']) and ('sta' in call['text']):
                            mappings.append({'function_level':level,'diagnostic_only':True,'call':call})
        save(destination/'argument_parameter_mapping.json',mappings)
        solvers=[]
        for p in sorted((destination/'recorded_raw').glob('solver_*.json')):
            e=json.loads(p.read_text(encoding='utf-8'))
            (destination/(p.stem+'.py')).write_text(e['source'],encoding='utf-8')
            for qi,q in enumerate(e.get('queries',[]),1):
                (destination/f'{p.stem}_query_{qi:02d}.smt2').write_text(q['smt2'],encoding='utf-8')
            solvers.append({'file':p.name,'level':e['level'],'ok':e.get('ok'),'error':e.get('error'),
                            'feasible':e.get('feasible'),'query_results':[q['result'] for q in e.get('queries',[])]})
        info={'audit_id':aid,'sample_id':row['sample_id'],'selection_reason':reason,'selection':'purposive diagnostic; not random and not representative',
              'label':row['label'],'prediction':row['prediction'],'status':row['status'],'error':row['error'],
              'source_status':'No explicit source location/complete SARIF codeFlow in published row; raw function_list/assignment hints preserved, not invented',
              'sink':original['location'],'saved_context_exists':bool(context),
              'function_chain':[f['function'] for f in context['frames']] if context else [],
              'final_attempt_call_ids':[c['call_id'] for c in final_calls],
              'earlier_attempt_call_ids_not_reused':[c['call_id'] for c in historical_calls],
              'solver_evidence':solvers,'argument_parameter_mapping':mappings,
              'duration_seconds':row['duration_seconds'],'cost_upper_bound_cny':row['cost_upper_bound_cny'],
              'missing_steps':[] if row['status']=='success' else ['See recorded error; unexecuted steps have no LLM/SMT output and are not fabricated']}
        save(destination/'evidence_index.json',info)
        selected.append(info)
    save(HERE/'audit_samples.json',selected)

    # Independent arithmetic: do not call completion.metrics.evaluate.
    cell=Counter((r['label'],r['prediction'] if r['status']=='success' else None) for r in rows)
    a,b,c,d=cell[0,'filter'],cell[0,'keep'],cell[1,'filter'],cell[1,'keep']
    nf=sum(r['label']==0 for r in rows); nb=sum(r['label']==1 for r in rows)
    precision=a/(a+c); recall=a/nf
    metrics={'sample_count':len(rows),'successful':a+b+c+d,'failed':sum(r['status']=='failed' for r in rows),
             'blocked':sum(r['status'].startswith('blocked') for r in rows),'false_alarm_count':nf,'real_bug_count':nb,
             'counts':{'false_alarm_filtered':a,'false_alarm_kept':b,'real_bug_filtered':c,'real_bug_kept':d},
             'unclassified':{'false_alarm':cell[0,None],'real_bug':cell[1,None]},
             'false_positive_filter_rate':a/nf,'real_bug_retention_rate':d/nb,'real_bug_deletion_rate':c/nb,
             'precision':precision,'recall':recall,'f1':2*precision*recall/(precision+recall),
             'success_rate':(a+b+c+d)/len(rows),
             'mean_wall_seconds_all_selected':statistics.mean(r['duration_seconds'] for r in rows),
             'classified_only_secondary':{'false_alarm_filter_rate':a/(a+b),'real_bug_retention_rate':d/(c+d)},
             'failure_recovery_ceiling_without_changing_completed_predictions':(a+cell[0,None])/nf}
    checked={k:bundle['overall'][k]==metrics[k] for k in ['sample_count','successful','failed','blocked','false_alarm_count','real_bug_count','counts','false_positive_filter_rate','real_bug_retention_rate','real_bug_deletion_rate','precision','recall','f1','success_rate','mean_wall_seconds_all_selected']}
    assert all(checked.values())
    with (ROOT/'results/processed/expanded_all_npd.csv').open(encoding='utf-8-sig',newline='') as f:csv_rows=list(csv.DictReader(f))
    assert len(csv_rows)==len(rows) and {r['sample_id'] for r in csv_rows}=={r['sample_id'] for r in rows}
    assert all(next(x for x in csv_rows if x['sample_id']==r['sample_id'])['prediction']==(r['prediction'] or '') for r in rows)
    save(HERE/'independent_metrics_check.json',{'metrics':metrics,'matches_existing':checked,'CSV_matches':True,
         'positive_class':'false_alarm_to_filter','abstention_policy':'Unknown FP included in recall denominator, unknown bugs not silently counted as kept; F1 is coverage-penalized, not conventional classified-only F1'})

    data=[]
    unique_files={}; types=Counter()
    for p in sorted((ROOT/'upstream/benchmark').rglob('*.json')):
        raw=json.loads(p.read_text(encoding='utf-8')); digest=sha(p)
        labels=Counter(str(x.get('result')) for x in raw)
        item={'path':p.relative_to(ROOT).as_posix(),'sha256':digest,'rows':len(raw),'label_distribution':dict(labels),
              'valid_rows':sum(type(x.get('result')) is int and x['result'] in (0,1) for x in raw),
              'explicit_source_key_rows':sum(any(k.lower() in {'source','source_location','sources','codeflows'} for k in x) for x in raw),
              'duplicate_of':unique_files.get(digest)}
        data.append(item)
        if digest not in unique_files:
            unique_files[digest]=item['path']; types[p.relative_to(ROOT/'upstream/benchmark').parts[0]]+=len(raw)
    save(HERE/'data_version_check.json',{'files':data,'all_raw_rows':sum(x['rows'] for x in data),
         'unique_file_rows':sum(x['rows'] for x in data if not x['duplicate_of']), 'unique_rows_by_type':dict(types),
         'label_mapping':'result=0 false alarm; result=1 real bug; corroborated with author aggregate metrics, no per-sample independent ground truth proof',
         'label_audit_from_expansion':load('results/processed/expanded_label_audit.json'),
         'data_manifest_hashes_match':all(sha(ROOT/'upstream'/load('configs/expanded_'+g+'_manifest.json')['dataset'])==load('configs/expanded_'+g+'_manifest.json')['dataset_sha256'] for g in ['codeql_linux','codeql_libav','codeql_openssl','cppcheck_linux','cppcheck_libav','cppcheck_openssl','infer_libav','infer_openssl'])})

    patterns=Counter(); assignments=[]; solver_replay=[]; multi=[]; terminal=Counter(); successful_contexts=0
    for r in rows:
        raw=ROOT/r['raw_output']; cp=raw/'context.json'
        if not cp.exists():continue
        ctx=json.loads(cp.read_text(encoding='utf-8'))
        if r['status']=='success':
            successful_contexts+=1; terminal[ctx['frames'][-1].get('sink_kind')]+=1
        if len(ctx['frames'])>1:
            multi.append({'sample_id':r['sample_id'],'label':r['label'],'status':r['status'],'prediction':r['prediction'],'frames':len(ctx['frames'])})
        for f in ctx['frames']:
            ext=f.get('extracted',{})
            assignments.append({'sample_id':r['sample_id'],'frame':f['level'],'variable_assignment_text':ext.get('variable_assignments',{}).get('text'),
                                'first_code_line':f['code'].splitlines()[0] if f['code'] else '',
                                'is_first_code_line':ext.get('variable_assignments',{}).get('text')==(f['code'].splitlines()[0] if f['code'] else '')})
        for p in sorted(raw.glob('solver_*.json')):
            e=json.loads(p.read_text(encoding='utf-8'))
            if not e.get('ok'):continue
            for i,q in enumerate(e.get('queries',[])):
                entry={'sample_id':r['sample_id'],'file':p.relative_to(ROOT).as_posix(),'query':i+1,'saved':q['result']}
                try:
                    solver=z3.Solver();solver.set(timeout=5000);solver.from_string(q['smt2']);new=str(solver.check())
                    entry.update({'offline_replay':new,'assertions':len(solver.assertions()),'matches':new==q['result']})
                except Exception as exc:
                    entry.update({'offline_replay':None,'matches':None,'replay_error':type(exc).__name__+': '+str(exc),
                                  'note':'SMT2 serialization/reload limitation; original in-memory solver result retained. No formula rewriting.'})
                solver_replay.append(entry)
        good=[json.loads(p.read_text(encoding='utf-8')) for p in sorted(raw.glob('solver_*.json'))]
        good=[e for e in good if e.get('ok')]
        if r['status']=='success' and good:
            last=good[-1]
            assert last['feasible']==(r['prediction']=='keep')
            solver=z3.Solver()
            try:solver.from_string(last['queries'][-1]['smt2'])
            except z3.Z3Exception:continue
            if len(solver.assertions())==1 and str(solver.assertions()[0])==ctx['frames'][last['level']]['var_name']+' == 0':
                patterns['base_null_only_last_query']+=1
                if r['label']==0:patterns['false_alarm_base_null_only_last_query']+=1
    errors=Counter()
    for r in rows:
        if r['status']!='failed':continue
        e=r['error']
        category='other'
        if 'JSONDecodeError' in e:category='json_parse'
        elif 'finish_reason=length' in e:category='truncation'
        elif 'Unsupported generated-code operation' in e:category='worker_rejected_operation'
        elif 'Z3 sort expected' in e:category='z3_sort'
        elif 'Returned boolean disagrees' in e:category='boolean_disagrees'
        elif 'unsupported operand type(s) for &' in e:category='integer_bitwise'
        elif 'ReadTimeout' in e:category='network_timeout'
        errors[category]+=1
    save(HERE/'population_diagnostics.json',{'final_attempts':len(rows),'blocked_errors':dict(Counter(r['error'] for r in rows if r['status'].startswith('blocked'))),
        'execution_failure_types':dict(errors),'patterns':dict(patterns),'multi_frame_records':multi,'multi_frame_count':len(multi),
        'successful_terminal_sink_kinds':dict(terminal),'assignment_extractor_diagnostics':assignments,
        'assignment_text_equals_first_line_count':sum(x['is_first_code_line'] for x in assignments),
        'saved_frames':len(assignments),'solver_query_replays':solver_replay,
        'replay_comparable_all_match':all(x['matches'] for x in solver_replay if x['matches'] is not None),
        'replay_reload_failures':sum(x['matches'] is None for x in solver_replay)})
    save(HERE/'checkpoint_02_data_metrics.json',{'complete':True,'data_files':len(data),'selected':len(rows),'all_metric_checks_passed':all(checked.values()),
                                              'model_calls_added':0,'selected_audit_samples':len(selected)})
    print(json.dumps({'samples':[(x['audit_id'],x['sample_id']) for x in selected],'independent_metric_checks':checked,
         'patterns':dict(patterns),'failed':dict(errors),'solver_queries_replayed':len(solver_replay),
         'all_reloadable_solver_queries_match':all(x['matches'] for x in solver_replay if x['matches'] is not None),
         'reload_failures':sum(x['matches'] is None for x in solver_replay),'saved_frames':len(assignments),
         'assignment_equals_first_line':sum(x['is_first_code_line'] for x in assignments),'terminal_sinks':dict(terminal)},ensure_ascii=True,indent=2))

if __name__=='__main__':main()
