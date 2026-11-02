"""Source-driven checks, path/version invariants and adversarial claims."""
import argparse
import copy
import json
import time
import traceback
from adapter import ROOT, r01, offline_boundary, counts
from return_transfer import analyze, proposal_from, verify_proposal


def save(path, obj):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(obj, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def run(output):
    offline_boundary.install()
    output.mkdir(parents=True, exist_ok=False)
    tests, reports = [], {}
    started = time.perf_counter()
    def record(name, expected, actual, evidence):
        tests.append({'test': name, 'expected': expected, 'actual': actual,
                      'passed': expected == actual, 'evidence': evidence,
                      'mismatch_reason': None if expected == actual else 'observed_result_differs_from_stated_contract'})
    def invariant(name, ok, evidence):
        record(name, 'PASS', 'PASS' if ok else 'REJECT', evidence)
    try:
        cases = json.loads((ROOT/'synthetic_fixtures/cases.json').read_text('utf-8'))
        for case in cases:
            path = ROOT/'synthetic_fixtures'/case['source']
            assert r01.digest(path.read_bytes()) == case['source_sha256']
            report = analyze(path, dataset_id='synthetic-r03', position=0,
                build_status='synthetic-self-contained', caller=case['caller'],
                candidate_source_paths=[ROOT/'synthetic_fixtures'/p for p in case.get('candidate_source_paths',[])])
            reports[case['case']] = report
            save(output/(case['case']+'.json'), report)
            record(case['case'], case['expected_status'], report['status'], case)
        def callee(name, i=0): return reports[name]['callees'][i]
        def caller(name): return reports[name]['caller']
        def versions(fn, name): return [v for v in fn['versions'] if v['declaration_identity']['name'] == name]
        def transfers(name): return reports[name]['return_transfers']
        def return_values(name): return callee(name)['return_values']
        def reads(fn, name):
            slots = {s['slot_id'] for s in fn['slots'] if s['declaration']['name'] == name}
            return [r for r in fn['reads'] if r['slot_id'] in slots]

        # Independent end-to-end origin walk: caller a -> entry x -> copied y -> return -> caller b.
        r = reports['S02_local']; f = callee('S02_local'); t = transfers('S02_local')[0]
        x,y = versions(f,'x')[0], versions(f,'y')[0]
        a,b = versions(caller('S02_local'),'a')[0],versions(caller('S02_local'),'b')[0]
        invariant('S02_complete_origin_chain', y['source_value_version_id'] == x['value_version_id']
            and x['value']['caller_pre_value_version_id'] == a['value_version_id']
            and t['evidence_chain']['callee_return']['source_value_version_id'] == y['value_version_id']
            and b['value']['callee_return_value_id'] == t['callee_return_value_id']
            and len({a['slot_id'], x['slot_id'], b['slot_id']}) == 3, t)
        for name,var in [('S06_reassign_param','x'),('X_pointer_param','p')]:
            f = callee(name); xs = versions(f,var); a = versions(caller(name),'a')
            t = transfers(name)[0]
            invariant(name+'_by_value_isolation', len(xs)==2 and len(a)==1
                and return_values(name)[0]['source_value_version_id'] == xs[-1]['value_version_id']
                and t['caller_pre_environment']['current'][a[0]['slot_id']] == a[0]['value_version_id']
                and t['caller_post_environment']['current'][a[0]['slot_id']] == a[0]['value_version_id']
                and xs[-1]['slot_id'] != a[0]['slot_id'], {'callee': xs, 'caller': a, 'transfer': t})
        f = callee('X_pointer_copy');xs=versions(f,'x');ys=versions(f,'y')
        invariant('X_pointer_copy_old_value', ys[0]['source_value_version_id']==xs[0]['value_version_id']
            and return_values('X_pointer_copy')[0]['source_value_version_id']==ys[0]['value_version_id']
            and xs[1]['value_version_id']!=ys[0]['source_value_version_id'], f)
        for name in ['S04_two_returns','S05_early']:
            ts=transfers(name);rs=reads(caller(name),'b')
            invariant(name+'_all_return_alternatives', len(ts)==2
                and len({t['caller_result_version_id'] for t in ts})==2
                and len({t['caller_post_path_id'] for t in ts})==2
                and all(t['complete_call_status']=='PASS' and not t['callee_return_terminates_caller'] for t in ts)
                and len(rs)==2 and not caller(name)['paths_merged'], {'transfers':ts,'reads':rs})
        b=versions(caller('S05_early'),'b')
        invariant('S05_caller_reassignment_independent',len(b)==4
            and all(v['previous_version_id'] in {t['caller_result_version_id'] for t in transfers('S05_early')}
                    for v in b if v['assignment_kind']=='constant_assignment'), b)
        r=reports['S07_read'];first=transfers('S07_read')[0];second=r['call_contexts'][1]
        invariant('S07_use_b_binds_received_version',second['parameter_mapping_records'][0]['caller_pre_version']==first['caller_result_version_id']
            and any(rd['value_version_id']==first['caller_result_version_id'] and rd['role']=='call_argument'
                    for rd in reads(caller('S07_read'),'b')),r['call_contexts'])
        for name in ['S08_ignored','S09_void','X_zero_void','X_void_if']:
            ts=transfers(name)
            invariant(name+'_no_receiver_no_guard_injection', bool(ts)
                and all(t['caller_result_version_id'] is None and t['caller_result_slot_id'] is None
                    and not t['callee_return_terminates_caller'] and not t['guard_transferred_to_caller']
                    and t['caller_pre_environment']['guards']==t['caller_post_environment']['guards'] for t in ts),ts)
        invariant('ignored_distinct_from_void',all(t['return_value_ignored'] and not t['void_normal_return']
            for t in transfers('S08_ignored')) and all(t['void_normal_return'] and not t['return_value_ignored']
            for t in transfers('S09_void')),{'ignored':transfers('S08_ignored'),'void':transfers('S09_void')})
        invariant('S08_execution_and_caller_continuation',len(callee('S08_ignored')['path_returns'])==2
            and len(reads(caller('S08_ignored'),'b'))==2,caller('S08_ignored'))
        for name in ['S10_callsites','S11_caller_paths','X_repeated','X_same_param_names','X_double_actual']:
            r=reports[name];cs=r['call_contexts'];entries=[b['callee_entry_version'] for c in cs for b in c['callee_entry_bindings']]
            invariant(name+'_context_entries_unique',len({c['call_context_id'] for c in cs})==len(cs)
                and len(entries)==len(set(entries)) and all(not c['callee_state_reused'] and not c['summary_cache_used'] for c in cs),cs)
        cs=reports['S11_caller_paths']['call_contexts']
        invariant('S11_same_callsite_distinct_path',len(cs)==2 and cs[0]['callsite_id']==cs[1]['callsite_id']
            and cs[0]['caller_path_id']!=cs[1]['caller_path_id'],cs)
        for name in ['S03_constant','X_unsigned_literal','X_float_literal','X_pointer_constant']:
            rv=return_values(name)[0];lit=rv['literal']
            invariant(name+'_typed_literal_provenance',rv['status']=='PASS' and lit['type']['bit_width']>0
                and lit['source_range']['start']['byte_offset']<lit['source_range']['end_exclusive']['byte_offset']
                and lit['evaluated_as_mathematical_integer'] is False,rv)
        invariant('unsigned_literal_signedness',return_values('X_unsigned_literal')[0]['literal']['type']['signedness']=='unsigned',return_values('X_unsigned_literal'))
        invariant('X_unknown_partial_return_not_complete',any(v['status']=='PASS' and v.get('literal',{}).get('raw')=='2'
            for v in return_values('X_unknown_after_early')) and all(t['status']=='UNKNOWN' and t['caller_result_version_id'] is None
            for t in transfers('X_unknown_after_early')) and all(e['termination']=='UNKNOWN_EFFECT_STOP'
            for e in caller('X_unknown_after_early')['final_environments']),reports['X_unknown_after_early'])
        invariant('unsupported_body_no_false_entry_PASS',all(t['argument_mapping_status']=='PASS'
            and t['argument_entry_status']=='UNKNOWN' and not t['callee_entry_version']
            for t in transfers('S15_loop')),transfers('S15_loop'))
        for name in ['S13_global','S13_indirect','X_unknown_call','X_member_write','X_array_write','X_escape','X_static','X_volatile','X_atomic']:
            f=caller(name);barriers=[e for e in f['events'] if e['kind']=='unknown_effect_barrier']
            invariant(name+'_caller_invalidation',bool(barriers) and all(v is None for v in barriers[-1]['after']['current'].values())
                and not any(rd['role']=='discarded_value' for rd in reads(f,'b'))
                and not any(t['caller_result_version_id'] for t in transfers(name)),f)
        for name in ['S01_param','S02_local','S04_two_returns','S10_callsites','S11_caller_paths','X_multi_param','X_scope_result']:
            r=reports[name]
            for i,f in enumerate([r['caller']]+r['callees']):
                ids={v['value_version_id'] for v in f['versions']}
                invariant(name+'_local_graph_'+str(i),len(ids)==len(f['versions'])
                    and all(v['previous_version_id'] is None or v['previous_version_id'] in ids for v in f['versions'])
                    and all(v['source_value_version_id'] is None or v['source_value_version_id'] in ids for v in f['versions'])
                    and all(rd['value_version_id'] in ids for rd in f['reads'] if rd['status']=='PASS'),
                    {'function':f['function'],'version_count':len(ids),'read_count':len(f['reads'])})

        # Explicitly false candidates: no repair or renaming to turn them into PASS.
        def negative(name,source,mutate):
            p=proposal_from(reports[source]);mutate(p)
            result=verify_proposal(reports[source],p)
            record(name,'REJECT',result['status'],result)
        negative('S19_merge_contexts','S10_callsites',lambda p:p['transfers'][1].update(call_context_id=p['contexts'][0]))
        negative('S20_callee_return_terminates_caller','S05_early',lambda p:p['transfers'][0].update(callee_return_terminates_caller=True))
        a=versions(caller('S06_reassign_param'),'a')[0]
        negative('S21_write_back_to_caller_parameter','S06_reassign_param',lambda p:p['transfers'][0].update(caller_result_slot_id=a['slot_id'],caller_result_version_id=a['value_version_id']))
        negative('S22_drop_return_path','S04_two_returns',lambda p:p['transfers'].pop())
        negative('X_wrong_return_version','S01_param',lambda p:p['transfers'][0].update(callee_return_value_id='wrong-version'))
        entry=versions(callee('S06_reassign_param'),'x')[0]['value_version_id']
        negative('X_stale_callee_return_source','S06_reassign_param',lambda p:p['transfers'][0].update(callee_return_source_version=entry))
        negative('X_wrong_entry_version','S01_param',lambda p:p['transfers'][0].update(callee_entry_version=['wrong-entry']))
        negative('X_wrong_type_candidate','S01_param',lambda p:p['transfers'][0]['type_compatibility']['formal_type'].update(kind='POINTER'))
        negative('X_cross_path_version','S04_two_returns',lambda p:p['transfers'][0].update(caller_result_version_id=p['transfers'][1]['caller_result_version_id']))
        good=verify_proposal(reports['S01_param'],proposal_from(reports['S01_param']))
        record('correct_proposal','PASS',good['status'],good)
        result=verify_proposal(reports['S01_param'],{})
        record('missing_proposal','UNKNOWN',result['status'],result)
        result=verify_proposal(reports['S13_global'],{})
        record('unsupported_reference','UNKNOWN',result['status'],result)
        path=ROOT/'synthetic_fixtures/S01_param.c'
        def parse(data,pos,build='synthetic-self-contained'):
            return analyze(path,dataset_id=data,position=pos,build_status=build,caller='test')
        a=parse('repeat',0);b=parse('repeat',0)
        def semantic(obj):
            if isinstance(obj,dict):return {k:semantic(v) for k,v in obj.items() if k!='elapsed_seconds'}
            if isinstance(obj,list):return [semantic(v) for v in obj]
            return obj
        invariant('repeat_parse_determinism',semantic(a)==semantic(b),{'first':a,'second':b})
        c=parse('repeat',1);d=parse('other-dataset',0)
        invariant('dataset_and_position_context_isolation',len({x['call_contexts'][0]['call_context_id'] for x in [a,c,d]})==3,
            {'contexts':[x['call_contexts'][0] for x in [a,c,d]]})
        different_callers=ROOT/'synthetic_fixtures/different_callers.c'
        ca=analyze(different_callers,dataset_id='caller-test',position=0,build_status='synthetic-self-contained',caller='first')
        cb=analyze(different_callers,dataset_id='caller-test',position=0,build_status='synthetic-self-contained',caller='second')
        save(output/'different_callers.json',{'first':ca,'second':cb})
        invariant('same_callee_different_caller_isolation',ca['status']==cb['status']=='PASS'
            and ca['call_contexts'][0]['call_context_id']!=cb['call_contexts'][0]['call_context_id']
            and ca['call_contexts'][0]['callee_entry_bindings'][0]['callee_entry_version']!=
                cb['call_contexts'][0]['callee_entry_bindings'][0]['callee_entry_version'],{'first':ca,'second':cb})
        f=caller('S05_early');latest={v['value_version_id'] for v in versions(f,'b') if v['assignment_kind']=='constant_assignment'}
        invariant('caller_reads_after_reassignment_bind_latest',all(rd['value_version_id'] in latest for rd in reads(f,'b')),f)
        historical=parse('historical',0,'saved-source-only')
        record('historical_build_gate','UNKNOWN',historical['status'],historical)
        invariant('historical_no_recovery_propagation',not historical['call_contexts'] and not historical['return_transfers'] and historical['caller'] is None,historical)
        invariant('counts_all_four_statuses',counts(iter(['PASS','REJECT','UNKNOWN','N/A','UNKNOWN']))==
            {'PASS':1,'REJECT':1,'UNKNOWN':2,'N/A':1},counts(iter(['PASS','REJECT','UNKNOWN','N/A','UNKNOWN'])))
        for name,r in reports.items():
            invariant(name+'_metric_no_status_loss',
                sum(r['metrics']['complete_call'].values())==len(r['call_contexts'])
                and sum(r['metrics']['caller_result'].values())==len(r['return_transfers'])
                and sum(r['metrics']['call_effect_coverage'].values())==len(r['callees']),r['metrics'])
    except Exception as exc:
        save(output/'failure.json',{'type':type(exc).__name__,'exception':str(exc),'traceback':traceback.format_exc(),'completed_tests':tests})
        raise
    metrics={}
    metric_reports=list(reports.values())+[ca,cb]
    for name in next(iter(reports.values()))['metrics']:
        metrics[name]={s:sum(r['metrics'][name][s] for r in metric_reports) for s in ('PASS','REJECT','UNKNOWN','N/A')}
    result={'fixture_count':len(cases)+1,'primary_manifest_scenarios':len(cases),'additional_scenarios':1,
            'total':len(tests),'passed':sum(t['passed'] for t in tests),
            'all_passed':all(t['passed'] for t in tests),'tests':tests,
            'scenario_status_counts':counts([r['status'] for r in reports.values()]+['PASS' if ca['status']==cb['status']=='PASS' else 'UNKNOWN']),
            'check_observation_status_counts':counts(t['actual'] for t in tests),
            'relation_metrics':metrics,'analysis_runs_in_relation_metrics':len(metric_reports),
            'elapsed_seconds':time.perf_counter()-started,
            'LLM_calls':0,'Harness_calls':0,'Z3_calls':0,'SMT_generated':0,'API_cost_CNY':0,
            'external_operations':offline_boundary.EVENTS}
    save(output/'synthetic_test_results.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='tests'}))
    if not result['all_passed']:
        print(json.dumps([t for t in tests if not t['passed']],ensure_ascii=False)[:4000])
        raise SystemExit(1)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=__import__('pathlib').Path,required=True)
    run(p.parse_args().output)
