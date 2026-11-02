"""Deterministic, bounded local def-use sidecar. No execution, SMT or call effects."""
from __future__ import annotations

import json
import re
import time

from r01_adapter import ROOT, namespace, r01, slot_evidence
from state_environment import StateEnvironment

c = r01.c
CONFIG = json.loads((ROOT/'config.json').read_text('utf-8'))
CONTROL_UNSUPPORTED = {'FOR_STMT','WHILE_STMT','DO_STMT','GOTO_STMT','INDIRECT_GOTO_STMT',
                       'SWITCH_STMT','ASM_STMT','GCC_ASM_STMT','LABEL_STMT'}


def supported_type(t):
    if t['volatile'] or t['restrict'] or t['size_bytes'] <= 0:
        return False
    if t['kind'] in r01.SCALARS:
        return True
    if t['kind'] != 'POINTER':
        return False
    p = t['pointee']
    if p['volatile'] or p['restrict']:
        return False
    if p['kind'] in r01.SCALARS:
        return p['size_bytes'] > 0
    return p['kind']=='RECORD' and p['record_declaration']['kind']=='STRUCT_DECL' and bool(p['record_declaration']['usr'])


def unwrap(node):
    while node.kind.name in {'PAREN_EXPR','UNEXPOSED_EXPR'}:
        children = list(node.get_children())
        if len(children)!=1:
            break
        node=children[0]
    return node


