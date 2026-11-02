"""Independent AST evidence sidecar. No state/effect/path propagation or solver.

PASS is conditional entry-value transfer at a source callsite, never reachability,
pointed-object identity, an interprocedural summary, or an alert decision.
Only the controlled self-contained synthetic build contract can PASS in R01.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys
import time

from clang import cindex as c

ROOT = Path(__file__).resolve().parent
CONFIG = json.loads((ROOT / 'config.json').read_text(encoding='utf-8'))
SCALARS = {'BOOL', 'CHAR_U', 'UCHAR', 'CHAR16', 'CHAR32', 'USHORT', 'UINT',
           'ULONG', 'ULONGLONG', 'CHAR_S', 'SCHAR', 'WCHAR', 'SHORT', 'INT',
           'LONG', 'LONGLONG', 'FLOAT', 'DOUBLE', 'LONGDOUBLE'}
SIGNED = {'SCHAR', 'SHORT', 'INT', 'LONG', 'LONGLONG'}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def stable_id(kind, data):
    return kind + ':' + digest(json.dumps(data, sort_keys=True,
                                        ensure_ascii=True).encode())


def location(loc):
    return {'file': str(loc.file) if loc.file else None,
            'line_1based': loc.line, 'column_1based': loc.column,
            'byte_offset': loc.offset}


def span(node):
    return {'start': location(node.extent.start), 'end_exclusive': location(node.extent.end)}


def raw(node, blob):
    return blob[node.extent.start.offset:node.extent.end.offset].decode('utf-8')


def declaration(node, namespace):
    canonical = node.canonical
    info = {'name': node.spelling, 'kind': node.kind.name,
            'usr': canonical.get_usr(), 'canonical_location': location(canonical.location),
            'location': location(node.location), 'source_range': span(node),
            'linkage': node.linkage.name}
    info['declaration_id'] = stable_id('decl', [namespace, info['usr'],
                                              info['canonical_location'], info['kind']])
    return info


def type_info(t, namespace):
    canonical = t.get_canonical()
    info = {'spelling': t.spelling, 'canonical': canonical.spelling,
            'kind': canonical.kind.name, 'size_bytes': canonical.get_size(),
            'const': canonical.is_const_qualified(),
            'volatile': canonical.is_volatile_qualified(),
            'restrict': canonical.is_restrict_qualified()}
    if canonical.kind == c.TypeKind.POINTER:
        p = canonical.get_pointee()
        info['pointee'] = type_info(p, namespace)
    elif canonical.kind == c.TypeKind.RECORD:
        d = canonical.get_declaration()
        info['record_declaration'] = declaration(d, namespace)
    return info


def same_unqualified(a, b):
    return (a['kind'], a['size_bytes']) == (b['kind'], b['size_bytes'])


def conversion(actual, formal, ast_argument):
    """Conservative subset, checked against the post-conversion AST expression type."""
    evidence = {'actual_type': actual, 'formal_type': formal,
                'ast_argument_type': ast_argument,
                'kind': 'unsupported', 'status': 'UNKNOWN', 'reasons': []}
    if any(t['volatile'] or t['restrict'] for t in (actual, formal)):
        evidence['reasons'] = ['qualified_or_volatile_type_not_supported']
        return evidence
    # Clang's CallExpr argument has its implicit converted type. Do not invent casts.
    if ast_argument['canonical'] != formal['canonical']:
        evidence['reasons'] = ['post_conversion_type_not_proven_equal_to_formal']
        return evidence
    if actual['kind'] in SCALARS and formal['kind'] in SCALARS:
        if same_unqualified(actual, formal):
            evidence.update(status='PASS', kind='identity')
        elif (actual['kind'] in SIGNED and formal['kind'] in SIGNED
              and 0 < actual['size_bytes'] < formal['size_bytes']):
            evidence.update(status='PASS', kind='signed_integer_widening')
        else:
            evidence['reasons'] = ['scalar_conversion_outside_supported_subset']
        return evidence
    if actual['kind'] != 'POINTER' or formal['kind'] != 'POINTER':
        evidence['reasons'] = ['non_scalar_or_incompatible_type_category']
        return evidence
    a, f = actual['pointee'], formal['pointee']
    if any(x['volatile'] or x['restrict'] for x in (a, f)):
        evidence['reasons'] = ['pointee_qualifiers_not_supported']
        return evidence
    if a['kind'] == f['kind'] == 'RECORD':
        ad, fd = a['record_declaration'], f['record_declaration']
        compatible = bool(ad['usr']) and ad['declaration_id'] == fd['declaration_id']
    else:
        compatible = a['kind'] in SCALARS and f['kind'] in SCALARS and same_unqualified(a, f)
    if not compatible:
        evidence['reasons'] = ['pointee_identity_or_supported_type_not_proven']
    elif a['const'] and not f['const']:
        evidence.update(status='REJECT', reasons=['pointee_const_discarded'])
    else:
        evidence.update(status='PASS', kind='pointee_const_addition'
                        if f['const'] and not a['const'] else 'identity')
    return evidence


def parse(path):
    path = Path(path).resolve()
    blob = path.read_bytes()
    # Avoid platform.system()'s shell fallback on Windows. Load the same installed
    # native library verified by environment_probe, with no dependency change.
    if not c.Config.loaded and not c.Config.library_file:
        filename = {'win32': 'libclang.dll', 'darwin': 'libclang.dylib'}.get(sys.platform, 'libclang.so')
        c.Config.set_library_file(str(Path(c.Config.library_path) / filename))
    # A single immutable byte snapshot is both parsed and hashed.
    tu = c.Index.create().parse(str(path), args=CONFIG['clang_args'],
                               unsaved_files=[(str(path), blob.decode('utf-8'))],
                               options=c.TranslationUnit.PARSE_DETAILED_PROCESSING_RECORD)
    diagnostics = [{'severity': d.severity, 'spelling': d.spelling,
                    'location': location(d.location), 'option': d.option,
                    'ranges': [{'start': location(r.start), 'end_exclusive': location(r.end)}
                               for r in d.ranges]} for d in tu.diagnostics]
    nodes = [n for n in tu.cursor.walk_preorder()
             if n.location.file and Path(n.location.file.name).resolve() == path]
    return path, blob, tu, nodes, diagnostics


def identifier_reference(arg, blob):
    """Only parentheses/implicit AST wrappers around one declared local are admitted."""
    node = arg
    while node.kind in {c.CursorKind.UNEXPOSED_EXPR, c.CursorKind.PAREN_EXPR}:
        children = list(node.get_children())
        if len(children) != 1:
            return None
        node = children[0]
    if node.kind != c.CursorKind.DECL_REF_EXPR or not node.referenced:
        return None
    decl = node.referenced
    if decl.kind not in {c.CursorKind.PARM_DECL, c.CursorKind.VAR_DECL}:
        return None
    text = raw(arg, blob).strip()
    # AST, not this lexical check, binds declaration identity. This only limits syntax.
    text = text.replace('(', '').replace(')', '').strip()
    if text != decl.spelling or not re.fullmatch(r'[A-Za-z_]\w*', text):
        return None
    return decl


def analyze(path, *, dataset_id, position, build_status,
            candidate_source_paths=()):
    """Analyze one TU. Extra clean TUs can deny uniqueness, never supply a definition.

    Historical saved fragments retain diagnostics/callsite candidates, all UNKNOWN.
    dataset_id/position label evidence only and do not alter semantics.
    """
    started = time.perf_counter()
    if not isinstance(dataset_id, str) or not dataset_id:
        raise ValueError('dataset_id must be a nonempty string')
    if isinstance(position, bool) or not isinstance(position, int) or position < 0:
        raise ValueError('position must be a nonnegative integer')
    path, blob, tu, nodes, diagnostics = parse(path)
    source_hash = digest(blob)
    build = {'status': build_status, 'args': CONFIG['clang_args'],
             'original_project_build_verified': False,
             'controlled_synthetic_TU': build_status == 'synthetic-self-contained'}
    namespace = {'dataset_id': dataset_id, 'position': position, 'file': str(path),
                 'source_sha256': source_hash, 'build': build}
    blockers = []
    if build_status != CONFIG['supported_build_status']:
        blockers.append('missing_original_build_evidence')
    if any(d['severity'] >= c.Diagnostic.Warning for d in diagnostics):
        blockers.append('clang_diagnostics_prevent_semantic_approval')
    if re.search(rb'^\s*#', blob, re.M):
        blockers.append('preprocessor_directives_not_supported')
    macro_expansions = [n for n in nodes if n.kind == c.CursorKind.MACRO_INSTANTIATION]
    functions = [n for n in nodes if n.kind == c.CursorKind.FUNCTION_DECL and n.is_definition()]
    external_definitions = {}
    candidate_inventory = []
    for extra_path in candidate_source_paths:
        ep, eb, etu, enodes, ediags = parse(extra_path)
        valid = not ediags and not re.search(rb'^\s*#', eb, re.M)
        defs = [n for n in enodes if n.kind == c.CursorKind.FUNCTION_DECL and n.is_definition()]
        candidate_inventory.append({'file': str(ep), 'sha256': digest(eb),
                                    'diagnostics': ediags, 'usable_for_ambiguity_check': valid,
                                    'definitions': [n.get_usr() for n in defs]})
        if not valid:
            blockers.append('candidate_definition_evidence_incomplete')
        for n in defs if valid else []:
            if n.linkage == c.LinkageKind.EXTERNAL:
                external_definitions.setdefault(n.get_usr(), set()).add(str(ep))
    calls = []
    for call in [n for n in nodes if n.kind == c.CursorKind.CALL_EXPR]:
        owner = [fn for fn in functions if fn.extent.start.offset <= call.extent.start.offset
                 < fn.extent.end.offset]
        if len(owner) != 1:
            continue
        caller = owner[0]
        caller_decl = declaration(caller, namespace)
        site = stable_id('call', [namespace, span(call), caller_decl['declaration_id']])
        result = {'dataset_id': dataset_id, 'position': position, 'callsite_id': site,
                  'caller': caller_decl, 'callee': None, 'callsite': span(call),
                  'call_text': raw(call, blob), 'caller_body_sha256': digest(raw(caller, blob).encode()),
                  'callee_body_sha256': None, 'source_sha256': source_hash,
                  'build_evidence': build, 'diagnostics_ref': '#/diagnostics',
                  'status': 'UNKNOWN', 'reasons': list(dict.fromkeys(blockers)),
                  'mappings': [], 'ast_is_trusted': not blockers,
                  'scope': CONFIG['scope'], 'reachability_verified': False,
                  'post_call_effects_verified': False, 'pointed_object_identity_verified': False}
        if any(call.extent.start.offset <= m.location.offset < call.extent.end.offset
               for m in macro_expansions):
            result['reasons'].append('macro_expansion_at_callsite')
        ref = call.referenced
        if not ref or ref.kind != c.CursorKind.FUNCTION_DECL:
            result['reasons'].append('indirect_call_or_unresolved_callee')
            calls.append(result)
            continue
        result['callee'] = declaration(ref, namespace)
        # A CallExpr referring to f but written as (*f)(...) or (&f)(...) is excluded.
        if not re.match(r'\s*'+re.escape(ref.spelling)+r'\s*\(', result['call_text']):
            result['reasons'].append('non_plain_direct_callee_expression')
        definition = ref.get_definition()
        local_defs = [n for n in functions if n.canonical.get_usr() == ref.canonical.get_usr()]
        others = external_definitions.get(ref.canonical.get_usr(), set())
        if not definition or len(local_defs) != 1:
            result['reasons'].append('missing_or_nonunique_local_definition')
        if len(local_defs) + len(others - {str(path)}) > 1:
            result['reasons'].append('multiple_definition_candidates')
        if not definition or result['reasons']:
            # Never use recovery AST bindings as verified mappings.
            calls.append(result)
            continue
        result['callee'] = declaration(definition, namespace)
        result['callee_body_sha256'] = digest(raw(definition, blob).encode())
        args, params = list(call.get_arguments()), list(definition.get_arguments())
        if definition.type.is_function_variadic() or len(args) != len(params):
            result['reasons'].append('variadic_or_argument_count_unsupported')
            calls.append(result)
            continue
        if not args:
            result['reasons'].append('no_parameter_transfer_to_check')
            calls.append(result)
            continue
        for index, (arg, param) in enumerate(zip(args, params)):
            formal = declaration(param, namespace)
            actual = identifier_reference(arg, blob)
            item = {'actual_index_0based': index, 'formal_index_0based': index,
                    'actual_expression': raw(arg, blob), 'actual_source_range': span(arg),
                    'actual_declaration': None, 'formal_declaration': formal,
                    'actual_slot_id': None,
                    'formal_slot_id': stable_id('callee-slot', [namespace, formal['declaration_id']]),
                    'formal_type': type_info(param.type, namespace),
                    'actual_type': None, 'conversion': None, 'status': 'UNKNOWN',
                    'reasons': [], 'relation': 'converted_callsite_value_equals_parameter_entry_value',
                    'slot_equivalence': False, 'value_version_tracking': False}
            if actual is None:
                item['reasons'].append('actual_expression_outside_identifier_subset')
            elif actual.semantic_parent != caller:
                item['reasons'].append('actual_not_a_caller_local_or_parameter')
            elif actual.storage_class in {c.StorageClass.STATIC, c.StorageClass.EXTERN}:
                item['reasons'].append('nonautomatic_actual_slot_not_supported')
            else:
                ad = declaration(actual, namespace)
                at = type_info(actual.type, namespace)
                conv = conversion(at, item['formal_type'], type_info(arg.type, namespace))
                item.update(actual_declaration=ad, actual_type=at, conversion=conv,
                            actual_slot_id=stable_id('caller-slot', [namespace, ad['declaration_id']]),
                            status=conv['status'], reasons=conv['reasons'])
            item['transfer_id'] = stable_id('transfer', [site, index, item['actual_slot_id'],
                                                       item['formal_slot_id']])
            result['mappings'].append(item)
        statuses = {m['status'] for m in result['mappings']}
        result['status'] = 'REJECT' if 'REJECT' in statuses else 'UNKNOWN' if 'UNKNOWN' in statuses else 'PASS'
        result['reasons'] += sorted({x for m in result['mappings'] for x in m['reasons']})
        calls.append(result)
    statuses = {x['status'] for x in calls}
    status = 'REJECT' if 'REJECT' in statuses else 'UNKNOWN' if blockers or not calls or 'UNKNOWN' in statuses else 'PASS'
    return {'dataset_id': dataset_id, 'position': position, 'status': status,
            'reasons': list(dict.fromkeys(blockers + ([] if calls else ['no_call_expr_recovered']))),
            'source': str(path), 'source_sha256': source_hash, 'build_evidence': build,
            'diagnostics': diagnostics, 'macro_expansions': [span(m) for m in macro_expansions],
            'candidate_inventory': candidate_inventory, 'calls': calls,
            'elapsed_seconds': time.perf_counter() - started}


def verify_proposal(call, proposed):
    """Check a proposed mapping against a fully approved AST call, without mutation."""
    if call['status'] != 'PASS':
        return {'status': 'UNKNOWN', 'reasons': ['reference_call_not_verified']}
    keys = ['actual_index_0based', 'formal_index_0based', 'actual_slot_id',
            'formal_slot_id', 'conversion_kind']
    if not isinstance(proposed, list) or any(not isinstance(p, dict) or
                                           any(k not in p for k in keys) for p in proposed):
        return {'status': 'UNKNOWN', 'reasons': ['proposal_missing_required_evidence']}
    expected = [{k: m[k] if k != 'conversion_kind' else m['conversion']['kind']
                 for k in keys} for m in call['mappings']]
    projection = [{k: p[k] for k in keys} for p in proposed]
    sort_key = lambda p: json.dumps(p, sort_keys=True)
    if sorted(expected, key=sort_key) != sorted(projection, key=sort_key):
        return {'status': 'REJECT', 'reasons': ['proposal_conflicts_with_AST_index_slot_or_conversion'],
                'expected': expected, 'proposed': projection}
    return {'status': 'PASS', 'reasons': [], 'checked_mapping_count': len(expected)}
