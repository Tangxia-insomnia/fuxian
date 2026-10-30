# LLM4PFA × DeepSeek Harness 第一阶段 MCP 接入报告

执行日期：2026-10-30（Asia/Shanghai）。本阶段停止于工具封装和离线 MCP 验证，不启动完整 Agent，不调用模型、不重跑实验。

## 结果与范围

两个只读工具已经实现：`get_alert_context` 和 `lookup_function_source`。真实 Python MCP stdio 客户端完成 initialize、tools/list 和 tools/call；正常响应与显式错误均通过验证。**最终18/18项测试通过，0失败、0异常、0跳过，耗时7.287536秒（含完整性检查）。**

Harness Desktop 的版本与配置格式来自本机实际安装包，已形成配置示例。本轮未写入用户 Harness 配置、未启动或重启 Harness，也未声称已在 Desktop 界面看到工具；Desktop 内的实际发现和调用留待下一阶段获授权后验证。

用户指定的 `agent_architecture_analysis.md` 未找到；当前唯一对应材料为 `reproduction/LLM4PFA_architecture_analysis.md`，已阅读其接口、MCP边界及禁用项说明，并与真实 `completion/context.py` 对照。未虚构缺失文件或将报告当成原实现。

## 新增文件

全部实现、依赖和测试记录新增于 `reproduction/harness_bridge/`，另新增本报告；没有修改原核心文件。

| 文件 | 用途 |
|---|---|
| `server.py` | 官方 MCP Python SDK v1 的 stdio Server，仅注册两个只读工具，stdout仅JSON-RPC |
| `tools.py` | 白名单参数校验、原 `ContextRepository.prepare/lookup` 封装、源码/来源哈希和显式错误 |
| `worker.py` | 关闭stdin的本地短生命周期worker；30秒限制、无shell、最小环境、不传模型密钥 |
| `test_server.py` | 原代码/哈希对照、正常/失败/歧义/参数案例及真实MCP管道测试 |
| `config_example.json` | 从本机版本核实的Cordis insert patch列表，可作为YAML内容；不是猜测的mcpServers对象 |
| `README.md` | 依赖、命令、参数、错误、配置位置与已成功调用示例 |
| `requirements.txt` / `requirements-lock.txt` | 独立桥接环境的直接pin及完整依赖锁定 |
| `baseline_state.json` | 开始前3433个已有文件的SHA-256与官方Git状态 |
| `environment.json` / `config_verification.json` | 实际运行依赖与配置字段/路径核查结果 |
| `harness_evidence/` | 安装包内版本、MCP文档/schema/transport、官方patch模板、Desktop目录解析与哈希；附原MIT许可 |
| `results/initial_validation/` | 首次16项测试中1项stdio超时的真实失败记录与输入输出，未删除 |
| `results/stdio_isolation_validation/` | 隔离stdin修复后16/16测试通过的记录 |
| `results/final_validation/` | 增补worker限制测试后18/18的最终结果及逐调用完整输入输出 |
| `hashes.json` | 新增交付物的SHA-256清单（自身除外） |

所有测试/依赖安装使用新的 `harness_bridge/.venv`，MCP SDK固定1.30.0（本次选择稳定v1接口），lizard固定1.17.31。原 `reproduction/.venv` 未安装或升级包；本地虚拟环境和缓存由bridge自己的.gitignore排除。

## 接口及源码证据

`get_alert_context(dataset_id, position)` 以原JSON数组0起始行号调用 `ContextRepository.prepare`，完整保留 `origin/historical_ref/duplicate_equivalent_matches/frames/function_call`。额外返回目标函数、Sink和原location、变量名、函数名调用链、每帧来源JSON Pointer及代码SHA-256。每个body哈希与返回的UTF-8函数文本逐字节核对。没有混入新增路径条件提取或可行性判定。

`lookup_function_source(dataset_id, name, position?)` 从服务端恢复指定样本的调用链；调用链无匹配时查选定数据集及固定历史基线索引。唯一候选交给原 `.lookup` 获取正文，再核对返回的哈希。遇到多份不同正文先返回 `FUNCTION_AMBIGUOUS`，不自动选一份，不把客户端任意传入文本当成本地调用链。

封装刻意比原按compact文本去重更保守：同优先级多个不同SHA-256正文，即使只差空白/注释，也拒绝选版本。完整性来源是官方benchmark JSON及Git历史JSON，不代表已经获得整个C项目的源码提交、构建身份和绝对行号证明。

允许数据集是现有8组NPD配置的固定ID，不接受路径、Git ref或源码参数。输入未知字段、负行号、布尔值/字符串行号、路径穿越、非法函数名均明确失败。实际只对codeql_linux进行了本轮端到端检索验证；其他7组沿用已有白名单配置，未逐组重跑，不能宣称全部上下文均可恢复。

