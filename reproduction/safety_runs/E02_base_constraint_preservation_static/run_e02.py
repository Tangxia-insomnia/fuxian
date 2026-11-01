"""Evidence-only runner. All writes stay under this E02 directory.

Do not import any historical project modules, execute generated scripts, or solve.
The fixed regression command requires an already frozen checker and runs once.
"""
from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
import time

from checker import check_contract, code_block, Unsupported

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASELINE = HERE/'baseline_state.json'
FROZEN = ['checker.py', 'test_checker.py', 'run_e02.py', 'experiment_config.json']


def now():
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def save(path, value):
    path = HERE/path
    if HERE not in path.resolve().parents:
        raise RuntimeError('STOP: write outside E02')
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as out:
        out.write(json.dumps(value, ensure_ascii=False, indent=2)+'\n' if not isinstance(value, str) else value)


def verify_protected():
    baseline = read(BASELINE)
    for rel, expected in baseline['protected_sha256'].items():
        p = ROOT/rel
        if not p.is_file() or sha_file(p) != expected:
            raise RuntimeError('STOP: protected file changed: '+rel)
    for rel, expected in baseline['fixed_inputs'].items():
        if sha_file(ROOT/rel) != expected:
            raise RuntimeError('STOP: fixed input hash mismatch: '+rel)
    return {'checked_at':now(), 'protected_file_count':len(baseline['protected_sha256']),
            'changed_files':[], 'fixed_inputs_match':True}


def verify_freeze():
    frozen = read(HERE/'candidate_freeze.json')
    for rel, sha in frozen['candidate_sha256'].items():
        if sha_file(HERE/rel) != sha:
            raise RuntimeError('STOP: frozen candidate changed: '+rel)
    return frozen


def history_code(text):
    # Documented historical code_response strips imports of all z3 names.
    # The AST reader supports explicit imports, so no module is imported here.
    match = re.search(r'```(?:python)?\s*\n?(.*?)```', text, re.S)
    return (match[1] if match else text).replace('from z3 import *','').strip()


def segment(prompt, begin, end):
    if prompt.count(begin) != 1 or prompt.count(end) != 1:
        raise RuntimeError('STOP: historical prompt structure unconfirmed: '+begin)
    return prompt.split(begin,1)[1].split(end,1)[0].strip()


def role(prompt):
    if prompt.lstrip().startswith('Convert C code constraints into Z3 solver script.'):
        return 'U02'
    if prompt.lstrip().startswith('Task: Extend the existing Z3 constraint script'):
        return 'U06'
    if prompt.lstrip().startswith('As a Z3 constraint solver expert, optimize the following script'):
        return 'U10'
    if prompt.lstrip().startswith('As a Z3 constraint solver expert, merge the following constraint sets'):
        return 'U09'
    if prompt.lstrip().startswith('The Z3 script contains errors.'):
        return 'U01'
    if prompt.lstrip().startswith('As a C language expert, convert C code constraints'):
        return 'U07'
    return 'analysis_or_filter'


def canonical_content(text):
    return history_code(text).strip()


def collect_calls(sample_id, n_calls, expected_ids=None):
    ledger = read(ROOT/'results/raw/completed/budget_ledger.json')
    ids = [c['call_id'] for c in ledger['calls'] if c['sample_id'] == sample_id]
    chosen = ids[-n_calls:] if n_calls else []
    if expected_ids is not None and chosen != expected_ids:
        raise RuntimeError('STOP: final-attempt call identity mismatch')
    records = []
    for call_id in chosen:
        path = ROOT/'results/raw/completed/calls'/f'{call_id:04}.json'
        obj = read(path)
        if obj.get('sample_id') != sample_id or obj.get('call_id') != call_id:
            raise RuntimeError('STOP: historical call binding mismatch')
        records.append((path,obj))
    return records, {'selected_call_ids':chosen, 'earlier_ids_not_used':ids[:-n_calls] if n_calls else ids,
                     'selection':'frozen last-attempt count suffix; also checked against saved final-response/source evidence'}


