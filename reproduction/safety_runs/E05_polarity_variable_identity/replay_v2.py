"""Hash-verified historical static replay. Never execute saved generated code.

The same generic adapter processes all samples. Labels/IDs are bookkeeping
only; no semantic rule dispatches on any sample ID or function name.
"""
import ast
from collections import Counter
import datetime
import json
from pathlib import Path
import re
import sys
import time

import offline_boundary
offline_boundary.install()
from dependencies import ROOT, PINS, load
from semantics import Source, Unsupported, check_polarity, member_collapse_diagnostics, sha

HERE = Path(__file__).resolve().parent
E02 = ROOT / 'safety_runs/E02_base_constraint_preservation_static'
ND = ROOT / 'safety_runs/E04_nonempty_delta_validation'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def digest(path):
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    with path.open('x', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write('\n')


def verified(path):
    baseline = read(HERE / 'baseline_state.json')['protected_files']
    relative = path.relative_to(ROOT).as_posix()
    if relative not in baseline or digest(path) != baseline[relative]:
        raise RuntimeError('STOP: unverified historical source ' + relative)
    return path


def assert_frozen():
    freeze = read(HERE / 'candidate_freeze_v2.json')
    for relative, expected in freeze['sha256'].items():
        if digest(ROOT / relative) != expected:
            raise RuntimeError('STOP: frozen input changed ' + relative)


def code_atoms(script):
    """Read add() atoms without running expressions. Keep every original input."""
    try:
        code = load('e02').code_block(script)
        tree = ast.parse(code)
    except (SyntaxError, ValueError) as exc:
        return [], ['unparseable_model_script:' + str(exc)]
    if any(isinstance(n, (ast.If, ast.For, ast.While, ast.Try, ast.With, ast.Lambda)) for n in ast.walk(tree)):
        return [], ['model_control_flow_unsupported']
    declarations = {}
    counts = Counter()
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name):
                    counts[t.id] += 1
            if (len(n.targets)==1 and isinstance(n.targets[0],ast.Name) and
                isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Name) and
                n.value.func.id in ('Int','Bool','BitVec') and n.value.args and
                isinstance(n.value.args[0],ast.Constant) and isinstance(n.value.args[0].value,str)):
                declarations[n.targets[0].id] = (n.value.args[0].value,n.value.func.id)
    result=[]

    def add(node, line):
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='And':
            for arg in node.args:
                add(arg,line)
        else:
            names=sorted({n.id for n in ast.walk(node) if isinstance(n,ast.Name)}-{'Not','And','Or','True','False'})
            # A diagnostic association requires a single declared unchanged name.
            result.append({'expression':ast.unparse(node),'generated_line':line,'names':names,
                'binding': declarations.get(names[0]) if len(names)==1 and counts[names[0]]==1 else None,
                'response_sha256':sha(script)})
    for n in ast.walk(tree):
        if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='add':
            for arg in n.args:
                add(arg,n.lineno)
    return result, []


