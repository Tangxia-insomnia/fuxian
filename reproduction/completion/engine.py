"""Load author function bodies with explicit, persisted completion patches."""
import __future__
import ast
import difflib
import json
import os
from pathlib import Path
import re
import runpy
import subprocess
import sys

from .context import ROOT, ContextUnavailable, called_function, parameter_name, direct_dereference
from .model import save


def load_extractor():
    path = ROOT / 'upstream/llm4pfa/extract_util_plus.py'
    tree = ast.parse(path.read_text(encoding='utf-8'))
    tree.body = [n for n in tree.body if not isinstance(n, ast.ImportFrom) or n.module != 'LLM4Detection.m_agent.conditions_info']
    ns = {'__name__': '__completed_extractor__', '__file__': str(path)}
    exec(compile(tree, str(path), 'exec', flags=__future__.annotations.compiler_flag), ns)
    return ns


def completed_source():
    original = (ROOT / 'upstream/llm4pfa/feasibility_analysis_pipeline.py').read_text(encoding='utf-8')
    source = original[original.index('def get_context_function_body_with_tool'):original.index('def detect_pipeline():')]
    old = '''    for item_constraint in target_conditions:
        if "goto" in item_constraint["condition"] or "return" in item_constraint["condition"]:
            target_conditions.remove(item_constraint)
            goto_label = item_constraint'''
    new = '''    # Completion fix: do not remove items while iterating; label is text.
    for item_constraint in list(target_conditions):
        if "goto" in item_constraint["condition"] or "return" in item_constraint["condition"]:
            target_conditions.remove(item_constraint)
            goto_label = item_constraint["condition"].removeprefix("goto ").strip()'''
    assert old in source
    source = source.replace(old, new)
    source = source.replace('target_conditions = [item for item in target_conditions if "while" not in item]', 'target_conditions = [item for item in target_conditions if "while" not in item["condition"]]')
    source = re.sub(r'exec\(final_response, globals\(\)\)\n(?:\s*#.*\n)*\s*result = check_constraints\(\)', 'result = solve_z3(final_response)', source)
    assert 'exec(final_response' not in source
    source = source.replace('''                messages.append({"role": "assistant", "content": final_response})''', '''                if cnt >= 4:
                    raise RuntimeError("Z3 repair attempts exhausted: " + str(e)) from e
                messages.append({"role": "assistant", "content": final_response})''')
    begin = source.index('    # get next function information in the call trace')
    end = source.index('    # get new sink point in the next function', begin)
    source = source[:begin] + '''    # Completion fix: even an unconstrained path must execute its base SMT query.
    if target_conditions == [] and early_jump_constraints_list == []:
        solve_base_query(response_message_target)

    # Explicit recovered chain end; missing context is never silently feasible.
    next_info = get_next_frame(original_index, level)
    if next_info is None:
        return {"response": response_list, "function_name_list": function_name_list,
                "function_body_list": function_body_list, "result": True}
    new_function_name, new_function_body = next_info
    function_body_list.append(new_function_body)
    function_name_list.append(new_function_name)

''' + source[end:]
    # Original catches dereference resolution errors as a string. The runner keeps
    # such results as failures, and never casts non-booleans into predictions.
    source = source.replace('args = extract_function_arguments(new_function_name)', 'args = extract_function_arguments(loc_text)')
    source = source.replace('if item in con1:', 'if item in con1["condition"]:')
    save(ROOT / 'patches/completed_pipeline_changes.json', {'base_commit': '4efb4b9bf7e845e180451b43ba29a25e3edaa0e3', 'upstream_modified': False, 'loaded_range': 'author helper functions and data_flow_analysis_pipeline; original imports/config/batch entry replaced by adapter runner', 'changes': ['remove goto/return conditions without mutating iterator; pass goto label text', 'filter while in condition text instead of dict keys', 'replace exec in global namespace with bounded Z3 worker; record actual SMT queries', 'stop after solver repair exhaustion', 'execute base query when neither target nor jump constraints remain', 'use explicitly recovered chain end; never swallow missing context as True', 'extract call arguments from call text rather than bare function name', 'inspect propagated constraint text rather than dict keys', 'strict JSON/code response parsing and actual function/context helpers supplied by adapter'], 'method_changes': 'Prompts and main iterative analysis retained; error handling, data plumbing and base-solver omission repaired. This is a modified completion, not the authors exact executable.'})
    (ROOT / 'patches/completed_pipeline.diff').write_text(''.join(difflib.unified_diff(original.splitlines(True), source.splitlines(True), fromfile='upstream/llm4pfa/feasibility_analysis_pipeline.py', tofile='completed_function_bodies.py')), encoding='utf-8')
    (ROOT / 'patches/completed_function_bodies.py').write_text(source, encoding='utf-8')
    return source


