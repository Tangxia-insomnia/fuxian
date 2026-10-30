"""Keep alerts unless a separately reviewed, bound UNSAT justifies filtering.

Reviews are attestations by a human/trusted analyzer, not proofs of C semantics.
Historical logs contain no such complete attestations. Dataset labels are never
an input to this policy. This module does not execute generated Python.
"""
import hashlib
import json
import time

import z3

VERSION = 'real-bugs-first-v1'
CONDITIONS = (
    'target_location', 'control_conditions', 'variable_identity',
    'constraint_semantics', 'solver_validity', 'context_integrity',
)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')).encode()).hexdigest()


def text_digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def source_texts(bundle):
    return {f'frame/{i}': f['code'] for i, f in
            enumerate((bundle.get('context') or {}).get('frames', []))}


def _check(state, reason):
    return {'status': state, 'reason': reason}


def replay_last_query(bundle):
    """Independently check the decisive saved formula, not its C meaning."""
    events = bundle.get('solver_events', [])
    if not events:
        return {'valid': False, 'reason': 'no_saved_solver_event'}
    event = events[-1]
    queries = event.get('queries', [])
    if event.get('ok') is not True or type(event.get('feasible')) is not bool or not queries:
        return {'valid': False, 'reason': 'last_solver_event_incomplete'}
    if any(q.get('result') not in ('sat', 'unsat') for q in queries):
        return {'valid': False, 'reason': 'unknown_or_invalid_saved_query'}
    query = queries[-1]
    text = query.get('smt2')
    if not isinstance(text, str) or not text.strip() or len(text) > 512_000:
        return {'valid': False, 'reason': 'invalid_smt2_payload'}
    try:
        solver = z3.Solver()
        solver.from_string(text)
        solver.set(timeout=5000)
        assertions = [a.sexpr() for a in solver.assertions()]
        actual = str(solver.check())
    except z3.Z3Exception:
        return {'valid': False, 'reason': 'smt2_cannot_be_loaded_unambiguously'}
    if not assertions:
        return {'valid': False, 'reason': 'empty_constraint_set'}
    if actual not in ('sat', 'unsat') or actual != query['result']:
        return {'valid': False, 'reason': 'solver_replay_mismatch_or_unknown', 'actual': actual}
    if event['feasible'] != (actual == 'sat'):
        return {'valid': False, 'reason': 'saved_boolean_disagrees_with_solver'}
    return {'valid': True, 'result': actual, 'query_sha256': text_digest(text),
            'assertions': assertions, 'event_id': event.get('event_id'),
            'meaning': 'formula replay only; source semantics not established'}


def machine_checks(bundle, replay):
    """Mechanical facts may reject filtering, but cannot certify all semantics."""
    checks = {k: _check('needs_review', 'no_complete_source_semantics_review')
              for k in CONDITIONS}
    frames = (bundle.get('context') or {}).get('frames', [])
    if not frames:
        checks['target_location'] = _check('failed', 'no_recorded_context')
    else:
        bad = []
        for frame in frames:
            code, target = frame.get('code', ''), frame.get('target', '').strip()
            if not target or code.count(target) != 1:
                bad.append('missing_or_ambiguous_target')
            if frame.get('body_sha256') != text_digest(code):
                bad.append('body_hash_mismatch')
        alert = bundle.get('alert', {})
        snippet = alert.get('location', {}).get('context', {}).get('snippet', {}).get('text', '').strip()
        original_code = alert.get('function_code', alert.get('func_info', ''))
        if (frames[0].get('target', '').strip() != snippet or
                frames[0].get('code') != original_code or
                frames[0].get('var_name') != alert.get('var_name')):
            bad.append('alert_context_mismatch')
        checks['target_location'] = _check(
            'failed' if bad else 'needs_review',
            ','.join(sorted(set(bad))) if bad else
            'unique_text_and_body_hash_match; absolute_source_location_not_proven')
        if any(not isinstance(f.get('extracted'), dict) for f in frames):
            checks['control_conditions'] = _check('failed', 'missing_saved_extraction')
    checks['solver_validity'] = _check('verified' if replay['valid'] else 'failed',
                                      'actual_query_replayed' if replay['valid'] else replay['reason'])
    record = bundle['candidate']
    if record.get('status') != 'success' or record.get('error'):
        checks['context_integrity'] = _check('failed', 'original_execution_not_successful')
    elif bundle.get('issues'):
        checks['context_integrity'] = _check('failed', 'known_audit_or_evidence_issue')
    elif (type((bundle.get('recorded_answer') or {}).get('result')) is not bool or
          ('keep' if bundle['recorded_answer']['result'] else 'filter') != record.get('prediction')):
        checks['context_integrity'] = _check('failed', 'saved_answer_candidate_mismatch')
    elif any(e.get('ok') is not True for e in bundle.get('solver_events', [])):
        checks['context_integrity'] = _check('needs_review', 'solver_repair_history_needs_semantics_review')
    else:
        checks['context_integrity'] = _check('needs_review', 'no_complete_context_review')
    return checks


