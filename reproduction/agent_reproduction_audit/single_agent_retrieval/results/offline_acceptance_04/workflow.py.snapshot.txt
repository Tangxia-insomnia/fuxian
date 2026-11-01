"""Offline reference state machine; no model, MCP transport or C semantic engine.

Requests are trace objects only. A future Harness session must execute its own
native tools. Offline callers supply recorded/synthetic replies explicitly.
"""
import copy
from dataclasses import dataclass
import hashlib
import json
import re

UPSTREAM = '4efb4b9bf7e845e180451b43ba29a25e3edaa0e3'
HISTORY = '29ca96e0d5f860d1f4ce07cd3e54e5e25732d1a1'
BRIDGE = 'llm4pfa-mcp-bridge-v1'
TOOLS = {
    'get_alert_context': 'mcp__llm4pfa__get_alert_context',
    'lookup_function_source': 'mcp__llm4pfa__lookup_function_source',
}
DATASETS = {
    'codeql_linux': ('benchmark/NPD/codeql/codeql_kernel69_nullpointer.json', 'baseline/NPD-codeql-linux.json'),
    'codeql_libav': ('benchmark/NPD/codeql/codeql_libav_nullpointer.json', 'baseline/NPD-codeql-libav.json'),
    'codeql_openssl': ('benchmark/NPD/codeql/codeql_openssl_nullpointer.json', 'baseline/NPD-codeql-openssl.json'),
    'cppcheck_linux': ('benchmark/NPD/cppcheck/cppcheck_linux_nullpointer.json', 'baseline/NPD-cppcheck-linux.json'),
    'cppcheck_libav': ('benchmark/NPD/cppcheck/cppcheck_libav_nullpointer.json', 'baseline/NPD-cppcheck-libav.json'),
    'cppcheck_openssl': ('benchmark/NPD/cppcheck/cppcheck_openssl_nullpointer.json', 'baseline/NPD-cppcheck-openssl.json'),
    'infer_libav': ('benchmark/NPD/infer/infer_libav_nullpointer.json', 'baseline/NPD-infer-libav.json'),
    'infer_openssl': ('benchmark/NPD/infer/infer_openssl_nullpointer.json', 'baseline/NPD-infer-openssl.json'),
}
IDENTIFIER = re.compile(r'[A-Za-z_][A-Za-z0-9_]{0,127}\Z')
SHA = re.compile(r'[0-9a-f]{64}\Z')


class ContractError(ValueError):
    pass


def require(ok, reason):
    if not ok:
        raise ContractError(reason)


