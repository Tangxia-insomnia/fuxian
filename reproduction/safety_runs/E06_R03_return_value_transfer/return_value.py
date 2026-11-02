"""Path-local return records layered over unchanged R02 def-use rules."""
import copy
from adapter import r01, r02, StateEnvironment, preflight, typed


class ReturnTrace(r02.FunctionTrace):
    def __init__(self, fn, blob, ns, *, role, context=None):
        super().__init__(fn, blob, ns)
        self.role, self.context = role, context
        self.return_values, self.path_returns = [], []
        self.final_paths = []

    def version(self, *args, **kwargs):
        record = super().version(*args, **kwargs)
        record.update(frame_role=self.role, call_context_id=self.context['call_context_id'] if self.context else None)
        return record

    def return_statement(self, node, path, implicit=False):
        exprs = [] if implicit else [n for n in node.get_children() if n.kind.is_expression()]
        event = self.event(node, path, 'callee_return' if self.role == 'callee' else 'caller_return')
        expected = typed(self.fn.result_type, self.ns)
        item = {'dataset_id': self.ns['dataset_id'], 'position': self.ns['position'],
                'caller_function_identity': self.context['caller_function_identity'] if self.context else self.function,
                'callee_function_identity': self.function if self.role == 'callee' else None,
                'call_context_id': self.context['call_context_id'] if self.context else None,
                'callsite_id': self.context['callsite_id'] if self.context else None,
                'callee_path_id': path.path_id, 'frame_role': self.role,
                'return_event_id': event['event_id'], 'return_source_range': r01.span(node),
                'raw_return_expression': r01.raw(exprs[0], self.blob) if len(exprs) == 1 else None,
                'return_type': expected, 'value_category': 'void' if not exprs else 'unknown_expression',
                'source_slot_id': None, 'source_value_version_id': None,
                'callee_current_versions': dict(path.current), 'return_guard': copy.deepcopy(path.guards),
                'source_sha256': self.ns['source_sha256'], 'body_sha256': self.body_hash,
                'status': 'UNKNOWN', 'reasons': [], 'type_compatibility': None}
        if not exprs and expected['kind'] == 'VOID':
            item['status'] = 'PASS'
        elif len(exprs) != 1 or not r02.supported_type(expected):
            item['reasons'].append('unsupported_return_type_or_expression_count')
        else:
            expr, leaf = exprs[0], r02.unwrap(exprs[0])
            k = leaf.kind.name
            actual = typed(leaf.type, self.ns)
            conv = r01.conversion(actual, expected, typed(expr.type, self.ns))
            item['type_compatibility'] = conv
            if k == 'DECL_REF_EXPR':
                read = self.read(leaf, path, 'return_value')
                if read and read['status'] == 'PASS':
                    item.update(value_category='parameter' if leaf.referenced.kind.name == 'PARM_DECL' else 'local_variable',
                                source_slot_id=read['slot_id'], source_value_version_id=read['value_version_id'],
                                source_read_id=read['read_id'])
                    if conv['status'] == 'PASS':
                        item['status'] = 'PASS'
                    else:
                        item['reasons'].append('unsupported_return_conversion')
                else:
                    item['reasons'].append('no_verified_return_reaching_definition')
            elif k in {'INTEGER_LITERAL', 'FLOATING_LITERAL'}:
                text = r01.raw(leaf, self.blob)
                item.update(value_category='constant', literal={'raw': text, 'type': actual,
                            'source_range': r01.span(leaf), 'evaluated_as_mathematical_integer': False})
                if (expected['kind'] == 'POINTER' and k == 'INTEGER_LITERAL' and text == '0'
                        and typed(expr.type, self.ns)['canonical'] == expected['canonical']):
                    item['type_compatibility'] = {'status': 'PASS', 'kind': 'clang_null_pointer_constant',
                                                  'actual_type': actual, 'formal_type': expected,
                                                  'ast_argument_type': typed(expr.type, self.ns)}
                    item['status'] = 'PASS'
                elif conv['status'] == 'PASS':
                    item['status'] = 'PASS'
                else:
                    item['reasons'].append('unsupported_return_literal_conversion')
            else:
                # Do not recursively analyze return f(), arithmetic or casts.
                item['reasons'].append('unsupported_return_expression_' + k)
        if item['status'] != 'PASS' and path.termination is None:
            self.barrier(node, path, item['reasons'][0] if item['reasons'] else 'unverified_return')
        item['callee_current_versions'] = dict(path.current) if item['status'] != 'PASS' else item['callee_current_versions']
        item['return_value_id'] = (r01.stable_id('return-value', [self.ns, event['event_id'], item['source_value_version_id']])
                                   if item['value_category'] != 'void' else None)
        self.return_values.append(item)
        normal = item['status'] == 'PASS' and path.termination is None
        self.path_returns.append({'path_id': path.path_id, 'guard': copy.deepcopy(path.guards),
                                  'return_event_id': event['event_id'], 'return_value_id': item['return_value_id'],
                                  'normal_return': normal, 'can_continue_caller': False,
                                  'status': item['status'], 'reasons': list(item['reasons']),
                                  'call_context_id': item['call_context_id']})
        if normal:
            path.termination = 'RETURN'

    def statement(self, node, path):
        if node.kind.name == 'RETURN_STMT':
            self.return_statement(node, path)
            return [path]
        return super().statement(node, path)

    def run(self):
        initial = StateEnvironment(r01.stable_id('r03-path-entry', [self.ns, self.function['declaration_id']]))
        reasons = preflight(self.fn)
        if reasons:
            self.barrier(self.fn, initial, reasons[0])
            self.reasons.extend(reasons[1:])
        for parameter in self.fn.get_arguments():
            if initial.termination:
                break
            item = self.slot(parameter)
            if not r02.supported_type(item['type']):
                self.barrier(parameter, initial, 'unsupported_parameter_type')
                break
            value = {'kind': 'unconstrained_entry_value'}
            if self.context:
                matching = [a for a in self.context['parameter_mapping_records']
                            if a['formal_declaration_offset'] == parameter.location.offset]
                if len(matching) != 1 or matching[0]['status'] != 'PASS':
                    self.barrier(parameter, initial, 'missing_verified_argument_binding')
                    break
                arg = matching[0]
                value = {'kind': 'argument_transfer', 'argument_transfer_id': arg['argument_transfer_id'],
                         'caller_pre_value_version_id': arg['caller_pre_version'],
                         'caller_pre_slot_id': arg['caller_pre_slot_id'], 'conversion': arg['type_compatibility']}
            record = self.version(parameter, parameter, initial, 'parameter_entry', value)
            if self.context:
                self.context['callee_entry_bindings'].append({'argument_transfer_id': arg['argument_transfer_id'],
                    'caller_pre_version': arg['caller_pre_version'], 'caller_pre_slot_id': arg['caller_pre_slot_id'],
                    'callee_entry_version': record['value_version_id'], 'callee_slot_id': record['slot_id'],
                    'formal_declaration_offset': parameter.location.offset, 'slots_merged': False, 'status': 'PASS'})
        body = next(n for n in self.fn.get_children() if n.kind.name == 'COMPOUND_STMT')
        self.final_paths = self.compound(body, [initial])
        for path in self.final_paths:
            if any(p['path_id'] == path.path_id for p in self.path_returns):
                continue
            if path.termination is None and self.fn.result_type.kind.name == 'VOID':
                self.return_statement(body, path, implicit=True)
                self.return_values[-1]['implicit_void_fallthrough'] = True
                # A compound may contain expressions; this event has no return operand.
            else:
                self.path_returns.append({'path_id': path.path_id, 'guard': copy.deepcopy(path.guards),
                    'return_event_id': None, 'return_value_id': None, 'normal_return': False,
                    'can_continue_caller': False, 'status': 'UNKNOWN',
                    'reasons': ['unknown_effect_stop' if path.termination else 'nonvoid_fallthrough'],
                    'call_context_id': self.context['call_context_id'] if self.context else None})
                self.reasons.append('unknown_effect_stop' if path.termination else 'nonvoid_fallthrough')
        complete = bool(self.path_returns) and all(p['status'] == 'PASS' and p['normal_return'] for p in self.path_returns)
        status = 'PASS' if complete and not self.reasons else 'UNKNOWN'
        return {'function': self.function, 'frame_role': self.role, 'body_sha256': self.body_hash,
                'status': status, 'reasons': list(dict.fromkeys(self.reasons)),
                'slots': list(self.slots.values()), 'versions': self.versions, 'reads': self.reads,
                'events': self.events, 'state_snapshots': self.snapshots,
                'final_environments': [p.snapshot() for p in self.final_paths],
                'unprocessed_ranges': self.blocked_ranges, 'return_values': self.return_values,
                'path_returns': self.path_returns, 'return_path_completeness': 'PASS' if complete else 'UNKNOWN',
                'call_effect_coverage': 'PASS' if status == 'PASS' else 'UNKNOWN',
                'paths_merged': False, 'SMT_generated': False}