def frame_semantics(frame, scripts, reference):
    code=frame['code']; findings=[]; uncertainties=[]; polarities=[]; identities=[]
    try:
        source=Source(code,frame['function'],reference,frame.get('body_sha256'))
    except Unsupported as exc:
        return {'status':'UNKNOWN','reason':str(exc),'findings':[], 'whole_context_verified':False}
    targets=[i for i,line in enumerate(code.splitlines(),1) if line.strip()==frame['target'].strip()]
    entries=(frame.get('extracted') or {}).get('target_conditions',[])
    local_specs=[]
    if len(targets)!=1:
        uncertainties.append('target_location_missing_or_ambiguous')
    for entry in entries:
        raw=entry.get('condition','')
        m=re.fullmatch(r'\s*if\s*\((.*)\)\s*',raw)
        if not m:
            uncertainties.append('recorded_condition_not_simple_if:'+raw)
            continue
        # Find exact raw guard in real saved body. Record historical line separately.
        canonical=re.sub(r'\s+','',raw)
        hits=[i for i,line in enumerate(code.splitlines(),1)
              if re.sub(r'\s+','',line.strip().removesuffix('{'))==canonical]
        if len(hits)!=1 or len(targets)!=1:
            uncertainties.append('source_guard_not_uniquely_bound:'+raw)
            continue
        try:
            scalar=load('e01').normalize_c(m[1],True)
        except load('e01').Unsupported as exc:
            uncertainties.append(str(exc)+':'+raw)
            continue
        # Never confuse the injected null-pointer bug hypothesis with a path guard.
        if scalar['variable']==frame.get('var_name'):
            uncertainties.append('target_bug_assumption_and_guard_provenance_ambiguous')
            continue
        local_specs.append((entry,hits[0],targets[0],scalar))
    multiplicity=Counter(spec[3]['variable'] for spec in local_specs)
    for role,script,script_ref in scripts:
        if role!='B':
            # Later stages can encode different time states. Do not bind their
            # same-name atoms to the sink guard without state provenance.
            continue
        atoms,reasons=code_atoms(script); uncertainties.extend(reasons)
        for entry,guard,target,scalar in local_specs:
            bound=[]
            if multiplicity[scalar['variable']]==1:
                bound=[a for a in atoms if a['names']==[scalar['variable']] and
                       a['binding'] and a['binding'][0]==scalar['variable']]
            if not bound:
                uncertainties.append('no_unique_U02_condition_atom:'+scalar['variable'])
            for atom in bound:
                result=check_polarity(source,guard,target,True,atom['expression'],
                    sort=atom['binding'][1],target_text=frame['target'],
                    context_reasons=['historical_whole_context_unverified','assertion_role_diagnostic_association_only'])
                result.update(model_source=script_ref,raw_response_sha256=sha(script),
                    generated_line=atom['generated_line'],original_recorded_condition=entry,
                    actual_guard_body_line=guard,
                    provenance_basis='unique source guard + same-name explicit U02 declaration; diagnostic association, not author-provided assertion map')
                polarities.append(result)
                if result['local_status']=='REJECT':
                    findings.append({'category':'polarity','codes':result['reasons'],
                                     'model_source':script_ref,'guard_line':guard})
    base=next((s for role,s,ref in scripts if role=='B'),None)
    inherited=None
    if base:
        try:
            inherited=load('e02')._parse(base,'python','U02/raw').env()
        except load('e02').Unsupported as exc:
            uncertainties.append('base_parse:'+str(exc))
    for role,script,ref in scripts:
        if role not in ('B','delta'):
            continue
        result=member_collapse_diagnostics(source,script,inherited)
        result.update(role=role,model_source=ref,raw_response_sha256=sha(script))
        identities.append(result)
        if result['findings']:
            findings.append({'category':'identity','codes':['pointer_member_identity_collapse'],
                             'model_source':ref,'witnesses':result['findings']})
    return {'status':'REJECT' if findings else 'UNKNOWN','polarity_checks':polarities,
            'identity_checks':identities,'findings':findings,
            'uncertainties':sorted(set(uncertainties+['full_C_state_types_control_and_provenance_not_proven'])),
            'source_reference':reference,'source_sha256':source.digest,'source_declarations':source.declarations,
            'whole_context_verified':False,'assertions_removed':0,'alert_safety_decision':None}


def structural_checks(directory):
    results=[]; scripts_by_frame={}
    for path in sorted((directory/'contracts').glob('*.json')):
        verified(path); c=read(path)
        if not all(k in c for k in ('B','delta','Final')):
            raise RuntimeError('STOP: historical contract schema unconfirmed')
        refs=c.get('references', ['B','delta','Final'])
        result=load('e02').check_contract(c['B'],c['delta'],c['Final'],
                formats=tuple(c.get('formats',('python',)*3)),refs=tuple(refs),extra_deltas=c.get('extra_deltas',[]))
        results.append({'input':path.relative_to(ROOT).as_posix(),'input_sha256':digest(path),
                        'result':result})
        m=re.fullmatch(r'frame/(\d+)/U02',refs[0]); frame=int(m[1]) if m else None
        if frame is not None:
            values=scripts_by_frame.setdefault(frame,{})
            for role,field,ref in [('B','B',refs[0]),('delta','delta',refs[1])]:
                if isinstance(c[field],str):
                    values.setdefault((role,sha(c[field])),(role,c[field],ref))
    return results,{f:list(v.values()) for f,v in scripts_by_frame.items()}


def sample(directory, manifest_row, original_e02_row):
    start=time.perf_counter(); path=verified(directory/'bundle.json'); bundle=read(path)
    sid=bundle.get('candidate',{}).get('sample_id')
    if sid!=manifest_row['sample_id'] or sid!=original_e02_row['sample_id']:
        raise RuntimeError('STOP: fixed sample identity mismatch')
    structural,scripts=structural_checks(directory)
    frames=[]
    for i,frame in enumerate((bundle.get('context') or {}).get('frames',[])):
        frames.append(frame_semantics(frame,scripts.get(i,[]),path.relative_to(ROOT).as_posix()+f'#/context/frames/{i}'))
    findings=[x for f in frames for x in f['findings']]
    return {'sample_id':sid,'dataset_label':manifest_row.get('dataset_label',manifest_row.get('label')),
        'label_use':'metadata only; published labels not individually verified; never used by checks',
        'diagnostic_status':'REJECT' if findings else 'UNKNOWN','frames':frames,'structural_checks':structural,
        'bundle_sha256':digest(path),'bundle_reference':path.relative_to(ROOT).as_posix(),
        'local_findings':findings,'whole_context_verified':False,'alert_safety_decision':None,
        'seconds':time.perf_counter()-start,'model_calls':0,'z3_calls':0,'assertions_removed':0}


