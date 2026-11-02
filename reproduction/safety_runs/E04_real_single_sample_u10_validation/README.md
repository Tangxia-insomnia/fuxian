# E04 使用与材料索引

主报告：[E04_report.md](E04_report.md)。本目录保存一次真实 DeepSeek 目标帧实验；不是缓存重放，不是 Harness 或完整跨函数实验。

实际运行命令（工作目录 `reproduction/`）：

```powershell
.\.venv\Scripts\python.exe -B safety_runs/E04_real_single_sample_u10_validation/test_stop_hook.py
.\.venv\Scripts\python.exe -B safety_runs/E04_real_single_sample_u10_validation/run_e04.py
.\.venv\Scripts\python.exe -B safety_runs/E04_real_single_sample_u10_validation/analyze_outputs.py
```

这些命令的产物已经保存。运行器发现 `live_start.json` 会停止，其他写入使用排他创建，不能原地重跑或覆盖。新的真实实验需要新指令和新的独立目录，不要删除本次证据来重复调用。

- `experiment_config.json`、`source_config.snapshot.json`：实际配置和原配置快照，无密钥。
- `sample_manifest.json`、`extracted_conditions.json`：样本、函数体、行号、哈希及原提取结果。
- `baseline_state.json`、`candidate_freeze.json`：开始前保护清单及真实调用前的代码冻结。
- `offline_tests.json`、`offline_hook_traces/`：10 项离线停止检查。
- `model_calls/1188.json` 至 `1191.json`：U02、U05、U06、U10 的真实新请求与完整响应。
- `transport/`：服务检查及生成请求的实际 PreparedRequest body 和对应 HTTP 响应，不保存请求头。
- `constraint_transfer/`：原始 B/Δ、新合并脚本、实际 U10 消息、新响应、原门检查和对照证据。
- `events/`、`execution_trace.json`、`pipeline_stdout.txt`：逐步轨迹、停止原因和运行输出。
- `budget_ledger.before.json`、`budget_ledger.after.json`：原累计账本前后副本；没有清零或删除旧记录。
- `metrics.json`、`preservation_check.json`、`hashes.json`：用量、费用口径、不可变文件及产物完整性。

费用为原配置保守费率下的真实 Token 用量记账上界；没有账户实扣凭证。结构 PASS 不能替代源码语义、极性核验、安全 v1 或真实求解。本次没有执行模型生成 Python 或 Z3，也没有安全裁决。

本次只提交 E04 目录。实际本机累计账本已追加四条，after 快照随本目录保存；发布副本的旧根账本不在本次提交范围内，后续继续实验应使用最新累计账本。
