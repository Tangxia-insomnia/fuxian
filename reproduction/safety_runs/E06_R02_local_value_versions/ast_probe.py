"""Trusted local AST probe only; never compile/run the C input."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent/'E06_R01_direct_call_argument_mapping'))
import mapper
import offline_boundary

offline_boundary.install()
path, blob, tu, nodes, diagnostics = mapper.parse(ROOT/'ast_probe.c')
out = {'source_sha256':mapper.digest(blob), 'diagnostics':diagnostics,
       'nodes':[{'kind':n.kind.name,'text':mapper.raw(n,blob),
                 'type':n.type.spelling,'range':mapper.span(n),
                 'referenced_usr':n.referenced.get_usr() if n.referenced else None,
                 'children':[x.kind.name for x in n.get_children()]} for n in nodes],
       'model_calls':0,'Z3_calls':0,'C_execution':0}
with (ROOT/'ast_probe_result.json').open('x',encoding='utf-8') as f:
    json.dump(out,f,indent=2);f.write('\n')
print(json.dumps({'diagnostics':diagnostics,'kinds':sorted({x['kind'] for x in out['nodes']}),
                  'node_count':len(nodes)}))
