"""One real target-frame experiment; no generated code or solver is executed.

The author function bodies, original Prompt and E03 callbacks are unchanged.
All local adaptation is observation, limits, persistence routing and a stop hook.
"""
from datetime import datetime, timedelta, timezone
import ast
import contextlib
import copy
import hashlib
import importlib.abc
import importlib.metadata
import io
import json
from pathlib import Path
import platform
import re
import runpy
import subprocess
import sys
import time
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from completion import engine as engine_module
from completion import model as model_module
from completion.constraint_bundle import ConstraintTransferRejected
from completion.context import ContextRepository, called_function, parameter_name, direct_dereference

SAMPLE_ID = 'NPD/codeql/kernel69:row=23:index=42'
POSITION = 23
FRAME_LEVEL = 0
DATASET = 'benchmark/NPD/codeql/codeql_kernel69_nullpointer.json'
MAX_HTTP_REQUESTS = 9  # eight generation calls plus GET /models
MAX_GENERATION_REQUESTS = 8
MAX_INCREMENT_CNY = 0.5
STAGES = {
    'get_z3_by_target_conditions': 'U02',
    'analysis_constraints_prompt_context_multi': 'U04',
    'bug_line_constraints_prompt_step1': 'U05',
    'bug_line_constraints_prompt_step2': 'U06',
    'get_z3_extract': 'U10',
}


def stamp():
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


def sha(data):
    if isinstance(data, str):
        data = data.encode('utf-8')
    return hashlib.sha256(data).hexdigest()


def put(path, data):
    """Every experiment artifact is new; never overwrite an existing result."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write('\n')


def put_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as handle:
        handle.write(text)


class ExperimentStop(BaseException):
    """Deliberately outside the author's `except Exception` repair handlers."""
    def __init__(self, reason, **details):
        self.reason, self.details = reason, details
        super().__init__(reason)


def make_stop_hook(engine, emit):
    def after_u10(bundle, final, attempt=1):
        emit('postcondition_started', attempt=attempt)
        try:
            audit = engine.validate_transfer_output(bundle, final, attempt=attempt)
        except ConstraintTransferRejected as exc:
            emit('postcondition_finished', status=exc.audit['contract_status'], accepted=False,
                 rejection_reasons=exc.audit['rejection_reasons'])
            raise ExperimentStop('postcondition_rejected', status=exc.audit['contract_status']) from None
        emit('postcondition_finished', status=audit['contract_status'], accepted=True)
        raise ExperimentStop('completed_before_solver', status=audit['contract_status'])
    return after_u10


