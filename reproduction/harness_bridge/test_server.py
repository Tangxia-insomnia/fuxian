"""Offline unit tests and a real MCP stdio client/server round trip.

Does not launch Harness or import any model/engine. Only Git reads and local
subprocess pipes are used. Ambiguity/missing-context fixtures are explicitly
synthetic; official datasets are never changed.
"""
import argparse
import asyncio
import copy
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from tools import (ContextRepository, ContextUnavailable, RetrievalTools, ROOT,
                   body_digest, function_name)
from completion.context import compact
from worker import RetrievalWorker
import subprocess

TRACES = []


def trace(name, inputs, output, kind='python_wrapper', fixture=None):
    TRACES.append({'tool': name, 'input': inputs, 'output': copy.deepcopy(output),
                   'transport': kind, 'fixture': fixture})


class ToolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bridge = RetrievalTools()
        cls.state = cls.bridge._load('codeql_linux')

    def invoke(self, name, args, bridge=None, fixture=None):
        result = (bridge or self.bridge).invoke(name, args)
        trace(name, args, result, fixture=fixture)
        return result

    def test_normal_context_and_original_hashes(self):
        result = self.invoke('get_alert_context', {'dataset_id': 'codeql_linux', 'position': 10})
        self.assertTrue(result['ok'])
        original = self.state['repo'].prepare(10)
        for key in ('frames', 'function_call', 'origin', 'historical_ref', 'duplicate_equivalent_matches'):
            self.assertEqual(result['data'][key], original[key])
        for frame in result['data']['frames']:
            self.assertEqual(frame['body_sha256'], body_digest(frame['code']))
            self.assertIn(frame['body_sha256'], self.state['sources'])

    def test_multiframe_chain_is_not_truncated(self):
        result = self.invoke('get_alert_context', {'dataset_id': 'codeql_linux', 'position': 12})
        self.assertTrue(result['ok'])
        original = self.state['repo'].prepare(12)
        self.assertEqual(len(result['data']['frames']), 2)
        self.assertEqual(result['data']['frames'], original['frames'])
        self.assertEqual(result['data']['function_call'], original['function_call'])

    def test_lookup_local_source_and_provenance(self):
        result = self.invoke('lookup_function_source', {'dataset_id': 'codeql_linux', 'position': 10,
                                                       'name': 'tcp_sendmsg_locked'})
        self.assertTrue(result['ok'])
        original = self.state['repo'].lookup('tcp_sendmsg_locked', self.state['repo'].prepare(10)['function_call'])
        self.assertEqual(result['data']['code'], original)
        self.assertEqual(result['data']['body_sha256'], body_digest(original))
        self.assertEqual(result['data']['selection_tier'], 'sample_chain')
        self.assertTrue(result['data']['source_locations'])

    def test_lookup_global_source(self):
        result = self.invoke('lookup_function_source', {'dataset_id': 'codeql_linux', 'name': 'tcp_sendmsg_locked'})
        self.assertTrue(result['ok'])
        self.assertEqual(result['data']['selection_tier'], 'dataset_index')

    def test_function_missing(self):
        result = self.invoke('lookup_function_source', {'dataset_id': 'codeql_linux', 'name': 'llm4pfa_nonexistent_fixture_name'})
        self.assertEqual(result['error']['code'], 'FUNCTION_NOT_FOUND')

    def fixture_bridge(self, local_bodies=None):
        # Construct only an in-memory test repository; no new MCP debug flag.
        bridge = RetrievalTools()
        repo = ContextRepository.__new__(ContextRepository)
        bodies = ['int duplicate(void) { return 1; }', 'int duplicate(void) { return 2; }']
        repo.bodies = {'duplicate': {compact(b): b for b in bodies}}
        repo.data = [{}]
        original_state = getattr(ToolTests, 'state', None) or RetrievalTools()._load('codeql_linux')
        state = dict(original_state, repo=repo, names={'duplicate': [body_digest(b) for b in bodies]},
                     sources={body_digest(b): {'code': b, 'origins': [{'kind': 'synthetic_fixture',
                               'json_pointer': f'/definitions/{i}'}]} for i, b in enumerate(bodies)})
        bridge._repos['codeql_linux'] = state
        if local_bodies is not None:
            repo.prepare = lambda _: {'function_call': [bodies[i] for i in local_bodies]}
        return bridge

    def test_multiple_definitions_rejected(self):
        result = self.invoke('lookup_function_source', {'dataset_id': 'codeql_linux', 'name': 'duplicate'},
                             self.fixture_bridge(), 'two distinct synthetic definitions')
        self.assertFalse(result['ok'])
        self.assertEqual(result['error']['code'], 'FUNCTION_AMBIGUOUS')
        self.assertEqual(result['error']['details']['definition_count'], 2)
        self.assertNotIn('data', result)

    def test_local_chain_has_priority_over_global_ambiguity(self):
        result = self.invoke('lookup_function_source', {'dataset_id': 'codeql_linux', 'name': 'duplicate', 'position': 0},
                             self.fixture_bridge([0]), 'one local definition, two global synthetic definitions')
        self.assertTrue(result['ok'])
        self.assertEqual(result['data']['selection_tier'], 'sample_chain')

    def test_ambiguous_local_chain_rejected(self):
        result = self.invoke('lookup_function_source', {'dataset_id': 'codeql_linux', 'name': 'duplicate', 'position': 0},
                             self.fixture_bridge([0, 1]), 'two conflicting synthetic local definitions')
        self.assertEqual(result['error']['code'], 'FUNCTION_AMBIGUOUS')

    def test_missing_context_fails_explicitly(self):
        with patch.object(self.state['repo'], 'prepare', side_effect=ContextUnavailable('synthetic missing call chain')):
            result = self.invoke('get_alert_context', {'dataset_id': 'codeql_linux', 'position': 10},
                                 fixture='synthetic ContextUnavailable, no official inputs changed')
        self.assertEqual(result['error']['code'], 'CONTEXT_UNAVAILABLE')

    def test_malformed_context_fails_explicitly(self):
        with patch.object(self.state['repo'], 'prepare', side_effect=KeyError('location')):
            result = self.invoke('get_alert_context', {'dataset_id': 'codeql_linux', 'position': 10},
                                 fixture='synthetic malformed context')
        self.assertEqual(result['error']['code'], 'CONTEXT_MALFORMED')

    def test_sample_missing_and_negative_index(self):
        for position, expected in [(10**9, 'SAMPLE_NOT_FOUND'), (-1, 'INVALID_ARGUMENT')]:
            with self.subTest(position=position):
                result = self.invoke('get_alert_context', {'dataset_id': 'codeql_linux', 'position': position})
                self.assertEqual(result['error']['code'], expected)

    def test_invalid_parameters_and_path_injection(self):
        cases = [
            ('get_alert_context', {}, 'INVALID_ARGUMENT'),
            ('get_alert_context', {'dataset_id': 'codeql_linux', 'position': True}, 'INVALID_ARGUMENT'),
            ('get_alert_context', {'dataset_id': 'codeql_linux', 'position': '10'}, 'INVALID_ARGUMENT'),
            ('get_alert_context', {'dataset_id': 'codeql_linux', 'position': 1.0}, 'INVALID_ARGUMENT'),
            ('get_alert_context', {'dataset_id': '../.env', 'position': 0}, 'DATASET_NOT_ALLOWED'),
            ('get_alert_context', {'dataset_id': 'C:/Windows/win.ini', 'position': 0}, 'DATASET_NOT_ALLOWED'),
            ('get_alert_context', {'dataset_id': 'codeql_linux', 'position': 0, 'path': '.env'}, 'INVALID_ARGUMENT'),
            ('lookup_function_source', {'dataset_id': 'codeql_linux', 'name': '../x'}, 'INVALID_ARGUMENT'),
            ('lookup_function_source', {'dataset_id': 'codeql_linux', 'name': 'x;system()'}, 'INVALID_ARGUMENT'),
            ('lookup_function_source', {'dataset_id': 'codeql_linux', 'name': ''}, 'INVALID_ARGUMENT'),
            ('lookup_function_source', {'dataset_id': 'codeql_linux', 'name': 'x'*129}, 'INVALID_ARGUMENT'),
            ('lookup_function_source', {'dataset_id': 'codeql_linux', 'name': 'x', 'local_chain': ['injected code']}, 'INVALID_ARGUMENT'),
            ('CompletedEngine.run', {}, 'UNKNOWN_TOOL'), ('completed_source', {}, 'UNKNOWN_TOOL'),
        ]
        for name, args, expected in cases:
            with self.subTest(name=name, args=args):
                self.assertEqual(self.invoke(name, args)['error']['code'], expected)

    def test_no_model_engine_or_safety_guard_import(self):
        forbidden = ['completion.engine', 'completion.model', 'safety.policy', 'offline_guard']
        self.assertFalse([name for name in forbidden if name in sys.modules])

    def test_source_hash_mismatch_is_not_success(self):
        context = copy.deepcopy(self.state['repo'].prepare(10))
        context['frames'][0]['body_sha256'] = '0'*64
        with patch.object(self.state['repo'], 'prepare', return_value=context):
            result = self.invoke('get_alert_context', {'dataset_id': 'codeql_linux', 'position': 10},
                                 fixture='synthetic tampered frame hash')
        self.assertEqual(result['error']['code'], 'SOURCE_HASH_MISMATCH')

    def test_worker_stdin_is_closed_and_environment_excludes_keys(self):
        payload = {'ok': True, 'data': {'fixture': True}}
        completed = subprocess.CompletedProcess([], 0, json.dumps(payload).encode(), b'')
        with patch.dict(os.environ, {'DEEPSEEK_APIkey': 'synthetic-test-placeholder'}):
            with patch('worker.subprocess.run', return_value=completed) as run:
                result = RetrievalWorker().invoke('get_alert_context', {'dataset_id': 'codeql_linux', 'position': 10})
        self.assertEqual(result, payload)
        self.assertEqual(run.call_args.kwargs['stdin'], subprocess.DEVNULL)
        self.assertNotIn('DEEPSEEK_APIkey', run.call_args.kwargs['env'])
        self.assertEqual(run.call_args.kwargs['timeout'], 30)

    def test_worker_failures_are_explicit(self):
        cases = [('timeout', subprocess.TimeoutExpired('synthetic-worker', 30), 'RETRIEVAL_TIMEOUT'),
                 ('launch_error', OSError('synthetic-worker'), 'WORKER_FAILED')]
        for label, exc, code in cases:
            with self.subTest(label=label):
                with patch('worker.subprocess.run', side_effect=exc):
                    result = RetrievalWorker().invoke('get_alert_context', {'dataset_id': 'codeql_linux', 'position': 10})
                trace('get_alert_context', {'dataset_id': 'codeql_linux', 'position': 10}, result,
                      'worker_handler', 'synthetic ' + label)
                self.assertEqual(result['error']['code'], code)


