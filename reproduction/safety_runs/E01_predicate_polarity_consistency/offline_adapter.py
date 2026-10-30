"""Inspect frozen source/response syntax only; no extractor or engine imports.

This does not repair locations, derive dominance, introduce aliases, propagate
states or infer macros. Unverified whole-program context remains unsupported.
"""
import ast
from collections import Counter
import re

from predicate_check import (Unsupported, check_condition, normalize_c,
                             normalize_generated, symbol_identity, text_sha)


def explicit_declaration(code, name):
    """Read evidence for one builtin scalar or struct-pointer declaration only."""
    declarations = []
    type_pattern = r'((?:(?:unsigned|signed)\s+)?(?:char|short(?:\s+int)?|int|long(?:\s+long)?(?:\s+int)?)|struct\s+[A-Za-z_]\w*)'
    for i, line in enumerate(code.splitlines(), 1):
        match = re.fullmatch(r'\s*' + type_pattern + r'\s+([^;]+);\s*', line)
        if not match:
            continue
        for declarator in match[2].split(','):
            item = re.fullmatch(r'\s*(\*+)?\s*' + re.escape(name) + r'\s*(?:=\s*.+)?', declarator)
            if item:
                pointer = bool(item[1])
                if match[1].startswith('struct ') and not pointer:
                    continue
                declarations.append({'name': name, 'declaration_line': i,
                    'type_spelling': match[1] + (' ' + item[1] if pointer else ''),
                    'type_kind': 'pointer' if pointer else 'integer',
                    'type_evidence': 'explicit_declaration',
                    'identity': symbol_identity(text_sha(code), i, name)})
    return declarations[0] if len(declarations) == 1 else None


def condition_records(bundle):
    records = []
    for frame_index, frame in enumerate((bundle.get('context') or {}).get('frames', [])):
        code = frame['code']
        saved = frame.get('extracted') or {}
        entries = [(x.get('condition', ''), True, x.get('line_number'), 'saved_target_condition')
                   for x in saved.get('target_conditions', []) if isinstance(x, dict)]
        for exit_item in saved.get('early_jump_constraints', []):
            entries.extend((s, False, None, 'saved_early_exit_condition')
                           for s in exit_item.get('condition', []))
        for index, (raw, branch, zero_line, kind) in enumerate(entries):
            match = re.fullmatch(r'\s*if\s*\((.*)\)\s*', raw)
            expression = match[1] if match else raw
            line = zero_line + 1 if type(zero_line) is int else None
            # Bind only an exact unique recorded guard spelling, not a new sink locator.
            if line is None:
                expected = re.sub(r'\s+', '', 'if(' + expression + ')')
                hits = [i for i, s in enumerate(code.splitlines(), 1)
                        if re.sub(r'\s+', '', s.rstrip().removesuffix('{')) == expected]
                line = hits[0] if len(hits) == 1 else None
            name = None
            try:
                name = normalize_c(expression, branch)['variable']
            except Unsupported:
                pass
            symbol = explicit_declaration(code, name) if name else None
            records.append({'condition_id': f'frame/{frame_index}/condition/{index}',
                'frame_index': frame_index, 'expression': expression, 'branch': branch,
                'kind': kind,
                'branch_basis': kind + '; local recorded edge only, not a new CFG proof',
                'original_saved_condition': raw, 'symbol': symbol,
                'source': {'path': (bundle.get('alert', {}).get('location', {}).get('file_path')
                                    if frame_index == 0 else None),
                           'path_basis': 'saved alert path; callee absolute path not established',
                           'frame': frame_index, 'function': frame['function'],
                           'line': line, 'line_numbering': '1-based in saved function, not absolute file',
                           'absolute_file_line': None, 'code': code, 'code_sha256': text_sha(code)},
                'context_unsupported': ['whole_program_state_and_control_not_verified_in_e01'] +
                    (['early_exit_dominance_not_verified'] if not branch else [])})
    return records


def saved_scripts(bundle):
    scripts = []
    frame = -1
    for index, response in enumerate((bundle.get('recorded_answer') or {}).get('response', [])):
        if not isinstance(response, str):
            continue
        if response.startswith('step 1 z3 script:'):
            frame += 1
        if '```json' in response:
            continue
        blocks = re.findall(r'```python\s*\n(.*?)```', response, re.S)
        source = blocks[0] if len(blocks) == 1 else response.partition(':')[2].strip()
        if not source:
            continue
        scripts.append({'source': source, 'frame_index': max(frame, 0),
                        'origin': {'kind': 'saved_model_response', 'response_index': index,
                                   'response_sha256': text_sha(response),
                                   'script_sha256': text_sha(source)}})
    for event in bundle.get('solver_events', []):
        if event.get('source'):
            scripts.append({'source': event['source'], 'frame_index': event.get('level', 0),
                'origin': {'kind': 'saved_solver_generated_script', 'event_id': event.get('event_id'),
                           'script_sha256': text_sha(event['source'])}})
    # Identical snapshots are indexed, not executed again; no assertions are rewritten.
    unique = {}
    for item in scripts:
        key = item['frame_index'], text_sha(item['source'])
        if key in unique:
            unique[key]['also_saved_at'].append(item['origin'])
        else:
            item['also_saved_at'] = []
            unique[key] = item
    return list(unique.values())


