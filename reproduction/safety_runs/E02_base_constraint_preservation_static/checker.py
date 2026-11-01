"""E02: bounded structural constraint preservation; never imports or calls Z3.

SMT-LIB is parsed into S-expressions. Historical Python is inspected as AST only.
PASS means exact structural preservation within this grammar, never C correctness,
logical equivalence, solver validity, or an alert safety decision.
"""
import ast
from collections import Counter, defaultdict
from dataclasses import dataclass, field
import hashlib
import json
import re
import time

VERSION = 'e02-static-contract-v1'


class Unsupported(ValueError):
    pass


def sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def sexpr(node):
    return '(' + ' '.join(map(sexpr, node)) + ')' if isinstance(node, tuple) else node


def expressions(text):
    """Parse bounded SMT-LIB tokens, comments, quoted names and parentheses."""
    if len(text) > 300000:
        raise Unsupported('input_too_large')
    tokens, i = [], 0
    while i < len(text):
        c = text[i]
        if c.isspace():
            i += 1
        elif c == ';':
            j = text.find('\n', i)
            i = len(text) if j < 0 else j + 1
        elif c in '()':
            tokens.append(c); i += 1
        elif c == '|':
            j = text.find('|', i + 1)
            if j < 0 or '\\' in text[i+1:j]:
                raise Unsupported('unsupported_quoted_symbol')
            name = text[i+1:j]
            if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.$:-]*', name):
                raise Unsupported('quoted_symbol_outside_subset')
            tokens.append(name); i = j + 1
        elif c == '"':
            # Strings are metadata only in the supported grammar.
            j = i + 1
            while j < len(text):
                if text[j] == '"':
                    if j+1 < len(text) and text[j+1] == '"':
                        j += 2; continue
                    break
                j += 1
            if j == len(text):
                raise Unsupported('unterminated_string')
            tokens.append(text[i:j+1]); i = j+1
        else:
            j = i
            while j < len(text) and not text[j].isspace() and text[j] not in '();':
                j += 1
            tokens.append(text[i:j]); i = j
    pos = 0

    def take(depth=0):
        nonlocal pos
        if depth > 80 or pos >= len(tokens):
            raise Unsupported('invalid_or_deep_sexpression')
        token = tokens[pos]; pos += 1
        if token == ')':
            raise Unsupported('unexpected_close_parenthesis')
        if token != '(':
            return token
        out = []
        while pos < len(tokens) and tokens[pos] != ')':
            out.append(take(depth+1))
        if pos == len(tokens):
            raise Unsupported('unclosed_parenthesis')
        pos += 1
        return tuple(out)

    result = []
    while pos < len(tokens):
        result.append(take())
    return result


def sort_name(node):
    if isinstance(node, str) and node in {'Int', 'Bool', 'Real'}:
        return node
    if (isinstance(node, tuple) and len(node) == 3 and node[:2] == ('_', 'BitVec')
            and node[2].isdigit() and 0 < int(node[2]) <= 256):
        return 'BitVec:' + str(int(node[2]))
    raise Unsupported('sort_outside_subset:' + sexpr(node))


def valid_symbol(symbol):
    if not isinstance(symbol, str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.$:-]*', symbol) or symbol in {'true', 'false', 'let', 'forall', 'exists'}:
        raise Unsupported('symbol_outside_subset')


