"""Read-only exploration of saved evidence. No model or experiment imports."""
from pathlib import Path
from collections import Counter
import json
import sys

ROOT = Path(__file__).resolve().parents[2]

def load(path):
    return json.loads((ROOT/path).read_text(encoding='utf-8'))

rows = load('results/processed/expanded_all_npd.json')
if len(sys.argv) == 1:
    print('STATES', Counter((r['label'], r['status'], r['prediction']) for r in rows))
    print('BLOCKS', Counter(r['error'] for r in rows if r['status'].startswith('blocked')))
    for r in rows:
        if r['status'] == 'failed' or (r['label'] == 1 and r['prediction'] == 'filter'):
            print('FAIL', r['sample_id'], r['raw_output'], r['error'])
    for r in rows:
        if r['label'] == 0 and r['prediction'] == 'keep':
            d = ROOT/r['raw_output']
            c = json.loads((d/'context.json').read_text(encoding='utf-8'))
            print('KEPT_FP', r['sample_id'], 'frames', len(c['frames']), 'sink', c['frames'][-1]['target'].strip(), 'function', c['frames'][0]['function'])
else:
    # Select rows using group substring and zero-based source position.
    needle, position = sys.argv[1], int(sys.argv[2])
    r = next(x for x in rows if needle in x['sample_id'] and x['row_position'] == position)
    print('RESULT', json.dumps(r, ensure_ascii=False, indent=2))
    original = load('upstream/'+r['dataset'])[position]
    if len(sys.argv) > 3 and sys.argv[3] == 'brief':
        print('ALERT', original.get('var_name'), original.get('function_name'), original.get('location'))
        if (ROOT/r['raw_output']/'context.json').exists():
            context = load(r['raw_output']+'/context.json')
            for frame in context['frames']:
                print('FRAME', frame['level'], frame['function'], frame['var_name'], frame['target'])
                print('EXTRACTED', json.dumps({k:v for k,v in frame.get('extracted',{}).items() if k != 'filter_function_code'}, ensure_ascii=False))
                lines = frame['code'].splitlines()
                needles = ['skb =', 'if (!skb)', 'TCP_SKB_CB(skb)->tcp_flags', 'copied', 'che', 'TYPE_', 'return', 'kfree', 'free_large', 'NULL', 'dst[']
                if len(sys.argv)>4:
                    needles=sys.argv[4:]
                wanted = {i+j for i,line in enumerate(lines) if any(n in line for n in needles) for j in range(-1,3)}
                print('CODE', '\n'.join(f'{i+1}: {line}' for i,line in enumerate(lines) if i in wanted))
        d = ROOT/r['raw_output']
        if (d/'author_pipeline_output.json').exists():
            out=load(r['raw_output']+'/author_pipeline_output.json')
            print('PIPELINE', json.dumps({k:v for k,v in out.items() if k != 'function_body_list'},ensure_ascii=False))
        for p in d.glob('solver_*.json'):
            sol=json.loads(p.read_text(encoding='utf-8'))
            print('SOLVER',p.name,json.dumps({k:v for k,v in sol.items() if k not in {'source','stdout'}},ensure_ascii=False))
        allcalls=[]
        for p in sorted((ROOT/'results/raw/completed/calls').glob('*.json')):
            c=json.loads(p.read_text(encoding='utf-8'))
            if c.get('sample_id')==r['sample_id']:
                choices=c.get('choices') or []
                msg=choices[0].get('message',{}).get('content','') if choices else ''
                allcalls.append((c['call_id'],c.get('timestamp'),(c.get('messages') or [{}])[-1].get('content','')[:110],msg,choices[0].get('finish_reason') if choices else None))
        print('CALLS',json.dumps(allcalls,ensure_ascii=False))
        raise SystemExit(0)
    print('ORIGINAL', json.dumps({k:v for k,v in original.items() if k not in {'function_code','func_info'}}, ensure_ascii=False, indent=2))
    d = ROOT/r['raw_output']
    if (d/'context.json').exists():
        print('CONTEXT', (d/'context.json').read_text(encoding='utf-8'))
    if (d/'author_pipeline_output.json').exists():
        print('PIPELINE', (d/'author_pipeline_output.json').read_text(encoding='utf-8'))
    for p in d.glob('solver_*.json'):
        print(p.name, p.read_text(encoding='utf-8'))
    if (d/'stdout.txt').exists():
        print('STDOUT', (d/'stdout.txt').read_text(encoding='utf-8'))
