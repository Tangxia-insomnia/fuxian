"""One immutable evidence namespace per callsite/path/pre-state; no cache."""
import copy
from adapter import r01


def create_context(ns, call, caller_path, pre_environment, argument_records):
    payload = {'dataset_id': ns['dataset_id'], 'position': ns['position'],
               'caller_function_identity': call['caller'],
               'callee_function_identity': call['callee'],
               'caller_body_sha256': call['caller_body_sha256'],
               'callee_body_sha256': call['callee_body_sha256'],
               'source_sha256': ns['source_sha256'],
               'callsite_id': call['callsite_id'], 'callsite_range': call['callsite'],
               'caller_path_id': caller_path,
               'caller_pre_environment': copy.deepcopy(pre_environment),
               'parameter_mapping_records': copy.deepcopy(argument_records)}
    return {'call_context_id': r01.stable_id('call-context', payload), **payload,
            'summary_cache_used': False, 'callee_state_reused': False,
            'callee_entry_bindings': [], 'status': 'UNKNOWN'}


def verify_isolation(contexts):
    ids = [x['call_context_id'] for x in contexts]
    return {'status': 'PASS' if len(ids) == len(set(ids)) else 'REJECT',
            'context_count': len(ids), 'distinct_context_count': len(set(ids)),
            'reasons': [] if len(ids) == len(set(ids)) else ['duplicate_call_context']}
