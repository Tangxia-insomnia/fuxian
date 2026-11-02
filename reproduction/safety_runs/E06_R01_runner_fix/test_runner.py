"""Runner-only structure and fail-stop contracts; no alteration of R01 mapper."""
import copy
import json
from pathlib import Path
import time
import traceback
from unittest.mock import patch

import run_regression as runner


def main():
    runner.offline_boundary.install()
    output = runner.ROOT/'runner_test_artifacts'
    output.mkdir(exist_ok=False)
    began = time.perf_counter()
    source = 'void f(int *p) { (void)p; }\n'
    frame = {'function': 'f', 'code': source, 'body_sha256': runner.digest(source.encode())}
    candidate = {'status': 'blocked_context', 'error': 'SYNTHETIC: source context unavailable'}
    proof = {'verified': True, 'context_file_absent': True, 'historical_status': 'blocked_context',
             'historical_error': candidate['error'], 'scope': 'synthetic_runner_fixture_only'}
    cases = [
        ('null_with_provenance', {'candidate': candidate, 'context': None}, proof,
         'EXPLICIT_NULL_SAVED_CONTEXT_UNAVAILABLE', None),
        ('null_without_provenance', {'candidate': candidate, 'context': None}, None,
         None, 'NULL_CONTEXT_WITHOUT_VERIFIED_ABSENCE_PROVENANCE'),
        ('missing_context_field', {'candidate': candidate}, None, None, 'CONTEXT_FIELD_MISSING'),
        ('empty_context_object', {'context': {}}, None, None, 'FRAMES_FIELD_MISSING'),
        ('empty_context_array', {'context': []}, None, None, 'CONTEXT_MUST_BE_OBJECT_OR_PROVEN_ABSENT_NULL'),
        ('context_string', {'context': 'wrong'}, None, None, 'CONTEXT_MUST_BE_OBJECT_OR_PROVEN_ABSENT_NULL'),
        ('context_number', {'context': 7}, None, None, 'CONTEXT_MUST_BE_OBJECT_OR_PROVEN_ABSENT_NULL'),
        ('context_boolean', {'context': False}, None, None, 'CONTEXT_MUST_BE_OBJECT_OR_PROVEN_ABSENT_NULL'),
        ('empty_frames_array', {'context': {'frames': []}}, None, 'EMPTY_FRAMES_ARRAY', None),
        ('frames_null', {'context': {'frames': None}}, None, None, 'FRAMES_MUST_BE_ARRAY'),
        ('frames_object', {'context': {'frames': {}}}, None, None, 'FRAMES_MUST_BE_ARRAY'),
        ('invalid_frame', {'context': {'frames': [None]}}, None, None, 'FRAME_0_MUST_BE_OBJECT'),
        ('valid_context', {'context': {'frames': [frame]}}, None, 'FRAMES_PRESENT', None),
    ]
    bad_hash = copy.deepcopy(frame); bad_hash['body_sha256'] = '0'*64
    bad_code = copy.deepcopy(frame); bad_code['code'] = 7
    cases += [('body_hash_conflict', {'context': {'frames': [bad_hash]}}, None,
               None, 'FRAME_0_BODY_HASH_MISMATCH'),
              ('code_not_text', {'context': {'frames': [bad_code]}}, None,
               None, 'FRAME_0_INVALID_code')]
    bad_proof = dict(proof, historical_error='different')
    cases.append(('null_conflicting_provenance', {'candidate': candidate, 'context': None},
                  bad_proof, None, 'NULL_CONTEXT_WITHOUT_VERIFIED_ABSENCE_PROVENANCE'))
    cases.append(('null_status_conflict', {'candidate': dict(candidate, status='success'), 'context': None},
                  proof, None, 'NULL_CONTEXT_WITHOUT_VERIFIED_ABSENCE_PROVENANCE'))
    rows = []
    for name, bundle, provenance, expected_state, expected_error in cases:
        before = json.dumps(bundle, sort_keys=True)
        observed = {'state': None, 'exception': None, 'exception_type': None}
        try:
            state, frames = runner.context_state(bundle, provenance)
            observed.update(state=state, frames=frames)
        except runner.DataShapeError as exc:
            observed.update(exception=str(exc), exception_type=type(exc).__name__,
                            traceback=traceback.format_exc())
        passed = (observed['state']==expected_state and observed['exception']==expected_error
                  and json.dumps(bundle, sort_keys=True)==before)
        if name=='null_with_provenance':
            passed = passed and observed.get('frames', 'absent') is None
        rows.append({'test': name, 'input': bundle, 'provenance': provenance,
                     'expected': {'state': expected_state, 'exception': expected_error},
                     'actual': observed, 'input_unchanged': json.dumps(bundle, sort_keys=True)==before,
                     'passed': bool(passed)})
    # Reproduce only the old expression on a synthetic null, not the old regression.
    try:
        synthetic = {'context': None}
        synthetic['context']['frames']
    except TypeError as exc:
        rows.append({'test': 'old_expression_error_reproduction', 'expected': 'TypeError',
                     'actual': type(exc).__name__, 'passed': str(exc)=="'NoneType' object is not subscriptable",
                     'exception': str(exc), 'traceback': traceback.format_exc(),
                     'provenance': 'new synthetic reproduction, not original run stderr'})
    # A runtime failure must be re-raised and must stop before the second sample.
    for error in (RuntimeError('SYNTHETIC unexpected parser failure'),
                  runner.DataShapeError('SYNTHETIC malformed evidence')):
        dest = output/type(error).__name__
        dest.mkdir(exist_ok=False)
        calls = []
        def failing_check(spec, *_):
            calls.append(spec['sample_id'])
            raise error
        caught = None
        with patch.object(runner, 'check_sample', side_effect=failing_check):
            try:
                runner.execute_specs([{'sample_id':'synthetic-1'},{'sample_id':'synthetic-2'}], dest, {})
            except type(error) as exc:
                caught = exc
        failure = json.loads((dest/'failure.json').read_text('utf-8'))
        rows.append({'test':'fail_stop_'+type(error).__name__, 'expected':'rethrow, save traceback, stop',
                     'actual':failure, 'called_samples':calls,
                     'passed': caught is error and calls==['synthetic-1'] and
                     failure['mapping_status'] is None and failure['result_relabeling'] is False and
                     failure['execution_status']=='FAILED_STOPPED' and bool(failure['traceback'])})
    result = {'tests': rows, 'passed': sum(r['passed'] for r in rows), 'total': len(rows),
              'all_passed': all(r['passed'] for r in rows),
              'elapsed_seconds': time.perf_counter()-began,
              'live_model_calls': 0, 'Z3_calls': 0, 'generated_code_executions': 0,
              'blocked_external_operations': runner.offline_boundary.EVENTS,
              'core_module_path': str(Path(runner.analyze.__code__.co_filename).resolve())}
    runner.save(runner.ROOT/'runner_tests.json', result)
    print(json.dumps({k:v for k,v in result.items() if k not in {'tests','core_module_path'}}))
    if not result['all_passed']:
        print(json.dumps([r for r in rows if not r['passed']]))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