def generated_atoms(script):
    try:
        tree = ast.parse(script['source'])
    except SyntaxError:
        return [], ['saved_response_not_python_syntax']
    if any(isinstance(n, (ast.If, ast.For, ast.While, ast.Try, ast.With, ast.Lambda,
                          ast.AsyncFunctionDef)) for n in ast.walk(tree)):
        return [], ['generated_control_flow_not_statically_supported']
    bindings = {}
    ambiguous = set()
    assignment_counts = Counter()
    for node in ast.walk(tree):
        if isinstance(node, ast.arg):
            ambiguous.add(node.arg)
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                for child in ast.walk(target):
                    if isinstance(child, ast.Name):
                        assignment_counts[child.id] += 1
        if (isinstance(node, ast.Assign) and len(node.targets) == 1 and
                isinstance(node.targets[0], ast.Name) and isinstance(node.value, ast.Call) and
                isinstance(node.value.func, ast.Name) and node.value.func.id in ('Int', 'Bool', 'BitVec') and
                node.value.args and isinstance(node.value.args[0], ast.Constant) and
                isinstance(node.value.args[0].value, str)):
            name = node.targets[0].id
            value = node.value.args[0].value, node.value.func.id
            if name in bindings and bindings[name] != value:
                ambiguous.add(name)
            bindings[name] = value
    atoms, reasons = [], []

    def collect(node, line):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and
                node.func.id == 'And' and not node.keywords):
            for arg in node.args:
                collect(arg, line)
            return
        expression = ast.unparse(node)
        item = {'expression': expression, 'origin': {**script['origin'], 'generated_line': line},
                'frame_index': script['frame_index'], 'sort': None, 'variable': None}
        try:
            normalized = normalize_generated(expression)
            name = normalized['variable']
            if (name in ambiguous or name not in bindings or bindings[name][0] != name or
                    assignment_counts[name] != 1):
                raise Unsupported('generated_symbol_name_or_sort_identity_unbound')
            item.update(variable=name, sort=bindings[name][1], normalized=normalized['normalized'])
        except Unsupported as exc:
            item['unsupported_reason'] = str(exc)
        atoms.append(item)

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'add':
            for arg in node.args:
                collect(arg, node.lineno)
    if not atoms:
        reasons.append('no_statically_readable_add_assertions')
    return atoms, reasons


def inspect_bundle(bundle):
    records = condition_records(bundle)
    atoms, script_reasons = [], []
    scripts = saved_scripts(bundle)
    for script in scripts:
        values, reasons = generated_atoms(script)
        atoms.extend(values)
        script_reasons.extend(reasons)
    keys = Counter((r['frame_index'], (r.get('symbol') or {}).get('name')) for r in records if r.get('symbol'))
    checks = []
    for record in records:
        symbol = record.get('symbol')
        bound = []
        # An early-exit candidate cannot be attributed from a name alone: it may
        # instead be the null bug hypothesis. Do not invent assertion provenance.
        attributable = (record['kind'] == 'saved_target_condition' and symbol and
                        symbol['name'] != (bundle.get('context') or {}).get('frames', [])[record['frame_index']].get('var_name') and
                        keys[record['frame_index'], symbol['name']] == 1)
        if attributable:
            for atom in atoms:
                if atom['frame_index'] == record['frame_index'] and atom['variable'] == symbol['name']:
                    bound.append({**atom, 'source_condition_id': record['condition_id'],
                                  'symbol_identity': symbol['identity']})
        check = check_condition(record, bound)
        check['branch_basis'] = record['branch_basis']
        check['binding_basis'] = ('unique recorded target predicate and matching generated declaration; '
                                 'diagnostic association only, not independent assertion provenance'
                                 if attributable else 'assertion role/provenance not established')
        if not attributable:
            check['reasons'].append('assertion_role_or_provenance_unbound')
        checks.append(check)
    conflicts = [c['condition_id'] for c in checks if c['local_status'] == 'mismatch']
    local_checked = sum(c['local_status'] in ('consistent', 'mismatch') for c in checks)
    unsupported = Counter(reason for c in checks for reason in c['reasons'])
    unsupported.update(script_reasons)
    if not records:
        unsupported['no_recorded_predicate_in_supported_evidence'] += 1
    if not scripts:
        unsupported['no_saved_model_script'] += 1
    # No new context or independent semantic approval is manufactured by this adapter.
    return {'status': 'rejected' if conflicts else 'unsupported', 'checks': checks,
            'source_condition_count': len(records), 'locally_checked_condition_count': local_checked,
            'conflicting_condition_count': len(conflicts), 'conflicting_conditions': conflicts,
            'conflicting_atom_occurrences': sum(a['status'] == 'mismatch' for c in checks for a in c['atom_checks']),
            'whole_sample_supported': False,
            'whole_sample_unsupported_reason': 'C state, control and full merge provenance not established; R02/R03 untouched',
            'saved_script_count': len(scripts), 'saved_generated_atom_count': len(atoms),
            'unsupported_reasons': dict(unsupported), 'atoms_removed': 0,
            'original_scripts_sha256': [text_sha(s['source']) for s in scripts],
            'cache_scope': 'original saved response consistency only, not a new end-to-end experiment'}
