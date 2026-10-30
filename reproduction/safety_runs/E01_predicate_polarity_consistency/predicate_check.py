"""R01 only: check a bound scalar predicate against saved generated atoms.

No C flow/alias analysis, LLM calls, script execution, assertion deletion or FILTER.
Bindings are evidence inputs, not newly inferred program-state proofs.
"""
import ast
import hashlib
import re

VERSION = 'e01-predicate-polarity-v1'


class Unsupported(ValueError):
    pass


def text_sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


class ScalarParser:
    """C truth-value subset: identifier, !, parentheses, ==0 and !=0."""
    def __init__(self, expression):
        if not isinstance(expression, str) or len(expression) > 512:
            raise Unsupported('invalid_or_oversized_expression')
        self.tokens = re.findall(r'!=|==|!|\(|\)|0|[A-Za-z_]\w*', expression)
        if ''.join(self.tokens) != re.sub(r'\s+', '', expression) or len(self.tokens) > 80:
            raise Unsupported('outside_scalar_syntax')
        self.i = 0

    def accept(self, token):
        if self.i < len(self.tokens) and self.tokens[self.i] == token:
            self.i += 1
            return True
        return False

    def primary(self):
        if self.accept('('):
            value = self.equality()
            if not self.accept(')'):
                raise Unsupported('unbalanced_parentheses')
            return value
        if self.i == len(self.tokens):
            raise Unsupported('missing_operand')
        value = self.tokens[self.i]
        self.i += 1
        if value == '0':
            return None, None
        if not re.fullmatch(r'[A-Za-z_]\w*', value):
            raise Unsupported('outside_scalar_syntax')
        return value, False  # expression true iff this variable is nonzero

    def unary(self):
        if self.accept('!'):
            name, zero = self.unary()
            if name is None:
                raise Unsupported('constant_only_predicate')
            return name, not zero
        return self.primary()

    def equality(self):
        name, zero = self.unary()
        if self.i < len(self.tokens) and self.tokens[self.i] in ('==', '!='):
            operator = self.tokens[self.i]
            self.i += 1
            rhs_name, rhs_zero = self.unary()
            if name is None or rhs_name is not None or rhs_zero is not None:
                raise Unsupported('only_scalar_comparison_to_zero_supported')
            zero = not zero if operator == '==' else zero
        return name, zero

    def parse(self):
        name, zero = self.equality()
        if self.i != len(self.tokens) or name is None:
            raise Unsupported('outside_scalar_syntax')
        return name, zero


def normalize_c(expression, branch):
    if type(branch) is not bool:
        raise Unsupported('unconfirmed_branch_direction')
    name, zero = ScalarParser(expression).parse()
    zero = zero if branch else not zero
    return {'variable': name, 'zero': zero,
            'normalized': name + (' == 0' if zero else ' != 0')}


def normalize_generated(expression):
    """Inspect syntax, never eval/exec model-generated Python."""
    if not isinstance(expression, str) or len(expression) > 1024:
        raise Unsupported('invalid_generated_atom')
    try:
        node = ast.parse(expression, mode='eval').body
    except (SyntaxError, ValueError):
        raise Unsupported('unparseable_generated_atom')

    def parse(n):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and
                n.func.id == 'Not' and len(n.args) == 1 and not n.keywords):
            name, zero = parse(n.args[0])
            return name, not zero
        if (isinstance(n, ast.Compare) and len(n.ops) == 1 and
                isinstance(n.left, ast.Name) and len(n.comparators) == 1 and
                isinstance(n.comparators[0], ast.Constant) and
                type(n.comparators[0].value) is int and n.comparators[0].value == 0 and
                isinstance(n.ops[0], (ast.Eq, ast.NotEq))):
            return n.left.id, isinstance(n.ops[0], ast.Eq)
        raise Unsupported('generated_atom_outside_subset')

    name, zero = parse(node)
    return {'variable': name, 'zero': zero,
            'normalized': name + (' == 0' if zero else ' != 0')}


def symbol_identity(code_sha, declaration_line, name):
    return f'{code_sha}:declaration:{declaration_line}:{name}'


