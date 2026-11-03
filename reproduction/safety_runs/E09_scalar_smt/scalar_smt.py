"""E09: source-pinned, two-width scalar experiment; no general C compiler.

Only the reviewed seven-line function grammar is admitted. Z3 expressions are
partial C values paired with explicit definedness. Fault queries deliberately
do not assume the outer division's nonzero-denominator precondition.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
import importlib.metadata
import json
from pathlib import Path
import re
import time

import z3

ROOT = Path(__file__).resolve().parent
REPRO = ROOT.parents[1]
DATASET = REPRO / 'upstream/benchmark/DBZ/all_cwe369.json'
AUDIT = REPRO / 'safety_runs/SMT_dataset_audit/candidate_samples.json'
DATASET_SHA256 = '0275cd83a4c1cf617f0049d6dbb191dcc3d232e5545ca0139bab3aa45f747fd8'
BODY_SHA256 = '4ad8431edd6f874dcfb6b1c47d3d83607e7c3ce11f9521e45496eff794a5f9f6'
AUDIT_SHA256 = '2788dff05a5f611965fb9745bb62379bc76683639a5dedacc643b00fcf02aef0'
AUDIT_SAMPLE_ID = 'benchmark/DBZ/all_cwe369.json:row=4:index=4'
REQUEST_SAMPLE_ID = 'DBZ/all_cwe369.json:row=4:index=4'
CONTRACT_VERSION = 'e09-stb0899-signed-long-v1'


class InputMismatch(ValueError):
    """Stop: original identity or source bytes differ from the audited input."""


class UnsupportedSemantics(ValueError):
    """Reject this finite prototype's unsupported input, without solving it."""


class CUndefinedBehavior(ValueError):
    pass


class SemanticMismatch(RuntimeError):
    """Stop immediately: independent arithmetic disagrees with SMT."""


def sha(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text('utf-8-sig'))


