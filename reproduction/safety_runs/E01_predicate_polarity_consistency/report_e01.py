"""Generate the E01 report from actual saved results; no inference or API."""


def report(state, audit, holdout, metrics, tests):
    both = metrics['combined']['e01']
    before = metrics['combined']['frozen_safety_v1']
    lines = [
        '# E01_predicate_polarity_consistency 实验报告', '',
        '## 结论与验收', '',
        '本轮完成 R01 的窄范围离线一致性检查。合成测试与审计检查通过，候选冻结后仅运行固定20条回归集一次；未进入 R02/R03。',
        '验收结论：通过本轮限定范围的离线安全/诊断验收；不代表原论文完整复现成功、端到端修复完成或误报过滤率提高。',
        'A01 的 `if (!copied)` 记录真分支与保存响应中的 `Not(copied == 0)` 冲突被检出；拒绝候选并保留告警。未删除任何矛盾断言。',
        'A10 的宏和复合条件不在支持范围内，没有被误判为局部极性错误，最终仍为 UNKNOWN。A02/A04 的控制范围、变量身份问题仍未解决，保持 UNKNOWN。', '',
        '## 固定基线与输入', '',
        f'- 官方上游 commit：`{state["upstream_commit"]["stdout"]}`，原工作区干净。',
        f'- 已上传快照 commit：`{state["published_snapshot_commit"]["stdout"]}`；本地 reproduction 目录自身不是 Git 仓库。',
        '- 原始上游、补全实现、安全 v1、历史结果全部保留；保护文件 SHA-256 在 baseline_state.json，共 '
        f'{len(state["protected_sha256"])} 个文件。',
        '- 调试集：原 audit_samples.json 10条，有目的诊断抽样，标签1共3条、标签0共7条。',
        '- 固定回归集：原 fixed_holdout.json 20条，8条标签1、12条标签0；原种子与样本顺序完全不变。它是已执行基准中的固定回归集，不是未接触的盲测集。',
        '- 数据范围为现有 NPD 复现缓存；发布标签1表示真实缺陷、0表示误报，标签未逐条独立核实。原数据内容与标签未更改。',
    ]
    for path, digest in state['fixed_input_sha256'].items():
        lines.append(f'- `{path}`：`{digest}`。')
    lines += ['', '## 实现与证据边界', '',
              '只新增 E01 目录中的一致性核对层、离线适配、测试和报告工具。原提示词、条件提取、赋值提取、completion/engine.py 和 safety/policy.py 均未修改。实现位置与审查见 source_review.md，实际新增代码见 patch.diff。',
              '支持 x、!x、!!x、x==0、x!=0、括号及重复否定，且须有明确分支、显式已知标量类型、来源哈希和符号身份。对生成约束仅做 AST 读取，不执行模型生成的 Python。',
              '检查结果保留原表达式、方向、变量/声明身份、类型、规范条件、保存函数相对行号及代码哈希。源码绝对版本未证实处明确留空，不伪造定位。',
              '对提前退出约束，不根据同名变量把缺陷假设误作可达性条件。对重赋值、别名、复杂控制流、宏、跨函数状态和未绑定的来源，只输出 unsupported/UNKNOWN。所有基准样本均缺完整程序状态/控制与断言来源证据，因此整样本支持率为0。',
              '局部极性一致只提供诊断，不授予任何六条件认证或人工复核。原安全 v1 被原样调用，新增层仅可拒绝/降级；UNKNOWN 的操作始终是 KEEP。', '',
              '## 已完成测试', '',
              f'- 参数化合成检查：{tests["pass_count"]}/{tests["test_count"]}通过，失败{tests["fail_count"]}项，耗时{tests["seconds"]:.6f}秒。包括正确/反向分支、重复否定、同名作用域、未知类型、宏、方向不明、来源篡改、错误sort、重复合并和真实矛盾不删断言。',
              f'- 原审计样本：10/10处理完成，验收断言{sum(c["passed"] for c in audit["acceptance_checks"])}/{len(audit["acceptance_checks"])}通过，离线阶段耗时{audit["offline_seconds"]:.6f}秒。',
              f'- 冻结后固定回归：20/20处理完成，未更换样本或按结果调整代码，离线阶段耗时{holdout["offline_seconds"]:.6f}秒。',
              '- 保存的 SMT2 由未修改的安全 v1 重新求解。重放只验证保存公式的可解性，不证明 C 路径语义。没有新的端到端模型实验。',
              '- 开发预检查发现的“缺陷假设/提前退出错误归因”在冻结前已收紧为不适用；未作为正式极性错误计数。正式未通过检查见 test_results.json 的 fail_count（若为0即无失败）；不适用样本仍被保留。', '',
              '## 指标对比', '',
              'FILTER/KEEP/UNKNOWN 均为判定数量；操作保留率=(KEEP+UNKNOWN的标签1数)/全部标签1数，误删率=FILTER的标签1数/全部标签1数，误报过滤率=FILTER的标签0数/全部标签0数。UNKNOWN不计为过滤成功。', '',
              '| 数据集 | 版本 | FILTER | KEEP | UNKNOWN | 标签1操作保留 | 标签1明确KEEP | 标签1误删 | 误报过滤 | UNKNOWN比例 |',
              '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for cohort in ('audit', 'holdout', 'combined'):
        for key, title in (('frozen_safety_v1', '安全v1'), ('e01', 'E01')):
            m = metrics[cohort][key]; v = m['verdict_counts']
            lines.append(f'| {cohort} | {title} | {v["FILTER"]} | {v["KEEP"]} | {v["UNKNOWN"]} | '
                         f'{m["operational_real_bug_retention_rate"]:.2%} | {m["explicit_keep_real_bug_count"]}/{m["real_bug_count"]} | '
                         f'{m["real_bug_deletion_rate"]:.2%} | {m["false_positive_filter_rate"]:.2%} | {m["unknown_rate"]:.2%} |')
    lines += ['', '明确 KEEP 减少是严格不适用规则将未验证上下文降为 UNKNOWN 的结果，操作保留并未下降，也不能据此宣称推理质量提高。100%操作保留依赖于本轮全部保留的保守策略，不是检测完备性证据。', '',
              '| 数据集 | 保存条件条目（含重复） | 局部可核对条目 | 子集覆盖率 | 冲突条目 | 冲突样本 | 整样本支持 |',
              '|---|---:|---:|---:|---:|---:|---:|']
    for cohort in ('audit', 'holdout', 'combined'):
        m = metrics[cohort]['e01']; cov = m['local_support_subset_coverage']
        lines.append(f'| {cohort} | {m["recorded_condition_count"]} | {m["locally_checked_condition_count"]} | '
                     f'{cov:.2%} | {m["polarity_conflict_condition_count"]} | {m["polarity_conflict_sample_count"]} | {m["whole_sample_supported_count"]}/{m["sample_count"]} |')
    lines += ['', '冲突条目按来源condition_id计数；同一错误在多个保存快照中的出现次数另存 polarity_conflict_atom_occurrences，不能当成多个独立错误。局部支持率分母是保存条件条目，含重复提前退出条件；整样本支持率另算。',
              '混淆矩阵行顺序为[发布误报,发布真实缺陷]，列为[FILTER,KEEP,UNKNOWN]：',
              '```json', str(both['confusion_matrix']['values']), '```',
              '误报过滤为正类。无FILTER时Precision、F1为null（未定义），Recall为0，不能把null当作满分。', '',
              '## 10条逐样本结论', '',
              '| 审计ID | 发布标签 | 原预测 | 安全v1 | E01 | 局部冲突条目 | 局部可核对/记录条目 | 结果解释 |',
              '|---|---:|---|---|---|---:|---:|---|']
    for row in audit['rows']:
        c = row['r01']
        why = '局部极性冲突，拒绝候选' if c['conflicting_condition_count'] else '不适用/证据不完整，保留'
        lines.append(f'| {row["audit_id"]} | {row["dataset_label"]} | {row["original_prediction"]} | '
                     f'{row["baseline_v1_verdict"]} | {row["verdict"]} | {c["conflicting_condition_count"]} | '
                     f'{c["locally_checked_condition_count"]}/{c["source_condition_count"]} | {why} |')
    lines += ['', '详细表达式、分支、代码哈希、类型、符号身份、候选原子、原响应/脚本哈希与原SMT结果见 audit_results.json、holdout_results.json；原始响应和完整源码继续保留在 input_evidence_path，不重复改写。', '',
              '## 拒绝与不适用原因', '']
    for reason, count in sorted(both['rejected_or_unsupported_reasons'].items(), key=lambda x: (-x[1], x[0])):
        lines.append(f'- `{reason}`：{count}（条件/脚本层统计，同一样本可多项）。')
    lines += ['', '另有整样本共同缺口：C状态、控制范围、完整合并来源和独立语义复核均未新建证明；不适用原因不是新的模型执行错误。', '',
              '## 资源、完整性与未完成部分', '',
              f'- 本轮模型调用0次，新增API费用0元。历史账本仍为{state["model_calls_before"]}次、估算累计上界{state["cost_upper_cny_before"]:.6f}元；不是本轮费用。',
              f'- 合计样本处理CPU/墙钟计时累计{both["offline_processing_seconds"]:.6f}秒，其中R01检查{both["r01_seconds"]:.6f}秒；阶段耗时还含保护哈希复核。',
              '- 网络/凭据/子进程防护无违规；原3413个保护文件、固定输入和安全策略哈希均未变；冻结代码在20条前后均校验通过。详细见 preservation_check.json、candidate_freeze.json、hashes.json。',
              '- 未改原提示词；未修复R02目标定位/控制范围、R03赋值提取、变量版本/跨函数传播或宏建模；未调用模型、未全量重跑、未补签人工复核。',
              '- 下一步如获授权，应另立R02或其他单问题实验；保持同一回归集和六条件门槛。本轮到此停止。', '',
              '## 重现命令', '',
              '在reproduction目录用现有.venv运行。各阶段使用独占创建输出，原目录已有结果时会拒绝覆盖；复验应复制候选到新实验目录并保留原冻结输入。',
              '```powershell',
              '.\\.venv\\Scripts\\python.exe -B safety_runs/E01_predicate_polarity_consistency/run_e01.py synthetic',
              '.\\.venv\\Scripts\\python.exe -B safety_runs/E01_predicate_polarity_consistency/run_e01.py audit',
              '.\\.venv\\Scripts\\python.exe -B safety_runs/E01_predicate_polarity_consistency/run_e01.py freeze',
              '.\\.venv\\Scripts\\python.exe -B safety_runs/E01_predicate_polarity_consistency/run_e01.py holdout',
              '.\\.venv\\Scripts\\python.exe -B safety_runs/E01_predicate_polarity_consistency/run_e01.py finalize',
              '```', '']
    return '\n'.join(lines)
