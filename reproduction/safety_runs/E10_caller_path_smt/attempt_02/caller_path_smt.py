"""Finite E10 caller-path scalar model; source review is separate from SMT proof."""
from __future__ import annotations
from pathlib import Path
import copy, hashlib, importlib.metadata, importlib.util, json, sys, time
import z3
ROOT=Path(__file__).resolve().parent
REPRO=ROOT.parents[2]
COMMIT='9c5a72fbc90d829ffb761da64a73c23cd4e0503f'
CONTRACT_SHA256='8deb27b5f3f967869d19e8e42e36debd4a58975d45b7a028646cada9f3668ee0'
BODY_SHA256='4ad8431edd6f874dcfb6b1c47d3d83607e7c3ce11f9521e45496eff794a5f9f6'
CHECK_COUNT=0
class IntegrityError(ValueError):pass
class UnsupportedSemantics(ValueError):pass
class EvidenceUnknown(RuntimeError):pass
class SemanticMismatch(RuntimeError):pass
def sha(blob):return hashlib.sha256(blob).hexdigest()
def load(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def write_new(path,doc):
    with Path(path).open('x',encoding='utf-8',newline='\n') as f:
        if isinstance(doc,str):f.write(doc)
        else:json.dump(doc,f,ensure_ascii=False,indent=2);f.write('\n')
def ensure(condition,message):
    if not condition:raise IntegrityError(message)
def import_e09(expected_hash):
    path=REPRO/'safety_runs/E09_scalar_smt/scalar_smt.py'
    ensure(sha(path.read_bytes())==expected_hash,'E09 helper bytes changed')
    name='e09_scalar_helpers_read_only_e10'
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module

def scope_status(review,configuration_id=None,delivery_system='SYS_DVBS'):
    if review.get('status')!='SCOPED_SOURCE_REVIEW_COMPLETE':return 'UNKNOWN'
    if review.get('unresolved_modification_paths_within_declared_scope'):return 'UNKNOWN'
    if configuration_id is not None and configuration_id not in review.get('configuration_ids',[]):return 'UNKNOWN'
    if delivery_system not in ('SYS_DVBS','SYS_DSS'):return 'NOT_THIS_CALL_PATH'
    expected={'P_PRIVATE_FIELD':'PRESERVES_PARAMS_SRATE','P_CALLBACKS':'PRESERVES_PARAMS_SRATE','P_TRANSPORT':'NO_PARAMS_POINTER_IN_REVIEWED_IO','P_SYNC':'SERIALIZED_RELEVANT_CORE_WRITERS'}
    if {r.get('id'):r.get('result') for r in review.get('reviews',[])}!=expected:return 'UNKNOWN'
    return 'SCOPED_SOURCE_REVIEW_ADMITTED'

def load_materials():
    contract_path=ROOT/'caller_path_contract.json'
    ensure(sha(contract_path.read_bytes())==CONTRACT_SHA256,'Frozen E10 contract changed')
    c=load(contract_path)
    checks={'source_manifest.json':'source_manifest_sha256','source_evidence.json':'source_evidence_sha256','side_effect_review.json':'side_effect_review_sha256','input_verification.json':'input_verification_sha256','upstream_body_verification.json':'upstream_body_verification_sha256'}
    for filename,key in checks.items():ensure(sha((ROOT/filename).read_bytes())==c[key],filename+' changed')
    manifest=load(ROOT/'source_manifest.json');evidence=load(ROOT/'source_evidence.json');review=load(ROOT/'side_effect_review.json')
    ensure(manifest['commit']==COMMIT==c['source_commit'],'Commit mismatch')
    tagpath=ROOT/manifest['tag_verification_file']
    ensure(sha(tagpath.read_bytes())==manifest['tag_verification_sha256'],'Tag receipt changed')
    tag=load(tagpath);ensure(tag['observed_peeled_commit']==COMMIT and tag['status']=='MATCH','Tag/commit mismatch')
    sources={}
    for item in manifest['sources']:
        blob=(ROOT/item['local_path']).read_bytes()
        ensure(sha(blob)==item['sha256'],'Source SHA mismatch: '+item['path'])
        ensure(item['commit']==COMMIT and item['final_URL'].startswith('https://raw.githubusercontent.com/gregkh/linux/'+COMMIT+'/'),'Source version URL mismatch')
        sources[item['path']]=blob
    ensure(len(sources)==29,'Source coverage changed')
    ensure(sha((ROOT/'source_manifest.json').read_bytes())==evidence['source_manifest_sha256'],'Evidence manifest mismatch')
    for fact in evidence['facts']:
        data=sources[fact['path']];lines=data.splitlines(keepends=True)
        ensure(1<=fact['start_line']<=fact['end_line']<=len(lines),'Invalid fact range')
        span=b''.join(lines[fact['start_line']-1:fact['end_line']])
        ensure(sha(data)==fact['file_sha256'] and sha(span)==fact['span_sha256'] and span.decode('utf-8')==fact['source_text'],'Evidence source span mismatch')
    raw=(REPRO/'upstream/benchmark/DBZ/all_cwe369.json').read_bytes();record=json.loads(raw)[4]
    ensure(record['index']==4 and record['result']==0 and len(record['function_call'])==1,'Original identity/label changed')
    body=record['function_call'][0]
    old_contract=load(REPRO/'safety_runs/E09_scalar_smt/semantic_contract.json')
    old_results=load(REPRO/'safety_runs/E09_scalar_smt/experiment_results.json')
    ensure(sha(body.encode('utf-8'))==BODY_SHA256==old_contract['source_body_sha256']==old_results['source']['function_body_sha256'],'Three-way function-body hash mismatch')
    ensure(sha(raw)==old_contract['dataset_sha256']==old_results['source']['dataset_sha256'],'Original dataset SHA mismatch')
    upstream=sources['drivers/media/dvb-frontends/stb0899_algo.c']
    start=upstream.index(b'static long stb0899_calc_derot_time(long srate)');end=upstream.index(b'\n}',start)+2
    ensure(upstream[start:end]==body.encode('utf-8') and upstream[:start].count(b'\n')+1==107 and record['location']['region']['startLine']==110,'Upstream body/location mismatch')
    ensure(c['range']=={'lower':1000000,'upper':45000000,'comparison':'UNSIGNED','closed':True,'source_evidence_ids':['F_INRANGE','F_BRANCH'],'human_added_numeric_assumption':False},'Unreviewed range contract')
    ensure(evidence['range']['lower']==c['range']['lower'] and evidence['range']['upper']==c['range']['upper'],'Source-derived constants mismatch')
    ensure(scope_status(review)=='SCOPED_SOURCE_REVIEW_ADMITTED','Unresolved effect or synchronization evidence')
    ensure(len(c['configuration_ids'])==len(evidence['configurations'])==5 and c['configuration_ids']==review['configuration_ids'],'Configuration coverage mismatch')
    helper=import_e09(c['E09_helper_sha256'])
    parsed=helper.parse_fragment(body)
    return {'contract':c,'manifest':manifest,'evidence':evidence,'review':review,'source_record':record,'helper':helper,'parsed':parsed,'E09_results':old_results}

def validate_width(width,input_type='u32',division='toward_zero'):
    if type(width) is not int or width not in (32,64) or input_type!='u32' or division!='toward_zero':
        raise UnsupportedSemantics('Only u32 input and explicit signed-long32/64 toward-zero contracts')

def encode(materials,width,*,input_type='u32',division='toward_zero',configuration_id=None,delivery_system='SYS_DVBS'):
    validate_width(width,input_type,division)
    if scope_status(materials['review'],configuration_id,delivery_system)!='SCOPED_SOURCE_REVIEW_ADMITTED':
        raise EvidenceUnknown('No caller-range transfer for this scope or unreviewed effects')
    lower=materials['contract']['range']['lower'];upper=materials['contract']['range']['upper']
    if not 0<lower<=upper<=(1<<(width-1))-1:raise UnsupportedSemantics('u32-to-long conversion not value-preserving on this range')
    names=['input_symbol_rate','assigned_params_srate','guard_params_srate','target_params_srate']
    u={n:z3.BitVec('e10_'+n+'_u32',32) for n in names}
    x=z3.BitVec('e10_target_srate_signed_long_'+str(width),width)
    selected=z3.Bool('e10_SYS_DVBS_or_SYS_DSS_branch')
    converted=u['target_params_srate'] if width==32 else z3.ZeroExt(32,u['target_params_srate'])
    v=lambda n:z3.BitVecVal(n,width)
    inner,inner_defined=materials['helper'].signed_division(x,v(1000),width)
    outer,outer_defined=materials['helper'].signed_division(v(100000),inner,width)
    ranged=z3.And(z3.UGE(u['guard_params_srate'],z3.BitVecVal(lower,32)),z3.ULE(u['guard_params_srate'],z3.BitVecVal(upper,32)))
    relationships=[('input_assignment',u['assigned_params_srate']==u['input_symbol_rate'],['F_INPUT']),('guard_read',u['guard_params_srate']==u['assigned_params_srate'],['F_INPUT','F_BRANCH']),('real_caller_unsigned_range',ranged,['F_INRANGE','F_BRANCH']),('preserved_field_until_target',u['target_params_srate']==u['guard_params_srate'],['P_PRIVATE_FIELD','P_CALLBACKS','P_TRANSPORT','P_SYNC']),('argument_u32_to_long',x==converted,['F_CALLEE','T_INPUT','T_PARAMS']),('selected_delivery_branch',selected,['F_BRANCH']),('target_original_signed_guard',x>v(0),['F_TARGET']),('inner_division_definedness',inner_defined,['F_TARGET'])]
    return {'width':width,'u32_variables':u,'signed_long':x,'selected_delivery':selected,'relationships':relationships,'constraints':[formula for _,formula,_ in relationships],'fault':inner==v(0),'inner':inner,'inner_defined':inner_defined,'outer':outer,'outer_defined':outer_defined,'unsigned_range':ranged,'lower':lower,'upper':upper,'c_type':'signed long','division':'toward_zero'}

def u32_to_long_reference(value,width):
    validate_width(width)
    if type(value) is not int or not 0<=value<1<<32:raise UnsupportedSemantics('Not a u32 value')
    if value>(1<<(width-1))-1:raise UnsupportedSemantics('Out-of-range signed conversion is not certified')
    return value

def reference_path(materials,value,width,delivery_system='SYS_DVBS'):
    validate_width(width)
    if type(value) is not int or not 0<=value<1<<32:raise UnsupportedSemantics('Input is not u32')
    lo=materials['contract']['range']['lower'];hi=materials['contract']['range']['upper']
    in_range=lo<=value<=hi
    selected=delivery_system in ('SYS_DVBS','SYS_DSS')
    reached=in_range and selected
    local=None
    # This independent hypothetical local result is never described as a call
    # that happened when the caller rejects the input.
    if value<=(1<<(width-1))-1:
        local=materials['helper'].reference_execution(u32_to_long_reference(value,width),width,materials['parsed'])
    return {'input_symbol_rate_u32':value,'long_bits':width,'delivery_system':delivery_system,'caller_range_passed':in_range,'target_call_reached':reached,'actual_target_result':local if reached else None,'counterfactual_local_result':local,'counterfactual_label':'Local arithmetic only; not an executed call when target_call_reached=false'}

def independent_interval_check(materials,width):
    validate_width(width)
    lo=materials['contract']['range']['lower'];hi=materials['contract']['range']['upper'];div=materials['helper'].c_signed_divide
    left=u32_to_long_reference(lo,width);right=u32_to_long_reference(hi,width)
    qlo=div(left,1000,width);qhi=div(right,1000,width)
    ok=0<left<=right and qlo>=1 and qhi>=qlo
    return {'status':'MATCH_NONZERO_DENOMINATOR' if ok else 'MISMATCH','input_interval_u32':[lo,hi],'signed_long_interval':[left,right],'inner_quotient_interval':[qlo,qhi],'outer_return_interval':[div(100000,qhi,width),div(100000,qlo,width)] if ok else None,'argument':'For a positive ordered interval and fixed positive divisor1000, C toward-zero quotient is monotone; its minimum here is1000. All conversions are representable. No member has denominator zero.','method':'Independent Python exact integer arithmetic plus stated monotonicity argument','z3_used':False,'exhaustive_enumeration':False,'independent_solver_proof_certificate':False}

def run_query(materials,width):
    global CHECK_COUNT
    enc=encode(materials,width)
    solver=z3.SolverFor('QF_BV');solver.set(timeout=30000)
    solver.add(*enc['constraints'],enc['fault'])
    formula=solver.to_smt2()
    write_new(ROOT/('query_'+str(width)+'.smt2'),formula)
    CHECK_COUNT+=1
    start=time.perf_counter();answer=solver.check();elapsed=time.perf_counter()-start
    status={'sat':'SAT','unsat':'UNSAT','unknown':'UNKNOWN'}[str(answer)]
    doc={'width_bits':width,'ABI_assumption':materials['contract']['ABI_contracts'][0 if width==32 else 1],'status':status,'logic':'QF_BV','timeout_ms':30000,'check_seconds':elapsed,'formula_smt2':formula,'formula_file':'query_'+str(width)+'.smt2','asserted_constraints':[{'name':name,'SMT':pred.sexpr(),'source_evidence_ids':ids,'human_added_numeric_assumption':False} for name,pred,ids in enc['relationships']],'fault_SMT':enc['fault'].sexpr(),'outer_definedness_SMT':enc['outer_defined'].sexpr(),'outer_definedness_asserted_in_fault_query':False,'outer_undefined_term_consumed_as_C_result':False,'model':None,'independent_model_check':None,'independent_interval_check':independent_interval_check(materials,width),'unsat_proof':{'certificate_requested':False,'certificate_independently_checked':False,'status':'SOLVER_REPORTED_UNSAT_NO_CERTIFICATE' if status=='UNSAT' else 'NOT_APPLICABLE'},'certification_scope':'The five pinned in-tree source configurations, normal executions reaching the target; field retention supplied by static source review, not solved by Z3','caller_path_property':'SCOPED_SOURCE_REVIEW_AND_SCALAR_UNSAT' if status=='UNSAT' else 'UNKNOWN','original_alert_decision':None,'filter_authority':False,'full_program_semantics':'UNKNOWN'}
    if status=='SAT':
        model=solver.model();vals={n:model.eval(v,model_completion=True).as_long() for n,v in enc['u32_variables'].items()};vals['signed_long_srate']=model.eval(enc['signed_long'],model_completion=True).as_signed_long();vals['inner_quotient']=model.eval(enc['inner'],model_completion=True).as_signed_long()
        doc['model']={'values':vals,'SMT':model.sexpr()}
        ref=reference_path(materials,vals['input_symbol_rate'],width)
        local=ref['actual_target_result'];ok=bool(local and local['outer_denominator_zero'] and local['inner']==vals['inner_quotient'] and len({vals[n] for n in enc['u32_variables']})==1)
        doc['independent_model_check']={'status':'MATCH' if ok else 'MISMATCH','reference':ref}
    elif status=='UNKNOWN':doc['reason_unknown']=solver.reason_unknown()
    write_new(ROOT/('query_'+str(width)+'.json'),doc)
    if status=='SAT' and doc['independent_model_check']['status']!='MATCH':raise SemanticMismatch('SAT model disagrees with independent C calculation')
    if doc['independent_interval_check']['status']!='MATCH_NONZERO_DENOMINATOR':raise SemanticMismatch('Independent range arithmetic failed')
    return doc

def main():
    if any((ROOT/n).exists() for n in ['experiment_results.json','query_32.smt2','query_32.json','query_64.smt2','query_64.json']):raise FileExistsError('Results already exist; no overwrite or implicit rerun')
    try:
        materials=load_materials();runs=[]
        for width in (32,64):
            result=run_query(materials,width);runs.append(result)
            if result['status']!='UNSAT':break
        success=len(runs)==2 and all(r['status']=='UNSAT' for r in runs)
        old=materials['E09_results']
        doc={'phase':'E10','attempt':2,'sample_id':materials['contract']['sample_id'],'original_index':4,'original_label':0,'source_commit':COMMIT,'source_body_sha256':BODY_SHA256,'contract_sha256':CONTRACT_SHA256,'implementation_sha256':sha(Path(__file__).read_bytes()),'source_manifest_sha256':materials['contract']['source_manifest_sha256'],'side_effect_review_sha256':materials['contract']['side_effect_review_sha256'],'solver_version':z3.get_full_version(),'solver_package_version':importlib.metadata.version('z3-solver'),'solver_check_calls':CHECK_COUNT,'runs':runs,'research_status':'SCOPED_CALLER_SCALAR_PROPERTY_CONFIRMED' if success else 'UNKNOWN','both_contracts_agree':len(runs)==2 and runs[0]['status']==runs[1]['status'],'source_review_vs_solver':'Source/hash/alias/callback/semaphore review supplies the retention relation. SMT only checks the resulting typed scalar implication.','E09_control_reference':{'file':'reproduction/safety_runs/E09_scalar_smt/experiment_results.json','sha256':sha((REPRO/'safety_runs/E09_scalar_smt/experiment_results.json').read_bytes()),'rerun':False,'local_A':[{'width':r['width_bits'],'status':r['status'],'model':r['model']} for r in old['runs'] if r['experiment']=='A'],'B_remains_human_hypothesis_not_used':True},'unsupported_scope_status':'Out-of-tree callbacks, unresolved writes/synchronization, unreviewed type/width/operation are UNKNOWN or rejected before solving','original_alert_decision':None,'filter_authority':False,'full_program_semantics':'UNKNOWN','LLM_calls':0,'Harness_calls':0,'old_regression_runs':0}
        write_new(ROOT/'experiment_results.json',doc)
        print(json.dumps({'research_status':doc['research_status'],'queries':[(r['width_bits'],r['status']) for r in runs],'solver_check_calls':CHECK_COUNT,'filter_authority':False}))
        if not success:raise SystemExit(2)
    except Exception as exc:
        write_new(ROOT/'solver_failure.json',{'stage':'E10_SCALAR_EXECUTION','type':type(exc).__name__,'message':str(exc),'solver_checks_started':CHECK_COUNT,'status':'STOPPED','query_records_preserved':True,'filter_authority':False})
        raise
if __name__=='__main__':main()
