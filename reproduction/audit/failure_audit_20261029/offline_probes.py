"""Targeted audit probes on in-memory copies; no production or prediction edits."""
from pathlib import Path
from collections import Counter, defaultdict
import __future__
import ast
import json
import os
import re
import subprocess
import sys
import z3

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT))
from completion.context import called_function, parameter_name, calls, definitions

def read(p):return json.loads(p.read_text(encoding='utf-8'))
def write(name,value):(HERE/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')

def extractor():
    p=ROOT/'upstream/llm4pfa/extract_util_plus.py'
    tree=ast.parse(p.read_text(encoding='utf-8'))
    tree.body=[n for n in tree.body if not isinstance(n,ast.ImportFrom) or n.module!='LLM4Detection.m_agent.conditions_info']
    ns={'__name__':'offline_audit_only','__file__':str(p)}
    exec(compile(tree,str(p),'exec',flags=__future__.annotations.compiler_flag),ns)
    return ns['extract_conditions']

def normalize_indent(text):
    # Diagnostic counterfactual only: convert groups of four leading spaces.
    # C tokens, expressions, line order and line count are unchanged.
    return '\n'.join(re.sub(r'^( +)',lambda m:'\t'*(len(m[1])//4)+' '*(len(m[1])%4),line) for line in text.split('\n'))

def main():
    get_conditions=extractor()
    probes=[]
    for aid,level in [('A03',0),('A08',1),('A06',0)]:
        frame=read(HERE/'samples'/aid/'recorded_raw/context.json')['frames'][level]
        actual=json.loads(get_conditions(frame['var_name'],None,frame['target'],frame['code']))
        changed_code=normalize_indent(frame['code']); changed_target=normalize_indent(frame['target'])
        diagnostic=json.loads(get_conditions(frame['var_name'],None,changed_target,changed_code))
        assert re.sub(r'\s+','',changed_code)==re.sub(r'\s+','',frame['code'])
        probes.append({'audit_id':aid,'frame':level,'saved_conditions':frame['extracted']['target_conditions'],
            'original_extractor_replay':actual['target_conditions'],
            'indentation_only_counterfactual':diagnostic['target_conditions'],
            'not_an_experiment_result':True,'prediction_not_rerun':True,
            'target_occurrences_in_saved_code':sum(frame['target'] in line for line in frame['code'].splitlines())})
    write('indentation_probes.json',probes)

    candidate=read(HERE/'samples/A05/offline_context_diagnostic.json')['context']
    preflight=[]
    for f in candidate['frames']:
        ext=json.loads(get_conditions(f['var_name'],None,f['target'],f['code']))
        for cond in ext['target_conditions']:
            if any(x in cond['condition'] for x in ['goto','return','while']):continue
            try:result={'called_function':called_function(f['var_name'],cond['condition'])}
            except Exception as exc:result={'error':type(exc).__name__+': '+str(exc)}
            preflight.append({'frame':f['level'],'function':f['function'],'tracked':f['var_name'],'condition':cond,**result})
    first=candidate['frames'][0];second=candidate['frames'][1]
    write('A05_block_location.json',{'note':'repo.prepare succeeds; engine.prepare additionally scans conditions and blocks. This is not a demonstrated parameter-position error.',
         'chain_transition_parameter_check':parameter_name(first['var_name'],first['target'],second['code']),
         'condition_preflight_diagnostic':preflight})

    formula_probes=[]
    def solve_text(path):
        q=read(path)['queries'][-1];s=z3.Solver();s.set(timeout=5000);s.from_string(q['smt2']);return s
    a=solve_text(HERE/'samples/A01/recorded_raw/solver_01.json')
    copied=z3.Int('copied');skb=z3.Int('skb');s=z3.Solver();s.add(skb==0,copied==0)
    formula_probes.append({'id':'A01','original_query':str(a.check()),'diagnostic_query':str(s.check()),
        'change':'Only use correct branch predicate copied==0 instead of both copied!=0 and copied==0; no full C execution proof or changed prediction'})
    b=solve_text(HERE/'samples/A03/recorded_raw/solver_01.json');before=str(b.check())
    b.add(z3.Int('elem_type')!=z3.Int('TYPE_END'),z3.Int('elem_type')<z3.Int('TYPE_DSE'))
    formula_probes.append({'id':'A03','original_query':before,'diagnostic_query':str(b.check()),
        'change':'Add the omitted loop and branch-order assumptions; relation TYPE_SCE/TYPE_LFE < TYPE_DSE still requires actual enum definition to establish, not guessed as ground truth'})
    c=solve_text(HERE/'samples/A04/recorded_raw/solver_04.json');before=str(c.check())
    c.add(z3.Int('object')==z3.Int('object_ptr'),z3.Int('object')==z3.BV2Int(z3.BitVec('object_bv',64)))
    formula_probes.append({'id':'A04','original_query':before,'diagnostic_query':str(c.check()),
        'change':'Connect renamed Int and BitVec representations of the same pointer; diagnostic identity equalities only, no recorded prediction edits'})
    write('formula_probes.json',formula_probes)

    pop=read(HERE/'population_diagnostics.json')
    entries=[]
    env={k:v for k,v in os.environ.items() if not any(t in k.upper() for t in ['KEY','TOKEN','SECRET','PASSWORD'])}
    for e in pop['solver_query_replays']:
        if e['matches'] is not None:continue
        saved=read(ROOT/e['file'])
        declarations=re.findall(r'^\(declare-fun\s+([^\s()]+)\s+\(\)\s+(.+)\)$',saved['queries'][e['query']-1]['smt2'],re.M)
        names=defaultdict(set)
        for name,sort in declarations:names[name].add(sort)
        ambiguous={k:sorted(v) for k,v in names.items() if len(v)>1}
        run=subprocess.run([sys.executable,'-I','-B',str(ROOT/'completion/solver_worker.py')],input=json.dumps({'source':saved['source']}),
                           capture_output=True,text=True,encoding='utf-8',env=env,timeout=15)
        result=json.loads(run.stdout)
        entries.append({'sample_id':e['sample_id'],'file':e['file'],'same_name_different_sorts':ambiguous,
                        'offline_original_worker_replay':result,'matches_recorded_feasible':result.get('feasible')==saved['feasible'],
                        'interpretation':'Replay confirms execution, not semantic correctness. Same C entity split into sorts is a candidate/confirmed encoding defect depending on source identity.'})
    write('same_symbol_sort_audit.json',entries)

    rows=read(ROOT/'results/processed/expanded_all_npd.json')
    patterns=[];stats=Counter();json_failures=[]
    all_calls=[read(p) for p in sorted((ROOT/'results/raw/completed/calls').glob('*.json'))]
    for r in rows:
        path=ROOT/r['raw_output']/'context.json'
        if path.exists():
            for f in read(path)['frames']:
                nonempty=[line for line in f['code'].splitlines() if line.strip()]
                tabs=any(line.startswith('\t') for line in nonempty)
                spaces=any(line.startswith('    ') for line in nonempty)
                mode='spaces_only' if spaces and not tabs else 'has_tabs' if tabs else 'no_indentation'
                same=[i+1 for i,line in enumerate(f['code'].splitlines()) if f['target'] in line]
                info={'sample_id':r['sample_id'],'frame':f['level'],'indentation':mode,
                      'target_conditions_empty':not f['extracted']['target_conditions'],'matching_target_lines':same}
                patterns.append(info);stats[(mode,'total')]+=1
                if info['target_conditions_empty']:stats[(mode,'empty_target_conditions')]+=1
                if len(same)>1:stats[('all','duplicate_target_text')]+=1
        if r['status']=='failed' and 'JSONDecodeError' in r['error']:
            cs=[c for c in all_calls if c['sample_id']==r['sample_id']][-r['api_calls']:]
            last=cs[-1];text=last['choices'][0]['message']['content'];fences=re.findall(r'```([^\n`]*)',text)
            json_match=re.search(r'```json\s*(.*?)```',text,re.S)
            try:embedded=json.loads(json_match[1]) if json_match else None
            except Exception:embedded=None
            json_failures.append({'sample_id':r['sample_id'],'last_call_id':last['call_id'],'fence_headers':fences,
                'valid_explicit_json_array_later':isinstance(embedded,list) and all(isinstance(x,str) for x in embedded),
                'array':embedded,'note':'Read-only language-specific parse diagnostic, not a reclassification or automatic repair'})
    write('extraction_population_patterns.json',{'counts':{'|'.join(k):v for k,v in stats.items()},'frames':patterns})
    write('format_failures_audit.json',json_failures)
    write('checkpoint_03_probes.json',{'model_calls':0,'diagnostic_probes_only':True,'production_modified':False,
            'indentation_probes':len(probes),'formula_probes':len(formula_probes),'worker_replays':len(entries),
            'original_prediction_recomputed':False,'initial_SMT2_reload_issue':'7 mixed-sort name overloads could not be parsed directly; handled by original restricted worker replay, raw text untouched'})
    print(json.dumps({'indentation':probes,'A05':read(HERE/'A05_block_location.json'),'formulas':formula_probes,
                     'population_indent':{'|'.join(k):v for k,v in stats.items()},'format':json_failures,
                     'mixed_sort_count':len(entries),'worker_replay_all_match':all(e['matches_recorded_feasible'] for e in entries)},ensure_ascii=True,indent=2))

if __name__=='__main__':main()
