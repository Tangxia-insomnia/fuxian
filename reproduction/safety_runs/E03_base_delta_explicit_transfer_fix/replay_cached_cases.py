"""Two explicitly requested historical cases only; never execute their code.

This is a static input substitution experiment, not a new U10 model response.
"""
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
import time
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from completion.constraint_bundle import validate_base_delta, CHECKER_SHA256, _checker
from completion.engine import CompletedEngine

HERE = Path(__file__).resolve().parent
E02 = ROOT/'safety_runs/E02_base_constraint_preservation_static'


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def save(name, value):
    path=HERE/name
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8',newline='\n') as handle:
        json.dump(value,handle,ensure_ascii=False,indent=2)


def segment(prompt,begin,end):
    if prompt.count(begin)!=1 or prompt.count(end)!=1:
        raise RuntimeError('STOP: ambiguous historical prompt segment')
    return prompt.split(begin,1)[1].split(end,1)[0].strip()


def history_decode(text):
    match=re.search(r'```(?:python)?\s*\n?(.*?)```',text,re.S)
    return (match[1] if match else text).replace('from z3 import *','').strip()


def execute():
    started=time.perf_counter()
    frozen=json.loads((E02/'hashes.json').read_text(encoding='utf-8'))['files_sha256']
    before=json.loads((HERE/'baseline_state.json').read_text(encoding='utf-8'))
    requests=[{'case':'A04','folder':'04','sample_id':'NPD/codeql/kernel69:row=12:index=24','position':12,
               'B':231,'delta':233,'U10':234,'other':[235,238],'expected_cached_post':'UNKNOWN'},
              {'case':'A01','folder':'01','sample_id':'NPD/codeql/kernel69:row=10:index=22','position':10,
               'B':224,'delta':226,'U10':227,'other':[],'expected_cached_post':'PASS'}]
    merges=[];posts=[];case_reports=[]
    for request in requests:
        case=request['case'];records={};sources=[]
        for call_id in [request['B'],request['delta'],request['U10']]+request['other']:
            relative=f'evidence/audit_10_frozen_candidate/{request["folder"]}/calls/{call_id:04d}.json'
            path=E02/relative;data=path.read_bytes();h=sha_bytes(data)
            if h!=frozen[relative] or h!=before['original_sha256'][path.relative_to(ROOT).as_posix()]:
                raise RuntimeError('STOP: historical evidence hash mismatch')
            call=json.loads(data)
            if call['sample_id']!=request['sample_id'] or call['call_id']!=call_id or call['choices'][0]['finish_reason']!='stop':
                raise RuntimeError('STOP: historical call provenance cannot be confirmed')
            target=HERE/'evidence'/case/'calls'/path.name
            target.parent.mkdir(parents=True,exist_ok=True)
            with target.open('xb') as handle:handle.write(data)
            sources.append({'source':path.relative_to(ROOT).as_posix(),'sha256':h,'copy':target.relative_to(HERE).as_posix()})
            records[call_id]=call
        def response(call_id):
            return records[call_id]['choices'][0]['message']['content']
        base=response(request['B']);delta=response(request['delta']);u10=response(request['U10'])
        u06_input=segment(records[request['delta']]['messages'][-1]['content'],'Existing script:','Key requirements:')
        if history_decode(u06_input)!=history_decode(base):
            raise RuntimeError('STOP: U06 base differs from U02 response')
        old_input=segment(records[request['U10']]['messages'][0]['content'],'Input Z3 script:','Optimization requirements:')
        if history_decode(old_input)!=history_decode(delta):
            raise RuntimeError('STOP: old U10 input not equal to U06 delta')
        old_check=validate_base_delta(base,delta,old_input,final_source=f'{case}/old_U10_input')
        obj=object.__new__(CompletedEngine)
        obj.repository=SimpleNamespace(dataset='benchmark/NPD/codeql/codeql_kernel69_nullpointer.json')
        obj.model=SimpleNamespace(sample_id=request['sample_id'])
        obj.transfer_events=[];obj.transfer_position=request['position'];obj.level=1 if len(request['other']) else 0
        obj.sample_dir=HERE/'engine_traces'/case;obj.sample_dir.mkdir(parents=True,exist_ok=False)
        bundle=obj.assemble_transfer(base,delta)
        # Independent offline observer; no real U10 call occurs.
        received={'value':None,'calls':0}
        def observe_u10_argument(value):
            received['value']=value;received['calls']+=1
        observe_u10_argument(bundle['merged_script'])
        if received['value']!=bundle['merged_script']:
            raise RuntimeError('STOP: offline transfer observer mismatch')
        from completion.constraint_bundle import ConstraintTransferRejected
        try:
            post=obj.validate_transfer_output(bundle,history_decode(u10))
            permitted=True
        except ConstraintTransferRejected as exc:
            post=exc.audit;permitted=False
        merge={'case':case,'sample_id':request['sample_id'],'source_files':sources,
               'old_U10_input':old_input,'old_input_equals_delta':True,'old_input_check':old_check,
               'new_bundle':bundle,'offline_U10_observed_input':received['value'],
               'offline_U10_observer_calls':received['calls'],'real_U10_model_calls':0,
               'before_after_scope':'old recorded payload vs new deterministic payload; no new model output'}
        postrecord={'case':case,'sample_id':request['sample_id'],'recorded_U10_raw_output':u10,
                    'recorded_U10_code_sent_to_gate':history_decode(u10),'postcondition':post,
                    'structurally_admissible_for_next_stage':permitted,'solver_executed':False,
                    'scope':'cached old U10 output; not a response to the new payload',
                    'semantic_correctness':'NOT_ASSESSED','polarity_correctness':'NOT_ASSESSED'}
        if request['other']:
            repair=response(request['other'][0])
            repair_check=validate_base_delta(base,delta,history_decode(repair),final_source=f'{case}/old_U01')
            # Observe only the already recorded U09 input/outputs with its explicit
            # sets. It is OUTSIDE the modified route; no engine branch is changed.
            u09call=records[request['other'][1]];prompt=u09call['messages'][0]['content']
            b=segment(prompt,'1. Base Z3 script:','2. Constraint set 1:')
            d1=segment(prompt,'2. Constraint set 1:','3. Constraint set 2:')
            d2=segment(prompt,'3. Constraint set 2:','Requirements:')
            if history_decode(b)!=history_decode(base) or history_decode(d1)!=history_decode(repair):
                raise RuntimeError('STOP: U09 recorded lineage mismatch')
            u09out=response(request['other'][1])
            u09check=_checker().check_contract(base,delta,u09out,formats=('python',)*3,
               refs=(case+'/U02',case+'/U06',case+'/historical_U09'),
               extra_deltas=[{'text':d1,'format':'python','reference':case+'/U09/input1'},
                             {'text':d2,'format':'python','reference':case+'/U09/input2'}])
            postrecord.update(historical_U01_output=repair,historical_U01_check=repair_check,
                               historical_U09_output=u09out,historical_U09_full_input_check=u09check,
                               U09_modified=False)
        merges.append(merge);posts.append(postrecord)
        case_reports.append({'case':case,'old_input_contract':old_check['contract_status'],
            'new_input_contract':bundle['assembly_audit']['contract_status'],
            'new_input_accepted':bundle['assembly_audit']['accepted'],
            'cached_U10_output_contract':post['contract_status'],'cached_U10_output_accepted':permitted,
            'expected_cached_post':request['expected_cached_post'],
            'acceptance_passed':old_check['contract_status']=='FAIL' and bundle['assembly_audit']['accepted']
                                and post['contract_status']==request['expected_cached_post']
                                and permitted==(request['expected_cached_post']=='PASS')
                                and post['semantic_correctness']=='NOT_ASSESSED'
                                and post['polarity_correctness']=='NOT_ASSESSED',
            'semantic_correctness':'NOT_ASSESSED','polarity_correctness':'NOT_ASSESSED'})
    save('merge_audit.json',{'cases':merges,'checker_sha256':CHECKER_SHA256,'model_calls':0,'z3_runs':0})
    save('postcondition_audit.json',{'cases':posts,'model_calls':0,'z3_runs':0,'new_safety_decisions':0})
    save('cached_replay_results.json',{'completed_at':datetime.now(timezone(timedelta(hours=8))).isoformat(),
          'cases':case_reports,'seconds':time.perf_counter()-started,'case_count':2,
          'full_audit_10_run':False,'fixed_20_run':False,'historical_python_executions':0,
          'model_calls':0,'z3_runs':0,'scope':'targeted A04/A01 static cached replay only'})
    print(json.dumps(case_reports,ensure_ascii=False))
    if not all(r['acceptance_passed'] for r in case_reports):
        raise RuntimeError('Cached-case static acceptance failed; evidence retained')


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    execute()