def write_new(path, doc):
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(doc, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def width_check(width, c_type='signed long', division='toward_zero'):
    if type(width) is not int or width not in (32, 64):
        raise UnsupportedSemantics('only explicit signed-long 32/64 contracts')
    if c_type != 'signed long' or division != 'toward_zero':
        raise UnsupportedSemantics('unsupported C type or division semantics')
    return -(1 << (width - 1)), (1 << (width - 1)) - 1


@dataclass(frozen=True)
class ScalarFragment:
    function: str
    variable: str
    guard_constant: int
    numerator: int
    inner_divisor: int
    else_value: int


# Full-source grammar, not a text search for an arbitrary matching expression.
# No macros, comments, typedefs, casts, calls, other operators or extra statements.
FRAGMENT = re.compile(
    r'\s*static\s+long\s+(?P<fn>[A-Za-z_]\w*)\s*\('
    r'\s*long\s+(?P<var>[A-Za-z_]\w*)\s*\)\s*\{\s*'
    r'if\s*\(\s*(?P=var)\s*>\s*(?P<guard>[0-9]+)\s*\)\s*'
    r'return\s*\(\s*(?P<num>[0-9]+)\s*/\s*\('
    r'\s*(?P=var)\s*/\s*(?P<den>[0-9]+)\s*\)\s*\)\s*;\s*'
    r'else\s+return\s+(?P<else>[0-9]+)\s*;\s*\}\s*'
)


def parse_fragment(body: str) -> ScalarFragment:
    if not isinstance(body, str):
        raise UnsupportedSemantics('source must be text')
    match = FRAGMENT.fullmatch(body)
    if not match:
        raise UnsupportedSemantics('outside the reviewed full-source grammar')
    fields = match.groupdict()
    parsed = ScalarFragment(fields['fn'], fields['var'], int(fields['guard']),
                            int(fields['num']), int(fields['den']), int(fields['else']))
    if parsed != ScalarFragment('stb0899_calc_derot_time', 'srate', 0, 100000, 1000, 0):
        raise UnsupportedSemantics('only the audited function/constants are supported')
    return parsed


def load_inputs(dataset_path=DATASET, audit_path=AUDIT):
    """Hash gates precede parsing/encoding/any solver.check call."""
    audit_bytes = Path(audit_path).read_bytes()
    if sha(audit_bytes) != AUDIT_SHA256:
        raise InputMismatch('audit record SHA256 mismatch; stop')
    audit = json.loads(audit_bytes)
    candidates = [c for c in audit['candidates'] if c['sample_id'] == AUDIT_SAMPLE_ID]
    if len(candidates) != 1:
        raise InputMismatch('audit sample identity missing or ambiguous; stop')
    candidate = candidates[0]
    if (candidate['dataset_sha256'] != DATASET_SHA256 or
            candidate['function_body_sha256'] != BODY_SHA256):
        raise InputMismatch('audited hashes conflict with pinned hashes; stop')
    blob = Path(dataset_path).read_bytes()
    if sha(blob) != candidate['dataset_sha256']:
        raise InputMismatch('dataset SHA256 mismatch; stop')
    row = json.loads(blob)[4]
    if row['index'] != candidate['original_index'] or row['result'] != candidate['original_label']:
        raise InputMismatch('index or label mismatch; stop')
    if len(row['function_call']) != 1:
        raise InputMismatch('source selection is not unique; stop')
    body = row['function_call'][0]
    if sha(body.encode('utf-8')) != candidate['function_body_sha256']:
        raise InputMismatch('function body SHA256 mismatch; stop')
    parsed = parse_fragment(body)
    source = {
        'request_sample_id': REQUEST_SAMPLE_ID,
        'sample_id': candidate['sample_id'],
        'sample_id_origin': candidate['sample_id_origin'],
        'original_dataset_sample_id': row.get('sample_id'),
        'row_zero_based': 4, 'original_index': row['index'], 'original_label': row['result'],
        'dataset_file': str(Path(dataset_path).resolve()), 'dataset_sha256': sha(blob),
        'record_pointer': '/4', 'audit_file': str(Path(audit_path).resolve()),
        'audit_sha256': sha(audit_bytes), 'audit_record_pointer': '/candidates/0',
        'function_body_pointer': '/4/function_call/0', 'function_body': body,
        'function_body_sha256': sha(body.encode()),
        'source_location_original_metadata': row['location'],
        'original_record': row, 'parsed_fragment': asdict(parsed),
        'identity_verified_scope': 'audited saved bytes only; original TU/build not certified',
        'label_used_for_constraints': False,
    }
    return source, parsed


def load_contract():
    contract = read_json(ROOT / 'semantic_contract.json')
    if (contract.get('contract_version') != CONTRACT_VERSION or
            contract.get('source_body_sha256') != BODY_SHA256 or
            contract.get('abi_widths') != [32, 64] or
            contract.get('c_type') != 'signed long' or
            contract.get('integer_division') != 'toward_zero'):
        raise UnsupportedSemantics('contract changed or unsupported')
    return contract


def c_signed_divide(numerator: int, denominator: int, width: int) -> int:
    """Independent, exact host-integer reference: no Z3 and no float division."""
    lo, hi = width_check(width)
    if type(numerator) is not int or type(denominator) is not int:
        raise UnsupportedSemantics('reference operands must be integers')
    if not lo <= numerator <= hi or not lo <= denominator <= hi:
        raise UnsupportedSemantics('operand outside signed-long contract')
    if denominator == 0:
        raise CUndefinedBehavior('division by zero')
    if numerator == lo and denominator == -1:
        raise CUndefinedBehavior('signed division overflow')
    magnitude = abs(numerator) // abs(denominator)
    return -magnitude if (numerator < 0) != (denominator < 0) else magnitude


def signed_division(numerator, denominator, width):
    """SMT bvsdiv plus C definedness; do not consume the term when undefined."""
    lo, _ = width_check(width)
    if (not z3.is_bv(numerator) or not z3.is_bv(denominator) or
            numerator.size() != width or denominator.size() != width):
        raise UnsupportedSemantics('mismatched bit-vector types/widths')
    zero = z3.BitVecVal(0, width)
    defined = z3.And(denominator != zero,
                     z3.Not(z3.And(numerator == z3.BitVecVal(lo, width),
                                   denominator == z3.BitVecVal(-1, width))))
    # BitVecRef / is signed division (SMT-LIB bvsdiv), not UDiv or Int division.
    return numerator / denominator, defined


def encode_fragment(parsed, width, *, c_type='signed long', division='toward_zero'):
    width_check(width, c_type, division)
    if parsed != ScalarFragment('stb0899_calc_derot_time', 'srate', 0, 100000, 1000, 0):
        raise UnsupportedSemantics('unreviewed fragment')
    x = z3.BitVec('e09_srate_signed_long_' + str(width), width)
    value = lambda n: z3.BitVecVal(n, width)
    guard = x > value(parsed.guard_constant)  # bvslt, signed comparison
    inner, inner_defined = signed_division(x, value(parsed.inner_divisor), width)
    outer, outer_defined = signed_division(value(parsed.numerator), inner, width)
    # A total SMT term is not an unconditional C return value.
    return {'width': width, 'srate': x, 'guard': guard, 'inner': inner,
            'inner_defined': inner_defined, 'outer': outer, 'outer_defined': outer_defined,
            'defined_on_selected_path': z3.Or(z3.Not(guard), z3.And(inner_defined, outer_defined)),
            'return_term_valid_only_when_defined': z3.If(guard, outer, value(parsed.else_value))}


def reference_execution(srate, width, parsed):
    lo, hi = width_check(width)
    if type(srate) is not int or not lo <= srate <= hi:
        raise UnsupportedSemantics('srate is not a representable signed long')
    if srate <= parsed.guard_constant:
        return {'srate': srate, 'division_branch_entered': False, 'inner': None,
                'outer_evaluated': False, 'outer_denominator_zero': False,
                'status': 'DEFINED', 'return_value': parsed.else_value}
    inner = c_signed_divide(srate, parsed.inner_divisor, width)
    if inner == 0:
        return {'srate': srate, 'division_branch_entered': True, 'inner': inner,
                'outer_evaluated': False, 'outer_denominator_zero': True,
                'status': 'UNDEFINED_DIVISION_BY_ZERO', 'return_value': None}
    outer = c_signed_divide(parsed.numerator, inner, width)
    return {'srate': srate, 'division_branch_entered': True, 'inner': inner,
            'outer_evaluated': True, 'outer_denominator_zero': False,
            'status': 'DEFINED', 'return_value': outer}


def verify_sat_witness(srate, model_inner, width, experiment, parsed):
    ref = reference_execution(srate, width, parsed)
    conditions = [ref['division_branch_entered'], ref['inner'] == model_inner,
                  ref['outer_denominator_zero']]
    if experiment == 'B':
        conditions.append(srate >= 1000)
    elif experiment != 'A':
        raise UnsupportedSemantics('unknown experiment')
    if not all(conditions):
        raise SemanticMismatch('SAT witness conflicts with independent C arithmetic')
    return {'status': 'MATCH', 'method': 'Python arbitrary-precision abs // abs and sign',
            'z3_used_in_reference': False, 'all_query_conditions_checked': True,
            'reference_execution': ref}


def run_query(parsed, width, experiment, timeout_ms=30000):
    if experiment not in ('A', 'B') or type(timeout_ms) is not int or timeout_ms <= 0:
        raise UnsupportedSemantics('unknown query or invalid timeout')
    enc = encode_fragment(parsed, width)
    zero = z3.BitVecVal(0, width)
    solver = z3.SolverFor('QF_BV')
    solver.set(timeout=timeout_ms)
    assumptions = [{'expression': 'srate > 0', 'origin': 'saved function line 3',
                    'source_field': '/4/function_call/0', 'experimental': False}]
    solver.add(enc['guard'], enc['inner_defined'], enc['inner'] == zero)
    if experiment == 'B':
        solver.add(enc['srate'] >= z3.BitVecVal(1000, width))
        assumptions.append({'expression': 'srate >= 1000',
                            'origin': 'human-added experimental caller-range assumption',
                            'experimental': True, 'proven_in_original_project': False})
    formula = solver.to_smt2()  # Preserve exactly the query sent to this solver.
    start = time.perf_counter()
    answer = solver.check()
    elapsed = time.perf_counter() - start
    status = {'sat': 'SAT', 'unsat': 'UNSAT', 'unknown': 'UNKNOWN'}[str(answer)]
    doc = {'experiment': experiment, 'width_bits': width, 'status': status,
           'abi_is_experimental_assumption': True, 'assumptions': assumptions,
           'variable': {'name': str(enc['srate']), 'c_type': 'signed long', 'width': width,
                        'range': list(width_check(width)), 'identity_scope': 'one pinned local parameter'},
           'fault_query': 'branch_entered AND inner_division_defined AND (srate / 1000 == 0)',
           'formula_smt2': formula, 'inner_expression_smt2': enc['inner'].sexpr(),
           'outer_execution_precondition_smt2': enc['outer_defined'].sexpr(),
           'outer_definedness_asserted_in_fault_query': False,
           'outer_undefined_term_used_as_result': False, 'timeout_ms': timeout_ms,
           'check_seconds': elapsed, 'model': None, 'independent_model_check': None,
           'unsat_proof': {'certificate_generated': False, 'independently_checked_certificate': False,
                           'status': 'NOT_APPLICABLE'}, 'filter_authority': False,
           'original_alert_decision': None, 'full_program_semantics': 'UNKNOWN'}
    if status == 'SAT':
        model = solver.model()
        value = model.eval(enc['srate'], model_completion=False).as_signed_long()
        inner = model.eval(enc['inner'], model_completion=False).as_signed_long()
        doc['model'] = {'srate_signed': value, 'inner_signed': inner, 'smt_model': model.sexpr()}
        doc['independent_model_check'] = verify_sat_witness(value, inner, width, experiment, parsed)
    elif status == 'UNSAT':
        doc['unsat_proof']['status'] = 'SOLVER_REPORTED_UNSAT_NO_PROOF_CERTIFICATE'
        doc['unsat_proof']['explanation'] = (
            'Finite QF_BV check by Z3. No proof object requested or independently verified. '
            'For B, positive signed srate >= 1000 entails trunc(srate/1000) >= 1; '
            'this is a local arithmetic argument, not a caller precondition proof.')
    else:
        doc['reason_unknown'] = solver.reason_unknown()
    return doc


def run_experiments():
    source, parsed = load_inputs()  # Stop before any query on mismatch.
    contract = load_contract()
    runs = []
    for width in contract['abi_widths']:
        for experiment in ('A', 'B'):
            # A SemanticMismatch aborts the run; no repair/retry is hidden here.
            runs.append(run_query(parsed, width, experiment))
    statuses = {(r['width_bits'], r['experiment']): r['status'] for r in runs}
    confirmed = all(statuses[(w, 'A')] == 'SAT' and statuses[(w, 'B')] == 'UNSAT'
                    for w in (32, 64))
    return {'experiment_version': CONTRACT_VERSION, 'source': source,
            'semantic_contract': contract,
            'semantic_contract_sha256': sha((ROOT / 'semantic_contract.json').read_bytes()),
            'implementation_sha256': sha(Path(__file__).read_bytes()),
            'solver': {'name': 'Z3', 'runtime_version': z3.get_full_version(),
                       'package_version': importlib.metadata.version('z3-solver'),
                       'logic': 'QF_BV', 'signed_division_operator': 'bvsdiv'},
            'runs': runs, 'core_solver_checks': len(runs),
            'both_contracts_agree': all(statuses[(32, e)] == statuses[(64, e)] for e in ('A', 'B')),
            'expected_local_results_observed': confirmed,
            'research_status': 'LOCAL_SCALAR_CONFIRMED' if confirmed else 'INCOMPLETE',
            'full_program_semantics': 'UNKNOWN', 'filter_authority': False,
            'original_alert_decision': None, 'original_label_preserved': True,
            'limitations': ['Original ABI/build/TU and caller reachability are not authenticated.',
                            'B caller range is an experimental assumption, not extracted evidence.',
                            'Only the exact reviewed source grammar is admitted.',
                            'No pointers, arrays, memory, interprocedural paths, or R01-R05 integration.'],
            'LLM_calls': 0, 'Harness_runs': 0, 'old_regression_runs': 0,
            'original_analyzer_runs': 0, 'R05_builder_validator_runs': 0,
            'Git_commits': 0, 'Git_pushes': 0}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=ROOT / 'experiment_results.json')
    args = parser.parse_args()
    if args.output.resolve().parent != ROOT:
        raise ValueError('E09 output must remain in its independent directory')
    if args.output.exists():
        raise FileExistsError('preserve existing experiment results; do not overwrite')
    doc = run_experiments()
    write_new(args.output, doc)
    print(json.dumps({'research_status': doc['research_status'],
                      'runs': [(r['width_bits'], r['experiment'], r['status']) for r in doc['runs']],
                      'filter_authority': False}))


if __name__ == '__main__':
    main()