class FunctionTrace:
    def __init__(self, fn, blob, ns):
        self.fn, self.blob, self.ns = fn, blob, ns
        self.function = r01.declaration(fn,ns)
        self.body_hash = r01.digest(r01.raw(fn,blob).encode())
        self.slots, self.versions, self.reads = {}, [], []
        self.by_version, self.events, self.snapshots, self.blocked_ranges = {}, [], [], []
        self.reasons = []

    def event(self, node, path, kind):
        event = {'event_id':r01.stable_id('definition-event',[self.ns,r01.span(node),path.path_id,kind]),
                 'kind':kind,'path_id':path.path_id,'source_range':r01.span(node),
                 'raw_expression':r01.raw(node,self.blob)}
        self.events.append(event)
        return event

    def slot(self, decl):
        item=slot_evidence(decl,self.ns)
        self.slots.setdefault(item['slot_id'], item)
        return item

    def barrier(self, node, path, reason):
        event=self.event(node,path,'unknown_effect_barrier')
        event.update(reason=reason, before=path.snapshot())
        path.invalidate(event['event_id'])
        event['after']=path.snapshot()
        self.reasons.append(reason)

    def version(self, decl, node, path, kind, value, status='PASS', reasons=(), previous=None):
        slot=self.slot(decl); sid=slot['slot_id']
        prior=path.current.get(sid) if previous is None else previous
        event=self.event(node,path,kind)
        number=path.next_version(sid)
        vid=r01.stable_id('value-version',[self.ns,sid,path.path_id,event['event_id'],number])
        record={'dataset_id':self.ns['dataset_id'],'position':self.ns['position'],
                'function_identity':self.function,'declaration_identity':slot['declaration'],
                'slot_id':sid,'value_version_id':vid,'version_number':number,
                'display_name':slot['declaration']['name']+'@'+str(number),
                'previous_version_id':prior,'definition_event_id':event['event_id'],
                'definition_range':r01.span(node),'raw_assignment':r01.raw(node,self.blob),
                'type':slot['type'],'assignment_kind':kind,'value':value,
                'source_slot_id':value.get('source_slot_id'),
                'source_value_version_id':value.get('source_value_version_id'),
                'path_id':path.path_id,'status':status,'reasons':list(reasons),
                'reaching_definition_evidence':{'method':'ordered_supported_statements_on_one_path',
                    'guard_chain':list(path.guards),'unknown_effects_crossed':False if status=='PASS' else None},
                'source_sha256':self.ns['source_sha256'],'body_sha256':self.body_hash,
                'memory_object_identity_verified':False,'call_effects_verified':False}
        self.versions.append(record); self.by_version[vid]=record
        path.current[sid]=vid
        return record

    def read(self, node, path, role):
        decl=node.referenced
        if not decl or decl.kind.name not in {'PARM_DECL','VAR_DECL'} or decl.semantic_parent!=self.fn:
            self.barrier(node,path,'nonlocal_or_unbound_read')
            return None
        item=self.slot(decl); sid=item['slot_id']; vid=path.current.get(sid)
        value=self.by_version.get(vid)
        ok=value is not None and value['status']=='PASS' and supported_type(item['type'])
        rd={'read_id':r01.stable_id('read',[self.ns,r01.span(node),path.path_id,role]),
            'dataset_id':self.ns['dataset_id'],'position':self.ns['position'],
            'path_id':path.path_id,'slot_id':sid,'value_version_id':vid,
            'source_range':r01.span(node),'expression':r01.raw(node,self.blob),'role':role,
            'status':'PASS' if ok else 'UNKNOWN',
            'reasons':[] if ok else ['no_verified_reaching_definition'],
            'environment_before_read':dict(path.current),'source_sha256':self.ns['source_sha256']}
        self.reads.append(rd)
        if not ok:
            self.barrier(node,path,'no_verified_reaching_definition')
        return rd

    def operator(self,node):
        children=list(node.get_children())
        if len(children)!=2:
            return None
        lo,hi=children[0].extent.end.offset,children[1].extent.start.offset
        tokens=[t.spelling for t in node.get_tokens() if lo<=t.location.offset<hi and t.kind!=c.TokenKind.COMMENT]
        return tokens[0] if len(tokens)==1 else None

    def expression(self,node,path,role='read'):
        leaf=unwrap(node); kind=leaf.kind.name
        if kind=='DECL_REF_EXPR':
            return self.read(leaf,path,role) is not None and path.termination is None
        if kind in {'INTEGER_LITERAL','FLOATING_LITERAL'}:
            return True
        children=list(leaf.get_children())
        if kind=='CSTYLE_CAST_EXPR' and leaf.type.kind==c.TypeKind.VOID:
            exprs=[n for n in children if n.kind.is_expression()]
            return len(exprs)==1 and self.expression(exprs[0],path,role)
        if kind=='UNARY_OPERATOR':
            tokens=list(leaf.get_tokens())
            op=tokens[0].spelling if tokens else None
            if op=='!' and len(children)==1:
                return self.expression(children[0],path,role)
            self.barrier(leaf,path,'address_escape' if op=='&' else 'unsupported_unary_or_write')
            return False
        if kind=='BINARY_OPERATOR' and self.operator(leaf) in {'==','!='}:
            # Record reads/branch direction only; never turn this expression into SMT.
            return all(self.expression(x,path,role) for x in children)
        if kind=='CALL_EXPR':
            self.call(leaf,path)
            return False
        self.barrier(leaf,path,'unsupported_expression_'+kind)
        return False

    def call(self,node,path):
        # All calls are effect barriers in R02, even if a direct callee is visible.
        ref=node.referenced
        if (not ref or ref.kind.name!='FUNCTION_DECL' or
            not re.match(r'\s*'+re.escape(ref.spelling)+r'\s*\(',r01.raw(node,self.blob))):
            self.barrier(node,path,'indirect_or_complex_callee_not_supported')
            return
        args=list(node.get_arguments())
        # C argument evaluation order is unspecified. Inspect ALL arguments before
        # approving any pre-call read; a later x=... could precede an earlier x read.
        for arg in args:
            leaf=unwrap(arg)
            if leaf.kind.name=='DECL_REF_EXPR':
                d=leaf.referenced
                safe=(d is not None and d.kind.name in {'PARM_DECL','VAR_DECL'} and
                      d.semantic_parent==self.fn and supported_type(r01.type_info(d.type,self.ns)))
            else:
                safe=leaf.kind.name in {'INTEGER_LITERAL','FLOATING_LITERAL'}
            if not safe:
                reason='address_escape' if leaf.kind.name=='UNARY_OPERATOR' and any(t.spelling=='&' for t in leaf.get_tokens()) else 'unsupported_call_argument_evaluation_order'
                self.barrier(node,path,reason)
                return
        for arg in args:
            if path.termination is None:
                self.expression(arg,path,'call_argument')
        if path.termination is None:
            self.barrier(node,path,'unknown_function_call_effect')

    def rhs(self,node,decl,path):
        leaf=unwrap(node); kind=leaf.kind.name
        target=r01.type_info(decl.type,self.ns)
        if kind=='DECL_REF_EXPR':
            rd=self.read(leaf,path,'assignment_rhs')
            if rd is None or rd['status']!='PASS':
                return None,'unverified_rhs_read'
            actual=r01.type_info(leaf.referenced.type,self.ns)
            conversion=r01.conversion(actual,target,r01.type_info(node.type,self.ns))
            if conversion['status']!='PASS':
                return None,'unsupported_assignment_conversion'
            return {'kind':'value_copy','source_slot_id':rd['slot_id'],
                    'source_value_version_id':rd['value_version_id'],
                    'source_read_id':rd['read_id'],'conversion':conversion},None
        if kind in {'INTEGER_LITERAL','FLOATING_LITERAL'}:
            text=r01.raw(leaf,self.blob)
            if (target['kind']=='POINTER' and kind=='INTEGER_LITERAL' and text=='0' and
                node.type.get_canonical().spelling==decl.type.get_canonical().spelling):
                return {'kind':'null_pointer_constant','literal':'0','ast_conversion_type':node.type.spelling},None
            conversion=r01.conversion(r01.type_info(leaf.type,self.ns),target,r01.type_info(node.type,self.ns))
            if conversion['status']=='PASS':
                return {'kind':'constant','literal':text,'conversion':conversion},None
            return None,'unsupported_literal_conversion'
        if kind=='CALL_EXPR':
            self.call(leaf,path)
            return {'kind':'unknown_return','call_range':r01.span(leaf),'return_semantics_verified':False},'unknown_return_and_call_effect'
        return None,'unsupported_rhs_'+kind

    def assign(self,decl,node,rhs,path,initialization=False):
        slot=self.slot(decl); sid=slot['slot_id']; previous=path.current.get(sid)
        if decl.storage_class in {c.StorageClass.STATIC,c.StorageClass.EXTERN} or not supported_type(slot['type']):
            self.barrier(node,path,'unsupported_storage_or_type')
            return
        value,reason=self.rhs(rhs,decl,path)
        if reason:
            if path.termination is None:
                self.barrier(rhs,path,reason)
            self.version(decl,node,path,'unknown_return' if value else 'unsupported_assignment',
                         value or {'kind':'unverified_expression'},'UNKNOWN',[reason],previous)
            return
        kind='initialization' if initialization else 'variable_copy' if value['kind']=='value_copy' else 'constant_assignment'
        self.version(decl,node,path,kind,value,previous=previous)

    def statement(self,node,path):
        kind=node.kind.name
        if kind=='COMPOUND_STMT':
            return self.compound(node,[path])
        if kind=='DECL_STMT':
            for decl in node.get_children():
                if decl.kind.name!='VAR_DECL':
                    self.barrier(node,path,'unsupported_declaration');break
                item=self.slot(decl)
                exprs=[x for x in decl.get_children() if x.kind.is_expression()]
                if not supported_type(item['type']) or decl.storage_class in {c.StorageClass.STATIC,c.StorageClass.EXTERN}:
                    self.barrier(decl,path,'unsupported_storage_or_type');break
                if not exprs:
                    path.current[item['slot_id']]=None
                    self.event(decl,path,'uninitialized_declaration')
                elif len(exprs)==1:
                    self.assign(decl,decl,exprs[0],path,True)
                else:
                    self.barrier(decl,path,'multiple_initializer_expressions')
                if path.termination:
                    break
        elif kind=='BINARY_OPERATOR' and self.operator(node)=='=':
            lhs,rhs=list(node.get_children()); lhs=unwrap(lhs)
            decl=lhs.referenced if lhs.kind.name=='DECL_REF_EXPR' else None
            if decl and decl.kind.name in {'PARM_DECL','VAR_DECL'} and decl.semantic_parent==self.fn:
                self.assign(decl,node,rhs,path)
            else:
                self.barrier(node,path,'indirect_member_array_or_nonlocal_write')
        elif kind=='IF_STMT':
            children=list(node.get_children())
            if len(children) not in {2,3} or not children[0].kind.is_expression():
                self.barrier(node,path,'unsupported_if_shape');return [path]
            condition=children[0]; before=len(self.reads)
            if not self.expression(condition,path,'branch_condition'):
                return [path]
            results=[]
            for direction,body in [(True,children[1]),(False,children[2] if len(children)==3 else None)]:
                guard={'expression':r01.raw(condition,self.blob),'direction':direction,
                       'source_range':r01.span(condition),
                       'condition_read_ids':[r['read_id'] for r in self.reads[before:]],
                       'semantics_inferred':False,'SMT_generated':False}
                pid=r01.stable_id('path',[path.path_id,r01.span(node),direction])
                fork=path.fork(pid,guard)
                results.extend(self.statement(body,fork) if body else [fork])
            return results
        elif kind=='RETURN_STMT':
            exprs=[x for x in node.get_children() if x.kind.is_expression()]
            if exprs:
                self.expression(exprs[0],path,'return_read_only')
            if path.termination is None:
                self.event(node,path,'return_terminates_local_path')
                path.termination='RETURN'
        elif kind=='NULL_STMT':
            pass
        else:
            self.expression(node,path,'discarded_value')
        return [path]

    def compound(self,body,paths):
        locals_here=[]
        for stmt in body.get_children():
            if stmt.kind.name=='DECL_STMT':
                locals_here.extend(self.slot(d)['slot_id'] for d in stmt.get_children() if d.kind.name=='VAR_DECL')
            next_paths=[]
            for path in paths:
                if path.termination is not None:
                    if path.termination!='RETURN':
                        self.blocked_ranges.append({'path_id':path.path_id,'range':r01.span(stmt),
                                                    'reason':'not_analyzed_after_unknown_effect'})
                    next_paths.append(path)
                else:
                    next_paths.extend(self.statement(stmt,path))
                self.snapshots.extend(p.snapshot() for p in next_paths[-CONFIG['max_paths']:])
            paths=next_paths
        for path in paths:
            for sid in locals_here:
                path.current.pop(sid,None)
        return paths

    def run(self):
        initial=StateEnvironment(r01.stable_id('path-entry',[self.ns,self.function['declaration_id']]))
        for parameter in self.fn.get_arguments():
            item=self.slot(parameter)
            if not supported_type(item['type']):
                self.barrier(parameter,initial,'unsupported_parameter_type');break
            self.version(parameter,parameter,initial,'parameter_entry',{'kind':'unconstrained_entry_value'})
        body=next(x for x in self.fn.get_children() if x.kind.name=='COMPOUND_STMT')
        paths=self.compound(body,[initial])
        status='UNKNOWN' if self.reasons else 'PASS' if self.versions or self.reads else 'NOT_APPLICABLE'
        return {'function':self.function,'body_sha256':self.body_hash,'status':status,
                'reasons':list(dict.fromkeys(self.reasons)), 'slots':list(self.slots.values()),
                'versions':self.versions,'reads':self.reads,'events':self.events,
                'state_snapshots':self.snapshots,'final_environments':[p.snapshot() for p in paths],
                'unprocessed_ranges':self.blocked_ranges,'paths_merged':False,
                'return_values_propagated':False,'call_effects_proven':False}