class ProtocolTests(unittest.TestCase):
    def test_real_stdio_initialize_list_call_and_errors(self):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        async def run():
            parameters = StdioServerParameters(command=sys.executable,
                        args=['-B', str(HERE / 'server.py')], cwd=str(HERE),
                        env={'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONUTF8': '1'})
            async with stdio_client(parameters) as (read, write):
                async with ClientSession(read, write, read_timeout_seconds=timedelta(seconds=30)) as session:
                    init = await session.initialize()
                    trace('initialize', {}, init.model_dump(mode='json'), 'mcp_stdio')
                    listed = await session.list_tools()
                    trace('tools/list', {}, listed.model_dump(mode='json'), 'mcp_stdio')
                    self.assertEqual({t.name for t in listed.tools}, {'get_alert_context', 'lookup_function_source'})
                    for tool in listed.tools:
                        self.assertTrue(tool.annotations.readOnlyHint)
                        self.assertFalse(tool.inputSchema['additionalProperties'])
                    cases = [
                        ('get_alert_context', {'dataset_id': 'codeql_linux', 'position': 12}, None),
                        ('lookup_function_source', {'dataset_id': 'codeql_linux', 'name': 'kfree', 'position': 12}, None),
                        ('lookup_function_source', {'dataset_id': 'codeql_linux', 'name': 'llm4pfa_nonexistent_fixture_name'}, 'FUNCTION_NOT_FOUND'),
                        ('get_alert_context', {'dataset_id': 'codeql_linux', 'position': 999999}, 'SAMPLE_NOT_FOUND'),
                        ('get_alert_context', {'dataset_id': '../../.env', 'position': 0}, 'DATASET_NOT_ALLOWED'),
                        ('get_alert_context', {'dataset_id': 'codeql_linux', 'position': True}, 'INVALID_ARGUMENT'),
                        ('lookup_function_source', {'dataset_id': 'codeql_linux', 'name': 'x', 'path': '.env'}, 'INVALID_ARGUMENT'),
                        ('completed_source', {}, 'UNKNOWN_TOOL'),
                    ]
                    for name, inputs, expected_error in cases:
                        response = await session.call_tool(name, inputs)
                        result = response.model_dump(mode='json')
                        trace(name, inputs, result, 'mcp_stdio')
                        data = response.structuredContent
                        self.assertIsNotNone(data)
                        self.assertEqual(json.loads(response.content[0].text), data)
                        self.assertEqual(response.isError, expected_error is not None)
                        if expected_error:
                            self.assertEqual(data['error']['code'], expected_error)
                        else:
                            self.assertTrue(data['ok'])
                            if 'frames' in data['data']:
                                for frame in data['data']['frames']:
                                    self.assertEqual(body_digest(frame['code']), frame['body_sha256'])
                            else:
                                self.assertEqual(body_digest(data['data']['code']), data['data']['body_sha256'])
        asyncio.run(asyncio.wait_for(run(), timeout=60))

    def test_mcp_ambiguous_error_is_structured_and_flagged(self):
        import server
        fixture = ToolTests().fixture_bridge()

        async def run():
            with patch.object(server, 'retrieval', fixture):
                result = await server.call_tool('lookup_function_source', {'dataset_id': 'codeql_linux', 'name': 'duplicate'})
                trace('lookup_function_source', {'dataset_id': 'codeql_linux', 'name': 'duplicate'},
                      result.model_dump(mode='json'), 'mcp_handler', 'synthetic conflicting definitions')
                self.assertTrue(result.isError)
                self.assertEqual(result.structuredContent['error']['code'], 'FUNCTION_AMBIGUOUS')
        asyncio.run(run())


