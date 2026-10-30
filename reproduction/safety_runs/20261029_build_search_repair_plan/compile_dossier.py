"""Assemble read-only search/code-review findings and a proposed experiment plan.

No model, extractor, engine, solver, policy or experiment runner is executed.
Existing evidence is referenced by hash; all outputs use exclusive creation.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SEARCH = HERE / 'search'


def load(p):
    return json.loads(p.read_text(encoding='utf-8'))


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def link(p, label=None, line=None):
    return f'[{label or p.name}](<{p.as_posix()}' + (f':{line}' if line else '') + '>)'


def put(name, data):
    with (HERE / name).open('x', encoding='utf-8', newline='\n') as f:
        f.write(data if isinstance(data, str) else json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def main():
    conclusion = load(SEARCH / 'search_conclusion.json')
    before = load(HERE / 'state_before.json')
    correspondence = load(SEARCH / 'a10_restore_correspondence.json')
    metrics = load(ROOT / 'safety_runs/20261029_v1/offline_regression/metrics.json')
    holdout = ROOT / 'safety_runs/20261029_v1/fixed_holdout.json'
    audits = ROOT / 'audit/failure_audit_20261029/audit_samples.json'

    # Exact current-file locations, not line numbers inferred from a new checkout.
    locations = {
        'upstream/llm4pfa/extract_util_plus.py': [(164, 174), (1137, 1187), (640, 655), (748, 801)],
        'upstream/llm4pfa/prompt_templates.py': [(136, 151), (171, 187)],
        'upstream/llm4pfa/feasibility_analysis_pipeline.py': [(116, 125), (155, 184), (276, 283), (420, 433)],
        'completion/engine.py': [(17, 23), (26, 42), (64, 69), (83, 108), (158, 170)],
        'completion/context.py': [(75, 100), (141, 161)],
        'completion/solver_worker.py': [(35, 46), (63, 72)],
        'safety/policy.py': [(38, 69), (117, 139), (157, 177), (198, 215)],
        'safety/metrics.py': [(18, 43), (45, 63)],
    }
    numbered = ['# 现有实现的只读代码证据', '',
                '本文件只摘录代码，不导入或执行流水线。行号来自已冻结当前文件。', '']
    code_index = []
    for name, ranges in locations.items():
        p = ROOT / name
        ls = p.read_text(encoding='utf-8').splitlines()
        code_index.append({'path': str(p), 'sha256': sha(p), 'line_ranges': ranges})
        numbered += [f'## {name}', '', f'SHA-256: `{sha(p)}`', '', '```text']
        for a, b in ranges:
            numbered += [f'{i}: {ls[i-1]}' for i in range(a, b + 1)] + ['']
        numbered += ['```', '']
    put('code_review_evidence.md', '\n'.join(numbered))
    put('code_review_locations.json', code_index)

    repairs = [
        {
            'id': 'R01', 'priority': 'P0-1', 'topic': '条件极性与合并完整性',
            'locations': ['upstream/llm4pfa/prompt_templates.py:136-148,171-187',
                          'upstream/llm4pfa/feasibility_analysis_pipeline.py:174-179,276-282',
                          'completion/engine.py:110-130'],
            'cases': ['A01: copied!=0 与 copied==0 同时进入最终查询，UNSAT 导致标签1被过滤',
                      'A10: 双重否定和合并正确的局部逻辑对照，不代表可批准过滤'],
            'confirmed_scope': 'A01 的翻译极性与合并错误已由原日志和既有诊断确认；不是证明其完整C路径一定可行',
            'minimum_change': '为已知类型的简单标量空值/零值条件保存原表达式、分支方向、符号和来源；用确定性规则核对生成原子；与来源不一致则拒绝该候选，保持UNKNOWN。不自动删除任意矛盾断言。',
            'verification': '不含样本ID的参数化合成条件与A01/A10缓存输出；验证正确否定、错误极性可定位、合并不改名/不丢失。原提示词!ptr→ptr!=0另行纠错但不能以离线缓存证明提示词效果。',
        },
        {
            'id': 'R02', 'priority': 'P0-2', 'topic': '目标定位及提前退出的控制范围',
            'locations': ['completion/context.py:141-161', 'completion/engine.py:158-170',
                          'upstream/llm4pfa/extract_util_plus.py:1139-1152,164-174,640-801',
                          'upstream/llm4pfa/feasibility_analysis_pipeline.py:159-170'],
            'cases': ['A03: 同文目标两处，循环覆盖为最后一处；空格缩进遗漏case/while',
                      'A06: 空格缩进丢失switch分支',
                      'A02: 分配分支内!skb保护未证明支配所有进入路径'],
            'confirmed_scope': '重复目标和Tab依赖已确认；A02控制范围与原标签冲突仍未裁决',
            'minimum_change': '分两次：先要求位置/源码身份唯一，重复且无法绑定行号时UNKNOWN；再修空格/Tab和无歧义块结构。提前return/goto必须具有可证明的路径范围，不能把向上扫描得到的局部guard当全局支配条件；复杂跳转先拒绝。',
            'verification': '重复同文语句在不同分支、不可识别绝对行、混合缩进、多行条件、switch穿透、循环和goto绕过的合成片段；A03/A06结构结果只与已核验位置比较，不猜枚举值。',
        },
        {
            'id': 'R03', 'priority': 'P0-3', 'topic': '符号身份、类型与赋值版本',
            'locations': ['completion/solver_worker.py:35-46,63-72',
                          'upstream/llm4pfa/prompt_templates.py:145-148,183-187',
                          'completion/context.py:86-100'],
            'cases': ['A04: object:Int/object_ptr:Int/object_bv:BitVec64被建成独立符号',
                      'A02: 多次skb赋值未区分版本',
                      '既有same_symbol_sort_audit记录: dev同名Bool/Int'],
            'confirmed_scope': 'A04身份拆分已确认；没有足够证据为所有指针强加64位或任意别名等式',
            'minimum_change': '先增加符号清单核对，按作用域/声明/赋值版本登记；同一实体多个独立表示、同名异sort或未绑定重赋值先UNKNOWN。别名关系只由具体赋值/参数证据引入，缺位宽不擅自Int2BV。完整SSA不在首轮范围。',
            'verification': '相同变量不能无依据拆分；不同作用域同名变量不能强行合并；重赋值产生新版本；未知类型保持UNKNOWN。A04仅允许诊断连接，不因此批准FILTER。',
        },
        {
            'id': 'R04', 'priority': 'P1-1', 'topic': '赋值提取的函数头占位与缺失状态',
            'locations': ['completion/engine.py:83-86',
                          'upstream/llm4pfa/feasibility_analysis_pipeline.py:159',
                          'upstream/llm4pfa/extract_util_plus.py:1137-1154,1165,1183'],
            'cases': ['A10: variable_assignments.text=static void',
                      'A01/A02/A04: variable_assignments.text也是函数签名'],
            'confirmed_scope': '上游None输入+assignment_line_index=0直接制造占位；当前主流程并未消费variable_assignments字段，不能把仅修占位说成效果修复',
            'minimum_change': '先将未提供/未找到赋值表示成显式missing/空结果及原因，禁止函数头冒充赋值；另一次变更再提取目标前已定位的简单赋值（含声明初始化），多候选/链式赋值未建模时UNKNOWN，不盲取最近文本。',
            'verification': 'None、未找到、目标后赋值、声明、初始化、重复赋值、链式赋值及遮蔽；A10可见lookup位置应作为候选附来源，不冒称扫描Source。原始JSON不改写。',
        },
        {
            'id': 'R05', 'priority': 'P1-2', 'topic': '跨函数状态传递与条件中的调用识别',
            'locations': ['completion/context.py:75-100,163-180',
                          'completion/engine.py:88-97',
                          'upstream/llm4pfa/feasibility_analysis_pipeline.py:159-162,420-433'],
            'cases': ['A08: 形参名映射正确但两帧只留下各自的空指针假设',
                      'A05: !WARN_ON(!sta)被当作不支持的复合实参阻塞'],
            'confirmed_scope': '参数位置映射成功不等于值/路径状态已传递；原函数入口重提取覆盖传入条件，未绑定caller/callee符号环境',
            'minimum_change': '先显式记录跨帧输入/输出与实际参数等式，仅支持已确认的直接实参；未绑定则UNKNOWN。区分布尔条件包装与真实指针参数调用，不将!sta当sta，不随意略过宏。',
            'verification': '两函数简单指针传递、同名/异名、遮蔽、调用前重赋值、无支持宏/复合实参的合成案例；A08检查状态是否缺失，A05只消除误识别而不自动放行宏语义。',
        },
        {
            'id': 'R06', 'priority': 'P1-3', 'topic': 'SMT断言与源码的语义来源绑定',
            'locations': ['safety/policy.py:38-69,117-177,198-215',
                          'completion/solver_worker.py:43-46',
                          'safety/metrics.py:22-43,52-63'],
            'cases': ['A10: UNSAT可重放但原始构建身份不齐',
                      'A01: 可解的生成脚本可表达错误断言',
                      'A02/A04: 作用域/变量状态证据未闭合'],
            'confirmed_scope': '求解重放只证明公式；现有安全门槛有效阻止无完整复核的FILTER',
            'minimum_change': '补充逐断言来源清单：代码哈希/范围、角色、分支方向、符号版本/类型、宏证据、模型输出及查询哈希；保留六条件门槛与独立复核要求。UNSAT core只能辅助定位，不自动成为证明或批准。',
            'verification': '缺任一关键来源/源码变化/类型冲突/模型输出截断/UNSAT无来源均UNKNOWN；继续验证UNKNOWN不算过滤。诊断层不得自签manual_source_review。',
        },
        {
            'id': 'R07', 'priority': 'P2', 'topic': '输出解析及可执行性问题',
            'locations': ['completion/engine.py:99-108', 'completion/model.py:88-90'],
            'cases': ['A06: JSON解析抓取前面的C代码块', 'A07: 输出截断'],
            'confirmed_scope': '旧审计已有5条合法JSON解析失败的证据；不重新统计或调用模型',
            'minimum_change': '明确JSON块标签与schema，歧义或截断继续失败/UNKNOWN；单独修复，不同极性、状态传播一起修改。',
            'verification': '只用已保存混合C/JSON/解释文本和截断输出；解析成功不能直接变成FILTER。',
        },
    ]
    put('priority_repairs.json', repairs)

    experiment = {
        'status': 'planned_not_executed', 'next_experiment': 'E01_predicate_polarity_consistency',
        'single_primary_issue': 'R01', 'model_calls_allowed': False, 'full_benchmark_allowed': False,
        'safety_policy_changes_allowed': False, 'sample_id_special_cases_allowed': False,
        'audit_manifest': {'path': str(audits), 'sha256': sha(audits), 'count': 10},
        'fixed_regression_holdout': {'path': str(holdout), 'sha256': sha(holdout), 'count': 20,
            'status': 'existing fixed regression holdout; already executed benchmark, not untouched blind test',
            'replacement_or_reselection_allowed': False},
        'baseline_metrics': {'path': str(ROOT / 'safety_runs/20261029_v1/offline_regression/metrics.json'),
                             'sha256': sha(ROOT / 'safety_runs/20261029_v1/offline_regression/metrics.json')},
        'synthetic_syntax_scope': ['known pointer/integral scalar x', '!x', '!!x', 'x==0', 'x!=0',
                                   'unambiguous true/false edge for if(x) and if(!x)'],
        'unsupported_for_initial_check': ['unknown types', 'macro returns without evidence',
            'mixed-width pointer/integer operations', 'unresolved reassignment/aliasing',
            'non-dominating early exits and complex goto flow'],
        'planned_outputs': ['frozen_inputs.json', 'changes.patch', 'predicate_checks.json',
                           'derived_diagnostics.json', 'decisions.json', 'metrics.json',
                           'tests.log', 'preservation_verification.json'],
        'execution_phases': ['freeze isolated candidate sources and existing inputs without changing old baselines',
            'implement only general predicate polarity consistency helper; no model client or constructor',
            'run parameterized synthetic and A01/A10 saved-output checks',
            'run all ten debug cases offline; freeze code before holdout',
            'evaluate exactly twenty sealed regression cases with same frozen code, no tuning on holdout',
            'report debug/holdout separately and stop on any real-bug deletion or unsupported FILTER'],
        'cache_semantics': 'Saved responses can validate their original exact prompt/input only; new extraction or prompt invalidates equivalence. Use explicit deterministic diagnostics or UNKNOWN, never claim offline cached output equals a new LLM experiment.',
        'gate_expectation': 'No new complete semantic approval expected. Zero FILTER may persist; judge polarity detection separately from filtering performance.',
        'stop_conditions': ['any label-1 FILTER', 'UNKNOWN counted as filtering success',
            'incomplete evidence auto-filtered', 'holdout changed or used for case-specific tuning',
            'network/model call attempted', 'multiple principal issues changed together'],
    }
    put('experiment_plan.json', experiment)

    # A complete provenance index, including safe historic snippets and copied source members.
    evidence = []
    for p in sorted(SEARCH.rglob('*')):
        if not p.is_file():
            continue
        meta_path = p.with_name(p.name + '.metadata.json')
        meta = load(meta_path) if meta_path.exists() else {}
        entry = {'path': str(p), 'sha256': sha(p), 'bytes': p.stat().st_size,
                 'source_url': meta.get('url'), 'http_status': meta.get('http_status')}
        if p.suffix in ('.tex', '.bib', '.md', '.py', '.json'):
            entry['line_range'] = [1, len(p.read_text(encoding='utf-8').splitlines())]
        if 'paper_source_excerpts' in p.parts:
            entry['origin'] = 'member in arxiv_v1_source.response; member path is relative to paper_source_excerpts'
            entry['archive_sha256'] = sha(SEARCH / 'arxiv_v1_source.response')
        elif p.name.endswith('.metadata.json'):
            entry['origin'] = 'local public GET metadata, linked to payload by name and SHA-256'
        elif not meta:
            entry['origin'] = 'derived read-only inspection; original filenames/commits/links named inside JSON'
        evidence.append(entry)
    put('evidence_index.json', {'search_files': evidence, 'code_files': code_index})
    lines = ['# 证据来源与哈希', '',
             '下载正文旁保留同名metadata；论文摘录来自固定v1源码包，不是重新生成的扫描数据。', '',
             '| 本地路径 | 来源 / 对应关系 | 行范围 | SHA-256 |', '|---|---|---|---|']
    for e in evidence:
        p = Path(e['path'])
        origin = e.get('source_url') or e.get('origin')
        span = '–'.join(map(str, e['line_range'])) if 'line_range' in e else '二进制包/见成员清单'
        lines.append(f"| {link(p, p.relative_to(HERE).as_posix())} | {origin} | {span} | `{e['sha256']}` |")
    for e in code_index:
        p = Path(e['path'])
        spans = ', '.join(f'{a}–{b}' for a, b in e['line_ranges'])
        lines.append(f"| {link(p, p.relative_to(ROOT).as_posix())} | 当前冻结实现；只读审查 | {spans} | `{e['sha256']}` |")
    put('evidence_index.md', '\n'.join(lines) + '\n')

    repair_text = '''# 通用算法修复计划（尚未实施）

第一目标为真实缺陷保留，第二目标为误报过滤。基线和 real-bugs-first-v1 六条件门槛均保留，任何新增检查只提供诊断或拒绝不可靠候选，不能自签过滤批准。以下样本 ID 仅用于测试夹具与报告，不得进入生产条件、白名单、例外分支或符号转换逻辑。

当前代码是基于 2025 旧实现的 documented completion，并非新增 restore 分支。审查发现 restore 分支近期补齐部分模块，但仍标明候选来源且缺 dereferences；此阶段不切换代码、不把它当原论文完整实现。未来若比较新分支，必须另设版本与实验，不与本轮单问题修复混合。

'''
    for item in repairs:
        repair_text += f"## {item['priority']} / {item['id']}：{item['topic']}\n\n"
        repair_text += '代码位置：\n\n'
        for ref in item['locations']:
            name, ranges = ref.rsplit(':', 1)
            first = int(ranges.split(',')[0].split('-')[0])
            repair_text += f"- {link(ROOT / name, name, first)}；相关行 {ranges}。\n"
        repair_text += '\n既有案例：' + '；'.join(item['cases']) + '。\n\n'
        repair_text += '证据边界：' + item['confirmed_scope'] + '。\n\n'
        repair_text += '最小修改：' + item['minimum_change'] + '\n\n'
        repair_text += '验证：' + item['verification'] + '\n\n'
    repair_text += '''## 实施顺序与避免混杂

先做 R01 的通用极性一致性检查，解决已见真实缺陷误删的直接错误来源。R02 必须拆成定位唯一性和控制范围/缩进两轮；R03 拆成本地符号身份与后续赋值版本；R04 拆成去掉假占位和真正赋值恢复；R05 拆成状态绑定与宏/调用识别。每轮只变一个主要问题。

R04 去占位是小而确定的真实性修复，可在其单独轮次执行，不能和 R01 同时改后把指标变化归给某一个。当前主流程只读取 bug_line_constraints、target_conditions 和 early_jump_constraints；未消费 variable_assignments。故只把 static void 换成 missing 会改善证据契约，不会自动补出别名关系或改变旧最终预测。

R02 不应仅把空格全改Tab就宣布C控制流正确；该做法仅为旧审计的诊断探针。R03 不应把所有同名变量绑定，也不应把所有指针硬编码64位。R06不修改既有FILTER门槛，完整来源也不能代替真实语义复核。R07解析成功只代表格式通过，仍须走相同安全门槛。

下一轮先实现 R01 的小范围一致性核对，暂不重建整套C前端、完整SSA或代理框架。修复代码允许识别语法、类型和来源；禁止识别样本ID、标签或项目中的某个函数名来决定例外。
'''
    put('repair_plan.md', repair_text)

    baseline_rows = []
    for cohort in ['audit', 'holdout', 'combined']:
        b = metrics[cohort]['guarded']
        counts = metrics[cohort]['verdict_counts']
        baseline_rows.append({'cohort': cohort, 'counts': counts, 'metrics': b})
    put('baseline_reference.json', {
        'status': 'existing_results_referenced_not_recomputed',
        'source_path': str(ROOT / 'safety_runs/20261029_v1/offline_regression/metrics.json'),
        'source_sha256': sha(ROOT / 'safety_runs/20261029_v1/offline_regression/metrics.json'),
        'cohorts': baseline_rows,
        'audit_manifest_sha256': sha(audits), 'fixed_holdout_sha256': sha(holdout),
    })
    experiment_text = f'''# 下一次最小修复实验计划

状态：**仅计划，未执行**。下一次建议实验 `E01_predicate_polarity_consistency`，只处理 R01 条件极性一致性。模型调用0、全量重跑0、安全门槛变更0，不为A10通过增加例外。

## 固定输入与比较对象

- 调试集：原有十条审计样本，使用 {link(audits)}，SHA-256 `{sha(audits)}`。不能只跑A01然后宣称整体修复。
- 固定回归留出集：原20条，{link(holdout)}，SHA-256 **`{sha(holdout)}`**，8条标签1、12条标签0。保持所有ID、分层、顺序和失败样本；不替换、不重新抽样。
- 该留出集来自已经执行过的基准，之前也已回放，属于固定回归集，不是未接触的盲测。开发仅使用调试集和通用合成片段，不依据留出单条失败调整代码；若查看留出细节并调参，须标注额外污染，仍不换样本。
- 比较上游旧基线、冻结安全v1、E01离线派生结果，三者各自保留，不能覆盖旧配置或结果。

## E01 的范围与步骤

1. 在独立候选目录固定输入、补丁、代码哈希和版本；保留既有安全策略。不要直接构造真实 `DeepSeekModel` 或 `CompletedEngine`：前者读取密钥，后者的 `completed_source()` 会写入现有 patches/。离线夹具使用只读字典、纯函数和隔离输出。
2. 只实现通用 `原谓词 + 分支方向 + 已知类型/符号 -> 生成原子的一致性检查`。首轮限定为已知指针或整数标量的 `x`、`!x`、`!!x`、`x==0`、`x!=0`，以及明确的true/false边。未知类型、宏、别名、重赋值或复杂控制流标为unsupported/UNKNOWN。不是实现完整C约束翻译器。
3. 对已保存的原子核对来源极性；A01中 `if(!copied)` 真分支不应生成 `copied!=0`。发现不一致应拒绝候选并指出错误断言，不能为了SAT删去任意一条冲突。可另存确定性小片段诊断公式，但不得替换原SMT日志或把它当完整程序新预测。
4. 用参数化合成片段验证零/非零边、重复否定、括号、同名异作用域、未知类型及不支持宏；再用A01/A10原响应作为真实回归。测试逻辑不能包含Axx/样本ID或标签特判。A10的正确局部极性不应被误标为反向，但最终仍UNKNOWN。
5. 离线检查全部10条调试样本并冻结候选代码；再以同一候选检查固定20条回归集。每条记录适用性、错误/拒绝原因、原候选、派生判定、六条件证据完整性及耗时，失败不得丢弃。
6. 分别输出调试、留出及合计指标；保存补丁、测试日志、逐条JSON、指标和哈希校验。不调用API，不因指标不好换样本，不重跑完整基准。

## 缓存与因果边界

原LLM响应只能代表当时的精确提示词/输入。如果之后修改条件提取或提示词，不得继续用旧响应冒称修复后端到端运行结果。可做原响应一致性验证，或明确标记确定性支持子集的诊断；不支持或缓存失配输出UNKNOWN。仅修正提示词中错误的 `!ptr -> ptr!=0` 例子，无法在不重新调用模型时证明新输出改善，应单独记录“提示词变更、效果未评估”。

安全v1仍要求独立、完整且绑定的语义复核；本轮预计不会凭缓存产生新获批FILTER。FILTER保持0也可能是正确回归结果，但不能据此宣称算法有效。极性错误检出率、支持子集覆盖和拒绝原因要与最终过滤指标分开。

## 指标及分母

以数据原标签0=误报、1=真实缺陷为评估参照，保留逐条标签疑点，不冒称独立真值：

- FILTER / KEEP / UNKNOWN分别计数；UNKNOWN始终action=KEEP。
- 真实缺陷操作保留率 = `(标签1且KEEP或UNKNOWN) / 全部标签1`，目标100%。同时单报明确KEEP率与真实缺陷UNKNOWN率，不能把操作保留说成语义识别。
- 真实缺陷误删率 = `(标签1且FILTER) / 全部标签1`，目标0%；列出每个误删案例。
- 误报过滤率 = `(标签0且FILTER) / 全部标签0`；UNKNOWN、异常和未处理误报仍留在分母。
- UNKNOWN率 = `UNKNOWN / 全部固定样本`；自动过滤数和每条证据是否完整单列。缺标签另列，不补标签。
- 三列混淆矩阵分别列两类标签。误报为正类时Precision只在FILTER中计算，Recall等于上述过滤率；无FILTER时Precision/F1沿用现有null约定。
- 单报原运行成功率、这轮离线校验的通过/拒绝/不适用/异常、耗时；禁止混成新端到端处理成功率。新增API调用/费用应为0。

既有冻结安全v1结果（本阶段未重算）：

| 集合 | 样本/标签1 | FILTER/KEEP/UNKNOWN | 真实缺陷操作保留率 | 误删率 | 误报过滤率 |
|---|---:|---|---:|---:|---:|
| 调试审计集 | 10/3 | 0/0/10 | 100% | 0% | 0% |
| 固定回归留出 | 20/8 | 0/15/5 | 100% | 0% | 0% |
| 合计 | 30/11 | 0/15/15 | 100% | 0% | 0% |

这是“没有自动过滤”的安全起点，不证明模型判断可靠。旧全量64/241过滤、2/37真实缺陷标签误删的基线继续保留，不能把30条离线指标写成全量修复效果。

## 验收、回退与停机

接受：通用合成测试能检出错误极性并接受正确极性；A01错误被定位；A10仍为UNKNOWN；A01/A02不被误删；A04不因身份问题被错误过滤；所有原失败保留在结果中；UNKNOWN不计成功过滤；门槛和固定样本不变。

任一真实缺陷标签出现FILTER、任何证据不完整告警自动过滤、调用模型/联网执行、留出集变动或同时修改多个主要问题，立即终止该候选并保存失败记录，保留原安全v1。新增公式/源码不能复用旧哈希下的复核。所有输出放新run目录；不以无新增误删代替极性检查本身的有效性验证。

本文件不包含已执行的修复成绩或测试通过声明。
'''
    put('experiment_plan.md', experiment_text)

    restore_root = SEARCH / 'restore_branch'
    report = f'''# A10 原始构建证据限时查找与通用算法修复准备

结论：**未找到新的A10原始扫描构建证据，继续UNKNOWN / KEEP**。新找到官方仓库 `reproducibility-restore` 分支及论文v1源码包，增加了可追溯公开材料，但没有补齐原CodeQL数据库、完整SARIF路径、扫描checkout与实际构建/预处理身份。查找已停止，后续优先处理通用条件极性与约束合并问题，不为A10放宽门槛。

本阶段只读查找、代码审查和计划编制；没有实施算法修复，没有模型调用、求解器重放、单元测试重跑或全量实验。所有旧结果与留出集保留；3103个既有文件在开始固定，结束完整性校验另存。费用账本仍为1187次调用、估算上界4.491330元，本阶段新增0。

## 1. 限时查找范围与停止记录

查找窗口：`{conclusion['search_started_at']}` 至 `{conclusion['search_ended_at']}`，实际 **{conclusion['elapsed_seconds']:.1f}秒，约6分35秒**，上限900秒。有限来源清单完成后提前结束，未反复访问同一失败来源；查找结束后只进行代码审查与文档整理。见 {link(SEARCH / 'search_conclusion.json')}。

| 来源 | 实际完成的检查 | 结果与证据边界 |
|---|---|---|
| 本地官方Git历史 | 19个可达提交、155个历史路径；逐提交文件树和安全的非模型文本关键字检查 | 无CodeQL DB/SARIF/编译配置/tdls.i文件；README和代码路径文字不能证明扫描构建 |
| 当前远端main | `37a1fdc99d59a8af176ae8c93fa4bf0adbeed997`，完整非截断树114个文件 | 仍为PATHAGENT README；没有原构建材料 |
| 远端分支 | 公开返回main和reproducibility-restore；后者21提交中新增的两个提交及其完整文件树均查 | 新增恢复实现和候选缓存，未发现原构建数据库或预处理证据 |
| 标签与发布 | GitHub tags/releases列表 | 均为空，没有可下载的release资产；仅限本次公开返回，不能推断私有或外部材料不存在 |
| 官方benchmark/现有项目文件 | 文件树、已存告警和A10历史上下文身份对比；本地项目文件名清点 | 只有已有告警/片段/缓存；发现的ZIP是本项目先前冻结备份，不是作者数据库 |
| 论文v1 HTML与源码包 | 缓存HTML外链；新取得固定v1源码包并列49成员，检查TeX/Bib相关文本与三个appendix | 有数据集/基线/提示词附录和静态分析查询名称，无实际CodeQL构建命令、配置或A10路径 |

公开只读GET共17次，均为HTTP200；来源是GitHub源码/元数据与arXiv，未连接模型服务。未下载整个内核、创建新CodeQL数据库、生成新构建配置或预处理文件。仓库工作区未fetch/checkout或切换分支。

查找不是全互联网穷举，没有作者私有磁盘或未公开扫描数据库的访问权；未找到不等于作者从未保留。本阶段没有向作者或任何人发送消息。完整下载URL、路径、行范围和SHA-256见 {link(HERE / 'evidence_index.md')} / {link(HERE / 'evidence_index.json')}，原响应与同名metadata保留在search/。

## 2. 新公开分支的对应关系

分支 `reproducibility-restore`，头提交 `7fd55480e756db90080ac364105ed835ed30b0f2`，上一新增提交 `b209d667204750e8f3585abc259d9cff00b66597`，日期2026-10-28。远端读取不改变本地采用的旧提交 `4efb4b9bf7e845e180451b43ba29a25e3edaa0e3`。

新增README给出安装/运行入口，明确 `dereferences.json` 缺失，并说明允许空索引可能直接返回True。新配置 {link(restore_root / 'llm4pfa/configs/linux-codeql-npd.json')} 指定source_version=6.9.6、可配置source_root，且将context/constraints标为 **identity-aligned-candidate**，tools为interface-adapter。它描述恢复工程的输入契约，不能证明2025论文实验使用了这些新文件或某次扫描的实际checkout/config。

A10对应关系已具体核对：

- 原benchmark零基行65、index95；新context零基行65、index96。
- 变量sta、完整第一层函数和Sink文本与原告警一致，不能只靠index对齐。
- 新context的这条记录与历史 `29ca96e0d5f860d1f4ce07cd3e54e5e25732d1a1:baseline/NPD-codeql-linux.json` 第95个零基行、index96 **整个记录相同**。因此它恢复了已有历史候选，不是新发现的原扫描数据库。
- `source`内容仅为 `for_each_sta_info(local, addr, sta, tmp)` 与 `sta = sta_info_get(sdata, peer)` 两条代码提示，无绝对Source位置、codeFlow或构建ID。
- 新constraints第65行仍记录 `variable_assignments.text="static void"`；新conditions.py也仍将未提供赋值的索引默认为0。

机器可读映射见 {link(SEARCH / 'a10_restore_correspondence.json')}，原记录副本与下载文件SHA均已保存。index差异作为来源/对齐风险记录，不擅自改正标签或认定候选函数错误。

## 3. 论文补充材料带来的信息

固定URL `https://arxiv.org/src/2506.10322v1` 实际返回gzip源码包，8,539,773字节，SHA-256 **`c02abf4e361ac111cae8f003ea353e2ca1427a75b80720ecdea7bf45f3151457`**。保留原包和49成员清单；只从包内读取指定文本成员，没有执行内容或解压整个工程。

`appendix/dataset.tex`、`appendix/baselines.tex`、`appendix/prompt.tex`提供论文统计/基线设置/提示词。`table/command.tex:10`列NPD的CodeQL `MissingNullTest.ql`，是查询名称，不是数据库创建或编译命令；`ref.bib:2552–2553`指向Linux v6.9.6浏览页面，只能佐证版本名称。没有在所查材料中发现把A10绑定到某个CodeQL库、源码SHA、架构、.config或编译flags的记录。

## 4. 仍然缺失的原始构建证据

1. 原始CodeQL数据库元数据/完整SARIF规则与Source→Sink codeFlow。
2. 原扫描源码checkout commit或源码归档身份；已匹配的v6.9.6函数不能代表整个原构建的提交证明。
3. 原架构、`.config`、编译器版本、include/宏定义/编译参数、compile_commands。
4. 原生成头文件、实际预处理后的tdls翻译单元及与该告警的绑定。

截至本次有限查找，这些缺口无法通过新分支或论文附录补齐。不得用新生成数据库、默认构建或当前源码倒填。维持前阶段A10报告的UNKNOWN/KEEP、未获人工复核批准和filter_evidence_complete=false。本轮不会继续追查该样本；若以后取得真正新材料，再作为独立补充。

## 5. 现有实现中最值得优先修复的内容

完整逐项位置、案例、最小方案和验证方法见 {link(HERE / 'repair_plan.md')}；结构化清单见 {link(HERE / 'priority_repairs.json')}，只读代码摘录和SHA见 {link(HERE / 'code_review_evidence.md')}。

优先级按真实缺陷风险与证据强弱排序：

1. **P0-1 条件极性与合并一致性**：A01的同一分支条件被译成互相冲突的两条断言，再因UNSAT过滤标签1告警。这是已确认的直接错误来源；不是Z3算错。
2. **P0-2 目标与控制范围**：A03重复Sink选最后文本、空格缩进丢条件已有证据；A02局部分配guard未证明覆盖所有路径，不能据此全局过滤。
3. **P0-3 符号身份/类型/赋值版本**：A04把同一指针拆成独立Int/BitVec；A02多次赋值没有版本。先核对并拒绝不一致，再逐步建立有来源的关系。
4. **P1 赋值缺失状态、跨帧状态、逐断言来源**：static void根因明确，但只改占位不会改变当前未消费该字段的推理。跨函数参数名正确不代表状态已传递；SMT重放也不代表源码语义已验证。

没有把A01/A02的原标签冒称独立重标注结论；A02还存在数据/路径不确定性。所有建议是语法、作用域、状态与证据的通用逻辑，不以样本ID或标签设置例外。

## 6. 下一次最小实验

建议 **E01：简单标量条件的极性一致性核对**，只处理R01。使用不含ID特判的合成条件与缓存中的A01/A10响应，定位错误极性并保留正确局部翻译；未知宏/类型/复杂流输出UNKNOWN。保留原SMT和模型输出，不自动删除冲突断言或把诊断公式当新端到端预测。

先用原10条审计集调试，冻结代码后检查原20条固定回归集；manifest SHA **`{before['holdout_sha256']}`**保持不变。分别报告FILTER/KEEP/UNKNOWN、真实缺陷操作保留率和误删率、误报过滤率、UNKNOWN率、证据完整性、时间和0模型费用。计划的分母、缓存适用性、单因素控制与停止条件见 {link(HERE / 'experiment_plan.md')} / {link(HERE / 'experiment_plan.json')}。

原安全v1这30条为0 FILTER、15 KEEP、15 UNKNOWN；标签1操作保留11/11、误删0/11、误报过滤0/19。这只是引用既有结果，非本阶段新实验；零过滤不证明算法判断正确。没有新完整复核证据时，E01也可能保持零FILTER，不能为了抬高过滤率绕开安全门槛。

本阶段至此停止：未修改核心、安全门槛、提示词、样本集或原始结果，未执行E01，也未启动全量实验。
'''
    put('build_evidence_and_repair_report.md', report)
    put('stage_status.json', {
        'completed_at': datetime.now(timezone.utc).isoformat(),
        'search_completed': True, 'code_review_and_plan_completed': True,
        'new_original_a10_build_evidence_found': False,
        'new_public_restoration_branch_found': True,
        'a10_verdict': 'UNKNOWN', 'a10_action': 'KEEP',
        'filter_evidence_complete': False, 'core_changes': [], 'safety_rule_changes': [],
        'prompt_changes': [], 'experiment_executed': False, 'solver_checks': 0,
        'new_model_calls': 0, 'new_api_cost_cny': 0,
        'next_proposed_experiment': 'E01_predicate_polarity_consistency',
        'stopped': True,
    })
    print('Reports and single-issue experiment plan saved; no implementation or experiment executed.')


if __name__ == '__main__':
    main()
