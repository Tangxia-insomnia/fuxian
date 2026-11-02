"""Parameterized source fixtures plus independent def-use/path invariants."""
import argparse
import json
from pathlib import Path
import time

from r01_adapter import ROOT, offline_boundary, r01, link_call_reads
from value_version import analyze, verify_expression_claim, verify_read_claim


def main(output):
    offline_boundary.install()
    output.mkdir(exist_ok=False, parents=True)
    started=time.perf_counter(); tests=[]; reports={}
    def record(name, expected, actual, passed, evidence):
        tests.append({'test':name,'expected':expected,'actual':actual,'passed':bool(passed),'evidence':evidence})
    def save(path,obj):
        with path.open('x',encoding='utf-8') as f:json.dump(obj,f,indent=2);f.write('\n')
    cases=json.loads((ROOT/'synthetic_fixtures/cases.json').read_text('utf-8'))
    for case in cases:
        path=ROOT/'synthetic_fixtures'/case['source']
        assert r01.digest(path.read_bytes())==case['source_sha256']
        report=analyze(path,dataset_id='synthetic-r02',position=0,
                       build_status='synthetic-self-contained',function=case['function'])
        reports[case['case']]=report;save(output/(case['case']+'.json'),report)
        record(case['case'],case['expected_status'],report['status'],report['status']==case['expected_status'],case)
    def function(name):return reports[name]['functions'][0]
    def named_versions(name,var):
        return [v for v in function(name)['versions'] if v['declaration_identity']['name']==var]
    def tail_reads(name,var):
        f=function(name); slots={s['slot_id'] for s in f['slots'] if s['declaration']['name']==var}
        return [rd for rd in f['reads'] if rd['slot_id'] in slots and rd['role']=='discarded_value']
    p=named_versions('S01_reassign','p');read=tail_reads('S01_reassign','p')[0]
    record('S01_versions_and_last_read','p@0,p@1,p@2; tail binds p@2',
           [v['display_name'] for v in p],len(p)==3 and p[1]['previous_version_id']==p[0]['value_version_id'] and
           p[2]['previous_version_id']==p[1]['value_version_id'] and read['value_version_id']==p[2]['value_version_id'] and
           p[1]['value']['kind']=='null_pointer_constant' and p[2]['value']['kind']=='value_copy',{'versions':p,'read':read})
    wrong=verify_read_claim(reports['S01_reassign'],read['read_id'],read['slot_id'],p[1]['value_version_id'])
    record('S02_wrong_version_merge','REJECT',wrong['status'],wrong['status']=='REJECT',wrong)
    good=verify_read_claim(reports['S01_reassign'],read['read_id'],read['slot_id'],p[2]['value_version_id'])
    record('S02_correct_read_claim','PASS',good['status'],good['status']=='PASS',good)
    p=named_versions('S03_copy','p');q=named_versions('S03_copy','q');rd=tail_reads('S03_copy','q')[0]
    record('S03_copy_stays_old','q@0 copies p@0; p@1 independent',rd['value_version_id'],
           q[0]['slot_id']!=p[0]['slot_id'] and q[0]['source_value_version_id']==p[0]['value_version_id'] and
           rd['value_version_id']==q[0]['value_version_id'] and p[1]['value_version_id']!=q[0]['source_value_version_id'],
           {'p':p,'q':q,'read':rd})
    wrong=verify_read_claim(reports['S03_copy'],rd['read_id'],p[1]['slot_id'],p[1]['value_version_id'])
    record('S03_wrong_copy_rebinding','REJECT',wrong['status'],wrong['status']=='REJECT',wrong)
    f=function('S04_branches');rs=tail_reads('S04_branches','p')
    record('S04_paths_separate','2 distinct path reads/definitions, no phi',len(rs),
           len(rs)==2 and len({x['path_id'] for x in rs})==2 and
           len({x['value_version_id'] for x in rs})==2 and f['paths_merged'] is False and
           {e['guards'][0]['direction'] for e in f['final_environments']}=={True,False},f)
    wrong=verify_read_claim(reports['S04_branches'],rs[0]['read_id'],rs[0]['slot_id'],rs[1]['value_version_id'])
    record('S04_wrong_cross_path_claim','REJECT',wrong['status'],wrong['status']=='REJECT',wrong)
    f=function('S04_early_return');rs=tail_reads('S04_early_return','p')
    record('S04_return_stops_only_own_path','one continuation read, false direction, no nonnull inference',len(rs),
           len(rs)==1 and sorted(str(p['termination']) for p in f['final_environments'])==['None','RETURN'] and
           next(e for e in f['final_environments'] if e['path_id']==rs[0]['path_id'])['guards'][0]['direction'] is False and
           all(not g['semantics_inferred'] and not g['SMT_generated'] for e in f['final_environments'] for g in e['guards']),f)
    report=reports['S07_member'];member=next(e for e in report['expression_evidence'] if e['kind']=='MEMBER_REF_EXPR')
    root=next(e for e in report['expression_evidence'] if e['text']=='skb')
    v=verify_expression_claim(report,member['expression_id'],root['referenced_declaration']['declaration_id'])
    record('S07_root_member_conflict','REJECT',v['status'],v['status']=='REJECT',v)
    v=verify_expression_claim(reports['S07_missing_member_type'],'unverified','unknown')
    record('S07_missing_evidence','UNKNOWN',v['status'],v['status']=='UNKNOWN',v)
    f=function('X_scope');rs=tail_reads('X_scope','q')
    record('X_scope_isolation','inner q and outer q distinct and correctly bound',len(rs),
           len(rs)==2 and rs[0]['slot_id']!=rs[1]['slot_id'] and
           rs[0]['value_version_id']!=rs[1]['value_version_id'],f)
    p=named_versions('X_self_assignment','p')
    record('X_self_copy','new version depends on previous version',len(p),len(p)==2 and
           p[1]['source_value_version_id']==p[0]['value_version_id'] and
           p[1]['previous_version_id']==p[0]['value_version_id'],p)
    p=named_versions('X_sequence','x')
    record('X_multiple_writes_preserved','4 immutable versions',len(p),len(p)==4 and
           all(p[i]['previous_version_id']==p[i-1]['value_version_id'] for i in range(1,4)),p)
    f=function('X_unknown_return');p=named_versions('X_unknown_return','p')
    record('X_unknown_return_barrier','new unknown assignment, prefix retained, no later read PASS',len(p),
           len(p)==2 and p[1]['status']=='UNKNOWN' and p[1]['value']['kind']=='unknown_return' and
           p[1]['previous_version_id']==p[0]['value_version_id'] and bool(f['unprocessed_ranges']) and
           not tail_reads('X_unknown_return','p'),f)
    for name in ['X_address_escape','X_indirect_write','X_member_write','X_array_write','X_call_bridge']:
        f=function(name)
        barriers=[e for e in f['events'] if e['kind']=='unknown_effect_barrier']
        record(name+'_invalidate','current bindings invalidated; no continuation approved',len(barriers),
               bool(barriers) and all(v is None for v in barriers[-1]['after']['current'].values()) and
               barriers[-1]['after']['termination']=='UNKNOWN_EFFECT_STOP',f)
    # Candidate/source identity is linked to the accepted R01, effects stay unknown.
    path=ROOT/'synthetic_fixtures/X_call_bridge.c'
    r1=r01.analyze(path,dataset_id='synthetic-r02',position=0,build_status='synthetic-self-contained')
    links=link_call_reads(reports['X_call_bridge'],r1)
    record('X_R01_value_interface','verified pre-call read link, no callee propagation',len(links),
           len(links)==1 and links[0]['status']=='PASS' and links[0]['whole_call_effect_status']=='UNKNOWN' and
           not links[0]['slots_merged'] and not links[0]['callee_state_propagated'],{'R01':r1,'links':links})
    f=function('X_argument_order')
    record('X_no_false_argument_reaching_definition','no argument read approved across unsequenced write',len(f['reads']),
           not f['reads'] and f['status']=='UNKNOWN',f)
    path=ROOT/'synthetic_fixtures/X_two_functions.c'
    full=analyze(path,dataset_id='functions',position=0,build_status='synthetic-self-contained')
    slots=[s['slot_id'] for f in full['functions'] for s in f['slots'] if s['declaration']['name']=='p']
    record('X_different_functions_same_name','2 distinct slots',len(set(slots)),
           len(slots)==len(set(slots))==2,full)
    path=ROOT/'synthetic_fixtures/S03_copy.c'
    a=analyze(path,dataset_id='repeat',position=0,build_status='synthetic-self-contained',function='test')
    b=analyze(path,dataset_id='repeat',position=0,build_status='synthetic-self-contained',function='test')
    a.pop('elapsed_seconds');b.pop('elapsed_seconds')
    record('X_repeatability','identical semantic records',a==b,a==b,{'first':a,'second':b})
    historical=analyze(path,dataset_id='saved-negative',position=0,build_status='saved-source-only',function='test')
    record('X_build_gate','UNKNOWN, no verified versions',historical['status'],historical['status']=='UNKNOWN' and
           all(not f['versions'] for f in historical['functions']),historical)
    for name,report in reports.items():
        for f in report['functions']:
            ids={v['value_version_id'] for v in f['versions']}
            invariant=(len(ids)==len(f['versions']) and all(v['previous_version_id'] is None or v['previous_version_id'] in ids for v in f['versions']) and
                       all(v['source_value_version_id'] is None or v['source_value_version_id'] in ids for v in f['versions']) and
                       all(rd['value_version_id'] in ids for rd in f['reads'] if rd['status']=='PASS'))
            record(name+'_graph_integrity','no deleted or dangling definition links',invariant,invariant,
                   {'source_sha256':report['source_sha256'],'versions':len(ids),'reads':len(f['reads'])})
    result={'tests':tests,'fixture_count':len(cases),'passed':sum(x['passed'] for x in tests),'total':len(tests),
            'all_passed':all(x['passed'] for x in tests),'elapsed_seconds':time.perf_counter()-started,
            'model_calls':0,'Z3_calls':0,'generated_code_execution':0,'external_operations':offline_boundary.EVENTS}
    save(output/'synthetic_test_results.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='tests'}))
    if not result['all_passed']:
        print(json.dumps([x for x in tests if not x['passed']],ensure_ascii=True)[:12000])
        raise SystemExit(1)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    main(parser.parse_args().output)
