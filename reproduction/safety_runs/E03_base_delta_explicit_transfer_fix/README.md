# E03 离线验证材料

本目录对应 `E03_base_delta_explicit_transfer_fix`。主报告：[E03_report.md](E03_report.md)。本轮只修复补全版正常 U06→U10 的 B/Δ 传递，不运行模型、Z3、Harness 或完整审计/回归集。

## 实现与依赖

- `../../completion/constraint_bundle.py`：确定性拼接、原文来源和哈希、E02 结构准入。
- `../../completion/engine.py`：正常路径精确接入、U10/修复输出后置检查、排他存档。
- `../../completion/test_constraint_bundle.py`：合成与接入检查。
- 只读依赖 `../E02_base_constraint_preservation_static/checker.py`，SHA-256 固定为 `5a0d6532e73af8485113541fd3982f491ddeef0b6b44c7f856ad61d649a1916a`。
- 使用原有 `reproduction/.venv/Scripts/python.exe`，不安装依赖。现有 engine 的导入依赖 lizard；本机 Anaconda 环境缺少该包，已切换现有 venv。

## 实际运行命令

以下命令的工作目录是 `reproduction/`，使用 `-B` 避免写入历史目录的字节码缓存：

```powershell
.\.venv\Scripts\python.exe -B -m completion.test_constraint_bundle
.\.venv\Scripts\python.exe -B safety_runs/E03_base_delta_explicit_transfer_fix/replay_cached_cases.py
```

以上输出已保存，采用排他创建，再执行同名命令会拒绝覆盖。只重跑合成/接入测试时指定新的、尚不存在的文件名：

```powershell
.\.venv\Scripts\python.exe -B -m completion.test_constraint_bundle synthetic_test_results_rerun_01.json
```

缓存重放脚本记录了本轮确切输入和算法，默认输出固定文件名。请在独立副本的新输出目录中复核，不能在原目录删除或覆盖已有文件。直接阅读 `merge_audit.json`、`postcondition_audit.json` 和来源副本即可逐项核验。本轮没有运行旧 `test_completion.py`，因为它会运行 Z3 并覆盖旧快照。

## 文件索引

- `synthetic_cases/T01.json` 至 `T23.json`：全部合成输入和预期。
- `synthetic_test_results.json`：23 项场景和 18 项接入检查完整结果。
- `merge_audit.json`：旧输入、新 bundle、离线观察参数及来源。
- `postcondition_audit.json`：旧 U10 输出的结构检查、A04 旧 U01/U09 观察。
- `cached_replay_results.json`：仅 A04、A01 的验收摘要。
- `evidence/`：经 E02 清单和本轮基线双重校验的历史调用副本。
- `engine_traces/`：适配器绑定方法生成的逐事件记录，不是新模型调用日志。
- `test_runs/`：成功的渲染/AST与模拟对象检查材料。
- `development_01_*`、`rendered_candidate/`、`synthetic_engine_traces/`：保留的开发阶段输出；局部失败 JSON 以 `.partial.json.txt` 留存，不冒充完整 JSON。
- `baseline_state.json`、`preservation_check.json`、`hashes.json`、`patch.diff`、`metrics.json`、`execution_log.md`：基线、保护、哈希、实际差异、统计及执行记录。

结构 PASS 只表示受限成员保留；它不能代替 E01、源码语义核验或安全 v1。本目录不输出告警安全裁决。
