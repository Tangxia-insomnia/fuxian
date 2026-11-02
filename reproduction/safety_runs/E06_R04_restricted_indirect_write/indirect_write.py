"""Bounded direct &local -> *formal=literal -> caller value/memory evidence."""
import copy
import re
import time
from r03_adapter import (r01,r02,r03_api,ReturnTrace,StateEnvironment,namespace,typed,counts,
                         create_context,verify_isolation,direct_reference,snapshot,invalidate_memory)
from memory_object import MemoryStore
from pointer_target import address_evidence,pointer_record


class EffectTrace(ReturnTrace):
    def __init__(self,fn,blob,ns,context,address):
        super().__init__(fn,blob,ns,role='callee',context=context)
        self.address=address;self.writes=[];self.escape_events=[];self.pointer_targets=[]
        self.parameter=list(fn.get_arguments())[0];self.entry=None
        self.write_inventory=[]

    def escape(self,node,reason):
        self.escape_events.append({'escape_event_id':r01.stable_id('escape',[self.ns,r01.span(node),reason]),
            'source_location':r01.span(node),'original_expression':r01.raw(node,self.blob),
            'reason':reason,'status':'UNKNOWN','call_context_id':self.context['call_context_id']})

    def statement(self,node,path):
        kind=node.kind.name
        if kind=='DECL_STMT':
            self.escape(node,'local_declaration_or_pointer_copy_unsupported')
            self.barrier(node,path,'callee_local_declarations_unsupported');return [path]
        if kind=='CALL_EXPR':
            self.escape(node,'pointer_transfer_or_unknown_function_call')
            self.barrier(node,path,'callee_calls_unsupported');return [path]
        if kind=='RETURN_STMT' and list(node.get_children()):
            self.escape(node,'return_value_or_pointer_escape_unsupported')
            self.barrier(node,path,'nonvoid_return_unsupported');return [path]
        if kind=='UNARY_OPERATOR' and any(t.spelling in {'++','--','&'} for t in node.get_tokens()):
            self.escape(node,'pointer_arithmetic_or_address_escape_unsupported')
            self.barrier(node,path,'pointer_arithmetic_or_address_escape_unsupported');return [path]
        if kind=='BINARY_OPERATOR' and self.operator(node)=='=':
            lhs,rhs=list(node.get_children());leaf=r02.unwrap(lhs)
            if leaf.kind.name=='UNARY_OPERATOR':
                return self.store(node,leaf,rhs,path)
            decl=leaf.referenced if leaf.kind.name=='DECL_REF_EXPR' else None
            right=r02.unwrap(rhs)
            if (decl is not None and decl==self.parameter and right.kind.name=='INTEGER_LITERAL'
                and r01.raw(right,self.blob)=='0'):
                self.assign(decl,node,rhs,path)
                return [path]
            self.escape(node,'pointer_rebinding_copy_global_or_other_write_unsupported')
            self.barrier(node,path,'unsupported_non_indirect_assignment');return [path]
        # Restrict reads to no-effect local operations accepted by R02. Its barriers
        # handle pointer arithmetic, casts, address escape and unsupported mutation.
        return super().statement(node,path)

    def store(self,node,lhs,rhs,path):
        children=list(lhs.get_children());toks=[t.spelling for t in lhs.get_tokens() if t.kind!=r01.c.TokenKind.COMMENT]
        operand=r02.unwrap(children[0]) if len(children)==1 else None
        valid_pointer=bool(toks and toks[0]=='*' and operand is not None
                           and operand.kind.name=='DECL_REF_EXPR' and operand.referenced==self.parameter)
        current=path.current.get(self.entry['slot_id']) if self.entry else None
        rd=self.read(operand,path,'indirect_write_pointer') if valid_pointer else None
        literal=r02.unwrap(rhs)
        actual=typed(literal.type,self.ns);target=typed(lhs.type,self.ns)
        conversion=r01.conversion(actual,target,typed(rhs.type,self.ns))
        why=[]
        if not valid_pointer:why.append('write_not_through_original_pointer_parameter')
        if not self.entry or current!=self.entry['value_version_id']:why.append('current_pointer_target_not_proven_after_rebinding')
        if self.writes:why.append('multiple_indirect_writes_unsupported')
        if literal.kind.name not in {'INTEGER_LITERAL','FLOATING_LITERAL'}:why.append('write_rhs_not_simple_typed_literal')
        if conversion['status']!='PASS':why.append('unsupported_write_value_conversion')
        if rd is None or rd['status']!='PASS':why.append('pointer_read_not_verified')
        event=self.event(node,path,'indirect_store')
        record={'indirect_write_id':r01.stable_id('indirect-write',[self.ns,event['event_id']]),
            'caller_pre_version':self.address['caller_pre_version'],'target_memory_object_id':self.address['target_memory_object_id'] if valid_pointer and self.entry and current==self.entry['value_version_id'] else None,
            'pointer_parameter_identity':r01.declaration(self.parameter,self.ns),
            'pointer_slot_id':self.entry['slot_id'] if self.entry else None,
            'pointer_entry_version':self.entry['value_version_id'] if self.entry else None,
            'pointer_current_version':current if valid_pointer else None,'indirect_write_location':r01.span(node),
            'original_expression':r01.raw(node,self.blob),'write_event_id':event['event_id'],
            'assigned_value':{'raw_literal':r01.raw(literal,self.blob),'source_type':actual,
                              'source_location':r01.span(literal),'evaluated_as_mathematical_integer':False},
            'assigned_value_type':target,'type_compatibility':conversion,'callee_body_sha256':self.body_hash,
            'call_context_id':self.context['call_context_id'],'callee_path_id':path.path_id,
            'caller_post_version':None,'caller_post_memory_version':None,'effect_coverage':'UNKNOWN',
            'source_evidence':{'source_sha256':self.ns['source_sha256'],'address_evidence_id':self.address['address_evidence_id']},
            'status':'UNKNOWN' if why else 'PASS','reasons':why}
        self.writes.append(record)
        if why:self.barrier(node,path,why[0])
        return [path]

    def run(self):
        path=StateEnvironment(r01.stable_id('r04-callee-path',[self.ns,self.function]))
        body=next(n for n in self.fn.get_children() if n.kind.name=='COMPOUND_STMT')
        nodes=list(self.fn.walk_preorder())
        self.write_inventory=[{'source_location':r01.span(n),'original_expression':r01.raw(n,self.blob),
                               'status':'UNKNOWN','method':'trusted_AST_write_syntax_not_effect_approval'}
            for n in nodes if n.kind.name in {'BINARY_OPERATOR','COMPOUND_ASSIGNMENT_OPERATOR'}
            and (n.kind.name=='COMPOUND_ASSIGNMENT_OPERATOR' or self.operator(n)=='=')
            and list(n.get_children()) and r02.unwrap(list(n.get_children())[0]).kind.name in {'UNARY_OPERATOR','ARRAY_SUBSCRIPT_EXPR','MEMBER_REF_EXPR'}]
        self.entry=self.version(self.parameter,self.parameter,path,'pointer_parameter_entry',{
            'kind':'address_argument_transfer','target_memory_object_id':self.address['target_memory_object_id'],
            'address_evidence_id':self.address['address_evidence_id'],
            'argument_transfer_id':self.context['parameter_mapping_records'][0]['argument_transfer_id']})
        pointer=pointer_record(self.context,self.address,self.entry,self.parameter,self.ns);self.pointer_targets.append(pointer)
        self.context['callee_entry_bindings'].append({'argument_transfer_id':self.context['parameter_mapping_records'][0]['argument_transfer_id'],
            'callee_entry_version':self.entry['value_version_id'],'callee_slot_id':self.entry['slot_id'],
            'target_memory_object_id':self.address['target_memory_object_id'],'address_evidence_id':self.address['address_evidence_id'],
            'status':'PASS','entry_kind':'address_not_scalar_value_equality'})
        pre=r03_api.preflight(self.fn)
        if any(n.kind.name=='IF_STMT' for n in nodes):pre.append('callee_branches_unsupported')
        if any(n.kind.name not in {'TYPE_REF'} for n in self.parameter.get_children()):pre.append('parameter_declarator_effects_unsupported')
        # Non-void is rejected while scanning return syntax for explicit escape evidence.
        if self.fn.result_type.kind.name!='VOID':pre.append('nonvoid_callee_unsupported')
        if pre:
            for n in nodes:
                if n.kind.name=='RETURN_STMT' and list(n.get_children()):self.escape(n,'return_value_or_pointer_escape_unsupported')
            self.barrier(self.fn,path,pre[0]);self.reasons.extend(pre[1:])
        paths=self.compound(body,[path])
        for p in paths:
            if p.termination is None:self.return_statement(body,p,implicit=True)
        complete=all(p.termination=='RETURN' for p in paths) and not self.reasons and all(w['status']=='PASS' for w in self.writes)
        return {'function':self.function,'body_sha256':self.body_hash,'call_context_id':self.context['call_context_id'],
            'status':'PASS' if complete else 'UNKNOWN','reasons':list(dict.fromkeys(self.reasons)),
            'slots':list(self.slots.values()),'versions':self.versions,'reads':self.reads,'events':self.events,
            'pointer_targets':self.pointer_targets,'indirect_writes':self.writes,'write_syntax_inventory':self.write_inventory,
            'escape_events':self.escape_events,'escape_coverage':'PASS' if complete else 'UNKNOWN',
            'effect_coverage':'PASS' if complete else 'UNKNOWN','normal_return_status':'PASS' if complete else 'UNKNOWN',
            'path_returns':self.path_returns,'final_environments':[p.snapshot() for p in paths],
            'unprocessed_ranges':self.blocked_ranges,'summary_cache_used':False}


