"""Safety invariants and original-log regression; synthetic results stay separate."""
import copy
import json
from pathlib import Path
import unittest

import z3

from .metrics import evaluate
from .policy import CONDITIONS, decide, digest, replay_last_query, text_digest

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT/'audit/failure_audit_20261029/samples'


def fixture():
    """Fully visible null guard; no macros, calls, aliases, assignments or gotos."""
    code = 'int f(int *p) {\n    if (p == 0) return 0;\n    return *p;\n}\n'
    target = 'return *p;'
    p = z3.Int('p')
    solver = z3.Solver()
    solver.add(p == 0, p != 0)
    assert str(solver.check()) == 'unsat'
    bundle = {
        'scope': 'synthetic_fixture',
        'candidate': {'sample_id': 'synthetic_null_guard', 'status': 'success', 'prediction': 'filter', 'error': None},
        'alert': {'var_name': 'p', 'function_code': code,
                  'location': {'context': {'snippet': {'text': target}}}},
        'context': {'frames': [{'code': code, 'target': target, 'var_name': 'p',
                               'body_sha256': text_digest(code), 'extracted': {
                                   'early_jump_constraints': [{'condition': ['p == 0'], 'text': 'return 0;'}]}}]},
        'recorded_answer': {'result': False}, 'issues': [],
        'solver_events': [{'event_id': 1, 'ok': True, 'feasible': False,
                           'queries': [{'result': 'unsat', 'smt2': solver.to_smt2()}]}],
    }
    replay = replay_last_query(bundle)
    ref = {'source': 'frame/0', 'source_sha256': text_digest(code), 'start_line': 1, 'end_line': 4}
    rationales = {
        'target_location': 'Only one *p in fully visible fixture, at line 3.',
        'control_conditions': 'Only guard exits at line 2; the only sink is after it; no alternate entry.',
        'variable_identity': 'p is one int pointer parameter, never reassigned or aliased, no interprocedural transition.',
        'constraint_semantics': 'Bug needs p==0 at line 3; reaching line 3 requires p!=0 because line 2 returns.',
        'solver_validity': 'Actual independent replay of these two assertions is UNSAT.',
        'context_integrity': 'Whole fixture visible, no missing macros/calls or parsing/modeling issues.',
    }
    review = {
        'scope': 'synthetic_fixture', 'verification_mode': 'synthetic_fixture_review',
        'reviewer': 'explicitly-reviewed-local-fixture', 'reviewed_at': '2026-10-29',
        'evidence_sha256': digest(bundle), 'query_sha256': replay['query_sha256'],
        'unresolved_issues': [],
        'conditions': {k: {'status': 'verified', 'rationale': rationales[k], 'source_refs': [ref]}
                       for k in CONDITIONS},
        'assertion_provenance': [
            {'index': i, 'formula': f, 'role': 'bug_assumption' if i == 0 else 'reachability',
             'rationale': 'Null dereference requirement.' if i == 0 else 'Negation of unconditional null-guard exit.',
             'source_refs': [ref]} for i, f in enumerate(replay['assertions'])],
    }
    return bundle, review


