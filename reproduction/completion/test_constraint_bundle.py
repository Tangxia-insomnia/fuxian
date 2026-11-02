"""E03 offline tests. Generated/historical Python remains inert text/AST.

Run from reproduction/: python -B -m completion.test_constraint_bundle [output]
Only E03 output files are created; no old completion tests (which run Z3) are run.
"""
import ast
import hashlib
import json
from pathlib import Path
import sys
import time
from types import SimpleNamespace
from unittest.mock import patch

from .constraint_bundle import (assemble_base_delta, validate_base_delta,
                                ConstraintTransferRejected, replace_once, CHECKER_SHA256, _checker)

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT/'safety_runs/E03_base_delta_explicit_transfer_fix'


def cases():
    b = "```python\nx=Int('x')\ns.add(x == 0)\n```"
    decl = "x=Int('x')\n"
    def final(assertions, declarations=decl):
        return 'def check_constraints():\n' + ''.join('    '+s+'\n' for s in (declarations+'s=Solver()\n'+assertions+'\nreturn s.check() == sat').splitlines())
    add = 's.add(x >= 0)'
    same = 's.add(x == 0)'
    opposite = 's.add(Not(x == 0))'
    rows = [
        ('T01','empty_delta',b,'',final(same),True,True),
        ('T02','comment_only_delta',b,'# no new constraints\n',final(same),True,True),
        ('T03','new_assertion',b,add,final(same+'\n'+add),True,True),
        ('T04','new_declaration_and_assertion',b,"y=Int('y')\ns.add(y != 0)",final(same+'\ns.add(y != 0)',decl+"y=Int('y')\n"),True,True),
        ('T05','duplicate_assertion_preserved',b,same,final(same+'\n'+same),True,True),
        ('T06','duplicate_declaration_rejected',b,"x=Int('x')\n"+same,final(same),False,None),
        ('T07','type_conflict_rejected',b,"x=Bool('x')\ns.add(x)",final(same),False,None),
        ('T08','wrong_rename_in_U10',b,'',final('s.add(y == 0)',"y=Int('y')\n"),True,False),
        ('T09','missing_B',None,add,final(add),False,None),
        ('T10','missing_delta',b,None,final(same),False,None),
        ('T11','U10_drops_base',b,add,final(add),True,False),
        ('T12','U10_drops_delta',b,add,final(same),True,False),
        ('T13','U10_unsupported_control_flow',b,'',final('if x == 0:\n    s.add(x == 0)'),True,False),
        ('T14','contradictions_preserved_not_semantics_approved',b,opposite,final(same+'\n'+opposite),True,True),
        ('T15','unknown_delta_syntax',b,'s.push()',final(same),False,None),
        ('T16','unsupported_B_macro',"x=Int('x')\ns.add(MACRO(x))",'',final(same),False,None),
        ('T17','U10_duplicate_declaration_rejected',b,'',final(same,decl+decl),True,False),
        ('T18','missing_base_raw_empty_string','',add,final(add),False,None),
        ('T19','plain_code_preserves_whitespace',"x = Int('x')\n\ns.add(x == 0)\n",'# delta trailing space \n',final(same),True,True),
        ('T20','fence_with_extraneous_text_rejected',b,'Here is code:\n```python\n'+add+'\n```',final(same+'\n'+add),False,None),
        ('T21','U10_new_solver_without_reload',b,'',final(same+'\ns=Solver()'),True,False),
        ('T22','U10_extra_unexplained_assertion',b,'',final(same+'\n'+add),True,False),
        ('T23','delta_rebinds_Python_name',b,"x=Int('replacement')\ns.add(x == 0)",final(same),False,None),
    ]
    return [dict(test_id=i,scenario=n,B=base,delta=d,U10_output=f,expected_assembly=a,expected_postcondition=p)
            for i,n,base,d,f,a,p in rows]


