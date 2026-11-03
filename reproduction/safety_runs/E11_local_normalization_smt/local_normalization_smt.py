"""E11 only: versioned unsigned-long normalization and zero-denominator queries.

Source admission uses exact saved hashes, not a general C-to-SMT translator.
The core query is the projection onto the divisor, so it does not encode the
numerator, quotient, unsigned-int cast, or min macro's result. It never assumes
the very nonzero-denominator property being tested.
"""
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import time

import z3

ROOT = Path(__file__).resolve().parent
REPRO = ROOT.parents[1]
DATASET = REPRO / 'upstream/benchmark/DBZ/all_cwe369.json'
DATASET_SHA = '0275cd83a4c1cf617f0049d6dbb191dcc3d232e5545ca0139bab3aa45f747fd8'
BODY_SHA = '604a27c78dd3bd48933665f8253480eef56107e88e7e4039701dd4f397615ebb'
CONTRACT_SHA = '729bbc9788ad8943b0075a7ee7c08a65f7db2b7b01aa691f3d296f806ce0441b'
COMMIT = '9c5a72fbc90d829ffb761da64a73c23cd4e0503f'
SAMPLE_ID = 'DBZ/all_cwe369.json:row=2:index=2'
SOURCE_PATH = 'drivers/gpu/drm/omapdrm/dss/pll.c'
SOLVER_CHECKS = 0


class InputMismatch(ValueError):
    """UNKNOWN and stop before solving: input identity differs."""


class UnsupportedSemantics(ValueError):
    """REJECT this prototype input; no general C semantics are inferred."""


class SemanticMismatch(RuntimeError):
    """Stop: an actual solver result disagrees with the independent reference."""


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_json(name):
    return json.loads((ROOT / name).read_text('utf-8'))


