"""Read immutable saved sources; no legacy code execution, model or SMT import."""
import argparse
from collections import Counter
import datetime
import json
from pathlib import Path
import re
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parent
CORE_ROOT = ROOT.parent/'E06_R01_direct_call_argument_mapping'
sys.path.insert(0, str(CORE_ROOT))
import offline_boundary
from mapper import analyze, digest

REPRO = ROOT.parents[1]
FIXED = 'safety_runs/20261029_v1/fixed_holdout.json'
FIXED_HASH = 'c4ef793abe5f00437f52c27b6fe545dfa613ed661eb441362e1315f1ed98243d'
AUDIT = 'audit/failure_audit_20261029/audit_samples.json'
AUDIT_HASH = '6980a64dd1d499188ccc83002bfdf3255196f1c17e462eaab44d83db67aa366b'
INVENTORY = 'safety_runs/E06_design/candidate_inventory.json'


class DataShapeError(ValueError):
    """Malformed evidence is an operational error, never a mapping verdict."""


def context_state(bundle, null_provenance=None):
    """Do not coerce missing/null/objects/arrays to a shared default container."""
    if not isinstance(bundle, dict) or 'context' not in bundle:
        raise DataShapeError('CONTEXT_FIELD_MISSING')
    context = bundle['context']
    if context is None:
        candidate = bundle.get('candidate')
        p = null_provenance
        if (not isinstance(candidate, dict) or not isinstance(p, dict) or
            p.get('verified') is not True or p.get('context_file_absent') is not True or
            candidate.get('status') != 'blocked_context' or
            p.get('historical_status') != candidate.get('status') or
            not isinstance(candidate.get('error'), str) or not candidate['error'] or
            p.get('historical_error') != candidate['error']):
            raise DataShapeError('NULL_CONTEXT_WITHOUT_VERIFIED_ABSENCE_PROVENANCE')
        return 'EXPLICIT_NULL_SAVED_CONTEXT_UNAVAILABLE', None
    if not isinstance(context, dict):
        raise DataShapeError('CONTEXT_MUST_BE_OBJECT_OR_PROVEN_ABSENT_NULL')
    if 'frames' not in context:
        raise DataShapeError('FRAMES_FIELD_MISSING')
    frames = context['frames']
    if not isinstance(frames, list):
        raise DataShapeError('FRAMES_MUST_BE_ARRAY')
    for i, frame in enumerate(frames):
        if not isinstance(frame, dict):
            raise DataShapeError(f'FRAME_{i}_MUST_BE_OBJECT')
        for key in ('function', 'code', 'body_sha256'):
            if not isinstance(frame.get(key), str) or not frame[key]:
                raise DataShapeError(f'FRAME_{i}_INVALID_{key}')
        if digest(frame['code'].encode('utf-8')) != frame['body_sha256']:
            raise DataShapeError(f'FRAME_{i}_BODY_HASH_MISMATCH')
    return ('EMPTY_FRAMES_ARRAY' if not frames else 'FRAMES_PRESENT'), frames


