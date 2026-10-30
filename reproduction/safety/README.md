# 真实缺陷优先的离线最终判定层

本轮仅新增最终判定与指标，不改变作者算法、提示词、原始标签、模型配置或基线结果。
正式说明和结果在 `../safety_runs/20261029_v1/safety_policy_report.md`。

- `policy.py`：独立读取已保存的 SMT2 并重放。FILTER 还必须通过六项检查，以及绑定源码、查询和逐条断言的独立复核记录。缺失、冲突或格式异常均不得自动过滤。
- `metrics.py`：分别统计 FILTER/KEEP/UNKNOWN；UNKNOWN 的实际动作是 KEEP，绝不计为过滤成功；将操作保留率与明确 KEEP 比例分开。
- `replay.py`：只回放固定的十条审计样本与二十条回归留出样本，保存新结果，拒绝覆盖。
- `test_policy.py`：原始日志回归、缺证据/异常/篡改/标签隔离和指标检查；正向过滤使用完全可见的合成空指针保护程序，不计为基准实验。

在 reproduction/ 执行：

```powershell
.\.venv\Scripts\python.exe -B -m unittest safety.test_policy -v
.\.venv\Scripts\python.exe -B -m safety.replay
```

第二个命令已经执行完成，再次执行会拒绝覆盖，应读取保存的结果。不能删除旧结果冒充新实验。

**当前生效范围**：只在新离线入口 `safety.replay` 生效。旧 `scripts/run_completed.py` / `run_expanded.py` 保留为冻结的基线，不提供这套保护，不能将其旧预测直接当作新的安全决策。
下次获得授权运行新实验时，应让最终发布结果显式经过 `policy.decide`；本轮没有启动任何在线入口。

KEEP 表示继续保留告警，并不证明存在真实缺陷；UNKNOWN 表示证据不足/异常，继续保留并记录原因。
安全层不读取评估标签。日志中的 SAT/UNSAT 只验证所提交公式；复核文件的哈希、来源覆盖和格式校验也不能证明任意 C 程序语义。
本轮真实日志没有足够的完整复核记录，所有原 FILTER 候选降级为 UNKNOWN；没有伪造人工复核来恢复过滤率。