def write_new(name, document):
    with (ROOT / name).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(document, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def check_sha(data, expected, description):
    if sha(data) != expected:
        raise InputMismatch(description + ' SHA-256 differs; stop')


def verify_dataset_bytes(data):
    check_sha(data, DATASET_SHA, 'original dataset')
    row = json.loads(data)[2]
    if row['index'] != 2 or len(row['function_call']) != 1:
        raise InputMismatch('original sample index/body identity differs')
    check_sha(row['function_call'][0].encode('utf-8'), BODY_SHA, 'function body')
    return row


def load_inputs():
    row = verify_dataset_bytes(DATASET.read_bytes())
    body = row['function_call'][0]
    check_sha((ROOT / 'original_function.c').read_bytes(), BODY_SHA, 'saved body')
    raw_contract = (ROOT / 'semantic_contract.json').read_bytes()
    check_sha(raw_contract, CONTRACT_SHA, 'frozen finite contract')
    contract = json.loads(raw_contract)
    if (contract['c_type'] != 'unsigned long'
            or contract['unsigned_long_widths'] != [32, 64]
            or contract['sample_id'] != SAMPLE_ID
            or contract['original_label'] != row['result']
            or contract['definedness_asserted_in_fault_query'] is not False
            or contract['filter_authority'] is not False
            or contract['original_alert_decision'] is not None):
        raise InputMismatch('contract/label/boundary mismatch')
    raw_manifest = (ROOT / 'source_manifest.json').read_bytes()
    check_sha(raw_manifest, contract['source_manifest_sha256'], 'source manifest')
    manifest = json.loads(raw_manifest)
    check_sha((ROOT / 'source_evidence.json').read_bytes(),
              contract['source_evidence_sha256'], 'source evidence')
    check_sha((ROOT / 'input_verification.json').read_bytes(),
              manifest['input_verification_sha256'], 'original record evidence')
    for record in manifest['files']:
        if record['commit'] != COMMIT:
            raise InputMismatch('source file commit differs')
        check_sha((ROOT / record['local_path']).read_bytes(), record['sha256'],
                  record['path'])
    matches = [r for r in manifest['files'] if r['path'] == SOURCE_PATH]
    if len(matches) != 1:
        raise InputMismatch('target source missing or ambiguous')
    source = (ROOT / matches[0]['local_path']).read_bytes().decode('utf-8')
    extracted = ''.join(source.splitlines(keepends=True)[175:199]).removesuffix('\n')
    if extracted != body:
        raise InputMismatch('upstream function differs from dataset')
    tag = read_json('upstream_tag_verification.json')
    if tag['status'] != 'MATCH' or tag['refs'].get('refs/tags/v6.9.6^{}') != COMMIT:
        raise InputMismatch('upstream tag association differs')
    return row, contract


def width_check(width, c_type='unsigned long'):
    if type(width) is not int or width not in (32, 64) or c_type != 'unsigned long':
        raise UnsupportedSemantics('only explicit unsigned-long 32/64 contracts')
    return (1 << width) - 1


def reference_normalize(value, width, c_type='unsigned long'):
    """Independent host-integer C scalar reference, without a solver or wrapping."""
    maximum = width_check(width, c_type)
    if type(value) is not int or not 0 <= value <= maximum:
        raise UnsupportedSemantics('value is not an unsigned long in this contract')
    return 1 if value == 0 else value


def normalized_term(value, width):
    width_check(width)
    if not z3.is_bv(value) or value.size() != width:
        raise UnsupportedSemantics('normalization needs a matching-width bit vector')
    return z3.If(value == z3.BitVecVal(0, width), z3.BitVecVal(1, width), value)


def encode(width, c_type='unsigned long'):
    width_check(width, c_type)
    prefix = 'e11_row2_out_min_'
    pre = z3.BitVec(prefix + 'v0_u' + str(width), width)
    post = z3.BitVec(prefix + 'v1_u' + str(width), width)
    use = z3.BitVec(prefix + 'use189_u' + str(width), width)
    term = normalized_term(pre, width)
    return {'width': width, 'pre': pre, 'post': post, 'use': use, 'term': term,
            'relations': (post == term, use == post),
            'division_definedness': use != z3.BitVecVal(0, width)}


def core_constraints(encoding, experiment):
    width = encoding['width']
    zero = z3.BitVecVal(0, width)
    if experiment == 'A':
        # Counterfactual: the use is the original value, without normalization.
        return (encoding['pre'] == zero,)
    if experiment == 'B':
        return (*encoding['relations'], encoding['use'] == zero)
    raise UnsupportedSemantics('unknown E11 core experiment')


def solve_saved(query_id, encoding, constraints, include_post):
    """Exactly one check per saved query; tests never recheck these formulas."""
    global SOLVER_CHECKS
    solver = z3.SolverFor('QF_BV')
    solver.set(timeout=30000)
    solver.add(*constraints)
    smtlib = '(set-logic QF_BV)\n(set-option :timeout 30000)\n' + solver.to_smt2()
    filename = 'queries/' + query_id + '.smt2'
    with (ROOT / filename).open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(smtlib)
    started = time.perf_counter()
    SOLVER_CHECKS += 1
    answer = solver.check()
    elapsed = time.perf_counter() - started
    status = {'sat': 'SAT', 'unsat': 'UNSAT', 'unknown': 'UNKNOWN'}[str(answer)]
    result = {'query_id': query_id, 'width_bits': encoding['width'], 'status': status,
              'elapsed_seconds': elapsed, 'SMT_logic': 'QF_BV', 'timeout_ms': 30000,
              'smtlib_file': filename, 'smtlib_sha256': sha(smtlib.encode('utf-8')),
              'exact_smtlib': smtlib, 'model': None, 'raw_model': None,
              'unsat_proof': None, 'reason_unknown': None}
    if status == 'SAT':
        model = solver.model()
        keys = ('pre', 'post', 'use') if include_post else ('pre',)
        result['model'] = {key: model.eval(encoding[key], model_completion=True).as_long()
                           for key in keys}
        result['raw_model'] = model.sexpr()
    elif status == 'UNSAT':
        result['unsat_proof'] = {
            'solver_reported_unsat': True, 'certificate_generated': False,
            'independently_checked_solver_proof': False,
            'note': 'separate elementary case analysis checks this scalar property; it is not a checked Z3 proof'}
    else:
        result['reason_unknown'] = solver.reason_unknown()
    return result


def main():
    if (ROOT / 'experiment_results.json').exists() or (ROOT / 'queries').exists():
        raise FileExistsError('prior E11 results/queries exist; do not overwrite')
    row, contract = load_inputs()  # All identity checks precede any solver check.
    (ROOT / 'queries').mkdir()
    core, boundary = [], []
    for width in (32, 64):
        encoding = encode(width)
        for experiment in ('A', 'B'):
            result = solve_saved('core_' + experiment + '_' + str(width), encoding,
                                 core_constraints(encoding, experiment), experiment == 'B')
            result['experiment'] = experiment
            result['denominator_nonzero_asserted'] = False
            result['expected_status'] = 'SAT' if experiment == 'A' else 'UNSAT'
            if result['status'] != result['expected_status']:
                result['independent_verification'] = {'status': 'NOT_VERIFIED'}
            elif experiment == 'A':
                value = result['model']['pre']
                if value != 0 or reference_normalize(value, width) != 1:
                    raise SemanticMismatch('unnormalized zero witness disagrees')
                result['independent_verification'] = {
                    'status': 'MATCH', 'unnormalized_divisor': value,
                    'normalized_reference': 1, 'z3_used_in_reference': False}
            else:
                result['independent_verification'] = {
                    'status': 'MATCH_BY_EXHAUSTIVE_SYMBOLIC_CASE_SPLIT',
                    'cases': ['v0=0 => v1=1, use=1', 'v0!=0 => v1=v0!=0, use!=0'],
                    'all_unsigned_values_covered': True, 'z3_used_in_reference': False,
                    'machine_checked_certificate': False}
            core.append(result)
        for label, value in [('zero', 0), ('one', 1), ('two', 2),
                             ('ULONG_MAX', (1 << width) - 1)]:
            result = solve_saved('boundary_' + str(width) + '_' + label, encoding,
                                 (*encoding['relations'],
                                  encoding['pre'] == z3.BitVecVal(value, width)), True)
            reference = reference_normalize(value, width)
            result.update({'input': value, 'boundary': label,
                           'independent_reference': reference, 'z3_used_in_reference': False})
            result['independent_match'] = (
                result['status'] == 'SAT'
                and result['model'] == {'pre': value, 'post': reference, 'use': reference})
            boundary.append(result)
    success = (all(q['status'] == q['expected_status'] for q in core)
               and all(q['independent_match'] for q in boundary))
    document = {
        'sample_id': SAMPLE_ID, 'original_index': row['index'], 'original_label': row['result'],
        'dataset_sha256': DATASET_SHA, 'function_body_sha256': BODY_SHA,
        'source_commit': COMMIT, 'contract_sha256': CONTRACT_SHA,
        'implementation_sha256': sha(Path(__file__).read_bytes()),
        'solver': {'name': 'Z3', 'version': z3.get_version_string(),
                   'package_version': importlib.metadata.version('z3-solver'),
                   'logic': 'QF_BV'},
        'recorded_at_UTC': datetime.now(timezone.utc).isoformat(),
        'core_queries': core, 'boundary_queries': boundary,
        'solver_check_count': SOLVER_CHECKS, 'core_check_count': 4,
        'boundary_check_count': 8, 'semantic_experiment_checks_passed': success,
        'original_ABI': 'UNKNOWN; 32/64 unsigned-long contracts are explicit',
        'property_scope': contract['certified_scope'],
        'unsigned_division_quotient_encoded': False,
        'solver_scope': 'version equations and zero-divisor query only; no whole C semantics',
        'prior_constraints_imported': False,
        'calls': {'LLM': 0, 'Harness': 0, 'original_analyzer': 0, 'old_regression': 0},
        'original_alert_decision': None, 'filter_authority': False,
        'full_program_semantics': 'UNKNOWN',
    }
    write_new('experiment_results.json', document)
    print(json.dumps({'core': [(r['query_id'], r['status']) for r in core],
                      'boundary_models_match': sum(r['independent_match'] for r in boundary),
                      'solver_checks': SOLVER_CHECKS, 'checks_passed': success}))
    if not success:
        raise SemanticMismatch('unexpected core result or boundary mismatch; stop')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        failure = {'status': 'UNKNOWN', 'error_type': type(error).__name__,
                   'error': str(error), 'solver_checks_before_failure': SOLVER_CHECKS,
                   'original_alert_decision': None, 'filter_authority': False,
                   'full_program_semantics': 'UNKNOWN'}
        if not (ROOT / 'execution_failure.json').exists():
            write_new('execution_failure.json', failure)
        raise
