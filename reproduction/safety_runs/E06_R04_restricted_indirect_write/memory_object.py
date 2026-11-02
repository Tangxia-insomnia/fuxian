"""Identity and immutable versions of one automatic scalar object per address."""
from r03_adapter import r01,typed


class MemoryStore:
    def __init__(self):
        self.objects={};self.by_slot={};self.versions=[]

    def object(self,trace,decl):
        slot=trace.slot(decl);sid=slot['slot_id']
        if sid not in self.by_slot:
            identity=r01.stable_id('memory-object',[trace.ns,trace.function,slot['declaration'],trace.body_hash])
            self.by_slot[sid]=identity
            self.objects[identity]={'dataset_id':trace.ns['dataset_id'],'position':trace.ns['position'],
                'memory_object_id':identity,'owning_function':trace.function,'declaration_identity':slot['declaration'],
                'caller_slot_id':sid,'object_type':typed(decl.type,trace.ns),'object_scope':'automatic_caller_local',
                'source_location':r01.span(decl),'body_sha256':trace.body_hash,'source_sha256':trace.ns['source_sha256'],
                'storage_kind':'automatic_scalar','escape_status':'no_prior_escape_on_supported_prefix',
                'status':'PASS','unknown_reason':None,'unique_by':'AST_declaration_and_no_previous_address_escape'}
        return self.objects[self.by_slot[sid]]

    def version(self,obj,path,caller_value,*,kind,write_event=None,source_location=None,body_sha=None,context=None,value_type=None):
        if not hasattr(path,'memory_current'):path.memory_current={}
        oid=obj['memory_object_id'];previous=path.memory_current.get(oid)
        value=caller_value['value']
        record={'memory_object_id':oid,'memory_version_id':r01.stable_id('memory-version',[
                    oid,path.path_id,previous,caller_value['value_version_id'],kind,write_event,context]),
            'previous_memory_version_id':previous,'caller_value_version_id':caller_value['value_version_id'],
            'write_event_id':write_event,'kind':kind,'write_value':value,
            'write_value_type':value_type or obj['object_type'],'call_context_id':context,'path_id':path.path_id,
            'source_location':source_location or caller_value['definition_range'],
            'body_sha256':body_sha or obj['body_sha256'],'source_sha256':obj['source_sha256'],
            'status':caller_value['status'],'unknown_reason':None if caller_value['status']=='PASS' else 'unverified_value_version'}
        self.versions.append(record);path.memory_current[oid]=record['memory_version_id']
        return record

    def ensure_snapshot(self,obj,path,current):
        if getattr(path,'memory_current',{}).get(obj['memory_object_id']) is None:
            return self.version(obj,path,current,kind='initial_value_snapshot')
        return next(v for v in self.versions if v['memory_version_id']==path.memory_current[obj['memory_object_id']])
