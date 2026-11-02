"""Bounded source/constraint diagnostics. No solver, code execution or alert verdict.

PASS is local consistency under explicit evidence, never full C semantics.
REJECT means reject a constraint candidate; UNKNOWN means insufficient evidence.
No function in this file edits constraints or synthesizes replacement assertions.
"""
import ast
import hashlib
import json
import re

from dependencies import load

VERSION = 'e05-local-semantic-rejection-v1'
NAME = r'[A-Za-z_]\w*'
TYPE = r'(?:(?:const|volatile)\s+)*(?:struct\s+' + NAME + r'|void|bool|_Bool|(?:(?:unsigned|signed)\s+)?(?:char|short(?:\s+int)?|int|long(?:\s+long)?(?:\s+int)?))'


class Unsupported(ValueError):
    pass


def sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def mask(code):
    """Keep offsets/lines; comments and string/char literals cannot create scopes."""
    return re.sub(r'/\*.*?\*/|//[^\n]*|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'',
                  lambda m: ''.join('\n' if c == '\n' else ' ' for c in m[0]), code, flags=re.S)


def ctype(spelling):
    s = re.sub(r'\s+', ' ', spelling.strip())
    if '*' in s:
        kind = 'pointer'
    elif s in ('bool', '_Bool'):
        kind = 'boolean'
    elif re.fullmatch(r'(?:(?:unsigned|signed) )?(?:char|short(?: int)?|int|long(?: long)?(?: int)?)', s):
        kind = 'integer'
    elif s.startswith('struct '):
        kind = 'aggregate'
    else:
        kind = 'unknown'
    return {'spelling': s, 'kind': kind, 'unsigned': s.startswith('unsigned '),
            'width': None, 'arithmetic_semantics': 'NOT_MODELED'}


