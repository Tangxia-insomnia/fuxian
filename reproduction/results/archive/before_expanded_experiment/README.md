# LLM4PFA 简单复现：补全实现

已在保留作者原代码的前提下补写缺失支撑，并真实运行模型和 SMT。当前 smoke 5/5、pilot 16/20；最终报告见 results/final_report.md。此为补全版小样本实验，不是作者原版或完整论文复现。

## 运行

Windows / PowerShell，在本目录运行：

```powershell
.\.venv\Scripts\python.exe -B -m unittest completion.test_completion -v
.\.venv\Scripts\python.exe -B scripts/run_completed.py --phase preflight
.\.venv\Scripts\python.exe -B scripts/run_completed.py --phase all
.\.venv\Scripts\python.exe -B scripts/report_completed.py
.\.venv\Scripts\python.exe -B scripts/validate_completed.py
```

`all` 先完成固定 smoke，达到门槛才运行 20 条 pilot；已有结果会复用，不重复扣费。只有在明确修复实现错误后，使用 `--retry-failed` 归档失败尝试并重跑；原始记录不会删除。
新机器先按 environment/requirements-reproduction.txt 建立 Python 环境，克隆 upstream 并固定 4efb4b9bf7e845e180451b43ba29a25e3edaa0e3；未升级系统环境。作者缺少版本固定，本次版本选择见环境日志。

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r environment/requirements-reproduction.txt
git clone https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis.git upstream
git -C upstream checkout --detach 4efb4b9bf7e845e180451b43ba29a25e3edaa0e3
```

上面的安装/克隆步骤只适用于新目录；本机环境和 upstream 已就绪。模型密钥写入本地 .env 的 DEEPSEEK_APIkey 变量，配置后按前述运行命令执行。

## 凭据与费用

模型 deepseek-flash，API https://api.deepseek.com/，本地 .env 变量 DEEPSEEK_APIkey；禁止把密钥发聊天、日志或提交 Git。.gitignore 已忽略 .env；客户端不使用作者内嵌凭据。
预算累计上限 10 元，目前所有尝试调用 191 次，保守费用上界 0.905162 元。配置见 configs/completed_experiment.json，ledger 持续记录，不因重跑清零；这不是账户账单。

## 记录与实现边界

- 上游：upstream/，原始代码未修改；复用提示词及主分析函数。
- 补全代码：completion/；逐项说明 logs/stage_06_completion.md，差异 patches/completed_pipeline.diff。
- 当前数据：官方 CodeQL/Linux NPD；上下文来自官方基准和历史 baseline，歧义/缺失保留阻塞。
- 样本清单：configs/*manifest.json；逐样本 CSV/JSON：results/processed/completed_*。
- 原始模型调用、usage、SMT2、耗时及失败：results/raw/completed/。
- 当前指标：results/metrics/completed_metrics.json；报告：results/final_report.md。
- 阶段日志：logs/stage_01 至 stage_06；补全前结论快照：results/archive/before_authorized_completion/。
- 旧 smoke_results 和 reproduction_metrics 是先前离线组件阶段数据；当前真实实验使用 completed_ 前缀。scripts/finalize_records.py 只用于旧阶段，不要用它覆盖当前报告。

仅支持有界的 NPD 上下文，未实现任意工程的完整跨过程分析、宏展开或函数指针解析；不能把运行成功当作约束语义正确，也不能把当前模型结果直接等同论文 GPT-4o-mini 效果。未运行全基准或基线。
