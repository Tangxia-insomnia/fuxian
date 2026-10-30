"""Separate retained alerts (KEEP+UNKNOWN) from confident KEEP predictions."""
from collections import Counter
from statistics import mean


def ratio(a, b):
    return a / b if b else None


def evaluate(rows):
    ids = [r['sample_id'] for r in rows]
    if len(set(ids)) != len(ids):
        raise ValueError('Duplicate sample IDs')
    counts = {str(label): Counter({'FILTER': 0, 'KEEP': 0, 'UNKNOWN': 0}) for label in (0, 1)}
    unlabeled = Counter()
    deleted = []
    evidence = []
    for row in rows:
        verdict = row['verdict']
        if verdict not in ('FILTER', 'KEEP', 'UNKNOWN'):
            raise ValueError('Unknown verdict')
        expected = 'FILTER' if verdict == 'FILTER' else 'KEEP'
        if row.get('action') != expected:
            raise ValueError('UNKNOWN/KEEP must retain alert')
        label = row.get('dataset_label')
        if type(label) is int and label in (0, 1):
            counts[str(label)][verdict] += 1
            if label == 1 and verdict == 'FILTER':
                deleted.append(row['sample_id'])
        else:
            unlabeled[verdict] += 1
        if verdict == 'FILTER':
            if row.get('filter_evidence_complete') is not True:
                raise ValueError('Filtered record without complete evidence')
            evidence.append({'sample_id': row['sample_id'], 'evidence_complete': True,
                             'evidence_sha256': row.get('evidence_sha256'),
                             'review_sha256': row.get('review_sha256')})
    fp, bug = counts['0'], counts['1']
    n_fp, n_bug = sum(fp.values()), sum(bug.values())
    precision = ratio(fp['FILTER'], fp['FILTER'] + bug['FILTER'])
    recall = ratio(fp['FILTER'], n_fp)
    f1 = (None if precision is None or recall is None else
          (2*precision*recall/(precision+recall) if precision+recall else 0.0))
    return {
        'sample_count': len(rows), 'dataset_label_status': 'published_labels_not_independently_verified',
        'confusion_matrix': {'rows': ['published_false_alarm', 'published_real_bug'],
                             'columns': ['FILTER', 'KEEP', 'UNKNOWN'],
                             'values': [[counts[str(y)][v] for v in ('FILTER', 'KEEP', 'UNKNOWN')] for y in (0, 1)]},
        'unverified_or_missing_label_count': sum(unlabeled.values()),
        'unverified_or_missing_label_verdicts': dict(unlabeled),
        'false_alarm_count': n_fp, 'real_bug_count': n_bug,
        'operational_real_bug_retention_rate': ratio(bug['KEEP'] + bug['UNKNOWN'], n_bug),
        'explicit_keep_real_bug_rate': ratio(bug['KEEP'], n_bug),
        'unknown_real_bug_rate': ratio(bug['UNKNOWN'], n_bug),
        'real_bug_deletion_rate': ratio(bug['FILTER'], n_bug),
        'real_bug_deletion_cases': deleted,
        'false_positive_filter_rate': ratio(fp['FILTER'], n_fp),
        'unknown_count': sum(r['verdict'] == 'UNKNOWN' for r in rows),
        'unknown_rate': ratio(sum(r['verdict'] == 'UNKNOWN' for r in rows), len(rows)),
        'auto_filter_count': len(evidence), 'auto_filter_evidence': evidence,
        'positive_class': 'published_false_alarm_to_filter',
        'precision': precision, 'recall': recall, 'f1': f1,
        'undefined_metric_policy': 'precision/F1 null when no positive prediction; not perfect performance',
        'original_execution_success_count': sum(r.get('original_status') == 'success' for r in rows),
        'original_execution_success_rate': ratio(sum(r.get('original_status') == 'success' for r in rows), len(rows)),
        'mean_original_final_attempt_seconds': mean(r['original_duration_seconds'] for r in rows) if rows else None,
        'mean_offline_gate_seconds': mean(r['decision_seconds'] for r in rows) if rows else None,
        'historical_final_attempt_api_calls': sum(r['original_api_calls'] for r in rows),
        'historical_final_attempt_cost_upper_cny': sum(r['original_cost_upper_cny'] for r in rows),
        'new_model_calls': sum(r['new_model_calls'] for r in rows),
        'new_api_cost_cny': sum(r['new_api_cost_cny'] for r in rows),
        'retention_meaning': 'KEEP+UNKNOWN means alert not deleted; not proof of semantic detection, completeness, or generalization',
    }