class Source:
    """Lexical scopes + explicit simple declarations, not a C compiler/CFG.

    Preprocessor directives are refused. Historical macro invocations can still
    be recorded but cannot obtain whole-context approval. Declaration discovery
    accepts primitive types and struct pointers only; typedefs remain unknown.
    """
    def __init__(self, code, function, reference, expected_sha=None):
        self.code, self.function, self.reference = code, function, reference
        self.digest, self.clean = sha(code), mask(code)
        if expected_sha is not None and self.digest != expected_sha:
            raise Unsupported('source_hash_mismatch')
        if re.search(r'^\s*#', self.clean, re.M):
            raise Unsupported('preprocessor_configuration_unresolved')
        self.pairs = {}
        stacks = {'(': [], '{': [], '[': []}
        close = {')': '(', '}': '{', ']': '['}
        for i, c in enumerate(self.clean):
            if c in stacks:
                stacks[c].append(i)
            elif c in close:
                stack = stacks[close[c]]
                if not stack:
                    raise Unsupported('unbalanced_source')
                self.pairs[stack.pop()] = i
        if any(stacks.values()):
            raise Unsupported('unbalanced_source')
        headers = []
        for m in re.finditer(r'\b' + re.escape(function) + r'\s*\(', self.clean):
            start = self.clean.index('(', m.start()); end = self.pairs[start]
            body = self.space(end + 1)
            if body < len(code) and self.clean[body] == '{':
                headers.append((start, end, body, self.pairs[body]))
        if len(headers) != 1:
            raise Unsupported('function_definition_not_unique')
        self.args_start, self.args_end, self.start, self.end = headers[0]
        self.scopes = [(a, b) for a, b in self.pairs.items()
                       if self.clean[a] == '{' and self.start <= a < b <= self.end]
        self.declarations = []
        self._discover()

    def line(self, offset):
        return self.code.count('\n', 0, offset) + 1

    def offset(self, line):
        if type(line) is not int or not 1 <= line <= len(self.code.splitlines()):
            raise Unsupported('invalid_source_line')
        return sum(len(s) for s in self.code.splitlines(keepends=True)[:line - 1])

    def space(self, offset):
        while offset < len(self.clean) and self.clean[offset].isspace():
            offset += 1
        return offset

    def location(self, offset):
        return {'reference': self.reference, 'body_sha256': self.digest,
                'function': self.function, 'line': self.line(offset), 'offset': offset,
                'line_basis': 'one-based saved source body; no absolute-file claim'}

    def _decl(self, text, offset, scope):
        match = re.fullmatch(r'\s*(' + TYPE + r')\s+(.+?)\s*', text, re.S)
        if not match:
            return
        # Commas in initializers/complex declarators are unsupported, not guessed.
        cursor = match.start(2)
        for part in match[2].split(','):
            d = re.fullmatch(r'\s*(\*+\s*)?(' + NAME + r')\s*(?:=\s*[^,]+)?\s*', part, re.S)
            if not d:
                cursor += len(part) + 1
                continue
            name = d[2]; spelling = match[1] + (' ' + d[1].strip() if d[1] else '')
            name_offset = offset + cursor + d.start(2)
            record = {'name': name, 'type': ctype(spelling), 'scope': list(scope),
                      'declaration': self.location(name_offset), 'declaration_text': text.strip(),
                      'structure': {'kind': 'identifier', 'name': name}}
            record['identity'] = sha(json.dumps([self.digest, self.function, scope, name_offset,
                                                spelling, record['structure']], sort_keys=True))
            self.declarations.append(record)
            cursor += len(part) + 1

    def _discover(self):
        args = self.clean[self.args_start + 1:self.args_end]
        cursor = self.args_start + 1
        parts, last, depth = [], 0, 0
        for i, char in enumerate(args):
            if char in '([':
                depth += 1
            elif char in ')]':
                depth -= 1
            elif char == ',' and depth == 0:
                parts.append(args[last:i]); last = i + 1
        parts.append(args[last:])
        for part in parts:
            # Function-pointer parameters/prototypes remain unsupported; their
            # nested argument declarations must never become this function's locals.
            if '(' in part or '[' in part:
                cursor += len(part) + 1
                continue
            self._decl(part, cursor, (self.start, self.end))
            cursor += len(part) + 1
        # A local declaration must start a statement (or block), not match a call/cast.
        pattern = r'(?:^|(?<=[;{}]))(?P<decl>\s*(?:' + TYPE + r')\s+[^;{}]+);'
        for m in re.finditer(pattern, self.clean[self.start:self.end], re.M):
            a = self.start + m.start('decl'); text = m['decl']
            scopes = [s for s in self.scopes if s[0] <= a < s[1]]
            if scopes:
                self._decl(text, a, max(scopes, key=lambda s: s[0]))

    def resolve(self, expression, use_line):
        """Resolve identifier/member/pointee from checked source evidence."""
        use = self.offset(use_line)
        m = re.fullmatch(r'\s*(\*)?(' + NAME + r')(?:\s*(->|\.)\s*(' + NAME + r'))?\s*', expression)
        if not m:
            return {'status': 'UNKNOWN', 'reason': 'unsupported_source_expression', 'expression': expression}
        candidates = [d for d in self.declarations if d['name'] == m[2] and
                      d['scope'][0] <= use < d['scope'][1] and d['declaration']['line'] <= use_line]
        if candidates:
            deepest = max(d['scope'][0] for d in candidates)
            candidates = [d for d in candidates if d['scope'][0] == deepest]
        if len(candidates) != 1:
            return {'status': 'UNKNOWN', 'reason': 'declaration_missing_or_ambiguous',
                    'expression': expression, 'candidates': candidates}
        root = candidates[0]
        prior = self.clean[max(self.start, root['declaration']['offset']):use]
        writes = re.search(r'\b' + re.escape(root['name']) + r'\s*(?:=(?!=)|\+=|-=|\+\+|--)|(?:\+\+|--)\s*\b' + re.escape(root['name']) + r'\b', prior)
        address = re.search(r'&\s*\b' + re.escape(root['name']) + r'\b', prior)
        state_reasons = (['assignment_or_reassignment_deferred_E06'] if writes else [])
        if address:
            state_reasons.append('address_escape_or_call_effect_deferred_E06')
        result = dict(root, status='PASS', expression=expression, use=self.location(use),
                      state_uncertainties=state_reasons)
        if not m[1] and not m[3]:
            return result
        structure = {'kind': 'pointee' if m[1] else 'member', 'root_identity': root['identity'],
                     'operator': '*' if m[1] else m[3], 'member': m[4]}
        if m[1] and m[3]:
            return dict(result, status='UNKNOWN', reason='complex_dereference_unsupported')
        pointer = root['type']['kind'] == 'pointer'
        if (m[1] or m[3] == '->') != pointer:
            return dict(result, status='UNKNOWN', reason='expression_type_mismatch')
        t = root['type']['spelling'].rstrip('* ').strip()
        if m[1]:
            result['type'] = ctype(t)
        else:
            definitions = [d for d in re.finditer(r'\b' + re.escape(t) + r'\s*\{', self.clean)
                           if d.start() < use and not any(self.clean[a] == '{' and a < d.start() < b
                                                         for a,b in self.pairs.items())]
            member = []
            if len(definitions) == 1:
                definition = definitions[0]
                a = self.clean.index('{', definition.start()); b = self.pairs[a]
                for decl in re.finditer(r'(' + TYPE + r')\s+(\*+\s*)?' + re.escape(m[4]) + r'\s*;', self.clean[a+1:b]):
                    member.append((ctype(decl[1] + (' '+decl[2].strip() if decl[2] else '')), a+1+decl.start()))
            if len(member) != 1:
                result.update(status='UNKNOWN', reason='member_type_or_definition_missing', type=ctype('unknown'))
            else:
                result['type'], member_offset = member[0]
                result['member_declaration'] = self.location(member_offset)
        result['structure'] = structure
        result['identity'] = sha(json.dumps([root['identity'], structure, result['type']], sort_keys=True))
        return result

    def statement_end(self, start):
        """Bounded single statement. Complex control statements are refused."""
        start = self.space(start)
        if self.clean[start] == '{':
            return self.pairs[start] + 1
        if re.match(r'(if|for|while|switch|do)\b', self.clean[start:]):
            raise Unsupported('nested_control_statement_not_supported')
        i = start
        while i < self.end:
            if self.clean[i] in '([':
                i = self.pairs[i] + 1
            elif self.clean[i] == ';':
                return i + 1
            elif self.clean[i] in '{}':
                break
            else:
                i += 1
        raise Unsupported('statement_boundary_unknown')

    def guard(self, guard_line, target_line, branch, target_text=None):
        """Verify immediate arm or tightly bounded post-return edge.

        A local arm can be recognized inside a larger unsupported function. A
        post-return edge requires same lexical scope, no bypass label/control,
        and an unconditional return; gotos/break/continue are not inferred.
        """
        if type(branch) is not bool:
            raise Unsupported('branch_direction_unconfirmed')
        start, target = self.offset(guard_line), self.offset(target_line)
        line = self.clean.splitlines()[guard_line - 1]
        m = re.match(r'\s*if\s*\(', line)
        if not m:
            raise Unsupported('guard_location_not_if')
        op = start + m.end() - 1; close = self.pairs[op]
        expression = self.clean[op+1:close].strip()
        body_start = self.space(close + 1); body_end = self.statement_end(body_start)
        target = self.space(target)
        if target_text is not None and target_text.strip() not in self.code.splitlines()[target_line - 1]:
            raise Unsupported('target_text_location_mismatch')
        after = self.space(body_end); else_start = else_end = None
        if re.match(r'else\b', self.clean[after:]):
            else_start = self.space(after+4); else_end = self.statement_end(else_start)
        if body_start <= target < body_end:
            actual, basis = True, 'lexical_true_arm'
        elif else_start is not None and else_start <= target < else_end:
            actual, basis = False, 'lexical_false_arm'
        elif target >= body_end and else_start is None:
            body = self.clean[body_start:body_end].strip()
            if body.startswith('{') and body.endswith('}'):
                body = body[1:-1].strip()
            if not re.fullmatch(r'return\b[^;{}]*;', body):
                raise Unsupported('post_guard_not_unconditional_return')
            gap = self.clean[body_end:target]
            scopes = lambda pos: [s for s in self.scopes if s[0] <= pos < s[1]]
            if scopes(start) != scopes(target) or re.search(r'\b(if|for|while|do|goto|switch|return)\b|[{}:]|\belse\b', gap):
                raise Unsupported('early_return_dominance_unconfirmed')
            # No statements between guard and use: no hidden reassignment/call effects.
            if gap.strip():
                raise Unsupported('intervening_state_or_call_deferred_E06')
            actual, basis = False, 'immediate_after_unconditional_return'
        else:
            raise Unsupported('target_branch_not_verified')
        if branch != actual:
            raise Unsupported('claimed_branch_disagrees_with_source')
        return {'expression': expression, 'branch': actual, 'basis': basis,
                'guard': self.location(op), 'target': self.location(target),
                'target_text': self.code.splitlines()[target_line - 1]}