def audit_and_nd():
    assert_frozen()
    save(HERE/'historical_attempt02_started.json',{'started_at':datetime.datetime.now(datetime.timezone.utc).isoformat()})
    original=read(verified(E02/'audit_10_results.json'))['rows']
    manifest=read(verified(ROOT/'audit/failure_audit_20261029/audit_samples.json'))
    rows=manifest['samples'] if isinstance(manifest,dict) else manifest
    if len(rows)!=10 or len(original)!=10:
        raise RuntimeError('STOP: audit manifest size changed')
    results=[sample(E02/'evidence/audit_10_frozen_candidate'/f'{i:02}',row,old)
             for i,(row,old) in enumerate(zip(rows,original),1)]
    source_path=verified(ND/'selected_source.c'); m=read(verified(ND/'sample_manifest.json'))
    selected=read(verified(ND/'selected_sample.json')); frame=m['frames'][m['historical_target_frame']]
    frame=dict(frame,code=source_path.read_text(encoding='utf-8'),extracted={'target_conditions':[]})
    # Read source guards generically; use the original U02 request to bind which
    # saved guard was actually converted. No invented assertion or ID special case.
    calls={}
    for path in sorted((ND/'model_calls').glob('*.json')):
        verified(path); d=read(path)
        if d.get('e04_stage') in ('U02','U06','U10'):
            calls[d['e04_stage']]=(d,path)
    u02,p02=calls['U02']; content=u02['messages'][0]['content']
    found=re.findall(r"'condition':\s*'(if\s*\([^'\n]+\))'\s*,\s*'line_number':\s*(\d+)",content)
    frame['extracted']['target_conditions']=[{'condition':x,'line_number':int(y)} for x,y in found]
    scripts=[('B',calls['U02'][0]['choices'][0]['message']['content'],calls['U02'][1].relative_to(ROOT).as_posix()),
             ('delta',calls['U06'][0]['choices'][0]['message']['content'],calls['U06'][1].relative_to(ROOT).as_posix())]
    final=calls['U10'][0]['choices'][0]['message']['content']
    structural=load('e03').validate_base_delta(scripts[0][1],scripts[1][1],final)
    nd={'sample_id':m['sample_id'],'dataset':m['dataset'],'position':m['position'],
        'frame':frame_semantics(frame,scripts,source_path.relative_to(ROOT).as_posix()),
        'original_U02_guard_records':frame['extracted']['target_conditions'],
        'structural_check':structural,'original_selected_sample':selected,
        'response_hashes':{k:sha(v[0]['choices'][0]['message']['content']) for k,v in calls.items()},
        'model_calls':0,'z3_calls':0,'alert_safety_decision':None}
    save(HERE/'historical_replay.json',{'audit_10':results,'E04_ND':nd,'scope':'offline cached data only',
                                      'boundary_attempts':offline_boundary.ATTEMPTS})
    print('audit10',dict(Counter(x['diagnostic_status'] for x in results)))
    print('ND local findings',[(x['category'],x['codes']) for x in nd['frame']['findings']])


def fixed():
    assert_frozen()
    if not (HERE/'historical_replay.json').is_file():
        raise RuntimeError('STOP: historical replay must precede fixed regression')
    save(HERE/'fixed_20_started.json',{'started_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'run_count':1,'candidate_sha256':digest(HERE/'candidate_freeze_v2.json'),'no_post_result_tuning':True})
    original=read(verified(E02/'fixed_20_results.json'))['rows']
    manifest=read(verified(ROOT/'safety_runs/20261029_v1/fixed_holdout.json'))
    if len(original)!=20 or len(manifest['samples'])!=20:
        raise RuntimeError('STOP: fixed set size changed')
    results=[sample(E02/'evidence/fixed_20_frozen_candidate'/f'{i:02}',row,old)
             for i,(row,old) in enumerate(zip(manifest['samples'],original),1)]
    save(HERE/'fixed_holdout_results.json',{'sample_count':20,'seed':manifest['seed'],
        'scope':'previously encountered fixed regression, not blind','rows':results,
        'boundary_attempts':offline_boundary.ATTEMPTS,'model_calls':0,'z3_calls':0,'cost_cny':0})
    print('fixed20',dict(Counter(x['diagnostic_status'] for x in results)))


if __name__=='__main__':
    {'historical':audit_and_nd,'fixed20':fixed}[sys.argv[1]]()
