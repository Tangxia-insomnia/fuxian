# E04-ND 真实非空增量实验

主报告：[E04_ND_report.md](E04_ND_report.md)。这次只执行一个预先固定的真实样本，不运行 Z3，不执行生成代码，不产生告警裁决。

实际命令（工作目录 `reproduction/`）：

```powershell
.\.venv\Scripts\python.exe -B safety_runs/E04_nonempty_delta_validation/test_stop_hook.py
.\.venv\Scripts\python.exe -B safety_runs/E04_nonempty_delta_validation/run_nd.py
.\.venv\Scripts\python.exe -B safety_runs/E04_nonempty_delta_validation/analyze_outputs.py
.\.venv\Scripts\python.exe -B safety_runs/E04_nonempty_delta_validation/review_delta.py
```

全部结果已留存。发现 `live_start.json` 会停止真实运行，文件排他创建防止覆盖；不要删除已有结果原地重跑。新真实实验需要新授权和独立输出目录。

- `selected_sample.json`、`selected_source.c`、`sample_manifest.json`：固定样本、精确源码、来源及哈希。
- `historical_candidate_scan.json`、`source_candidate_preflight.json`、`historical_evidence/`：只读筛查材料；历史输出不充当新响应。
- `run_nd.py`、`driver_adaptation.diff`：独立 E04 驱动适配，不修改核心算法或 Prompt。
- `offline_tests.json`、`candidate_freeze.json`：真实执行前 10/10 停止测试及冻结哈希。
- `model_calls/1192.json` 至 `1195.json`：真实 U02/U05/U06/U10 请求、响应和用量。
- `transport/`：实际 PreparedRequest body 与 HTTP 响应，无鉴权头。
- `constraint_transfer/`：原始 B/Δ、新合并、实际 U10 输入/输出、前后置检查及逐断言来源/哈希。
- `acceptance.json`：非空结构验收与已定位语义缺陷分别报告。
- `execution_trace.json`、`events/`：真实轨迹及 Solver 前停止。
- `metrics.json`、`budget_ledger.*.json`、`preservation_check.json`、`hashes.json`：用量、费用口径、账本追加及历史保护。

本次有 3 条新增断言，实际 U10 保留契约 PASS。但其中一条错误使用 skb 指针代替 skb->len，不能把结构通过视作语义正确。费用 0.026430 元仅为配置保守费率下的真实 Token 用量上界，账户实扣未知。

只提交本目录；实际本机累计账本已追加本次四条，后续继续使用最新账本，不使用发布副本中的旧根账本回滚计费。
