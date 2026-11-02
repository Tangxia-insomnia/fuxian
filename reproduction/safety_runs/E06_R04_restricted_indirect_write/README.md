# E06-R04 独立单级指针写入证据

R01/R02/R03 只读复用；仅本目录新增。主接口为 indirect_write.analyze / verify_proposal，范围及记录合同见 R04_design_and_scope.md、mapping_contract.md，最终报告 E06_R04_report.md。

最终合成证据在 synthetic_runs/final_candidate_01/；旧开发输出和失败记录原样保存，不累加统计。原回归输出在 r01_core_recheck、r02_core_recheck、r03_core_recheck、r03_boundary_recheck，原历史目录不写入。

使用既有 reproduction/.venv/Scripts/python.exe -B。冻结后 run_r04.py fixed20 只运行一次；fixed_20目录为不可重试标记。任何异常或候选问题保存并停止，不改冻结代码重新验收。audit_evidence.py、r04_protection.py、finalize_results.py 只读取已保存证据/哈希，不作为重跑固定20入口。

真实片段缺原始构建/TU/类型/效果时保持UNKNOWN；取址文本和局部写入PASS都不构成FILTER授权。本轮无模型、Harness、Z3、SMT、安全裁决或R05接入。
