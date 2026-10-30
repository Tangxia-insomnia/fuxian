"""Local component checks; never instantiate upstream model clients."""
from datetime import datetime
import importlib.metadata as md
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time
from datetime import timedelta, timezone

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'results/raw/environment'
RAW.mkdir(parents=True, exist_ok=True)
sys.dont_write_bytecode = True
report = {'timestamp': datetime.now(timezone(timedelta(hours=8), 'Asia/Shanghai')).isoformat(), 'os': platform.platform(), 'python': sys.version, 'executable': sys.executable, 'packages': {}, 'tools': {x: shutil.which(x) for x in ['git', 'clang', 'codeql', 'cppcheck', 'infer', 'wsl', 'docker']}, 'checks': {}}
for name in ['z3-solver', 'libclang', 'lizard', 'openai', 'anthropic', 'requests', 'tqdm', 'python-dotenv']:
    try:
        report['packages'][name] = md.version(name)
    except md.PackageNotFoundError:
        report['packages'][name] = None


def check(name, fn):
    start = time.perf_counter()
    try:
        report['checks'][name] = {'status': 'passed', 'output': fn()}
    except Exception as exc:
        report['checks'][name] = {'status': 'failed', 'error': f'{type(exc).__name__}: {exc}'}
    report['checks'][name]['duration_seconds'] = time.perf_counter() - start


def z3_test():
    import z3
    x = z3.Int('environment_test_x')
    s = z3.Solver()
    s.add(x > 0, x < 2)
    sat = str(s.check())
    model = str(s.model())
    s.add(x == 0)
    unsat = str(s.check())
    assert sat == 'sat' and unsat == 'unsat'
    return {'version': z3.get_version_string(), 'satisfiable_case': sat, 'model': model, 'contradictory_case': unsat, 'not_a_benchmark_prediction': True}


def clang_test():
    import clang.cindex as ci
    index = ci.Index.create()
    tu = index.parse('environment_test.c', args=['-xc'], unsaved_files=[('environment_test.c', 'int f(int *p) { if (p) return *p; return 0; }')])
    diagnostics = [str(d) for d in tu.diagnostics]
    assert not any(d.severity >= ci.Diagnostic.Error for d in tu.diagnostics)
    return {'parsed': True, 'library_path': ci.Config.library_path, 'diagnostics': diagnostics}


def lizard_test():
    import lizard
    data = lizard.analyze_file.analyze_source_code('sample.c', 'int f(int x) { return x + 1; }')
    names = [f.name for f in data.function_list]
    assert names == ['f']
    return {'functions': names, 'not_a_project_scan': True}


def read_data():
    paths = list((ROOT / 'upstream/benchmark').rglob('*.json'))
    return {'readable_files': len(paths), 'records_including_duplicate_files_and_unlabeled': sum(len(json.loads(p.read_text(encoding='utf-8'))) for p in paths)}


check('z3_sat_unsat', z3_test)
check('libclang_parse', clang_test)
check('lizard_parse', lizard_test)
check('official_data_read', read_data)
imports = []
for filename in ['feasibility_analysis_pipeline.py', 'extract_util_plus.py', 'prompt_templates.py', 'model.py']:
    path = ROOT / 'upstream/llm4pfa' / filename
    code = 'import runpy; runpy.run_path(' + repr(str(path)) + ', run_name="__diagnostic__")'
    start = time.perf_counter()
    run = subprocess.run([sys.executable, '-B', '-c', code], cwd=ROOT / 'upstream', capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=30)
    # The original pipeline fails on its first import, before touching clients.
    # Never save model source text or any environment values.
    (RAW / (filename + '.import.stdout.txt')).write_text(run.stdout, encoding='utf-8')
    (RAW / (filename + '.import.stderr.txt')).write_text(run.stderr, encoding='utf-8')
    imports.append({'file': filename, 'exit_code': run.returncode, 'duration_seconds': time.perf_counter() - start, 'last_error_line': run.stderr.strip().splitlines()[-1] if run.stderr.strip() else None})