class CallerTrace(ReturnTrace):
    def __init__(self,fn,blob,ns,reference):
        super().__init__(fn,blob,ns,role='caller')
        self.reference=reference;self.memory=MemoryStore();self.addresses=[];self.contexts=[];self.callees=[];self.transfers=[]
        self.attempts=[]

    def barrier(self,node,path,reason):
        before=snapshot(path)
        super().barrier(node,path,reason);invalidate_memory(path)
        self.events[-1]['before']=before;self.events[-1]['after']=snapshot(path)

    def version(self,decl,node,path,kind,value,*args,**kwargs):
        rec=super().version(decl,node,path,kind,value,*args,**kwargs)
        oid=self.memory.by_slot.get(rec['slot_id'])
        if oid:
            self.memory.version(self.memory.objects[oid],path,rec,
                kind='indirect_call_write' if kind=='indirect_call_receive' else 'caller_local_assignment',
                write_event=value.get('write_event_id',rec['definition_event_id']),
                source_location=value.get('write_location'),body_sha=value.get('callee_body_sha256'),
                context=value.get('call_context_id'),value_type=value.get('assigned_value_type'))
        return rec

    def statement(self,node,path):
        if node.kind.name=='CALL_EXPR':return self.invoke(node,path)
        return super().statement(node,path)

    def compound(self,body,paths):
        results=super().compound(body,paths)
        # Preserve the version ledger while dropping lexical objects from the
        # active memory environment when R02 drops their local slots.
        for path in results:
            for oid in list(getattr(path,'memory_current',{})):
                if self.memory.objects[oid]['caller_slot_id'] not in path.current:
                    path.memory_current.pop(oid)
        return results

    def invoke(self,node,path):
        args=list(node.get_arguments());matches=[c for c in self.reference['calls'] if c['callsite']==r01.span(node)]
        attempt={'callsite':r01.span(node),'original_expression':r01.raw(node,self.blob),'caller_path_id':path.path_id,
            'status':'UNKNOWN','reasons':[],'address_status':'UNKNOWN','pointer_entry_status':'UNKNOWN',
            'unique_target_status':'UNKNOWN','caller_new_version_status':'UNKNOWN'};self.attempts.append(attempt)
        if len(matches)!=1 or len(args)!=1 or not direct_reference(matches[0],node,self.blob):
            attempt['reasons']=matches[0]['reasons'] if len(matches)==1 else ['no_unique_call_evidence']
            # Reuse R02's pre-call read binding for unsupported ordinary calls such
            # as use(x); it then invalidates and stops, without proving effects.
            super().call(node,path);invalidate_memory(path)
            if path.termination is None:self.barrier(node,path,'R04_call_contract_not_supported')
            return [path]
        call=matches[0];attempt['direct_call_status']='PASS';attempt['R01_original_mapping_status']=call['status']
        address,decl=address_evidence(self,args[0],path,call);self.addresses.append(address)
        attempt['address_status']=address['status']
        if address['status']!='PASS':
            self.barrier(node,path,address['unknown_reason']);attempt['reasons']=[address['unknown_reason']];return [path]
        current=self.by_version.get(address['caller_pre_version'])
        if not current or current['status']!='PASS':
            self.barrier(node,path,'target_current_value_not_verified');attempt['reasons']=['target_current_value_not_verified'];return [path]
        obj=self.memory.objects[address['target_memory_object_id']]
        self.memory.ensure_snapshot(obj,path,current)
        before=snapshot(path)
        if len(self.contexts)>=16:
            self.barrier(node,path,'call_context_budget_exceeded');attempt['reasons']=['call_context_budget_exceeded'];return [path]
        argument={'argument_transfer_id':r01.stable_id('address-transfer',[call['callsite_id'],address['address_evidence_id'],obj['memory_object_id']]),
            'R01_original_transfer_id':call['mappings'][0]['transfer_id'],'address_evidence_id':address['address_evidence_id'],
            'target_memory_object_id':obj['memory_object_id'],'caller_pre_version':current['value_version_id'],
            'caller_pre_slot_id':address['caller_slot_id'],'formal_declaration':call['mappings'][0]['formal_declaration'],
            'type_compatibility':address['type_compatibility'],'status':'PASS','value_category':'address_of_object'}
        context=create_context(self.ns,call,path.path_id,before,[argument]);context['target_memory_object_id']=obj['memory_object_id']
        self.contexts.append(context)
        definition=node.referenced.get_definition();callee_ns={**self.ns,'call_context_id':context['call_context_id'],'frame_role':'callee'}
        effect=EffectTrace(definition,self.blob,callee_ns,context,address).run();self.callees.append(effect)
        attempt.update(pointer_entry_status='PASS',unique_target_status='PASS')
        full=effect['status']=='PASS';context['status']='PASS' if full else 'UNKNOWN'
        transfer={'effect_transfer_id':r01.stable_id('effect-transfer',[context['call_context_id'],obj['memory_object_id']]),
            'call_context_id':context['call_context_id'],'callsite_id':call['callsite_id'],
            'target_memory_object_id':obj['memory_object_id'],'address_evidence_id':address['address_evidence_id'],
            'argument_transfer_id':argument['argument_transfer_id'],'pointer_target_id':effect['pointer_targets'][0]['pointer_target_id'],
            'caller_pre_version':current['value_version_id'],'caller_pre_memory_version':before['memory_current'][obj['memory_object_id']],
            'caller_post_version':None,'caller_post_memory_version':None,'caller_pre_environment':before,'caller_post_environment':None,
            'indirect_write_ids':[w['indirect_write_id'] for w in effect['indirect_writes']],
            'effect_coverage':effect['effect_coverage'],'escape_coverage':effect['escape_coverage'],
            'unknown_effect_block_status':'N/A' if full else 'PASS','caller_new_version_status':'UNKNOWN' if not full else 'N/A',
            'pointer_entry_status':'PASS','unique_target_status':'PASS','status':'PASS' if full else 'UNKNOWN',
            'reasons':[] if full else effect['reasons'],'source_sha256':self.ns['source_sha256'],
            'caller_body_sha256':self.body_hash,'callee_body_sha256':effect['body_sha256'],
            'evidence_chain':{'CallerPre':current['value_version_id'],'AddressEvidence':address['address_evidence_id'],
                'ArgumentTransfer':argument['argument_transfer_id'],'CalleePointerEntry':effect['pointer_targets'][0]['callee_entry_version_id'],
                'IndirectWrite':[w['indirect_write_id'] for w in effect['indirect_writes']],'CallerPost':None}}
        self.transfers.append(transfer);attempt['call_context_id']=context['call_context_id'];attempt['status']=transfer['status']
        for write in effect['indirect_writes']:write['effect_coverage']=effect['effect_coverage']
        if not full:
            self.barrier(node,path,'uncovered_callee_effects');attempt['reasons']=effect['reasons'];return [path]
        post=copy.deepcopy(path);post.path_id=r01.stable_id('r04-caller-post',[context['call_context_id'],path.path_id])
        if effect['indirect_writes']:
            write=effect['indirect_writes'][0]
            rec=self.version(decl,node,post,'indirect_call_receive',{
                'kind':'verified_indirect_write','indirect_write_id':write['indirect_write_id'],
                'assigned_value':write['assigned_value'],'assigned_value_type':write['assigned_value_type'],
                'conversion':write['type_compatibility'],'call_context_id':context['call_context_id'],
                'write_event_id':write['write_event_id'],'write_location':write['indirect_write_location'],
                'callee_body_sha256':effect['body_sha256']})
            transfer.update(caller_post_version=rec['value_version_id'],caller_post_memory_version=post.memory_current[obj['memory_object_id']],caller_new_version_status='PASS')
            transfer['evidence_chain']['CallerPost']={'value_version_id':rec['value_version_id'],'memory_version_id':transfer['caller_post_memory_version']}
            write.update(caller_post_version=rec['value_version_id'],caller_post_memory_version=transfer['caller_post_memory_version'])
        transfer['caller_post_environment']=snapshot(post)
        attempt['caller_new_version_status']=transfer['caller_new_version_status']
        return [post]


