"""Independent finite C-prefix reference for E12; Python standard library only.

This manually reviewed interpreter covers exactly the two source statements.
It does not import Z3, the SMT implementation, labels, or historical outcomes.
It never models a strcmp return value, address, string object, or memory read.
"""
from itertools import product


def _booleans(A, B):
    if type(A) is not bool or type(B) is not bool:
        raise ValueError('only two actual Boolean NULL statuses are supported')


def execute_prefix(A, B):
    _booleans(A, B)
    # C == yields int 0/1. C ^ evaluates these integers, not pointer bits.
    s1_comparison_int = 1 if A else 0
    s2_comparison_int = 1 if B else 0
    first_condition_int = s1_comparison_int ^ s2_comparison_int
    trace = {
        'A': A, 'B': B, 'C_first_condition_int': first_condition_int,
        'early_return_taken': False, 'second_left_evaluated': False,
        'second_left_value': None, 'strcmp_evaluated': False,
        'strcmp_result_used_for_reachability': False,
    }
    if first_condition_int != 0:
        trace['early_return_taken'] = True
        return trace
    trace['second_left_evaluated'] = True
    trace['second_left_value'] = A
    if A:
        # C || stops after its true left operand; strcmp is never evaluated.
        return trace
    trace['strcmp_evaluated'] = True
    return trace


def query_value(query_id, A, B):
    trace = execute_prefix(A, B)
    if query_id == 'Q1':
        return trace['strcmp_evaluated']
    if query_id == 'Q2':
        return trace['strcmp_evaluated'] and B
    if query_id == 'Q3':
        # Counterfactual removal of the first if/return, retaining C ||.
        if A:
            return False
        return B
    if query_id == 'Q4':
        # Deliberately invalid model: only the first guard, no OR boundary.
        return not trace['early_return_taken'] and B
    raise ValueError('unsupported query; this reference is E12-specific')


def enumerate_domain():
    traces = []
    satisfying = {query_id: [] for query_id in ('Q1', 'Q2', 'Q3', 'Q4')}
    for A, B in product((False, True), repeat=2):
        traces.append(execute_prefix(A, B))
        for query_id in satisfying:
            if query_value(query_id, A, B):
                satisfying[query_id].append({'A': A, 'B': B})
    return {
        'domain_size': 4, 'domain_completely_enumerated': True,
        'traces': traces, 'satisfying_assignments': satisfying,
        'finite_domain_status': {name: 'SAT' if models else 'UNSAT'
                                 for name, models in satisfying.items()},
        'method': 'Python integer 0/1 XOR and sequential early-return/short-circuit interpretation',
        'Z3_imported_or_used': False, 'solver_checks': 0,
        'scope': 'complete for two Boolean NULL statuses, not full C program semantics',
    }
