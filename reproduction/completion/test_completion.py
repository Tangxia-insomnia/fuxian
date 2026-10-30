"""Meaningful local tests; synthetic cases never count as benchmark results."""
import unittest
from .context import calls, called_function, parameter_name, direct_dereference, ContextUnavailable, ContextRepository
from .solver_worker import execute
from .engine import completed_source, load_extractor
from .metrics import evaluate


class InfrastructureTests(unittest.TestCase):
    def test_false_alarm_positive_metrics_keep_failures(self):
        rows = [{'label': y, 'prediction': p, 'status': status, 'duration_seconds': 1, 'api_calls': 0, 'cost_upper_bound_cny': 0} for y,p,status in [(0,'filter','success'),(0,'keep','success'),(1,'filter','success'),(1,'keep','success'),(0,None,'failed')]]
        result = evaluate(rows)
        self.assertEqual(result['confusion_matrix']['values'], [[1,1],[1,1]])
        self.assertEqual(result['false_positive_filter_rate'], 1/3)
        self.assertEqual(result['precision'], 0.5)
        self.assertEqual(result['success_rate'], 4/5)

    def test_balanced_arguments_and_comments(self):
        source = '/* a long comment */ f(p, g(a,b), "fake(call)");'
        found = calls(source)
        f = next(x for x in found if x['name'] == 'f')
        self.assertEqual(f['arguments'], ['p', 'g(a,b)', '"fake(call)"'])
        self.assertEqual(called_function('p', source), 'f')

    def test_parameter_mapping_and_ambiguity(self):
        code = 'int consume(int n, struct item *item) { return item->value; }'
        self.assertEqual(parameter_name('p', 'consume(1, p);', code), 'item')
        with self.assertRaises(ContextUnavailable):
            parameter_name('p', 'consume(p, p);', code)
        with self.assertRaises(ContextUnavailable):
            called_function('p', 'f(p) + g(p)')
        with self.assertRaises(ContextUnavailable):
            called_function('p', 'f(p->child)')

    def test_dereference_not_multiplication(self):
        self.assertTrue(direct_dereference('p', 'return p->value;'))
        self.assertTrue(direct_dereference('p', 'x = *p;'))
        self.assertFalse(direct_dereference('p', 'x = n * p;'))
        self.assertFalse(direct_dereference('p', 'consume(p);'))

    def test_actual_z3_sat_unsat(self):
        for condition, expected in [('x == 0', True), ('And(x == 0, x != 0)', False)]:
            result = execute('def check_constraints():\n    x = Int("x")\n    s = Solver()\n    s.add(' + condition + ')\n    return s.check() == sat\n')
            self.assertEqual(result['feasible'], expected)
            self.assertEqual(len(result['queries']), 1)

    def test_no_solver_and_non_boolean_rejected(self):
        with self.assertRaisesRegex(ValueError, 'No actual'):
            execute('def check_constraints():\n    return True\n')
        with self.assertRaisesRegex(ValueError, 'boolean'):
            execute('def check_constraints():\n    return "False"\n')
        with self.assertRaises(ValueError):
            execute('import os\ndef check_constraints(): return True')

    def test_nested_z3_imports_and_alias(self):
        for prefix, solver, integer, sat_value in [('from z3 import Solver, Int, sat', 'Solver', 'Int', 'sat'), ('import z3 as smt', 'smt.Solver', 'smt.Int', 'smt.sat')]:
            result = execute(f'def check_constraints():\n    {prefix}\n    x = {integer}("x")\n    s = {solver}()\n    s.add(x == 0)\n    return s.check() == {sat_value}\n')
            self.assertTrue(result['feasible'])

    def test_uninterpreted_function_constraints(self):
        source = '''def check_constraints():
    from z3 import Function, IntSort, BoolSort, Solver, Int, Not, sat
    predicate = Function('predicate', IntSort(), BoolSort())
    x = Int('x')
    s = Solver()
    s.add(predicate(x), Not(predicate(x)))
    return s.check() == sat
'''
        result = execute(source)
        self.assertFalse(result['feasible'])
        self.assertEqual(result['queries'][0]['result'], 'unsat')
        self.assertIn('declare-fun predicate', result['queries'][0]['smt2'])

    def test_real_sample_context_mapping(self):
        repo = ContextRepository()
        for row in [21, 23, 34, 35, 65]:
            ctx = repo.prepare(row)
            self.assertGreaterEqual(len(ctx['frames']), 1)
            self.assertIn(ctx['frames'][0]['target'].strip(), ctx['frames'][0]['code'])
        ctx = repo.prepare(21)
        self.assertEqual(ctx['frames'][1]['var_name'], 'net')
        self.assertEqual(ctx['frames'][1]['function'], 'ip6_sublist_rcv')
        self.assertEqual(ctx['frames'][1]['sink_kind'], 'author_historical_macro_or_call_sink')

    def test_author_source_loads_with_patches(self):
        compile(completed_source(), '<completed>', 'exec')
        extractor = load_extractor()
        source = 'int f(int *p) {\n\tif (p) {\n\t\treturn *p;\n\t}\n\treturn 0;\n}'
        self.assertIn('bug_line_constraints', extractor['extract_conditions']('p', None, '\t\treturn *p;', source))


if __name__ == '__main__':
    unittest.main()
