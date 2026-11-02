"""Retain the original E01 *local* diagnostic independently of the new reader.

No safety runner/solver is imported. This is not a relaxation of E05 source
parsing: E05 still refuses unresolved preprocessing, and no global PASS results.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import offline_boundary
offline_boundary.install()
from dependencies import ROOT, load

HERE = Path(__file__).resolve().parent
ADAPTER = ROOT / 'safety_runs/E01_predicate_polarity_consistency/offline_adapter.py'
PIN = 'df26d3a71b7a3018efe5de319d4d2ed0563b2c78ea1b07c15dd502934fe88c4d'


def original_adapter():
    if hashlib.sha256(ADAPTER.read_bytes()).hexdigest() != PIN:
        raise RuntimeError('STOP: E01 adapter hash mismatch')
    sys.modules['predicate_check'] = load('e01')
    spec = importlib.util.spec_from_file_location('_e05_original_e01_adapter', ADAPTER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def save(path, result):
    with path.open('x', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
        f.write('\n')


def synthetic():
    adapter = original_adapter()
    rows = []
    for condition, atom, expected in [('!x','Not(x == 0)',1), ('!x','x == 0',0),
                                       ('x','x == 0',1), ('x','x != 0',0)]:
        code='void f(void)\n{\n    int x;\n    if ('+condition+')\n        use(x);\n}\n'
        bundle={'context':{'frames':[{'code':code,'function':'f','var_name':'other',
                  'extracted':{'target_conditions':[{'condition':'if ('+condition+')','line_number':3}]}}]},
                'recorded_answer':{'response':["step 1 z3 script: ```python\nx=Int('x')\ns.add("+atom+")\n```"]}}
        result=adapter.inspect_bundle(bundle)
        rows.append({'input':bundle,'expected_conflicts':expected,'actual':result,
                     'passed':result['conflicting_condition_count']==expected})
    save(HERE/'baseline_local_tests.json',{'rows':rows,'passed':sum(r['passed'] for r in rows),'total':len(rows),
                                         'scope':'retention of unchanged E01 diagnostic only'})
    if not all(r['passed'] for r in rows):
        raise RuntimeError('STOP: original E01 local baseline regression')
    print('original E01 local retention:',len(rows),'/',len(rows))


def run(cohort):
    freeze=json.loads((HERE/'baseline_local_freeze.json').read_text(encoding='utf-8'))
    for relative, expected in freeze['sha256'].items():
        if hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()!=expected:
            raise RuntimeError('STOP: local baseline freeze mismatch')
    baseline=json.loads((HERE/'baseline_state.json').read_text(encoding='utf-8'))['protected_files']
    adapter=original_adapter(); rows=[]
    prefix=ROOT/'safety_runs/E02_base_constraint_preservation_static/evidence'/(cohort+'_frozen_candidate')
    for p in sorted(prefix.glob('*/bundle.json')):
        relative=p.relative_to(ROOT).as_posix()
        if hashlib.sha256(p.read_bytes()).hexdigest()!=baseline[relative]:
            raise RuntimeError('STOP: original bundle mismatch')
        bundle=json.loads(p.read_text(encoding='utf-8'))
        result=adapter.inspect_bundle(bundle)
        rows.append({'sample_id':bundle['candidate']['sample_id'],'input':relative,'sha256':baseline[relative],
                     'result':result,'alert_safety_decision':None})
    save(HERE/('retained_E01_'+cohort+'.json'),{'rows':rows,'count':len(rows),'boundary_attempts':offline_boundary.ATTEMPTS,
        'meaning':'Original E01 local evidence retained, not a new full E05 semantic proof or safety replay',
        'z3_calls':0,'model_calls':0})
    print('retained E01',cohort,'local conflicts:',sum(r['result']['conflicting_condition_count'] for r in rows))


if __name__=='__main__':
    if sys.argv[1]=='synthetic':
        synthetic()
    else:
        run(sys.argv[1])
