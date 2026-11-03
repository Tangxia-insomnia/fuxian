"""E12-only tests: source gates, saved queries/models, and complete finite domain.

No solver.check is called. Solver constructors are blocked during the suite.
The independent reference is a separate standard-library-only interpreter.
"""
import copy
import io
import json
from pathlib import Path
import unittest
from unittest import mock

import z3
from z3.z3util import get_vars

import e12_nullness_smt as smt
import independent_reference as reference


def evaluate_boolean(expression, encoding, A, B):
    value = z3.simplify(z3.substitute(
        expression, (encoding['A'], z3.BoolVal(A)), (encoding['B'], z3.BoolVal(B))))
    if not (z3.is_true(value) or z3.is_false(value)):
        raise AssertionError('concrete expression did not reduce to a Boolean')
    return z3.is_true(value)


def contains(expression, target):
    return expression.eq(target) or any(contains(child, target) for child in expression.children())


class NullnessChecks(unittest.TestCase):
    formula_observations = []

    @classmethod
    def setUpClass(cls):
        cls.inputs = smt.verify_inputs()
        cls.contract = smt.load_contract()
        cls.results = smt.read_json(smt.ROOT / 'experiment_results.json')
        cls.independent = smt.read_json(smt.ROOT / 'independent_verification.json')
        cls.runs = {run['query_id']: run for run in cls.results['queries']}
        cls.encoding = smt.build_encoding()

    def assert_input_code(self, code, function, *arguments):
        with self.assertRaises(smt.InputMismatch) as error:
            function(*arguments)
        self.assertEqual(error.exception.code, code)

    def test_01_frozen_preflight_and_original_identity(self):
        self.assertEqual(self.inputs['status'], 'MATCH')
        self.assertEqual(self.inputs['sample_id'], smt.SAMPLE_ID)
        self.assertEqual(self.inputs['row_zero_based'], 3)
        self.assertEqual(self.inputs['dataset_sha256'], smt.DATASET_SHA)
        self.assertEqual(self.inputs['function_body_sha256'], smt.BODY_SHA)
        self.assertEqual(self.inputs['preflight_SHA256'], smt.PREFLIGHT_SHA256)
        self.assertEqual(len(self.inputs['preflight_SHA256']), 5)
        self.assertEqual(self.inputs['original_record']['function_name'], 'test_str_ne')
        self.assertEqual(self.inputs['original_record']['var_name'], 's2')
        self.assertEqual(self.inputs['original_record']['location'], smt.LOCATION)

    def test_02_dataset_hash_tampering_is_stopped(self):
        self.assert_input_code('dataset', smt.verify_dataset_bytes, smt.DATASET.read_bytes() + b'\n')

    def test_03_function_hash_tampering_is_stopped(self):
        record = copy.deepcopy(self.inputs['original_record'])
        record['function_code'] = record['function_code'].replace(' ^ ', ' | ')
        self.assert_input_code('function_body', smt.verify_record, record)

    def test_04_target_location_and_variable_identity_are_pinned(self):
        record = copy.deepcopy(self.inputs['original_record'])
        record['location']['region']['startLine'] = 295
        self.assert_input_code('record_location', smt.verify_record, record)
        for key, value in [('var_name', 's1'), ('function_name', 'test_strn_ne')]:
            record = copy.deepcopy(self.inputs['original_record'])
            record[key] = value
            self.assert_input_code('record_identity', smt.verify_record, record)

    def test_05_index_absence_and_label_preservation(self):
        record = copy.deepcopy(self.inputs['original_record'])
        self.assertNotIn('index', record)
        self.assertFalse(self.inputs['original_index_present'])
        record['index'] = 3
        self.assert_input_code('index_absence', smt.verify_record, record)
        for bad_label in (1, False, None):
            record = copy.deepcopy(self.inputs['original_record'])
            record['result'] = bad_label
            self.assert_input_code('original_label', smt.verify_record, record)
        self.assertEqual(self.results['original_label'], 0)
        self.assertFalse(self.results['label_used_as_constraint'])

    def test_06_saved_source_bytes_commit_span_and_line(self):
        source = smt.read_json(smt.PREFLIGHT / 'source_manifest.json')['upstream_source_observation']
        body = self.inputs['original_record']['function_code']
        verified = smt.verify_saved_source(source, body)
        self.assertEqual(verified['function_span'], [291, 303])
        self.assertEqual((verified['unique_occurrences'], verified['target_line']), (1, 296))
        self.assertEqual(verified['commit'], smt.SOURCE_COMMIT)
        self.assertFalse(verified['original_scanning_TU_build_or_scan_commit_authenticated'])
        changed = copy.deepcopy(source)
        changed['raw_source_utf8'] += '\n'
        self.assert_input_code('saved_source_file', smt.verify_saved_source, changed, body)
        changed = copy.deepcopy(source)
        changed['pinned_commit'] = '0' * 40
        self.assert_input_code('source_identity', smt.verify_saved_source, changed, body)

    def test_07_failed_input_gate_precedes_any_solver_or_result_write(self):
        with mock.patch.object(smt, 'verify_inputs', side_effect=smt.InputMismatch('dataset', 'bad hash')), \
             mock.patch.object(smt, 'write_new') as writer:
            self.assert_input_code('dataset', smt.run_experiment)
            writer.assert_not_called()
        self.assertEqual(smt.SOLVER_CHECKS, 0)

    def test_08_unsupported_sample_and_memory_inputs_are_rejected(self):
        for arguments in ({'sample_id': 'test_strn_ne'}, {'abstraction': 'full_memory'},
                          {'pointer_width': 32}, {'pointer_width': 64}, {'pointer_width': False}):
            with self.subTest(arguments=arguments), self.assertRaises(smt.UnsupportedInput):
                smt.build_encoding(**arguments)
        for values in ((0, False), (False, 1), (None, True), ('NULL', False)):
            with self.subTest(values=values), self.assertRaises(ValueError):
                reference.execute_prefix(*values)
        with self.assertRaises(ValueError):
            reference.query_value('Q5', False, False)

    def test_09_two_distinct_declared_bool_variables(self):
        enc = self.encoding
        self.assertFalse(enc['A'].eq(enc['B']))
        self.assertTrue(z3.is_bool(enc['A']) and z3.is_bool(enc['B']))
        self.assertEqual({v.decl().name() for v in get_vars(enc['PC'])},
                         {'e12_test_str_ne_s1_is_null', 'e12_test_str_ne_s2_is_null'})
        variables = self.contract['variables']
        self.assertEqual(variables['A']['parameter_ordinal_zero_based'], 4)
        self.assertEqual(variables['B']['parameter_ordinal_zero_based'], 5)
        self.assertEqual(variables['A']['C_pointer_type'], 'const char *')
        self.assertEqual(variables['B']['C_pointer_type'], 'const char *')

    def test_10_integer_xor_differs_from_or(self):
        enc = self.encoding
        for A, B, expected in ((False, False, 0), (False, True, 1),
                               (True, False, 1), (True, True, 0)):
            trace = reference.execute_prefix(A, B)
            self.assertEqual(trace['C_first_condition_int'], expected)
            self.assertEqual(evaluate_boolean(enc['xor_guard'], enc, A, B), expected != 0)
        self.assertFalse(evaluate_boolean(enc['xor_guard'], enc, True, True))
        self.assertTrue(evaluate_boolean(z3.Or(enc['A'], enc['B']), enc, True, True))
        self.assertEqual(enc['xor_guard'].decl().kind(), z3.Z3_OP_XOR)

    def test_11_branch_polarity_and_early_return(self):
        expected = {(False, False): (False, True), (False, True): (True, False),
                    (True, False): (True, False), (True, True): (False, True)}
        for (A, B), (early_return, continued) in expected.items():
            trace = reference.execute_prefix(A, B)
            self.assertEqual(trace['early_return_taken'], early_return)
            self.assertEqual(trace['second_left_evaluated'], continued)
            self.assertEqual(evaluate_boolean(self.encoding['continue_guard'], self.encoding, A, B),
                             continued)
            if early_return:
                self.assertIsNone(trace['second_left_value'])
                self.assertFalse(trace['strcmp_evaluated'])

    def test_12_short_circuit_and_target_call_boundary(self):
        trace = reference.execute_prefix(True, True)
        self.assertTrue(trace['second_left_evaluated'])
        self.assertTrue(trace['second_left_value'])
        self.assertFalse(trace['strcmp_evaluated'])
        trace = reference.execute_prefix(False, False)
        self.assertFalse(trace['second_left_value'])
        self.assertTrue(trace['strcmp_evaluated'])
        self.assertFalse(trace['strcmp_result_used_for_reachability'])
        self.assertFalse(self.contract['C_short_circuit_OR']['strcmp_return_value_used_as_precondition'])

    def test_13_complete_independent_domain_and_formula_agreement(self):
        expected = {'Q1': [{'A': False, 'B': False}], 'Q2': [],
                    'Q3': [{'A': False, 'B': True}], 'Q4': [{'A': True, 'B': True}]}
        fresh = reference.enumerate_domain()
        self.assertEqual(fresh['satisfying_assignments'], expected)
        self.assertEqual(fresh['domain_size'], 4)
        self.assertTrue(fresh['domain_completely_enumerated'])
        self.assertEqual(self.independent['traces'], fresh['traces'])
        self.assertEqual(self.independent['satisfying_assignments'], expected)
        for query_id, expression in self.encoding['queries'].items():
            for trace in fresh['traces']:
                A, B = trace['A'], trace['B']
                actual = evaluate_boolean(expression, self.encoding, A, B)
                independent = reference.query_value(query_id, A, B)
                self.assertEqual(actual, independent)
                self.formula_observations.append({'query_id': query_id, 'A': A, 'B': B,
                                                  'SMT_substitution': actual,
                                                  'independent_Python': independent, 'match': True})
        reachable = [r for r in fresh['traces'] if r['strcmp_evaluated']]
        self.assertEqual([(r['A'], r['B']) for r in reachable], [(False, False)])
        self.assertTrue(all(not r['B'] for r in reachable))

    def test_14_Q1_path_reachability_model(self):
        run = self.runs['Q1']
        self.assertEqual(run['solver_status'], 'SAT')
        self.assertEqual(run['model'], {'A': False, 'B': False})
        self.assertTrue(run['real_source_path_encoding'])
        self.assertTrue(run['real_source_reference_trace_for_model']['strcmp_evaluated'])

    def test_15_Q2_fault_unsat_without_solver_certificate_claim(self):
        run = self.runs['Q2']
        self.assertEqual(run['solver_status'], 'UNSAT')
        self.assertIsNone(run['model'])
        self.assertIsNone(run['raw_model'])
        self.assertEqual(run['independent_verification']['satisfying_assignments'], [])
        self.assertEqual(run['independent_verification']['status'], 'MATCH')
        self.assertFalse(run['UNSAT_certificate_generated'])
        self.assertFalse(run['UNSAT_solver_certificate_independently_checked'])

    def test_16_Q3_counterfactual_is_not_actual_source_execution(self):
        run = self.runs['Q3']
        self.assertEqual(run['solver_status'], 'SAT')
        self.assertEqual(run['model'], {'A': False, 'B': True})
        self.assertEqual(run['classification'], 'COUNTERFACTUAL_XOR_GUARD_REMOVED')
        self.assertFalse(run['real_source_path_encoding'])
        self.assertTrue(run['real_source_reference_trace_for_model']['early_return_taken'])
        self.assertFalse(run['real_source_reference_trace_for_model']['strcmp_evaluated'])

    def test_17_Q4_invalid_encoding_produces_a_spurious_path(self):
        run = self.runs['Q4']
        self.assertEqual(run['solver_status'], 'SAT')
        self.assertEqual(run['model'], {'A': True, 'B': True})
        self.assertEqual(run['classification'], 'INVALID_ENCODING_DIAGNOSTIC_ONLY')
        self.assertFalse(run['real_source_path_encoding'])
        trace = run['real_source_reference_trace_for_model']
        self.assertFalse(trace['early_return_taken'])
        self.assertTrue(trace['second_left_value'])
        self.assertFalse(trace['strcmp_evaluated'])

    def test_18_no_assumed_not_B_or_future_return_value(self):
        enc = self.encoding
        self.assertEqual(enc['PC'].num_args(), 2)
        self.assertTrue(enc['PC'].arg(0).eq(z3.Not(z3.Xor(enc['A'], enc['B']))))
        self.assertTrue(enc['PC'].arg(1).eq(z3.Not(enc['A'])))
        self.assertFalse(contains(enc['PC'], z3.Not(enc['B'])))
        self.assertTrue(enc['queries']['Q2'].eq(z3.And(enc['PC'], enc['B'])))
        self.assertFalse(self.results['NOT_B_asserted_as_path_assumption'])
        self.assertFalse(self.results['strcmp_return_value_used_as_path_assumption'])
        self.assertTrue(all('strcmp_result' not in v.decl().name()
                            for e in enc['queries'].values() for v in get_vars(e)))

    def test_19_saved_SMT_files_models_and_independent_status_are_exact(self):
        for query_id, run in self.runs.items():
            raw = (smt.ROOT / run['smtlib_file']).read_bytes()
            self.assertEqual(raw, run['exact_smtlib'].encode('utf-8'))
            self.assertEqual(smt.sha(raw), run['smtlib_sha256'])
            assertions = z3.parse_smt2_string(raw.decode('utf-8'))  # parse, do not solve
            self.assertEqual(len(assertions), 1)
            for trace in self.independent['traces']:
                A, B = trace['A'], trace['B']
                self.assertEqual(evaluate_boolean(assertions[0], self.encoding, A, B),
                                 reference.query_value(query_id, A, B))
            self.assertEqual(run['solver_status'], self.independent['finite_domain_status'][query_id])
            self.assertEqual(run['independent_verification']['status'], 'MATCH')
            self.assertTrue(run['query_checks_passed'])
            self.assertGreaterEqual(run['elapsed_seconds'], 0)
            saved = smt.read_json(smt.ROOT / 'queries' / (smt.QUERY_FILES[query_id] + '.json'))
            self.assertEqual(saved, run)

    def test_20_filter_authority_and_unresolved_scope_stay_explicit(self):
        for document in (self.contract, self.results, self.inputs):
            self.assertIsNone(document['original_alert_decision'])
            self.assertFalse(document['filter_authority'])
            self.assertEqual(document['full_program_semantics'], 'UNKNOWN')
        for field in ('original_checker_rule_ID', 'original_scanning_TU',
                      'original_build_environment', 'original_scanning_commit'):
            self.assertEqual(self.results[field], 'UNKNOWN')
        self.assertFalse(self.results['blind_test_claim'])
        self.assertFalse(self.results['pointer_width_or_distinct_objects_assumed'])
        self.assertEqual(self.results['non_NULL_object_lifetime_or_readability'], 'NOT_VERIFIED')
        self.assertFalse(self.contract['pointer_address_or_heap_encoding'])

    def test_21_code_contract_and_verification_hashes(self):
        self.assertEqual(self.results['implementation_sha256'], smt.sha(Path(smt.__file__).read_bytes()))
        self.assertEqual(self.results['independent_reference_sha256'],
                         smt.sha(Path(reference.__file__).read_bytes()))
        self.assertEqual(self.results['contract_sha256'], smt.CONTRACT_SHA)
        self.assertEqual(self.results['input_verification_sha256'],
                         smt.sha((smt.ROOT / 'input_verification.json').read_bytes()))
        self.assertEqual(self.results['independent_verification_sha256'],
                         smt.sha((smt.ROOT / 'independent_verification.json').read_bytes()))

    def test_22_counts_unknown_handling_and_no_extra_solving(self):
        self.assertEqual(set(self.runs), {'Q1', 'Q2', 'Q3', 'Q4'})
        self.assertEqual(self.results['solver_check_count'], 4)
        self.assertEqual(self.results['solver']['version'], z3.get_version_string())
        self.assertEqual(self.results['independent_reference_solver_checks'], 0)
        self.assertEqual(smt.SOLVER_CHECKS, 0)
        self.assertTrue(self.results['all_input_gates_completed_before_solver_checks'])
        self.assertTrue(self.results['all_query_checks_passed'])
        self.assertIn('retain UNKNOWN', self.results['unknown_handling'])
        self.assertTrue(all(count == 0 for count in self.results['calls'].values()))
        self.assertNotIn('z3', vars(reference))
        self.assertNotIn('e12_nullness_smt', vars(reference))


