"""Bounded return-to-caller value evidence. No solver, summaries or alert action."""
import copy
import re
import time

from adapter import r01, r02, namespace, typed, counts
from call_context import create_context, verify_isolation
from return_value import ReturnTrace

MAX_CONTEXTS = 16
MAX_PATHS = 8


class CallerTrace(ReturnTrace):
    def __init__(self, fn, blob, ns, r01_report):
        super().__init__(fn, blob, ns, role='caller')
        self.r01_report = r01_report
        self.contexts, self.callees, self.transfers, self.call_attempts = [], [], [], []

    def statement(self, node, path):
        k = node.kind.name
        if k == 'CALL_EXPR':
            return self.invoke(node, path)
        if k == 'DECL_STMT':
            decls = list(node.get_children())
            if len(decls) == 1 and decls[0].kind.name == 'VAR_DECL':
                exprs = [n for n in decls[0].get_children() if n.kind.is_expression()]
                if len(exprs) == 1 and r02.unwrap(exprs[0]).kind.name == 'CALL_EXPR':
                    return self.invoke(r02.unwrap(exprs[0]), path, decls[0], decls[0], exprs[0])
        if k == 'BINARY_OPERATOR' and self.operator(node) == '=':
            lhs, rhs = list(node.get_children())
            if r02.unwrap(rhs).kind.name == 'CALL_EXPR':
                leaf = r02.unwrap(lhs)
                decl = leaf.referenced if leaf.kind.name == 'DECL_REF_EXPR' else None
                return self.invoke(r02.unwrap(rhs), path, decl, node, rhs, received=True)
        return super().statement(node, path)

    def invoke(self, node, path, target=None, assignment=None, rhs=None, received=False):
        received = received or target is not None
        before = path.snapshot()
        matches = [c for c in self.r01_report['calls'] if c['callsite'] == r01.span(node)]
        attempt = {'callsite_range': r01.span(node), 'call_text': r01.raw(node, self.blob),
                   'caller_path_id': path.path_id, 'before': before,
                   'result_disposition': 'received' if received else 'ignored',
                   'status': 'UNKNOWN', 'reasons': []}
        self.call_attempts.append(attempt)
        if len(matches) != 1:
            self.barrier(node, path, 'no_unique_R01_call_evidence')
            attempt['reasons'] = ['no_unique_R01_call_evidence']
            return [path]
        call = matches[0]
        # Record pre-call reads before stopping on a missing definition. No return
        # propagation follows these reads, and unsupported arguments are never read.
        args = list(node.get_arguments())
        safe_args = all(r01.identifier_reference(a, self.blob) is not None for a in args)
        if safe_args:
            for arg in args:
                self.read(r02.unwrap(arg), path, 'call_argument')
                if path.termination:
                    break
        no_args_contract = (not args and call['reasons'] == ['no_parameter_transfer_to_check']
                            and call['ast_is_trusted'] and call['callee_body_sha256'])
        if path.termination or not safe_args or not (call['status'] == 'PASS' or no_args_contract):
            why = 'unverified_argument_or_direct_call'
            attempt['reasons'] = list(call['reasons']) + ([] if safe_args else ['unsupported_argument'])
            if path.termination is None:
                self.barrier(node, path, why)
            return [path]
        if len(self.contexts) >= MAX_CONTEXTS:
            self.barrier(node, path, 'call_context_budget_exceeded')
            attempt['reasons'] = ['call_context_budget_exceeded']
            return [path]
        argument_records = []
        for m in call['mappings']:
            decl = list(node.get_arguments())[m['actual_index_0based']]
            leaf = r02.unwrap(decl)
            local_slot = self.slot(leaf.referenced)['slot_id']
            vid = before['current'].get(local_slot)
            record = self.by_version.get(vid)
            if (m['status'] != 'PASS' or record is None or record['status'] != 'PASS'
                    or self.slot(leaf.referenced)['r01_caller_slot_id'] != m['actual_slot_id']):
                self.barrier(node, path, 'argument_value_not_bound_to_R01_slot')
                attempt['reasons'] = ['argument_value_not_bound_to_R01_slot']
                return [path]
            argument_records.append({'argument_transfer_id': m['transfer_id'],
                'actual_index_0based': m['actual_index_0based'], 'formal_index_0based': m['formal_index_0based'],
                'caller_pre_slot_id': local_slot, 'caller_pre_version': vid,
                'r01_actual_slot_id': m['actual_slot_id'], 'r01_formal_slot_id': m['formal_slot_id'],
                'formal_declaration_offset': m['formal_declaration']['location']['byte_offset'],
                'type_compatibility': m['conversion'], 'actual_source_range': m['actual_source_range'],
                'formal_source_range': m['formal_declaration']['source_range'], 'status': 'PASS'})
        context = create_context(self.ns, call, path.path_id, before, argument_records)
        context['result_disposition'] = 'received' if received else 'ignored'
        self.contexts.append(context)
        attempt['call_context_id'] = context['call_context_id']
        definition = node.referenced.get_definition()
        callee_ns = {**self.ns, 'call_context_id': context['call_context_id'], 'frame_role': 'callee'}
        callee_trace = ReturnTrace(definition, self.blob, callee_ns, role='callee', context=context)
        callee = callee_trace.run()
        callee['call_context_id'] = context['call_context_id']
        self.callees.append(callee)
        result_type = typed(node.type, self.ns)
        receiving_type = typed(target.type, self.ns) if target is not None else None
        valid_target = bool(target and target.kind.name in {'PARM_DECL','VAR_DECL'}
                            and target.semantic_parent == self.fn
                            and target.storage_class not in {r01.c.StorageClass.STATIC, r01.c.StorageClass.EXTERN}
                            and r02.supported_type(receiving_type))
        conv = (r01.conversion(result_type, receiving_type, typed(rhs.type, self.ns))
                if received and valid_target else {'status': 'N/A' if not received else 'UNKNOWN',
                                                   'reasons': [] if not received else ['unsupported_caller_result_target']})
        # Every callee path must be covered, even if one local return binding PASSes.
        full = callee['status'] == 'PASS' and (not received or conv['status'] == 'PASS')
        reason = 'unsupported_caller_result_target_or_conversion' if received and conv['status'] != 'PASS' else 'incomplete_callee_effect_or_return_paths'
        candidate_paths = callee['path_returns']
        if len(candidate_paths) + len(self.transfers) > MAX_PATHS:
            full = False
            reason = 'caller_path_budget_exceeded'
        outputs = []
        for pr in candidate_paths:
            rv = next((v for v in callee['return_values'] if v['return_event_id'] == pr['return_event_id']), None)
            is_void = result_type['kind'] == 'VOID'
            post_id = r01.stable_id('caller-post-path', [path.path_id, context['call_context_id'], pr['path_id']])
            transfer = {'dataset_id': self.ns['dataset_id'], 'position': self.ns['position'],
                'call_context_id': context['call_context_id'], 'callsite_id': call['callsite_id'],
                'caller_pre_version': [a['caller_pre_version'] for a in argument_records],
                'argument_transfer_id': [a['argument_transfer_id'] for a in argument_records],
                'callee_entry_version': [a['callee_entry_version'] for a in context['callee_entry_bindings']],
                'callee_return_value_id': pr['return_value_id'], 'callee_path_id': pr['path_id'],
                'return_event_id': pr['return_event_id'], 'caller_result_slot_id': None,
                'caller_result_version_id': None, 'caller_post_path_id': post_id if full else None,
                'return_value_received': received, 'return_value_ignored': not received and not is_void,
                'void_normal_return': is_void and pr['normal_return'],
                'result_disposition': 'received' if received else 'void' if is_void else 'ignored',
                'type_compatibility': conv, 'call_effect_coverage': callee['call_effect_coverage'],
                'return_path_completeness': callee['return_path_completeness'],
                'argument_mapping_status': 'PASS' if argument_records else 'N/A',
                'argument_entry_status': ('N/A' if not argument_records else 'PASS'
                    if len(context['callee_entry_bindings']) == len(argument_records)
                    and all(b['status']=='PASS' for b in context['callee_entry_bindings']) else 'UNKNOWN'),
                'return_binding_status': rv['status'] if rv and not is_void else 'N/A' if is_void and pr['normal_return'] else 'UNKNOWN',
                'caller_result_status': 'PASS' if full and received else 'N/A' if not received else 'UNKNOWN',
                'complete_call_status': 'PASS' if full else 'UNKNOWN',
                'status': 'PASS' if full else 'UNKNOWN', 'reasons': [] if full else [reason],
                'source_sha256': self.ns['source_sha256'], 'caller_body_sha256': self.body_hash,
                'callee_body_sha256': callee['body_sha256'], 'callee_return_terminates_caller': False,
                'caller_pre_environment': copy.deepcopy(before), 'caller_post_environment': None,
                'evidence_chain': {'caller_pre': argument_records,
                    'argument_transfer': [a['argument_transfer_id'] for a in argument_records],
                    'callee_entry': copy.deepcopy(context['callee_entry_bindings']),
                    'callee_return': copy.deepcopy(rv), 'caller_post': None},
                'guard_transferred_to_caller': False, 'path_satisfiability_proven': False}
            transfer['return_transfer_id'] = r01.stable_id('return-transfer', [context['call_context_id'], pr['path_id'], post_id])
            self.transfers.append(transfer)
            if full:
                # A return alternative identifies a distinct continuation. Its
                # callee guard remains in evidence; it is not a caller condition.
                post = copy.deepcopy(path)
                post.path_id = post_id
                if received:
                    rec = self.version(target, assignment, post, 'call_return_receive',
                        {'kind': 'call_return', 'call_context_id': context['call_context_id'],
                         'return_transfer_id': transfer['return_transfer_id'],
                         'callee_return_value_id': pr['return_value_id'], 'conversion': conv})
                    transfer.update(caller_result_slot_id=rec['slot_id'], caller_result_version_id=rec['value_version_id'])
                    transfer['evidence_chain']['caller_post'] = {'slot_id': rec['slot_id'],
                        'value_version_id': rec['value_version_id'], 'definition_range': rec['definition_range']}
                transfer['caller_post_environment'] = post.snapshot()
                pr['can_continue_caller'] = True
                outputs.append(post)
        context['status'] = 'PASS' if full else 'UNKNOWN'
        attempt['status'] = context['status']
        if not full:
            attempt['reasons'] = [reason]
            self.barrier(node, path, reason)
            # No caller version or continuation from a partially supported call.
            return [path]
        return outputs


