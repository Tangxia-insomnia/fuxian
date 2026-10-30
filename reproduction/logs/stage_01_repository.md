# 阶段 1：仓库与论文核查

状态：已完成公开材料核查；未证明代码与论文实验完全一致，未运行模型实验。
核查时间：2026-10-25T23:53:23.420424+08:00（Asia/Shanghai）。

## 版本证据

- 官方仓库：https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis.git
- 当前远端 main：`37a1fdc99d59a8af176ae8c93fa4bf0adbeed997`，2026-10-16 更新。
- 实际采用：`4efb4b9bf7e845e180451b43ba29a25e3edaa0e3`，detached HEAD，2025-07-21 的公开 LLM4PFA 版本。
- 选择理由：最新 README 改名 PATHAGENT，流水线清空 6 项路径并改变样本上限；历史版本仍描述 LLM4PFA，保留更多原始配置和作者结果。没有 tag 或 release 提供论文版本映射。
- 该版本 5 个 Python 源文件与 2025-03-29 提交相同；完整历史共 19 个可达提交，内部缺失模块在历史路径中也未出现。
- 原论文：arXiv:2506.10322v1，2025-06-12。正文为三类缺陷 NPD/UAF/BOF、364 条告警、45 个真实缺陷；主模型 GPT-4o-mini、temperature=0，其他模型为 Claude Sonnet 3.5、Qwen2.5-Coder-32B-Instruct、DeepSeek-V2-Instruct；基线 LLM4SA、LLMDFA。
- README 扩展为五类、443 条、47 个真实缺陷，不能混同论文 v1。论文 HTML 下载状态：`{'downloaded': True, 'sha256': '42d06616f8efeec696ca30b890fda76051a79d0ef837ca35f685177ff3cd1227', 'url': 'https://arxiv.org/html/2506.10322v1'}`。

## 代码职责与运行入口

| 文件 | 功能与限制 |
|---|---|
| `llm4pfa/feasibility_analysis_pipeline.py` | `detect_pipeline()` 读取告警和约束缓存，调用条件提取、LLM、Z3、上下文递归；目前导入即被缺失内部模块阻断。示例默认面向 NPD、Linux，不能直接声称支持所有缺陷。 |
| `llm4pfa/extract_util_plus.py` | 条件、提前跳转、赋值等提取；导入缺失 `conditions_info` 并依赖 clang。 |
| `llm4pfa/prompt_templates.py` | 条件推理、Z3 脚本生成、合并和错误修复提示词。 |
| `llm4pfa/model.py` | 多模型封装；仍导入缺失工具定义，部分配置为非空字面量，禁止使用或记录其中可能的凭据。 |
| `llm4pfa/analyze_c_cpp_project.py` | lizard 项目函数索引，包含作者机器路径；本次不运行整项目扫描。 |

## 数据文件实际清点

下表仅记录 `result` 原始值，不将未核实的值擅自解释为标签。

| 数据文件 | 记录数 | result 分布 |
|---|---:|---|
| `benchmark/BOF/codeql_openssl_cwe122.json` | 42 | `{'0': 42}` |
| `benchmark/DBZ/all_cwe369.json` | 16 | `{'0': 14, '1': 2}` |
| `benchmark/NPD/codeql/codeql_kernel69_nullpointer.json` | 70 | `{'0': 48, '1': 22}` |
| `benchmark/NPD/codeql/codeql_libav_nullpointer.json` | 57 | `{'0': 55, '1': 2}` |
| `benchmark/NPD/codeql/codeql_openssl_nullpointer.json` | 50 | `{'0': 41, '1': 8, '-1': 1}` |
| `benchmark/NPD/cppcheck/cppcheck_libav_nullpointer.json` | 10 | `{'1': 2, '0': 8}` |
| `benchmark/NPD/cppcheck/cppcheck_linux_nullpointer.json` | 594 | `{'0': 65, '-1': 3, 'None': 526}` |
| `benchmark/NPD/cppcheck/cppcheck_openssl_nullpointer.json` | 5 | `{'0': 5}` |
| `benchmark/NPD/infer/infer_libav_nullpointer.json` | 6 | `{'0': 6}` |
| `benchmark/NPD/infer/infer_openssl_nullpointer.json` | 16 | `{'0': 13, '1': 3}` |
| `benchmark/UAF/codeql_kernel69_cwe416.json` | 16 | `{'0': 16}` |
| `benchmark/UAF/codeql_openssl_cwe416.json` | 9 | `{'0': 9}` |
| `benchmark/UBI/all_cwe457.json` | 63 | `{'0': 63}` |
| `benchmark/UUA/all_cwe457.json` | 63 | `{'0': 63}` |

- `UBI/all_cwe457.json` 与 `UUA/all_cwe457.json` SHA-256 相同，视为文件副本，不能累计两遍。
- Cppcheck/Linux 的 594 条包含 526 条无 result、3 条 -1；与论文对应分组 83 条/8 个真实缺陷不一致，不能任意补标签。
- CodeQL/OpenSSL NPD 含 1 条 -1，暂不纳入有监督指标。
- 原论文三类缺陷的文件在 2025-03-29 与采用版本中 Git blob 相同，因此简单退回 3 月不能修复已知数据不一致。
- 作者 LLM4PFA 聚合指标 32 份；另有 LLMDFA 和 LLM4SA 输出。聚合结果不等于本次实验结果，已单独标记来源；未发现 LLM4PFA 完整逐样本预测、正式评测脚本或安装说明。

## 阻塞和后续边界

- 缺失模块：`LLM4Detection.agent.tool_utils, LLM4Detection.agent_simple, LLM4Detection.agent_simple.prompt_template, LLM4Detection.agent_simple.tool_definion, LLM4Detection.baseline_models.model, LLM4Detection.m_agent.conditions_info, util, util.data_utils, util.path_util`。
- 缺少 `PathUtil`、`DataUtils`、函数检索、函数调用/参数识别、解引用定位、工具 schema、`ContextHelper/Conditions` 等公开实现，以及流水线所需函数调用链/解引用/缓存文件。
- 历史路径中出现过 `cache_dataflow_function.py`，需要进一步查看，不能仅依据文件名认定它能恢复缺失模块。
- 部分捕获异常会返回 `result=True`；上下文缺失不能当成成功分析。原代码不应直接用于可信评测。
- 用户指定 DeepSeek `deepseek-flash`、`https://api.deepseek.com/`、环境变量名 `DEEPSEEK_APIkey`、总费用上限 10 元；与原论文模型不同，必须独立报告。未读取或使用仓库中的任何凭据。
- 只允许必要接线、路径和依赖适配；若需要重写函数检索、跨过程分析等核心模块，停止端到端复现并记录阻塞。

证据：`results/raw/repository/`；数据清单：`results/processed/dataset_inventory.json`。原始仓库代码未修改。

## 历史上下文材料补充核查

在提交 `29ca96e0d5f860d1f4ce07cd3e54e5e25732d1a1` 找到已删除的 `cache_dataflow_function.py` 和 8 份 `baseline/NPD-*.json`。缓存脚本仍导入缺失 `util`、`tool_utils`，无法独立重建缓存。历史 baseline 包含函数调用链，可作为后续恢复部分上下文的材料，但没有数据集标签，不能据此补出论文缺失标签，也不能替代函数解析/参数映射/解引用定位实现。详见 `results/raw/repository/historical_context_inventory.json`。