class SafetyTests(unittest.TestCase):
    def test_unsat_alone_is_unknown_and_kept(self):
        bundle, _ = fixture()
        result = decide(bundle)
        self.assertEqual((result['verdict'], result['action']), ('UNKNOWN', 'KEEP'))

    def test_fully_reviewed_simple_guard_can_filter(self):
        bundle, review = fixture()
        result = decide(bundle, review)
        self.assertEqual(result['verdict'], 'FILTER')
        self.assertTrue(result['filter_evidence_complete'])
        self.assertTrue(all(c['status'] == 'verified' for c in result['checks'].values()))

    def test_each_missing_safety_condition_prevents_filter(self):
        for name in CONDITIONS:
            with self.subTest(name=name):
                bundle, review = fixture()
                del review['conditions'][name]
                self.assertEqual(decide(bundle, review)['verdict'], 'UNKNOWN')

    def test_string_true_and_missing_provenance_are_rejected(self):
        bundle, review = fixture()
        review['conditions']['constraint_semantics']['status'] = True
        self.assertEqual(decide(bundle, review)['verdict'], 'UNKNOWN')
        _, review = fixture()
        review['assertion_provenance'] = []
        self.assertEqual(decide(bundle, review)['verdict'], 'UNKNOWN')

    def test_stale_review_after_code_or_query_change_is_rejected(self):
        for kind in ('code', 'query'):
            with self.subTest(kind=kind):
                bundle, review = fixture()
                if kind == 'code':
                    bundle['context']['frames'][0]['code'] += '// changed source\n'
                else:
                    bundle['solver_events'][0]['queries'][0]['smt2'] += '\n; modified query\n'
                self.assertEqual(decide(bundle, review)['verdict'], 'UNKNOWN')

    def test_wrong_source_line_or_hash_prevents_filter(self):
        for field, bad in [('start_line', 0), ('source_sha256', '0'*64), ('end_line', 999)]:
            with self.subTest(field=field):
                bundle, review = fixture()
                review['assertion_provenance'][0]['source_refs'] = [
                    {**review['assertion_provenance'][0]['source_refs'][0], field: bad}]
                self.assertEqual(decide(bundle, review)['verdict'], 'UNKNOWN')

    def test_synthetic_review_cannot_approve_benchmark(self):
        bundle, review = fixture()
        bundle['scope'] = 'benchmark'
        review.update(scope='benchmark', evidence_sha256=digest(bundle))
        self.assertEqual(decide(bundle, review)['verdict'], 'UNKNOWN')

    def test_duplicate_target_and_variable_conflict_cannot_be_approved(self):
        for issue in ('target', 'identity'):
            with self.subTest(issue=issue):
                bundle, review = fixture()
                if issue == 'target':
                    bundle['context']['frames'][0]['code'] += 'return *p;\n'
                    bundle['context']['frames'][0]['body_sha256'] = text_digest(bundle['context']['frames'][0]['code'])
                else:
                    bundle['issues'] = [{'code': 'same_pointer_split_into_independent_symbols'}]
                review['evidence_sha256'] = digest(bundle)
                self.assertEqual(decide(bundle, review)['verdict'], 'UNKNOWN')

    def test_failed_execution_cannot_become_filter_even_with_review(self):
        for status in ('failed', 'blocked_context', 'started'):
            with self.subTest(status=status):
                bundle, review = fixture()
                bundle['candidate']['status'] = status
                review['evidence_sha256'] = digest(bundle)
                self.assertEqual(decide(bundle, review)['verdict'], 'UNKNOWN')

    def test_inconsistent_unknown_missing_solver_and_answer_rejected(self):
        for kind in ('unknown', 'missing', 'boolean', 'answer'):
            with self.subTest(kind=kind):
                bundle, review = fixture()
                if kind == 'missing':
                    bundle['solver_events'] = []
                elif kind == 'boolean':
                    bundle['solver_events'][0]['feasible'] = True
                elif kind == 'answer':
                    bundle['recorded_answer'] = {'result': True}
                else:
                    bundle['solver_events'][0]['queries'][0]['result'] = 'unknown'
                review['evidence_sha256'] = digest(bundle)
                self.assertEqual(decide(bundle, review)['verdict'], 'UNKNOWN')

    def test_raw_a01_a02_a04_a10_not_filtered_without_review(self):
        for aid in ('A01', 'A02', 'A04', 'A10'):
            with self.subTest(audit_id=aid):
                def read(p): return json.loads(p.read_text(encoding='utf-8'))
                folder = AUDIT/aid
                row = read(folder/'recorded_result.json')
                bundle = {'scope': 'benchmark',
                          'candidate': {k: row.get(k) for k in ('sample_id', 'status', 'prediction', 'error')},
                          'alert': {k: v for k, v in read(folder/'original_alert.json').items() if k != 'result'},
                          'context': read(folder/'recorded_raw/context.json'),
                          'recorded_answer': read(folder/'recorded_raw/author_pipeline_output.json'),
                          'solver_events': [read(p) for p in sorted((folder/'recorded_raw').glob('solver_*.json'))],
                          'issues': [{'code': 'unresolved_pointer_identity'}] if aid == 'A04' else []}
                result = decide(bundle)
                self.assertNotEqual(result['verdict'], 'FILTER')
                self.assertEqual(result['action'], 'KEEP')

    def test_candidate_is_independent_of_dataset_labels(self):
        bundle, review = fixture()
        # Label changes are ignored by the gate but invalidate a stale review.
        # Real adapter removes all labels before binding the review.
        for label in (0, 1, -1, None):
            changed = copy.deepcopy(bundle)
            changed['evaluation_label_not_read_by_policy'] = label
            self.assertEqual(decide(changed)['verdict'], 'UNKNOWN')
        from .replay import load_bundle, read
        row = read(ROOT/'results/processed/expanded_all_npd.json')[0]
        left, _ = load_bundle({**row, 'label': 0})
        right, _ = load_bundle({**row, 'label': 1})
        self.assertEqual(left, right)
        self.assertNotIn('result', left['alert'])

    def test_unknown_never_counts_as_filtering_success(self):
        template = {'action': 'KEEP', 'filter_evidence_complete': False, 'decision_seconds': 0,
                    'original_duration_seconds': 1, 'original_api_calls': 0, 'original_cost_upper_cny': 0,
                    'new_model_calls': 0, 'new_api_cost_cny': 0, 'original_status': 'failed'}
        rows = [{**template, 'sample_id': str(y), 'dataset_label': y, 'verdict': 'UNKNOWN'} for y in (0, 1)]
        result = evaluate(rows)
        self.assertEqual(result['false_positive_filter_rate'], 0)
        self.assertEqual(result['operational_real_bug_retention_rate'], 1)
        self.assertEqual(result['explicit_keep_real_bug_rate'], 0)
        self.assertEqual(result['real_bug_deletion_rate'], 0)
        self.assertIsNone(result['precision'])
        self.assertIsNone(result['f1'])
        with self.assertRaises(ValueError):
            evaluate([{**rows[0], 'action': 'FILTER'}])

    def test_malformed_evidence_and_review_fail_closed(self):
        for malformed in (None, {}, {'candidate': None}, {'candidate': {}, 'solver_events': [None]}):
            with self.subTest(value=malformed):
                result = decide(malformed)
                self.assertEqual((result['verdict'], result['action']), ('UNKNOWN', 'KEEP'))
        bundle, review = fixture()
        review['assertion_provenance'] = [None, None]
        self.assertEqual(decide(bundle, review)['verdict'], 'UNKNOWN')

    def test_mixed_metrics_do_not_hide_deleted_bug_or_unknown(self):
        template = {'decision_seconds': 0, 'original_duration_seconds': 1, 'original_api_calls': 0,
                    'original_cost_upper_cny': 0, 'new_model_calls': 0, 'new_api_cost_cny': 0}
        rows = [{**template, 'sample_id': str(i), 'dataset_label': y, 'verdict': verdict,
                 'action': 'FILTER' if verdict == 'FILTER' else 'KEEP',
                 'filter_evidence_complete': verdict == 'FILTER'}
                for i, (y, verdict) in enumerate([(0, 'FILTER'), (0, 'UNKNOWN'), (1, 'FILTER'), (1, 'UNKNOWN')])]
        result = evaluate(rows)
        self.assertEqual(result['confusion_matrix']['values'], [[1, 0, 1], [1, 0, 1]])
        self.assertEqual(result['real_bug_deletion_rate'], 0.5)
        self.assertEqual(result['operational_real_bug_retention_rate'], 0.5)
        self.assertEqual(result['false_positive_filter_rate'], 0.5)
        self.assertEqual(result['real_bug_deletion_cases'], ['2'])
        result = evaluate([rows[2]])
        self.assertEqual((result['precision'], result['recall']), (0.0, None))
        self.assertIsNone(result['f1'])
        result = evaluate([rows[1], rows[2]])
        self.assertEqual(result['f1'], 0.0)

    def test_unverified_labels_not_silently_converted_to_truth(self):
        template = {'sample_id': 'unlabeled', 'dataset_label': True, 'verdict': 'KEEP', 'action': 'KEEP',
                    'filter_evidence_complete': False, 'decision_seconds': 0, 'original_duration_seconds': 1,
                    'original_api_calls': 0, 'original_cost_upper_cny': 0, 'new_model_calls': 0, 'new_api_cost_cny': 0}
        result = evaluate([template])
        self.assertEqual(result['real_bug_count'], 0)
        self.assertEqual(result['unverified_or_missing_label_count'], 1)
        self.assertIsNone(result['operational_real_bug_retention_rate'])


if __name__ == '__main__':
    unittest.main()