def analyze(path, *, dataset_id, position, build_status, caller=None, candidate_source_paths=()):
    started = time.perf_counter()
    if not isinstance(dataset_id, str) or not dataset_id or type(position) is not int or position < 0:
        raise ValueError('invalid data identity')
    path, blob, tu, nodes, diagnostics = r01.parse(path)
    ns = namespace(path, blob, dataset_id, position, build_status)
    reasons = []
    if build_status != 'synthetic-self-contained':
        reasons.append('missing_original_build_evidence')
    if re.search(rb'^\s*#', blob, re.M):
        reasons.append('preprocessing_not_supported')
    if any(d['severity'] >= r01.c.Diagnostic.Warning for d in diagnostics):
        reasons.append('clang_diagnostics_no_recovery_approval')
    functions = [n for n in nodes if n.kind.name == 'FUNCTION_DECL' and n.is_definition()
                 and n.spelling == caller]
    if caller is None or len(functions) != 1:
        reasons.append('caller_definition_not_uniquely_selected')
    result = {'dataset_id': dataset_id, 'position': position, 'source': str(path),
              'source_sha256': ns['source_sha256'], 'build_evidence': ns['build'],
              'status': 'UNKNOWN', 'reasons': reasons, 'diagnostics': diagnostics,
              'caller': None, 'call_contexts': [], 'callees': [], 'return_transfers': [],
              'call_attempts': [], 'source_return_inventory': [
                  {'source_range': r01.span(n), 'raw': r01.raw(n, blob),
                   'status': 'UNKNOWN', 'method': 'source_inventory_not_approved_propagation'}
                  for n in nodes if n.kind.name == 'RETURN_STMT'],
              'summary_cache_used': False, 'SMT_generated': False, 'safety_decisions': False}
    if not reasons:
        reference = r01.analyze(path, dataset_id=dataset_id, position=position, build_status=build_status,
                                candidate_source_paths=candidate_source_paths)
        if reference['source_sha256'] != ns['source_sha256']:
            raise RuntimeError('source changed between AST snapshots')
        trace = CallerTrace(functions[0], blob, ns, reference)
        result['caller'] = trace.run()
        result.update(call_contexts=trace.contexts, callees=trace.callees, return_transfers=trace.transfers,
                      call_attempts=trace.call_attempts, R01_evidence=reference)
        result['status'] = ('UNKNOWN' if result['caller']['status'] != 'PASS'
                            or any(c['status'] != 'PASS' for c in trace.contexts)
                            else 'PASS' if trace.contexts else 'N/A')
        result['reasons'] = result['caller']['reasons']
    result['context_isolation'] = verify_isolation(result['call_contexts']) if result['call_contexts'] else {'status': 'N/A', 'context_count': 0}
    result['metrics'] = relation_metrics(result)
    result['elapsed_seconds'] = time.perf_counter() - started
    return result


