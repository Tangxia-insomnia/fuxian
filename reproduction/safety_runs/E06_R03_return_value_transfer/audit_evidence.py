"""Inspect already saved evidence; no parsing/rerunning sources or fixed samples."""
import json
from adapter import ROOT, r01, counts


def audit():
    checks=[]
    def check(name,ok):
        checks.append({'check':name,'status':'PASS' if ok else 'REJECT'})
    synth=json.loads((ROOT/'synthetic_runs/final_candidate_02/synthetic_test_results.json').read_text('utf-8'))
    check('synthetic_expected_outcomes',synth['all_passed'] and synth['total']==synth['passed']==201 and synth['fixture_count']==66)
    check('all_synthetic_scenarios_accounted',sum(synth['scenario_status_counts'].values())==66)
    ids=[];entry_ids=[]
    for path in sorted((ROOT/'synthetic_runs/final_candidate_02').glob('*.json')):
        if path.name in {'synthetic_test_results.json','different_callers.json'}:continue
        report=json.loads(path.read_text('utf-8'))
        if 'call_contexts' not in report:continue
        inspect_report(report,check,ids,entry_ids)
    extra=json.loads((ROOT/'synthetic_runs/final_candidate_02/different_callers.json').read_text('utf-8'))
    for report in extra.values():inspect_report(report,check,ids,entry_ids)
    check('all_call_contexts_unique',len(ids)==len(set(ids)))
    check('all_callee_entries_unique',len(entry_ids)==len(set(entry_ids)))
    for name,n in [('r01_core_recheck/test_results.json',41),('r02_core_recheck/synthetic_test_results.json',110),('input_boundary_final/test_results.json',15)]:
        report=json.loads((ROOT/name).read_text('utf-8'))
        check(name,report['all_passed'] and report['total']==report['passed']==n and not report['external_operations'])
    hist=json.loads((ROOT/'historical_results.json').read_text('utf-8'))
    check('historical_all_four_unknown',len(hist['rows'])==4 and all(r['status']=='UNKNOWN' for r in hist['rows']))
    openssl=hist['rows'][0]
    candidates=openssl['edges'][0]['callsite_candidates'];rs=openssl['frames'][1]['return_source_candidates']
    check('OpenSSL_112_ignored',len(candidates)==1 and candidates[0]['source_range']['start']['line_1based']==112
          and candidates[0]['result_disposition_candidate']=='ignored' and candidates[0]['caller_result_version_id'] is None)
    check('OpenSSL_early_return_and_nested_unknown',len(rs)==2 and rs[0]['raw_return_expression']=='2'
          and rs[0]['return_source_range']['start']['line_1based']==9 and rs[1]['contains_call_candidate']
          and all(v['status']=='UNKNOWN' and v['source_value_version_id'] is None for v in rs))
    check('historical_no_false_caller_propagation',all(not e['caller_result_versions'] and not e['return_guard_propagation']
          and not e['callee_return_terminates_caller'] and not e['R05_path_composition_performed'] for r in hist['rows'] for e in r['edges']))
    check('external_operations_empty',not hist['metrics']['external_operations'] and not synth['external_operations'])
    return {'all_passed':all(c['status']=='PASS' for c in checks),'checks':checks,
            'status_counts':counts(c['status'] for c in checks),'call_contexts_examined':len(ids),
            'entry_versions_examined':len(entry_ids),'new_source_analyses':0,'new_fixed20_executions':0}


def inspect_report(report,check,ids,entry_ids):
    label=__import__('pathlib').Path(report['source']).stem
    contexts={c['call_context_id']:c for c in report['call_contexts']}
    ids.extend(contexts)
    for f in report['callees']:
        ctx=contexts[f['call_context_id']]
        check(label+'_lexical_instance_source_identity_'+f['call_context_id'][-8:],
              f['function']['usr']==ctx['callee_function_identity']['usr']
              and f['function']['location']==ctx['callee_function_identity']['location']
              and f['body_sha256']==ctx['callee_body_sha256'])
        versions={v['value_version_id']:v for v in f['versions']}
        for binding in ctx['callee_entry_bindings']:
            entry_ids.append(binding['callee_entry_version']);v=versions[binding['callee_entry_version']]
            check(label+'_entry_chain_'+v['value_version_id'][-8:],
                v['value']['caller_pre_value_version_id']==binding['caller_pre_version']
                and v['value']['argument_transfer_id']==binding['argument_transfer_id']
                and v['slot_id']==binding['callee_slot_id'] and v['slot_id']!=binding['caller_pre_slot_id'])
        for value in f['return_values']:
            if value['status']=='PASS' and value['source_slot_id']:
                vid=value['source_value_version_id']
                check(label+'_return_current_'+value['return_event_id'][-8:],vid in versions
                      and value['callee_current_versions'][value['source_slot_id']]==vid
                      and versions[vid]['slot_id']==value['source_slot_id'])
    for t in report['return_transfers']:
        tag=label+'_transfer_'+t['return_transfer_id'][-8:]
        if t['status']=='PASS':
            check(tag+'_fully_covered',t['call_effect_coverage']==t['return_path_completeness']=='PASS')
            pre=t['caller_pre_environment'];post=t['caller_post_environment'];result=t['caller_result_slot_id']
            check(tag+'_caller_unrelated_slots_unchanged',all(v==post['current'].get(s) for s,v in pre['current'].items() if s!=result))
            check(tag+'_no_guard_or_return_leak',pre['guards']==post['guards'] and not t['callee_return_terminates_caller'] and not t['guard_transferred_to_caller'])
            if t['return_value_received']:
                check(tag+'_receiver_exact_new_version',post['current'][result]==t['caller_result_version_id']
                      and t['caller_result_version_id'] not in pre['current'].values())
            else:check(tag+'_no_receiver',result is None and t['caller_result_version_id'] is None)
        else:check(tag+'_unknown_no_continuation',t['caller_post_path_id'] is None and t['caller_result_version_id'] is None)


if __name__=='__main__':
    from run_r03 import save
    result=audit();save(ROOT/'pre_freeze_evidence_check.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='checks'}))
    if not result['all_passed']:raise SystemExit(1)
