"""Only the AST expression &one automatic scalar local is admitted."""
from r03_adapter import r01,r02,typed,ordinary_scalar


def address_evidence(trace,arg,path,call):
    leaf=r02.unwrap(arg)
    record={'address_evidence_id':r01.stable_id('address',[trace.ns,call['callsite_id'],path.path_id,r01.span(arg)]),
        'dataset_id':trace.ns['dataset_id'],'position':trace.ns['position'],'callsite_id':call['callsite_id'],
        'caller_path_id':path.path_id,'original_expression':r01.raw(arg,trace.blob),'source_location':r01.span(arg),
        'source_sha256':trace.ns['source_sha256'],'caller_body_sha256':trace.body_hash,
        'target_memory_object_id':None,'caller_slot_id':None,'declaration_identity':None,
        'caller_pre_version':None,'type_compatibility':None,'status':'UNKNOWN','unknown_reason':None}
    children=list(leaf.get_children())
    toks=[t.spelling for t in leaf.get_tokens() if t.kind!=r01.c.TokenKind.COMMENT]
    if leaf.kind.name!='UNARY_OPERATOR' or not toks or toks[0]!='&' or len(children)!=1:
        record['unknown_reason']='argument_not_direct_address';return record,None
    operand=r02.unwrap(children[0]);decl=operand.referenced if operand.kind.name=='DECL_REF_EXPR' else None
    if (decl is None or decl.kind.name!='VAR_DECL' or decl.semantic_parent!=trace.fn
        or decl.storage_class in {r01.c.StorageClass.STATIC,r01.c.StorageClass.EXTERN}
        or not ordinary_scalar(typed(decl.type,trace.ns))):
        record['unknown_reason']='target_not_automatic_unqualified_scalar_local';return record,None
    formal=call['mappings'][0]['formal_type']
    at=typed(arg.type,trace.ns)
    if (formal['kind']!='POINTER' or not r02.supported_type(formal)
        or formal['pointee']['kind'] not in r01.SCALARS or not ordinary_scalar(formal['pointee'])):
        record['unknown_reason']='formal_not_single_pointer_to_writable_scalar';return record,None
    conv=r01.conversion(at,formal,at)
    record['type_compatibility']=conv
    if conv['status']!='PASS':
        record['unknown_reason']='unsupported_address_parameter_conversion';return record,None
    obj=trace.memory.object(trace,decl);slot=trace.slot(decl)
    record.update(target_memory_object_id=obj['memory_object_id'],caller_slot_id=slot['slot_id'],
                  declaration_identity=slot['declaration'],caller_pre_version=path.current.get(slot['slot_id']),status='PASS')
    return record,decl


def pointer_record(context,address,parameter_entry,parameter,ns):
    return {'pointer_target_id':r01.stable_id('pointer-target',[context['call_context_id'],parameter_entry['value_version_id'],address['address_evidence_id']]),
        'pointer_slot_id':parameter_entry['slot_id'],'pointer_value_version_id':parameter_entry['value_version_id'],
        'target_memory_object_id':address['target_memory_object_id'],'target_address_evidence_id':address['address_evidence_id'],
        'call_context_id':context['call_context_id'],'caller_path_id':context['caller_path_id'],
        'callee_entry_version_id':parameter_entry['value_version_id'],'type_compatibility':address['type_compatibility'],
        'uniqueness_status':'PASS','source_location':r01.span(parameter),'parameter_identity':r01.declaration(parameter,ns),
        'status':'PASS','relation':'entry_address_points_to_unique_automatic_scalar_object','slots_merged':False}
