"""E12 fixed-source NULL-argument reachability; exactly four Boolean queries.

No source download, general C parser, pointer/heap model or alert adjudication.
Every input gate is completed before constructing any solver. Result writers
create files exclusively; existing source, preflight and results are read-only.
"""
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys
import time

import z3
import independent_reference as reference

ROOT = Path(__file__).resolve().parent
REPRO = ROOT.parents[1]
PREFLIGHT = ROOT / 'preflight'
DATASET = REPRO / 'upstream/benchmark/NPD/cppcheck/cppcheck_openssl_nullpointer.json'
SAMPLE_ID = 'NPD/cppcheck/cppcheck_openssl_nullpointer.json:row=3'
DATASET_SHA = '5a7e89ffb017ece94403f862a5cc8d33f478fc92360d4e957648d66aeee12d29'
BODY_SHA = '8b2a929c68a079ae0d9ff1f504feffdaab1b20d23389b8f6c8527a371a81fbde'
SOURCE_SHA = 'ebad1a5844d1c24dcb8fd049047064effd3e297511005961959667d5939a347c'
SOURCE_COMMIT = '98acb6b02839c609ef5b837794e08d906d965335'
CONTRACT_SHA = '150a75871a7ed55b56d2aeffda7b9bafcc2512b9eeb4e1a5a9565fb49f22d8e8'
PREFLIGHT_COMMIT = '3d58641c8c62e80d60e82d137b03bcba7b8ed5cd'
PREFLIGHT_SHA256 = {
    'candidate_samples.json': '7d921eb575997956b93ee4a18ef668e1cb3b9511eb9b5737e6416d914ec20dd8',
    'E12_candidate_audit.md': 'b05041f22854d4d2e1b0eac8298c72cd53b43bbb341e20b63d9a0d110b99af09',
    'preservation_baseline.json': '1405db75a6ab107c3517a8abdd0585b38e6bc1a7cb5b0cea6f5e51c7a88acbfe',
    'preservation_check.json': '456fdbb31aa4ab603fd1911cf696b36ef6259fbf917e3b7123c2d61882f35654',
    'source_manifest.json': '4dd824303e0bc0be7aad2580029af3260dbd7484ce79b23d80b2409d155d2d6f',
}
LOCATION = {
    'file_path': 'test/testutil/tests.c',
    'region': {'startLine': 296, 'startColumn': 34, 'endColumn': 36},
    'context': {'startLine': 294, 'endLine': 298,
                'snippet': {'text': 'if (s1 == NULL || strcmp(s1, s2) == 0) {'}},
}
QUERY_FILES = {'Q1': 'Q1_path_reachable', 'Q2': 'Q2_real_path_s2_null',
               'Q3': 'Q3_counterfactual_no_xor_guard', 'Q4': 'Q4_invalid_no_short_circuit'}
SOLVER_CHECKS = 0
PHASE = 'START'


class InputMismatch(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


class UnsupportedInput(ValueError):
    pass


class VerificationFailure(RuntimeError):
    pass


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text('utf-8'))


