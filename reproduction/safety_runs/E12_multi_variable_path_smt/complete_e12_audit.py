"""Finalize E12 reports and immutable integrity records without invoking Z3.

Only standard-library file/hash/Git checks run here. Existing preflight,
experiment results, tests, and historical artifacts are never rewritten.
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
BASE = '3d58641c8c62e80d60e82d137b03bcba7b8ed5cd'
MAIN = 'f4850309b19cd049ff38356881549bb33c615144'


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


def git(*args):
    return subprocess.check_output(['git', '-C', str(REPO), *args], timeout=50).decode().strip()


def snapshot(baseline):
    exclusions = baseline['exclusions']
    dirs_to_skip = set(exclusions['directories'])
    credential = re.compile(exclusions['credential_name_regex'], re.I)
    result = {}
    for current, dirs, names in os.walk(REPRO):
        dirs[:] = sorted(d for d in dirs if d not in dirs_to_skip)
        for name in sorted(names):
            path = Path(current) / name
            if (name == '.env' or name.startswith('.env.')
                    or path.suffix.lower() in exclusions['extensions']
                    or credential.search(name)):
                continue
            result[path.relative_to(REPRO).as_posix()] = sha(path.read_bytes())
    return result


def compare_existing(baseline):
    before, now = baseline['files'], snapshot(baseline)
    changed = sorted(k for k in before.keys() & now.keys() if before[k] != now[k])
    removed = sorted(before.keys() - now.keys())
    added = sorted(now.keys() - before.keys())
    prefix = 'safety_runs/E12_multi_variable_path_smt/'
    outside = [p for p in added if not p.startswith(prefix) or p.startswith(prefix + 'preflight/')]
    return {'changed': changed, 'removed': removed, 'added_outside_new_E12_files': outside,
            'new_files_present_at_comparison': added,
            'existing_files_unchanged': not changed and not removed and not outside}


def main():
    final_names = {'preservation_check.json', 'acceptance_check.json', 'E12_report.md',
                   'execution_log.md', 'publication_file_list.md', 'artifact_hashes.json'}
    if any((ROOT / name).exists() for name in final_names):
        raise FileExistsError('final audit artifacts already exist; do not overwrite')
    baseline = load('preservation_baseline.json')
    before = compare_existing(baseline)
    inputs = load('input_verification.json')
    contract = load('semantic_contract.json')
    results = load('experiment_results.json')
    tests = load('test_results.json')
    independent = load('independent_verification.json')
    query_list = results['queries']
    queries = {r['query_id']: r for r in query_list}
    expected_status = {'Q1': 'SAT', 'Q2': 'UNSAT', 'Q3': 'SAT', 'Q4': 'SAT'}
    expected_models = {'Q1': {'A': False, 'B': False}, 'Q2': None,
                       'Q3': {'A': False, 'B': True}, 'Q4': {'A': True, 'B': True}}
    expected_solutions = {k: [] if v is None else [v] for k, v in expected_models.items()}
    baseline_git = baseline['publication_git_state']
    remote_output = git('-c', 'http.proxy=http://127.0.0.1:7890', '-c',
                        'http.version=HTTP/1.1', 'ls-remote', '--refs', 'origin',
                        'refs/heads/main', 'refs/heads/experiment/E12')
    refs = {line.split()[1]: line.split()[0] for line in remote_output.splitlines()}
    local_git = {'branch': git('branch', '--show-current'), 'HEAD': git('rev-parse', 'HEAD'),
                 'local_main': git('rev-parse', 'main'), 'status': git('status', '--porcelain=v1')}
    git_safe = (refs == {'refs/heads/main': MAIN, 'refs/heads/experiment/E12': BASE}
                and local_git == {'branch': 'experiment/E12', 'HEAD': BASE,
                                  'local_main': baseline_git['local_main'], 'status': ''})
    all_query_files_match = True
    for run in query_list:
        raw = (ROOT / run['smtlib_file']).read_bytes()
        saved = load(run['smtlib_file'].removesuffix('.smt2') + '.json')
        all_query_files_match &= (sha(raw) == run['smtlib_sha256']
                                  and raw == run['exact_smtlib'].encode('utf-8') and saved == run)
    for path in ROOT.glob('*.py'):
        ast.parse(path.read_text('utf-8'), filename=path.name)
    historical_inputs_match = all(
        sha((ROOT / 'preflight' / name).read_bytes()) == digest
        for name, digest in baseline['preflight_file_SHA256'].items())
    implementation_match = (
        sha((ROOT / 'e12_nullness_smt.py').read_bytes()) == results['implementation_sha256']
        and sha((ROOT / 'independent_reference.py').read_bytes()) == results['independent_reference_sha256']
        and sha((ROOT / 'test_e12_nullness_smt.py').read_bytes()) == tests['test_code_sha256']
        and sha((ROOT / 'semantic_contract.json').read_bytes()) == results['contract_sha256'])
    failure_files = [p.relative_to(ROOT).as_posix() for p in ROOT.rglob('*failure*.json')
                     if p.is_file() and 'preflight' not in p.relative_to(ROOT).parts]
    criteria = {
        'all_source_and_input_gates_match': inputs['status'] == 'MATCH',
        'five_preflight_files_unchanged': historical_inputs_match,
        'exact_four_queries': len(query_list) == 4 and set(queries) == set(expected_status),
        'four_solver_statuses_correct': all(queries[k]['solver_status'] == v for k, v in expected_status.items()),
        'three_SAT_models_correct': all(queries[k]['model'] == v for k, v in expected_models.items()),
        'all_solver_independent_checks_match': all(r['query_checks_passed'] and
                                                  r['independent_verification']['status'] == 'MATCH'
                                                  for r in query_list),
        'complete_independent_domain': independent['domain_completely_enumerated']
                                      and independent['domain_size'] == 4
                                      and independent['satisfying_assignments'] == expected_solutions,
        'all_22_tests_pass': tests['passed'] and tests['tests_run'] == 22
                           and tests['failures'] == 0 and tests['errors'] == 0,
        'sixteen_formula_reference_comparisons': len(tests['recorded_formula_truth_comparisons']) == 16
                                               and all(r['match'] for r in tests['recorded_formula_truth_comparisons']),
        'only_four_solver_checks': results['solver_check_count'] == 4
                                   and tests['extra_solver_checks'] == 0,
        'counterfactual_and_invalid_encoding_labeled':
            queries['Q3']['classification'] == 'COUNTERFACTUAL_XOR_GUARD_REMOVED'
            and not queries['Q3']['real_source_path_encoding']
            and queries['Q4']['classification'] == 'INVALID_ENCODING_DIAGNOSTIC_ONLY'
            and not queries['Q4']['real_source_path_encoding'],
        'no_unsupported_scope_or_filter_authority':
            contract['original_alert_decision'] is None and not contract['filter_authority']
            and results['full_program_semantics'] == 'UNKNOWN' and not results['blind_test_claim'],
        'saved_SMT_and_result_bytes_match': all_query_files_match,
        'implementation_contract_test_hashes_match': implementation_match,
        'all_existing_research_files_preserved': before['existing_files_unchanged'],
        'publication_git_state_safe': git_safe,
        'no_unresolved_failure_records': not failure_files,
    }
    success = all(criteria.values())
    write_new('acceptance_check.json', {
        'stage': 'E12-1+E12-2', 'local_experiment_checks_passed': success,
        'publish_allowed_by_task_criteria': success, 'criteria': criteria,
        'failure_records': failure_files, 'research_review_state': 'PENDING_GPT_REVIEW',
        'scope': 'local NULL-argument path property; not original-alert adjudication',
        'original_alert_decision': None, 'filter_authority': False,
        'full_program_semantics': 'UNKNOWN'})
    query_rows = '\n'.join('| ' + name + ' | `' + run['formula'] + '` | ' + run['solver_status']
                           + ' | `' + json.dumps(run['model'], sort_keys=True) + '` | '
                           + format(run['elapsed_seconds'], '.9f') + ' |'
                           for name, run in queries.items())
    report = f'''# E12：多变量路径条件组合与故障可达性 SMT 验证

## 1. 结果与认证范围

E12-1 和 E12-2 合并执行完成。本轮局部检查：`{'PASS' if success else 'FAIL'}`；研究状态：等待 GPT 最终审查。四个查询依次为 **Q1=SAT、Q2=UNSAT、Q3=SAT、Q4=SAT**，模型与独立四情况穷举一致。22/22 项测试通过；实际只有 4 次 solver.check，测试和独立参考均没有额外求解。

结论只涉及固定 `test_str_ne` 源码前缀：当第 296 行 `strcmp(s1, s2)` 真正被求值时，s2 的 NULL 状态不能为真。它不认证整个函数、strcmp 内部或非空对象的可读性；不裁决原告警。

```json
{{"original_alert_decision": null, "filter_authority": false, "full_program_semantics": "UNKNOWN", "blind_test_claim": false}}
```

## 2. 样本与冻结输入

- 论文数据文件：`reproduction/upstream/benchmark/NPD/cppcheck/cppcheck_openssl_nullpointer.json`。
- 样本定位：`{inputs['sample_id']}`；零基 row=3，JSON Pointer `/3`，函数字段 `/3/function_code`。
- 原始 function_name=`test_str_ne`、var_name=`s2`、result=0。原始 index **不存在**，未写成 index=3；原标签只作身份元数据，不参与公式。
- 数据集 SHA-256：`{inputs['dataset_sha256']}`。
- 原始函数字符串 UTF-8 SHA-256：`{inputs['function_body_sha256']}`。
- E12-0 提交：`{BASE}`；五份 preflight 文件全部与该远端提交逐字节核对、固定哈希并只读使用。

`input_verification.json` 保留完整原始记录、location、index 缺失状态、五份输入文件哈希和源码对应结果。输入核验在任何求解器构造/check 之前完成；篡改或身份不一致即 UNKNOWN 停止，不替换备选样本。

## 3. 保存的上游源码对应

读取 E12-0 `preflight/source_manifest.json:/upstream_source_observation/raw_source_utf8`，**没有重新下载源码**。

- OpenSSL tag：`openssl-3.4.0`；固定 commit：`{results['source_commit']}`。
- 文件：`test/testutil/tests.c`，17,153 字节。
- 文件 SHA-256：`{inputs['source_correspondence']['sha256']}`。
- 固定函数完整且唯一出现于 291–303 行，与原始函数字节一致。原始位置为第 296 行、第 34–36 列，context 294–298 行，均核对一致。

这只认证已保存源码和 benchmark 文本的对应。原始扫描 TU、编译环境、实际扫描提交及 checker/rule ID 继续 UNKNOWN。没有恢复构建或预处理环境，也没有验证 tag 签名。

## 4. 变量身份与保持关系

第 292 行分别声明 `const char *s1` 和 `const char *s2`，参数零基序号分别为 4、5；是两个独立参数身份，而不是按名字合并的一个变量。映射为两个独立 Bool：

| 变量 | C 含义 | SMT 标识 |
| --- | --- | --- |
| A | s1 == NULL | e12_test_str_ne_s1_is_null |
| B | s2 == NULL | e12_test_str_ne_s2_is_null |

入口到目标调用求值前没有指针参数重写、变量地址逃逸、其他调用、循环或 goto，因此分别引用各自入口值。`const char *` 并不保证指针变量不变；值保持来自已核对前缀中的实际无写入。未创建或修改 R02/R05 ID，未开展跨帧传播。

不假设指针位宽、不编码地址、不把 NULL 当成全零地址位模式，不假设两指针指向不同对象。有限空值抽象允许两个非空指针互相别名，但不验证内存别名、对象生命周期或读取合法性。

## 5. C 条件、极性和调用求值边界

```c
/* 294 */ if ((s1 == NULL) ^ (s2 == NULL))
/* 295 */   return 1;
/* 296 */ if (s1 == NULL || strcmp(s1, s2) == 0) {{
```

两个相等比较各产生 int 0 或 1；对这两个整数执行按位 XOR，与本抽象的布尔 XOR 精确对应。不是对指针位模式异或。294 行条件为真时在 295 行返回，因此继续执行取 **NOT(XOR(A,B))**。

C 的 `||` 从左向右短路。只有左侧 `s1 == NULL` 为假才会对右侧 strcmp 求值，因此调用边界另需 **NOT(A)**。进入 296 行条件的求值，不代表调用 strcmp；两指针均空时会继续到该行，但在左侧短路。

不使用尚未产生的 `strcmp(...) == 0` 返回值作为调用发生前的条件。后续 test_fail_string_message、strlen 和 return 不纳入目标调用前缀，也不认证这些行为。

## 6. 有限语义合同与故障条件

`semantic_contract.json` 冻结以下关系；实现只接受本样本、固定哈希和此二变量抽象：

```text
A = (s1 == NULL)
B = (s2 == NULL)
PC = NOT(XOR(A, B)) AND NOT(A)
Fault = B
core fault query = PC AND B
```

没有预加 NOT(B)，没有调用者前提或其他样本条件，没有把原标签当约束。SMT 逻辑为 QF_UF 的纯布尔子集，只有这两个 Bool 常量，无位向量、量词、指针地址或完整内存模型。

## 7. 四个求解查询

使用现有 Z3 `{results['solver']['version']}`，包版本 `{results['solver']['package_version']}`，每个查询 timeout=30000 ms。每个查询只执行一次 check。准确 SMT-LIB 原文及哈希、公式、模型、耗时、分类和独立状态同时保存在 `experiment_results.json` 与 `queries/*.json`，四个 `.smt2` 文件另行保存。

| 查询 | 公式 | Z3 状态 | 模型（A/B 为 NULL 状态） | check 耗时（秒） |
| --- | --- | --- | --- | --- |
{query_rows}

Q1 为真实源码调用可达性；其唯一抽象输入为两个指针均非空。Q2 将故障 B 加到完整真实路径条件，结果 UNSAT，无模型。未生成 UNSAT 证书，也未声称独立检查了求解器证书；此处额外使用独立有限域穷举核对。

UNKNOWN 按 UNKNOWN 保存，不转换为 UNSAT；查询或独立验证不通过即保留失败并禁止发布。四个本次实际返回均不是 UNKNOWN。

## 8. 独立 Python 四情况穷举

`independent_reference.py` 仅导入 Python 标准库，不导入 Z3 或 SMT 实现，不读取标签/历史裁决。它先计算 int 0/1 的 XOR，再执行提前返回，最后按 OR 左侧决定是否调用；不是调用 SMT 公式来充当独立参考。

| A | B | 第一条件 int | 提前返回 | OR 左侧是否求值/其值 | strcmp |
| --- | --- | --- | --- | --- | --- |
| false | false | 0 | 否 | 是 / false | 执行 |
| false | true | 1 | 是 | 不求值 | 不执行 |
| true | false | 1 | 是 | 不求值 | 不执行 |
| true | true | 0 | 否 | 是 / true | 不执行 |

该四情况完全覆盖**两个布尔变量的抽象域**；独立解集分别为 Q1={{(false,false)}}、Q2=空集、Q3={{(false,true)}}、Q4={{(true,true)}}。与四个 Z3 状态及三个 SAT 模型均一致。穷举不是完整 C 指针、字符串或程序状态空间的穷举。

`independent_verification.json` 保存四条执行轨迹、每个查询的独立解集和状态、参考代码哈希。测试对四个公式各作四次具体替换，共记录 16 条公式/参考比较；另解析保存的 SMT-LIB，再按同一域核对，均不调用 solver.check。

## 9. 反事实与错误编码诊断

**Q3：COUNTERFACTUAL_XOR_GUARD_REMOVED。** 删除第一条 XOR/return 守卫，只保留 NOT(A) AND B，SAT 模型为 A=false、B=true。把该模型放回原源码，294 行为真，会提前返回，实际不会调用 strcmp。Q3 是反事实对照，不是原告警真实故障证据。

**Q4：INVALID_ENCODING_DIAGNOSTIC_ONLY。** 故意遗漏 296 行的 OR 短路约束，只用 NOT(XOR(A,B)) AND B，SAT 模型为 A=true、B=true。原源码此时在 296 行左侧为真而短路，实际不调用 strcmp。Q4 证明错误编码会产生伪调用路径，不能用作实际程序路径或真实故障。

两个诊断记录均标记 `real_source_path_encoding=false`，同时保存相应模型在真实源码参考解释器中的“不调用”轨迹。没有将它们混入 Q1/Q2 的真实路径结论。

## 10. 边界、错误输入和测试

`test_e12_nullness_smt.py`：**22/22 通过，0 失败、0 错误、0 额外求解**。整个测试套件阻断 Solver/SolverFor 构造；解析 SMT-LIB 不执行其中 check-sat。

覆盖数据集字节篡改、函数 XOR 篡改、目标位置/函数/变量不匹配、缺失 index 被错误补造、原标签身份及不参与公式、保存源码哈希/commit、输入失败先于求解器和结果写入、备选/内存/指针 ABI 等不支持输入拒绝、两个参数身份、XOR 与 OR 区别、分支极性、提前返回、短路和目标求值边界、四公式与独立参考、Q3/Q4 分类、没有预加 NOT(B) 或返回值、精确 SMT-LIB/结果哈希、未生成证书、过滤权限关闭和求解次数。

本轮没有执行失败需要修复或重跑。所有结果、查询和审计输出独占新建；代码的失败路径会保留 UNKNOWN 记录并阻止发布，不能覆盖既有失败记录或换用 test_strn_ne。

## 11. 三类证据分别支持什么

| 证据层 | 本轮内容 | 支持范围 |
| --- | --- | --- |
| 源码静态语义依据 | 固定字节、声明、行号、C int XOR、return 和 OR 求值顺序 | 支持这段源码前缀到有限空值合同的映射，非原扫描 TU 认证 |
| Z3 求解 | 4 个准确布尔查询及 3 个 SAT 模型、1 个 UNSAT | 支持所编码公式的可满足性结论，不自行证明 C 建模完整 |
| Python 独立验证 | 4 种输入顺序执行、完整有限解集、模型核对 | 完整覆盖该二布尔抽象，非内存模型或 Z3 证书 |

三层一致才作为本轮局部实验检查通过；文件保护另行验收，不将其替代为语义依据。

## 12. 研究结论与未解决问题

可以正确组合两个变量的关联条件、提前返回和短路边界：仅知道两个空值相同不足以进入调用，仅知道 s1 非空也不足以排除 s2 为空；完整源码路径共同排除了空实参故障。Q3 和 Q4 各自展示缺失一种守卫时的反事实/伪路径。

该实验验证有限多变量空值路径机制，未重做 R01-R05；与 E10 的跨函数调用者范围、E11 的赋值归一化和值版本转换不同。本实现没有发展为通用 C-to-SMT 编译器，也没有扩大样本或研究备选。

仍未解决且不宣称已认证：

- 原始 checker/rule ID、原扫描 TU、编译环境、实际扫描提交：UNKNOWN。
- 非空对象的有效生命周期、可读范围、NUL 终止、悬空指针、完整地址/堆、内存破坏与并发：未验证。
- strcmp 返回值、实际实现及内部读取，整个 test_str_ne、后续日志/strlen、调用者或完整程序：未认证。
- 无独立检查的求解器 UNSAT 证书；独立穷举只覆盖明确二布尔抽象。
- 样本已接触过，盲测声明为 false；原标签不重标注，不提高或报告整体数据集准确率。

即使 Q2 为 UNSAT，也不能直接把原告警标为误报或 FILTER。原告警裁决保持 null，filter_authority=false，full_program_semantics=UNKNOWN。

## 13. 文件保护

创建任何 E12-1/E12-2 新文件之前建立 `preservation_baseline.json`，记录 {baseline['protected_file_count']} 份既有非凭据文件。包含 E01-E11、完整 E12-0 preflight、原始数据、audit、R01-R05 和其他已有研究文件。

保护沿用 E10/E11：排除 .git、.venv、__pycache__、node_modules，排除 .env/.env.*、.key/.pem/.pfx/.p12 和声明的凭据名称模式；不记录凭据内容。`preservation_check.json` 单独记录原文件逐字节比较、范围外新增检查、preflight 哈希和 Git 状态。文件保护 PASS 只表示文件未变，不等于语义或告警通过。

本轮新增文件均在 E12 根目录或 queries 下，preflight 内不新增、不修改。未运行 E01-E11 历史回归、原分析器、Harness、LLM API、项目构建、源码或数据下载；没有安装或升级依赖。

## 14. Git 发布记录与交付

执行前及发布前检查分支 `experiment/E12`、HEAD `{BASE}`、远端 main `{MAIN}`、工作区干净；五份 preflight 与远端对应。未 reset、修改旧提交或切换备选。受保护的本地 main `{baseline_git['local_main']}` 及其未发布历史保留，不并入本轮提交。

仅在 `acceptance_check.json` 全部局部标准通过时，向已有 `experiment/E12` 正常提交并推送本轮新增文件；不修改远端 main、不 force push。提交前检查 staged diff、文件清单和源文件/副本/Git blob 字节一致性；推送后核对分支 HEAD 与 main。实际发布 SHA 由最终回复/远端 Git 提交提供，冻结报告不改写为自引用提交号。

`publication_file_list.md` 列出本轮新文件；`artifact_hashes.json` 冻结全部新产物及受保护 preflight 的哈希。四个 SMT-LIB 文件对应 Q1–Q4，旁边 JSON 保留单次求解结果。实现和测试入口使用既有 Python -B 环境；由于结果独占创建，不应在本冻结目录重跑实验或覆盖测试，复核可读取已保存记录。

E12-1+E12-2 到此停止，等待 GPT 最终研究审查，不进入 E13，不修复或修改 E10/E11。
'''
    text_new('E12_report.md', report)
    text_new('execution_log.md', '''# E12-1 + E12-2 execution log

1. Read the complete user attachment and all frozen preflight inputs. Verified experiment/E12 at 3d58641c8c62e80d60e82d137b03bcba7b8ed5cd, clean worktree and main at f4850309b19cd049ff38356881549bb33c615144. Fetched only Git branch metadata/objects; downloaded no source/dataset.
2. Compared all five original preflight files against the fetched remote commit and publication checkout bytes. Captured preservation_baseline.json before creating implementation or result files.
3. Confirmed existing Z3 4.13.4 / z3-solver 4.13.4.0; installed nothing. Added the frozen finite semantic contract, separate Python reference, SMT implementation and E12-only tests.
4. Parsed three initial Python files, loaded all fixed source/dataset/preflight/contract gates, and wrote input_verification.json plus implementation_preflight.json. Zero solver checks at this point; no original index invented.
5. Ran e12_nullness_smt.py once using the existing Python -B. Saved exactly Q1/Q2/Q3/Q4 and their JSON records. Results SAT/UNSAT/SAT/SAT with models (false,false), none, (false,true), (true,true); four solver checks total. The separate Python reference enumerated all four inputs, without Z3.
6. Ran test_e12_nullness_smt.py once using Python -B. 22 tests passed, no failures/errors or extra solver checks. Saved 16 formula/reference truth comparisons; solver constructors were blocked throughout the suite.
7. Ran complete_e12_audit.py for read-only file/hash/Git checks, acceptance, reports and final artifact hashes. This step invokes no solver or historical tests. No implementation, result, preflight or failure record was overwritten.

Publication is conditional on every acceptance criterion. Only new E12 files are eligible for the existing experiment/E12 branch; main is never a push destination. Q3 is counterfactual, Q4 is INVALID_ENCODING_DIAGNOSTIC_ONLY. Original-alert decision remains null, filtering authority false, full-program semantics UNKNOWN.
''')
    existing = {p.relative_to(ROOT).as_posix() for p in ROOT.rglob('*') if p.is_file()
                and 'preflight' not in p.relative_to(ROOT).parts}
    planned_paths = sorted(existing | final_names)
    text_new('publication_file_list.md', '# E12-1 + E12-2 publication file list\n\n'
             + str(len(planned_paths)) + ' new files under '
             '`reproduction/safety_runs/E12_multi_variable_path_smt/`.\n'
             + 'The five preflight files are protected existing inputs and are excluded from this new-file list.\n\n'
             + '\n'.join('- `' + p + '`' for p in planned_paths) + '\n')
    final_preservation = compare_existing(baseline)
    if not final_preservation['existing_files_unchanged']:
        raise RuntimeError('existing file preservation changed during finalization; do not publish')
    write_new('preservation_check.json', {
        'status': 'PASS' if final_preservation['existing_files_unchanged'] else 'FAIL',
        'recorded_at_UTC': datetime.now(timezone.utc).isoformat(),
        'protected_file_count': baseline['protected_file_count'],
        **final_preservation, 'preflight_files_unchanged': historical_inputs_match,
        'protected_preflight_SHA256': baseline['preflight_file_SHA256'],
        'exclusions': baseline['exclusions'], 'publication_git_state_before_copy': local_git,
        'verified_remote_refs_before_copy': refs, 'publication_branch': 'experiment/E12',
        'expected_new_artifact_paths_including_final_manifests': planned_paths,
        'scope': 'existing-file and Git preservation only, not semantic acceptance',
        'original_alert_decision': None, 'filter_authority': False,
        'full_program_semantics': 'UNKNOWN'})
    hashes = {p.relative_to(ROOT).as_posix(): sha(p.read_bytes())
              for p in sorted(ROOT.rglob('*')) if p.is_file()
              and 'preflight' not in p.relative_to(ROOT).parts}
    write_new('artifact_hashes.json', {
        'algorithm': 'SHA-256', 'scope': 'all new E12 files except this self-referential manifest',
        'new_files_excluding_this_manifest': hashes,
        'protected_preflight_files': baseline['preflight_file_SHA256']})
    actual_paths = sorted(p.relative_to(ROOT).as_posix() for p in ROOT.rglob('*')
                          if p.is_file() and 'preflight' not in p.relative_to(ROOT).parts)
    if actual_paths != planned_paths:
        raise RuntimeError('final publication list mismatch; do not publish')
    print(json.dumps({'local_experiment_checks_passed': success,
                      'protected_files_unchanged': baseline['protected_file_count'],
                      'preflight_files_unchanged': 5, 'new_files': len(actual_paths),
                      'tests_passed': tests['tests_run'], 'solver_checks': results['solver_check_count'],
                      'failure_records': failure_files}))
    if not success:
        raise SystemExit(2)


if __name__ == '__main__':
    main()