report['upstream_import_checks'] = imports
report['llm'] = {'provider': 'deepseek', 'requested_model': 'deepseek-flash', 'base_url': 'https://api.deepseek.com/', 'api_key_env_name': 'DEEPSEEK_APIkey', 'credential_present': bool(os.environ.get('DEEPSEEK_APIkey')), 'model_service_test': 'not_run', 'reason': 'Original pipeline prerequisites missing; no paid call authorized to bypass the pipeline. Credential absent if credential_present=false.', 'api_calls': 0, 'cost_cny': 0, 'budget_cny': 10}
report['upstream_git_status'] = subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT / 'upstream', text=True).strip()
(RAW / 'environment_checks.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
(ROOT / 'environment/environment.txt').write_text(json.dumps({k: report[k] for k in ['timestamp', 'os', 'python', 'executable', 'tools']}, ensure_ascii=False, indent=2), encoding='utf-8')
freeze = subprocess.check_output([sys.executable, '-m', 'pip', 'freeze'], text=True)
(ROOT / 'environment/dependencies.txt').write_text(freeze, encoding='utf-8')
rows = '\n'.join(f"| {name} | {r['status']} | `{r.get('output', r.get('error'))}` |" for name, r in report['checks'].items())
import_rows = '\n'.join(f"| {r['file']} | {r['exit_code']} | `{r['last_error_line']}` |" for r in imports)
log = f'''# 阶段 2：环境配置与运行检查

状态：本地依赖和组件测试完成；官方端到端流水线被内部模块缺失阻塞。
时间：{report['timestamp']}（Asia/Shanghai）。

## 环境

- 操作系统：{report['os']}
- Python：{sys.version.splitlines()[0]}
- 可执行文件：`{sys.executable}`
- 原仓库未给依赖版本。独立 `.venv` 使用 `environment/requirements-reproduction.txt` 中明确固定的版本，不升级系统 Python 环境；这些版本为本次选择，并非作者版本。
- 实际依赖：`{report['packages']}`。完整 freeze 见 `environment/dependencies.txt`，安装原始输出见 `results/raw/environment/install.log`。

## 实际检查

| 项目 | 结果 | 输出 |
|---|---|---|
{rows}

Z3 的 SAT/UNSAT 是人工构造环境测试，不是论文样本预测。

## 原始模块加载检查

使用 `runpy.run_path(..., run_name="__diagnostic__")`，不触发模型自测主入口。未修改源码、未伪造缺失模块。

| 文件 | 退出码 | 实际错误 |
|---|---:|---|
{import_rows}

官方仓库没有可直接使用的最小测试套件；以上模块加载是实际执行的入口诊断，不能称为官方端到端自测成功。

## 模型、外部工具与路径

- 用户模型：`deepseek-flash`；接口：`https://api.deepseek.com/`；凭据变量：`DEEPSEEK_APIkey`；预算上限 10 元。
- 当前进程该变量已配置：`{report['llm']['credential_present']}`。不记录其值。
- 模型请求 0 次，费用 0 元；服务可用性、模型 ID、价格和参数兼容性均未验证。不会使用仓库内嵌字面量凭据。
- 外部工具检测只证明命令是否位于 PATH，不证明服务可用：`{report['tools']}`。现有基准可直接读取，无需下载或扫描 Linux Kernel。
- 作者硬编码 Linux 路径、上下文缓存和内部工具仍缺失，安装第三方包不能解决这些问题。
- 本次未更改官方源码；检查后的 Git 状态：`{report['upstream_git_status'] or 'clean'}`。

下一阶段仅进行 5 条官方样本的离线组件诊断。若原始入口和上下文依赖未恢复，不启动 LLM 小实验或全量评测。
'''
(ROOT / 'logs/stage_02_environment.md').write_text(log, encoding='utf-8')
print(json.dumps({'stage': 2, 'checks': {k: r['status'] for k, r in report['checks'].items()}, 'imports': imports, 'credential_present': report['llm']['credential_present'], 'log_exists': (ROOT / 'logs/stage_02_environment.md').is_file()}, ensure_ascii=True))
