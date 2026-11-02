"""Parameterized synthetic AST contracts; never execute fixture C."""
import argparse
import copy
import json
from pathlib import Path
import time

import offline_boundary
from mapper import ROOT, analyze, digest, verify_proposal


def proposal(call):
    return [{'actual_index_0based': m['actual_index_0based'],
             'formal_index_0based': m['formal_index_0based'],
             'actual_slot_id': m['actual_slot_id'], 'formal_slot_id': m['formal_slot_id'],
             'conversion_kind': m['conversion']['kind']} for m in call['mappings']]


def run(output):
    output.mkdir(exist_ok=False, parents=True)
    offline_boundary.install()
    started = time.perf_counter()
    rows = []

    def record(name, expected, actual, passed, evidence):
        rows.append({'test': name, 'expected': expected, 'actual': actual,
                     'passed': bool(passed), 'evidence': evidence})

    def check(name, fixture, expected='PASS', extra=()):
        path = ROOT / 'fixtures' / fixture
        report = analyze(path, dataset_id='synthetic-r01', position=0,
                         build_status='synthetic-self-contained',
                         candidate_source_paths=[ROOT / 'fixtures' / p for p in extra])
        (output / (name+'.json')).write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
        record(name, expected, report['status'], report['status'] == expected,
               {'fixture': fixture, 'source_sha256': digest(path.read_bytes()),
                'report': name+'.json'})
        return report

    r = check('M01_direct', 'M01.c')
    m = r['calls'][0]['mappings'][0]
    record('M01_distinct_slots', 'different caller/formal slots',
           [m['actual_slot_id'], m['formal_slot_id']],
           m['actual_slot_id'] != m['formal_slot_id'], m)
    for suffix in ['struct', 'widen', 'const']:
        r = check('M01_'+suffix, 'M01_'+suffix+'.c')
        conv = r['calls'][0]['mappings'][0]['conversion']
        expected_conversion = {'struct': 'identity', 'widen': 'signed_integer_widening',
                               'const': 'pointee_const_addition'}[suffix]
        record('M01_'+suffix+'_conversion_evidence', expected_conversion, conv['kind'],
               conv['kind']==expected_conversion, conv)
    c = check('M02_reference', 'M02.c')['calls'][0]
    p = proposal(c)
    p[0]['formal_index_0based'], p[1]['formal_index_0based'] = 1, 0
    v = verify_proposal(c, p)
    record('M02_swapped_indexes', 'REJECT', v['status'], v['status'] == 'REJECT', v)
    good = verify_proposal(c, proposal(c))
    record('M02_correct_proposal', 'PASS', good['status'], good['status'] == 'PASS', good)
    r = check('M03_scope_binding', 'M03.c')
    ms = [c['mappings'][0] for c in r['calls']]
    slots = [m['actual_slot_id'] for m in ms]
    record('M03_scope_isolation', '3 distinct actual slots, one declared formal slot',
           slots, len(slots) == len(set(slots)) == 3 and
           len({m['formal_slot_id'] for m in ms}) == 1,
           {'mappings': ms, 'meaning': 'formal lexical slot reused with separate callsite transfers'})
    wrong = proposal(r['calls'][1]); wrong[0]['actual_slot_id'] = slots[0]
    v = verify_proposal(r['calls'][1], wrong)
    record('M03_wrong_scope_candidate', 'REJECT', v['status'], v['status']=='REJECT', v)
    c = check('M04_duplicate_actual', 'M04.c')['calls'][0]
    a, b = c['mappings']
    record('M04_formals_not_merged', 'same actual, distinct formals/transfers', c['status'],
           a['actual_slot_id'] == b['actual_slot_id'] and
           a['formal_slot_id'] != b['formal_slot_id'] and a['transfer_id'] != b['transfer_id'], c)
    wrong = proposal(c); wrong[1]['formal_slot_id'] = wrong[0]['formal_slot_id']
    v = verify_proposal(c, wrong)
    record('M04_merged_formal_candidate', 'REJECT', v['status'], v['status']=='REJECT', v)
    for suffix in ['narrow', 'cast', 'invalid', 'void', 'distinct_struct']:
        r = check('M05_'+suffix, 'M05_'+suffix+'.c', 'UNKNOWN')
        if r['diagnostics']:
            clean = all(not call['mappings'] and not call['ast_is_trusted'] for call in r['calls'])
            record('M05_'+suffix+'_no_recovery_approval', 'no mappings trusted', clean,
                   clean, {'diagnostics': r['diagnostics']})
    v = verify_proposal(c, [{'actual_index_0based': 0}])
    record('M05_missing_evidence', 'UNKNOWN', v['status'], v['status']=='UNKNOWN', v)
    p = proposal(c); p[0]['conversion_kind'] = 'invented_cast'
    v = verify_proposal(c, p)
    record('M05_false_conversion_claim', 'REJECT', v['status'], v['status']=='REJECT', v)
    check('M06_missing', 'M06_missing.c', 'UNKNOWN')
    r = check('M06_ambiguous', 'M06_missing.c', 'UNKNOWN',
              extra=['M06_definition_one.c', 'M06_definition_two.c'])
    record('M06_detect_ambiguity', 'multiple_definition_candidates',
           r['calls'][0]['reasons'], 'multiple_definition_candidates' in r['calls'][0]['reasons'],
           r['candidate_inventory'])
    for suffix in ['pointer', 'callback', 'macro']:
        r = check('M07_'+suffix, 'M07_'+suffix+'.c', 'UNKNOWN')
        if suffix=='macro':
            record('M07_macro_expansion_evidence', 'expansion recorded, no mappings',
                   bool(r['macro_expansions']), bool(r['macro_expansions']) and
                   all(not c['mappings'] for c in r['calls']), r)
    for suffix in ['byvalue', 'member', 'address']:
        check('M08_'+suffix, 'M08_'+suffix+'.c', 'UNKNOWN')
    # No build assertion can upgrade a historical fragment into a verified TU.
    p = ROOT / 'fixtures/M01.c'
    r = analyze(p, dataset_id='history-negative', position=3, build_status='saved-source-only')
    record('G01_build_missing', 'UNKNOWN', r['status'], r['status']=='UNKNOWN', r)
    r1 = analyze(p, dataset_id='repeat', position=0, build_status='synthetic-self-contained')
    r2 = analyze(p, dataset_id='repeat', position=0, build_status='synthetic-self-contained')
    r1.pop('elapsed_seconds'); r2.pop('elapsed_seconds')
    record('G02_repeatability', 'identical semantic output', r1 == r2, r1==r2,
           {'first': r1, 'second': r2})
    invalid_inputs = [(None, 0), ('x', -1), ('x', True)]
    for i, (dataset, position) in enumerate(invalid_inputs):
        caught = False
        try:
            analyze(p, dataset_id=dataset, position=position, build_status='synthetic-self-contained')
        except ValueError:
            caught = True
        record('G03_invalid_input_'+str(i), 'ValueError', caught, caught,
               {'dataset_id': dataset, 'position': position})
    result = {'tests': rows, 'passed': sum(r['passed'] for r in rows), 'total': len(rows),
              'all_passed': all(r['passed'] for r in rows),
              'elapsed_seconds': time.perf_counter()-started,
              'external_operations': offline_boundary.EVENTS,
              'LLM_calls': 0, 'Z3_calls': 0, 'C_runtime_executions': 0}
    (output / 'test_results.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({k: v for k,v in result.items() if k != 'tests'}))
    if not result['all_passed']:
        print(json.dumps([r for r in rows if not r['passed']], ensure_ascii=True))
        raise SystemExit(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args().output)
