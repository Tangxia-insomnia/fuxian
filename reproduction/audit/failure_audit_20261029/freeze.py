"""Offline audit snapshot; never imports the model client or reads credentials."""
from pathlib import Path
import hashlib
import json
import subprocess
import zipfile
from datetime import datetime, timezone, timedelta

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT/'upstream'), *args], text=True, encoding='utf-8').strip()

def main():
    target = HERE/'frozen_snapshot.zip'
    if target.exists():
        raise SystemExit('Snapshot already exists; refusing overwrite')
    files = []
    for directory in ['completion', 'configs', 'environment', 'logs', 'patches', 'results', 'scripts']:
        for p in (ROOT/directory).rglob('*'):
            if p.is_file() and not any(x in p.parts for x in ['__pycache__', 'pip-cache']) and p.name != '.env' and not p.name.startswith('.env.'):
                files.append(p)
    files += [ROOT/x for x in ['README.md', 'reproduction_plan.md', '.gitignore']]
    tracked = git('ls-files').splitlines()
    files += [ROOT/'upstream'/x for x in tracked if (ROOT/'upstream'/x).is_file()]
    files = sorted(set(files))
    manifest = {p.relative_to(ROOT).as_posix(): {'sha256': digest(p), 'bytes': p.stat().st_size} for p in files}
    with zipfile.ZipFile(target, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for p in files:
            archive.write(p, p.relative_to(ROOT).as_posix())
    old_identity = json.loads((ROOT/'configs/expanded_run_identity.json').read_text(encoding='utf-8'))
    changed = [name for name, sha in old_identity['source_sha256'].items() if not (ROOT/name).exists() or digest(ROOT/name) != sha]
    state = {
        'time': datetime.now(timezone(timedelta(hours=8))).isoformat(),
        'upstream_url': 'https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis',
        'upstream_commit': git('rev-parse', 'HEAD'),
        'upstream_branch_or_detached': git('rev-parse', '--abbrev-ref', 'HEAD'),
        'upstream_status_porcelain': git('status', '--porcelain'),
        'upstream_changed_files': git('diff', '--name-only'),
        'reproduction_is_git_repository': False,
        'completion_tracking': 'Independent untracked completion/ directory, captured by file hashes and archive; no completion Git commit exists',
        'changed_since_expanded_identity': changed,
        'configuration': json.loads((ROOT/'configs/expanded_experiment.json').read_text(encoding='utf-8')),
        'snapshot': target.name, 'snapshot_sha256': digest(target),
        'file_count': len(files), 'uncompressed_bytes': sum(x['bytes'] for x in manifest.values()),
        'excluded': ['.env and credentials', '.venv', 'upstream/.git', '__pycache__', 'pip-cache', 'audit output itself'],
        'files': manifest,
    }
    (HERE/'frozen_state.json').write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
    with zipfile.ZipFile(target) as archive:
        assert archive.testzip() is None
    (HERE/'checkpoint_01_freeze.md').write_text(
        '# 冻结阶段已完成\n\n'
        f"上游 commit：{state['upstream_commit']}；工作树 {'干净' if not state['upstream_status_porcelain'] else '有修改'}。\n\n"
        f'补全目录不在 Git 仓库中，不能虚构其 commit；以文件 SHA-256 固定。相对扩展实验 identity 变化：{changed}。\n\n'
        f'备份 {len(files)} 个文件，共 {state["uncompressed_bytes"]} 字节，ZIP 完整性检查通过。详见 frozen_state.json。\n\n'
        '审计仅生成 audit/ 下的新证据和独立 failure_audit.md，不修改实验代码、配置、已有结果或预算账本，不调用模型。\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in state.items() if k not in ['files', 'configuration']}, ensure_ascii=True, indent=2))

if __name__ == '__main__':
    main()
