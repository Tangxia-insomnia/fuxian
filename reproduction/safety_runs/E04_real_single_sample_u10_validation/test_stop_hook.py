"""Offline stopping tests; all constraint strings remain inert."""
import ast
import json
from pathlib import Path
import runpy
from types import SimpleNamespace

import run_e04 as trial


def execute():
    results = []
    base = "x=Int('x')\ns.add(x == 0)"
    delta = 's.add(x >= 0)'
    outputs = {
        'PASS': "def check_constraints():\n x=Int('x')\n s=Solver()\n s.add(x == 0)\n s.add(x >= 0)\n return s.check() == sat",
        'FAIL': "def check_constraints():\n x=Int('x')\n s=Solver()\n s.add(x >= 0)\n return s.check() == sat",
        'UNKNOWN': "def check_constraints():\n values=[]\n return True",
    }
    for expected, output in outputs.items():
        obj = object.__new__(trial.engine_module.CompletedEngine)
        obj.repository = SimpleNamespace(dataset='offline_synthetic')
        obj.model = SimpleNamespace(sample_id='offline_hook_'+expected)
        obj.transfer_position = 0
        obj.level = 0
        obj.transfer_events = []
        obj.sample_dir = trial.HERE/'offline_hook_traces'/expected
        obj.sample_dir.mkdir(parents=True, exist_ok=False)
        bundle = obj.assemble_transfer(base, delta)
        events = []
        hook = trial.make_stop_hook(obj, lambda kind, **d: events.append({'kind':kind, **d}))
        solver, repair = 0, 0
        observed = None
        try:
            hook(bundle, output)
            solver += 1
        except Exception:
            repair += 1
        except trial.ExperimentStop as stop:
            observed = stop
        audit = obj.transfer_events[-1]
        results.append({'name': 'stop_after_original_postcondition_'+expected,
            'passed': bool(observed and observed.details['status']==expected and solver==repair==0
                           and audit['contract_status']==expected and audit['accepted']==(expected=='PASS')),
            'contract_status': audit['contract_status'], 'solver_calls': solver, 'repair_calls': repair,
            'stop_reason': observed.reason if observed else None})

    source = trial.engine_module.completed_source(patch_dir=trial.HERE/'offline_rendered_pipeline')
    tree = ast.parse(source)
    fn = next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='data_flow_analysis_pipeline')
    gates = [n for n in ast.walk(fn) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='validate_base_delta_output']
    loop = next(n for n in ast.walk(fn) if isinstance(n,ast.While) and any(
        isinstance(x,ast.Expr) and isinstance(x.value,ast.Call) and isinstance(x.value.func,ast.Name)
        and x.value.func.id=='validate_base_delta_output' for x in n.body))
    index = next(i for i,n in enumerate(loop.body) if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call)
                 and isinstance(n.value.func,ast.Name) and n.value.func.id=='validate_base_delta_output')
    results.append({'name':'unchanged_E03_gate_is_before_solver_try',
                    'passed':len(gates)==1 and isinstance(loop.body[index+1],ast.Try)})
    results.append({'name':'stop_bypasses_Exception_handlers',
                    'passed':issubclass(trial.ExperimentStop,BaseException) and not issubclass(trial.ExperimentStop,Exception)})
    for name in ('z3','z3.z3','completion.solver_worker'):
        stopped = False
        try:
            trial.NoSolverImports().find_spec(name)
        except trial.ExperimentStop:
            stopped = True
        results.append({'name':'deny_import_'+name, 'passed':stopped})
    prompt = runpy.run_path(str(trial.ROOT/'upstream/llm4pfa/prompt_templates.py'),run_name='__e04_test_prompt__')['Prompt']()
    state = {}; events = []
    observer = trial.ObservedPrompt(prompt,state,lambda kind,**d:events.append({'kind':kind,**d}))
    original = prompt.get_z3_extract(base+'\n'+delta)
    observed = observer.get_z3_extract(base+'\n'+delta)
    results.append({'name':'prompt_observation_preserves_original_exact_string',
                    'passed':original==observed and state['stage']=='U10' and len(events)==1})
    stopped = False
    try:
        observer.re_generate_prompt('error')
    except trial.ExperimentStop:
        stopped = True
    results.append({'name':'repair_prompt_forbidden','passed':stopped})
    report = {'tests':results,'total':len(results),'passed':sum(x['passed'] for x in results),
              'model_calls':0,'z3_runs':0,'historical_generated_python_executions':0,
              'scope':'only synthetic postconditions and AST placement, not real model execution'}
    trial.put(trial.HERE/'offline_tests.json',report)
    print(json.dumps({k:v for k,v in report.items() if k!='tests'}))
    assert report['passed']==report['total'], 'STOP: offline hook tests failed'


if __name__=='__main__':
    execute()
