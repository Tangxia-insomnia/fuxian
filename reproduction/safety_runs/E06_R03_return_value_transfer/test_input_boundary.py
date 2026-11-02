"""Regression for prior null-context failure and text-only historical locators."""
import argparse
import json
from pathlib import Path
from adapter import ROOT, r01, offline_boundary, counts, STATUSES
from run_r03 import RF, save
from source_locator import returns, calls_to


def main(output):
    offline_boundary.install();output.mkdir(parents=True,exist_ok=False);checks=[]
    def record(name,expected,actual,evidence):
        checks.append({'test':name,'expected':expected,'actual':actual,'passed':expected==actual,'evidence':evidence})
    bad=[{}, {'context':[]},{'context':{}},{'context':{'frames':None}},
         {'context':{'frames':[None]}},{'context':{'frames':[{}]}},
         {'context':{'frames':[{'function':'f','code':'int f(){}','body_sha256':'wrong'}]}},
         {'context':None}]
    for i,obj in enumerate(bad):
        try:RF.context_state(obj);actual='ACCEPTED'
        except RF.DataShapeError:actual='STOP'
        record('malformed_'+str(i),'STOP',actual,obj)
    state,frames=RF.context_state({'context':{'frames':[]}})
    record('empty_frames_explicit','EMPTY_FRAMES_ARRAY',state,{'frames':frames})
    bundle={'context':None,'candidate':{'status':'blocked_context','error':'context not saved'}}
    provenance={'verified':True,'context_file_absent':True,'historical_status':'blocked_context','historical_error':'context not saved'}
    state,frames=RF.context_state(bundle,provenance)
    record('proven_absence_is_not_runtime_error','EXPLICIT_NULL_SAVED_CONTEXT_UNAVAILABLE',state,{'frames':frames,'provenance':provenance})
    sources={}
    def source(name):
        path=ROOT/'synthetic_fixtures'/name;blob=path.read_bytes()
        sources[name]={'source_sha256':r01.digest(blob),'original_C':blob.decode('utf-8')}
        return blob.decode('utf-8')
    text=source('locator_returns.c')
    rs=returns(text)
    record('ignore_comment_returns','PASS','PASS' if len(rs)==2 and rs[0]['raw_return_expression']=='2' and rs[1]['contains_call_candidate'] else 'REJECT',rs)
    record('locator_no_semantic_promotion','UNKNOWN','UNKNOWN' if all(r['status']=='UNKNOWN' and r['type'] is None and not r['normal_return_verified'] for r in rs) else 'PASS',rs)
    text=source('locator_calls.c')
    cs=calls_to(text,'f')
    record('ignored_vs_received_candidates','PASS','PASS' if len(cs)==3 and cs[0]['result_disposition_candidate']=='ignored'
           and all(c['result_disposition_candidate']=='unverified_expression_use' for c in cs[1:]) else 'REJECT',cs)
    text=source('locator_utf8.c')
    rs=returns(text)
    record('utf8_byte_range','PASS','PASS' if text.encode()[rs[0]['return_source_range']['start']['byte_offset']:].startswith(b'return 2;') else 'REJECT',rs)
    record('literal_ignored_no_versions','PASS','PASS' if all(c['caller_result_version_id'] is None and c['binding_status']=='UNKNOWN' for c in cs) else 'REJECT',cs)
    result={'total':len(checks),'passed':sum(c['passed'] for c in checks),'all_passed':all(c['passed'] for c in checks),
            'tests':checks,'source_inputs':sources,'semantic_status_counts':counts(c['actual'] for c in checks),
            'structural_outcome_counts':{s:sum(c['actual']==s for c in checks) for s in
                 sorted({c['actual'] for c in checks if c['actual'] not in STATUSES})},
            'external_operations':offline_boundary.EVENTS}
    save(output/'test_results.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='tests'}))
    if not result['all_passed']:raise SystemExit(1)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);main(p.parse_args().output)
