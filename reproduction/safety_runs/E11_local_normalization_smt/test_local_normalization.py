"""E11 source/encoding/model checks; no repeated solver.check calls.

The experiment saves four symbolic checks and eight concrete models. Tests
inspect those records and compare concrete substitutions to independent host
arithmetic. Solver constructors are blocked throughout this test run.
"""
import io
import json
from pathlib import Path
import unittest
from unittest import mock

import z3
import local_normalization_smt as local


class NormalizationChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.row, cls.contract = local.load_inputs()
        cls.results = local.read_json('experiment_results.json')
        cls.core = {(r['width_bits'], r['experiment']): r
                    for r in cls.results['core_queries']}

    def test_01_original_hashes_identity_label_and_source_correspondence(self):
        self.assertEqual(self.results['dataset_sha256'], local.DATASET_SHA)
        self.assertEqual(self.results['function_body_sha256'], local.BODY_SHA)
        self.assertEqual(self.results['sample_id'], local.SAMPLE_ID)
        self.assertEqual((self.row['index'], self.row['result']), (2, 0))
        self.assertEqual(self.results['original_label'], self.row['result'])
        manifest = local.read_json('source_manifest.json')
        self.assertTrue(manifest['upstream_body_match'])
        self.assertEqual(manifest['source_span'], [176, 199])
        self.assertEqual(manifest['target_division_line'], 189)

    def test_02_changed_dataset_or_body_is_stopped(self):
        raw = local.DATASET.read_bytes()
        with self.assertRaises(local.InputMismatch):
            local.verify_dataset_bytes(raw + b'\n')
        mutated = self.row['function_call'][0].replace('out_min : 1', 'out_min : 0')
        with self.assertRaises(local.InputMismatch):
            local.check_sha(mutated.encode(), local.BODY_SHA, 'mutated source')

    def test_03_source_type_assignment_and_preservation_are_scoped(self):
        evidence = local.read_json('source_evidence.json')
        facts = {f['id']: f for f in evidence['facts']}
        self.assertIn('unsigned long out_min', facts['F_TYPE']['text'])
        self.assertEqual(facts['F_NORMALIZE']['line'], 184)
        self.assertEqual(facts['F_NORMALIZE']['text'].strip(),
                         'out_min = out_min ? out_min : 1;')
        self.assertNotIn('out_min', facts['F_PRESERVE']['text'])
        self.assertIn('clkdco / out_min', facts['F_USE']['text'])
        self.assertFalse(evidence['AST_or_original_build_verified'])

    def test_04_unsigned_widths_and_unsupported_types(self):
        for width in (32, 64):
            self.assertEqual(local.width_check(width), (1 << width) - 1)
        for width in (8, 16, 128, 32.0, True, '64', None):
            with self.subTest(width=width), self.assertRaises(local.UnsupportedSemantics):
                local.encode(width)
        for c_type in ('signed long', 'unsigned int', 'pointer', 'float'):
            with self.subTest(c_type=c_type), self.assertRaises(local.UnsupportedSemantics):
                local.encode(32, c_type)

    def test_05_out_of_range_values_are_not_silently_wrapped(self):
        for width in (32, 64):
            for value in (-1, 1 << width, True, 1.0, '0'):
                with self.subTest(width=width, value=value):
                    with self.assertRaises(local.UnsupportedSemantics):
                        local.reference_normalize(value, width)
        with self.assertRaises(local.UnsupportedSemantics):
            local.normalized_term(z3.Int('not_a_bitvector'), 32)
        with self.assertRaises(local.UnsupportedSemantics):
            local.normalized_term(z3.BitVec('wrong_width', 32), 64)

    def test_06_versions_are_distinct_and_post_uses_pre(self):
        for width in (32, 64):
            enc = local.encode(width)
            self.assertEqual(len({enc[k].decl().name() for k in ('pre', 'post', 'use')}), 3)
            self.assertEqual(enc['term'].arg(0).arg(0).decl().name(),
                             enc['pre'].decl().name())
            self.assertEqual(enc['term'].arg(1).as_long(), 1)
            self.assertTrue(enc['term'].arg(2).eq(enc['pre']))
            self.assertTrue(enc['relations'][1].eq(enc['use'] == enc['post']))
            self.assertFalse(enc['relations'][1].eq(enc['use'] == enc['pre']))

    def test_07_required_boundaries_match_reference_and_smt_models(self):
        records = {(r['width_bits'], r['boundary']): r
                   for r in self.results['boundary_queries']}
        self.assertEqual(len(records), 8)
        for width in (32, 64):
            for label, value, expected in [('zero', 0, 1), ('one', 1, 1), ('two', 2, 2),
                                           ('ULONG_MAX', (1 << width) - 1, (1 << width) - 1)]:
                with self.subTest(width=width, value=value):
                    saved = records[width, label]
                    self.assertEqual(saved['status'], 'SAT')
                    self.assertEqual(saved['input'], value)
                    self.assertEqual(local.reference_normalize(value, width), expected)
                    self.assertEqual(saved['model'], {'pre': value, 'post': expected, 'use': expected})
                    self.assertEqual(saved['independent_reference'], expected)
                    self.assertTrue(saved['independent_match'])

    def test_08_concrete_substitutions_include_unsigned_high_bit(self):
        for width in (32, 64):
            enc = local.encode(width)
            for value in (0, 1, 2, 999, 1 << (width - 1), (1 << width) - 1):
                with self.subTest(width=width, value=value):
                    actual = z3.simplify(z3.substitute(
                        enc['term'], (enc['pre'], z3.BitVecVal(value, width)))).as_long()
                    self.assertEqual(actual, local.reference_normalize(value, width))
                    self.assertGreater(actual, 0)
            # ULONG_MAX must retain its unsigned magnitude instead of becoming -1.
            self.assertEqual(local.reference_normalize((1 << width) - 1, width),
                             (1 << width) - 1)

    def test_09_raw_control_is_sat_and_witness_is_zero(self):
        for width in (32, 64):
            run = self.core[width, 'A']
            self.assertEqual(run['status'], 'SAT')
            self.assertEqual(run['model'], {'pre': 0})
            self.assertEqual(run['independent_verification']['normalized_reference'], 1)
            self.assertNotIn('ite', run['exact_smtlib'])

    def test_10_normalized_core_unsat_with_no_claimed_checked_certificate(self):
        for width in (32, 64):
            run = self.core[width, 'B']
            self.assertEqual(run['status'], 'UNSAT')
            self.assertIsNone(run['model'])
            self.assertFalse(run['unsat_proof']['certificate_generated'])
            self.assertFalse(run['unsat_proof']['independently_checked_solver_proof'])
            self.assertEqual(run['independent_verification']['status'],
                             'MATCH_BY_EXHAUSTIVE_SYMBOLIC_CASE_SPLIT')
            self.assertIn('ite', run['exact_smtlib'])

    def test_11_fault_query_never_assumes_nonzero(self):
        for width in (32, 64):
            enc = local.encode(width)
            query = local.core_constraints(enc, 'B')
            self.assertEqual(len(query), 3)
            self.assertFalse(any(c.eq(enc['division_definedness']) for c in query))
            self.assertTrue(query[-1].eq(enc['use'] == z3.BitVecVal(0, width)))
            replacements = tuple((enc[k], z3.BitVecVal(v, width))
                                 for k, v in [('pre', 0), ('post', 1), ('use', 1)])
            self.assertTrue(all(z3.is_true(z3.simplify(z3.substitute(c, *replacements)))
                                for c in enc['relations']))
            self.assertTrue(z3.is_false(z3.simplify(z3.substitute(query[-1], *replacements))))
            # Binding the use to the old zero would violate the reaching definition.
            wrong = tuple((enc[k], z3.BitVecVal(v, width))
                          for k, v in [('pre', 0), ('post', 1), ('use', 0)])
            self.assertTrue(z3.is_false(z3.simplify(z3.substitute(enc['relations'][1], *wrong))))

    def test_12_saved_smtlib_is_exact_and_contains_no_signed_arithmetic(self):
        queries = self.results['core_queries'] + self.results['boundary_queries']
        for run in queries:
            raw = (local.ROOT / run['smtlib_file']).read_bytes()
            self.assertEqual(raw, run['exact_smtlib'].encode('utf-8'))
            self.assertEqual(local.sha(raw), run['smtlib_sha256'])
            assertions = z3.parse_smt2_string(raw.decode('utf-8'))  # parse, never solve
            self.assertEqual(len(assertions), 1 if run.get('experiment') == 'A' else 3)
            for operator in ('bvslt', 'bvsle', 'bvsgt', 'bvsge', 'bvsdiv'):
                self.assertNotIn(operator, raw.decode('utf-8'))
            self.assertIn('(set-logic QF_BV)', raw.decode('utf-8'))
            self.assertGreaterEqual(run['elapsed_seconds'], 0)

    def test_13_width_domains_differ_but_zero_property_agrees(self):
        self.assertEqual(self.core[32, 'A']['status'], self.core[64, 'A']['status'])
        self.assertEqual(self.core[32, 'B']['status'], self.core[64, 'B']['status'])
        self.assertEqual(local.reference_normalize(0, 32), local.reference_normalize(0, 64))
        with self.assertRaises(local.UnsupportedSemantics):
            local.reference_normalize((1 << 64) - 1, 32)

    def test_14_no_foreign_conditions_or_filter_authority(self):
        self.assertFalse(self.results['prior_constraints_imported'])
        self.assertFalse(self.results['unsigned_division_quotient_encoded'])
        self.assertFalse(self.results['filter_authority'])
        self.assertIsNone(self.results['original_alert_decision'])
        self.assertEqual(self.results['full_program_semantics'], 'UNKNOWN')
        self.assertEqual(self.results['calls'],
                         {'LLM': 0, 'Harness': 0, 'original_analyzer': 0, 'old_regression': 0})
        evidence = local.read_json('source_evidence.json')
        self.assertEqual({r['line'] for r in evidence['uncertified_expressions']}, {187, 192})
        self.assertTrue(all(r['status'] == 'NOT_CERTIFIED'
                            for r in evidence['uncertified_expressions']))

    def test_15_execution_count_and_code_identity(self):
        self.assertEqual(self.results['solver_check_count'], 12)
        self.assertEqual((self.results['core_check_count'], self.results['boundary_check_count']), (4, 8))
        self.assertTrue(self.results['semantic_experiment_checks_passed'])
        self.assertEqual(self.results['implementation_sha256'],
                         local.sha(Path(local.__file__).read_bytes()))
        self.assertEqual(self.results['solver']['version'], z3.get_version_string())
        self.assertEqual(local.SOLVER_CHECKS, 0)  # experiment ran in a separate process


