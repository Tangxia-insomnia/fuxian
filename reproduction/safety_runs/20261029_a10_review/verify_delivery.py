"""Verify A10 dossier and preservation; no solving, model imports or networking."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(name, value):
    with (HERE / name).open('x', encoding='utf-8', newline='\n') as f:
        f.write(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def main():
    before = load(HERE / 'state_before.json')
    protected = {**before['preserved_sha256'], **before['additional_state_sha256']}
    changed = []
    for relative, expected in protected.items():
        path = ROOT / relative
        if not path.is_file() or sha(path) != expected:
            changed.append(relative)
    ledger = load(ROOT / 'results/raw/completed/budget_ledger.json')
    calls = len(ledger['calls'])
    cost = ledger['cost_upper_bound_cny']
    git = lambda *args: subprocess.run(['git', '-C', str(ROOT / 'upstream'), *args],
                                     capture_output=True, text=True, check=True).stdout.strip()
    commit, status = git('rev-parse', 'HEAD'), git('status', '--short')
    report = HERE / 'a10_evidence_review.md'
    links = re.findall(r'\]\(<([^>]+)>\)', report.read_text(encoding='utf-8'))
    missing_links = [s for s in links if not Path(re.sub(r':\d+$', '', s)).is_file()]
    evidence = load(HERE / 'derived/evidence_inventory.json')
    inventory_errors = []
    for item in evidence['fetched_artifacts'] + evidence['original_a10_exact_copies']:
        if sha(Path(item['path'])) != item['sha256']:
            inventory_errors.append(item['path'])
    for item in evidence['fetched_artifacts']:
        if sha(Path(item['metadata_path'])) != item['metadata_sha256']:
            inventory_errors.append(item['metadata_path'])
    review = load(HERE / 'review_status.json')
    smt = load(HERE / 'derived/z3_replay.json')
    checks = {
        'protected_files_unchanged': not changed,
        'upstream_commit_unchanged': commit == before['upstream_commit'],
        'upstream_status_unchanged': status == before['upstream_status'],
        'model_calls_unchanged': calls == before['api_calls_before'],
        'budget_cost_unchanged': cost == before['api_cost_upper_before'],
        'report_local_links_exist': not missing_links,
        'evidence_hashes_match': not inventory_errors,
        'only_A10_query_recorded': smt['sample_id'] == before['a10_sample_id'] and smt['check_count'] == 1,
        'query_bytes_bound': sha(HERE / 'derived/original_query.smt2') == smt['query_sha256'],
        'unknown_and_no_approval': review['review_verdict'] == 'UNKNOWN'
            and review['action'] == 'KEEP' and review['filter_evidence_complete'] is False
            and review['approval_artifact_created'] is False,
    }
    result = {
        'at': datetime.now(timezone.utc).isoformat(), 'checks': checks, 'all_passed': all(checks.values()),
        'protected_files_checked': len(protected), 'changed_files': changed,
        'missing_report_links': missing_links, 'evidence_hash_errors': inventory_errors,
        'upstream_commit': commit, 'upstream_status': status,
        'model_calls_after': calls, 'cost_upper_cny_after': cost,
        'added_model_calls': calls - before['api_calls_before'],
        'added_cost_upper_cny': cost - before['api_cost_upper_before'],
        'scope_limitation': 'Preservation and artifact integrity only; not independent source semantics proof',
    }
    save('preservation_verification.json', result)
    assert result['all_passed'], result
    save('checkpoint_03_complete.md',
         '# A10 review complete and stopped\n\n'
         f'Protected files checked: {len(protected)}; changes: 0.\n'
         'A10 original query replay: 1, UNSAT; other sample executions: 0.\n'
         'New model calls and additional cost: 0.\n'
         'Report/status: UNKNOWN / KEEP; original scan build evidence incomplete.\n'
         'No independent review approval or final-rule changes.\n')
    files = [p for p in HERE.rglob('*') if p.is_file()]
    save('delivery_manifest.json', {
        'scope': 'A10-only source evidence review; no approval',
        'files': {p.relative_to(HERE).as_posix(): sha(p) for p in sorted(files)},
        'self_excluded': True,
    })
    manifest = load(HERE / 'delivery_manifest.json')
    assert all(sha(HERE / name) == expected for name, expected in manifest['files'].items())
    print(json.dumps({'all_checks_passed': result['all_passed'],
                      'protected_files': len(protected), 'new_delivery_files': len(files) + 1,
                      'new_model_calls': 0, 'verdict': 'UNKNOWN'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