class RecordingResult(unittest.TextTestResult):
    def startTest(self, test):
        self.started = time.perf_counter()
        super().startTest(test)

    def addSuccess(self, test):
        super().addSuccess(test)
        CASES.append({'test': test.id(), 'passed': True, 'seconds': time.perf_counter()-self.started})

    def addFailure(self, test, error):
        super().addFailure(test, error)
        CASES.append({'test': test.id(), 'passed': False, 'error': self._exc_info_to_string(error, test)})

    def addError(self, test, error):
        super().addError(test, error)
        CASES.append({'test': test.id(), 'passed': False, 'error': self._exc_info_to_string(error, test)})


CASES = []


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir', type=Path)
    args = parser.parse_args()
    output = args.output_dir or HERE / 'results' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    output = output.resolve()
    if HERE not in output.parents:
        raise SystemExit('Test artifacts must stay inside harness_bridge.')
    output.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    result = unittest.TextTestRunner(verbosity=2, resultclass=RecordingResult).run(
        unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    baseline = json.loads((HERE / 'baseline_state.json').read_text('utf-8'))
    changed = [rel for rel, sha in baseline['protected_sha256'].items()
               if not (ROOT/rel).is_file() or hashlib.sha256((ROOT/rel).read_bytes()).hexdigest() != sha]
    summary = {'completed_at': datetime.now(timezone.utc).astimezone().isoformat(),
               'passed': result.wasSuccessful() and not changed, 'test_count': result.testsRun,
               'failure_count': len(result.failures), 'error_count': len(result.errors),
               'skip_count': len(result.skipped), 'seconds': time.perf_counter()-started, 'cases': CASES,
               'subtests': 'parameter/error cases also recorded individually in tool_calls.json',
               'protected_file_count': len(baseline['protected_sha256']), 'changed_protected_files': changed,
               'mcp_version': importlib.metadata.version('mcp'), 'python': sys.version,
               'new_model_calls': 0, 'new_api_cost_cny': 0, 'harness_launched_by_tests': False}
    for name, data in [('test_results.json', summary), ('tool_calls.json', TRACES)]:
        (output/name).write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', 'utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k!='cases'}, ensure_ascii=False))
    raise SystemExit(0 if summary['passed'] else 1)
