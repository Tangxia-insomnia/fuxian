"""Read-only adapter to accepted R01/R02/R03; no core globals changed."""
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parent
REPRO=ROOT.parents[1]
R03=ROOT.parent/'E06_R03_return_value_transfer'
sys.path.insert(0,str(R03))
import adapter as r03_api
from adapter import r01,r02,StateEnvironment,namespace,typed,counts,offline_boundary,rf_inputs
from call_context import create_context,verify_isolation
from return_value import ReturnTrace


def snapshot(path):
    return {**path.snapshot(),'memory_current':dict(getattr(path,'memory_current',{}))}


def invalidate_memory(path):
    path.memory_current={k:None for k in getattr(path,'memory_current',{})}


def ordinary_scalar(t):
    return t['kind'] in r01.SCALARS and r02.supported_type(t) and not t['const']


def direct_reference(call,node,blob):
    # R01 leaves &local outside its original argument subset. Reuse ONLY its
    # trusted unique direct-definition evidence, never relabel its mapping PASS.
    return (call['ast_is_trusted'] and call['callee_body_sha256'] is not None
        and call['reasons']==['actual_expression_outside_identifier_subset']
        and len(call['mappings'])==1 and call['mappings'][0]['reasons']==['actual_expression_outside_identifier_subset']
        and node.referenced is not None and node.referenced.kind.name=='FUNCTION_DECL'
        and node.referenced.get_definition() is not None
        and r01.digest(r01.raw(node.referenced.get_definition(),blob).encode())==call['callee_body_sha256'])
