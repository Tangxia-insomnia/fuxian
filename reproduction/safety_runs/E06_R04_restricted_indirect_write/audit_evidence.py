"""Inspect saved evidence and frozen historical references; no source reruns."""
import json
from r03_adapter import ROOT,r01,counts
from run_r04 import save


def audit():
    checks=[];contexts=[];entries=[];blocked_attempts=0;attempts=0;context_statuses=[];escape_events=[]
    def check(name,ok):checks.append({'check':name,'status':'PASS' if ok else 'REJECT'})
    paths=sorted((ROOT/'synthetic_runs/final_candidate_01').glob('*.json'));reports=[]
    for p in paths:
        if p.name=='synthetic_test_results.json':continue
        data=json.loads(p.read_text('utf-8'))
        if p.name=='different_callers.json':reports.extend(data.values())
        else:reports.append(data)
    for report in reports:
        label=__import__('pathlib').Path(report['source']).stem
        blob=__import__('pathlib').Path(report['source']).read_bytes()
        check(label+'_source_snapshot',r01.digest(blob)==report['source_sha256'])
        objs={o['memory_object_id']:o for o in report['memory_objects']}
        mvs={v['memory_version_id']:v for v in report['memory_versions']}
        cvs={v['value_version_id']:v for v in (report['caller']['versions'] if report['caller'] else [])}
        for mv in mvs.values():
            prior=mvs.get(mv['previous_memory_version_id']);vid=mv['caller_value_version_id']
            check(label+'_memory_'+mv['memory_version_id'][-8:],mv['memory_object_id'] in objs and vid in cvs
                and (prior is None and mv['previous_memory_version_id'] is None or prior is not None and prior['memory_object_id']==mv['memory_object_id'])
                and cvs[vid]['slot_id']==objs[mv['memory_object_id']]['caller_slot_id'])
        callee_by={f['call_context_id']:f for f in report['callees']}
        context_by={c['call_context_id']:c for c in report['call_contexts']}
        for ctx in report['call_contexts']:
            contexts.append(ctx['call_context_id']);context_statuses.append(ctx['status'])
            f=callee_by[ctx['call_context_id']];pt=f['pointer_targets'][0]
            entries.append(pt['callee_entry_version_id']);escape_events.extend(f['escape_events'])
            check(label+'_lexical_instance_'+ctx['call_context_id'][-8:],f['function']['usr']==ctx['callee_function_identity']['usr']
                and f['function']['location']==ctx['callee_function_identity']['location'] and f['body_sha256']==ctx['callee_body_sha256'])
            check(label+'_pointer_target_'+pt['pointer_target_id'][-8:],pt['target_memory_object_id']==ctx['target_memory_object_id']
                and pt['pointer_slot_id']!=objs[pt['target_memory_object_id']]['caller_slot_id']
                and pt['callee_entry_version_id'] not in cvs
                and f['versions'][0]['value']['kind']=='address_argument_transfer')
        for transfer in report['effect_transfers']:
            oid=transfer['target_memory_object_id'];ctx=context_by[transfer['call_context_id']];f=callee_by[ctx['call_context_id']]
            pre=transfer['caller_pre_environment'];post=transfer['caller_post_environment'];sid=objs[oid]['caller_slot_id']
            check(label+'_pre_chain_'+transfer['effect_transfer_id'][-8:],pre['current'][sid]==transfer['caller_pre_version']
                and mvs[transfer['caller_pre_memory_version']]['caller_value_version_id']==transfer['caller_pre_version']
                and ctx['parameter_mapping_records'][0]['target_memory_object_id']==oid)
            if transfer['status']=='PASS':
                check(label+'_complete_effect_'+transfer['effect_transfer_id'][-8:],transfer['effect_coverage']=='PASS'
                    and all(p['status']=='PASS' for p in f['path_returns']) and f['escape_coverage']=='PASS'
                    and pre['guards']==post['guards'] and all(v==post['current'].get(k) for k,v in pre['current'].items() if k!=sid))
                if transfer['caller_post_version'] is not None:
                    vid=transfer['caller_post_version'];mv=mvs[transfer['caller_post_memory_version']];w=f['indirect_writes'][0]
                    check(label+'_write_commit_'+transfer['effect_transfer_id'][-8:],len(f['indirect_writes'])==1
                        and w['target_memory_object_id']==oid and w['pointer_current_version']==w['pointer_entry_version']
                        and post['current'][sid]==vid and cvs[vid]['previous_version_id']==transfer['caller_pre_version']
                        and mv['previous_memory_version_id']==transfer['caller_pre_memory_version']
                        and mv['write_event_id']==w['write_event_id'] and mv['caller_value_version_id']==vid
                        and transfer['caller_pre_version'] in cvs and w['type_compatibility']['status']=='PASS')
                else:check(label+'_no_false_write_'+transfer['effect_transfer_id'][-8:],not f['indirect_writes']
                    and pre['current']==post['current'] and pre['memory_current']==post['memory_current'])
            else:check(label+'_uncovered_no_commit_'+transfer['effect_transfer_id'][-8:],post is None
                and transfer['caller_post_version'] is None and transfer['caller_post_memory_version'] is None)
        for attempt in report['call_attempts']:
            attempts+=1
            if attempt['status']=='UNKNOWN':
                lo=attempt['callsite']['start']['byte_offset'];hi=attempt['callsite']['end_exclusive']['byte_offset']
                barriers=[e for e in report['caller']['events'] if e['kind']=='unknown_effect_barrier'
                    and lo<=e['source_range']['start']['byte_offset']<=hi]
                blocked=bool(barriers) and barriers[-1]['after']['termination']=='UNKNOWN_EFFECT_STOP'
                blocked=blocked and all(v is None for v in barriers[-1]['after']['current'].values())
                blocked=blocked and all(v is None for v in barriers[-1]['after'].get('memory_current',{}).values())
                check(label+'_unknown_attempt_block_'+str(lo),blocked)
                blocked_attempts+=bool(blocked)
    check('all_contexts_isolated',len(contexts)==len(set(contexts)))
    check('all_pointer_entries_isolated',len(entries)==len(set(entries)))
    synth=json.loads((ROOT/'synthetic_runs/final_candidate_01/synthetic_test_results.json').read_text('utf-8'))
    check('final_tests_expected',synth['all_passed'] and synth['passed']==synth['total']==257 and synth['fixture_count']==68)
    for rel,n in [('r01_core_recheck/test_results.json',41),('r02_core_recheck/synthetic_test_results.json',110),
                  ('r03_core_recheck/synthetic_test_results.json',201),('r03_boundary_recheck/test_results.json',15)]:
        data=json.loads((ROOT/rel).read_text('utf-8'))
        check(rel,data['all_passed'] and data['passed']==data['total']==n and not data['external_operations'])
    hist=json.loads((ROOT/'historical_results.json').read_text('utf-8'))
    check('four_historical_unknown',len(hist['rows'])==4 and all(r['status']=='UNKNOWN' for r in hist['rows']))
    check('historical_no_objects_or_write_approval',all(r['verified_objects']==r['verified_indirect_writes']==r['verified_caller_new_versions']==0 for r in hist['rows']))
    check('historical_original_risks_not_promoted',all(not p['recomputed_or_promoted_by_R04'] for r in hist['rows'] for p in r['prior_diagnoses_preserved']))
    check('OpenSSL_return_still_ignored',hist['rows'][0]['edges'][0]['callsite_candidates'][0]['result_disposition_candidate']=='ignored'
          and not hist['rows'][0]['edges'][0]['caller_state_updated'])
    return {'all_passed':all(c['status']=='PASS' for c in checks),'checks':checks,
        'check_status_counts':counts(c['status'] for c in checks),'contexts_examined':len(contexts),'pointer_entries_examined':len(entries),
        'context_isolation_counts':{'PASS':len(contexts),'REJECT':0,'UNKNOWN':0,'N/A':0},
        'call_attempt_count':attempts,'unknown_attempts_confirmed_blocked':blocked_attempts,
        'unknown_attempt_block_counts':{'PASS':blocked_attempts,'REJECT':0,'UNKNOWN':0,'N/A':attempts-blocked_attempts},
        'escape_event_status_counts':counts(e['status'] for e in escape_events),
        'escape_reason_counts':dict(__import__('collections').Counter(e['reason'] for e in escape_events)),
        'new_source_analyses':0,'new_fixed20_executions':0}


if __name__=='__main__':
    result=audit();save(ROOT/'pre_freeze_evidence_check.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='checks'}))
    if not result['all_passed']:
        print(json.dumps([c for c in result['checks'] if c['status']!='PASS']));raise SystemExit(1)
