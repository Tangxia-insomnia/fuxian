"""Additive test correction: Z3 may print/construct equality as 0 == v0.

The first test file and its failure result stay immutable. No implementation,
semantic contract, formula, or experiment result is changed or rerun.
"""
import io
import json
from pathlib import Path
import unittest
from unittest import mock

import z3
import local_normalization_smt as local
from test_local_normalization import NormalizationChecks


class CorrectedNormalizationChecks(NormalizationChecks):
    def test_06_versions_are_distinct_and_post_uses_pre(self):
        for width in (32, 64):
            enc = local.encode(width)
            self.assertEqual(len({enc[k].decl().name() for k in ('pre', 'post', 'use')}), 3)
            condition = enc['term'].arg(0)
            self.assertTrue(z3.is_eq(condition))
            operands = [condition.arg(i) for i in range(2)]
            self.assertEqual(sum(v.eq(enc['pre']) for v in operands), 1)
            self.assertEqual(sum(v.eq(z3.BitVecVal(0, width)) for v in operands), 1)
            self.assertEqual(enc['term'].arg(1).as_long(), 1)
            self.assertTrue(enc['term'].arg(2).eq(enc['pre']))
            self.assertTrue(enc['relations'][1].eq(enc['use'] == enc['post']))
            self.assertFalse(enc['relations'][1].eq(enc['use'] == enc['pre']))


def main():
    if (local.ROOT / 'test_results_v2.json').exists():
        raise FileExistsError('corrected test results already exist; do not overwrite')
    original = local.read_json('test_results.json')
    if (original['tests_run'], original['failures'], original['errors']) != (15, 1, 0):
        raise RuntimeError('unexpected first-test history; stop')
    output = io.StringIO()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(CorrectedNormalizationChecks)
    with mock.patch.object(z3, 'SolverFor', side_effect=AssertionError('test solver forbidden')), \
         mock.patch.object(z3, 'Solver', side_effect=AssertionError('test solver forbidden')):
        result = unittest.TextTestRunner(stream=output, verbosity=2).run(suite)
    document = {
        'tests_run': result.testsRun, 'failures': len(result.failures),
        'errors': len(result.errors), 'skipped': len(result.skipped),
        'passed': result.wasSuccessful(), 'extra_solver_checks': local.SOLVER_CHECKS,
        'required_boundary_model_observations': 8, 'concrete_substitutions': 12,
        'test_code_sha256': local.sha(Path(__file__).read_bytes()),
        'inherited_test_file': 'test_local_normalization.py',
        'inherited_test_code_sha256': local.sha((local.ROOT / 'test_local_normalization.py').read_bytes()),
        'prior_failure_record': 'test_results.json',
        'prior_failure_record_sha256': local.sha((local.ROOT / 'test_results.json').read_bytes()),
        'correction': 'check both operands of equality by identity; no dependence on operand order',
        'output': output.getvalue(), 'failure_details': [
            {'test': str(test), 'traceback': trace}
            for test, trace in result.failures + result.errors],
        'implementation_contract_and_solver_results_changed': False,
        'experiment_repeated': False, 'file_preservation_checked_here': False,
    }
    local.write_new('test_results_v2.json', document)
    print(json.dumps({k: document[k] for k in ('tests_run', 'failures', 'errors', 'passed',
                                               'extra_solver_checks')}))
    if not result.wasSuccessful():
        raise SystemExit(1)


if __name__ == '__main__':
    main()