def main():
    if (local.ROOT / 'test_results.json').exists():
        raise FileExistsError('test results already exist; do not overwrite')
    output = io.StringIO()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(NormalizationChecks)
    with mock.patch.object(z3, 'SolverFor', side_effect=AssertionError('test solver forbidden')), \
         mock.patch.object(z3, 'Solver', side_effect=AssertionError('test solver forbidden')):
        result = unittest.TextTestRunner(stream=output, verbosity=2).run(suite)
    document = {'tests_run': result.testsRun, 'failures': len(result.failures),
                'errors': len(result.errors), 'skipped': len(result.skipped),
                'passed': result.wasSuccessful(), 'extra_solver_checks': local.SOLVER_CHECKS,
                'required_boundary_model_observations': 8, 'concrete_substitutions': 12,
                'test_code_sha256': local.sha(Path(__file__).read_bytes()),
                'output': output.getvalue(), 'failure_details': [
                    {'test': str(test), 'traceback': trace}
                    for test, trace in result.failures + result.errors],
                'file_preservation_checked_here': False}
    local.write_new('test_results.json', document)
    print(json.dumps({k: document[k] for k in ('tests_run', 'failures', 'errors', 'passed',
                                               'extra_solver_checks')}))
    if not result.wasSuccessful():
        raise SystemExit(1)


if __name__ == '__main__':
    main()