def snapshot_sample(cohort, number, item, audit=False):
    """Load one fixed row from the frozen evidence/binding set; never classify it."""
    all_bindings = read(ROOT/'safety_runs/20261029_v1/offline_regression/evidence_bindings.json')
    position = number-1 if audit else number+9
    binding = all_bindings[position]
    sample_id = item['sample_id']
    if binding['sample_id'] != sample_id:
        raise RuntimeError('STOP: frozen evidence sample ordering mismatch')
    evidence_path = ROOT/'safety_runs/20261029_v1/offline_regression/evidence'/f'{position+1:02}.json'
    bundle = read(evidence_path)
    if bundle['candidate']['sample_id'] != sample_id or digest(bundle) != binding['evidence_sha256']:
        raise RuntimeError('STOP: frozen evidence binding cannot be verified')
    for rel, expected in binding['artifact_sha256'].items():
        if sha_file(ROOT/rel) != expected:
            raise RuntimeError('STOP: historical artifact mismatch: '+rel)
    sample_files = [ROOT/p for p in binding['artifact_sha256'] if p.endswith('/sample_result.json')]
    if len(sample_files) != 1:
        raise RuntimeError('STOP: final-attempt origin ambiguous')
    raw = sample_files[0].parent
    saved_result = read(sample_files[0])
    if saved_result['sample_id'] != sample_id:
        raise RuntimeError('STOP: raw sample identity mismatch')
    n_calls = saved_result.get('api_calls',0)
    records, selected = collect_calls(sample_id,n_calls,item['final_attempt_call_ids'] if audit else None)
    prefix = Path('evidence')/(cohort+'_frozen_candidate')/f'{number:02}'
    sources = []
    paths = [evidence_path, sample_files[0]] + [p for p in sorted(raw.glob('solver_*.json'))]
    if (raw/'author_pipeline_output.json').exists():
        paths.append(raw/'author_pipeline_output.json')
    for path in paths:
        dest = prefix/('bundle.json' if path == evidence_path else path.name)
        save(dest,read(path))
        sources.append({'source':path.relative_to(ROOT).as_posix(),'source_sha256':sha_file(path),
                        'snapshot':dest.as_posix(),'snapshot_sha256':sha_file(HERE/dest)})
    for path,obj in records:
        dest = prefix/'calls'/path.name
        save(dest,obj)
        sources.append({'source':path.relative_to(ROOT).as_posix(),'source_sha256':sha_file(path),
                        'snapshot':dest.as_posix(),'snapshot_sha256':sha_file(HERE/dest)})
        if audit:
            copied = ROOT/'audit/failure_audit_20261029/samples'/item['audit_id']/'calls'/path.name
            if read(copied) != obj:
                raise RuntimeError('STOP: audit call copy disagrees with global record')
    response_texts = (bundle.get('recorded_answer') or {}).get('response',[])
    solver_sources = [s.get('source','') for s in bundle.get('solver_events',[])]
    return records, prefix, sources, selected, response_texts, solver_sources


