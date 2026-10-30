"""Artifact/preservation check only. Does not execute experiments or core code."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def load(p):
    return json.loads(p.read_text(encoding='utf-8'))


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def put(n, v):
    with (HERE / n).open('x', encoding='utf-8', newline='\n') as f:
        f.write(v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, indent=2) + '\n')


def main():
    state = load(HERE / 'state_before.json')
    changes = [name for name, h in state['protected_sha256'].items()
               if not (ROOT / name).is_file() or sha(ROOT / name) != h]
    ledger = load(ROOT / 'results/raw/completed/budget_ledger.json')
    holdout_hash = sha(ROOT / 'safety_runs/20261029_v1/fixed_holdout.json')
    evidence = load(HERE / 'evidence_index.json')
    evidence_errors = [e['path'] for e in evidence['search_files'] + evidence['code_files']
                       if sha(Path(e['path'])) != e['sha256']]
    missing_links = []
    for n in ['build_evidence_and_repair_report.md', 'repair_plan.md', 'experiment_plan.md',
              'evidence_index.md']:
        for s in re.findall(r'\]\(<([^>]+)>\)', (HERE / n).read_text(encoding='utf-8')):
            target = Path(re.sub(r':\d+$', '', s))
            if not target.is_file():
                missing_links.append(s)
    metadata_errors = []
    for p in (HERE / 'search').rglob('*.metadata.json'):
        meta = load(p)
        body = p.with_name(p.name.removesuffix('.metadata.json'))
        if meta.get('http_status') != 200 or not body.is_file() or sha(body) != meta.get('sha256'):
            metadata_errors.append(str(p))
    git = lambda *args: subprocess.check_output(['git', '-C', str(ROOT / 'upstream'), *args]).decode().strip()
    commit, status = git('rev-parse', 'HEAD'), git('status', '--porcelain')
    conclusion = load(HERE / 'search/search_conclusion.json')
    experiment = load(HERE / 'experiment_plan.json')
    stage = load(HERE / 'stage_status.json')
    checks = {
        'all_prior_files_unchanged': not changes,
        'model_call_count_unchanged': len(ledger['calls']) == state['model_calls_before'],
        'cost_unchanged': ledger['cost_upper_bound_cny'] == state['cost_upper_cny_before'],
        'fixed_holdout_unchanged': holdout_hash == state['holdout_sha256'],
        'source_evidence_hashes_match': not evidence_errors and not metadata_errors,
        'report_links_exist': not missing_links,
        'upstream_unchanged': commit == '4efb4b9bf7e845e180451b43ba29a25e3edaa0e3' and status == '',
        'search_within_time_cap': conclusion['elapsed_seconds'] < conclusion['time_cap_seconds'],
        'a10_unknown_keep': stage['a10_verdict'] == 'UNKNOWN' and stage['a10_action'] == 'KEEP'
                            and stage['filter_evidence_complete'] is False,
        'planning_only': stage['experiment_executed'] is False and stage['solver_checks'] == 0
                         and stage['core_changes'] == [] and stage['safety_rule_changes'] == [],
        'one_issue_proposed_no_exceptions': experiment['single_primary_issue'] == 'R01'
            and experiment['sample_id_special_cases_allowed'] is False,
    }
    result = {
        'verified_at': datetime.now(timezone.utc).isoformat(),
        'checks': checks, 'all_passed': all(checks.values()),
        'prior_files_checked': len(state['protected_sha256']), 'changed_files': changes,
        'missing_links': missing_links, 'evidence_errors': evidence_errors,
        'download_metadata_errors': metadata_errors,
        'public_source_get_count': len(list((HERE / 'search').rglob('*.metadata.json'))),
        'model_calls': len(ledger['calls']), 'new_model_calls': 0,
        'cost_upper_cny': ledger['cost_upper_bound_cny'], 'new_api_cost_cny': 0,
        'holdout_sha256': holdout_hash,
        'note': 'Integrity and planning-scope checks only; not algorithm regression or independent semantic review.',
    }
    put('preservation_verification.json', result)
    assert result['all_passed'], result
    put('checkpoint_03_complete.md',
        '# 本阶段完成并停止\n\n'
        f'限时查找完成；未取得新的A10原始构建证据，保持UNKNOWN/KEEP。\n'
        f'已审查当前代码并保存优先修复清单、单问题离线实验计划。\n'
        f'既有{len(state["protected_sha256"])}个文件哈希不变，固定留出集不变。\n'
        '本阶段未修复算法/门槛、未运行模型/求解器/回归/全量实验。\n')
    files = sorted(p for p in HERE.rglob('*') if p.is_file())
    put('delivery_manifest.json', {
        'scope': 'bounded A10 original-build search and generic repair planning; no experiment executed',
        'files': {p.relative_to(HERE).as_posix(): sha(p) for p in files},
        'self_excluded': True,
    })
    manifest = load(HERE / 'delivery_manifest.json')
    assert all(sha(HERE / p) == h for p, h in manifest['files'].items())
    print(json.dumps({'all_passed': result['all_passed'],
                      'preserved_files': result['prior_files_checked'],
                      'delivery_files': len(files) + 1,
                      'new_model_calls': 0, 'a10': 'UNKNOWN / KEEP',
                      'experiment_status': 'planned_not_executed'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
