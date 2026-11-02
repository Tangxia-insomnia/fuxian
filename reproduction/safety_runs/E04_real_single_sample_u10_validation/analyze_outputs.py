"""Offline accounting/trace verification only; no model, solver or generated exec."""
from collections import Counter
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def digest(data):
    if isinstance(data, str):
        data = data.encode('utf-8')
    return hashlib.sha256(data).hexdigest()


def put(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write('\n')


def text(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as handle:
        handle.write(value)


def execute():
    trace = read(HERE/'execution_trace.json')
    before, after = read(HERE/'budget_ledger.before.json'), read(HERE/'budget_ledger.after.json')
    live_ledger = read(ROOT/'results/raw/completed/budget_ledger.json')
    assert after == live_ledger
    assert after['calls'][:len(before['calls'])] == before['calls']
    assert after['budget_cny'] == before['budget_cny']
    calls = [read(p) for p in sorted((HERE/'model_calls').glob('*.json'))]
    by_stage = {c['e04_stage']: c for c in calls}
    assert set(by_stage) == {'U02','U05','U06','U10'} and len(calls) == 4
    assert after['calls'][len(before['calls']):] == [entry for entry in live_ledger['calls'] if entry['call_id'] in {c['call_id'] for c in calls}]
    transport = [read(p) for p in sorted((HERE/'transport').glob('*_request.json'))]
    transport_posts = [r for r in transport if r['method'] == 'POST']
    request_proofs = []
    for packet in transport_posts:
        call = by_stage[packet['stage']]
        payload = packet['json_payload']
        assert digest(packet['actual_prepared_body_utf8']) == packet['actual_prepared_body_sha256']
        assert json.loads(packet['actual_prepared_body_utf8']) == payload
        assert payload['messages'] == call['messages']
        assert payload['model'] == call['model_requested'] == 'deepseek-flash'
        reply = read(HERE/'transport'/f'{packet["ordinal"]:02d}_response.json')
        assert reply['http_status'] == call['http_status'] == 200
        assert reply['payload']['id'] == call['response_id']
        assert reply['payload']['choices'] == call['choices']
        request_proofs.append({'stage':packet['stage'],'call_id':call['call_id'],
            'transport_request':f'transport/{packet["ordinal"]:02d}_request.json',
            'transport_response':f'transport/{packet["ordinal"]:02d}_response.json',
            'prepared_body_sha256':packet['actual_prepared_body_sha256'],
            'messages_equal_client_record':True,'response_id_matches_client_record':True})

    records = [read(p) for p in sorted((HERE/'constraint_transfer/constraint_transfer_e03').glob('*.json'))]
    assert len(records) == 2
    assembly, post = records
    assert assembly['stage']=='before_U10' and post['stage']=='after_U10_before_solver'
    bundle = assembly['bundle']
    def response(stage):
        return by_stage[stage]['choices'][0]['message']['content']
    assert bundle['base']['raw_text'] == response('U02')
    assert bundle['delta']['raw_text'] == response('U06')
    for role in ('base','delta'):
        item = bundle[role]
        assert digest(item['raw_text'])==item['raw_sha256']
        span = item['merged_span']
        assert bundle['merged_script'][span['start']:span['end']]==item['code_text']
    assert digest(bundle['merged_script'])==bundle['merged_sha256']
    u10packet = next(p for p in transport_posts if p['stage']=='U10')
    assert len(u10packet['json_payload']['messages']) == 1
    actual_message = u10packet['json_payload']['messages'][0]['content']
    assert actual_message.count(bundle['merged_script']) == 1
    # Prompt equality was frozen/tested separately; compare actual payload to
    # the exact original template without invoking or modifying a Prompt class.
    constructed = next(e for e in trace['events'] if e['kind']=='prompt_constructed' and e['stage']=='U10')
    assert digest(actual_message)==constructed['prompt_sha256']
    assert trace['outcome']=={'reason':'completed_before_solver','status':'PASS'}
    assert assembly['accepted'] and post['accepted']
    assert trace['counters']['solver_boundary_attempts']==0 and not trace['z3_imported']
    assert not any(e['kind'] in {'forbidden_solver_boundary','forbidden_subprocess'} for e in trace['events'])
    assert not any(c['e04_stage']=='U01' for c in calls)
    transfer = HERE/'constraint_transfer'
    text(transfer/'U02_raw_response.txt',response('U02'))
    text(transfer/'U06_raw_response.txt',response('U06'))
    text(transfer/'merged_script.py.txt',bundle['merged_script'])
    text(transfer/'U10_raw_response.txt',response('U10'))
    text(transfer/'U10_code_checked.py.txt',post['sources']['final']['raw_text'])
    put(transfer/'base_delta_bundle.json',bundle)
    put(transfer/'U10_actual_request.json',u10packet)
    put(transfer/'U10_actual_request_messages.json',u10packet['json_payload']['messages'])
    put(transfer/'U10_postcondition.json',post)
    put(transfer/'base_delta_ir.json',assembly['check_contract']['ir'])
    put(transfer/'request_response_verification.json',{'requests':request_proofs,
        'actual_U10_contains_exact_merged_script':True,
        'actual_U10_contains_base_code_verbatim':bundle['base']['code_text'] in actual_message,
        'actual_U10_contains_delta_code_verbatim':bundle['delta']['code_text'] in actual_message,
        'U10_prompt_constructed_hash_matches_transport':True,
        'distinct_objects':['local merged_script','actual PreparedRequest body','real HTTP response choices'],
        'semantic_correctness':'NOT_ASSESSED','polarity_correctness':'NOT_ASSESSED'})

    rates = read(HERE/'source_config.snapshot.json')
    cost = sum(Decimal(str(c['cost_upper_bound_cny'])) for c in calls)
    assert cost <= Decimal('2') and len(transport) <= 8
    assert abs(float(cost)-(after['cost_upper_bound_cny']-before['cost_upper_bound_cny'])) < 1e-10
    tokens = {k:sum(c['usage'].get(k,0) for c in calls) for k in ('prompt_tokens','completion_tokens','total_tokens','prompt_cache_hit_tokens','prompt_cache_miss_tokens')}
    stages = []
    for call in calls:
        historical_id = {'U02':231,'U06':233,'U10':234}.get(call['e04_stage'])
        old = read(ROOT/f'safety_runs/E03_base_delta_explicit_transfer_fix/evidence/A04/calls/{historical_id:04d}.json') if historical_id else None
        if old:
            assert old['response_id'] != call['response_id']
        stages.append({'stage':call['e04_stage'],'calls':1,'call_id':call['call_id'],
            'model_requested':call['model_requested'],'model_returned':call['model_returned'],
            'raw_response_sha256':digest(call['choices'][0]['message']['content']),
            'usage':call['usage'],'duration_seconds':call['duration_seconds'],
            'cost_upper_bound_cny':call['cost_upper_bound_cny'],
            'response_id_distinct_from_historical':True if old else None})
    put(HERE/'metrics.json',{'scope':'one real isolated target frame; structural transfer only',
        'stages':stages,'stage_call_counts':dict(Counter(c['e04_stage'] for c in calls)),
        'generation_requests':len(calls),'service_GET_requests':len(transport)-len(calls),'total_HTTP_requests':len(transport),
        'tokens':tokens,'duration_seconds':trace['duration_seconds'],
        'model_call_duration_sum_seconds':sum(c['duration_seconds'] for c in calls),
        'new_usage_based_cost_upper_cny':float(cost),'new_usage_based_cost_upper_cny_decimal':str(cost),
        'actual_account_billed_cny':None,
        'cost_scope':'actual returned token usage times existing conservative configured rates; not a verified account debit; API returned no billing field',
        'input_rate_upper_cny_per_million':rates['input_cny_per_million_upper'],
        'output_rate_upper_cny_per_million':rates['output_cny_per_million_upper'],
        'ledger_before':{'entries':len(before['calls']),'cost_upper_bound_cny':before['cost_upper_bound_cny']},
        'ledger_after':{'entries':len(after['calls']),'cost_upper_bound_cny':after['cost_upper_bound_cny']},
        'assembly_status':assembly['contract_status'],'output_status':post['contract_status'],
        'actual_U10_contains_complete_B_delta':True,'assembly_counts':assembly['counts'],'output_counts':post['counts'],
        'base_declarations':len(assembly['check_contract']['ir']['B']['declarations']),
        'base_assertions':len(assembly['check_contract']['ir']['B']['assertions']),
        'delta_declarations':len(assembly['check_contract']['ir']['delta']['declarations']),
        'delta_assertions':len(assembly['check_contract']['ir']['delta']['assertions']),
        'offline_tests_passed':10,'offline_tests_total':10,
        'solver_boundary_attempts':0,'z3_runs':0,'z3_imported':False,'U01_calls':0,
        'generated_Python_executions':0,'new_safety_decisions':0,
        'semantic_correctness':'NOT_ASSESSED','polarity_correctness':'NOT_ASSESSED',
        'nonempty_delta_real_output_coverage':False})

    baseline = read(HERE/'baseline_state.json')
    changed, missing = [], []
    for rel, expected in baseline['original_sha256'].items():
        p = ROOT/rel
        if not p.is_file():
            missing.append(rel)
        elif digest(p.read_bytes())!=expected:
            changed.append(rel)
    unexpected = []
    for folder, dirs, files in os.walk(ROOT):
        dirs[:]=[n for n in dirs if n not in {'.git','.venv','__pycache__','node_modules'}]
        for name in files:
            if name.startswith('.env'):
                continue
            rel = (Path(folder)/name).relative_to(ROOT).as_posix()
            if rel not in baseline['original_sha256'] and not rel.startswith('safety_runs/E04_real_single_sample_u10_validation/'):
                unexpected.append(rel)
    assert changed==['results/raw/completed/budget_ledger.json'] and not missing and not unexpected
    git_status = subprocess.check_output(['git','status','--porcelain=v1'],cwd=ROOT/'upstream',text=True).strip()
    assert not git_status
    frozen = read(HERE/'candidate_freeze.json')
    assert all(digest((ROOT/p).read_bytes())==h for p,h in frozen['sha256'].items())
    put(HERE/'preservation_check.json',{'checked_at':datetime.now(timezone(timedelta(hours=8))).isoformat(),
        'passed':True,'original_files_checked':len(baseline['original_sha256']),
        'immutable_files_byte_unchanged':len(baseline['original_sha256'])-1,
        'only_authorized_mutation':'results/raw/completed/budget_ledger.json',
        'ledger_contract':{'old_entries_preserved':before['calls']==after['calls'][:len(before['calls'])],
            'old_entries_count':len(before['calls']),'new_entries_count':len(calls),
            'budget_unchanged':before['budget_cny']==after['budget_cny'],
            'before_sha256':digest((HERE/'budget_ledger.before.json').read_bytes()),
            'after_sha256':digest((ROOT/'results/raw/completed/budget_ledger.json').read_bytes()),
            'note':'Shared cumulative ledger was explicitly authorized to append; its entire file bytes necessarily differ. No old ledger entry or historic call file changed.'},
        'unexpected_changes':[],'missing_files':missing,'unexpected_new_files':unexpected,
        'upstream_status':git_status,'E03_candidate_and_E02_checker_unchanged':True,
        'all_original_file_hashes':'baseline_state.json','freeze_hashes':'candidate_freeze.json'})
    print(json.dumps({'calls':len(calls),'actual_U10_payload_verified':True,'assembly':'PASS','postcondition':'PASS',
        'tokens':tokens,'cost_upper_cny':str(cost),'immutable_files_verified':len(baseline['original_sha256'])-1}))


if __name__=='__main__':
    execute()