def formula_truth(node, name, is_zero, kind):
    """Two-element zero/nonzero abstraction; no SAT solver or eval."""
    if isinstance(node, ast.Constant) and type(node.value) is bool:
        return node.value
    if isinstance(node, ast.Name) and node.id == name and kind == 'boolean':
        return not is_zero
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and not node.keywords:
        fn = node.func.id
        if fn == 'Not' and len(node.args) == 1:
            return not formula_truth(node.args[0], name, is_zero, kind)
        if fn in ('And', 'Or') and node.args:
            vals = [formula_truth(x, name, is_zero, kind) for x in node.args]
            return all(vals) if fn == 'And' else any(vals)
    if (kind != 'boolean' and isinstance(node, ast.Compare) and len(node.ops) == 1 and
            isinstance(node.ops[0], (ast.Eq, ast.NotEq))):
        a, b = node.left, node.comparators[0]
        if isinstance(b, ast.Name):
            a, b = b, a
        if (isinstance(a, ast.Name) and a.id == name and isinstance(b, ast.Constant) and
                type(b.value) is int and b.value == 0):
            return is_zero if isinstance(node.ops[0], ast.Eq) else not is_zero
    raise Unsupported('formula_outside_single_bound_zero_test')


def check_polarity(source, guard_line, target_line, branch, generated, *,
                   expected_identity=None, sort='Int', context_reasons=(), target_text=None):
    out = {'status': 'UNKNOWN', 'local_status': 'UNKNOWN', 'generated': generated,
           'reasons': [], 'context_reasons': list(context_reasons), 'assertions_removed': 0,
           'alert_safety_decision': None}
    try:
        evidence = source.guard(guard_line, target_line, branch, target_text)
        normalized = load('e01').normalize_c(evidence['expression'], branch)
        binding = source.resolve(normalized['variable'], guard_line)
        out.update(source=evidence, normalized=normalized, binding=binding)
        out['context_reasons'].extend(binding.get('state_uncertainties', []))
        if re.search(r'\b(goto|for|while|switch|do)\b', source.clean[source.start:source.end]):
            out['context_reasons'].append('complex_control_flow_not_verified')
        if binding['status'] != 'PASS':
            raise Unsupported(binding['reason'])
        if expected_identity is not None and expected_identity != binding['identity']:
            raise Unsupported('symbol_scope_identity_mismatch')
        kind = binding['type']['kind']
        if kind not in ('integer', 'pointer', 'boolean'):
            raise Unsupported('unknown_or_nonscalar_type')
        if sort != ('Bool' if kind == 'boolean' else 'Int'):
            out['local_status'] = 'REJECT'
            out['reasons'].append('c_type_smt_sort_conflict')
        else:
            node = ast.parse(generated, mode='eval').body
            truth = [formula_truth(node, binding['name'], zero, kind) for zero in (True, False)]
            expected = [normalized['zero'], not normalized['zero']]
            out.update(truth_zero_nonzero=truth, expected_zero_nonzero=expected,
                       abstraction='zero/nonzero only; no width/arithmetic/alias proof')
            if truth == expected:
                out['local_status'] = 'PASS'
            else:
                out['local_status'] = 'REJECT'
                out['reasons'].append('tautological_branch_weakening' if all(truth) else
                                      'constant_false_branch' if not any(truth) else 'polarity_conflict')
        out['status'] = ('REJECT' if out['local_status'] == 'REJECT' else
                         'UNKNOWN' if out['context_reasons'] else out['local_status'])
    except (Unsupported, load('e01').Unsupported, SyntaxError, ValueError) as exc:
        out['reasons'].append(str(exc))
    return out


