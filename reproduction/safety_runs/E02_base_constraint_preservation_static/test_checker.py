"""Parameterized structural contracts; inputs/output saved without running Z3."""
import json
from pathlib import Path
import sys
import time
from checker import check_contract, expressions

HERE = Path(__file__).resolve().parent


def cases():
    b = '(declare-const x Int)\n(assert (= x 0))\n'
    add = '(assert (>= x 0))\n'
    dec = '(declare-const x Int)\n'
    py_b = "x=Int('x')\ns.add(x == 0)\n"
    def final(body):
        return "def check_constraints():\n    x=Int('x')\n    s=Solver()\n" + ''.join('    '+s+'\n' for s in body) + '    return s.check() == sat\n'
    rows = [
        ('T01', 'empty_delta_keeps_base', b, '', b, 'PASS', None),
        ('T02', 'comment_only_delta_keeps_base', b, '; no new constraints\n', b, 'PASS', None),
        ('T03', 'valid_addition', b, add, b+add, 'PASS', None),
        ('T04', 'duplicate_assertion_visible', b, '(assert (= x 0))', b+'(assert (= x 0))', 'PASS', 'duplicate_assertions'),
        ('T05', 'missing_original_declaration', b, '', '; lost everything', 'FAIL', 'missing_declarations'),
        ('T06', 'same_symbol_different_sort', b, '', '(declare-const x Bool)\n(assert x)', 'FAIL', 'type_conflicts'),
        ('T07', 'renamed_without_identity_mapping', b, '', '(declare-const y Int)\n(assert (= y 0))', 'FAIL', 'symbol_identity_conflicts'),
        ('T08', 'new_solver_loses_old_assertion', py_b, '', final(['s.add(x == 0)', 's=Solver()']), 'FAIL', 'missing_base_assertions'),
        ('T09', 'repair_deletes_base_assertion', b, add, dec+add, 'FAIL', 'missing_base_assertions'),
        ('T10', 'quantified_expression_unsupported', b, '(assert (forall ((y Int)) (= y y)))', b, 'UNKNOWN', None),
        ('T11', 'delta_assertion_missing', b, add, b, 'FAIL', 'missing_delta_assertions'),
        ('T12', 'same_sort_duplicate_declaration', b, '', dec+b, 'PASS', 'duplicate_declarations'),
        ('T13', 'unexplained_extra_assertion', b, '', b+add, 'UNKNOWN', None),
        ('T14', 'SMT_let_expansion_is_structural', b, '', dec+'(assert (let ((t (= x 0))) t))', 'PASS', None),
        ('T15', 'quoted_same_symbol', b, '', '(declare-fun |x| () Int) (assert (= |x| 0))', 'PASS', None),
        ('T16', 'missing_delta_evidence', b, None, b, 'UNKNOWN', None),
        ('T17', 'logic_equivalence_not_assumed', b, '', dec+'(assert (= 0 x))', 'FAIL', 'missing_base_assertions'),
        ('T18', 'macro_function_unsupported', b, '(assert (MACRO x))', b, 'UNKNOWN', None),
        ('T19', 'new_solver_reloads_base', py_b, '', final(['s.add(x == 0)', 's=Solver()', 's.add(x == 0)']), 'PASS', None),
        ('T20', 'branching_generated_python_unsupported', py_b, '', final(['if x == 0:', '    s.add(x == 0)']), 'UNKNOWN', None),
        ('T21', 'last_query_does_not_include_later_add', py_b, '', final(['r=s.check()', 's.add(x == 0)', 'return r == sat']).replace('    return s.check() == sat\n',''), 'FAIL', 'missing_base_assertions'),
        ('T22', 'different_solver_is_not_union', py_b, '', final(['s.add(x == 0)', 'other=Solver()', 'r=other.check()', 'return r == sat']).replace('    return s.check() == sat\n',''), 'FAIL', 'missing_base_assertions'),
        ('T23', 'push_pop_unsupported', py_b, '', final(['s.add(x == 0)', 's.push()', 's.pop()']), 'UNKNOWN', None),
        ('T24', 'different_Python_alias_same_SMT_identity', py_b, '', "def check_constraints():\n    y=Int('x')\n    s=Solver()\n    s.add(y == 0)\n    return s.check() == sat\n", 'PASS', None),
        ('T25', 'same_python_binding_changes_SMT_identity', py_b, '', "def check_constraints():\n    x=Int('y')\n    s=Solver()\n    s.add(x == 0)\n    return s.check() == sat\n", 'FAIL', 'symbol_identity_conflicts'),
        ('T26', 'contradiction_preserved_not_semantics_approved', b, '(assert (not (= x 0)))', b+'(assert (not (= x 0)))', 'PASS', None),
        ('T27', 'unparseable_smt', b, '', '(assert (= x 0)', 'UNKNOWN', None),
        ('T28', 'arbitrary_python_never_executed', py_b, '', "open('SHOULD_NOT_EXIST','w').write('bad')", 'UNKNOWN', None),
        ('T29', 'bitvector_zero_literal_coercion', "x=BitVec('x',64)\ns.add(x != 0)", '', "def check_constraints():\n    x=BitVec('x',64)\n    s=Solver()\n    s.add(x != 0)\n    return s.check() == sat", 'PASS', None),
        ('T30', 'assumptions_not_silently_dropped', py_b, '', "def check_constraints():\n    x=Int('x')\n    s=Solver()\n    return s.check(x == 0) == sat", 'UNKNOWN', None),
        ('T31', 'reference_does_not_restore_missing_declaration', b, '', '(assert (= x 0))', 'FAIL', 'missing_declarations'),
        ('T32', 'SMT_query_snapshot_before_added_assertion', b, '', dec+'(check-sat)\n(assert (= x 0))', 'FAIL', 'missing_base_assertions'),
        ('T33', 'pure_trailing_model_diagnostic', py_b, '', "x=Int('x')\ns=Solver()\ns.add(x == 0)\nif s.check() == sat:\n    print('Model:',s.model())\n", 'PASS', None),
        ('T34', 'model_diagnostic_cannot_hide_constraint', py_b, '', "x=Int('x')\ns=Solver()\nif s.check() == sat:\n    s.add(x == 0)\n", 'UNKNOWN', None),
        ('T35', 'declaration_after_smt_query_is_not_present', b, '', '(assert (= x 0))\n(check-sat)\n(declare-const x Int)', 'FAIL', 'missing_declarations'),
        ('T36', 'extra_declaration_requires_provenance', b, '', b+'(declare-const y Int)', 'UNKNOWN', None),
        ('T37', 'reserved_symbol_is_not_accepted', b, '', '(declare-const true Int)', 'UNKNOWN', None),
    ]
    for cid, name, base, delta, result, status, nonzero in rows:
        fmt = 'python' if base == py_b or cid == 'T29' else 'smtlib'
        yield dict(test_id=cid, scenario=name, B=base, delta=delta, Final=result,
                   formats=[fmt]*3, expected_status=status, expected_nonzero=nonzero)


