# LLM4PFA 检索 MCP Server（第一阶段）

通过本地 stdio 暴露两个只读工具，调用未修改的 `completion/context.py`。不运行 Agent 推理、模型 API、Z3、原引擎或安全判定，不输出 FILTER/KEEP/UNKNOWN 结论。源码返回值是待分析的数据，不是指令或可行性证明。

## 环境与启动

本机 Windows、Python 3.11.5。MCP Python SDK 固定 `1.30.0`，lizard 沿用 `1.17.31`。依赖安装在独立 `harness_bridge/.venv`，未更新原 `reproduction/.venv`。完整版本在 `requirements-lock.txt`；无需 API Key，也不加载 `.env`。

从 `reproduction` 目录执行（首次安装需要访问 Python 包索引；服务运行只读本地数据）：

```powershell
python -m venv harness_bridge/.venv
& .\harness_bridge\.venv\Scripts\python.exe -m pip install -r harness_bridge/requirements-lock.txt
& .\harness_bridge\.venv\Scripts\python.exe -B harness_bridge/server.py
```

最后一条启动后等待 MCP stdin，stdout 专用于 JSON-RPC，诊断走 stderr。实际客户端应将解释器和 `server.py` 指定为绝对路径；服务不依赖调用者工作目录。

需要原 `upstream` Git 仓库和历史对象 `29ca96e0d5f860d1f4ce07cd3e54e5e25732d1a1`，只拿 benchmark JSON 不足以恢复历史调用链。若从含 submodule 的仓库克隆，先初始化 upstream，并确认该对象可通过 `git -C upstream cat-file -t 29ca96e0d5f860d1f4ce07cd3e54e5e25732d1a1` 读取。缺失时工具明确失败，不下载内核、不猜源码。

## 工具与参数

| 工具 | 必填参数 | 可选参数 | 行为 |
|---|---|---|---|
| `get_alert_context` | `dataset_id`, `position` | 无 | 原 `ContextRepository.prepare(position)`；完整返回 frames、function_call、function_chain、Sink、变量及来源哈希 |
| `lookup_function_source` | `dataset_id`, `name` | `position` | 指定样本时优先其调用链，否则查该数据集/固定历史上下文中的函数；原 `ContextRepository.lookup` 完成检索 |

`position` 是 **JSON 数组从0开始的行号**，不是告警的 `index` 字段。函数名仅接受最多128个ASCII字符的普通 C 标识符。无会话内“上次样本”默认值；每次显式传 `position`，避免串样本。客户端不能传 `local_chain`、源码或路径。

数据集 ID 白名单沿用 `scripts/run_expanded.py` 的八组配置：`codeql_linux`、`codeql_libav`、`codeql_openssl`、`cppcheck_linux`、`cppcheck_libav`、`cppcheck_openssl`、`infer_libav`、`infer_openssl`。路径和历史文件是代码常量，外部字符串不会拼接为文件路径或 Git ref。路径解析后须仍处于固定 benchmark 路径，拒绝目录穿越和越界链接。

同一优先级出现多个不同源码 SHA-256 时返回 `FUNCTION_AMBIGUOUS`，不自行选择。相比原索引按 `compact(body)` 合并，此封装更保守：即使仅空白/注释不同而导致源码字节哈希不同，也拒绝自动选版本。样本调用链中恰有一个定义时可优先于全库同名定义；调用链本身多定义则失败。

成功返回 `{"ok":true,"data":{...},"bridge_version":"llm4pfa-mcp-bridge-v1"}`。失败返回 `{"ok":false,"error":{"code":...,"message":...,"details":{...}},...}`，MCP 同时设置 `isError=true`。`structuredContent` 和 JSON text content 内容一致。主要错误：`INVALID_ARGUMENT`、`DATASET_NOT_ALLOWED`、`SAMPLE_NOT_FOUND`、`CONTEXT_UNAVAILABLE`、`CONTEXT_MALFORMED`、`FUNCTION_NOT_FOUND`、`FUNCTION_AMBIGUOUS`、`SOURCE_HASH_MISMATCH`、`PATH_NOT_ALLOWED`、`REPOSITORY_UNAVAILABLE`、`RETRIEVAL_TIMEOUT`、`WORKER_FAILED`。

每次 MCP 调用使用短生命周期 worker（30秒上限、stdin=DEVNULL、shell=False、最小环境且不传模型密钥），worker 再调用原仓库函数。首次版本曾因 Git 子进程继承开放的 MCP stdin 而阻塞；独立 worker 修复了这个通信问题。没有改动 `completion/context.py`，没有接入 `offline_guard.install`。进程/路径限制不等于完整 OS 沙箱；本地 Python、Git、仓库及依赖仍应可信。