def analyze(path,*,dataset_id,position,build_status,caller=None,candidate_source_paths=()):
    start=time.perf_counter()
    if not isinstance(dataset_id,str) or not dataset_id or type(position) is not int or position<0:raise ValueError('invalid data identity')
    path,blob,tu,nodes,diags=r01.parse(path);ns=namespace(path,blob,dataset_id,position,build_status)
    reasons=[]
    if build_status!='synthetic-self-contained':reasons.append('missing_original_build_evidence')
    if re.search(rb'^\s*#',blob,re.M):reasons.append('preprocessing_not_supported')
    if any(d['severity']>=r01.c.Diagnostic.Warning for d in diags):reasons.append('clang_diagnostics_no_recovery_approval')
    fns=[n for n in nodes if n.kind.name=='FUNCTION_DECL' and n.is_definition() and n.spelling==caller]
    if len(fns)!=1:reasons.append('caller_not_uniquely_selected')
    report={'dataset_id':dataset_id,'position':position,'source':str(path),'source_sha256':ns['source_sha256'],
        'build_evidence':ns['build'],'diagnostics':diags,'status':'UNKNOWN','reasons':reasons,'caller':None,
        'address_evidence':[],'memory_objects':[],'memory_versions':[],'call_contexts':[],'callees':[],'effect_transfers':[],
        'call_attempts':[],'summary_cache_used':False,'SMT_generated':False,'safety_decisions_produced':False}
    if not reasons:
        ref=r01.analyze(path,dataset_id=dataset_id,position=position,build_status=build_status,candidate_source_paths=candidate_source_paths)
        if ref['source_sha256']!=ns['source_sha256']:raise RuntimeError('source snapshot changed')
        trace=CallerTrace(fns[0],blob,ns,ref);report['caller']=trace.run()
        report.update(address_evidence=trace.addresses,memory_objects=list(trace.memory.objects.values()),memory_versions=trace.memory.versions,
            call_contexts=trace.contexts,callees=trace.callees,effect_transfers=trace.transfers,call_attempts=trace.attempts,R01_evidence=ref)
        report['status']='UNKNOWN' if report['caller']['status']!='PASS' else 'PASS' if trace.contexts else 'N/A'
        report['reasons']=report['caller']['reasons']
    report['context_isolation']=verify_isolation(report['call_contexts']) if report['call_contexts'] else {'status':'N/A'}
    report['metrics']=metrics(report);report['elapsed_seconds']=time.perf_counter()-start
    return report