def text_sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def object_sha(value):
    return text_sha(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')))


def envelope(raw):
    """Accept a bridge envelope or recorded MCP result; reject disagreeing views."""
    require(isinstance(raw, dict), 'malformed_response')
    if 'structuredContent' in raw:
        result = raw['structuredContent']
        texts = [x.get('text') for x in raw.get('content', []) if x.get('type') == 'text']
        require(len(texts) == 1 and json.loads(texts[0]) == result, 'mcp_content_disagrees')
        require(isinstance(result, dict) and type(result.get('ok')) is bool, 'malformed_envelope')
        require(type(raw.get('isError')) is bool and raw['isError'] == (not result['ok']), 'mcp_error_flag_disagrees')
    else:
        result = raw
    require(type(result.get('ok')) is bool and result.get('bridge_version') == BRIDGE, 'malformed_envelope')
    return copy.deepcopy(result)


def lexical_call(code, line, text, name):
    """Only check an exact, visible direct-call token; never prove C binding.

    Comments/quoted literals are masked. Macros, prototypes and complex C may
    still require manual interpretation; returned edges remain candidates.
    """
    require(type(line) is int and 1 <= line <= len(code.splitlines()), 'invalid_callsite_line')
    require(code.splitlines()[line - 1] == text, 'callsite_text_mismatch')
    masked = re.sub(r'/\*.*?\*/|//[^\n]*|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'',
                    lambda m: ''.join('\n' if c == '\n' else ' ' for c in m[0]), code, flags=re.S)
    visible = masked.splitlines()[line - 1]
    pattern = r'(?<![\w.>])' + re.escape(name) + r'\s*\('
    matches = list(re.finditer(pattern, visible))
    require(len(matches) == 1, 'callsite_not_unique_direct_token')
    offset = sum(len(s) for s in masked.splitlines(keepends=True)[:line - 1]) + matches[0].start()
    require(not masked[:offset].rstrip().endswith(('.', '->')), 'indirect_member_call_unsupported')


@dataclass(frozen=True)
class Task:
    dataset_id: str
    position: int
    analysis_question: str
    initial_states: str
    max_context_iterations: int = 5

    def __post_init__(self):
        require(isinstance(self.dataset_id, str) and self.dataset_id in DATASETS, 'dataset_not_allowed')
        require(type(self.position) is int and self.position >= 0, 'invalid_position')
        require(type(self.max_context_iterations) is int and 1 <= self.max_context_iterations <= 5, 'invalid_round_limit')
        require(isinstance(self.analysis_question, str) and bool(self.analysis_question.strip()), 'missing_analysis_question')
        require(isinstance(self.initial_states, str) and bool(self.initial_states.strip()), 'missing_initial_states')


class RetrievalSession:
    """A replay verifier, not a Harness plugin or autonomous Agent runtime."""
    def __init__(self, task, fixture_kind='saved_mcp_responses'):
        require(fixture_kind in {'saved_mcp_responses', 'synthetic'}, 'invalid_fixture_kind')
        self.task, self.fixture_kind = task, fixture_kind
        self.state, self.stop_reason = 'new', None
        self.context, self.binding = None, None
        self.nodes, self.edges, self.events = {}, [], []
        self.pending, self.lookup_rounds, self.counter, self.context_iterations = None, 0, 0, 0
        self.unresolved = []

    def _event(self, kind, **fields):
        self.events.append({'event_id': len(self.events) + 1, 'kind': kind, **copy.deepcopy(fields)})

    def _block(self, reason):
        self.state, self.stop_reason = 'blocked', reason
        self._event('stop', reason=reason, cancelled_request=self.pending)
        self.pending = None
        return None

    def _request(self, name, extra=None, edge=None):
        self.counter += 1
        args = {'dataset_id': self.task.dataset_id, 'position': self.task.position, **(extra or {})}
        self.pending = {'call_id': f'offline-{self.counter:03d}', 'tool': name,
                        'harness_tool': TOOLS[name], 'arguments': args, 'edge': edge}
        self._event('request', request=self.pending)
        return copy.deepcopy(self.pending)

    def begin(self):
        if self.state != 'new':
            return self._block('context_request_out_of_order')
        self.state = 'awaiting_context'
        return self._request('get_alert_context')

    def lookup(self, parent_sha, name, line, callsite_text, analysis_need):
        self._event('lookup_proposal', parent_sha256=parent_sha, name=name, line=line,
                    callsite_text=callsite_text, analysis_need=analysis_need)
        if self.state != 'ready':
            return self._block('lookup_out_of_order')
        if self.context_iterations >= self.task.max_context_iterations:
            return self._block('context_iteration_limit')
        self.context_iterations += 1  # Includes local reuse; a cache cycle cannot loop forever.
        try:
            require(isinstance(name, str) and IDENTIFIER.fullmatch(name), 'invalid_function_name')
            require(parent_sha in self.nodes, 'unknown_parent_source')
            require(isinstance(analysis_need, str) and bool(analysis_need.strip()), 'missing_analysis_need')
            parent = self.nodes[parent_sha]
            lexical_call(parent['code'], line, callsite_text, name)
            edge = {'caller_sha256': parent_sha, 'caller': parent['function'], 'callee': name,
                    'callsite_line_in_body': line, 'callsite_text': callsite_text,
                    'analysis_need': analysis_need, 'binding_status': 'lexical_candidate_not_semantic_proof'}
            known = [h for h, node in self.nodes.items() if node['function'] == name]
            require(len(known) <= 1, 'multiple_known_definitions')
            if known:
                self.edges.append({**edge, 'callee_sha256': known[0], 'retrieval': 'reuse'})
                self._event('reuse', edge=self.edges[-1], reason='source_already_available_no_tool_request')
                return None
            self.lookup_rounds += 1  # Count attempts, including tool errors; never retry indefinitely.
            self.state = 'awaiting_lookup'
            return self._request('lookup_function_source', {'name': name}, edge)
        except (ContractError, TypeError, KeyError) as exc:
            return self._block('invalid_lookup_proposal:' + str(exc))

    def _binding(self, evidence):
        require(isinstance(evidence, dict), 'missing_evidence')
        ds, hist = DATASETS[self.task.dataset_id]
        require(evidence.get('dataset_path') == ds and evidence.get('historical_path') == hist,
                'evidence_path_binding_mismatch')
        require(evidence.get('historical_ref') == HISTORY, 'historical_ref_mismatch')
        keys = ('dataset_path', 'dataset_sha256', 'historical_path', 'historical_ref',
                'historical_artifact_sha256', 'context_module_sha256')
        result = {k: evidence.get(k) for k in keys}
        require(all(isinstance(result[k], str) and SHA.fullmatch(result[k]) for k in
                    ('dataset_sha256', 'historical_artifact_sha256', 'context_module_sha256')), 'invalid_evidence_hash')
        if self.binding is not None:
            require(result == self.binding, 'evidence_changed_within_session')
        return result

    def _source(self, name, code, body_sha, origins, binding):
        require(isinstance(name, str) and IDENTIFIER.fullmatch(name), 'invalid_source_name')
        require(isinstance(code, str) and code.strip() and text_sha(code) == body_sha, 'source_hash_mismatch')
        require(isinstance(origins, list) and bool(origins), 'missing_source_locations')
        for origin in origins:
            require(isinstance(origin, dict), 'malformed_source_location')
            kind = origin.get('kind')
            if self.fixture_kind == 'synthetic':
                require(kind == 'synthetic_fixture', 'synthetic_source_not_labelled')
            else:
                require(kind in {'official_benchmark', 'pinned_historical_baseline'}, 'unrecognized_source_kind')
            historical = kind == 'pinned_historical_baseline'
            artifact = binding['historical_artifact_sha256'] if historical else binding['dataset_sha256']
            path = binding['historical_path'] if historical else binding['dataset_path']
            require(origin.get('artifact_sha256') == artifact and origin.get('path') == path, 'source_artifact_mismatch')
            require(isinstance(origin.get('json_pointer'), str) and origin['json_pointer'].startswith('/'), 'missing_json_pointer')
            if historical:
                require(origin.get('git_ref') == HISTORY, 'source_git_ref_mismatch')
        return {'function': name, 'code': code, 'body_sha256': body_sha, 'source_locations': copy.deepcopy(origins)}

    def accept(self, call_id, raw):
        self._event('response', call_id=call_id, raw=raw, raw_sha256=object_sha(raw))
        if self.pending is None or call_id != self.pending['call_id']:
            return self._block('response_call_id_mismatch')
        request = self.pending
        try:
            result = envelope(raw)
            if not result['ok']:
                require(isinstance(result.get('error', {}).get('code'), str), 'malformed_tool_error')
                return self._block('tool_error:' + result['error']['code'])
            data = result['data']
            require(data.get('dataset_id') == self.task.dataset_id and type(data.get('position')) is int
                    and data['position'] == self.task.position, 'sample_binding_mismatch')
            binding = self._binding(data.get('evidence'))
            if request['tool'] == 'get_alert_context':
                nodes, edges = self._context(data, binding)  # Commit only after every frame validates.
                self.nodes, self.edges = nodes, edges
                self.context, self.binding = copy.deepcopy(data), binding
            else:
                name = request['arguments']['name']
                require(data.get('function') == name, 'returned_function_mismatch')
                require(data.get('selection_tier') in {'sample_chain', 'dataset_index'}, 'invalid_selection_tier')
                node = self._source(name, data.get('code'), data.get('body_sha256'), data.get('source_locations'), binding)
                require(not any(n['function'] == name and h != node['body_sha256'] for h, n in self.nodes.items()),
                        'definition_identity_conflict')
                self.nodes[node['body_sha256']] = node
                self.edges.append({**request['edge'], 'callee_sha256': node['body_sha256'], 'retrieval': 'tool_response'})
            self.pending, self.state = None, 'ready'
            self._event('accepted', call_id=call_id)
            return True
        except (ContractError, KeyError, TypeError, ValueError, AttributeError) as exc:
            return self._block('invalid_response:' + str(exc))

    def _context(self, data, binding):
        frames, sources = data['frames'], data['frame_sources']
        require(isinstance(frames, list) and bool(frames) and len(frames) == len(sources), 'incomplete_frames')
        require(data.get('position_basis') == 'zero-based JSON array position', 'position_basis_mismatch')
        require(isinstance(data.get('sample_id'), str) and bool(data['sample_id']), 'missing_sample_id')
        require(data['function_chain'] == [f['function'] for f in frames]
                and data['function_call'] == [f['code'] for f in frames], 'chain_view_mismatch')
        require(data['target_function'] == frames[0]['function'] and data['variable']['name'] == frames[0]['var_name']
                and data['sink']['text'].strip() == frames[0]['target'].strip(), 'alert_view_mismatch')
        nodes, edges = {}, []
        for i, (frame, source) in enumerate(zip(frames, sources)):
            require(type(frame.get('level')) is int and frame['level'] == i and type(source.get('level')) is int
                    and source['level'] == i and source['body_sha256'] == frame['body_sha256'], 'frame_identity_mismatch')
            require(frame['target'].strip() and frame['target'] in frame['code'], 'target_not_in_source')
            node = self._source(frame['function'], frame['code'], frame['body_sha256'], source['source_locations'], binding)
            require(not any(n['function'] == node['function'] and h != node['body_sha256'] for h, n in nodes.items()),
                    'multiple_context_definitions')
            nodes[node['body_sha256']] = node
            if i:
                prev = frames[i - 1]
                edges.append({'caller': prev['function'], 'caller_sha256': prev['body_sha256'],
                              'callee': frame['function'], 'callee_sha256': frame['body_sha256'],
                              'callsite_text': prev['target'], 'retrieval': 'saved_alert_trace',
                              'binding_status': 'repository_recovered_not_independently_reproved'})
        return nodes, edges

    def finish(self, reason, unresolved=None):
        if self.state != 'ready':
            return self._block('finish_without_ready_context')
        if reason not in {'analysis_need_satisfied', 'unsupported_context', 'manual_stop'}:
            return self._block('invalid_stop_reason')
        if not isinstance(unresolved or [], list) or any(not isinstance(x, str) for x in (unresolved or [])):
            return self._block('invalid_unresolved_list')
        self.state, self.stop_reason, self.unresolved = 'stopped', reason, copy.deepcopy(unresolved or [])
        self._event('stop', reason=reason, unresolved=self.unresolved)

    def export(self):
        return copy.deepcopy({
            'schema_version': 'single-agent-retrieval-offline-v1', 'execution_mode': 'offline_replay_only',
            'fixture_kind': self.fixture_kind, 'upstream_commit': UPSTREAM,
            'task': vars(self.task), 'state': self.state, 'stop_reason': self.stop_reason,
            'context_iterations_simulated': self.context_iterations,
            'lookup_attempts_simulated': self.lookup_rounds, 'pending_request': self.pending,
            'alert_context': self.context, 'evidence_binding': self.binding,
            'source_nodes': list(self.nodes.values()), 'call_edges': self.edges,
            'events': self.events, 'unresolved': self.unresolved,
            'actual_tool_calls_this_run': 0, 'new_model_calls': 0, 'new_api_cost_cny': 0,
            'limitations': ['No Harness execution; decisions are supplied by offline fixtures.',
                            'Source hashes/locators are evidence integrity, not whole-project build proof.',
                            'Call edges/relevance are candidates, not C semantics or feasibility proofs.',
                            'No SMT, Z3, bug classification or alert filtering is performed.'],
        })
