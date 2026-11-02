"""C-source expectations and independent object/value/memory invariants."""
import argparse
import copy
import json
from pathlib import Path
import time
import traceback
from r03_adapter import ROOT,r01,counts,offline_boundary
from indirect_write import analyze,proposal_from,verify_proposal


def save(path,obj):
    with path.open('x',encoding='utf-8',newline='\n') as f:json.dump(obj,f,indent=2,ensure_ascii=False);f.write('\n')


def run(output):
    offline_boundary.install();output.mkdir(parents=True,exist_ok=False)
    start=time.perf_counter();tests=[];reports={};additional=[]
    def record(name,expected,actual,evidence):
        tests.append({'test':name,'expected':expected,'actual':actual,'passed':expected==actual,
            'evidence':evidence,'mismatch_reason':None if expected==actual else 'actual_differs_from_contract'})
    def check(name,ok,evidence):record(name,'PASS','PASS' if ok else 'REJECT',evidence)
    try:
        cases=json.loads((ROOT/'synthetic_fixtures/cases.json').read_text('utf-8'))
        for case in cases:
            path=ROOT/'synthetic_fixtures'/case['source'];assert r01.digest(path.read_bytes())==case['source_sha256']
            report=analyze(path,dataset_id='synthetic-r04',position=0,build_status='synthetic-self-contained',caller=case['caller'],
                candidate_source_paths=[ROOT/'synthetic_fixtures'/p for p in case.get('candidate_source_paths',[])])
            reports[case['case']]=report;save(output/(case['case']+'.json'),report)
            record(case['case'],case['expected_status'],report['status'],case)
        if any(not t['passed'] for t in tests):
            raise AssertionError('source scenario status mismatch: '+repr([(t['test'],t['actual']) for t in tests if not t['passed']]))
        def f(name):return reports[name]['caller']
        def t(name,i=0):return reports[name]['effect_transfers'][i]
        def callee(name,i=0):return reports[name]['callees'][i]
        def vs(name,var):return [v for v in f(name)['versions'] if v['declaration_identity']['name']==var]
        def rd(name,var):
            slots={s['slot_id'] for s in f(name)['slots'] if s['declaration']['name']==var}
            return [r for r in f(name)['reads'] if r['slot_id'] in slots]
        x=vs('S01_write','x');r=reports['S01_write'];tr=t('S01_write');pr=callee('S01_write')['pointer_targets'][0]
        check('S01_full_chain_distinct_identities',len(x)==2 and x[1]['previous_version_id']==x[0]['value_version_id']
            and tr['evidence_chain']['CallerPre']==x[0]['value_version_id']
            and tr['evidence_chain']['CallerPost']['value_version_id']==x[1]['value_version_id']
            and len({pr['pointer_slot_id'],x[0]['slot_id'],tr['target_memory_object_id']})==3
            and pr['target_memory_object_id']==r['memory_objects'][0]['memory_object_id'],tr)
        check('S02_read_latest',len(rd('S02_read','x'))==1 and rd('S02_read','x')[0]['value_version_id']==t('S02_read')['caller_post_version'],rd('S02_read','x'))
        x=vs('S03_old','x');y=vs('S03_old','y')
        check('S03_old_copy_preserved',len(x)==2 and y[0]['source_value_version_id']==x[0]['value_version_id']
            and rd('S03_old','y')[0]['value_version_id']==y[0]['value_version_id'],f('S03_old'))
        for name in ['S04_rebind','X_no_write','X_early_return']:
            tr=t(name)
            check(name+'_no_caller_version',len(vs(name,'x'))==1 and tr['caller_post_version'] is None
                and tr['caller_new_version_status']=='N/A' and tr['caller_pre_environment']['current']==tr['caller_post_environment']['current']
                and tr['caller_pre_environment']['memory_current']==tr['caller_post_environment']['memory_current'],tr)
        cp=callee('S04_rebind')['versions']
        check('S04_pointer_local_version_only',len(cp)==2 and cp[1]['previous_version_id']==cp[0]['value_version_id']
            and cp[1]['value']['kind']=='null_pointer_constant',cp)
        cp=callee('S05_write_rebind')['versions'];w=callee('S05_write_rebind')['indirect_writes'][0]
        check('S05_write_survives_later_pointer_rebind',len(cp)==2 and w['pointer_current_version']==cp[0]['value_version_id']
            and t('S05_write_rebind')['caller_post_version']==vs('S05_write_rebind','x')[-1]['value_version_id'],callee('S05_write_rebind'))
        r=reports['S06_two_targets'];a,b=r['effect_transfers']
        check('S06_updates_only_own_target',a['target_memory_object_id']!=b['target_memory_object_id']
            and a['call_context_id']!=b['call_context_id'] and b['caller_post_environment']['current'][vs('S06_two_targets','x')[0]['slot_id']]==a['caller_post_version'],r['effect_transfers'])
        cs=reports['S07_caller_paths']['call_contexts'];ts=reports['S07_caller_paths']['effect_transfers']
        check('S07_same_site_distinct_paths',len(cs)==2 and cs[0]['callsite_id']==cs[1]['callsite_id']
            and cs[0]['caller_path_id']!=cs[1]['caller_path_id'] and cs[0]['call_context_id']!=cs[1]['call_context_id']
            and ts[0]['caller_post_version']!=ts[1]['caller_post_version'] and len(rd('S07_caller_paths','x'))==2,cs)
        x=vs('S29_later_assignment','x');m=reports['S29_later_assignment']['memory_versions']
        check('S29_read_latest_local_assignment',len(x)==3 and rd('S29_later_assignment','x')[0]['value_version_id']==x[2]['value_version_id']
            and len(m)==3 and m[2]['previous_memory_version_id']==m[1]['memory_version_id'],{'values':x,'memory':m})
        a,b=reports['X_same_object_twice']['effect_transfers']
        check('same_object_sequential_memory_chain',a['target_memory_object_id']==b['target_memory_object_id']
            and a['call_context_id']!=b['call_context_id'] and b['caller_pre_version']==a['caller_post_version']
            and b['caller_pre_memory_version']==a['caller_post_memory_version'],[a,b])
        check('S32_write_type_unknown_after_valid_entry',len(callee('S32_narrow_write')['pointer_targets'])==1
            and callee('S32_narrow_write')['indirect_writes'][0]['type_compatibility']['status']=='UNKNOWN',callee('S32_narrow_write'))
        check('rebinding_before_store_does_not_use_entry_target',callee('X_rebind_before_write')['indirect_writes'][0]['status']=='UNKNOWN'
            and callee('X_rebind_before_write')['indirect_writes'][0]['target_memory_object_id'] is None
            and t('X_rebind_before_write')['caller_post_version'] is None,callee('X_rebind_before_write'))
        for name in ['S10_global_escape','S11_return_escape','S12_transfer_escape','S13_arithmetic','S14_pointer_copy','S19_unknown_call','S20_global_write','S24_two_writes','S25_compound','S26_increment','S27_read_modify','S28_branch','X_other_indirect']:
            tr=t(name);barriers=[e for e in f(name)['events'] if e['kind']=='unknown_effect_barrier']
            check(name+'_unknown_blocks_both_environments',tr['status']=='UNKNOWN' and tr['caller_post_version'] is None
                and tr['caller_post_memory_version'] is None and tr['caller_post_environment'] is None
                and bool(barriers) and all(v is None for v in barriers[-1]['after']['current'].values())
                and all(v is None for v in barriers[-1]['after']['memory_current'].values())
                and not rd(name,'x'),tr)
        for name in ['S10_global_escape','S11_return_escape','S12_transfer_escape','S14_pointer_copy']:
            check(name+'_escape_recorded_unknown',bool(callee(name)['escape_events'])
                and callee(name)['escape_coverage']=='UNKNOWN',callee(name)['escape_events'])
        check('unknown_use_reads_received_value_then_stops',any(r['role']=='call_argument' and r['value_version_id']==t('X_unknown_caller_after')['caller_post_version']
            for r in rd('X_unknown_caller_after','x')) and f('X_unknown_caller_after')['final_environments'][0]['termination']=='UNKNOWN_EFFECT_STOP',f('X_unknown_caller_after'))
        for name in ['X_unsigned','X_double','X_widen_write']:
            w=callee(name)['indirect_writes'][0]
            check(name+'_typed_literal',w['assigned_value']['source_type']['bit_width']>0
                and not w['assigned_value']['evaluated_as_mathematical_integer'] and w['type_compatibility']['status']=='PASS',w)
        check('shadowed_objects_separate',len(reports['X_shadow']['memory_objects'])==2 and
            len({o['memory_object_id'] for o in reports['X_shadow']['memory_objects']})==2,reports['X_shadow']['memory_objects'])
        inner=t('X_shadow')['target_memory_object_id']
        check('inner_scope_object_no_longer_active',inner not in t('X_shadow',1)['caller_pre_environment']['memory_current'],reports['X_shadow']['effect_transfers'])
        r=reports['X_context_budget']
        check('context_budget_stops_without_dropping_attempt',len(r['call_contexts'])==16 and len(r['call_attempts'])==17
            and r['call_attempts'][-1]['reasons']==['call_context_budget_exceeded']
            and f('X_context_budget')['final_environments'][0]['termination']=='UNKNOWN_EFFECT_STOP',r['call_attempts'][-1])
        def negative(name,source,mutator):
            p=proposal_from(reports[source]);mutator(p);result=verify_proposal(reports[source],p)
            record(name,'REJECT',result['status'],result)
        ptr=callee('S01_write')['pointer_targets'][0]
        negative('S08_pointer_slot_as_object','S01_write',lambda p:p['transfers'][0].update(target_memory_object_id=ptr['pointer_slot_id']))
        other=t('S06_two_targets',1)['target_memory_object_id']
        negative('S09_wrong_local_target','S06_two_targets',lambda p:p['transfers'][0].update(target_memory_object_id=other))
        negative('S30_merge_address_evidence','S06_two_targets',lambda p:p['transfers'][1].update(address_evidence_id=p['transfers'][0]['address_evidence_id']))
        negative('S31_deny_visible_prefix_write','S19_unknown_call',lambda p:p.update(has_indirect_write=False))
        negative('S32_wrong_write_type_candidate','S01_write',lambda p:p['writes'][0]['assigned_value_type'].update(kind='POINTER'))
        negative('wrong_call_context','S06_two_targets',lambda p:p['transfers'][1].update(call_context_id=p['transfers'][0]['call_context_id']))
        negative('wrong_old_memory_version','X_same_object_twice',lambda p:p['transfers'][1].update(caller_pre_memory_version=p['transfers'][0]['caller_pre_memory_version']))
        negative('wrong_write_pointer_version','S05_write_rebind',lambda p:p['writes'][0].update(pointer_current_version=cp[-1]['value_version_id']))
        negative('wrong_caller_post_version','S01_write',lambda p:p['transfers'][0].update(caller_post_version=p['transfers'][0]['caller_pre_version']))
        negative('wrong_literal_value','S01_write',lambda p:p['writes'][0]['assigned_value'].update(raw_literal='20'))
        p=proposal_from(reports['S01_write']);result=verify_proposal(reports['S01_write'],p)
        record('correct_claim','PASS',result['status'],result)
        record('missing_claim','UNKNOWN',verify_proposal(reports['S01_write'],{})['status'],{})
        record('unsupported_reference','UNKNOWN',verify_proposal(reports['S19_unknown_call'],{})['status'],{})
        def again(data,pos,build='synthetic-self-contained',function='test',source='S01_write.c'):
            return analyze(ROOT/'synthetic_fixtures'/source,dataset_id=data,position=pos,build_status=build,caller=function)
        a=again('repeat',0);b=again('repeat',0)
        def semantic(obj):
            if isinstance(obj,dict):return {k:semantic(v) for k,v in obj.items() if k!='elapsed_seconds'}
            if isinstance(obj,list):return [semantic(v) for v in obj]
            return obj
        check('repeat_parse_stable',semantic(a)==semantic(b),{'first':a,'second':b})
        c=again('repeat',1);d=again('other',0)
        check('dataset_position_object_and_context_isolation',len({r['memory_objects'][0]['memory_object_id'] for r in [a,c,d]})==3
            and len({r['call_contexts'][0]['call_context_id'] for r in [a,c,d]})==3,{'contexts':[r['call_contexts'][0] for r in [a,c,d]]})
        ca=again('callers',0,function='first',source='different_callers.c');cb=again('callers',0,function='second',source='different_callers.c')
        additional=[ca,cb];save(output/'different_callers.json',{'first':ca,'second':cb})
        check('different_callers_same_callee',ca['status']==cb['status']=='PASS'
            and ca['memory_objects'][0]['memory_object_id']!=cb['memory_objects'][0]['memory_object_id']
            and ca['call_contexts'][0]['call_context_id']!=cb['call_contexts'][0]['call_context_id'],{'first':ca,'second':cb})
        hist=again('historical',0,build='saved-source-only')
        record('historical_build_gate','UNKNOWN',hist['status'],hist)
        check('historical_no_recovery_approval',not hist['memory_objects'] and not hist['call_contexts'] and not hist['effect_transfers'],hist)
        for name,r in reports.items():
            mvs=r['memory_versions'];ids={m['memory_version_id'] for m in mvs};objs={o['memory_object_id'] for o in r['memory_objects']}
            check(name+'_memory_graph',len(ids)==len(mvs) and all(m['previous_memory_version_id'] is None or m['previous_memory_version_id'] in ids for m in mvs)
                and all(m['memory_object_id'] in objs for m in mvs),{'versions':len(mvs),'objects':len(objs),'source_sha256':r['source_sha256']})
            check(name+'_metric_counts',sum(r['metrics']['address_evidence'].values())==len(r['call_attempts'])
                and sum(r['metrics']['complete_call'].values())==len(r['call_contexts'])
                and sum(r['metrics']['caller_new_version'].values())==len(r['call_attempts']),r['metrics'])
    except Exception as exc:
        save(output/'failure.json',{'type':type(exc).__name__,'exception':str(exc),'traceback':traceback.format_exc(),'completed_checks':tests})
        print(str(exc));raise
    metric_reports=list(reports.values())+additional;metrics={}
    for key in next(iter(reports.values()))['metrics']:
        metrics[key]={s:sum(r['metrics'][key][s] for r in metric_reports) for s in ('PASS','REJECT','UNKNOWN','N/A')}
    result={'fixture_count':len(cases)+1,'primary_manifest_scenarios':len(cases),'relation_analysis_count':len(metric_reports),
        'total':len(tests),'passed':sum(t['passed'] for t in tests),'all_passed':all(t['passed'] for t in tests),'tests':tests,
        'scenario_status_counts':counts([r['status'] for r in reports.values()]+['PASS' if ca['status']==cb['status']=='PASS' else 'UNKNOWN']),
        'check_status_counts':counts(t['actual'] for t in tests),'relation_metrics':metrics,
        'elapsed_seconds':time.perf_counter()-start,'LLM_calls':0,'Harness_calls':0,'Z3_calls':0,'SMT_generated':0,
        'API_cost_CNY':0,'external_operations':offline_boundary.EVENTS}
    save(output/'synthetic_test_results.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='tests'}))
    if not result['all_passed']:
        print(json.dumps([t for t in tests if not t['passed']],ensure_ascii=False)[:4000]);raise SystemExit(1)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);run(p.parse_args().output)
