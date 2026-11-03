"""E09-only arithmetic, source-admission and saved-query verification.

Concrete Z3 simplifications are compared with independent integer arithmetic.
The four saved core queries are inspected, not repeated by this test runner.
"""
import json
from pathlib import Path
import unittest
from unittest import mock

import z3
import scalar_smt as scalar


class ScalarChecks(unittest.TestCase):
    observations = []

    @classmethod
    def setUpClass(cls):
        cls.source, cls.parsed = scalar.load_inputs()
        cls.results = scalar.read_json(scalar.ROOT / 'experiment_results.json')

    def test_source_hash_identity_and_original_label_are_preserved(self):
        self.assertEqual(self.source['dataset_sha256'], scalar.DATASET_SHA256)
        self.assertEqual(self.source['function_body_sha256'], scalar.BODY_SHA256)
        self.assertEqual((self.source['original_index'], self.source['original_label']), (4, 0))
        self.assertEqual(self.source['sample_id'], scalar.AUDIT_SAMPLE_ID)
        self.assertEqual(self.results['source'], self.source)
        self.assertEqual(self.results['implementation_sha256'],
                         scalar.sha(Path(scalar.__file__).read_bytes()))

    def test_required_boundary_values_and_nonpositive_branch(self):
        cases = [(1, 0), (999, 0), (1000, 1), (1001, 1)]
        for width in (32, 64):
            enc = scalar.encode_fragment(self.parsed, width)
            for value, expected in cases:
                with self.subTest(width=width, srate=value):
                    ref = scalar.reference_execution(value, width, self.parsed)
                    result = z3.simplify(z3.substitute(enc['inner'],
                                         (enc['srate'], z3.BitVecVal(value, width)))).as_signed_long()
                    self.assertEqual(ref['inner'], expected)
                    self.assertEqual(result, expected)
                    self.assertEqual(ref['outer_evaluated'], expected != 0)
                    self.assertEqual(ref['return_value'], None if expected == 0 else 100000)
                    self.observations.append({'width': width, 'srate': value,
                                              'smt_inner': result, 'reference': ref, 'match': True})
            for value in (0, -1, -999, -1000, -(1 << (width - 1))):
                with self.subTest(width=width, srate=value):
                    ref = scalar.reference_execution(value, width, self.parsed)
                    guard = z3.simplify(z3.substitute(enc['guard'],
                                        (enc['srate'], z3.BitVecVal(value, width))))
                    self.assertTrue(z3.is_false(guard))
                    self.assertEqual((ref['division_branch_entered'], ref['inner'], ref['return_value']),
                                     (False, None, 0))
                    self.observations.append({'width': width, 'srate': value,
                                              'smt_guard': False, 'reference': ref, 'match': True})

    def test_signed_division_signs_extrema_and_no_float_rounding(self):
        for width in (32, 64):
            lo, hi = scalar.width_check(width)
            pairs = [(-999, 1000), (-1001, 1000), (1001, -1000), (-1001, -1000),
                     (lo, 1000), (hi, 1000), (hi, -1000), (lo, 1), (lo, lo)]
            for numerator, denominator in pairs:
                with self.subTest(width=width, numerator=numerator, denominator=denominator):
                    term, defined = scalar.signed_division(z3.BitVecVal(numerator, width),
                                                         z3.BitVecVal(denominator, width), width)
                    self.assertTrue(z3.is_true(z3.simplify(defined)))
                    actual = z3.simplify(term).as_signed_long()
                    expected = scalar.c_signed_divide(numerator, denominator, width)
                    self.assertEqual(actual, expected)
                    self.observations.append({'width': width, 'numerator': numerator,
                                              'denominator': denominator, 'smt': actual,
                                              'independent_reference': expected, 'match': True})
        self.assertEqual(scalar.c_signed_divide(-999, 1000, 64), 0)
        self.assertEqual(scalar.c_signed_divide(-1001, 1000, 64), -1)

    def test_small_positive_range_differential_check(self):
        for width in (32, 64):
            for value in range(1, 2002):
                term, defined = scalar.signed_division(z3.BitVecVal(value, width),
                                                     z3.BitVecVal(1000, width), width)
                self.assertTrue(z3.is_true(z3.simplify(defined)))
                actual = z3.simplify(term).as_signed_long()
                self.assertEqual(actual, scalar.c_signed_divide(value, 1000, width))
                self.assertEqual(actual == 0, value < 1000)
        # This finite differential check is not claimed to enumerate either ABI domain.

    def test_undefined_divisions_are_blocked(self):
        for width in (32, 64):
            lo, _ = scalar.width_check(width)
            for numerator, denominator in ((1, 0), (0, 0), (lo, -1)):
                with self.subTest(width=width, numerator=numerator, denominator=denominator):
                    _, defined = scalar.signed_division(z3.BitVecVal(numerator, width),
                                                      z3.BitVecVal(denominator, width), width)
                    self.assertTrue(z3.is_false(z3.simplify(defined)))
                    with self.assertRaises(scalar.CUndefinedBehavior):
                        scalar.c_signed_divide(numerator, denominator, width)

    def test_fault_query_does_not_assume_away_zero_denominator(self):
        for width in (32, 64):
            enc = scalar.encode_fragment(self.parsed, width)
            replacements = (enc['srate'], z3.BitVecVal(1, width))
            self.assertTrue(z3.is_false(z3.simplify(z3.substitute(enc['outer_defined'], replacements))))
            self.assertTrue(z3.is_false(z3.simplify(z3.substitute(enc['defined_on_selected_path'], replacements))))
            replacements = (enc['srate'], z3.BitVecVal(0, width))
            self.assertTrue(z3.is_true(z3.simplify(z3.substitute(enc['defined_on_selected_path'], replacements))))
        self.assertTrue(all(not r['outer_definedness_asserted_in_fault_query'] for r in self.results['runs']))

    def test_saved_core_queries_and_cross_ABI_agreement(self):
        runs = {(r['width_bits'], r['experiment']): r for r in self.results['runs']}
        self.assertEqual(len(runs), 4)
        for width in (32, 64):
            self.assertEqual(runs[(width, 'A')]['status'], 'SAT')
            self.assertEqual(runs[(width, 'B')]['status'], 'UNSAT')
            self.assertEqual(runs[(width, 'B')]['unsat_proof']['status'],
                             'SOLVER_REPORTED_UNSAT_NO_PROOF_CERTIFICATE')
            self.assertFalse(runs[(width, 'B')]['unsat_proof']['certificate_generated'])
            self.assertIn('bvsdiv', runs[(width, 'A')]['formula_smt2'])
            self.assertTrue(runs[(width, 'B')]['assumptions'][-1]['experimental'])
            self.assertFalse(runs[(width, 'B')]['assumptions'][-1]['proven_in_original_project'])
        self.assertTrue(self.results['both_contracts_agree'])

    def test_saved_SAT_models_rechecked_independently(self):
        for run in self.results['runs']:
            if run['status'] != 'SAT':
                continue
            model = run['model']
            check = scalar.verify_sat_witness(model['srate_signed'], model['inner_signed'],
                                              run['width_bits'], run['experiment'], self.parsed)
            self.assertEqual(check, run['independent_model_check'])
            self.assertTrue(1 <= model['srate_signed'] <= 999)

    def test_mismatched_model_is_rejected(self):
        with self.assertRaises(scalar.SemanticMismatch):
            scalar.verify_sat_witness(1, 1, 32, 'A', self.parsed)
        with self.assertRaises(scalar.SemanticMismatch):
            scalar.verify_sat_witness(1, 0, 64, 'B', self.parsed)

    def test_unsupported_type_width_or_semantics_rejected_before_solver(self):
        with mock.patch.object(z3, 'SolverFor', side_effect=AssertionError('solver must not run')):
            for width in (16, 128, True, '32'):
                with self.assertRaises(scalar.UnsupportedSemantics):
                    scalar.encode_fragment(self.parsed, width)
            for c_type in ('unsigned long', 'int', 'float', 'long *'):
                with self.assertRaises(scalar.UnsupportedSemantics):
                    scalar.encode_fragment(self.parsed, 32, c_type=c_type)
            with self.assertRaises(scalar.UnsupportedSemantics):
                scalar.encode_fragment(self.parsed, 64, division='floor')
            with self.assertRaises(scalar.UnsupportedSemantics):
                scalar.run_query(self.parsed, 32, 'caller-guessed')
        with self.assertRaises(scalar.UnsupportedSemantics):
            scalar.signed_division(z3.BitVecVal(1, 32), z3.BitVecVal(1000, 64), 32)
        with self.assertRaises(scalar.UnsupportedSemantics):
            scalar.reference_execution(1 << 31, 32, self.parsed)

    def test_unreviewed_source_grammar_and_constants_rejected(self):
        body = self.source['function_body']
        for changed in (body.replace('long', 'unsigned long'), body.replace('1000)', '0)'),
                        body.replace('> 0', '>= 0'), body.replace('srate / 1000', '(int)srate / 1000'),
                        body + '\nint other;', body.replace('100000', '100001')):
            with self.subTest(changed=changed):
                with self.assertRaises(scalar.UnsupportedSemantics):
                    scalar.parse_fragment(changed)

    def test_dataset_and_body_hash_failures_stop_before_solver(self):
        original_read = Path.read_bytes
        def tampered(path):
            blob = original_read(path)
            return blob + b' ' if path == scalar.DATASET else blob
        with mock.patch.object(z3, 'SolverFor', side_effect=AssertionError('solver must not run')):
            with mock.patch.object(Path, 'read_bytes', autospec=True, side_effect=tampered):
                with self.assertRaisesRegex(scalar.InputMismatch, 'dataset SHA256'):
                    scalar.load_inputs()
            # Simulated hash failure at the body gate, without modifying original files.
            with mock.patch.object(scalar, 'sha', side_effect=[scalar.AUDIT_SHA256, scalar.DATASET_SHA256, '0' * 64]):
                with self.assertRaisesRegex(scalar.InputMismatch, 'function body SHA256'):
                    scalar.load_inputs()

    def test_result_authority_remains_local_only(self):
        self.assertEqual(self.results['full_program_semantics'], 'UNKNOWN')
        self.assertIsNone(self.results['original_alert_decision'])
        self.assertFalse(self.results['filter_authority'])
        self.assertTrue(self.results['original_label_preserved'])
        for run in self.results['runs']:
            self.assertFalse(run['filter_authority'])
            self.assertIsNone(run['original_alert_decision'])


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ScalarChecks)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    report = {'scope': 'E09 only; local arithmetic/admission/result checks',
              'status': 'PASS' if result.wasSuccessful() else 'FAIL',
              'test_methods': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors),
              'concrete_observations': ScalarChecks.observations,
              'small_positive_range': {'first': 1, 'last_inclusive': 2001, 'widths': [32, 64],
                                       'pairs_checked': 4002, 'complete_ABI_domain_enumerated': False},
              'additional_solver_check_calls': 0, 'original_C_compiles_or_executions': 0,
              'old_regression_runs': 0,
              'experiments_sha256': scalar.sha((scalar.ROOT / 'experiment_results.json').read_bytes()),
              'test_implementation_sha256': scalar.sha(Path(__file__).read_bytes())}
    scalar.write_new(scalar.ROOT / 'test_results.json', report)
    raise SystemExit(0 if result.wasSuccessful() else 1)