def inspect_calls(records, prefix, response_texts, solver_sources):
    stages, frame, base, delta, required_extra = [], -1, None, None, []
    last_candidate, last_kind = None, None
    previous_output = None
    previous_call_role = None
    complete_outputs = 0

    def add(stage, b, d, f, ref, extras=(), transport=False, **metadata):
        idx = len(stages)+1
        payload = {'B':b,'delta':d,'Final':f,'extra_deltas':list(extras),
                   'formats':['python']*3,'references':[f'frame/{frame}/U02',f'frame/{frame}/increment',ref]}
        input_path = prefix/'contracts'/f'{idx:03}_{stage}.json'
        save(input_path,payload)
        result = check_contract(b,d,f,formats=('python',)*3,refs=payload['references'],extra_deltas=extras)
        stages.append({'stage_id':idx,'stage':stage,'frame':frame,'input_path':input_path.as_posix(),
                       'input_sha256':sha_file(HERE/input_path),'transport_only':transport,
                       'result':result,**metadata})

    for path,call in records:
        messages = call.get('messages') or []
        if not messages or not isinstance(messages[-1].get('content'),str):
            raise RuntimeError('STOP: historical message schema unconfirmed')
        prompt = messages[-1]['content']; kind = role(prompt)
        choices = call.get('choices') or []
        output = choices[0].get('message',{}).get('content') if choices else None
        finished = bool(choices and choices[0].get('finish_reason') == 'stop' and output)
        ref = f'{path.relative_to(ROOT).as_posix()}#/choices/0/message/content'
        if kind == 'U02':
            frame += 1; base = output if finished else None; delta = None
            required_extra=[]; last_candidate=None; last_kind=None
        elif kind == 'U06':
            incoming = segment(prompt,'Existing script:','Key requirements:')
            if base is None or canonical_content(incoming) != canonical_content(base):
                raise RuntimeError('STOP: U06 base not traceable to recorded U02')
            delta = output if finished else None
        elif kind == 'U10':
            incoming = segment(prompt,'Input Z3 script:','Optimization requirements:')
            if previous_call_role == 'U06':
                if delta is None or canonical_content(incoming) != canonical_content(delta):
                    raise RuntimeError('STOP: U10 input not traceable to U06 increment')
            elif previous_call_role == 'U02':
                if base is None or canonical_content(incoming) != canonical_content(base):
                    raise RuntimeError('STOP: base-only U10 not traceable to U02')
                delta = ''  # documented base-only route, not invented missing delta
            else:
                raise RuntimeError('STOP: unrecognized U10 lineage')
            add('U10_received_input',base,delta,incoming,ref.replace('/choices/0/message/content','/messages/0/content'),transport=True,
                call_id=call['call_id'],lineage='exact prompt segment matched previous response')
            candidate = output if finished else None
            if candidate is not None and not any(canonical_content(candidate) in x for x in response_texts) and canonical_content(candidate) not in solver_sources:
                # Saved response strings can include the fenced content or the
                # code_response-normalized version, but not an unrecorded guess.
                if not any(canonical_content(candidate) == canonical_content(s.partition(':')[2]) for s in response_texts if ':' in s):
                    raise RuntimeError('STOP: U10 response missing saved final-attempt evidence')
            add('U10_output',base,delta,candidate,ref,call_id=call['call_id'],complete_response=finished)
            last_candidate=candidate;last_kind='U10';complete_outputs+=int(finished)
        elif kind == 'U09':
            b = segment(prompt,'1. Base Z3 script:','2. Constraint set 1:')
            d1 = segment(prompt,'2. Constraint set 1:','3. Constraint set 2:')
            d2 = segment(prompt,'3. Constraint set 2:','Requirements:')
            if base is None or canonical_content(b) != canonical_content(base):
                raise RuntimeError('STOP: U09 base lineage mismatch')
            if d1.strip() and last_candidate is not None and canonical_content(d1) != canonical_content(last_candidate):
                raise RuntimeError('STOP: U09 input1 does not match previous candidate')
            if previous_call_role != 'U07' or previous_output is None or canonical_content(d2) != canonical_content(previous_output):
                raise RuntimeError('STOP: U09 input2 not traceable to U07')
            required_extra=[{'text':d1,'format':'python','reference':ref+'#input_constraint_set_1'},
                            {'text':d2,'format':'python','reference':ref+'#input_constraint_set_2'}]
            # Keep the original U06 increment in addition to the explicit U09 inputs.
            if delta is None:
                delta=''  # no U06 route occurred; U09 provides both explicit sets
            add('U09_output_full_lineage',base,delta,output if finished else None,ref,
                extras=required_extra,call_id=call['call_id'],complete_response=finished)
            add('U09_base_presence_only',base,'',output if finished else None,ref,
                call_id=call['call_id'],limited_scope='base membership only; extra assertions mean UNKNOWN')
            last_candidate=output if finished else None;last_kind='U09';complete_outputs+=int(finished)
        elif kind == 'U01':
            if last_kind not in {'U09','U10'}:
                raise RuntimeError('STOP: repair without traceable original contract')
            if len(messages)<2 or messages[-2].get('role')!='assistant' or last_candidate is None or canonical_content(messages[-2]['content']) != canonical_content(last_candidate):
                raise RuntimeError('STOP: repair predecessor lineage mismatch')
            add('U01_repair_original_contract',base,delta,output if finished else None,ref,
                extras=required_extra,call_id=call['call_id'],complete_response=finished)
            add('U01_repair_vs_previous',last_candidate,'',output if finished else None,ref,
                call_id=call['call_id'],limited_scope='no semantic claim; unsupported predecessor remains unknown')
            last_candidate=output if finished else None;complete_outputs+=int(finished)
        if kind != 'analysis_or_filter':
            previous_output=output if finished else None;previous_call_role=kind
    primary = [s for s in stages if s['stage'] in {'U10_output','U01_repair_original_contract','U09_output_full_lineage'}]
    diagnostic_stages = {'U09_base_presence_only', 'U01_repair_vs_previous'}
    statuses = [s['result']['contract_status'] for s in stages if s['stage'] not in diagnostic_stages]
    if 'FAIL' in statuses:
        status='FAIL'
    elif not primary:
        status='NOT_APPLICABLE' if not records else 'UNKNOWN'
    elif 'UNKNOWN' in statuses:
        status='UNKNOWN'
    else:
        status='PASS'
    counts=Counter()
    for s in stages:
        counts.update(s['result']['counts'])
    return {'contract_status':status,'stages':stages,'stage_count':len(stages),
            'full_output_contract_count':len(primary),'complete_output_response_count':complete_outputs,
            'stage_status_counts':dict(Counter(statuses)),'issue_occurrence_counts':dict(counts),
            'diagnostic_only_stage_names':sorted(diagnostic_stages),
            'reason_if_no_stages':'no_completed_B_delta_Final_transition' if not stages else None,
            'semantic_correctness':'NOT_ASSESSED','polarity_correctness':'NOT_ASSESSED',
            'alert_safety_decision':None}