def run(output='synthetic_test_results.json'):
    start = time.perf_counter()
    folder = HERE/'synthetic_cases'
    folder.mkdir(exist_ok=True)
    results = []
    for case in cases():
        path = folder/(case['test_id']+'.json')
        text = json.dumps(case, ensure_ascii=False, indent=2)+'\n'
        if path.exists():
            assert path.read_text(encoding='utf-8') == text, 'Synthetic input changed'
        else:
            path.write_text(text, encoding='utf-8')
        result = check_contract(case['B'], case['delta'], case['Final'], formats=case['formats'])
        passed = result['contract_status'] == case['expected_status']
        if case['expected_nonzero']:
            passed = passed and result['counts'].get(case['expected_nonzero'], 0) > 0
        if case['test_id'] == 'T08':
            passed = passed and 'new_solver_did_not_reload_base' in result['reasons']
        passed = passed and result['semantic_correctness'] == 'NOT_ASSESSED' and result['alert_safety_decision'] is None
        results.append({'test_id':case['test_id'], 'scenario':case['scenario'], 'passed':passed, 'expected':case['expected_status'], 'result':result})
    report = {'test_count':len(results), 'passed_count':sum(r['passed'] for r in results), 'failed_count':sum(not r['passed'] for r in results),
              'seconds':time.perf_counter()-start, 'tests':results, 'z3_runs':0, 'model_calls':0, 'historical_code_executions':0}
    path = HERE/output
    with path.open('x',encoding='utf-8') as f:
        json.dump(report,f,ensure_ascii=False,indent=2)
    print(json.dumps({k:v for k,v in report.items() if k!='tests'}))
    for row in results:
        if not row['passed']:
            print('FAILED',row['test_id'],row['result']['contract_status'],row['result']['reasons'],row['result'].get('parse_errors'))
    return report['failed_count']==0


if __name__ == '__main__':
    if len(sys.argv)>2:
        raise SystemExit('Optional output filename only')
    raise SystemExit(0 if run(sys.argv[1] if len(sys.argv)==2 else 'synthetic_test_results.json') else 1)