def analyze(path, *, dataset_id, position, build_status, function=None):
    started=time.perf_counter()
    if not isinstance(dataset_id,str) or not dataset_id or type(position) is not int or position<0:
        raise ValueError('dataset_id/position invalid')
    path,blob,tu,nodes,diagnostics=r01.parse(path)
    ns=namespace(path,blob,dataset_id,position,build_status)
    reasons=[]
    if build_status!=CONFIG['supported_build_status']:
        reasons.append('missing_original_build_evidence')
    if re.search(rb'^\s*#',blob,re.M):
        reasons.append('preprocessing_not_supported')
    if any(d['severity']>=c.Diagnostic.Warning for d in diagnostics):
        reasons.append('clang_diagnostics_no_recovery_approval')
    functions=[n for n in nodes if n.kind.name=='FUNCTION_DECL' and n.is_definition() and
               (function is None or n.spelling==function)]
    expression_evidence=[]
    if not reasons:
        for n in nodes:
            if n.kind.name not in {'DECL_REF_EXPR','MEMBER_REF_EXPR'} or not n.referenced:
                continue
            expression_evidence.append({'expression_id':r01.stable_id('expression',[ns,r01.span(n),n.kind.name]),
                                       'kind':n.kind.name,'text':r01.raw(n,blob),'range':r01.span(n),
                                       'referenced_declaration':r01.declaration(n.referenced,ns),
                                       'source_sha256':ns['source_sha256'],'status':'PASS'})
    results=[]
    for fn in functions:
        fn_reasons=list(reasons); descendants=list(fn.walk_preorder())
        if any(n.kind.name in CONTROL_UNSUPPORTED for n in descendants):
            fn_reasons.append('unsupported_control_flow')
        if sum(n.kind.name=='IF_STMT' for n in descendants)>CONFIG['max_if_statements_per_function']:
            fn_reasons.append('if_or_path_budget_exceeded')
        if fn.type.is_function_variadic():
            fn_reasons.append('variadic_function_not_supported')
        if fn_reasons:
            results.append({'function':r01.declaration(fn,ns),'body_sha256':r01.digest(r01.raw(fn,blob).encode()),
                            'status':'UNKNOWN','reasons':list(dict.fromkeys(fn_reasons)),
                            'slots':[],'versions':[],'reads':[],'events':[],
                            'state_snapshots':[],'final_environments':[],'unprocessed_ranges':[],
                            'recovery_nodes_trusted':False})
        else:
            results.append(FunctionTrace(fn,blob,ns).run())
    if not functions:
        reasons.append('target_function_not_uniquely_available' if function else 'no_function_definition')
    if function and len(functions)!=1:
        reasons.append('target_function_not_uniquely_available')
    statuses={f['status'] for f in results}
    status='UNKNOWN' if reasons or 'UNKNOWN' in statuses else 'PASS' if 'PASS' in statuses else 'NOT_APPLICABLE'
    return {'dataset_id':dataset_id,'position':position,'source':str(path),
            'source_sha256':ns['source_sha256'],'build_evidence':ns['build'],
            'status':status,'reasons':list(dict.fromkeys(reasons)), 'diagnostics':diagnostics,
            'functions':results,'expression_evidence':expression_evidence,
            'elapsed_seconds':time.perf_counter()-started,'scope':CONFIG['scope'],
            'SMT_generated':False,'cross_function_state_propagated':False}


def verify_read_claim(report, read_id, slot_id, value_version_id):
    reads=[r for f in report['functions'] for r in f['reads'] if r['read_id']==read_id]
    if len(reads)!=1 or reads[0]['status']!='PASS':
        return {'status':'UNKNOWN','reasons':['read_not_verified']}
    rd=reads[0]
    if slot_id!=rd['slot_id'] or value_version_id!=rd['value_version_id']:
        return {'status':'REJECT','reasons':['candidate_conflicts_with_path_reaching_definition'],
                'expected':{'slot_id':rd['slot_id'],'value_version_id':rd['value_version_id']}}
    return {'status':'PASS','reasons':[]}


def verify_expression_claim(report, expression_id, claimed_declaration_id):
    expressions=[x for x in report['expression_evidence'] if x['expression_id']==expression_id]
    if len(expressions)!=1 or expressions[0]['status']!='PASS':
        return {'status':'UNKNOWN','reasons':['expression_identity_not_verified']}
    expected=expressions[0]['referenced_declaration']['declaration_id']
    return {'status':'PASS' if expected==claimed_declaration_id else 'REJECT',
            'reasons':[] if expected==claimed_declaration_id else ['member_or_variable_declaration_identity_conflict'],
            'expected_declaration_id':expected}
