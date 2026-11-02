# E06-R01-RF：空上下文运行器修复

完整说明：[E06_R01_RF_report.md](E06_R01_RF_report.md)。本目录是新 R01 候选，原 `E06_R01_direct_call_argument_mapping/` 整体保留，原 mapper/config 未复制或修改。

运行器仅在验证原导出器、历史绑定、原 blocked_context 错误和缺 context.json 后接受显式 null，输出缺证据 UNKNOWN。缺字段、空对象、错误类型和无来源 null 是数据错误；保存 traceback 后停止，不伪装成 UNKNOWN/N/A。正常单帧/多帧规则不变。

本次已执行（从 `reproduction/`）：

```powershell
& .\.venv\Scripts\python.exe -B .\safety_runs\E06_R01_runner_fix\test_runner.py
& .\.venv\Scripts\python.exe -B .\safety_runs\E06_R01_direct_call_argument_mapping\test_mapper.py --output .\safety_runs\E06_R01_runner_fix\core_synthetic_recheck
& .\.venv\Scripts\python.exe -B .\safety_runs\E06_R01_runner_fix\run_regression.py historical
# 之后冻结 candidate_manifest.json，再从头仅运行一次：
& .\.venv\Scripts\python.exe -B .\safety_runs\E06_R01_runner_fix\run_regression.py fixed20
```

运行器测试 20/20，原核心合成复查 41/41；历史三例 UNKNOWN；固定 20 条完整运行一次，PASS 0 / REJECT 0 / UNKNOWN 5 / N/A 15。输出文件独占创建，已有目录不可覆盖，不要原地重跑。固定集已经多次接触，不是盲测。

`runner_patch.diff` 对照旧运行器；`runner_tests.json` 保存原始测试输入、期望/实际状态和错误 traceback；`candidate_manifest.json` 是固定集运行前冻结；`fixed_20_results.json` 是新运行的完整 20 条，未拼接第一次结果。第一次不完整运行与第二次完整运行的对照在 `comparison.json`。

本轮没有模型、Harness、Z3、生成代码执行、告警裁决或 R02。PASS 仅是局部映射关系诊断，N/A 仅是保存链中无请求跨帧对；缺上下文不会被算作 N/A 或成功。
