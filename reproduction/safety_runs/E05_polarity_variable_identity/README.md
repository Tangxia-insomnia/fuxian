# E05 离线约束语义诊断

先读 [E05_report.md](E05_report.md) 和 [metrics.json](metrics.json)。实现未接入生产算法，没有告警真假裁决能力。

使用现有 Python 3.11 环境，仅标准库；不安装依赖。模块只读加载哈希固定的原 E01/E02/E03 静态代码，不导入模型/solver，不执行模型生成文本。

在工作区根目录，已实际执行：

```powershell
& reproduction/.venv/Scripts/python.exe -B reproduction/safety_runs/E05_polarity_variable_identity/test_semantics.py
& reproduction/.venv/Scripts/python.exe -B reproduction/safety_runs/E05_polarity_variable_identity/replay_v2.py historical
& reproduction/.venv/Scripts/python.exe -B reproduction/safety_runs/E05_polarity_variable_identity/baseline_local_check.py synthetic
& reproduction/.venv/Scripts/python.exe -B reproduction/safety_runs/E05_polarity_variable_identity/baseline_local_check.py audit_10
& reproduction/.venv/Scripts/python.exe -B reproduction/safety_runs/E05_polarity_variable_identity/replay_v2.py fixed20
& reproduction/.venv/Scripts/python.exe -B reproduction/safety_runs/E05_polarity_variable_identity/baseline_local_check.py fixed_20
```

历史结果采用独占创建，命令不可在同一结果目录原地重跑。`replay.py` 为保留的失败入口，不是正式入口。冻结与适配器失败经过见主报告。固定 20 条仅运行一轮，属于已接触过的固定回归集。

可重核通用合成测试并指定一个从未使用过的后缀，例如 `test_semantics.py _local_recheck_001`；这只生成新的合成结果文件，不调用模型或访问固定 20 条。不得覆盖现有输出，也不能将重核称为新的盲测。

主要 API：

- `Source(code, function, reference, expected_sha=...)` 读取源码证据。
- `check_polarity(...)` 返回局部一致性/拒绝/证据不足诊断。
- `check_mappings(...)` 验证调用方提供的显式源码身份与 SMT symbol/sort 对应；不猜关系。
- `member_collapse_diagnostics(...)` 静态读取原模型脚本，报告支持的成员→指针形状破坏。

PASS 仅指受限局部检查符合证据；REJECT 是约束候选拒绝；UNKNOWN 是诊断不确定，均不是 FILTER/KEEP/UNKNOWN 安全裁决。结构 B+Δ 保留、局部源码语义、完整程序状态及安全裁决必须分开。

`polarity_tests.json`、`variable_identity_tests.json` 含完整合成输入/输出；`historical_replay.json` 含原始证据路径与哈希，引用已有历史文件而不重复生成；`fixed_holdout_results.json` 保留全部 20 条；`retained_E01_*.json` 单独记录原有局部检查，不包含安全层/求解重放。