def term(node, declarations, lets=None):
    """Expand lexical let bindings, validate a small typed scalar grammar.

    No rewriting by commutativity, implication, simplification, or satisfiability.
    """
    lets = lets or {}
    if isinstance(node, str):
        if node in lets:
            return lets[node]
        if node in {'true', 'false'}:
            return node, 'Bool'
        if re.fullmatch(r'\d+', node):
            return str(int(node)), 'Int'
        if re.fullmatch(r'\d+\.\d+', node):
            return node, 'Real'
        if node in declarations and len(declarations[node]) == 1:
            return node, next(iter(declarations[node]))
        raise Unsupported('unknown_or_ambiguous_symbol:' + node)
    if not node:
        raise Unsupported('empty_term')
    op, *args = node
    if op == 'let' and len(args) == 2 and isinstance(args[0], tuple):
        additions = {}
        for item in args[0]:
            if not isinstance(item, tuple) or len(item) != 2 or not isinstance(item[0], str):
                raise Unsupported('invalid_let')
            if item[0] in additions:
                raise Unsupported('duplicate_let_binding')
            additions[item[0]] = term(item[1], declarations, lets)
        return term(args[1], declarations, {**lets, **additions})
    if op == '_' and len(args) == 2 and isinstance(args[0], str) and re.fullmatch(r'bv\d+', args[0]):
        width = int(args[1]) if str(args[1]).isdigit() else 0
        if 0 < width <= 256:
            return tuple(node), 'BitVec:' + str(width)
    if not isinstance(op, str):
        raise Unsupported('indexed_operator_outside_subset')
    if op not in {'=', 'distinct', '<', '<=', '>', '>=', 'and', 'or', 'not', '=>',
                  '+', '-', '*', 'ite'}:
        raise Unsupported('operator_outside_subset:' + op)
    values = [term(a, declarations, lets) for a in args]
    sorts = [s for _, s in values]
    if op in {'and', 'or', 'not', '=>'}:
        valid = all(s == 'Bool' for s in sorts) and (len(args) == 1 if op == 'not' else len(args) == 2 if op == '=>' else True)
        result_sort = 'Bool'
    elif op in {'=', 'distinct', '<', '<=', '>', '>='}:
        valid = len(args) >= 2 and len(set(sorts)) == 1
        if op in {'<', '<=', '>', '>='}:
            valid = valid and len(args) == 2 and sorts[0] in {'Int', 'Real'}
        result_sort = 'Bool'
    elif op == 'ite':
        valid = len(args) == 3 and sorts[0] == 'Bool' and sorts[1] == sorts[2]
        result_sort = sorts[1] if len(sorts) > 1 else ''
    else:
        valid = bool(args) and len(set(sorts)) == 1 and sorts[0] in {'Int', 'Real'}
        result_sort = sorts[0] if sorts else ''
    if not valid:
        raise Unsupported('ill_typed_or_wrong_arity:' + op)
    return (op, *(v for v, _ in values)), result_sort


@dataclass
class IR:
    declarations: list = field(default_factory=list)
    assertions: list = field(default_factory=list)
    bindings: list = field(default_factory=list)
    issues: list = field(default_factory=list)
    snapshots: list = field(default_factory=list)
    resets: list = field(default_factory=list)
    source: dict = field(default_factory=dict)

    def env(self):
        out = defaultdict(set)
        for d in self.declarations:
            out[d['symbol']].add(d['sort'])
        return out

    def payload(self):
        return {k: getattr(self, k) for k in self.__dataclass_fields__}


def smt_ir(text, ref, inherited=None):
    ir = IR(source={'reference': ref, 'sha256': sha(text), 'format': 'smtlib'})
    env = defaultdict(set)
    for k, v in (inherited or {}).items():
        env[k].update(v)
    declared_here = set()
    for index, cmd in enumerate(expressions(text)):
        if not isinstance(cmd, tuple) or not cmd:
            raise Unsupported('expected_smt_command')
        name = cmd[0]; origin = {'reference': ref, 'command_index': index, 'source_sha256': sha(text)}
        if name in {'set-logic', 'set-info', 'set-option', 'check-sat', 'exit'}:
            # No command is executed. check-sat is just an input boundary marker.
            if name == 'check-sat':
                ir.snapshots.append({'boundary': 'check-sat', 'assertion_count': len(ir.assertions), 'declaration_count':len(ir.declarations)})
        elif name == 'declare-const' and len(cmd) == 3:
            symbol, kind = cmd[1], sort_name(cmd[2])
            valid_symbol(symbol)
            ir.declarations.append({'symbol': symbol, 'sort': kind, 'origin': origin})
            if symbol not in declared_here:
                env[symbol] = set(); declared_here.add(symbol)
            env[symbol].add(kind)
        elif name == 'declare-fun' and len(cmd) == 4 and cmd[2] == ():
            symbol, kind = cmd[1], sort_name(cmd[3])
            valid_symbol(symbol)
            ir.declarations.append({'symbol': symbol, 'sort': kind, 'origin': origin})
            if symbol not in declared_here:
                env[symbol] = set(); declared_here.add(symbol)
            env[symbol].add(kind)
        elif name == 'assert' and len(cmd) == 2:
            expression, kind = term(cmd[1], env)
            if kind != 'Bool':
                raise Unsupported('assertion_not_boolean')
            ir.assertions.append({'formula': sexpr(expression), 'origin': origin})
        else:
            raise Unsupported('smt_command_outside_subset:' + str(name))
    if ir.snapshots:
        ir.assertions = ir.assertions[:ir.snapshots[-1]['assertion_count']]
        ir.declarations = ir.declarations[:ir.snapshots[-1]['declaration_count']]
    return ir