class NoSolverImports(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'z3' or fullname.startswith('z3.') or fullname.endswith('solver_worker'):
            raise ExperimentStop('forbidden_solver_import', module=fullname)
        return None


class ObservedPrompt:
    """Delegate original calls unchanged; record method identity, never edit text."""
    def __init__(self, original, state, emit):
        self.original, self.state, self.emit = original, state, emit

    def __getattr__(self, name):
        if name not in STAGES:
            raise ExperimentStop('out_of_scope_prompt', method=name)
        method = getattr(self.original, name)

        def invoke(*args, **kwargs):
            result = method(*args, **kwargs)
            self.state['stage'] = STAGES[name]
            self.emit('prompt_constructed', stage=STAGES[name], method=name,
                      prompt_sha256=sha(result))
            return result
        return invoke


def execute():
    if (HERE/'live_start.json').exists():
        raise RuntimeError('STOP: this E04 run has already started; no retry/overwrite')
    baseline = json.loads((HERE/'baseline_state.json').read_text(encoding='utf-8'))
    ledger_path = ROOT/'results/raw/completed/budget_ledger.json'
    ledger_before = json.loads((HERE/'budget_ledger.before.json').read_text(encoding='utf-8'))
    assert ledger_before == json.loads(ledger_path.read_text(encoding='utf-8'))
    # No model instance or network operation before this immutable-file check.
    for rel, expected in baseline['original_sha256'].items():
        assert sha((ROOT/rel).read_bytes()) == expected, 'STOP: protected file differs: '+rel
    config_path = ROOT/'configs/completed_experiment.json'
    config = json.loads(config_path.read_text(encoding='utf-8'))
    assert config == json.loads((HERE/'source_config.snapshot.json').read_text(encoding='utf-8'))
    assert config['model'] == 'deepseek-flash' and config['base_url'] == 'https://api.deepseek.com/'
    assert ledger_before['cost_upper_bound_cny'] < config['budget_cny']
    test = json.loads((HERE/'offline_tests.json').read_text(encoding='utf-8'))
    assert test['passed'] == test['total'] and test['model_calls'] == test['z3_runs'] == 0
    frozen = json.loads((HERE/'candidate_freeze.json').read_text(encoding='utf-8'))
    for rel, expected in frozen['sha256'].items():
        assert sha((ROOT/rel).read_bytes()) == expected, rel

    start = time.perf_counter()
    trace, state = [], {'stage': 'PREPARE'}
    counters = {'http_attempts': 0, 'generation_requests': 0, 'solver_boundary_attempts': 0}
    outcome = {'reason': 'not_started'}
    raw_model = None
    original_save = model_module.save
    console = io.StringIO()

    def sanitize(value):
        text = json.dumps(value, ensure_ascii=False)
        return json.loads(raw_model.redact(text)) if raw_model else value

    def emit(kind, **details):
        event = sanitize(dict(sequence=len(trace)+1, timestamp=stamp(), kind=kind, **details))
        trace.append(event)
        put(HERE/'events'/f'{len(trace):03d}.json', event)

    def forbid_solver(*args, **kwargs):
        counters['solver_boundary_attempts'] += 1
        emit('forbidden_solver_boundary')
        raise ExperimentStop('forbidden_solver_boundary')

    def forbid_subprocess(*args, **kwargs):
        emit('forbidden_subprocess')
        raise ExperimentStop('forbidden_subprocess')

    obj = None
    try:
        repository = ContextRepository(dataset=DATASET)
        row = repository.data[POSITION]
        assert row['index'] == 42
        context = repository.prepare(POSITION)
        frame = context['frames'][FRAME_LEVEL]
        assert frame['level'] == FRAME_LEVEL and frame['function'] == '__ip6_append_data'
        assert frame['body_sha256'] == '4f652c2800b05d4fab8cf926af60a66c348cbdd8e5cc95f2620555feaf1e20a9'
        for call_id in (10, 11, 12, 13):
            historical = ROOT/f'results/raw/completed/calls/{call_id:04d}.json'
            call = json.loads(historical.read_text(encoding='utf-8'))
            assert call['sample_id'] == SAMPLE_ID and call['call_id'] == call_id
        # Historical response text is never supplied to any prompt or callback.
        historical_bytes = subprocess.check_output(['git', 'show', repository.historical_ref
            + ':baseline/NPD-codeql-linux.json'], cwd=ROOT/'upstream') if hasattr(repository, 'historical_ref') else subprocess.check_output([
            'git', 'show', context['historical_ref']+':baseline/NPD-codeql-linux.json'], cwd=ROOT/'upstream')
        put(HERE/'sample_manifest.json', {
            'dataset': DATASET, 'dataset_sha256': sha((ROOT/'upstream'/DATASET).read_bytes()),
            'dataset_id': 'codeql_linux', 'position': POSITION, 'sample_id': SAMPLE_ID,
            'row_index': row['index'], 'historical_target_frame': FRAME_LEVEL,
            'experiment_scope': 'isolated target frame; no previous frame solving or P propagation',
            'context_origin': context['origin'], 'historical_ref': context['historical_ref'],
            'historical_blob': 'baseline/NPD-codeql-linux.json', 'historical_blob_sha256': sha(historical_bytes),
            'frames': context['frames'], 'target_frame': frame,
            'target_body_line_1based': frame['code'][:frame['code'].index(frame['target'])].count('\n')+1,
            'label_used_for_prompt_or_constraints': False,
            'historical_calls_used_for_identity_only': [10, 11, 12, 13]})

        obj = object.__new__(engine_module.CompletedEngine)  # avoid E03 default snapshot writes
        obj.repository = repository
        obj.extractor = engine_module.load_extractor()
        prompt_path = ROOT/'upstream/llm4pfa/prompt_templates.py'
        original_prompt = runpy.run_path(str(prompt_path), run_name='__e04_original_prompt__')['Prompt']()
        obj.prompt = ObservedPrompt(original_prompt, state, emit)
        obj.source = engine_module.completed_source(patch_dir=HERE/'rendered_pipeline')
        obj.frames, obj.level = context['frames'], FRAME_LEVEL
        obj.context, obj.sample_dir = context, HERE/'constraint_transfer'
        obj.sample_dir.mkdir(exist_ok=False)
        obj.solver_events, obj.transfer_events = [], []
        obj.transfer_position = POSITION
        extracted = json.loads(obj.extractor['extract_conditions'](frame['var_name'], None, frame['target'], frame['code']))
        assert extracted['bug_line_constraints'][0]['text'] == frame['target']
        put(HERE/'extracted_conditions.json', extracted)
        assert not any(n == 'z3' or n.startswith('z3.') for n in sys.modules)
        put(HERE/'experiment_config.json', {
            'experiment': 'E04_nonempty_delta_validation', 'created_at': stamp(),
            'source_config': 'configs/completed_experiment.json', 'source_config_sha256': sha(config_path.read_bytes()),
            'original_model_config': config, 'python': sys.version, 'executable': sys.executable,
            'platform': platform.platform(), 'dependencies': {n: importlib.metadata.version(n) for n in ('requests','python-dotenv','lizard','libclang')},
            'max_http_requests_including_service_check': MAX_HTTP_REQUESTS,
            'max_generation_requests': MAX_GENERATION_REQUESTS, 'max_new_cost_upper_cny': MAX_INCREMENT_CNY,
            'cumulative_ledger': str(ledger_path.relative_to(ROOT)),
            'cumulative_cost_upper_before_cny': ledger_before['cost_upper_bound_cny'],
            'cumulative_call_entries_before': len(ledger_before['calls']),
            'target_frame_isolated': True, 'nonempty_delta_acceptance': 'post-run read-only source review; no injected assertions', 'safety_decisions_enabled': False,
            'solver_enabled': False, 'repair_enabled': False,
            'persistence_adaptation': 'unchanged model.save behavior for cumulative ledger; new calls/service evidence redirected exclusively into E04'})

        raw_model = model_module.DeepSeekModel(config)
        assert raw_model._key  # presence only; never log credential
        raw_model.begin_sample(SAMPLE_ID)
        obj.model = raw_model
        last_saved_ledger = copy.deepcopy(ledger_before)

        def route_save(path, data):
            nonlocal last_saved_ledger
            path = Path(path)
            if path == ledger_path:
                disk = json.loads(path.read_text(encoding='utf-8'))
                if disk != last_saved_ledger:
                    raise ExperimentStop('concurrent_ledger_change')
                assert data['calls'][:len(ledger_before['calls'])] == ledger_before['calls']
                assert data['budget_cny'] == ledger_before['budget_cny']
                assert -1e-8 <= data['cost_upper_bound_cny']-ledger_before['cost_upper_bound_cny'] <= MAX_INCREMENT_CNY+1e-8
                original_save(path, data)
                last_saved_ledger = copy.deepcopy(data)
            elif path.parent == model_module.RAW/'calls':
                put(HERE/'model_calls'/path.name, sanitize(dict(data, e04_stage=state['stage'])))
            elif path == model_module.RAW/'service_check.json':
                put(HERE/'service_check.json', sanitize(data))
            else:
                raise ExperimentStop('unexpected_model_persistence_path')

        class BoundedClient:
            def __getattr__(self, name):
                return getattr(raw_model, name)

            def get_response_with_messages(self, model_name, messages):
                stage = state['stage']
                if stage not in STAGES.values():
                    raise ExperimentStop('unexpected_model_stage', stage=stage)
                if raw_model.sample_calls >= MAX_GENERATION_REQUESTS:
                    raise ExperimentStop('generation_request_cap')
                input_bound = len(json.dumps(messages, ensure_ascii=False).encode('utf-8'))+256*len(messages)+512
                reserve = (input_bound*config['input_cny_per_million_upper']+config['max_output_tokens']*config['output_cny_per_million_upper'])/1_000_000
                if raw_model.ledger['cost_upper_bound_cny']-ledger_before['cost_upper_bound_cny']+reserve > MAX_INCREMENT_CNY:
                    raise ExperimentStop('incremental_budget_guard')
                if raw_model.ledger['cost_upper_bound_cny']+reserve > config['budget_cny']:
                    raise ExperimentStop('cumulative_budget_guard')
                if stage in {'U02','U06','U10'} and any(x['kind']=='model_response' and x['stage']==stage for x in trace):
                    raise ExperimentStop('duplicate_main_stage_call', stage=stage)
                emit('model_request', stage=stage, next_ledger_call_id=len(raw_model.ledger['calls'])+1,
                     messages_sha256=sha(json.dumps(messages, ensure_ascii=False)), reserve_upper_cny=reserve)
                response = raw_model.get_response_with_messages(model_name, messages)
                emit('model_response', stage=stage, call_id=raw_model.ledger['calls'][-1]['call_id'],
                     raw_response_sha256=sha(response))
                return response

        obj.model = BoundedClient()
        send_original = model_module.requests.sessions.Session.send

        def observed_send(session, request, **kwargs):
            url = request.url
            allowed = {config['base_url'].rstrip('/')+'/models': 'GET',
                       config['base_url'].rstrip('/')+'/chat/completions': 'POST'}
            if url not in allowed or request.method != allowed[url]:
                raise ExperimentStop('unexpected_http_request')
            if counters['http_attempts'] >= MAX_HTTP_REQUESTS:
                raise ExperimentStop('http_request_cap')
            counters['http_attempts'] += 1
            if request.method == 'POST':
                counters['generation_requests'] += 1
            ordinal = counters['http_attempts']
            body = request.body or b''
            body = body.encode('utf-8') if isinstance(body, str) else body
            request_record = {'ordinal': ordinal, 'timestamp': stamp(), 'stage': state['stage'],
                'method': request.method, 'url': url, 'headers_saved': False,
                'actual_prepared_body_utf8': body.decode('utf-8'), 'actual_prepared_body_sha256': sha(body),
                'json_payload': json.loads(body) if body else None,
                'capture_point': 'requests.Session.send actual PreparedRequest, immediately before network transport'}
            put(HERE/'transport'/f'{ordinal:02d}_request.json', sanitize(request_record))
            emit('http_send', ordinal=ordinal, stage=state['stage'], method=request.method)
            try:
                response = send_original(session, request, **kwargs)
                try:
                    payload = response.json()
                except ValueError:
                    payload = {'non_json_text': raw_model.redact(response.text)}
                put(HERE/'transport'/f'{ordinal:02d}_response.json', sanitize({
                    'timestamp': stamp(), 'ordinal': ordinal, 'http_status': response.status_code,
                    'response_body_sha256': sha(response.content), 'payload': payload}))
                emit('http_response', ordinal=ordinal, status=response.status_code, stage=state['stage'])
                return response
            except BaseException as exc:
                emit('http_exception', ordinal=ordinal, error=raw_model.redact(type(exc).__name__+': '+str(exc)))
                raise

        namespace = {'json': json, 're': re, 'model_name': 'deepseek', 'model': obj.model,
            'prompt': obj.prompt, 'extract_util_plus': type('Extractor', (), {'extract_conditions': staticmethod(obj.extractor['extract_conditions'])}),
            'function_cache': {}, 'func_body_cache_path': str(HERE/'function_cache.json'),
            'solve_z3': forbid_solver, 'solve_base_query': forbid_solver,
            'extract_function_name': called_function, 'get_param_name': parameter_name,
            'is_direct_dereference': direct_dereference,
            'assemble_base_delta': obj.assemble_transfer,
            'validate_base_delta_output': make_stop_hook(obj, emit)}
        # Execute only fixed author/completion function definitions, never any
        # model output. The model-generated scripts remain inert string values.
        exec(compile(obj.source, '<E04_unchanged_E03_author_functions>', 'exec'), namespace)
        namespace['process_final_response'] = obj.code_response
        namespace['process_array_response'] = obj.array_response
        namespace['get_function_body_by_name'] = lambda name: repository.lookup(name, context['function_call'])
        namespace['get_next_frame'] = forbid_solver  # must be unreachable before stop
        put(HERE/'live_start.json', {'started_at': stamp(), 'sample_id': SAMPLE_ID,
                                    'target_frame': FRAME_LEVEL, 'core_sha256': frozen['sha256']})
        blocker = NoSolverImports()
        sys.meta_path.insert(0, blocker)
        try:
            with patch.object(model_module, 'save', route_save), \
                 patch.object(model_module.requests.sessions.Session, 'send', observed_send), \
                 patch.object(subprocess, 'Popen', forbid_subprocess), \
                 contextlib.redirect_stdout(console):
                state['stage'] = 'SERVICE_MODELS'
                emit('service_check_started', model=config['model'])
                raw_model.verify_service()
                emit('service_check_passed', model=config['model'])
                state['stage'] = 'PIPELINE'
                emit('target_frame_started', frame=FRAME_LEVEL, no_previous_solver_result_supplied=True)
                namespace['data_flow_analysis_pipeline'](
                    frame['var_name'], frame['target'], frame['code'], [], [], [],
                    0, 'official_context_snippet', {}, [], [], FRAME_LEVEL, POSITION, POSITION)
                raise ExperimentStop('pipeline_returned_before_u10_gate')
        finally:
            sys.meta_path.remove(blocker)
    except ExperimentStop as stop:
        outcome = {'reason': stop.reason, **stop.details}
        emit('experiment_stopped', **outcome)
    except BaseException as exc:
        outcome = {'reason': 'execution_error', 'error': (raw_model.redact(str(exc)) if raw_model else str(exc)), 'exception': type(exc).__name__}
        emit('experiment_stopped', **outcome)
    finally:
        stdout = console.getvalue()
        put_text(HERE/'pipeline_stdout.txt', raw_model.redact(stdout) if raw_model else stdout)
        put(HERE/'execution_trace.json', {'scope': 'real single isolated target frame', 'events': trace,
             'outcome': outcome, 'counters': counters, 'z3_runs': 0,
             'historical_generated_python_executions': 0, 'safety_decisions': 0,
             'z3_imported': any(n=='z3' or n.startswith('z3.') for n in sys.modules),
             'duration_seconds': time.perf_counter()-start})
        after = json.loads(ledger_path.read_text(encoding='utf-8'))
        put(HERE/'budget_ledger.after.json', after)
        print(json.dumps({'outcome': outcome, 'HTTP_requests': counters['http_attempts'],
              'generation_requests': counters['generation_requests'],
              'new_ledger_entries': len(after['calls'])-len(ledger_before['calls']),
              'new_cost_upper_cny': after['cost_upper_bound_cny']-ledger_before['cost_upper_bound_cny'],
              'solver_boundary_attempts': counters['solver_boundary_attempts'], 'Z3_runs': 0}, ensure_ascii=False))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    execute()