def run(output='synthetic_test_results.json'):
    start = time.perf_counter(); results=[]
    trial=RUN/'test_runs'/Path(output).stem
    trial.mkdir(parents=True,exist_ok=False)
    case_dir=RUN/'synthetic_cases';case_dir.mkdir(exist_ok=True)
    for case in cases():
        path=case_dir/(case['test_id']+'.json')
        encoded=json.dumps(case,ensure_ascii=False,indent=2)+'\n'
        if path.exists():
            assert path.read_text(encoding='utf-8')==encoded, 'Existing synthetic input changed'
        else:
            with path.open('x',encoding='utf-8',newline='\n') as handle:handle.write(encoded)
        bundle=None; assembly=None; post=None
        try:
            bundle=assemble_base_delta(case['B'],case['delta'],base_source=case['test_id']+'/U02',delta_source=case['test_id']+'/U06')
            assembly=bundle['assembly_audit'];actual_assembly=True
        except ConstraintTransferRejected as exc:
            assembly=exc.audit;actual_assembly=False
        passed=actual_assembly==case['expected_assembly']
        if bundle is not None:
            for role in ('base','delta'):
                evidence=bundle[role];span=evidence['merged_span']
                passed = passed and bundle['merged_script'][span['start']:span['end']]==evidence['code_text']
                passed = passed and evidence['raw_text']==case['B' if role=='base' else 'delta']
            second=assemble_base_delta(case['B'],case['delta'])
            passed = passed and second['merged_script']==bundle['merged_script']
            post=validate_base_delta(case['B'],case['delta'],case['U10_output'])
            passed = passed and post['accepted']==case['expected_postcondition']
            if case['test_id']=='T05':
                passed = passed and bundle['merged_script'].count('s.add(x == 0)')==2 and assembly['counts']['final_duplicate_assertions']==1
            if case['test_id']=='T14':
                passed = passed and 's.add(x == 0)' in bundle['merged_script'] and 's.add(Not(x == 0))' in bundle['merged_script']
        for record in (assembly,post):
            if record:
                passed=passed and record['semantic_correctness']=='NOT_ASSESSED' and record['polarity_correctness']=='NOT_ASSESSED' and record['alert_safety_decision'] is None and not record['solver_executed']
        results.append(dict(test_id=case['test_id'],scenario=case['scenario'],passed=passed,
                            expected_assembly=case['expected_assembly'],actual_assembly=actual_assembly,
                            expected_postcondition=case['expected_postcondition'],bundle=bundle,
                            assembly_audit=assembly,postcondition_audit=post))

    # Integration checks render the author's text but never execute that pipeline
    # or generated model code. Only the NEW adapter methods run with local spies.
    from . import engine
    integration=[]
    source=engine.completed_source(patch_dir=trial/'rendered_candidate')
    tree=ast.parse(source)
    pipeline=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='data_flow_analysis_pipeline')
    calls=[n for n in ast.walk(pipeline) if isinstance(n,ast.Call)]
    merge_calls=[n for n in calls if isinstance(n.func,ast.Name) and n.func.id=='assemble_base_delta']
    u10s=[n for n in calls if isinstance(n.func,ast.Attribute) and n.func.attr=='get_z3_extract']
    checks=[n for n in calls if isinstance(n.func,ast.Name) and n.func.id=='validate_base_delta_output']
    integration.append({'test':'exact_single_target_and_raw_B_delta', 'passed':len(merge_calls)==1 and [ast.unparse(x) for x in merge_calls[0].args]==['response_message_target','bug_line_constraints_response'] and len(u10s)==1 and ast.unparse(u10s[0].args[0])=="e03_bundle['merged_script']"})
    loop=next(n for n in ast.walk(pipeline) if isinstance(n,ast.While) and any(isinstance(s,ast.Expr) and isinstance(s.value,ast.Call) and isinstance(s.value.func,ast.Name) and s.value.func.id=='validate_base_delta_output' for s in n.body))
    check_index=next(i for i,n in enumerate(loop.body) if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Name) and n.value.func.id=='validate_base_delta_output')
    integration.append({'test':'postcheck_before_try_and_repair_catch', 'passed':len(checks)==1 and isinstance(loop.body[check_index+1],ast.Try)})
    before=ast.parse((RUN/'engine.before.py.txt').read_text(encoding='utf-8'))
    after=ast.parse((ROOT/'completion/engine.py').read_text(encoding='utf-8'))
    cb=next(n for n in before.body if isinstance(n,ast.ClassDef) and n.name=='CompletedEngine')
    ca=next(n for n in after.body if isinstance(n,ast.ClassDef) and n.name=='CompletedEngine')
    for name in ('solve','solve_base','prepare','code_response','array_response'):
        a=next(n for n in ca.body if isinstance(n,ast.FunctionDef) and n.name==name)
        b=next(n for n in cb.body if isinstance(n,ast.FunctionDef) and n.name==name)
        integration.append({'test':'unchanged_method_'+name,'passed':ast.dump(a)==ast.dump(b)})
    reference=ast.parse((ROOT/'patches/completed_function_bodies.py').read_text(encoding='utf-8'))
    oldfn=next(n for n in reference.body if isinstance(n,ast.FunctionDef) and n.name=='data_flow_analysis_pipeline')
    def branch(fn,needle):
        return [ast.dump(n) for n in fn.body if isinstance(n,ast.If) and needle in ast.unparse(n.test)]
    integration.append({'test':'U07_U09_early_jump_branch_unchanged','passed':branch(oldfn,'early_jump_constraints_list')==branch(pipeline,'early_jump_constraints_list')})
    new_run=next(n for n in ca.body if isinstance(n,ast.FunctionDef) and n.name=='run')
    injected=[n.targets[0].slice.value for n in ast.walk(new_run) if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Subscript) and isinstance(n.targets[0].value,ast.Name) and n.targets[0].value.id=='ns' and isinstance(n.targets[0].slice,ast.Constant)]
    integration.append({'test':'explicit_namespace_injection','passed':{'assemble_base_delta','validate_base_delta_output'}<=set(injected)})
    for count in (0,2):
        try:
            replace_once('target'*count,'target','replacement')
            ok=False
        except RuntimeError:
            ok=True
        integration.append({'test':f'reject_{count}_patch_targets','passed':ok})
    # Exercise completed_source's exact matching, not only its generic helper.
    author_path=ROOT/'upstream/llm4pfa/feasibility_analysis_pipeline.py'
    original=author_path.read_text(encoding='utf-8');read_text=Path.read_text
    target='        merged_prompt = prompt.get_z3_extract(bug_line_constraints_response_process)'
    for count in (0,2):
        modified=original.replace(target,'' if count==0 else target+'\n'+target)
        def fake_read(path,*args,**kwargs):
            return modified if path==author_path else read_text(path,*args,**kwargs)
        with patch.object(Path,'read_text',fake_read):
            try:
                engine.completed_source(patch_dir=trial/f'SHOULD_NOT_RENDER_{count}')
                ok=False
            except RuntimeError:
                ok=True
        integration.append({'test':f'completed_source_stops_on_{count}_matches_before_writing','passed':ok and not (trial/f'SHOULD_NOT_RENDER_{count}').exists()})
    # The original Prompt file is never executed. This spy observes the exact
    # payload passed to get_z3_extract by the adapter's offline call contract.
    def make_engine(name):
        obj=object.__new__(engine.CompletedEngine)
        obj.repository=SimpleNamespace(dataset='synthetic_offline')
        obj.model=SimpleNamespace(sample_id=name)
        obj.transfer_events=[];obj.transfer_position=0;obj.level=0
        obj.sample_dir=trial/'synthetic_engine_traces'/name;obj.sample_dir.mkdir(parents=True,exist_ok=False)
        return obj
    b=cases()[0]['B'];d='s.add(x >= 0)'
    obj=make_engine('rejected_U10')
    bundle=obj.assemble_transfer(b,d)
    spy=SimpleNamespace(received=None)
    def get_z3_extract(payload):
        spy.received=payload
        return 'U10 prompt with input:\n'+payload
    get_z3_extract(bundle['merged_script'])
    integration.append({'test':'offline_U10_spy_receives_exact_B_plus_delta','passed':spy.received==bundle['merged_script'] and bundle['base']['code_text'] in spy.received and bundle['delta']['code_text'] in spy.received})
    solver_calls=0;model_retry_calls=0
    try:
        obj.validate_transfer_output(bundle,cases()[10]['U10_output'])
        solver_calls+=1
        ok=False
    except ConstraintTransferRejected:
        ok=True
    integration.append({'test':'rejected_postcondition_stops_before_solver_and_retry','passed':ok and solver_calls==0 and model_retry_calls==0 and len(obj.transfer_events)==2})
    obj=make_engine('rejected_pre_U10')
    try:
        obj.assemble_transfer(b,"x=Int('x')\ns.add(x >= 0)")
        ok=False
    except ConstraintTransferRejected:
        ok=True
    integration.append({'test':'duplicate_declaration_stops_before_U10','passed':ok and len(obj.transfer_events)==1})
    # A repaired output must face the same original B+delta, not a weakened copy.
    obj=make_engine('repaired_output')
    bundle=obj.assemble_transfer(b,d)
    obj.validate_transfer_output(bundle,cases()[2]['U10_output'])
    try:
        obj.validate_transfer_output(bundle,cases()[10]['U10_output'],attempt=2)
        ok=False
    except ConstraintTransferRejected:
        ok=True
    integration.append({'test':'U01_cannot_bypass_original_postcondition','passed':ok and obj.transfer_events[-1]['stage']=='after_U01_before_solver'})
    # Simulate checker corruption without writing E02 or importing another parser.
    original_read_bytes=Path.read_bytes
    with patch.object(Path,'read_bytes',lambda self: b'bad' if self==ROOT/'safety_runs/E02_base_constraint_preservation_static/checker.py' else original_read_bytes(self)):
        try:
            _checker();ok=False
        except RuntimeError:
            ok=True
    integration.append({'test':'pinned_checker_hash_mismatch_stops','passed':ok})
    report={'synthetic_count':len(results),'synthetic_passed':sum(r['passed'] for r in results),
            'integration_count':len(integration),'integration_passed':sum(r['passed'] for r in integration),
            'tests':results,'integration_tests':integration,'seconds':time.perf_counter()-start,
            'e02_checker_sha256':CHECKER_SHA256,'z3_runs':0,'model_calls':0,'historical_python_executions':0,
            'scope':'synthetic adapter/method tests plus AST placement checks; no real U10/model/pipeline execution'}
    out=RUN/output
    with out.open('x',encoding='utf-8',newline='\n') as handle:json.dump(report,handle,ensure_ascii=False,indent=2)
    print(json.dumps({k:v for k,v in report.items() if k not in {'tests','integration_tests'}}))
    for item in results+integration:
        if not item['passed']:print('FAILED',item.get('test_id',item.get('test')))
    return all(r['passed'] for r in results+integration)


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    if len(sys.argv)>2:raise SystemExit('Only one optional E03 result filename')
    raise SystemExit(0 if run(sys.argv[1] if len(sys.argv)==2 else 'synthetic_test_results.json') else 1)