def metrics(report):
    return {'call_attempts':counts(a['status'] for a in report['call_attempts']),
        'address_evidence':counts(a['address_status'] for a in report['call_attempts']),
        'pointer_entry':counts(a['pointer_entry_status'] for a in report['call_attempts']),
        'unique_target':counts(a['unique_target_status'] for a in report['call_attempts']),
        'indirect_write':counts(w['status'] for f in report['callees'] for w in f['indirect_writes']),
        'caller_new_version':counts(a['caller_new_version_status'] for a in report['call_attempts']),
        'escape_coverage':counts(f['escape_coverage'] for f in report['callees']),
        'unknown_effect_block':counts(t['unknown_effect_block_status'] for t in report['effect_transfers']),
        'complete_call':counts(c['status'] for c in report['call_contexts'])}


def proposal_from(report):
    return {'has_indirect_write':any(w['status']=='PASS' for f in report['callees'] for w in f['indirect_writes']),
        'writes':[{k:copy.deepcopy(w[k]) for k in ('indirect_write_id','target_memory_object_id','pointer_slot_id',
                    'pointer_entry_version','pointer_current_version','assigned_value','assigned_value_type','type_compatibility')}
                  for f in report['callees'] for w in f['indirect_writes']],
        'transfers':[{k:copy.deepcopy(t[k]) for k in ('effect_transfer_id','call_context_id','target_memory_object_id',
            'address_evidence_id','pointer_target_id','caller_pre_version','caller_pre_memory_version',
            'caller_post_version','caller_post_memory_version','indirect_write_ids','effect_coverage')} for t in report['effect_transfers']]}


def verify_proposal(report,proposal):
    expected=proposal_from(report)
    if isinstance(proposal,dict) and proposal.get('has_indirect_write') is False and expected['has_indirect_write']:
        return {'status':'REJECT','reasons':['candidate_denies_verified_prefix_indirect_write']}
    if not report['effect_transfers'] or any(t['status']!='PASS' for t in report['effect_transfers']):
        return {'status':'UNKNOWN','reasons':['full_effect_reference_not_verified']}
    if not isinstance(proposal,dict) or set(proposal)!=set(expected) or not isinstance(proposal['transfers'],list) or not isinstance(proposal['writes'],list) or any(not isinstance(t,dict) or set(t)!=set(expected['transfers'][0]) for t in proposal['transfers']):
        return {'status':'UNKNOWN','reasons':['proposal_missing_required_evidence']}
    return {'status':'PASS' if proposal==expected else 'REJECT',
            'reasons':[] if proposal==expected else ['candidate_conflicts_with_verified_object_address_context_or_version'],
            'expected':expected,'proposed':proposal}
