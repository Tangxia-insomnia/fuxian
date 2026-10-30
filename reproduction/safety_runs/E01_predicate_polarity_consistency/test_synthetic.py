"""Parameterized semantic tests for R01; no benchmark IDs or model calls."""
import copy
import time

from predicate_check import (check_condition, check_merge, normalize_c,
                             symbol_identity, text_sha)
from offline_adapter import explicit_declaration, generated_atoms, inspect_bundle


def fixture(expression='x', branch=True, declaration='int x;', scope='fixture'):
    code = declaration + '\nif (' + expression + ') {\n    sink();\n}\n'
    sha = text_sha(code)
    record = {'condition_id': scope + '/guard', 'expression': expression, 'branch': branch,
              'symbol': {'name': 'x', 'declaration_line': 1, 'type_spelling': 'int',
                         'type_kind': 'integer', 'type_evidence': 'explicit_declaration',
                         'identity': symbol_identity(sha, 1, 'x')},
              'source': {'code': code, 'code_sha256': sha, 'line': 2, 'path': scope + '.c'},
              'context_unsupported': []}
    return record


def atom(record, expression):
    return {'expression': expression, 'source_condition_id': record['condition_id'],
            'symbol_identity': record['symbol']['identity'], 'sort': 'Int',
            'origin': {'kind': 'synthetic_fixture'}}