def cohort_run(cohort):
    before=verify_protected()
    frozen=None
    if cohort=='fixed_20':
        frozen=verify_freeze()
        save('fixed_20_started.json',{'started_at':now(),'freeze_sha256':sha_file(HERE/'candidate_freeze.json'),
                                    'note':'one attempt only; a failed run is not silently repeated'})
    else:
        tests=read(HERE/'synthetic_test_results.json')
        if tests['failed_count']:
            raise RuntimeError('STOP: synthetic tests failed')
    manifest_path=ROOT/('audit/failure_audit_20261029/audit_samples.json' if cohort=='audit_10' else 'safety_runs/20261029_v1/fixed_holdout.json')
    manifest=read(manifest_path);items=manifest if cohort=='audit_10' else manifest['samples']
    assert len(items)==(10 if cohort=='audit_10' else 20)
    started=time.perf_counter();rows=[]
    for n,item in enumerate(items,1):
        sample_started=time.perf_counter()
        records,prefix,sources,selected,responses,solvers=snapshot_sample(cohort,n,item,audit=cohort=='audit_10')
        result=inspect_calls(records,prefix,responses,solvers)
        result.update(sample_id=item['sample_id'],audit_id=item.get('audit_id'),position_in_fixed_manifest=n,
                      source_provenance=sources,call_selection=selected,seconds=time.perf_counter()-sample_started)
        rows.append(result)
        print(cohort,n,result['contract_status'],result['stage_status_counts'])
    after=verify_protected()
    if frozen:
        verify_freeze()
    report={'cohort':cohort,'completed_at':now(),'sample_count':len(rows),'rows':rows,
            'seconds':time.perf_counter()-started,'preservation_before':before,'preservation_after':after,
            'model_calls':0,'z3_runs':0,'historical_python_executions':0,'new_alert_decisions':0,
            'result_type':'static preservation diagnosis; not safety verdicts or accuracy',
            'candidate_freeze_sha256':sha_file(HERE/'candidate_freeze.json') if frozen else None}
    save(cohort+'_results.json',report)
    print('SUMMARY',dict(Counter(r['contract_status'] for r in rows)))


def freeze():
    verify_protected()
    if not (HERE/'audit_10_results.json').is_file():
        raise RuntimeError('Audit must precede freeze')
    if (HERE/'fixed_20_started.json').exists():
        raise RuntimeError('Cannot freeze after regression was started')
    files=FROZEN+[p.relative_to(HERE).as_posix() for p in sorted((HERE/'synthetic_cases').glob('*.json'))]
    save('candidate_freeze.json',{'frozen_at':now(),'candidate_sha256':{p:sha_file(HERE/p) for p in files},
                                'audit_results_sha256':sha_file(HERE/'audit_10_results.json'),
                                'synthetic_results_sha256':sha_file(HERE/'synthetic_test_results.json'),
                                'fixed_inputs':read(BASELINE)['fixed_inputs'],
                                'scope':'already observed fixed regression, one run after this freeze'})


if __name__=='__main__':
    if sys.argv[1:] not in [['audit_10'],['freeze'],['fixed_20']]:
        raise SystemExit('Use audit_10, freeze, or fixed_20; outputs are exclusive-create')
    try:
        freeze() if sys.argv[1]=='freeze' else cohort_run(sys.argv[1])
    except Exception as exc:
        # Preserve failure and stop. Do not silently invent a result or retry holdout.
        save('stopped_'+str(time.time_ns())+'.json',{'at':now(),'phase':sys.argv[1],'error':str(exc)})
        raise