## 已核实的 Harness Desktop 配置

核查对象是本机已安装的 **0.2.1-rc.5**，不是按通用 `mcpServers` 格式猜测：

- 程序：`E:\downloadsoftware\deepseekharness\DeepSeek Harness.exe`。
- 安装包 `resources/app.asar/package.json` 标明版本 `0.2.1-rc.5`、build commit `d4db512a969fccf0c5cc7ec8fe38e9c1d27af916`。
- 同包 `@deepseek-ai/dsh-mcp-client` 的 README、实际 `Config` schema、transport 实现均确认 `serverName/transport/command/args/env/cwd/toolCallTimeoutMs/failOnStartupError`。
- 同包 Desktop `resolveDesktopPaths` 确认 profile 为 `$DSH_HOME/profiles/desktop`；当前未设置 `DSH_HOME`，实际目录是 `C:\Users\22803\.dsh\profiles\desktop`。
- 配置目标：`C:\Users\22803\.dsh\profiles\desktop\cordis.patch.yml`。这里是 Cordis **patch 列表**，新增插件必须使用 `insert`。不能把 `.dsh` 凭据文件或 Electron `desktop/settings.json` 当成 MCP 配置。
- `harness_evidence/` 保存安装包内的文档、schema实现、官方 MCP patch 模板、目录解析片段及 SHA-256。官方项目地址由安装包 manifest 验证为 https://github.com/deepseek-ai/deepseek-harness 。

`config_example.json` 是已核实的 **Cordis insert patch 文档**，JSON 内容也是合法 YAML，可把其中的 `insert` 项追加到现有 `cordis.patch.yml` 列表；不要覆盖现有配置或凭据。使用其他机器时修改 command/args/cwd 的绝对路径。对应 YAML 如下：

```yaml
- insert:
    - id: mcp-llm4pfa-retrieval
      name: '@deepseek-ai/dsh-mcp-client'
      config:
        serverName: llm4pfa
        transport: stdio
        command: 'E:\codexconversation\课题研究\reproduction\harness_bridge\.venv\Scripts\python.exe'
        args:
          - '-B'
          - 'E:\codexconversation\课题研究\reproduction\harness_bridge\server.py'
        cwd: 'E:\codexconversation\课题研究\reproduction'
        env:
          PYTHONUTF8: '1'
          PYTHONDONTWRITEBYTECODE: '1'
        toolCallTimeoutMs: 60000
        failOnStartupError: false
```

配置启用后 Harness 的工具名按安装包文档应为 `mcp__llm4pfa__get_alert_context` 和 `mcp__llm4pfa__lookup_function_source`。本阶段**没有写入/应用配置，没有启动或重启 Harness，没有让 Harness 调用工具**；这两个前缀名的实际 Desktop 发现仍待后续验收。安装包文档说明新协议可协商旧协议；本次 Python 客户端实际协商 `2025-11-25`，与 Desktop 的真实协商尚未实测。

## 一次实际成功调用

Python MCP 客户端经真实 stdio 发送：

```json
{"name":"get_alert_context","arguments":{"dataset_id":"codeql_linux","position":12}}
```

调用成功，`isError=false`、`ok=true`，完整结果包含两帧 `tcp_set_allowed_congestion_control → kfree`。随后调用 `lookup_function_source`，参数为 `{"dataset_id":"codeql_linux","position":12,"name":"kfree"}`，返回 `selection_tier=sample_chain`，源码字节哈希与原仓库返回值一致。

这里是 Python MCP 客户端验证，不是 Harness 或模型推理结果。完整实际输入/输出、错误案例与测试结果保存在 `results/`；示例省略长函数正文，实际工具不截断 frames。

## 离线测试与证据

```powershell
& .\harness_bridge\.venv\Scripts\python.exe -B harness_bridge/test_server.py
```

默认创建新的时间戳结果目录，拒绝覆盖历史记录。测试含真实源码/多帧哈希比对、正常和失败检索、合成同名多定义、样本优先级、参数与路径注入、缺失上下文、worker异常和真实 MCP initialize/list/call。合成样本只在内存构造，不修改官方数据。模型调用0次；测试只启动本地 Python MCP 服务，不启动 Harness。

`baseline_state.json` 是本工作区的完整性快照（含本地已有的架构分析附件），测试还校验3433个已有文件不变。新克隆若缺少快照中的本地附件，完整性检查会报缺失，不能当作已验证不变；服务运行本身不依赖该快照。要复用完整性测试，先补齐所记录原件或在新审计目录建立本机基线，保留原快照。
