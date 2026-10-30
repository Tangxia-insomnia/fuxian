"""Execute generated Z3 code separately, with bounded solver time and no credentials."""
import ast
import contextlib
import io
import json
import sys
from types import SimpleNamespace
import z3


def execute(source):
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if not ((isinstance(node, ast.ImportFrom) and node.module == 'z3') or (isinstance(node, ast.Import) and all(a.name == 'z3' for a in node.names))):
                raise ValueError('Generated code may only import z3')
        if isinstance(node, ast.Attribute) and node.attr.startswith('_'):
            raise ValueError('Private attribute access rejected')
        if isinstance(node, ast.Name) and node.id.startswith('__'):
            raise ValueError('Private name access rejected')
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {'open', 'exec', 'eval', 'compile', '__import__', 'getattr', 'setattr', 'globals', 'locals', 'input', 'exit', 'quit'}:
            raise ValueError('Unsupported generated-code operation')
    class Z3Imports(ast.NodeTransformer):
        def visit_ImportFrom(self, node):
            replacements = [ast.Assign(targets=[ast.Name(id=a.asname, ctx=ast.Store())], value=ast.Name(id=a.name, ctx=ast.Load())) for a in node.names if a.asname]
            return replacements or ast.Pass()

        def visit_Import(self, node):
            replacements = [ast.Assign(targets=[ast.Name(id=a.asname, ctx=ast.Store())], value=ast.Name(id='z3', ctx=ast.Load())) for a in node.names if a.asname]
            return replacements or ast.Pass()

    tree = ast.fix_missing_locations(Z3Imports().visit(tree))
    queries = []

    class TrackedSolver:
        def __init__(self, *args, **kwargs):
            self.s = z3.Solver(*args, **kwargs)
            self.s.set(timeout=5000)

        def add(self, *args):
            return self.s.add(*args)

        def check(self, *args):
            result = self.s.check(*args)
            queries.append({'result': str(result), 'smt2': self.s.to_smt2()})
            return result

        def model(self): return self.s.model()
        def push(self): return self.s.push()
        def pop(self, *args): return self.s.pop(*args)
        def assertions(self): return self.s.assertions()

    safe = {'int': int, 'bool': bool, 'str': str, 'len': len, 'range': range, 'enumerate': enumerate, 'list': list, 'dict': dict, 'tuple': tuple, 'set': set, 'zip': zip, 'sum': sum, 'min': min, 'max': max, 'abs': abs, 'print': print, 'Exception': Exception, 'ValueError': ValueError}
    allowed = 'Int Ints IntVal Real Reals RealVal Bool Bools BoolVal BitVec BitVecs BitVecVal Array ArraySort Function IntSort RealSort BoolSort BitVecSort Select Store If And Or Not Xor Implies Distinct Sum Product ToReal ToInt IsInt Abs Concat Extract ZeroExt SignExt ULT ULE UGT UGE LShR simplify is_true is_false sat unsat unknown'.split()
    namespace = {k: getattr(z3, k) for k in allowed if hasattr(z3, k)}
    namespace.update({'__builtins__': safe, 'Solver': TrackedSolver})
    namespace['z3'] = SimpleNamespace(**{k: v for k, v in namespace.items() if k != '__builtins__'})
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        exec(compile(tree, '<model_z3>', 'exec'), namespace)
        if 'check_constraints' not in namespace:
            raise ValueError('Missing check_constraints function')
        answer = namespace['check_constraints']()
    if type(answer) is not bool:
        raise ValueError('check_constraints must return a Python boolean')
    if not queries:
        raise ValueError('No actual Solver.check executed')
    if any(q['result'] == 'unknown' for q in queries):
        raise ValueError('Z3 returned unknown; cannot classify')
    if answer != (queries[-1]['result'] == 'sat'):
        raise ValueError('Returned boolean disagrees with last solver result')
    return {'ok': True, 'feasible': answer, 'queries': queries, 'stdout': output.getvalue()}


if __name__ == '__main__':
    try:
        result = execute(json.loads(sys.stdin.read())['source'])
    except Exception as exc:
        result = {'ok': False, 'error': f'{type(exc).__name__}: {exc}'}
    print(json.dumps(result, ensure_ascii=True))