def code_block(text):
    blocks = re.findall(r'```(?:python)?\s*\n(.*?)```', text, re.S)
    if len(blocks) > 1:
        raise Unsupported('multiple_code_blocks')
    if blocks:
        if re.sub(r'```(?:python)?\s*\n.*?```', '', text, flags=re.S).strip():
            raise Unsupported('text_outside_code_block')
        return blocks[0]
    return text


def python_ir(text, ref, inherited=None):
    """Extract literal construction patterns. Never eval, exec, import, or solve.

    For final functions, retain only assertions in the last syntactically recorded
    query's solver. Reset/new-solver history remains visible. Branches/loops are
    unsupported; their bodies are never guessed to be reachable.
    """
    code = code_block(text)
    if len(code) > 300000:
        raise Unsupported('input_too_large')
    tree = ast.parse(code)
    ir = IR(source={'reference': ref, 'sha256': sha(text), 'format': 'python_ast'})
    env = defaultdict(set)
    for k, v in (inherited or {}).items():
        env[k].update(v)
    names, solvers, statements, last_query = {}, {}, [], None
    declared_here = set()
    solver_counter = 0
    saw_function = False
    stop = False

    def origin(node):
        return {'reference': ref, 'line': node.lineno, 'source_sha256': sha(text)}

    def name_of(node):
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == 'z3':
            return node.attr
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            return node.value.id + '.' + node.attr
        raise Unsupported('dynamic_call_target')

    def expression(node):
        if isinstance(node, ast.Name):
            if node.id in names:
                return names[node.id]
            if node.id in env and len(env[node.id]) == 1:
                return node.id
            raise Unsupported('unbound_python_name:' + node.id)
        if isinstance(node, ast.Constant):
            if type(node.value) is bool:
                return 'true' if node.value else 'false'
            if type(node.value) is int:
                return str(node.value) if node.value >= 0 else ('-', str(-node.value))
            raise Unsupported('literal_outside_subset')
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return ('-', expression(node.operand))
        if isinstance(node, ast.Compare) and len(node.ops) == 1:
            op = {ast.Eq: '=', ast.NotEq: 'distinct', ast.Lt: '<', ast.LtE: '<=', ast.Gt: '>', ast.GtE: '>='}.get(type(node.ops[0]))
            if op:
                left, right = expression(node.left), expression(node.comparators[0])
                # Literal coercion performed by Z3Py for a BV equality only.
                # No C pointer width is inferred here: the constructor gave it.
                if op in {'=', 'distinct'}:
                    ls, rs = term(left, env)[1], term(right, env)[1]
                    if ls.startswith('BitVec:') and isinstance(right, str) and right.isdigit() and int(right) < 2**int(ls.split(':')[1]):
                        right = ('_', 'bv' + right, ls.split(':')[1])
                    elif rs.startswith('BitVec:') and isinstance(left, str) and left.isdigit() and int(left) < 2**int(rs.split(':')[1]):
                        left = ('_', 'bv' + left, rs.split(':')[1])
                return (op, left, right)
        if isinstance(node, ast.BinOp):
            op = {ast.Add: '+', ast.Sub: '-', ast.Mult: '*'}.get(type(node.op))
            if op:
                return (op, expression(node.left), expression(node.right))
        if isinstance(node, ast.Call) and not node.keywords:
            name = name_of(node.func)
            op = {'And': 'and', 'Or': 'or', 'Not': 'not', 'Implies': '=>', 'If': 'ite', 'Distinct': 'distinct'}.get(name)
            if op:
                return (op, *(expression(x) for x in node.args))
            if name in {'IntVal', 'BoolVal'} and len(node.args) == 1:
                return expression(node.args[0])
        raise Unsupported('python_expression_outside_subset:' + type(node).__name__)

    def solver_call(node):
        nonlocal last_query
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute) or not isinstance(node.func.value, ast.Name):
            return False
        var, method = node.func.value.id, node.func.attr
        if var not in solvers:
            return False
        identity = solvers[var]
        if node.keywords:
            raise Unsupported('solver_keywords_not_supported')
        if method == 'add':
            for a in node.args:
                value, kind = term(expression(a), env)
                if kind != 'Bool':
                    raise Unsupported('assertion_not_boolean')
                statements.append({'formula': sexpr(value), 'solver': identity, 'origin': origin(a)})
            return True
        if method == 'check' and not node.args:
            last_query = identity
            ir.snapshots.append({'solver': identity, 'line': node.lineno,
                                 'assertion_indices': [i for i, x in enumerate(statements) if x['solver'] == identity],
                                 'declaration_count':len(ir.declarations),'binding_count':len(ir.bindings)})
            return True
        if method == 'model' and not node.args:
            return True  # textual diagnostic, no model is obtained
        raise Unsupported('solver_operation_outside_subset:' + method)

    def visit(body):
        nonlocal solver_counter, saw_function, stop
        for node in body:
            if stop:
                raise Unsupported('statements_after_return')
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                allowed = (isinstance(node, ast.ImportFrom) and node.module == 'z3' and all(x.asname is None for x in node.names)) or (isinstance(node, ast.Import) and all(x.name == 'z3' and x.asname is None for x in node.names))
                if not allowed:
                    raise Unsupported('import_outside_subset')
            elif isinstance(node, ast.FunctionDef):
                if saw_function or node.name != 'check_constraints' or node.args.args or node.decorator_list:
                    raise Unsupported('function_outside_subset')
                saw_function = True
                visit(node.body)
            elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                target, value = node.targets[0].id, node.value
                if isinstance(value, ast.Call) and name_of(value.func) in {'Int', 'Bool', 'Real', 'BitVec'} and not value.keywords:
                    constructor = name_of(value.func)
                    if not value.args or not isinstance(value.args[0], ast.Constant) or type(value.args[0].value) is not str:
                        raise Unsupported('nonliteral_symbol_name')
                    symbol = value.args[0].value
                    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.$:-]*', symbol):
                        raise Unsupported('symbol_name_outside_subset')
                    if constructor == 'BitVec':
                        if len(value.args) != 2 or not isinstance(value.args[1], ast.Constant) or type(value.args[1].value) is not int or not 0 < value.args[1].value <= 256:
                            raise Unsupported('invalid_bitvector_width')
                        kind = 'BitVec:' + str(value.args[1].value)
                    elif len(value.args) == 1:
                        kind = constructor
                    else:
                        raise Unsupported('declaration_arity')
                    if target in names and names[target] != symbol:
                        ir.issues.append({'code': 'python_binding_reassigned', 'python_name': target, 'old': names[target], 'new': symbol})
                    names[target] = symbol
                    if symbol not in declared_here:
                        env[symbol] = set(); declared_here.add(symbol)
                    env[symbol].add(kind)
                    ir.declarations.append({'symbol': symbol, 'sort': kind, 'origin': origin(node)})
                    ir.bindings.append({'python_name': target, 'symbol': symbol, 'sort': kind, 'origin': origin(node)})
                elif isinstance(value, ast.Call) and name_of(value.func) == 'Solver' and not value.args and not value.keywords:
                    solver_counter += 1
                    identity = f'solver/{solver_counter}'
                    if solvers:
                        ir.resets.append({'new_solver': identity, 'variable': target, 'previous': dict(solvers), 'origin': origin(node)})
                    solvers[target] = identity
                elif solver_call(value):
                    # Only textual check result binding, never a Python value.
                    if value.func.attr != 'check':
                        raise Unsupported('assigned_noncheck_solver_call')
                    names[target] = ('query-result', solvers[value.func.value.id])
                else:
                    names[target] = expression(value)
            elif isinstance(node, ast.Expr):
                if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                    continue
                if solver_call(node.value):
                    continue
                if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name) and node.value.func.id == 'print':
                    for a in node.value.args:
                        if isinstance(a, ast.Constant):
                            continue
                        if not solver_call(a):
                            term(expression(a), env)  # only a side-effect-free scalar
                else:
                    raise Unsupported('statement_expression_outside_subset')
            elif isinstance(node, ast.Return):
                # Accept a check result == sat/unsat expression only as a query
                # boundary. Its boolean semantics are deliberately not evaluated.
                v = node.value
                if isinstance(v, ast.Compare) and len(v.ops) == 1 and isinstance(v.ops[0], ast.Eq) and isinstance(v.comparators[0], ast.Name) and v.comparators[0].id in {'sat', 'unsat', 'unknown'}:
                    if isinstance(v.left, ast.Call):
                        if not solver_call(v.left) or v.left.func.attr != 'check':
                            raise Unsupported('return_not_query_result')
                    elif not (isinstance(v.left, ast.Name) and isinstance(names.get(v.left.id), tuple) and names[v.left.id][0] == 'query-result' and names[v.left.id][1] == last_query):
                        raise Unsupported('return_uses_unbound_query')
                else:
                    raise Unsupported('return_protocol_outside_subset')
                stop = True
            elif isinstance(node, ast.Pass):
                continue
            elif isinstance(node, ast.If) and not node.orelse:
                # A trailing generated diagnostic often prints a model under a
                # check==sat guard. Accept ONLY print(model()) bodies; no branch
                # containing add/assign/return is inspected as an unconditional path.
                test = node.test
                diagnostic = (isinstance(test, ast.Compare) and len(test.ops) == 1
                              and isinstance(test.ops[0], ast.Eq) and isinstance(test.left, ast.Call)
                              and isinstance(test.comparators[0], ast.Name) and test.comparators[0].id == 'sat')
                for statement in node.body:
                    v = statement.value if isinstance(statement, ast.Expr) else None
                    diagnostic = diagnostic and isinstance(v, ast.Call) and isinstance(v.func, ast.Name) and v.func.id == 'print' and not v.keywords
                    if diagnostic:
                        for argument in v.args:
                            if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                                continue
                            diagnostic = diagnostic and isinstance(argument, ast.Call) and isinstance(argument.func, ast.Attribute) and argument.func.attr == 'model' and isinstance(argument.func.value, ast.Name) and argument.func.value.id in solvers and not argument.args and not argument.keywords
                if not diagnostic or not solver_call(test.left) or test.left.func.attr != 'check':
                    raise Unsupported('conditional_control_flow_outside_subset')
            else:
                raise Unsupported('python_statement_outside_subset:' + type(node).__name__)

    visit(tree.body)
    if saw_function and not ir.snapshots:
        raise Unsupported('final_function_without_query_boundary')
    if last_query is None:
        # Fragments implicitly use an existing solver named s. Full functions do not.
        if len(set(solvers.values())) > 1:
            raise Unsupported('multiple_solvers_without_query_boundary')
        active = set(solvers.values()) or {'fragment/s'}
        ir.assertions = [x for x in statements if x['solver'] in active]
    else:
        snapshot = ir.snapshots[-1]
        ir.assertions = [statements[i] for i in snapshot['assertion_indices']]
        ir.declarations = ir.declarations[:snapshot['declaration_count']]
        ir.bindings = ir.bindings[:snapshot['binding_count']]
    ir.snapshots.append({'all_recorded_assertions': statements, 'selected_query_solver': last_query})
    return ir