def check_mappings(bindings):
    """Bindings must include a Source.resolve result, SMT symbol/sort and use mode.

    Int pointer symbols may only represent zero tests. A PASS on these limited
    bindings does not model addresses, C arithmetic or object memory.
    """
    diagnostics, by_symbol, by_identity = [], {}, {}
    for item in bindings:
        b, symbol = item['source'], item['symbol']
        status, reason = 'PASS', 'explicit_local_binding'
        kind, sort, mode = b.get('type', {}).get('kind'), item.get('sort'), item.get('mode')
        if b.get('status') != 'PASS' or kind in (None, 'unknown', 'aggregate'):
            status, reason = 'UNKNOWN', b.get('reason', 'unknown_or_nonscalar_type')
        elif sort != ('Bool' if kind == 'boolean' else 'Int'):
            status, reason = 'REJECT', 'c_type_smt_sort_conflict'
        elif mode not in ('zero_test', 'boolean_test'):
            status, reason = 'UNKNOWN', 'width_overflow_or_address_semantics_unmodeled'
        if item.get('alias_unresolved') or item.get('state_changed') or item.get('cross_function') or b.get('state_uncertainties'):
            status, reason = 'UNKNOWN', 'alias_state_or_cross_function_deferred_E06'
        diagnostics.append({'symbol': symbol, 'source': b, 'sort': sort, 'mode': mode,
                            'status': status, 'reason': reason})
        if b.get('identity'):
            by_symbol.setdefault(symbol, set()).add(b['identity'])
            by_identity.setdefault(b['identity'], set()).add(symbol)
    collisions = [{'symbol': s, 'identities': sorted(ids)} for s, ids in by_symbol.items() if len(ids) > 1]
    splits = [{'identity': i, 'symbols': sorted(names)} for i, names in by_identity.items() if len(names) > 1]
    status = ('REJECT' if collisions or any(d['status'] == 'REJECT' for d in diagnostics) else
              'UNKNOWN' if splits or not bindings or any(d['status'] == 'UNKNOWN' for d in diagnostics) else 'PASS')
    return {'status': status, 'bindings': diagnostics, 'distinct_objects_merged': collisions,
            'split_identity_unproven': splits, 'assertions_removed': 0, 'alert_safety_decision': None}