def run_tests():
    tests = []

    def add(name, expected, actual):
        tests.append({'test': name, 'expected': expected, 'actual': actual,
                      'passed': expected == actual})

    started = time.perf_counter()
    # Truth values independently enumerated: value -1/0/2, then C !, ==0 or !=0.
    cases = [('x', False), ('!x', True), ('!!x', False),
             ('x == 0', True), ('x != 0', False), ('(((x)))', False),
             ('!(!(!(!x)))', False), ('!((x == 0))', False),
             ('((!!x) == 0)', True), ('(!x) != 0', True)]
    for expression, truth_is_zero in cases:
        for branch in (True, False):
            zero = truth_is_zero if branch else not truth_is_zero
            r = fixture(expression, branch)
            expected = 'x == 0' if zero else 'x != 0'
            wrong = 'x != 0' if zero else 'x == 0'
            add(f'normalize/{expression}/{branch}', expected, normalize_c(expression, branch)['normalized'])
            good = check_condition(r, [atom(r, expected)])
            add(f'matching/{expression}/{branch}', ('consistent', True), (good['status'], good['candidate_accepted']))
            bad = check_condition(r, [atom(r, wrong)])
            add(f'opposite/{expression}/{branch}', ('rejected', 'UNKNOWN', 'KEEP'),
                (bad['status'], bad['verdict_on_rejection'], bad['action']))
            negated = 'Not(x != 0)' if zero else 'Not(x == 0)'
            add(f'generated_Not/{expression}/{branch}', 'consistent', check_condition(r, [atom(r, negated)])['status'])

    def unsupported(name, record, atoms=None, reason=None):
        out = check_condition(record, atoms if atoms is not None else [atom(record, 'x != 0')])
        add(name, 'unsupported', out['status'])
        add(name + '/cannot_accept', False, out['candidate_accepted'])
        if reason:
            add(name + '/reason', True, reason in out['reasons'] or
                any(a.get('reason') == reason for a in out['atom_checks']))

    r = fixture()
    other = fixture(declaration='int x; /* different enclosing scope */', scope='other')
    cross = atom(r, 'x != 0'); cross['symbol_identity'] = other['symbol']['identity']
    unsupported('same_name_different_scope', r, [cross], 'generated_source_or_scope_identity_unbound')
    code = 'int x;\nif (x) {\nint x;\nif (x) {\nsink();\n}\n}\n'
    outer, inner = fixture(), fixture(scope='inner_scope')
    for rec, declaration_line, condition_line in ((outer, 1, 2), (inner, 3, 4)):
        rec['source'].update(code=code, code_sha256=text_sha(code), line=condition_line)
        rec['symbol'].update(declaration_line=declaration_line,
                             identity=symbol_identity(text_sha(code), declaration_line, 'x'))
    unsupported('same_file_shadowed_variable', inner, [dict(atom(inner, 'x != 0'),
                symbol_identity=outer['symbol']['identity'])], 'generated_source_or_scope_identity_unbound')
    add('ambiguous_declaration_not_recovered', None, explicit_declaration(code, 'x'))
    r = fixture(); r['symbol']['type_kind'] = 'unknown'
    unsupported('unknown_type', r, reason='unknown_type')
    r = fixture(); r['symbol']['type_spelling'] = 'custom_typedef'
    unsupported('unverified_typedef', r, reason='unknown_type')
    unsupported('macro', fixture('WARN_ON_ONCE(x)'))
    unsupported('compound', fixture('x || y'))
    unsupported('member_alias', fixture('obj->x'))
    unsupported('branch_unknown', fixture(branch=None), reason='unconfirmed_branch_direction')
    unsupported('branch_string_not_boolean', fixture(branch='true'), reason='unconfirmed_branch_direction')
    r = fixture(); r['source']['code_sha256'] = '0' * 64
    unsupported('source_tamper', r, reason='source_hash_mismatch')
    r = fixture(); r['source']['line'] = 3
    unsupported('wrong_guard_location', r, reason='predicate_source_location_mismatch')
    r = fixture(); r['symbol']['identity'] += ':other'
    unsupported('source_scope_identity_unbound', r, reason='source_symbol_identity_unbound')
    for problem in ('alias_not_verified', 'reassignment_not_verified', 'complex_control_flow', 'missing_context'):
        r = fixture(); r['context_unsupported'] = [problem]
        unsupported(problem, r, reason='program_context_outside_e01')
    r = fixture()
    unsupported('no_candidate', r, [], 'no_bound_generated_atom')
    bad = atom(r, 'x != 0'); bad['sort'] = 'Bool'
    unsupported('wrong_z3_sort', r, [bad], 'generated_sort_outside_known_scalar_abstraction')
    bad = atom(r, 'y != 0')
    unsupported('generated_different_variable', r, [bad], 'generated_variable_identity_mismatch')
    for text in ('x > 0', 'x == 1', 'Or(x == 0, y == 0)', '__import__("os").system("invalid")'):
        unsupported('unsupported_generated/' + text, r, [atom(r, text)])

    pointer = fixture('!x', declaration='struct node *x;')
    pointer['symbol'].update(type_kind='pointer', type_spelling='struct node *')
    add('known_pointer_zero_test', 'consistent', check_condition(pointer, [atom(pointer, 'x == 0')])['status'])
    r = fixture(); a = atom(r, 'x != 0')
    merged = check_merge([r], [a, copy.deepcopy(a)])
    add('duplicate_assertions_kept', (2, 1, 0),
        (merged['input_atom_count'], merged['repeated_atom_count'], merged['atoms_removed']))
    add('duplicate_source_id_ambiguous', 'unsupported', check_merge([r, r], [a])['status'])
    unbound = dict(a, source_condition_id='unbound')
    add('orphan_atom_blocks_merge', 'unsupported', check_merge([r], [a, unbound])['status'])
    # Contradictory but correctly translated source guards: never delete either.
    code = 'int x;\nif (x) {\nif (!x) {\n sink();\n}\n}\n'
    r1, r2 = fixture(), fixture('!x', scope='inner')
    for rec, line in ((r1, 2), (r2, 3)):
        rec['source'].update(code=code, code_sha256=text_sha(code), line=line)
        rec['symbol']['identity'] = symbol_identity(text_sha(code), 1, 'x')
    merged = check_merge([r1, r2], [atom(r1, 'x != 0'), atom(r2, 'x == 0')])
    add('genuine_source_contradiction_not_rewritten', ('consistent', 2, 0),
        (merged['status'], merged['input_atom_count'], merged['atoms_removed']))
    merged = check_merge([r1], [atom(r1, 'x != 0'), atom(r1, 'x == 0')])
    add('bad_merge_rejected_without_deletion', ('rejected', 2, 0),
        (merged['status'], merged['input_atom_count'], merged['atoms_removed']))
    for script, reason in [
        ("x=Int('other'); s.add(x != 0)", 'generated_symbol_name_or_sort_identity_unbound'),
        ("x=Int('x'); x=1; s.add(x != 0)", 'generated_symbol_name_or_sort_identity_unbound'),
        ("x=Int('x')\ndef f(x):\n s.add(x != 0)", 'generated_symbol_name_or_sort_identity_unbound'),
        ("def f():\n x=Int('x')\n s.add(x != 0)\ndef g():\n x=Int('x')\n s.add(x == 0)", 'generated_symbol_name_or_sort_identity_unbound')]:
        values, _ = generated_atoms({'source': script, 'origin': {}, 'frame_index': 0})
        add('generated_binding/' + script, True, all(a.get('unsupported_reason') == reason for a in values) and bool(values))
    # A null bug hypothesis must never be attributed to an early-exit predicate.
    b = {'context': {'frames': [{'function': 'f', 'code': 'int x;\nif (!x)\n return;\nsink(x);',
          'var_name': 'x', 'extracted': {'target_conditions': [], 'early_jump_constraints': [{'condition': ['if (!x)']}]}}]},
         'recorded_answer': {'response': ["step 1 z3 script: x=Int('x'); s.add(x == 0)"]}}
    result = inspect_bundle(b)
    add('bug_hypothesis_not_early_exit_translation', 0, result['conflicting_condition_count'])
    add('unbound_early_exit_unknown', 'unsupported', result['status'])
    elapsed = time.perf_counter() - started
    return {'suite': 'R01 parameterized synthetic semantics', 'passed': all(t['passed'] for t in tests),
            'test_count': len(tests), 'pass_count': sum(t['passed'] for t in tests),
            'fail_count': sum(not t['passed'] for t in tests), 'seconds': elapsed, 'tests': tests,
            'new_model_calls': 0, 'new_api_cost_cny': 0,
            'limits': 'Fixtures have explicit local bindings. Passing does not prove arbitrary C paths.'}
