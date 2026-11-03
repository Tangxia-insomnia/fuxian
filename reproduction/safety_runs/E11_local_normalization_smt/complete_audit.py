"""Read-only preservation/acceptance checks, then exclusive E11 final artifacts.

No solver, analyzer, historical test, or experiment is executed here.
"""
import ast
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parent
REPRO = ROOT.parents[1]
REPO = REPRO.parent / 'fuxian-github-upload'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def load(name):
    return json.loads((ROOT / name).read_text('utf-8'))


def write_new(name, document):
    with (ROOT / name).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(document, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def text_new(name, content):
    with (ROOT / name).open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(content)


def snapshot():
    excluded_dirs = {'.git', '.venv', '__pycache__', 'node_modules'}
    excluded_ext = {'.key', '.pem', '.pfx', '.p12'}
    credential = re.compile(
        r'(^|[._-])(credentials?|secrets?|api[_-]?keys?|access[_-]?tokens?|passwords?)([._-]|$)',
        re.I)
    result = {}
    for current, dirs, names in os.walk(REPRO):
        dirs[:] = sorted(d for d in dirs if d not in excluded_dirs
                         and Path(current) / d != ROOT)
        for name in sorted(names):
            path = Path(current) / name
            if (name == '.env' or name.startswith('.env.')
                    or path.suffix.lower() in excluded_ext or credential.search(name)):
                continue
            result[path.relative_to(REPRO).as_posix()] = sha(path.read_bytes())
    return result


def git(*arguments):
    return subprocess.check_output(['git', '-C', str(REPO), *arguments]).decode().strip()


def main():
    outputs = ['preservation_check.json', 'acceptance_check.json', 'E11_report.md',
               'execution_log.md', 'publication_file_list.md', 'artifact_hashes.json']
    if any((ROOT / name).exists() for name in outputs):
        raise FileExistsError('final artifacts already exist; do not overwrite')
    baseline = load('preservation_baseline.json')
    before, now = baseline['files'], snapshot()
    changed = sorted(p for p in before.keys() & now.keys() if before[p] != now[p])
    removed = sorted(before.keys() - now.keys())
    added = sorted(now.keys() - before.keys())
    git_before = baseline['publication_git_state']
    git_now = {'HEAD': git('rev-parse', 'HEAD'), 'local_main': git('rev-parse', 'main'),
               'branch': git('branch', '--show-current'),
               'status_porcelain': git('status', '--porcelain=v1')}
    preserved = not changed and not removed and not added and git_before == git_now
    check = {'status': 'PASS' if preserved else 'FAIL',
             'protected_file_count': len(before), 'checked_file_count': len(now),
             'changed': changed, 'removed': removed, 'added_outside_E11': added,
             'publication_git_state_unchanged_at_prepublication': git_before == git_now,
             'git_state': git_now, 'exclusions': baseline['exclusions'],
             'scope': 'file/Git preservation only, not semantic acceptance',
             'recorded_at_UTC': datetime.now(timezone.utc).isoformat()}
    write_new('preservation_check.json', check)
    results = load('experiment_results.json')
    tests = load('test_results_v2.json')
    first_tests = load('test_results.json')
    failure = load('development_failure_01.json')
    source = load('source_manifest.json')
    contract = load('semantic_contract.json')
    evidence = load('source_evidence.json')
    unchanged_failure_history = all(
        sha((ROOT / name).read_bytes()) == digest
        for name, digest in failure['preserved_files'].items())
    for path in ROOT.glob('*.py'):
        ast.parse(path.read_text('utf-8'), filename=path.name)
    query_files_match = all(
        sha((ROOT / run['smtlib_file']).read_bytes()) == run['smtlib_sha256']
        and (ROOT / run['smtlib_file']).read_text('utf-8') == run['exact_smtlib']
        for run in results['core_queries'] + results['boundary_queries'])
    criteria = {
        'input_hashes_match': load('input_verification.json')['hash_status'] == 'MATCH',
        'fixed_source_body_matches': source['upstream_body_match'],
        'unsigned_type_and_conditional_semantics': contract['c_type'] == 'unsigned long',
        'distinct_versions_and_use_binding': tests['passed'],
        'normalized_core_UNSAT_both_widths': all(
            r['status'] == 'UNSAT' for r in results['core_queries'] if r['experiment'] == 'B'),
        'unnormalized_control_SAT_both_widths': all(
            r['status'] == 'SAT' for r in results['core_queries'] if r['experiment'] == 'A'),
        'independent_boundary_models_match': all(r['independent_match'] for r in results['boundary_queries']),
        'latest_tests_pass': tests['passed'] and tests['tests_run'] == 15,
        'existing_files_preserved': preserved,
        'first_failure_and_frozen_experiment_preserved': unchanged_failure_history,
        'saved_SMT_bytes_match': query_files_match,
    }
    success = all(criteria.values())
    write_new('acceptance_check.json', {
        'local_experiment_checks_passed': success, 'criteria': criteria,
        'first_test_run': {'tests': 15, 'failures': first_tests['failures'], 'errors': first_tests['errors']},
        'latest_test_run': {'tests': tests['tests_run'], 'failures': tests['failures'], 'errors': tests['errors']},
        'review_state': 'PENDING_GPT_RESEARCH_REVIEW',
        'scope': 'local line-189 divisor property only; not original-alert adjudication',
        'original_alert_decision': None, 'filter_authority': False,
        'full_program_semantics': 'UNKNOWN'})
    rows = '\n'.join('| ' + str(r['width_bits']) + ' | ' + r['experiment'] + ' | '
                     + r['status'] + ' | ' + format(r['elapsed_seconds'], '.9f') + ' |'
                     for r in results['core_queries'])
    source_rows = '\n'.join('| `' + r['path'] + '` | `' + r['sha256'] + '` |'
                            for r in source['files'])
    report = f'''# E11：局部赋值归一化与 SMT 验证

## 结果与范围

样本 `DBZ/all_cwe369.json:row=2:index=2` 的局部条件赋值非零性质得到验证：32 位与 64 位 unsigned long 合同下，未归一化对照为 SAT，归一化后第 189 行除数为零的查询均为 UNSAT。8 个具体边界模型与独立整数参考计算一致。最新测试 15/15 通过；首次测试的 1 项失败、原测试代码及修正记录完整保留。

这只证明固定源码中第 184 行赋值产生的值，在正常到达第 189 行的读取中不为零。没有证明整个函数、所有除法、原始构建或完整告警安全，也没有衡量数据集准确率。

```json
{{"original_alert_decision": null, "filter_authority": false, "full_program_semantics": "UNKNOWN"}}
```

本轮局部检查：`{'PASS' if success else 'FAIL'}`；研究状态：等待 GPT 研究审查。文件保护检查与局部语义检查分别记录。

## 1. 输入与源码身份

- 原始数据：`reproduction/upstream/benchmark/DBZ/all_cwe369.json`，16 条样本中的零基 row=2；JSON Pointer `/2/function_call/0`。
- 数据集 SHA-256：`{results['dataset_sha256']}`。
- UTF-8 原始函数字符串 SHA-256：`{results['function_body_sha256']}`。
- 原始 index=2、label/result=0；保存在 `input_verification.json:/original_record`，标签未作为约束。
- sample_id 是可追溯定位符，原 JSON 本身没有规范 sample_id。原 benchmark 没有本样本可独立核验的行级 checker/rule ID；作者组级 Cppcheck 统计不构成工具告警来源认证。
- 上游：`gregkh/linux`，tag `v6.9.6`，peeled commit `{source['commit']}`。`upstream_tag_verification.json` 保存本次远端 Git refs；未验证 GPG 签名。
- 函数：`drivers/gpu/drm/omapdrm/dss/pll.c:176-199`。仅省略闭合花括号之后用于文件分隔的一个 LF 后，上游函数与原始函数逐字节一致。类型见 177 行，赋值见 184 行，目标除法见 189 行。

`source_manifest.json` 记录每份源码的固定 commit URL、SHA-256、Git blob SHA-1 和取得时间；原文件完整保存于 `sources/`。本次仅获取 5 份源码/头文件，没有克隆或编译内核。

| 源码 | SHA-256 |
| --- | --- |
{source_rows}

## 2. 程序证据与局部 C 合同

原始语句：

```c
/* pll.c:177 */ unsigned long out_min, unsigned long out_max,
/* pll.c:184 */ out_min = out_min ? out_min : 1;
/* pll.c:185 */ out_max = out_max ? out_max : ULONG_MAX;
/* pll.c:187 */ m_start = max(DIV_ROUND_UP(clkdco, out_max), 1ul);
/* pll.c:189 */ m_stop = min((unsigned)(clkdco / out_min), hw->mX_max);
```

`out_min` 是按值传入的 unsigned long 参数。C 标量条件将零视为假，非零视为真；条件表达式的 `1` 原为 int，经通常算术转换得到 unsigned long，其值在两种合同下均精确为 1。使用完整无符号域，不添加调用者范围、自然语言条件或 E09/E10 数字前提。

第 185-188 行只给 out_max、m_start 赋值，不读写或取地址 out_min。固定函数中没有 out_min 地址逃逸，也没有位于赋值与目标除法之间的分支、goto 或回调；回调 `func` 首次出现在 194 行。相关宏静态核对位置：`include/linux/kernel.h:27-28`，`include/linux/math.h:37`，`include/uapi/linux/const.h:34`，`include/linux/minmax.h:43-58,85-92`。已检查的 min/max 算术与局部副本辅助宏、DIV_ROUND_UP 定义没有修改 out_min。宏检查用于确认这段源码的局部保持关系，不认证第 187 行算术安全。

证据等级是**固定原始源码字节核对、有限行级检查和人工静态宏语义审查**，不是原始 TU 的 AST/预处理/构建认证。没有恢复全部头文件、构建宏、ABI 或编译命令；这些仍 UNKNOWN。结论适用于按已核对源码语义正常执行并到达目标表达式的 C 路径，不认证之前的指针有效性、算术或其他潜在未定义行为。

## 3. 值版本和查询

`semantic_contract.json:/value_versions` 明确区分三个局部编码标识；它们不是伪造的 R02 声明/版本 ID，本轮没有调用、重写或修改 R01-R05：

| 版本 | 含义 | 依据 |
| --- | --- | --- |
| out_min_v0 | 赋值前的参数输入 | 177 行，F_TYPE |
| out_min_v1 | 184 行赋值后的新值 | F_NORMALIZE |
| out_min_use | 189 行读取，绑定到 v1，不是再次赋值 | F_PRESERVE、F_USE |

分别实例化位宽 w=32、64，所有版本均为 BitVec(w)，原 ABI 未确定，两个位宽均为明确实验合同：

```text
v1 = ITE(v0 == BV(0,w), BV(1,w), v0)
use = v1
```

A 对照：只查询 `v0 == 0`，不执行归一化。这是删除归一化的反事实对照，不是原始源码存在零除执行路径的证明。

B 核心：上述两个版本等式，且 `use == 0`。没有把 `use != 0` 预先加入查询，因此不会用除法定义性排除待检查故障。unsigned long 除法的非零分母条件在合同中单独记录。

核心性质仅依赖分母，投影掉任意 unsigned long 分子 clkdco，不需要编码商。SMT 中没有 signed 比较或 signed 除法；也没有声称已经编码 `bvudiv`、结果截为 unsigned int、min 的结果、完整赋值链以外的 C 行为。

## 4. 求解结果和独立验证

Z3 `{results['solver']['version']}`，Python 包 `{results['solver']['package_version']}`，逻辑 QF_BV，超时 30000 ms。`experiment_results.json` 保存每次准确 SMT-LIB、其 SHA-256、模型、状态和耗时；对应原文另存于 `queries/*.smt2`。

| 位宽 | 实验 | 结果 | check 耗时（秒） |
| --- | --- | --- | --- |
{rows}

A 的两个 SAT 模型均为 v0=0。B 的两个 UNSAT 没有模型，未生成或独立检查 Z3 UNSAT 证书。独立数学核对不调用求解器：v0=0 时 v1=1；v0!=0 时 v1=v0!=0；use=v1，因此覆盖完整无符号域。这是简单符号分情况证明，不是位宽域的穷举测试，也不是机器检查的 Z3 证明证书。

除 4 个核心查询外，8 个独立具体输入查询保存了版本模型，结果均为 SAT 且如下：

| 位宽 | v0 | v1/use |
| --- | --- | --- |
| 32 | 0 | 1 |
| 32 | 1 | 1 |
| 32 | 2 | 2 |
| 32 | 4294967295 (ULONG_MAX) | 4294967295 |
| 64 | 0 | 1 |
| 64 | 1 | 1 |
| 64 | 2 | 2 |
| 64 | 18446744073709551615 (ULONG_MAX) | 18446744073709551615 |

独立参考使用 Python 任意精度非负整数和条件选择，不依赖浮点、负数整除或隐式位宽回绕。测试另作 12 次具体 Z3 表达式替换，包含最高位为 1 的无符号值；不调用 solver.check。总计只有 **12 次新求解检查**：4 次核心、8 次边界。测试没有额外求解。

## 5. 测试失败与追加修正记录

首轮 `test_local_normalization.py` 执行 15 项：14 通过、1 失败、0 错误。`test_06` 错误假定等式第一个操作数总是变量；本机 Z3 的结构是 `0 == v0`。该失败涉及测试对表达式结构顺序的假定，不是 C 条件赋值与 SMT 语义不一致。原测试和 `test_results.json` 原样保留，未覆盖或改成 PASS。

新增 `test_local_normalization_v2.py` 只覆盖这一项：核对等式两侧分别具有唯一的 v0 和零常量，其他 14 项直接继承。`test_results_v2.json`：**15/15 通过，0 失败、0 错误、0 额外求解**。`development_failure_01.json` 保存原文件哈希和原因；实现、合同、4 组核心结果及 8 个边界结果均未修改或重跑。

有效验收以明确的 v2 入口为准，旧入口作为不可改写的失败证据保留。覆盖包括源哈希篡改阻断、不支持类型和位宽拒绝、越界输入拒绝、旧新版本隔离、错误旧值读取排除、反事实对照、定义性未被误加为前提、unsigned 高位值、精确 SMT-LIB、证书局限和过滤权限限制。

## 6. 文件保护与执行边界

`preservation_baseline.json` 在新增实现前建立，保护 {len(before)} 份既有非凭据文件。`preservation_check.json`：`{check['status']}`，changed={len(changed)}、removed={len(removed)}、E11 以外新增={len(added)}。覆盖原始数据、E01-E10、R01-R05 及已有账本/结果；虚拟环境、Git 内部文件、缓存和凭据按声明排除，未读取凭据内容或安装依赖。

发布前克隆 HEAD `{git_before['HEAD']}`，工作区干净；本地 main `{git_before['local_main']}` 的未发布历史不作为 E11 的父链。发布将从已核验远端 main 创建独立分支，仅复制本 E11 新目录，检查差异和逐字节内容后正常推送；禁止 force push。冻结报告不为后续 Git 发布而改写，实际提交号由最终发布回执提供。

未调用 LLM API、DeepSeek Harness、原始分析器、R05 Builder/Validator；未运行 624 项旧回归。没有扩大样本、研究全部 PLL、硬件、回调或构建内核。原始标签和结果保持不变。文件保护 PASS 不等同于程序语义或告警裁决 PASS。

## 7. 研究问题回答

1. **局部条件赋值的非零保证**：已在两个明确位宽合同中验证，限于 184→189 行的分母值关系。
2. **赋值前后版本**：v0、v1、use 分别建模；v0=0 而 v1/use=1 的保存模型直接检查了版本转换与读取绑定。
3. **32/64 位一致性**：零分母性质一致，ULONG_MAX 的数值随位宽改变，模型没有将两者混用；原 ABI 仍 UNKNOWN。
4. **与 E10 区别**：E10 依赖调用者范围、跨函数字段保持与同步静态审查；E11 使用一个函数内部的条件赋值和 reaching definition，不需要调用者范围，也未引入其他样本前提。
5. **复用可能**：位向量条件选择、显式版本和对照查询可作为下一个相同局部标量模式的模板；新样本仍需独立核验类型、转换、控制流、写入/别名和来源。当前实现只接收本样本精确哈希，不是通用转换器，也没有扩大支持范围。
6. **未认证行为**：187 行 DIV_ROUND_UP、192 行 clkdco/m、循环、回调、硬件、unsigned int 截断与 min 结果、整函数、原始 TU/构建、跨函数/内存/并发行为及原始告警真实可达性，均未认证。本轮 UNSAT 不授权过滤或重新标注告警。

本轮到此停止，等待 GPT 研究审查。
'''
    text_new('E11_report.md', report)
    text_new('execution_log.md', '''# E11 execution record

1. Read publication Git state and remote main: clean at ef1075976d5845c0017df28707a80d6a20bc696d; unrelated local main preserved.
2. Independently recomputed dataset and raw function hashes; both matched the request. Created preservation_baseline.json before implementation.
3. Ran acquire_sources.py once with the existing Python -B environment. Five pinned upstream files fetched; tag association matched; no fetch failures.
4. Ran prepare_evidence.py once. Exact upstream body/line/type checks matched; created source evidence, manifest and finite contract.
5. Parsed initial four Python sources and loaded source gates without solving; preflight_checks.json records the result.
6. Ran local_normalization_smt.py once: four core checks and eight boundary-model checks; A=SAT/B=UNSAT for both widths. All eight boundary models matched the independent reference.
7. Ran test_local_normalization.py once: 15 tests, 1 failure, 0 errors, 0 solver checks. Preserved test file and test_results.json. Failure was equality operand order assumed by test_06.
8. Added development_failure_01.json and test_local_normalization_v2.py; no experiment code, contract, solver query or result overwritten. Ran v2 once: 15 passed, 0 failures/errors, 0 solver checks.
9. Ran complete_audit.py for file preservation, explicit acceptance criteria, documentation and artifact hashes. No solver or old regression is run by this step.

All result/evidence writers use exclusive creation. Completed solver records and first-test failure remain immutable. The final report and commit publication are distinct from research review. No new research stage is started.
''')
    # List also the two files about to be created; neither modifies prior artifacts.
    paths = sorted({p.relative_to(ROOT).as_posix() for p in ROOT.rglob('*') if p.is_file()}
                   | {'publication_file_list.md', 'artifact_hashes.json'})
    text_new('publication_file_list.md', '# E11 complete publication file list\n\n'
             + str(len(paths)) + ' files; all are newly added under '
             '`reproduction/safety_runs/E11_local_normalization_smt/`.\n\n'
             + '\n'.join('- `' + path + '`' for path in paths) + '\n')
    hashes = {p.relative_to(ROOT).as_posix(): sha(p.read_bytes())
              for p in sorted(ROOT.rglob('*')) if p.is_file()}
    write_new('artifact_hashes.json', {
        'algorithm': 'SHA-256', 'scope': 'all E11 files except this self-referential manifest',
        'file_count_excluding_manifest': len(hashes), 'files': hashes})
    print(json.dumps({'local_experiment_checks_passed': success,
                      'protected_files': len(before), 'preservation': check['status'],
                      'latest_tests': tests['tests_run'], 'files': len(hashes) + 1,
                      'first_failure_retained': unchanged_failure_history}))
    if not success:
        raise SystemExit(2)


if __name__ == '__main__':
    main()