def main():
    if (smt.ROOT / 'test_results.json').exists():
        raise FileExistsError('test results exist; never overwrite failure or success records')
    output = io.StringIO()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(NullnessChecks)
    with mock.patch.object(z3, 'SolverFor', side_effect=AssertionError('test solver forbidden')), \
         mock.patch.object(z3, 'Solver', side_effect=AssertionError('test solver forbidden')):
        result = unittest.TextTestRunner(stream=output, verbosity=2).run(suite)
    document = {
        'tests_run': result.testsRun, 'failures': len(result.failures),
        'errors': len(result.errors), 'skipped': len(result.skipped),
        'passed': result.wasSuccessful(), 'extra_solver_checks': smt.SOLVER_CHECKS,
        'abstract_input_domain_size': 4, 'complete_abstract_domain_enumerated': True,
        'recorded_formula_truth_comparisons': NullnessChecks.formula_observations,
        'test_code_sha256': smt.sha(Path(__file__).read_bytes()),
        'independent_reference_sha256': smt.sha(Path(reference.__file__).read_bytes()),
        'verification_layers': ['source/hash static checks', 'four saved Z3 query results',
                                'pure Python reference with four cases',
                                'concrete SMT substitutions and parsing without solving'],
        'output': output.getvalue(), 'failure_details': [
            {'test': str(test), 'traceback': trace} for test, trace in result.failures + result.errors],
        'file_preservation_checked_here': False,
        'original_alert_decision': None, 'filter_authority': False,
        'full_program_semantics': 'UNKNOWN',
    }
    smt.write_new('test_results.json', document)
    print(json.dumps({'tests_run': result.testsRun, 'failures': len(result.failures),
                      'errors': len(result.errors), 'passed': result.wasSuccessful(),
                      'recorded_formula_comparisons': len(NullnessChecks.formula_observations),
                      'extra_solver_checks': smt.SOLVER_CHECKS}))
    if not result.wasSuccessful():
        raise SystemExit(1)


if __name__ == '__main__':
    main()