class CompletedEngine:
    def __init__(self, repository, model):
        self.repository, self.model = repository, model
        self.extractor = load_extractor()
        self.prompt = runpy.run_path(str(ROOT / 'upstream/llm4pfa/prompt_templates.py'), run_name='__completed_prompts__')['Prompt']()
        self.source = completed_source()
        self.frames = []
        self.solver_events = []
        self.level = 0
        self.sample_dir = None

    def prepare(self, position):
        context = self.repository.prepare(position)
        for frame in context['frames']:
            extracted = json.loads(self.extractor['extract_conditions'](frame['var_name'], None, frame['target'], frame['code']))
            if not extracted.get('bug_line_constraints'):
                raise ContextUnavailable('Author extractor cannot locate target')
            frame['extracted'] = extracted
            # Catch unavailable targeted contexts before spending on the sample.
            for cond in extracted['target_conditions']:
                if any(x in cond['condition'] for x in ['goto', 'return', 'while']):
                    continue
                name = called_function(frame['var_name'], cond['condition'])
                if name:
                    self.repository.lookup(name, context['function_call'])
        return context

    def code_response(self, response, content=''):
        match = re.search(r'```(?:python)?\s*\n?(.*?)```', response, re.S)
        return (match[1] if match else response).replace('from z3 import *', '').strip()

    def array_response(self, response):
        match = re.search(r'```(?:json)?\s*(.*?)```', response, re.S)
        value = json.loads(match[1] if match else response)
        if not isinstance(value, list) or any(not isinstance(x, str) for x in value):
            raise ValueError('Expected JSON array of condition strings')
        return value

    def solve(self, source):
        event_id = len(self.solver_events)+1
        event = {'event_id': event_id, 'level': self.level, 'source': source}
        path = self.sample_dir / f'solver_{event_id:02d}.json'
        try:
            # The secret is held only by the parent client, not placed in env.
            child_env = {k: v for k, v in os.environ.items() if not any(x in k.upper() for x in ['KEY', 'TOKEN', 'SECRET', 'PASSWORD'])}
            run = subprocess.run([sys.executable, '-I', '-B', str(ROOT / 'completion/solver_worker.py')], input=json.dumps({'source': source}), capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=15, env=child_env)
            if run.returncode:
                raise ValueError('Z3 worker exited ' + str(run.returncode))
            result = json.loads(run.stdout)
            event.update(result)
            if not result['ok']:
                raise ValueError(result['error'])
            return result['feasible']
        except Exception as exc:
            event.update({'ok': False, 'error': f'{type(exc).__name__}: {exc}'})
            raise
        finally:
            self.solver_events.append(event)
            save(path, event)

    def solve_base(self, base_source):
        messages = [{'role': 'user', 'content': self.prompt.get_z3_extract(self.code_response(base_source))}]
        for attempt in range(4):
            response = self.model.get_response_with_messages('deepseek', messages)
            try:
                answer = self.solve(self.code_response(response))
                if not answer:
                    # A base-only UNSAT cannot be returned as a feasible path.
                    raise BaseInfeasible()
                return True
            except BaseInfeasible:
                raise
            except Exception as exc:
                if attempt == 3:
                    raise
                messages += [{'role': 'assistant', 'content': response}, {'role': 'user', 'content': self.prompt.re_generate_prompt(str(exc))}]

    def run(self, position, sample_dir, context=None):
        self.context = context or self.prepare(position)
        self.frames = self.context['frames']
        self.solver_events = []
        self.sample_dir = sample_dir
        self.sample_dir.mkdir(parents=True, exist_ok=True)
        save(sample_dir / 'context.json', self.context)
        ns = {'json': json, 're': re, 'model_name': 'deepseek', 'model': self.model, 'prompt': self.prompt, 'extract_util_plus': type('Extractor', (), {'extract_conditions': staticmethod(self.extractor['extract_conditions'])}), 'function_cache': {}, 'func_body_cache_path': str(sample_dir / 'function_cache.json'), 'solve_z3': self.solve, 'solve_base_query': self.solve_base, 'extract_function_name': called_function, 'get_param_name': parameter_name, 'is_direct_dereference': direct_dereference}
        exec(compile(self.source, '<completed_author_pipeline>', 'exec'), ns)
        ns['process_final_response'] = self.code_response
        ns['process_array_response'] = self.array_response
        ns['get_function_body_by_name'] = lambda name: self.repository.lookup(name, self.context['function_call'])
        ns['get_next_frame'] = lambda original_index, level: (self.frames[level+1]['function'], self.frames[level+1]['code']) if level+1 < len(self.frames) else None

        def dereferenced_location(cache, function, var):
            frame = self.frames[self.level+1]
            if frame['function'] != function or frame['var_name'] != var:
                raise ContextUnavailable('Recovered next sink does not match callee/parameter')
            return frame['target'], frame['code'][:frame['code'].index(frame['target'].strip())].count('\n')+1, 'official_context_snippet'

        ns['get_dereferenced_locations_plus'] = dereferenced_location
        original_pipeline = ns['data_flow_analysis_pipeline']

        def wrapped(*args):
            self.level = args[11]
            if self.level >= len(self.frames):
                raise ContextUnavailable('Analysis exceeded verified context chain')
            try:
                return original_pipeline(*args)
            except BaseInfeasible:
                return {'result': False, 'response': args[3], 'reason': 'completed_base_solver_unsat'}

        ns['data_flow_analysis_pipeline'] = wrapped
        first = self.frames[0]
        return wrapped(first['var_name'], first['target'], first['code'], [], [], [], 0, 'official_context_snippet', {}, [], [], 0, position, position)


class BaseInfeasible(Exception):
    pass
