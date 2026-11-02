# 冻结前开发记录

`synthetic_runs/development_01/`：65 场景、131 项断言符合预期。随后静态复核发现 adapter.counts 对生成器执行多次 sum，后续分类被耗尽，导致统计遗漏。该次输出原样保留，**不作为最终统计或冻结依据**。逐项 expected/actual 未受此统计缺陷影响。

冻结前修复为先 materialize 输入，增加四分类计数和每场景指标总数一致性检查。后续最终候选必须重新生成完整合成证据；固定20尚未开始。开发轮次不累加为最终检查数。

`synthetic_runs/final_candidate_01/` 仍处冻结前。审查发现参数映射已验证但 callee 因不支持控制流未创建入口版本时，argument_entry 指标不应 PASS；已分成 argument_mapping 与 argument_entry，完整调用一直保持 UNKNOWN。另补入不同 caller 场景的两次分析至关系统计。此目录保留为开发证据，最终冻结使用后续 final_candidate_02，不累加断言数。