def review_errors(bundle, review, replay):
    """Bind review to the exact evidence and every submitted assertion.

    This validates the review's identity, coverage and freshness. A reviewer
    must actually check the C semantics; matching hashes cannot establish that.
    """
    if not isinstance(review, dict):
        return ['missing_semantic_review']
    errors = []
    if review.get('evidence_sha256') != digest(bundle):
        errors.append('review_evidence_mismatch')
    if review.get('scope') != bundle.get('scope'):
        errors.append('review_scope_mismatch')
    allowed = {'manual_source_review', 'trusted_analyzer'}
    if bundle.get('scope') == 'synthetic_fixture':
        allowed.add('synthetic_fixture_review')
    if review.get('verification_mode') not in allowed:
        errors.append('untrusted_review_mode')
    if not str(review.get('reviewer') or '').strip() or not str(review.get('reviewed_at') or '').strip():
        errors.append('review_identity_missing')
    if review.get('unresolved_issues') != []:
        errors.append('review_has_unresolved_or_unspecified_issues')
    if review.get('query_sha256') != replay.get('query_sha256'):
        errors.append('review_query_mismatch')
    sources = source_texts(bundle)

    def valid_refs(refs):
        if not isinstance(refs, list) or not refs:
            return False
        for ref in refs:
            if not isinstance(ref, dict) or ref.get('source') not in sources:
                return False
            text = sources[ref['source']]
            start, end = ref.get('start_line'), ref.get('end_line')
            if (type(start) is not int or type(end) is not int or
                    not (1 <= start <= end <= len(text.splitlines())) or
                    ref.get('source_sha256') != text_digest(text)):
                return False
        return True

    checks = review.get('conditions')
    if not isinstance(checks, dict) or set(checks) != set(CONDITIONS):
        errors.append('six_review_conditions_required')
        checks = {}
    for name in CONDITIONS:
        item = checks.get(name)
        if (not isinstance(item, dict) or item.get('status') != 'verified' or
                not str(item.get('rationale') or '').strip() or not valid_refs(item.get('source_refs'))):
            errors.append('review_condition_incomplete:' + name)
    trace = review.get('assertion_provenance')
    assertions = replay.get('assertions', [])
    if not isinstance(trace, list) or len(trace) != len(assertions) or not assertions:
        errors.append('incomplete_assertion_provenance')
    else:
        for i, (item, formula) in enumerate(zip(trace, assertions)):
            if (not isinstance(item, dict) or type(item.get('index')) is not int or
                    item['index'] != i or item.get('formula') != formula or
                    item.get('role') not in ('bug_assumption', 'reachability') or
                    not str(item.get('rationale') or '').strip() or not valid_refs(item.get('source_refs'))):
                errors.append('invalid_assertion_provenance:' + str(i))
    return errors


def _decide(bundle, review=None):
    """Return FILTER, KEEP or UNKNOWN. UNKNOWN always keeps the alert.

    KEEP is a conservative action supported by a consistent SAT candidate,
    not a claim that a real bug has been proved. FILTER additionally requires
    all six checks and a separate, source-directed semantic review.
    """
    start = time.perf_counter()
    replay = replay_last_query(bundle)
    checks = machine_checks(bundle, replay)
    candidate = bundle['candidate']
    issues = list(bundle.get('issues', []))
    reasons = [issue['code'] for issue in issues]
    blockers = [k + ':' + v['reason'] for k, v in checks.items() if v['status'] == 'failed']
    reasons.extend(blockers)
    verdict = 'UNKNOWN'
    complete = False
    review_validation = []
    if not blockers:
        predicted = candidate.get('prediction')
        expected = 'sat' if predicted == 'keep' else 'unsat' if predicted == 'filter' else None
        if replay.get('result') != expected or expected is None:
            reasons.append('candidate_solver_decision_mismatch')
        elif predicted == 'keep':
            verdict = 'KEEP'
            reasons.append('consistent_sat_candidate; alert_retained_not_bug_proved')
        else:
            review_validation = review_errors(bundle, review, replay)
            reasons.extend(review_validation)
            if not review_validation:
                complete = True
                verdict = 'FILTER'
                for name in CONDITIONS:
                    if name != 'solver_validity':
                        checks[name] = _check('verified', 'bound_source_review_attestation')
                reasons.append('six_checks_verified_and_bound_unsat_replayed')
    return {
        'policy_version': VERSION, 'sample_id': candidate['sample_id'],
        'verdict': verdict, 'action': 'FILTER' if verdict == 'FILTER' else 'KEEP',
        'reason_codes': sorted(set(reasons)), 'filter_evidence_complete': complete,
        'checks': checks, 'solver_replay': replay,
        'evidence_sha256': digest(bundle),
        'review_sha256': digest(review) if review is not None else None,
        'decision_seconds': time.perf_counter() - start,
        'new_model_calls': 0, 'new_api_cost_cny': 0,
    }


def decide(bundle, review=None):
    """Malformed evidence/reviews fail closed; no exception grants FILTER."""
    try:
        return _decide(bundle, review)
    except (KeyError, TypeError, ValueError, AttributeError, z3.Z3Exception):
        candidate = bundle.get('candidate', {}) if isinstance(bundle, dict) else {}
        sid = candidate.get('sample_id', '<missing>') if isinstance(candidate, dict) else '<missing>'
        return {
            'policy_version': VERSION, 'sample_id': sid, 'verdict': 'UNKNOWN', 'action': 'KEEP',
            'reason_codes': ['malformed_evidence_or_review'], 'filter_evidence_complete': False,
            'checks': {k: _check('failed', 'malformed_evidence_or_review') for k in CONDITIONS},
            'solver_replay': {'valid': False, 'reason': 'malformed_evidence_or_review'},
            'evidence_sha256': None, 'review_sha256': None, 'decision_seconds': 0,
            'new_model_calls': 0, 'new_api_cost_cny': 0,
        }