def write_new(name, document):
    with (ROOT / name).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(document, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def check_sha(data, expected, code):
    if sha(data) != expected:
        raise InputMismatch(code, 'SHA-256 mismatch: ' + code + '; UNKNOWN, stop')


def verify_record(record):
    if not isinstance(record, dict):
        raise InputMismatch('record_type', 'the fixed row must be a JSON object')
    if record.get('function_name') != 'test_str_ne' or record.get('var_name') != 's2':
        raise InputMismatch('record_identity', 'fixed function/variable mismatch')
    if 'index' in record:
        raise InputMismatch('index_absence', 'original index must remain absent; row is not index')
    if type(record.get('result')) is not int or record['result'] != 0:
        raise InputMismatch('original_label', 'original result=0 must be preserved as metadata')
    if record.get('location') != LOCATION:
        raise InputMismatch('record_location', 'fixed alert source location mismatch')
    body = record.get('function_code')
    if not isinstance(body, str):
        raise InputMismatch('body_type', 'fixed function body must be UTF-8 text')
    check_sha(body.encode('utf-8'), BODY_SHA, 'function_body')
    return body


def verify_dataset_bytes(data):
    check_sha(data, DATASET_SHA, 'dataset')
    records = json.loads(data)
    if not isinstance(records, list) or len(records) != 5:
        raise InputMismatch('dataset_shape', 'fixed five-record dataset required')
    record = records[3]
    verify_record(record)
    return record


def verify_saved_source(source, body):
    if (source.get('pinned_commit') != SOURCE_COMMIT
            or source.get('tag') != 'openssl-3.4.0'
            or source.get('path') != 'test/testutil/tests.c'
            or source.get('tag_refs', {}).get('refs/tags/openssl-3.4.0^{}') != SOURCE_COMMIT):
        raise InputMismatch('source_identity', 'fixed saved source commit/tag/path mismatch')
    text = source.get('raw_source_utf8')
    if not isinstance(text, str):
        raise InputMismatch('saved_source_type', 'saved complete source text is missing')
    raw = text.encode('utf-8')
    check_sha(raw, SOURCE_SHA, 'saved_source_file')
    if source.get('sha256') != SOURCE_SHA or len(raw) != source.get('bytes'):
        raise InputMismatch('saved_source_metadata', 'source length/hash metadata mismatch')
    if text.count(body) != 1:
        raise InputMismatch('unique_function', 'fixed function is missing or ambiguous')
    start = text[:text.index(body)].count('\n') + 1
    end = start + len(body.splitlines()) - 1
    extracted = ''.join(text.splitlines(keepends=True)[290:303]).removesuffix('\n')
    if (start, end) != (291, 303) or extracted.encode('utf-8') != body.encode('utf-8'):
        raise InputMismatch('function_position', 'fixed function span/body mismatch')
    lines = text.splitlines()
    expected_lines = {
        292: 'const char *s1, const char *s2)',
        294: 'if ((s1 == NULL) ^ (s2 == NULL))',
        295: 'return 1;',
        296: 'if (s1 == NULL || strcmp(s1, s2) == 0) {',
    }
    for line, expected in expected_lines.items():
        if lines[line - 1].strip() != expected:
            raise InputMismatch('statement_position', 'fixed declaration/guard/target mismatch')
    return {'repository': 'openssl/openssl', 'tag': 'openssl-3.4.0',
            'commit': SOURCE_COMMIT, 'path': 'test/testutil/tests.c',
            'sha256': sha(raw), 'bytes': len(raw), 'function_span': [start, end],
            'unique_occurrences': 1, 'target_line': 296, 'exact_body_match': True,
            'method': 'saved preflight source bytes, exact function and fixed-line checks',
            'original_scanning_TU_build_or_scan_commit_authenticated': False}


def verify_inputs():
    """No solver is created, no network operation or file mutation is performed."""
    if {p.name for p in PREFLIGHT.iterdir()} != set(PREFLIGHT_SHA256):
        raise InputMismatch('preflight_file_set', 'frozen five-file preflight set changed')
    documents = {}
    for name, digest in PREFLIGHT_SHA256.items():
        raw = (PREFLIGHT / name).read_bytes()
        check_sha(raw, digest, 'preflight/' + name)
        if name.endswith('.json'):
            documents[name] = json.loads(raw)
    record = verify_dataset_bytes(DATASET.read_bytes())
    candidates = documents['candidate_samples.json']
    matches = [c for c in candidates['recommended_candidates'] if c['sample_id'] == SAMPLE_ID]
    if (len(matches) != 1 or candidates['primary_sample_id'] != SAMPLE_ID
            or matches[0]['original_record'] != record
            or matches[0]['original_index_present'] is not False):
        raise InputMismatch('frozen_candidate', 'row disagrees with the frozen primary candidate')
    body = verify_record(record)
    source = verify_saved_source(
        documents['source_manifest.json']['upstream_source_observation'], body)
    return {'status': 'MATCH', 'sample_id': SAMPLE_ID, 'row_zero_based': 3,
            'record_pointer': '/3', 'function_pointer': '/3/function_code',
            'dataset_path': DATASET.relative_to(REPRO).as_posix(),
            'dataset_sha256': DATASET_SHA, 'function_body_sha256': BODY_SHA,
            'original_record': record, 'original_index_present': False,
            'original_label': record['result'], 'label_used_as_constraint': False,
            'preflight_commit': PREFLIGHT_COMMIT, 'preflight_SHA256': PREFLIGHT_SHA256,
            'source_correspondence': source, 'new_source_downloads': 0,
            'no_backup_selection': True, 'original_alert_decision': None,
            'filter_authority': False, 'full_program_semantics': 'UNKNOWN'}


def load_contract():
    raw = (ROOT / 'semantic_contract.json').read_bytes()
    check_sha(raw, CONTRACT_SHA, 'semantic_contract')
    contract = json.loads(raw)
    if (contract['sample_id'] != SAMPLE_ID or contract['pointer_width'] is not None
            or contract['NOT_B_added_to_path_condition'] is not False
            or contract['label_used_as_constraint'] is not False
            or contract['filter_authority'] is not False
            or contract['original_alert_decision'] is not None):
        raise InputMismatch('contract_boundary', 'finite semantic contract boundary mismatch')
    return contract


def build_encoding(*, sample_id=SAMPLE_ID, abstraction='two_nullness_booleans', pointer_width=None):
    if sample_id != SAMPLE_ID or abstraction != 'two_nullness_booleans' or pointer_width is not None:
        raise UnsupportedInput('only this fixed two-Boolean sample without a pointer ABI is supported')
    A = z3.Bool('e12_test_str_ne_s1_is_null')
    B = z3.Bool('e12_test_str_ne_s2_is_null')
    xor_guard = z3.Xor(A, B)
    continue_guard = z3.Not(xor_guard)
    short_circuit_guard = z3.Not(A)
    PC = z3.And(continue_guard, short_circuit_guard)
    return {'A': A, 'B': B, 'xor_guard': xor_guard, 'continue_guard': continue_guard,
            'short_circuit_guard': short_circuit_guard, 'PC': PC, 'Fault': B,
            'queries': {'Q1': PC, 'Q2': z3.And(PC, B),
                        'Q3': z3.And(z3.Not(A), B),
                        'Q4': z3.And(continue_guard, B)}}


def _solve_saved(query_id, encoding, contract, independent):
    global SOLVER_CHECKS, PHASE
    PHASE = query_id
    formula = encoding['queries'][query_id]
    solver = z3.SolverFor('QF_UF')
    solver.set(timeout=30000)
    solver.add(formula)
    smtlib = '(set-logic QF_UF)\n(set-option :timeout 30000)\n' + solver.to_smt2()
    basename = 'queries/' + QUERY_FILES[query_id]
    with (ROOT / (basename + '.smt2')).open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(smtlib)
    start = time.perf_counter()
    SOLVER_CHECKS += 1
    answer = solver.check()
    elapsed = time.perf_counter() - start
    status = {'sat': 'SAT', 'unsat': 'UNSAT', 'unknown': 'UNKNOWN'}[str(answer)]
    spec = contract['queries'][query_id]
    result = {'query_id': query_id, 'formula': spec['formula'],
              'SMT_expression': formula.sexpr(), 'classification': spec['classification'],
              'real_source_path_encoding': spec['real_source_path_encoding'],
              'claimed_actual_execution': False, 'logic': 'QF_UF (Boolean subset)',
              'solver_status': status, 'expected_status': spec['expected_status'],
              'elapsed_seconds': elapsed, 'timeout_ms': 30000,
              'smtlib_file': basename + '.smt2', 'exact_smtlib': smtlib,
              'smtlib_sha256': sha(smtlib.encode('utf-8')),
              'model': None, 'raw_model': None, 'reason_unknown': None,
              'UNSAT_certificate_generated': False,
              'UNSAT_solver_certificate_independently_checked': False}
    finite_status = independent['finite_domain_status'][query_id]
    model_match = None
    if status == 'SAT':
        model = solver.model()
        values = {name: z3.is_true(model.eval(encoding[name], model_completion=True))
                  for name in ('A', 'B')}
        result['model'], result['raw_model'] = values, model.sexpr()
        result['real_source_reference_trace_for_model'] = reference.execute_prefix(**values)
        model_match = (values in independent['satisfying_assignments'][query_id]
                       and reference.query_value(query_id, **values))
    elif status == 'UNKNOWN':
        result['reason_unknown'] = solver.reason_unknown()
    verified = (status != 'UNKNOWN' and status == finite_status
                and (model_match is not False))
    result['independent_verification'] = {
        'status': 'MATCH' if verified else 'NOT_VERIFIED',
        'finite_domain_status': finite_status,
        'all_four_inputs_enumerated': True,
        'satisfying_assignments': independent['satisfying_assignments'][query_id],
        'SAT_model_in_reference_solution_set': model_match, 'solver_checks': 0,
        'method': 'independent Python integer-XOR and sequential source-prefix interpretation',
        'scope': 'entire two-Boolean abstraction, not a solver proof certificate or full C program'}
    result['query_checks_passed'] = verified and status == spec['expected_status']
    write_new(basename + '.json', result)
    return result


def run_experiment():
    global PHASE
    PHASE = 'INPUT_GATES'
    inputs = verify_inputs()
    contract = load_contract()
    if (ROOT / 'queries').exists() or (ROOT / 'experiment_results.json').exists():
        raise FileExistsError('saved queries/results exist; do not overwrite or rerun')
    if (ROOT / 'input_verification.json').exists():
        if read_json(ROOT / 'input_verification.json') != inputs:
            raise InputMismatch('prior_input_verification', 'input gate record changed')
    else:
        write_new('input_verification.json', inputs)
    independent = reference.enumerate_domain()
    independent['reference_code_sha256'] = sha(Path(reference.__file__).read_bytes())
    write_new('independent_verification.json', independent)
    (ROOT / 'queries').mkdir()
    encoding = build_encoding()
    runs = []
    for query_id in QUERY_FILES:
        result = _solve_saved(query_id, encoding, contract, independent)
        runs.append(result)
        if not result['query_checks_passed']:
            raise VerificationFailure('saved ' + query_id + ' did not pass; stop without publishing')
    document = {
        'stage': 'E12-1+E12-2', 'sample_id': SAMPLE_ID,
        'original_index_present': False, 'original_label': inputs['original_label'],
        'label_used_as_constraint': False, 'dataset_sha256': DATASET_SHA,
        'function_body_sha256': BODY_SHA, 'source_commit': SOURCE_COMMIT,
        'input_verification_sha256': sha((ROOT / 'input_verification.json').read_bytes()),
        'contract_sha256': CONTRACT_SHA, 'implementation_sha256': sha(Path(__file__).read_bytes()),
        'independent_reference_sha256': sha(Path(reference.__file__).read_bytes()),
        'independent_verification_sha256': sha((ROOT / 'independent_verification.json').read_bytes()),
        'solver': {'name': 'Z3', 'version': z3.get_version_string(),
                   'package_version': importlib.metadata.version('z3-solver'),
                   'logic': 'QF_UF, Boolean subset only'},
        'recorded_at_UTC': datetime.now(timezone.utc).isoformat(), 'queries': runs,
        'solver_check_count': SOLVER_CHECKS, 'all_query_checks_passed': True,
        'all_input_gates_completed_before_solver_checks': True,
        'NOT_B_asserted_as_path_assumption': False,
        'strcmp_return_value_used_as_path_assumption': False,
        'pointer_width_or_distinct_objects_assumed': False,
        'independent_reference_solver_checks': 0,
        'unknown_handling': 'retain UNKNOWN, stop acceptance and do not publish',
        'UNSAT_certificate_generated': False,
        'UNSAT_solver_certificate_independently_checked': False,
        'calls': {'LLM_API': 0, 'Harness': 0, 'original_analyzer': 0,
                  'historical_regression': 0, 'build': 0, 'source_or_dataset_download': 0},
        'original_checker_rule_ID': 'UNKNOWN', 'original_scanning_TU': 'UNKNOWN',
        'original_build_environment': 'UNKNOWN', 'original_scanning_commit': 'UNKNOWN',
        'non_NULL_object_lifetime_or_readability': 'NOT_VERIFIED',
        'blind_test_claim': False, 'original_alert_decision': None,
        'filter_authority': False, 'full_program_semantics': 'UNKNOWN',
        'property_scope': contract['certified_scope'],
    }
    write_new('experiment_results.json', document)
    PHASE = 'FOUR_QUERIES_SAVED'
    print(json.dumps({'queries': [(r['query_id'], r['solver_status'], r['model']) for r in runs],
                      'solver_checks': SOLVER_CHECKS, 'independent_matches': 4}))


if __name__ == '__main__':
    try:
        if len(sys.argv) != 1:
            raise UnsupportedInput('no alternate sample, formula or CLI arguments supported')
        run_experiment()
    except Exception as error:
        if not (ROOT / 'failure_record.json').exists():
            write_new('failure_record.json', {
                'status': 'UNKNOWN', 'phase': PHASE, 'type': type(error).__name__,
                'error_code': getattr(error, 'code', None), 'message': str(error),
                'solver_checks_before_failure': SOLVER_CHECKS,
                'backup_sample_selected': False, 'publish_allowed': False,
                'original_alert_decision': None, 'filter_authority': False,
                'full_program_semantics': 'UNKNOWN'})
        raise