def check_condition(record, generated_atoms):
    """A local contradiction can be diagnosed without approving its path context."""
    result = {'condition_id': record.get('condition_id'), 'original_expression': record.get('expression'),
              'branch_direction': record.get('branch'), 'symbol': record.get('symbol'),
              'source': {k: v for k, v in (record.get('source') or {}).items() if k != 'code'},
              'status': 'unsupported', 'local_status': 'unsupported',
              'normalized_condition': None, 'reasons': [], 'atom_checks': [],
              'context_unsupported': list(record.get('context_unsupported', [])),
              'candidate_accepted': False, 'verdict_on_rejection': 'UNKNOWN', 'action': 'KEEP'}
    try:
        normalized = normalize_c(record.get('expression'), record.get('branch'))
        result['normalized_condition'] = normalized['normalized']
        symbol, source = record['symbol'], record['source']
        if not isinstance(symbol, dict):
            raise Unsupported('unknown_type_or_unbound_declaration')
        code = source['code']
        digest = text_sha(code)
        line, declaration = source['line'], symbol['declaration_line']
        if source.get('code_sha256') != digest:
            raise Unsupported('source_hash_mismatch')
        if (type(line) is not int or type(declaration) is not int or
                not 1 <= declaration <= line <= len(code.splitlines())):
            raise Unsupported('source_or_declaration_location_invalid')
        if symbol.get('name') != normalized['variable']:
            raise Unsupported('source_variable_identity_mismatch')
        if symbol.get('identity') != symbol_identity(digest, declaration, symbol['name']):
            raise Unsupported('source_symbol_identity_unbound')
        if (symbol.get('type_kind') not in ('integer', 'pointer') or
                not symbol.get('type_spelling') or symbol.get('type_evidence') != 'explicit_declaration'):
            raise Unsupported('unknown_type')
        builtin = r'(?:(?:unsigned|signed)\s+)?(?:char|short(?:\s+int)?|int|long(?:\s+long)?(?:\s+int)?)'
        spelling_type = symbol['type_spelling'].strip()
        if symbol['type_kind'] == 'integer':
            known = re.fullmatch(builtin, spelling_type)
        else:
            known = re.fullmatch(r'(?:' + builtin + r'|struct\s+[A-Za-z_]\w*)\s*\*+', spelling_type)
        if not known:
            raise Unsupported('unknown_type')
        declaration_text = code.splitlines()[declaration - 1].strip()
        spelling = symbol['type_spelling'].rstrip('* ').strip()
        if (not declaration_text.startswith(spelling + ' ') or
                not re.search(r'\b' + re.escape(symbol['name']) + r'\b', declaration_text)):
            raise Unsupported('declaration_evidence_mismatch')
        guard = re.fullmatch(r'\s*if\s*\((.*)\)\s*\{?\s*', code.splitlines()[line - 1])
        if not guard or normalize_c(guard[1], record['branch']) != normalized:
            raise Unsupported('predicate_source_location_mismatch')
        if not generated_atoms:
            raise Unsupported('no_bound_generated_atom')
        for atom in generated_atoms:
            item = {'expression': atom.get('expression'), 'origin': atom.get('origin'),
                    'status': 'unsupported', 'normalized': None}
            try:
                if (atom.get('source_condition_id') != record['condition_id'] or
                        atom.get('symbol_identity') != symbol['identity']):
                    raise Unsupported('generated_source_or_scope_identity_unbound')
                if atom.get('sort') != 'Int':
                    raise Unsupported('generated_sort_outside_known_scalar_abstraction')
                actual = normalize_generated(atom.get('expression'))
                if actual['variable'] != symbol['name']:
                    raise Unsupported('generated_variable_identity_mismatch')
                item.update(status='consistent' if actual['zero'] == normalized['zero'] else 'mismatch',
                            normalized=actual['normalized'])
            except Unsupported as exc:
                item['reason'] = str(exc)
            result['atom_checks'].append(item)
        states = [x['status'] for x in result['atom_checks']]
        if 'mismatch' in states:
            result.update(status='rejected', local_status='mismatch')
            result['reasons'].append('polarity_conflict_with_source_branch')
        elif 'unsupported' in states:
            result['reasons'].append('generated_atoms_not_completely_bound')
        else:
            result['local_status'] = 'consistent'
            if result['context_unsupported']:
                result['reasons'].append('program_context_outside_e01')
            else:
                result.update(status='consistent', candidate_accepted=True)
    except (Unsupported, KeyError, TypeError) as exc:
        result['reasons'].append(str(exc))
    return result


def check_merge(records, atoms):
    """Check all provenance-bound atoms; report repeats without dropping any."""
    ids = [r.get('condition_id') for r in records]
    if len(set(ids)) != len(ids):
        return {'status': 'unsupported', 'reason': 'ambiguous_source_condition_ids',
                'conditions': [], 'input_atom_count': len(atoms), 'atoms_removed': 0}
    checks = [check_condition(r, [a for a in atoms if a.get('source_condition_id') == r['condition_id']])
              for r in records]
    orphan = [a for a in atoms if a.get('source_condition_id') not in ids]
    status = ('rejected' if any(c['status'] == 'rejected' for c in checks) else
              'consistent' if checks and all(c['status'] == 'consistent' for c in checks) and not orphan
              else 'unsupported')
    duplicate = len(atoms) - len({(a.get('source_condition_id'), a.get('expression')) for a in atoms})
    return {'status': status, 'conditions': checks, 'input_atom_count': len(atoms),
            'unbound_atom_count': len(orphan), 'repeated_atom_count': duplicate,
            'atoms_removed': 0, 'meaning': 'provenance/polarity consistency only; no FILTER authority'}
