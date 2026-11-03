from pathlib import Path
import hashlib,json,re
ROOT=Path(__file__).resolve().parent
COMMIT='9c5a72fbc90d829ffb761da64a73c23cd4e0503f'
SRC=ROOT/'sources'/COMMIT
DRV='drivers/media/dvb-frontends/stb0899_drv.c'
ALGO='drivers/media/dvb-frontends/stb0899_algo.c'
PRIV='drivers/media/dvb-frontends/stb0899_priv.h'
CORE='drivers/media/dvb-core/dvb_frontend.c'
def sha(b):return hashlib.sha256(b).hexdigest()
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(name,doc):
    with (ROOT/name).open('x',encoding='utf-8',newline='\n') as f:json.dump(doc,f,ensure_ascii=False,indent=2);f.write('\n')
def main():
    outputs=['source_manifest.json','source_evidence.json','side_effect_review.json','caller_path_contract.json','acquisition_issue_resolution.json']
    if any((ROOT/name).exists() for name in outputs):raise FileExistsError('Refuse to overwrite source certificates')
    files={};logs=[];issues=[]
    for log in sorted(ROOT.glob('acquisition_*.json')):
        doc=load(log);logs.append({'file':log.name,'sha256':sha(log.read_bytes()),'status':doc['status']})
        issues.extend(doc.get('failures',[]))
        for r in doc['sources']:
            if r['path'] in files:raise ValueError('Duplicate acquired source')
            blob=(ROOT/r['local_path']).read_bytes()
            if sha(blob)!=r['sha256'] or r['commit']!=COMMIT:raise ValueError('Acquired source integrity mismatch')
            if r['git_blob_sha1']!=hashlib.sha1(b'blob '+str(len(blob)).encode()+b'\0'+blob).hexdigest():raise ValueError('Git blob identity mismatch')
            files[r['path']]=r
    actual_files={p.relative_to(SRC).as_posix() for p in SRC.rglob('*') if p.is_file()}
    if actual_files!=set(files):raise ValueError('Source manifest coverage mismatch')
    facts=[]
    def fact(eid,path,lo,hi,claim):
        lines=(SRC/path).read_bytes().splitlines(keepends=True)
        if not 1<=lo<=hi<=len(lines):raise ValueError('Invalid source range')
        blob=b''.join(lines[lo-1:hi])
        item={'evidence_id':eid,'kind':'EXACT_SOURCE_SPAN_WITH_STATIC_REVIEW','path':path,'commit':COMMIT,'file_sha256':files[path]['sha256'],'start_line':lo,'end_line':hi,'span_sha256':sha(blob),'source_text':blob.decode('utf-8'),'claim':claim,'claim_validation':'STATIC_SOURCE_REVIEW; byte/line checks are deterministic, not an AST or machine-checked C proof'}
        facts.append(item);return eid
    fact('T_INPUT','include/media/dvb_frontend.h',592,605,'dtv_frontend_properties.symbol_rate is declared u32')
    fact('T_PARAMS',PRIV,144,148,'stb0899_params.srate is declared u32')
    fact('T_STATE',PRIV,197,212,'params and internal are distinct non-union subobjects; search_lock is only a declaration and is not used as synchronization evidence')
    fact('T_U32','include/asm-generic/int-ll64.h',16,24,'Generic kernel aliases include typedef __u32 u32; no original architecture/build is recovered')
    fact('T_UINT','include/uapi/asm-generic/int-ll64.h',20,30,'Generic ABI defines __u32 as unsigned int; experimental Linux ILP32/LP64 contracts use 32-bit int')
    fact('F_INPUT',DRV,1415,1427,'state=fe->demodulator_priv; i_params=&state->params; props=&fe->dtv_property_cache; i_params->srate=props->symbol_rate')
    fact('F_INRANGE',PRIV,38,39,'INRANGE is a closed interval in either endpoint order; here ordered constants reduce it to 1000000<=srate<=45000000')
    fact('F_BRANCH',DRV,1433,1484,'The DVB-S/DSS call to stb0899_dvbs_algo(state) is nested under the range guard; SYS_DVBS2 has a different branch')
    fact('F_CALLEE',ALGO,489,557,'Same by-value state pointer; params=&state->params; target receives params->srate at line557')
    fact('F_TARGET',ALGO,107,113,'Exact saved target body; signed-long guard and nested division; division at line110')
    fact('F_ATTACH',DRV,1612,1641,'Distinct kzalloc demod state; embedded frontend.demodulator_priv points to that state; GPL-exported attach admits out-of-tree configurations outside certification')
    fact('F_OPS',DRV,1566,1609,'Custom frontend algorithm and .search=stb0899_search; get_frontend and i2c_gate_ctrl bindings are explicit')
    fact('M_DELIVERY',DRV,1290,1388,'set_delivery manipulates local register images and device I/O, not params.srate')
    fact('M_CLOCK',DRV,539,569,'set_mclk updates internal.master_clk; it does not update params.srate')
    fact('M_GATE',DRV,1222,1246,'I2C gate uses demod register I/O and local values, not params.srate')
    fact('M_READ',DRV,213,265,'Register reads use local message buffers, not the cached parameter object')
    fact('M_WRITE',DRV,484,532,'Register writes copy into local buffers; no address of params.srate is supplied')
    fact('M_RATE',ALGO,66,99,'set_srate accepts the scalar by value, calculates locals and writes device registers; no cached-field assignment')
    fact('M_DIV',ALGO,15,21,'do_div operates on by-value local n')
    fact('M_MACRO',PRIV,54,63,'SETFIELD_VAL only assigns its supplied local mask/register lvalue in the reviewed prefix')
    fact('M_BW_WRAP','drivers/media/dvb-frontends/stb6100_cfg.h',51,87,'Bandwidth wrapper writes cache.bandwidth_hz and temporarily cache.frequency, then dispatches tuner_ops; never demod params.srate')
    fact('M_BW_REAL','drivers/media/dvb-frontends/stb6100.c',241,296,'STB6100 bandwidth operations write tuner-private bandwidth, output u32* and registers; msleep does not release frontend semaphore')
    fact('M_TUNER_OPS','drivers/media/dvb-frontends/stb6100.c',502,549,'set_params dispatches frequency/bandwidth from cache; attachment uses a separate allocation and installs stb6100_ops')
    fact('M_FREQ_REENTRY','drivers/media/dvb-frontends/stb6100.c',324,342,'Frequency callback may call get_frontend; it is skipped by bandwidth wrapper frequency=0 and would only touch property cache via the fixed binding')
    fact('M_GET_FE',DRV,1553,1564,'get_frontend writes output/cache symbol_rate and frequency from internal; it does not write params.srate')
    fact('M_TDA','drivers/media/dvb-frontends/tda8261_cfg.h',8,49,'TDA8261 bandwidth getter only writes *bandwidth=40000000; set_frequency/get_frequency occur after target and are separately recorded')
    fact('M_TDA_ATTACH','drivers/media/dvb-frontends/tda8261.c',151,194,'TDA8261 attachment allocates a distinct tuner-private state and installs its own tuner_ops')
    fact('S_THREAD',CORE,658,772,'Worker takes fepriv.sem at695 and calls ops.search at747 without an intervening release; iteration release is before lock at681')
    fact('S_IOCTL',CORE,2062,2115,'Native ioctl handler takes the same fepriv.sem at2071 and calls handle_ioctl at2100 before releasing at2102')
    fact('S_COMPAT',CORE,2236,2255,'Compat property ioctls acquire the same semaphore; other compat requests use the native path')
    fact('S_SET',CORE,1905,1930,'DTV_SYMBOL_RATE cache assignment occurs in the serialized setter')
    fact('S_INIT',CORE,3033,3043,'The frontend semaphore is initialized to count1')
    fact('S_START',CORE,856,892,'Single frontend worker is reused; startup takes the same semaphore before launching it')
    fact('S_EVENT',CORE,270,279,'Blocking event helper releases/reacquires semaphore only in its event path; it is not a callee of the reviewed search prefix')
    fact('S_REINIT',CORE,351,358,'Asynchronous reinitialise only sets a flag/wakes the worker; it does not execute search concurrently or assign cached srate')
    fact('S_CI','drivers/media/pci/ttpci/budget-av.c',201,227,'CI reset can request reinitialise; it does not rewrite demod private cached parameters')
    fact('S_USB','drivers/media/usb/dvb-usb/dvb-usb-dvb.c',276,325,'USB frontend core wraps init/sleep, not search/get_frontend/tuner_ops')
    fact('IO_MANTIS','drivers/media/pci/mantis/mantis_i2c.c',26,207,'Transport writes hardware and supplied message buffers; no demod private parameter pointer is used')
    fact('IO_SAA','drivers/media/common/saa7146/saa7146_i2c.c',28,109,'SAA7146 cleanup writes even write-message buffers, but these callers supply local arrays, not params.srate')
    fact('IO_SAA_XFER','drivers/media/common/saa7146/saa7146_i2c.c',291,419,'SAA7146 adapter dispatch, I/O lock and local transport state; no frontend search invocation')
    fact('IO_AZ','drivers/media/usb/dvb-usb/az6027.c',951,1070,'AZ6027 transfer changes USB/transport buffers and bounded caller-supplied message buffers')
    fact('IO_PCTV','drivers/media/usb/dvb-usb/pctv452e.c',414,515,'PCTV transfer changes transport sequence and message buffers, not demod private parameters')
    config_specs=[('drivers/media/pci/ttpci/budget-av.c','knc1_dvbs2_config',1100,1140,1274,1275,'TDA8261'),('drivers/media/pci/ttpci/budget-ci.c','tt3200_config',1256,1293,1421,1423,'STB6100'),('drivers/media/pci/mantis/mantis_vp1041.c','vp1041_stb0899_config',254,289,306,312,'STB6100'),('drivers/media/usb/dvb-usb/az6027.c','az6027_stb0899_config',254,289,911,915,'STB6100'),('drivers/media/usb/dvb-usb/pctv452e.c','stb0899_config',857,901,918,949,'STB6100')]
    configs=[]
    for i,(path,name,lo,hi,attach_lo,attach_hi,family) in enumerate(config_specs,1):
        lines=(SRC/path).read_text(encoding='utf-8').splitlines()
        block='\n'.join(lines[lo-1:hi])
        if not re.search(r'static\s+struct\s+stb0899_config\s+'+name+r'\s*=\s*\{',block):raise ValueError('Unexpected configuration declaration')
        callbacks=dict(re.findall(r'\.(tuner_(?:set|get)_\w+)\s*=\s*(\w+)',block))
        expected={'tuner_get_frequency':('tda8261' if family=='TDA8261' else 'stb6100')+'_get_frequency','tuner_set_frequency':('tda8261' if family=='TDA8261' else 'stb6100')+'_set_frequency','tuner_set_bandwidth':'NULL' if family=='TDA8261' else 'stb6100_set_bandwidth','tuner_get_bandwidth':('tda8261' if family=='TDA8261' else 'stb6100')+'_get_bandwidth','tuner_set_rfsiggain':'NULL'}
        if callbacks!=expected:raise ValueError('Unreviewed callback table')
        eid=fact('CFG_'+str(i),path,lo,hi,'Exact callback initializer table for '+name)
        aid=fact('ATTACH_'+str(i),path,attach_lo,attach_hi,'Board installs this STB0899 configuration and the indicated tuner family on the same frontend')
        if path.endswith('pctv452e.c'):
            fact('ATTACH_PCTV_TUNER',path,943,953,'Separate tuner_attach installs STB6100 on the same fe_adap[0].fe')
        configs.append({'configuration_id':COMMIT+':'+path+':'+name,'name':name,'path':path,'declaration_line':lo,'tuner_family':family,'callbacks':callbacks,'evidence_ids':[eid,aid],'intermediate_rfsiggain':'NOT_CALLED_NULL','status':'SCOPED_STATIC_REVIEW_COMPLETE'})
    drv=(SRC/DRV).read_text(encoding='utf-8');algo=(SRC/ALGO).read_text(encoding='utf-8')
    guards=list(re.finditer(r'if\s*\(INRANGE\(i_params->srate,\s*(\d+),\s*(\d+)\)\)\s*\{',drv))
    if len(guards)!=1:raise ValueError('Range guard ambiguous')
    lower,upper=map(int,guards[0].groups())
    if (lower,upper)!=(1000000,45000000):raise ValueError('Source constants changed')
    required={'state = fe->demodulator_priv','*i_params = &state->params','*props = &fe->dtv_property_cache','i_params->srate = props->symbol_rate','if (stb0899_dvbs_algo(state)'}
    if any(text not in drv for text in required):raise ValueError('Caller anchors missing')
    if algo.count('stb0899_calc_derot_time(params->srate)')!=1:raise ValueError('Target callsite ambiguous')
    manifest={'repository':'gregkh/linux','tag':'v6.9.6','commit':COMMIT,'tag_verification_file':'upstream_tag_verification.json','tag_verification_sha256':sha((ROOT/'upstream_tag_verification.json').read_bytes()),'tag_signature_verified':False,'acquisition_logs':logs,'source_count':len(files),'total_source_bytes':sum(r['bytes'] for r in files.values()),'sources':[dict(r,key_lines=sorted({n for f in facts if f['path']==r['path'] for n in (f['start_line'],f['end_line'])})) for r in sorted(files.values(),key=lambda r:r['path'])],'version_evidence':'Exact commit HTTPS URLs plus remote tag peeled commit; Git blob IDs are locally computed, not separately authenticated Merkle paths','original_TU_or_build_recovered':False,'generic_AST_proof_claimed':False}
    write('source_manifest.json',manifest)
    write('source_evidence.json',{'commit':COMMIT,'source_manifest_sha256':sha((ROOT/'source_manifest.json').read_bytes()),'evidence_method':'Finite source anchors and exact source spans plus explicit static review. No general C parser, AST, R05 execution or machine proof of noninterference.','range':{'lower':lower,'upper':upper,'closed':True,'source_evidence':'F_INRANGE','guard_evidence':'F_BRANCH','source_constants_extracted_from_guard':True},'facts':facts,'configurations':configs,'typed_object_relations':[{'from':'fe.demodulator_priv','to':'stb0899_state allocation','evidence_ids':['F_ATTACH','F_INPUT']},{'from':'i_params','to':'same_state.params','evidence_ids':['F_INPUT','T_STATE']},{'from':'stb0899_dvbs_algo.state','to':'caller state, by-value pointer argument','evidence_ids':['F_BRANCH','F_CALLEE']},{'from':'params','to':'same_state.params','evidence_ids':['F_CALLEE','T_STATE']},{'from':'tuner_priv','to':'distinct kzalloc tuner allocation','evidence_ids':['M_TUNER_OPS','M_TDA_ATTACH']} ]})
    review={'status':'SCOPED_SOURCE_REVIEW_COMPLETE','evidence_level':'STATIC_SOURCE_REVIEW_WITH_HASHED_SPANS','scope':'Only the five listed configuration initializers; live frontend; normal defined executions that reach the target in SYS_DVBS/SYS_DSS; experimental ILP32/LP64 contracts','not_a_claim':'Not compiled-TU certification, automatic alias/effect proof, exhaustive kernel race verification or full-program proof','configuration_ids':[c['configuration_id'] for c in configs],'reviews':[
     {'id':'P_PRIVATE_FIELD','result':'PRESERVES_PARAMS_SRATE','reason':'The only cached-field assignment in the reviewed STB0899 driver/algorithm is input copy at drv1426. internal.srate is a distinct field. No whole-object store or params address escape appears in the reviewed prefix. Callee anchors alone are not the proof; entire pinned helper bodies and field lvalues were reviewed.','evidence_ids':['F_INPUT','F_BRANCH','F_CALLEE','T_STATE','M_RATE','M_DIV','M_DELIVERY','M_CLOCK','M_GATE','M_READ','M_WRITE','M_MACRO']},
     {'id':'P_CALLBACKS','result':'PRESERVES_PARAMS_SRATE','reason':'All five gain callbacks are NULL. Four bandwidth callback pairs resolve through stb6100_cfg.h to a separately allocated tuner. Bandwidth setter changes cache bandwidth/frequency (temporarily zero), so set_params skips frequency tuning on this prefix. Getter output aliases internal.tuner_bw, not params.srate. TDA setter is NULL and getter writes only the bandwidth output. Frequency callbacks are after target in dvbs_algo; their cache writes must not be described as globally effect-free.','evidence_ids':['F_BRANCH','T_STATE','M_BW_WRAP','M_BW_REAL','M_TUNER_OPS','M_FREQ_REENTRY','M_GET_FE','M_TDA','M_TDA_ATTACH']+[c['evidence_ids'][0] for c in configs]},
     {'id':'P_TRANSPORT','result':'NO_PARAMS_POINTER_IN_REVIEWED_IO','reason':'I2C/USB/MMIO helpers update their transport state and provided local message buffers. SAA cleanup may write all message buffers, including writes, but the demod helpers copy through local arrays. No params.srate pointer is passed. Standard kernel buffer-I/O semantics and absence of preceding memory corruption are part of the declared execution model, not a numeric caller assumption.','evidence_ids':['M_READ','M_WRITE','M_RATE','IO_MANTIS','IO_SAA','IO_SAA_XFER','IO_AZ','IO_PCTV']},
     {'id':'P_SYNC','result':'SERIALIZED_RELEVANT_CORE_WRITERS','reason':'Worker holds the count-one frontend semaphore across ops.search. Native and compat property writers use the same semaphore. Sleep/I2C waits retain this frontend semaphore. Event helper unlocks only on a different ioctl event path. Asynchronous CI reinitialise sets a flag; actual initialization occurs in the worker under semaphore. search_lock is unused and supplies no evidence.','evidence_ids':['S_THREAD','S_IOCTL','S_COMPAT','S_SET','S_INIT','S_START','S_EVENT','S_REINIT','S_CI','S_USB','T_STATE']}
    ],'unresolved_modification_paths_within_declared_scope':[],'unverified_outside_scope':['out-of-tree configurations or replacement callbacks','unknown modules or direct unsynchronized callers','lifetime violations or unrelated memory corruption','all hardware faults or all kernel races','original build configuration and actual ABI','repository-wide exhaustive reference scan beyond the five requested configuration sources'],'no_intervening_write_relation':'params_srate_at_target == params_srate_at_range_guard; source-review-derived summary, not encoded memory model','automatic_analysis_only_certification':False,'filter_authority':False,'full_program_semantics':'UNKNOWN'}
    write('side_effect_review.json',review)
    contract={'contract_version':'e10-attempt02-in-tree-caller-scalar-v1','sample_id':'DBZ/all_cwe369.json:row=4:index=4','original_index':4,'original_label':0,'function_body_sha256':load(ROOT/'input_verification.json')['formal_body_sha256'],'source_commit':COMMIT,'source_manifest_sha256':sha((ROOT/'source_manifest.json').read_bytes()),'source_evidence_sha256':sha((ROOT/'source_evidence.json').read_bytes()),'side_effect_review_sha256':sha((ROOT/'side_effect_review.json').read_bytes()),'input_verification_sha256':sha((ROOT/'input_verification.json').read_bytes()),'upstream_body_verification_sha256':sha((ROOT/'upstream_body_verification.json').read_bytes()),'E09_helper_sha256':'26abb4313e62ffa7d31049fd7330bd636d6aa2fdfd52f39e5f096888b478d105','certification_level':'SCOPED_STATIC_SOURCE_REVIEW','configuration_ids':[c['configuration_id'] for c in configs],'input_type':{'C':'u32','SMT':'BitVec(32)','signed':False},'field_type':{'C':'u32','SMT':'BitVec(32)','signed':False},'ABI_contracts':[{'signed_long_bits':32,'int_bits':32,'status':'EXPLICIT_EXPERIMENTAL_LINUX_ILP32_SCALAR_CONTRACT'},{'signed_long_bits':64,'int_bits':32,'status':'EXPLICIT_EXPERIMENTAL_LINUX_LP64_SCALAR_CONTRACT'}],'range':{'lower':lower,'upper':upper,'comparison':'UNSIGNED','closed':True,'source_evidence_ids':['F_INRANGE','F_BRANCH'],'human_added_numeric_assumption':False},'macro_expansion':'(((1000000 <= val) && (val <= 45000000)) || ((45000000 <= val) && (val <= 1000000)) ? 1 : 0)','macro_simplification':'Distinct ordered endpoints make reversed conjunct impossible for one stable u32 value; remaining comparisons are inclusive unsigned comparisons under both explicit int32 contracts.','assignment':'assigned_u32 == input_symbol_rate_u32','guard_read':'guard_u32 == assigned_u32','preservation':'target_read_u32 == guard_u32','preservation_basis':['P_PRIVATE_FIELD','P_CALLBACKS','P_TRANSPORT','P_SYNC'],'conversion':{'32':'Same bit pattern only within source-derived range, whose upper bound is below LONG_MAX; no out-of-range u32-to-long32 behavior is modeled','64':'ZeroExt(32,target_read_u32), value-preserving conversion from u32 to signed long64','actual_original_ABI':'UNKNOWN'},'delivery_path':'Only SYS_DVBS or SYS_DSS selected under outer range guard; no enum numeric values invented','target_guard':'signed_long_srate > 0','division':{'semantics':'toward_zero','SMT':'bvsdiv','inner_denominator':1000,'outer_numerator':100000,'definedness':'denominator != 0 and not (numerator == LONG_MIN and denominator == -1)','fault_query':'range and assignment/preservation/conversion and target_guard and inner_defined and inner_quotient == 0','outer_definedness_asserted':False},'execution_model':['Only normally executing, live frontend paths reaching the target; other prefix arithmetic faults are not certified','Kernel primitives follow their documented scalar, allocation, buffer-I/O and semaphore semantics; hardware/arbitrary memory corruption not modeled','Five source-pinned in-tree configurations only; callback replacement/out-of-tree is UNKNOWN'],'evidence_limitations':['No original kernel build or TU AST reconstructed','Static source review supplies the field-preservation summary; SMT verifies only scalar implication','No general C parser, pointer/memory/concurrency encoding or R05 integration','No independently checked UNSAT certificate'], 'original_alert_decision':None,'filter_authority':False,'full_program_semantics':'UNKNOWN'}
    write('caller_path_contract.json',contract)
    write('acquisition_issue_resolution.json',{'historical_acquisition_issues':issues,'resolution':[{'issue':'Three Kconfig requests rejected by helper extension gate','resolution':'Fetched exact same fixed-commit metadata with separately recorded acquisition_build_metadata.json; helper and rejected batch remain immutable'},{'issue':'stb0899.h request returned 404','resolution':'Actual #include in source is stb0899_drv.h; correct necessary header fetched at same commit; no source/version mismatch was bypassed'}],'unresolved_required_source_fetches':[],'solver_runs_during_acquisition':0})
    print(json.dumps({'source_files':len(files),'source_bytes':manifest['total_source_bytes'],'source_facts':len(facts),'configurations':len(configs),'range':[lower,upper],'review':review['status'],'contract_sha256':sha((ROOT/'caller_path_contract.json').read_bytes())}))
if __name__=='__main__':main()
