"""False-alarm-positive metrics; failed/blocked rows stay in denominators."""
import statistics


def ratio(a, b):
    return a/b if b else None


def evaluate(rows):
    counts = {'false_alarm_filtered': 0, 'false_alarm_kept': 0, 'real_bug_filtered': 0, 'real_bug_kept': 0}
    missing = {'false_alarm': 0, 'real_bug': 0}
    n_fp = sum(r['label'] == 0 for r in rows)
    n_bug = sum(r['label'] == 1 for r in rows)
    for row in rows:
        if row['label'] not in {0, 1}:
            raise ValueError('Unverified dataset label')
        category = 'false_alarm' if row['label'] == 0 else 'real_bug'
        if row['status'] != 'success' or row['prediction'] not in {'filter', 'keep'}:
            missing[category] += 1
        else:
            counts[category + ('_filtered' if row['prediction'] == 'filter' else '_kept')] += 1
    a, b, c, d = [counts[k] for k in ['false_alarm_filtered', 'false_alarm_kept', 'real_bug_filtered', 'real_bug_kept']]
    precision, recall = ratio(a, a+c), ratio(a, n_fp)
    f1 = None if precision is None or recall is None else (2*precision*recall/(precision+recall) if precision+recall else 0.0)
    return {'positive_class': 'false_alarm_to_filter', 'sample_count': len(rows), 'false_alarm_count': n_fp, 'real_bug_count': n_bug, 'successful': a+b+c+d, 'failed': sum(r['status'] == 'failed' for r in rows), 'blocked': sum(r['status'].startswith('blocked') for r in rows), 'missing_prediction_by_label': missing, 'success_rate': ratio(a+b+c+d, len(rows)), 'confusion_matrix': {'row_labels': ['actual_false_alarm', 'actual_real_bug'], 'column_labels': ['predicted_filter', 'predicted_keep'], 'values': [[a, b], [c, d]], 'unclassified': missing}, 'counts': counts, 'false_positive_filter_rate': ratio(a, n_fp), 'real_bug_retention_rate': ratio(d, n_bug), 'real_bug_deletion_rate': ratio(c, n_bug), 'precision': precision, 'recall': recall, 'f1': f1, 'mean_wall_seconds_all_selected': statistics.mean(r['duration_seconds'] for r in rows) if rows else None, 'mean_wall_seconds_successful': statistics.mean(r['duration_seconds'] for r in rows if r['status']=='success') if a+b+c+d else None, 'api_calls_final_attempts': sum(r['api_calls'] for r in rows), 'cost_upper_bound_cny_final_attempts': sum(r['cost_upper_bound_cny'] for r in rows), 'incomplete_coverage_note': 'If unclassified>0, all-selected recall/filter/retention rates count only confirmed outcomes; do not infer labels for failures.', 'false_positive_filter_rate_bounds': [ratio(a,n_fp), ratio(a+missing['false_alarm'],n_fp)], 'real_bug_retention_rate_bounds': [ratio(d,n_bug), ratio(d+missing['real_bug'],n_bug)]}