原 `upstream/` 仍在commit `4efb4b9bf7e845e180451b43ba29a25e3edaa0e3`；上下文历史对象仍为 `29ca96e0d5f860d1f4ce07cd3e54e5e25732d1a1`。原 `.prepare` 对缺失上下文、宏和复杂实参的既有限制保留，错误返回 `CONTEXT_UNAVAILABLE/CONTEXT_MALFORMED`，本阶段不修复原语义分析。

## 测试与失败定位

最终18个测试方法覆盖：

1. 正常告警上下文与原 `.prepare` 完整字段一致。
2. 两帧调用链不截断、Sink与变量沿用原结果。
3. 样本内函数检索与原源码哈希一致，提供来源信息。
4. 无样本全局索引检索。
5. 函数不存在明确失败。
6. 全局同名两定义拒绝（合成内存夹具）。
7. 当前样本唯一来源优先于全局歧义（合成）。
8. 当前样本调用链自身歧义时仍拒绝（合成）。
9. 上下文缺失明确失败（合成异常注入）。
10. 上下文必要字段缺失明确失败（合成）。
11. 样本超界及负行号拒绝。
12. 14组错误参数/路径/源码注入/禁止工具请求拒绝（参数化subtests）。
13. 无engine/model/safety/offline_guard导入。
14. 源码body哈希不符拒绝（合成篡改）。
15. worker关闭stdin、有限超时、不传模型密钥（合成环境）。
16. worker超时与启动失败返回明确错误（合成）。
17. 真实stdio进程上的initialize/list/call及8组成功/失败调用，结果同时含structuredContent和一致的JSON文本。
18. MCP handler上的歧义错误为结构化JSON且isError=true（合成，不开放测试后门）。

首次验证并非全部成功：16项中1项stdio工具调用超时，握手和工具列表已成功，工具读取历史Git数据时阻塞。进一步以faulthandler定位到 `tools.py::_load → subprocess.run → communicate`；关闭输入的原始管道测试能返回。最终使用stdin=DEVNULL的独立worker，使原仓库构造器内部Git调用也不继承活跃MCP输入管道，并异步等待worker而不阻塞协议主循环。原核心函数文件没有修改。首次失败、修复后记录和最终记录全部保留；SDK关闭管道时的BrokenResourceError未被掩盖成成功。

成功示例是MCP调用 `get_alert_context({"dataset_id":"codeql_linux","position":12})` 返回两帧 `tcp_set_allowed_congestion_control → kfree`，随后 `lookup_function_source` 用同样样本位置检索 `kfree` 成功。完整实际函数正文和SHA见 `results/final_validation/tool_calls.json`，并非模型生成文本。Python MCP本次协商协议版本为2025-11-25。

## Harness Desktop配置核查

本机进程实际可执行文件在 `E:\downloadsoftware\deepseekharness\DeepSeek Harness.exe`。Windows卸载项记录的旧路径已失效，没有据此填写启动路径。已从实际安装包 `resources/app.asar` 读取版本0.2.1-rc.5与build commit `d4db512a969fccf0c5cc7ec8fe38e9c1d27af916`。

安装包内 `@deepseek-ai/dsh-mcp-client` 同版本的README、实际Config schema与createTransport确认stdio配置字段；官方Cordis MCP模板确认 `- insert: ...` 形式。Desktop `resolveDesktopPaths` 明确profile是 `$DSH_HOME/profiles/desktop`，本机未设置DSH_HOME，实际配置文件为：

`C:\Users\22803\.dsh\profiles\desktop\cordis.patch.yml`

本轮只确认该路径存在，没有读取/打印凭据，没有替换、追加或热重载用户配置。`config_example.json` 提供完整insert片段；启用时应合并到现有patch列表，不覆盖原配置。具体启动命令和YAML示例见bridge README。

安装包文档约定的工具名为 `mcp__llm4pfa__get_alert_context` 与 `mcp__llm4pfa__lookup_function_source`。尚未验证在该Desktop版本中的真实发现、旧协议协商、工具展示和调用；不把Python侧测试冒充Harness端验证。安装包文档声明可协商旧协议，但只有实际接入才能确认这台Desktop与本服务的完整兼容性。

## 保护检查、费用和停止状态

3433个既有文件逐字节SHA-256验证未变，包含upstream、completion、safety、E01和全部历史结果。固定样本与费用账本没有更改。本轮没有接入 `CompletedEngine.run`、`completed_source`、模型提示词、Z3或安全策略；没有安装 `offline_guard.install` 审计钩子。

模型调用0次，新增API费用0元。依赖下载是普通包索引请求，不是模型实验。只启动了短生命周期Python测试服务/worker；原本已打开的Harness没有被本任务启动、重启或配置。

阶段验收：Python只读检索MCP封装、离线测试及版本有据的配置说明完成；Desktop端启用与实际调用未执行。已在本阶段停止。后续最小步骤应是单独批准后合并配置、确认两工具发现并手动调用一个样本；仍无需重写完整Agent或进行模型实验。
