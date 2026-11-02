# E06-R03：独立返回值证据层

本目录由项目补全，基于冻结 R01/R02 的只读接口。入口 `return_transfer.analyze`；证据结构、边界和指标见 `mapping_contract.md`、`R03_design_and_scope.md` 和最终 `E06_R03_report.md`。

合成输入在 `synthetic_fixtures/`，最终测试证据位于 `synthetic_runs/final_candidate_02/`；之前开发输出原样保留，不累加统计。原 R01/R02 回归输出只写本目录。OpenSSL/A01/A04/E04-ND 历史输入从已保护的原始保存源码读取，旧传播结果不作本轮结果。

运行必须使用现有 `reproduction/.venv/Scripts/python.exe -B`。测试和历史检查在冻结前完成。`candidate_manifest.json` 形成后 `run_r03.py fixed20` 只准执行一次；已有 `fixed_20/` 即禁止重跑。失败应保存记录并停止，不修补同一冻结候选。

`audit_evidence.py`、`protection.py`、`finalize_results.py` 只检查已保存记录或哈希，不能作为重新分析固定20的入口。发布仅本新目录。所有 PASS 都是局部证据状态，无 FILTER 权限；不进入 R04/R05。
