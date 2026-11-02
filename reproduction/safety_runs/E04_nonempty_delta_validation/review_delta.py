"""Post-run evidence extraction, not a program-semantic checker or a repair.

Canonical assertions come from the unchanged E02 IR. AST is used only to copy
their original text/line spans; none of the model's Python is executed.
"""
import ast
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load(name):
    return json.loads((HERE/name).read_text(encoding='utf-8'))


def sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def put(name, value):
    with (HERE/name).open('x',encoding='utf-8',newline='\n') as handle:
        json.dump(value,handle,ensure_ascii=False,indent=2)
        handle.write('\n')


def execute():
    bundle = load('constraint_transfer/base_delta_bundle.json')
    post = load('constraint_transfer/U10_postcondition.json')
    assembly = bundle['assembly_audit']
    ir = assembly['check_contract']['ir']
    delta = bundle['delta']['code_text']
    source = (HERE/'selected_source.c').read_text(encoding='utf-8')
    manifest = load('sample_manifest.json')
    assert sha(source)==manifest['target_frame']['body_sha256']
    source_lines = source.splitlines(keepends=True)
    tree = ast.parse(delta)  # text extraction only; no eval/exec
    nodes = {node.lineno:node for node in ast.walk(tree) if isinstance(node,ast.Call)
             and isinstance(node.func,ast.Attribute) and node.func.attr=='add'}
    baseline = {a['formula'] for a in ir['B']['assertions']}
    final = {a['formula'] for a in post['check_contract']['ir']['Final']['assertions']}
    body_sha = sha(source)

    def source_ref(first,last,explanation):
        snippet=''.join(source_lines[first-1:last])
        return {'file':'selected_source.c','body_sha256':body_sha,
                'body_lines_1based':[first,last],'snippet':snippet,
                'snippet_sha256':sha(snippet),'explanation':explanation,
                'scope':'published benchmark/historical function text, not independently verified original build evidence'}

    # These are explicit post-run source-text observations for this experiment.
    # They do not influence the already completed requests, prompts or checks.
    observations = [
        {'sources':[source_ref(175,178,'C branch assigns skb->len - maxfraglen or zero'),
                    source_ref(180,185,'maxfraglen may be modified and skb_prev is assigned old skb'),
                    source_ref(239,252,'skb is reassigned and checked before the target')],
         'source_fidelity':'KNOWN_FIELD_AND_STATE_MODELING_DEFECT',
         'observation':'The generated expression uses skb - maxfraglen instead of skb->len - maxfraglen. It also reuses one skb symbol across reassignment. Source association exists; faithful semantics is not established.'},
        {'sources':[source_ref(170,170,'fraggap has explicit unsigned int declaration'),
                    source_ref(271,275,'target lies inside the true branch of if (fraggap)')],
         'source_fidelity':'DIRECT_LOCAL_TRUE_BRANCH_TEXT_SUPPORTED',
         'observation':'fraggap != 0 matches this local true branch. This is a source-text correspondence, not complete C path or polarity certification.'},
        {'sources':[source_ref(251,252,'if (!skb) goto error precedes target'),
                    source_ref(271,275,'target after the allocation/null check'),
                    source_ref(175,185,'prior skb and skb_prev identities differ before reassignment')],
         'source_fidelity':'LOCAL_EXIT_TEXT_SUPPORTED_WITH_UNRESOLVED_STATE_IDENTITY',
         'observation':'The local early-exit check supports non-NULL current skb, but the model comment derives it from an earlier value. No SSA/state identity proof was performed.'},
    ]
    assertions = ir['delta']['assertions']
    assert len(assertions)==len(observations)==3
    items=[]
    for number,(assertion,observation) in enumerate(zip(assertions,observations),1):
        node=nodes[assertion['origin']['line']]
        original=ast.get_source_segment(delta,node)
        assert original is not None
        items.append({'assertion_id':f'ND{number:02d}','call_id':1194,
             'raw_U06_response_sha256':bundle['delta_sha256'],
             'delta_code_sha256':bundle['delta']['code_sha256'],
             'delta_body_lines_1based':[node.lineno,node.end_lineno],
             'original_assertion_text':original,'assertion_text_sha256':sha(original),
             'E02_formula':assertion['formula'],'formula_sha256':sha(assertion['formula']),
             'absent_from_B_exact_members':assertion['formula'] not in baseline,
             'present_in_U10_output_exact_members':assertion['formula'] in final,
             **observation})
    # A literal nonzero branch is a nontrivial new restriction here: B's only
    # fraggap member is the tautology Or(fraggap == 0, fraggap != 0).
    assert '(or (= fraggap 0) (distinct fraggap 0))' in baseline
    direct=next(a for a in items if a['E02_formula']=='(distinct fraggap 0)')
    assert direct['absent_from_B_exact_members']
    assert all(a['present_in_U10_output_exact_members'] for a in items)
    put('constraint_transfer/new_assertions.json',{
        'method':'E02 parsed IR + original code-span copy + explicit post-run source-text review',
        'review_is_not_independent_human_semantic_proof':True,
        'novel_assertion_count':sum(a['absent_from_B_exact_members'] for a in items),
        'at_least_one_nontrivial_source_anchored_assertion':True,
        'nontriviality_note':'B allows fraggap=0 through a tautological disjunction; the new fraggap!=0 excludes zero. No solver was used for this elementary observation.',
        'assertions':items})
    put('acceptance.json',{
        'real_U02':True,'real_U06':True,'real_U10':True,
        'delta_assertions':3,'novel_exact_assertion_members':3,
        'at_least_one_nontrivial_assertion_with_direct_source_basis':True,
        'assembly_status':assembly['contract_status'],'output_status':post['contract_status'],
        'actual_U10_payload_complete':load('constraint_transfer/request_response_verification.json')['actual_U10_contains_exact_merged_script'],
        'known_structural_duplicates_or_type_identity_conflicts':False,
        'logical_consistency':'NOT_SOLVED',
        'known_source_semantic_defects':[
            'U02 weakens if(fraggap) into a tautological Or',
            'U06 conflates skb pointer with skb->len and skb versions'],
        'all_delta_assertions_proven_faithful_to_source':False,
        'outcome':'NONEMPTY_STRUCTURAL_TRANSFER_VERIFIED_WITH_SEMANTIC_DEFECTS',
        'semantic_correctness':'NOT_ASSESSED_BY_E02_E03; known text-level defects recorded',
        'polarity_correctness':'NOT_ASSESSED',
        'z3_runs':0,'generated_code_executions':0,'safety_decisions':0})
    print(json.dumps({'nonempty_new_assertions':len(items),'direct_local_source_assertion':direct['original_assertion_text'],
                      'output_members_preserved':True,'known_semantic_defect':'skb used in place of skb->len','z3_runs':0}))


if __name__=='__main__':
    execute()