def arithmetic_tree(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Constant) and type(node.value) is int:
        return str(node.value)
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub)):
        return ['+' if isinstance(node.op, ast.Add) else '-', arithmetic_tree(node.left), arithmetic_tree(node.right)]
    raise Unsupported('arithmetic_shape_outside_subset')


def member_collapse_diagnostics(source, raw_script, inherited=None):
    """Compare direct assignment shapes with model equalities, never execute.

    Only a complete +/- tree match with a member leaf replaced by its pointer
    root is flagged. This establishes local expression-identity corruption of
    the claimed assignment, NOT which assignment/state reaches the sink.
    """
    checker = load('e02')
    try:
        ir = checker._parse(raw_script, 'python', 'model/raw', inherited)
    except checker.Unsupported as exc:
        return {'status': 'UNKNOWN', 'reasons': [str(exc)], 'findings': []}
    env = {b['python_name']: b['symbol'] for b in ir.bindings}
    if inherited:
        env.update({k:k for k in inherited})
    assignments = []
    for m in re.finditer(r'\b(' + NAME + r')\s*=(?!=)\s*([^;{}]+);', source.clean):
        if not source.start < m.start() < source.end:
            continue
        rhs = m[2].strip()
        leaves = re.findall(r'\b' + NAME + r'\s*->\s*' + NAME, rhs)
        if not leaves:
            continue
        transformed, members = rhs, {}
        for j, leaf in enumerate(dict.fromkeys(leaves)):
            key = 'E05_MEMBER_' + str(j)
            root = leaf.split('->')[0].strip()
            root_binding = source.resolve(root, source.line(m.start()))
            if root_binding.get('type', {}).get('kind') != 'pointer' or root_binding.get('status') != 'PASS':
                continue
            transformed = transformed.replace(leaf, key)
            members[key] = {'expression': leaf, 'root': root, 'root_binding': root_binding,
                            'member_binding': source.resolve(leaf, source.line(m.start()))}
        try:
            tree = arithmetic_tree(ast.parse(transformed, mode='eval').body)
        except (SyntaxError, Unsupported):
            continue
        if members:
            assignments.append((m, tree, members))

    def replace(tree, members):
        if isinstance(tree, (list, tuple)):
            return tuple(replace(x, members) for x in tree)
        return members[tree]['root'] if tree in members else env.get(tree, tree)

    def equalities(tree):
        if isinstance(tree, (list, tuple)):
            if len(tree) == 3 and tree[0] == '=':
                yield tree
            for child in tree[1:]:
                yield from equalities(child)

    findings = []
    for assertion in ir.assertions:
        for expr in checker.expressions(assertion['formula']):
            for eq in equalities(expr):
                for m, expected, members in assignments:
                    if eq[1] == env.get(m[1], m[1]) and eq[2] == replace(expected, members):
                        findings.append({'code': 'pointer_member_identity_collapse',
                            'source_assignment': source.code[m.start():m.end()],
                            'source': source.location(m.start()), 'members': members,
                            'actual_formula': assertion, 'expected_source_shape': expected,
                            'basis': 'exact +/- assignment shape; member replaced by pointer root',
                            'path_state': 'UNKNOWN/deferred_E06', 'member_type_semantics': 'NOT_PROVEN'})
    return {'status': 'REJECT' if findings else 'UNKNOWN', 'findings': findings,
            'reasons': [] if findings else ['no_supported_member_collapse_witness'],
            'assertions_removed': 0, 'alert_safety_decision': None}