def null_context_provenance(spec, bundle, baseline):
    """Verify the existing exporter's absent-file convention, no recovery attempt."""
    def checked_read(rel):
        path = REPRO/rel
        if digest(path.read_bytes()) != baseline['protected_files_sha256'][rel]:
            raise RuntimeError('Protected null provenance changed: '+rel)
        return json.loads(path.read_text('utf-8'))
    bindings_rel = 'safety_runs/20261029_v1/offline_regression/evidence_bindings.json'
    matches = [b for b in checked_read(bindings_rel) if b['sample_id']==spec['sample_id']]
    if len(matches) != 1:
        raise DataShapeError('NULL_CONTEXT_BINDING_NOT_UNIQUE')
    binding = matches[0]
    canonical = json.dumps(bundle, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()
    if digest(canonical) != binding['evidence_sha256']:
        raise DataShapeError('NULL_CONTEXT_BUNDLE_BINDING_MISMATCH')
    results = [n for n in binding['artifact_sha256'] if n.endswith('/sample_result.json')]
    if len(results) != 1:
        raise DataShapeError('NULL_CONTEXT_RAW_RESULT_NOT_UNIQUE')
    for rel, expected in binding['artifact_sha256'].items():
        if digest((REPRO/rel).read_bytes()) != expected:
            raise RuntimeError('Historical null provenance changed: '+rel)
    raw = checked_read(results[0])
    raw_file = REPRO/results[0]
    context_file = raw_file.parent/'context.json'
    if (raw['sample_id'] != spec['sample_id'] or raw['status'] != 'blocked_context' or
        raw['error'] != bundle['candidate']['error'] or context_file.exists()):
        raise DataShapeError('NULL_CONTEXT_ABSENCE_OR_STATUS_NOT_CONFIRMED')
    return {'verified': True, 'context_file_absent': True,
            'context_file': context_file.relative_to(REPRO).as_posix(),
            'historical_status': raw['status'], 'historical_error': raw['error'],
            'raw_sample_result': results[0], 'raw_sample_result_sha256': digest(raw_file.read_bytes()),
            'evidence_binding': bindings_rel, 'canonical_bundle_sha256': digest(canonical),
            'exporter': 'safety/replay.py:59',
            'exporter_sha256': baseline['protected_files_sha256']['safety/replay.py']}


def save(path, data):
    with path.open('x', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(data, ensure_ascii=False, indent=2)+'\n')


def verify_existing():
    baseline = json.loads((ROOT/'baseline_state.json').read_text('utf-8'))
    bad = [n for n,h in baseline['protected_files_sha256'].items()
           if not (REPRO/n).is_file() or digest((REPRO/n).read_bytes()) != h]
    if bad:
        raise RuntimeError('Protected inputs changed: '+repr(bad))
    assert digest((REPRO/FIXED).read_bytes()) == FIXED_HASH
    assert digest((REPRO/AUDIT).read_bytes()) == AUDIT_HASH
    return baseline


def candidate_calls(code, function):
    """Literal locator only. Never a semantic/direct-call/argument binding approval."""
    results = []
    for m in re.finditer(r'\b'+re.escape(function)+r'\s*\(', code):
        start = m.start(); index = m.end(); level = 1
        while index < len(code) and level:
            if code[index] == '(':
                level += 1
            elif code[index] == ')':
                level -= 1
            index += 1
        line = code.count('\n', 0, start)+1
        results.append({'line_1based_in_saved_body': line,
                        'column_1based': start-(code.rfind('\n',0,start)+1)+1,
                        'call_text_candidate': code[start:index],
                        'original_body_line': code.splitlines()[line-1],
                        'location_method': 'literal_locator_not_AST_proof',
                        'binding_status': 'UNKNOWN'})
    return results


def check_sample(spec, output, baseline):
    began = time.perf_counter()
    output.mkdir(exist_ok=False, parents=True)
    path = REPRO/spec['bundle']
    sha = digest(path.read_bytes())
    assert baseline['protected_files_sha256'][spec['bundle']] == sha
    bundle = json.loads(path.read_text('utf-8'))
    assert bundle['candidate']['sample_id'] == spec['sample_id']
    provenance = null_context_provenance(spec, bundle, baseline) if 'context' in bundle and bundle['context'] is None else None
    state, frames = context_state(bundle, provenance)
    result = {'sample_id': spec['sample_id'], 'dataset_id': spec['dataset_id'],
              'position': spec['position'], 'dataset': spec['dataset'],
              'dataset_sha256': digest((REPRO/'upstream'/spec['dataset']).read_bytes()),
              'bundle': spec['bundle'], 'bundle_sha256': sha,
              'frame_count': len(frames) if frames is not None else None,
              'context_state': state, 'null_context_provenance': provenance,
              'historical_context_error': bundle['candidate'].get('error') if frames is None else None,
              'execution_status': 'COMPLETED', 'status': 'UNKNOWN', 'reasons': [],
              'missing_source_evidence': not bool(frames),
              'missing_build_evidence': True, 'type_evidence_status': 'MISSING_OR_UNVERIFIED',
              'build_status': 'saved-source-only', 'frames': [], 'edges': [],
              'labels_used': False, 'prior_solver_results_used': False}
    if frames is None:
        result['reasons'] = ['historical_saved_context_unavailable', 'missing_original_build_evidence']
    elif not frames:
        result['reasons'] = ['missing_saved_frames', 'missing_original_build_evidence']
    elif len(frames) == 1:
        # No caller/callee pair is requested by this frozen chain. Do not invent one.
        result.update(status='NOT_APPLICABLE', type_evidence_status='NOT_CHECKED',
                      reasons=['single_saved_frame_no_cross_frame_pair_requested'])
        code = frames[0]['code'].encode()
        assert digest(code) == frames[0]['body_sha256']
        (output/'frame_0.c').write_bytes(code)
        result['frames'].append({'function': frames[0]['function'], 'body_sha256': digest(code),
                                 'source_ref': spec['bundle']+'#/context/frames/0',
                                 'parsing': 'NOT_ATTEMPTED_NO_REQUESTED_EDGE'})
    else:
        result['reasons'] = ['missing_original_build_evidence', 'no_verified_original_TU_or_type_identity']
        for i, frame in enumerate(frames):
            code = frame['code'].encode('utf-8')
            assert digest(code) == frame['body_sha256'], 'saved body hash mismatch'
            source = output/f'frame_{i}.c'
            source.write_bytes(code)
            report = analyze(source, dataset_id=spec['dataset_id'], position=spec['position'],
                             build_status='saved-source-only')
            assert report['status'] == 'UNKNOWN'
            assert all(c['status'] == 'UNKNOWN' and not c['mappings'] for c in report['calls'])
            save(output/f'frame_{i}_ast.json', report)
            result['frames'].append({'frame': i, 'function': frame['function'],
                                     'body_sha256': digest(code),
                                     'source_ref': spec['bundle']+f'#/context/frames/{i}',
                                     'source_copy': source.name, 'ast_report': f'frame_{i}_ast.json',
                                     'diagnostic_count': len(report['diagnostics']),
                                     'diagnostic_severity_counts': dict(Counter(d['severity'] for d in report['diagnostics'])),
                                     'semantic_mapping_status': 'UNKNOWN'})
        for i, (caller, callee) in enumerate(zip(frames, frames[1:])):
            result['edges'].append({'caller': caller['function'], 'callee': callee['function'],
                                    'caller_body_sha256': caller['body_sha256'],
                                    'callee_body_sha256': callee['body_sha256'],
                                    'caller_frame': i, 'callee_frame': i+1,
                                    'candidate_callsites': candidate_calls(caller['code'], callee['function']),
                                    'status': 'UNKNOWN', 'approved_mappings': [],
                                    'reasons': ['missing_original_build_evidence',
                                                'no_verified_AST_declaration_or_type_mapping']})
    result['elapsed_seconds'] = time.perf_counter()-began
    save(output/'sample_result.json', result)
    return result


def execute_specs(specs, output, baseline):
    """Persist errors with tracebacks, then raise; never relabel them UNKNOWN/N/A."""
    rows = []
    for i, spec in enumerate(specs, 1):
        try:
            rows.append(check_sample(spec, output/f'{i:02d}', baseline))
        except Exception as exc:
            failure = {'execution_status': 'FAILED_STOPPED', 'ordinal_1based': i,
                       'sample_id': spec.get('sample_id'), 'completed_samples': len(rows),
                       'exception_type': type(exc).__name__, 'exception': str(exc),
                       'traceback': traceback.format_exc(), 'mapping_status': None,
                       'action': 'STOP_NO_RETRY', 'result_relabeling': False}
            save(output/'failure.json', failure)
            raise
    return rows


def main(mode):
    offline_boundary.install()
    started = time.perf_counter()
    baseline = verify_existing()
    if mode == 'historical':
        output = ROOT/'historical'
        output.mkdir(exist_ok=False)
        specs = json.loads((CORE_ROOT/'history_inputs.json').read_text('utf-8'))['cases']
    else:
        freeze = json.loads((ROOT/'candidate_manifest.json').read_text('utf-8'))
        for n,h in freeze['frozen_files_sha256'].items():
            assert digest((REPRO/n).read_bytes()) == h, 'Frozen historical input changed: '+n
        output = ROOT/'fixed_20'
        output.mkdir(exist_ok=False)
        # Creation of this output dir is the one-shot run marker; no overwrite/retry.
        original = json.loads((REPRO/FIXED).read_text('utf-8'))
        inventory = json.loads((REPRO/INVENTORY).read_text('utf-8'))
        assert len(original['samples']) == len(inventory['rows']) == 20
        specs = []
        for i, (s, entry) in enumerate(zip(original['samples'], inventory['rows']), 1):
            assert s['sample_id'] == entry['sample_id']
            assert s['row_position'] == entry['row_position']
            assert s['dataset'] == entry['dataset']
            assert s['dataset_sha256'] == digest((REPRO/'upstream'/s['dataset']).read_bytes())
            tool, project = s['sample_id'].split('/')[1:3]
            project = project.split(':')[0]
            dataset_id = tool+'_'+('linux' if project=='kernel69' else project)
            specs.append({'sample_id': s['sample_id'], 'dataset_id': dataset_id,
                          'position': s['row_position'], 'dataset': s['dataset'], 'bundle': entry['bundle']})
        save(output/'run_start.json', {'created_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                                      'freeze_sha256': digest((ROOT/'candidate_manifest.json').read_bytes()),
                                      'fixed_manifest_sha256': FIXED_HASH, 'is_blind': False,
                                      'candidate': 'E06-R01-RF', 'candidate_attempt_number': 1,
                                      'project_fixed_regression_run_number': 2,
                                      'results_reused_from_first_run': 0,
                                      'sample_order': [s['sample_id'] for s in specs]})
    rows = execute_specs(specs, output, baseline)
    stats = {'sample_count': len(rows), 'completed_samples': len(rows),
             'runtime_errors': 0, 'not_executed_samples': 0,
             'status_counts': dict(Counter(r['status'] for r in rows)),
             'context_state_counts': dict(Counter(r['context_state'] for r in rows)),
             'missing_source_evidence': sum(r['missing_source_evidence'] for r in rows),
             'missing_build_evidence': sum(r['missing_build_evidence'] for r in rows),
             'type_evidence_status_counts': dict(Counter(r['type_evidence_status'] for r in rows)),
             'requested_adjacent_frame_pairs': sum(len(r['edges']) for r in rows),
             'located_literal_callsite_candidates': sum(len(e['candidate_callsites']) for r in rows for e in r['edges']),
             'approved_mapping_count': 0,
             'PASS_over_all_requested_samples': 0.0,
             'PASS_over_applicable_samples': 0.0,
             'elapsed_seconds': time.perf_counter()-started,
             'LLM_calls': 0, 'tokens': 0, 'API_cost_CNY': 0, 'Z3_calls': 0,
             'generated_code_executions': 0, 'C_runtime_executions': 0,
             'external_operations': offline_boundary.EVENTS}
    save(output/'results.json', {'mode': mode, 'rows': rows, 'metrics': stats})
    if mode == 'fixed20':
        save(ROOT/'fixed_20_results.json', {'mode': mode, 'rows': rows, 'metrics': stats,
                                           'complete_new_run': True, 'first_run_results_reused': 0})
    print(json.dumps(stats, ensure_ascii=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['historical', 'fixed20'])
    main(parser.parse_args().mode)