def parse(text, fmt, ref, inherited=None):
    if fmt == 'smtlib':
        return smt_ir(text, ref, inherited)
    if fmt == 'python':
        return python_ir(text, ref, inherited)
    raise Unsupported('unknown_format')


def _parse(text, fmt, ref, inherited=None):
    # s.add in fragments denotes the pre-existing solver. Prefixing an AST literal
    # constructor creates no solver at runtime and keeps the original lines intact.
    if fmt != 'python':
        return parse(text, fmt, ref, inherited)
    code = code_block(text)
    tree = ast.parse(code)
    has_solver = any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'Solver' for n in ast.walk(tree))
    if not has_solver and not any(isinstance(n, ast.FunctionDef) for n in tree.body):
        # Explicitly describe the fragment's assumed receiver in the static AST.
        ir = python_ir('s = Solver()\n' + code, ref, inherited)
        ir.source = {'reference': ref, 'sha256': sha(text), 'format': 'python_ast_fragment', 'implicit_receiver': 's'}
        for item in ir.declarations + ir.assertions + ir.bindings:
            item['origin']['line'] -= 1
            item['origin']['source_sha256'] = sha(text)
        return ir
    return python_ir(text, ref, inherited)


def check_contract(base, delta, final, *, formats=('smtlib', 'smtlib', 'smtlib'),
                   refs=('B', 'delta', 'Final'), extra_deltas=()):
    """Check exact declarations/assertions; no equivalence or safety decisions.

    extra_deltas permits explicit U09 second input sets with their own provenance.
    Missing evidence is None; an actually empty delta is the empty string.
    """
    start = time.perf_counter()
    out = {'checker_version': VERSION, 'contract_status': 'UNKNOWN', 'reasons': [],
           'scope': 'exact structural B+delta preservation only', 'semantic_correctness': 'NOT_ASSESSED',
           'polarity_correctness': 'NOT_ASSESSED', 'solver_executed': False,
           'alert_safety_decision': None, 'counts': {}, 'inputs': {}, 'ir': {}}
    if any(x is None for x in (base, delta, final)):
        out['reasons'] = ['missing_B_delta_or_Final_evidence']
        out['seconds'] = time.perf_counter() - start
        return out
    parsed, env, errors = {}, defaultdict(set), []
    chunks = [('B', base, formats[0], refs[0]), ('delta', delta, formats[1], refs[1])]
    chunks += [('delta_extra_' + str(i), x['text'], x['format'], x['reference']) for i, x in enumerate(extra_deltas)]
    chunks += [('Final', final, formats[2], refs[2])]
    for role, text, fmt, ref in chunks:
        out['inputs'][role] = {'reference': ref, 'sha256': sha(text), 'format': fmt}
        try:
            # Expected sorts let us read a reference whose final declaration was
            # lost, but do NOT add that declaration to Final: it is still missing.
            ir = _parse(text, fmt, ref, env)
            parsed[role] = ir
            if role != 'Final':
                for k, kinds in ir.env().items():
                    env[k].update(kinds)
            out['ir'][role] = ir.payload()
        except (Unsupported, SyntaxError, RecursionError, ValueError, TypeError) as exc:
            errors.append({'role': role, 'error': str(exc)})
    if errors:
        out.update(parse_errors=errors, reasons=['UNSUPPORTED_input_or_expression'])
        out['seconds'] = time.perf_counter() - start
        return out
    required = [ir for role, ir in parsed.items() if role != 'Final']
    req_decls = {(d['symbol'], d['sort']) for ir in required for d in ir.declarations}
    got_decls = {(d['symbol'], d['sort']) for d in parsed['Final'].declarations}
    missing_decls = sorted(req_decls - got_decls)
    final_asserts = Counter(x['formula'] for x in parsed['Final'].assertions)
    # Duplicate assertions are idempotent for this presence contract; multiplicity
    # is reported, not silently removed from the stored inputs or extracted IR.
    required_asserts = {x['formula'] for ir in required for x in ir.assertions}
    missing_base = sorted({x['formula'] for x in parsed['B'].assertions} - final_asserts.keys())
    missing_delta = sorted({x['formula'] for role, ir in parsed.items() if role not in {'B', 'Final'} for x in ir.assertions} - final_asserts.keys())
    extra = sorted(final_asserts.keys() - required_asserts)
    kinds = defaultdict(set)
    for symbol, kind in req_decls | got_decls:
        kinds[symbol].add(kind)
    conflicts = {k: sorted(v) for k, v in kinds.items() if len(v) > 1}
    req_bindings = {(b['python_name'], b['symbol'], b['sort']) for ir in required for b in ir.bindings}
    final_bindings = {(b['python_name'], b['symbol'], b['sort']) for b in parsed['Final'].bindings}
    binding_conflicts = [dict(python_name=n, expected_symbol=s, final_symbols=sorted({fs for fn, fs, _ in final_bindings if fn == n}))
                         for n, s, _ in sorted(req_bindings) if any(fn == n and fs != s for fn, fs, _ in final_bindings)]
    extra_symbols = sorted({n for n, _ in got_decls - req_decls})
    extra_declarations = sorted(got_decls - req_decls)
    lost_symbols = sorted({n for n, _ in req_decls - got_decls})
    identity_conflicts = binding_conflicts + [{'missing_symbol': n, 'unbound_replacement_candidates': extra_symbols}
                                             for n in lost_symbols if extra_symbols]
    duplicates = {}
    duplicate_declarations = {}
    for role, ir in parsed.items():
        ac = Counter(x['formula'] for x in ir.assertions)
        dc = Counter((x['symbol'], x['sort']) for x in ir.declarations)
        duplicates[role] = sum(v-1 for v in ac.values() if v > 1)
        duplicate_declarations[role] = sum(v-1 for v in dc.values() if v > 1)
    out['counts'] = {'missing_base_assertions': len(missing_base), 'missing_delta_assertions': len(missing_delta),
                     'missing_declarations': len(missing_decls), 'symbol_identity_conflicts': len(identity_conflicts),
                     'type_conflicts': len(conflicts), 'duplicate_assertions': sum(duplicates.values()),
                     'duplicate_declarations': sum(duplicate_declarations.values()),
                     'extra_final_assertions': len(extra), 'extra_final_declarations':len(extra_declarations),
                     'solver_recreations': len(parsed['Final'].resets)}
    out.update(missing_base_assertions=missing_base, missing_delta_assertions=missing_delta,
               missing_declarations=missing_decls, type_conflicts=conflicts,
               identity_conflicts=identity_conflicts, unexpected_final_assertions=extra,
               duplicate_assertions_by_role=duplicates, duplicate_declarations_by_role=duplicate_declarations,
               expected_declarations=sorted(req_decls), observed_declarations=sorted(got_decls),
               unexpected_final_declarations=extra_declarations)
    reasons = []
    for condition, code in [(missing_base, 'base_assertions_missing'), (missing_delta, 'delta_assertions_missing'),
                            (missing_decls, 'declarations_missing'), (conflicts, 'symbol_type_conflict'),
                            (identity_conflicts, 'symbol_identity_mapping_missing')]:
        if condition:
            reasons.append(code)
    if parsed['Final'].resets and missing_base:
        reasons.append('new_solver_did_not_reload_base')
    if any(ir.issues for ir in parsed.values()):
        reasons.append('python_symbol_binding_reassigned')
    out['contract_status'] = 'FAIL' if reasons else 'UNKNOWN' if extra or extra_declarations else 'PASS'
    out['reasons'] = reasons or ((['unexplained_extra_final_assertions'] if extra else []) +
                                (['unexplained_extra_final_declarations'] if extra_declarations else []) or ['all_required_structural_members_present'])
    out['seconds'] = time.perf_counter() - start
    return out


if __name__ == '__main__':
    import argparse
    from pathlib import Path
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ('base', 'delta', 'final'):
        parser.add_argument('--' + flag, required=True)
    parser.add_argument('--format', choices=['smtlib', 'python'], default='smtlib')
    args = parser.parse_args()
    paths = [getattr(args, n) for n in ('base', 'delta', 'final')]
    result = check_contract(*(Path(p).read_text(encoding='utf-8') for p in paths),
                            formats=(args.format,)*3, refs=tuple(paths))
    print(json.dumps(result, ensure_ascii=False, indent=2))
