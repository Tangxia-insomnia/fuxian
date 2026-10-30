# 阶段 2：环境配置与运行检查

状态：本地依赖和组件测试完成；官方端到端流水线被内部模块缺失阻塞。
时间：2026-10-25T23:58:02.570295+08:00（Asia/Shanghai）。

## 环境

- 操作系统：Windows-10-10.0.26200-SP0
- Python：3.11.5 | packaged by Anaconda, Inc. | (main, Sep 11 2023, 13:26:23) [MSC v.1916 64 bit (AMD64)]
- 可执行文件：`E:\codexconversation\课题研究\reproduction\.venv\Scripts\python.exe`
- 原仓库未给依赖版本。独立 `.venv` 使用 `environment/requirements-reproduction.txt` 中明确固定的版本，不升级系统 Python 环境；这些版本为本次选择，并非作者版本。
- 实际依赖：`{'z3-solver': '4.13.4.0', 'libclang': '18.1.1', 'lizard': '1.17.31', 'openai': '1.68.2', 'anthropic': '0.49.0', 'requests': '2.32.3', 'tqdm': '4.66.5', 'python-dotenv': '1.2.2'}`。完整 freeze 见 `environment/dependencies.txt`，安装原始输出见 `results/raw/environment/install.log`。

## 实际检查

| 项目 | 结果 | 输出 |
|---|---|---|
| z3_sat_unsat | passed | `{'version': '4.13.4', 'satisfiable_case': 'sat', 'model': '[environment_test_x = 1]', 'contradictory_case': 'unsat', 'not_a_benchmark_prediction': True}` |
| libclang_parse | passed | `{'parsed': True, 'library_path': 'E:\\codexconversation\\课题研究\\reproduction\\.venv\\Lib\\site-packages\\clang\\native', 'diagnostics': []}` |
| lizard_parse | passed | `{'functions': ['f'], 'not_a_project_scan': True}` |
| official_data_read | passed | `{'readable_files': 14, 'records_including_duplicate_files_and_unlabeled': 1017}` |

Z3 的 SAT/UNSAT 是人工构造环境测试，不是论文样本预测。

## 原始模块加载检查

使用 `runpy.run_path(..., run_name="__diagnostic__")`，不触发模型自测主入口。未修改源码、未伪造缺失模块。

| 文件 | 退出码 | 实际错误 |
|---|---:|---|
| feasibility_analysis_pipeline.py | 1 | `ModuleNotFoundError: No module named 'util'` |
| extract_util_plus.py | 1 | `ModuleNotFoundError: No module named 'LLM4Detection'` |
| prompt_templates.py | 0 | `None` |
| model.py | 1 | `ModuleNotFoundError: No module named 'LLM4Detection'` |

官方仓库没有可直接使用的最小测试套件；以上模块加载是实际执行的入口诊断，不能称为官方端到端自测成功。

## 模型、外部工具与路径

- 用户模型：`deepseek-flash`；接口：`https://api.deepseek.com/`；凭据变量：`DEEPSEEK_APIkey`；预算上限 10 元。
- 当前进程该变量已配置：`False`。不记录其值。
- 模型请求 0 次，费用 0 元；服务可用性、模型 ID、价格和参数兼容性均未验证。不会使用仓库内嵌字面量凭据。
- 外部工具检测只证明命令是否位于 PATH，不证明服务可用：`{'git': 'C:\\Program Files\\Git\\cmd\\git.EXE', 'clang': None, 'codeql': None, 'cppcheck': None, 'infer': None, 'wsl': 'C:\\Windows\\system32\\wsl.EXE', 'docker': 'C:\\Program Files\\Docker\\Docker\\resources\\bin\\docker.EXE'}`。现有基准可直接读取，无需下载或扫描 Linux Kernel。
- 作者硬编码 Linux 路径、上下文缓存和内部工具仍缺失，安装第三方包不能解决这些问题。
- 本次未更改官方源码；检查后的 Git 状态：`clean`。

下一阶段仅进行 5 条官方样本的离线组件诊断。若原始入口和上下文依赖未恢复，不启动 LLM 小实验或全量评测。

## 安装核验与配置过程错误记录

pip check 已运行，退出码 0，输出 No broken requirements found.；保存于 results/raw/environment/pip_check.txt。配置时遇到的日志目录、诊断脚本时区等错误及修复见 results/raw/environment/setup_errors.md。
