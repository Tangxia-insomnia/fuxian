"""Offline behavioral cases. Synthetic C and generated text are stored verbatim."""
import json
from pathlib import Path
import sys
import time

import offline_boundary
offline_boundary.install()

from semantics import Source, check_polarity, check_mappings, member_collapse_diagnostics, sha
from dependencies import load

HERE = Path(__file__).resolve().parent


def tests():
    polarity, identity = [], []

    def pred(name, code, guard, target, branch, generated, expected, **kwargs):
        source = Source(code, 'f', 'synthetic/' + name)
        result = check_polarity(source, guard, target, branch, generated, **kwargs)
        polarity.append({'case': name, 'input': {'code': code, 'sha256': sha(code), 'guard_line': guard,
                         'target_line': target, 'branch': branch, 'generated': generated, **kwargs},
                         'expected': expected, 'actual': result, 'passed': result['status'] == expected})

    for condition, truth in [('x', 'x != 0'), ('!x', 'x == 0'), ('!!x', 'x != 0'),
                             ('x == 0', 'x == 0'), ('x != 0', 'x != 0'),
                             ('!(((!!x)))', 'x == 0'), ('((x) == (0))', 'x == 0'),
                             ('!!!!((x))', 'x != 0')]:
        for branch in (True, False):
            code = 'void f(int x)\n{\n    if ('+condition+') {\n        use(x);\n    } else {\n        other(x);\n    }\n}\n'
            correct = truth if branch else 'Not(' + truth + ')'
            for label, generated, expected in [('correct', correct, 'PASS'),
                    ('opposite', 'Not('+correct+')', 'REJECT'),
                    ('tautology', 'Or(x == 0, x != 0)', 'REJECT'),
                    ('contradiction', 'And(x == 0, x != 0)', 'REJECT')]:
                pred(condition + '/' + str(branch) + '/' + label, code, 3, 4 if branch else 6,
                     branch, generated, expected)
    early = 'void f(int *p)\n{\n    if (!p)\n        return;\n    use(p);\n}\n'
    pred('early_return_after', early, 3, 5, False, 'p != 0', 'PASS')
    pred('early_return_opposite', early, 3, 5, False, 'p == 0', 'REJECT')
    pred('early_return_wrong_claim', early, 3, 5, True, 'p == 0', 'UNKNOWN')
    pred('inside_return_arm', early, 3, 4, True, 'p == 0', 'PASS')
    pred('intervening_assignment', early.replace('    use(p);','    p = alloc();\n    use(p);'),
         3, 6, False, 'p != 0', 'UNKNOWN')
    pred('conditional_return', early.replace('        return;', '        if (a) return;'),
         3, 5, False, 'p != 0', 'UNKNOWN')
    pred('label_bypass', early.replace('    use(p);', 'label:\n    use(p);'), 3, 6, False, 'p != 0', 'UNKNOWN')
    pred('goto_not_return', early.replace('return;', 'goto done;'), 3, 5, False, 'p != 0', 'UNKNOWN')
    for expression in ['MACRO(x)', 'x && y', 'x > 3', 'x->len', 'x + 1', '(x = 0)']:
        code = 'void f(int x)\n{\n    if ('+expression+')\n        use(x);\n}\n'
        pred('unsupported/' + expression, code, 3, 4, True, 'x != 0', 'UNKNOWN')
    simple = 'void f(int x)\n{\n    if (x)\n        use(x);\n}\n'
    pred('unknown_branch', simple, 3, 4, None, 'x != 0', 'UNKNOWN')
    pred('wrong_sort', simple, 3, 4, True, 'x != 0', 'REJECT', sort='Bool')
    pred('wrong_identity', simple, 3, 4, True, 'x != 0', 'UNKNOWN', expected_identity='wrong-scope')
    pred('unknown_type', simple.replace('int x', 'size_t x'), 3, 4, True, 'x != 0', 'UNKNOWN')
    pred('bool_condition', simple.replace('int x', 'bool x'), 3, 4, True, 'x', 'PASS', sort='Bool')
    pred('bool_negation', simple.replace('int x', 'bool x').replace('if (x)', 'if (!x)'),
         3, 4, True, 'Not(x)', 'PASS', sort='Bool')
    pred('different_symbol', simple, 3, 4, True, 'y != 0', 'UNKNOWN')
    pred('unknown_formula', simple, 3, 4, True, 'Other(x)', 'UNKNOWN')
    pred('source_target_mismatch', simple, 3, 4, True, 'x != 0', 'UNKNOWN', target_text='wrong();')
    pred('unsigned_zero_only', simple.replace('int x', 'unsigned int x'), 3, 4, True, 'x != 0', 'PASS')
    pred('local_match_global_unknown', simple, 3, 4, True, 'x != 0', 'UNKNOWN',
         context_reasons=['state_not_proven'])
    pred('local_reject_not_hidden', simple, 3, 4, True, 'x == 0', 'REJECT',
         context_reasons=['state_not_proven'])
    pred('complex_loop_unknown', simple.replace('    if (x)', '    while (a) {}\n    if (x)'),
         4, 5, True, 'x != 0', 'UNKNOWN')
    pred('assignment_state_unknown', simple.replace('    if (x)', '    x = next();\n    if (x)'),
         4, 5, True, 'x != 0', 'UNKNOWN')

    code = ('struct item { unsigned int len; char *data; };\n'
            'void f(struct item *p)\n{\n    int value;\n    use(p);\n    {\n        int value;\n'
            '        use(value);\n    }\n    use(value);\n}\n'
            'void g(int value)\n{\n    use(value);\n}\n')
    f, g = Source(code, 'f', 'synthetic/types'), Source(code, 'g', 'synthetic/types')
    p, member, data, pointee = [f.resolve(x, 5) for x in ('p', 'p->len', 'p->data', '*p')]
    outer, inner, other = f.resolve('value', 10), f.resolve('value', 8), g.resolve('value', 14)

    def mapping_case(name, bs, expected):
        result = check_mappings(bs)
        identity.append({'case': name, 'input': bs, 'expected': expected, 'actual': result,
                         'passed': result['status'] == expected})

    def b(source, symbol, sort='Int', mode='zero_test', **extra):
        return dict(source=source, symbol=symbol, sort=sort, mode=mode, **extra)

    mapping_case('distinct_pointer_member_and_data', [b(p,'ptr'),b(member,'len'),b(data,'data')], 'PASS')
    mapping_case('collapse_pointer_member', [b(p,'same'), b(member,'same')], 'REJECT')
    mapping_case('collapse_member_data', [b(member,'same'), b(data,'same')], 'REJECT')
    mapping_case('pointee_aggregate_unmodeled', [b(pointee,'object')], 'UNKNOWN')
    mapping_case('same_name_separate_scopes', [b(outer,'outer'), b(inner,'inner')], 'PASS')
    mapping_case('same_name_merged_scopes', [b(outer,'value'), b(inner,'value')], 'REJECT')
    mapping_case('same_name_separate_functions', [b(outer,'f_value'), b(other,'g_value')], 'PASS')
    mapping_case('same_name_merged_functions', [b(outer,'value'), b(other,'value')], 'REJECT')
    mapping_case('unproven_split_or_rename', [b(p,'p'), b(p,'p_ptr')], 'UNKNOWN')
    mapping_case('pointer_Bool_wrong_sort', [b(p,'p','Bool')], 'REJECT')
    mapping_case('integer_Bool_wrong_sort', [b(outer,'value','Bool')], 'REJECT')
    mapping_case('pointer_address_arithmetic', [b(p,'p',mode='arithmetic')], 'UNKNOWN')
    mapping_case('unsigned_overflow_not_modeled', [b(member,'len',mode='arithmetic')], 'UNKNOWN')
    mapping_case('signed_overflow_not_modeled', [b(outer,'value',mode='arithmetic')], 'UNKNOWN')
    for name, flags in [('alias', {'alias_unresolved':True}),('state', {'state_changed':True}),
                        ('cross_function', {'cross_function':True})]:
        mapping_case(name+'_E06', [b(p,'p',**flags)], 'UNKNOWN')
    missing = Source('void f(struct missing *p)\n{\n    use(p);\n}\n', 'f', 'missing/member')
    mapping_case('missing_member_definition', [b(missing.resolve('p->len',3),'len')], 'UNKNOWN')
    unknown = Source('void f(size_t x)\n{\n    use(x);\n}\n', 'f', 'unknown/typedef')
    mapping_case('unknown_typedef_never_default_Int', [b(unknown.resolve('x',3),'x')], 'UNKNOWN')
    ambiguous = Source('void f(int x)\n{\n    int x;\n    use(x);\n}\n','f','ambiguous')
    mapping_case('multiple_candidate_declarations', [b(ambiguous.resolve('x',4),'x')], 'UNKNOWN')
    bo = Source('void f(bool x)\n{\n    use(x);\n}\n','f','bool')
    mapping_case('boolean_sort', [b(bo.resolve('x',3),'x','Bool','boolean_test')], 'PASS')
    mapping_case('boolean_Int_wrong_sort', [b(bo.resolve('x',3),'x')], 'REJECT')
    mapping_case('merged_integer_and_boolean', [b(outer,'shared'),b(bo.resolve('x',3),'shared','Bool','boolean_test')], 'REJECT')
    nested = Source('void f(int cb(int n, struct item *p), struct item *p)\n{\n    use(p);\n}\n',
                    'f','function_pointer_parameter')
    mapping_case('nested_callback_parameters_not_locals', [b(nested.resolve('p',3),'p')], 'PASS')
    adjacent = Source('void f(void)\n{\n    int first;\n    int second;\n    use(second);\n}\n',
                      'f','adjacent_declarations')
    mapping_case('adjacent_declaration_not_skipped', [b(adjacent.resolve('second',5),'second')], 'PASS')

    collapse_source = 'void f(struct item *p, int limit)\n{\n    int n;\n    n = p->len - limit;\n    use(n);\n}\n'
    cs = Source(collapse_source, 'f', 'synthetic/collapse')
    for label, script, expected in [
        ('field_to_pointer', "n=Int('n')\np=Int('p')\nlimit=Int('limit')\ns.add(n == p-limit)", 'REJECT'),
        ('member_symbol_not_guessed', "n=Int('n')\np_len=Int('p_len')\nlimit=Int('limit')\ns.add(n == p_len-limit)", 'UNKNOWN'),
        ('different_shape_not_falsely_bound', "n=Int('n')\np=Int('p')\ns.add(n == p)", 'UNKNOWN')]:
        result = member_collapse_diagnostics(cs, script)
        identity.append({'case': label, 'input':{'code':collapse_source,'script':script},
                         'expected':expected,'actual':result,'passed':result['status']==expected})
    # Existing structural contract remains independent of semantic diagnostics.
    for label, final, expected in [('retained', "x=Int('x')\ns.add(x != 0)", 'PASS'),
                                    ('lost', "x=Int('x')\ns.add(x == 0)", 'FAIL')]:
        result=load('e03').validate_base_delta("x=Int('x')\ns.add(x != 0)", '# empty delta', final)
        identity.append({'case':'unchanged_E03_'+label,'expected':expected,'actual':result,
                         'passed':result['contract_status']==expected})
    malicious="__import__('os').system('E05_SHOULD_NEVER_EXECUTE')"
    result=load('e03').validate_base_delta("x=Int('x')\ns.add(x != 0)", '', malicious)
    identity.append({'case':'generated_call_never_executed','input':malicious,
                     'actual':result,'expected':'UNKNOWN','passed':result['contract_status']=='UNKNOWN'})
    # Evidence hash failures cannot silently bind to a different source.
    try:
        Source(simple,'f','hash_mismatch',expected_sha='0'*64)
        valid=False
    except ValueError as exc:
        valid=str(exc)=='source_hash_mismatch'
    identity.append({'case':'source_hash_mismatch','expected':'refuse','passed':valid})
    return polarity, identity


if __name__ == '__main__':
    start=time.perf_counter(); p,v=tests()
    suffix=sys.argv[1] if len(sys.argv)>1 else ''
    for name,rows in [('polarity_tests',p),('variable_identity_tests',v)]:
        path=HERE/(name+suffix+'.json')
        with path.open('x',encoding='utf-8') as f:
            json.dump({'cases':rows,'passed':sum(x['passed'] for x in rows),'total':len(rows),
                       'seconds':time.perf_counter()-start,'solver_calls':0,'model_calls':0},f,ensure_ascii=False,indent=2)
            f.write('\n')
        print(name, sum(x['passed'] for x in rows),'/',len(rows))
        print('failed:', [x['case'] for x in rows if not x['passed']])
    sys.exit(0 if all(x['passed'] for x in p+v) else 1)
