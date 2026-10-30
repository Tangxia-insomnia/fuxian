# LLM4PFA 补全版复现与扩展实验

已从 5 条 smoke、20 条 pilot 扩展到 8 组 NPD 全部 278 条有效标签记录。成功执行 224，阻塞 39，执行失败 15。这是补全版 NPD 扩展，非论文所有类型完整复现。

最终报告：results/final_report.md；逐样本：results/processed/expanded_all_npd.csv；指标：results/metrics/expanded_metrics.json。小样本旧报告在 results/archive/before_expanded_experiment/。

## 当前环境与运行

Windows PowerShell，在本目录执行；.venv 和固定 upstream 已就绪：

```powershell
.\.venv\Scripts\python.exe -B -m unittest completion.test_completion -v
.\.venv\Scripts\python.exe -B scripts/run_expanded.py --all-npd --preflight
.\.venv\Scripts\python.exe -B scripts/run_expanded.py --all-npd
.\.venv\Scripts\python.exe -B scripts/report_expanded.py
.\.venv\Scripts\python.exe -B scripts/validate_expanded.py
```

默认续跑复用已有结果，含阻塞和失败，避免重复扣费。CodeQL/Linux 原先 25 条最终结果复用，汇总不重复计数。原脚本 run_completed.py 仍可单独检查 smoke/pilot；report_completed.py 和 finalize_records.py 属于旧阶段，会覆盖当前报告，勿用于本次扩展汇总。

新目录安装：

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r environment/requirements-reproduction.txt
git clone https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis.git upstream
git -C upstream checkout --detach 4efb4b9bf7e845e180451b43ba29a25e3edaa0e3
```

模型 deepseek-flash，接口 https://api.deepseek.com/，本地 .env 配置 DEEPSEEK_APIkey。.gitignore 忽略凭据文件，禁止把密钥发聊天或提交。累计预算保持 10 元，所有阶段调用共 1187 次，费用估算上界 4.491330 元，包含失败，不是账户账单；账本不会因续跑清零。

## 记录和限制

configs/expanded_experiment.json 保存配置，expanded_*_manifest.json 保存固定全集与数据 SHA；results/raw/completed 保存真实模型/SMT及错误；logs/stage_01 至 stage_07 保存各阶段。
仅使用已有官方数据和历史上下文，无整工程扫描。530 条 NPD 标签未知/无效记录不补标；其他类型和重复文件排除原因详见 expanded_benchmark_scope.json。补全解析有界，无法恢复的代码关系保留阻塞。所有未分类保留在分母、另列数量，不能把成功执行等同判定正确。