def relation_metrics(report):
    transfers = report['return_transfers']
    values = [v for f in report['callees'] for v in f['return_values'] if v['return_value_id'] is not None]
    return {'argument_entry': counts(t['argument_entry_status'] for t in transfers),
            'return_binding': counts(v['status'] for v in values),
            'caller_result': counts(t['caller_result_status'] for t in transfers),
            'call_effect_coverage': counts(f['call_effect_coverage'] for f in report['callees']),
            'return_path_completeness': counts(f['return_path_completeness'] for f in report['callees']),
            'complete_call': counts(c['status'] for c in report['call_contexts']),
            'ignored_results': counts(t['status'] for t in transfers if t['return_value_ignored']),
            'void_returns': counts(t['status'] for t in transfers if t['void_normal_return']),
            'type_compatibility': counts(t['type_compatibility']['status'] for t in transfers)}


def proposal_from(report):
    return {'contexts': [c['call_context_id'] for c in report['call_contexts']],
            'transfers': [{**{k: copy.deepcopy(t[k]) for k in
                ('return_transfer_id','call_context_id','callee_return_value_id','caller_result_slot_id',
                 'caller_result_version_id','callee_return_terminates_caller','callee_path_id',
                 'caller_pre_version','callee_entry_version','type_compatibility')},
                'callee_return_source_version': t['evidence_chain']['callee_return']['source_value_version_id']
                    if t['evidence_chain']['callee_return'] else None}
                for t in report['return_transfers']]}


def verify_proposal(report, proposed):
    if (report['status'] != 'PASS' or not report['call_contexts']
            or any(t['status'] != 'PASS' for t in report['return_transfers'])):
        return {'status': 'UNKNOWN', 'reasons': ['reference_not_fully_verified']}
    expected = proposal_from(report)
    if not isinstance(proposed, dict) or set(proposed) != set(expected):
        return {'status': 'UNKNOWN', 'reasons': ['proposal_missing_required_evidence']}
    if not isinstance(proposed['transfers'], list) or any(not isinstance(t, dict) or set(t) != set(expected['transfers'][0]) for t in proposed['transfers']):
        return {'status': 'UNKNOWN', 'reasons': ['proposal_transfer_fields_missing']}
    if proposed != expected:
        return {'status': 'REJECT', 'reasons': ['candidate_conflicts_with_verified_context_version_type_or_return_path'],
                'expected': expected, 'proposed': proposed}
    return {'status': 'PASS', 'reasons': []}
