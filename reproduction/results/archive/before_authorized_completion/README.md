# LLM4PFA 简单复现记录

当前结论：部分流程可运行，原始端到端实现被公开内部模块缺失阻塞。没有 LLM 预测结果，没有论文完整复现成功结论。

## 固定材料

- 官方仓库：https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis
- 采用提交：`4efb4b9bf7e845e180451b43ba29a25e3edaa0e3`，保存在 `upstream/`，源码未修改。
- 论文：https://arxiv.org/html/2506.10322v1
- 当前远端 main 已改名 PATHAGENT；版本和数据差异见 `logs/stage_01_repository.md`。
- 完整总结：`results/final_report.md`；真实阶段状态：`results/processed/stage_status.json`。

## Windows / PowerShell 运行方法

以下命令在 reproduction 目录执行。若 upstream 和 .venv 已存在，复用即可。

```powershell
git clone https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis.git upstream
git -C upstream switch --detach 4efb4b9bf7e845e180451b43ba29a25e3edaa0e3
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r environment/requirements-reproduction.txt
.\.venv\Scripts\python.exe -B scripts/audit_repository.py
.\.venv\Scripts\python.exe -B scripts/check_environment.py
.\.venv\Scripts\python.exe -B scripts/probe_samples.py
.\.venv\Scripts\python.exe -B scripts/finalize_records.py
```

脚本职责是记录核查和离线诊断，绝不表示原始模型流水线已修复。再次执行会覆盖对应记录；如需保留本次时间测量，先备份 results、configs/smoke_manifest.json 和 logs。

原始入口检查会真实报 `ModuleNotFoundError: No module named 'util'`；不要通过返回固定值的占位模块来伪装成功。

## 已完成与未完成

- 仓库、完整历史、论文与数据清点已保存。
- 独立环境已安装依赖；Z3 SAT/UNSAT、Clang、lizard、数据读取均通过。
- 5 条官方 NPD 样本完成条件提取与提示词生成，包含原始 0/1 标签；预测字段全部为 null。
- LLM 分析、样本 SMT 求解、最终预测、20 条 pilot、全量评测均未执行。API 费用 0 元。
- 离线提取器只做内存导入适配，详见 patches；上游原文件保持不变。

## 模型与凭据

用户配置为 deepseek-flash、https://api.deepseek.com/、密钥环境变量名 DEEPSEEK_APIkey、总预算 10 元，见 configs/experiment_config.example.yaml。
当前进程未配置该变量。请在自己的本地进程环境或 reproduction/.env 中配置，不要发送到聊天中。`.gitignore` 已列出 `.env`、`.env.*`、`.venv/`、`upstream/`。
当前诊断脚本不调用模型，也不自动读取 .env；后续入口修复后才接入读取指定本地变量的模型客户端，并先验证准确模型名、参数和价格。不要执行上游 model.py 自测，它会尝试多个提供商，也不要使用其中任何嵌入式凭据。

## 证据目录

- logs/：五个阶段的真实状态；未运行阶段明确标记阻塞。
- environment/：Python/工具、固定依赖及实际 freeze。
- results/raw/repository/：Git 历史、树、版本差异、论文 HTML/文本、历史上下文清单。
- results/raw/environment/：安装和模块加载输出。
- results/raw/smoke/：5 条样本的实际提取结果及初始提示词。
- results/processed/：数据清单、逐样本 CSV/JSON、阶段状态。
- results/metrics/：本次指标 NA、指标定义，以及单独标记的作者既有指标。

恢复端到端需优先获取 util、LLM4Detection 相关内部模块和必要运行缓存，确认标签映射；本次未重写跨过程分析、未扫描 Linux Kernel、未开展算法改进或平台接入。
