# E04：真实模型单样本 U02→U06→U10 验证报告

日期：2026-11-02。结论：本次真实 DeepSeek 调用中，E03 确实将完整 B+Δ 传给 U10；真实 U10 输出通过原 E02/E03 的结构后置检查，随后在 Solver 之前停止。没有运行 Z3、U01 或模型生成代码。

本次属于 **A04 目标 frame=1 的隔离实验**。没有运行前序帧，没有提供或伪造前序求解结果，也没有恢复跨函数 P 传播。本结果不是完整 LLM4PFA 复现或缺陷真假判断。

## 1. 基线、样本和配置

- 开始前发布仓库 main 为 `773db17bf24bb29e21f730cc4e880534815e854a`，工作区干净。E03 三份实现/测试文件及全部清单产物哈希一致。
- 官方上游保持 `4efb4b9bf7e845e180451b43ba29a25e3edaa0e3`，论文 arXiv:2506.10322v1。
- 已阅读 E03 主报告、A04 报告、E02 报告，以及 engine、constraint_bundle、model、context 和 completed_experiment 配置。
- dataset：`benchmark/NPD/codeql/codeql_kernel69_nullpointer.json`；position=12（0 基）；row index=24；sample_id=`NPD/codeql/kernel69:row=12:index=24`。
- 目标 frame=1：`kfree`，变量 `object`，目标语句 `free_large_kmalloc(folio, (void *)object);`。函数体 SHA-256：`ce574246eb0cddd842776be658e862604e577e5dee1c5fc3333b9b4f32dccd39`。
- 函数体来自既有 `ContextRepository.prepare(12)` 的历史上下文，未替换成当前 Linux 源码。数据文件、历史 Git blob、所有 frames 与准确目标体内行号见 [sample_manifest.json](sample_manifest.json)。
- 原配置未修改：`deepseek-flash`、`https://api.deepseek.com/`、原英文 Prompt、max_tokens=3072、temperature=0.0000001、thinking disabled。实际模型返回也为 `deepseek-flash`。
- 密钥仅从现有本地环境/.env 读取；不进入消息、配置快照、日志、Git 或子进程。GET `/models` 返回 200，模型存在。

实际配置及环境：[experiment_config.json](experiment_config.json)、[source_config.snapshot.json](source_config.snapshot.json)。固定输入和代码：[baseline_state.json](baseline_state.json)、[candidate_freeze.json](candidate_freeze.json)。没有升级依赖。

## 2. 实验专用接入和停止方式

新增 [run_e04.py](run_e04.py)，不修改任何受保护模块。

1. 使用原 `ContextRepository`、原提取器、原 Prompt 和 `completed_source(patch_dir=E04新目录)`。生成的函数体就是 E03 的补全结果，没有对算法作新的源代码替换。
2. 为隔离目标帧，通过同一 `data_flow_analysis_pipeline` 的真实参数接口直接运行 frame=1。没有调用从 frame=0 开始的 `CompletedEngine.run()`；构造对象仅用于复用未改动的方法并避免默认向 E03 写快照。
3. 命名空间仍绑定原 `assemble_transfer()`。输出钩子先执行原 `validate_transfer_output()`；PASS 后抛出 `ExperimentStop(BaseException)`，FAIL/UNKNOWN 记录后同样终止。钩子位于原求解 `try/except Exception` 外，不返回 SAT、可行路径或其他模拟值。
4. 额外禁止导入 Z3/solver_worker、禁止实验运行段启动子进程；求解/跨帧回调只会抛出停止异常。它们本次均未被触达。U01/其他范围外 Prompt 也被禁止。
5. 原 `DeepSeekModel` 真实执行。实验包装层只限制次数/预算、观察 Prompt 方法及重定向新日志。Prompt 返回字符串不变；原模型 HTTP 请求、参数、Token 解析和累计账本逻辑不变。
6. 累计账本仍在原路径原子追加；新增 call/service 日志重定向到 E04，避免覆盖旧 `service_check.json` 或写入其他历史结果目录。每次保存前验证旧条目、额度及并发状态。

调用上限同时约束为：最多 8 个 HTTP 请求（含服务检查），最多 8 次生成请求，新增费用保守上界 2 元；原累计 10 元预算继续生效。没有自动重试。

离线停止测试 [offline_tests.json](offline_tests.json) **10/10 通过**，覆盖 PASS、FAIL、UNKNOWN 均先执行原后置检查且不进入求解/修复、原门位于 try 外、禁用导入、Prompt 字符串不变等。冻结候选后仅运行一次真实样本。

## 3. 真实调用与费用

| 阶段 | 新调用 ID | 次数 | 输入 Token | 输出 Token | 耗时/秒 | 配置费率记账上界/元 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| U02 | 1188 | 1 | 273 | 41 | 0.552645 | 0.000874 |
| U05（原流程中间推理） | 1189 | 1 | 561 | 45 | 1.133452 | 0.001482 |
| U06 | 1190 | 1 | 950 | 123 | 1.487895 | 0.002884 |
| U10 | 1191 | 1 | 600 | 159 | 1.552954 | 0.002472 |
| 合计 | — | 4 | 2384 | 368 | 4.726947 | **0.007712** |

另有 1 次 GET `/models`，总 HTTP 请求 5 次。总 Token 2752，其中输入 cache hit=768、cache miss=1616。整个目标实验计时约 6.478 秒，包括准备及服务检查，不是纯模型时间。

**费用口径：0.007712 元是实际返回 Token 用量乘以原配置输入 2 元/百万、输出 8 元/百万的保守上界；不是已核实的账户实扣账单。**当前接口响应没有 billing 字段，也没有按 cache hit 的实际结算费率核算，所以 `actual_account_billed_cny=null`，不得将估算冒充实际扣款。

原累计账本从 1187 条增至 1191 条，费用上界从约 4.491330 元增至 4.499042 元；原 1187 条内容和原预算不变。前后快照：[budget_ledger.before.json](budget_ledger.before.json)、[budget_ledger.after.json](budget_ledger.after.json)。完整使用量和计时见 [metrics.json](metrics.json)。

依照“只提交 E04 目录”的要求，本机实际累计账本的追加不会另行提交到发布副本的旧账本路径。E04 保留完整 after 快照；后续应延续本机最新账本，不能将发布副本中的旧账本当作已包含本轮费用。

## 4. 三个不同对象的证据

### 本地 B+Δ 合并脚本

原 `assemble_base_delta()` 通过 E03 的真实绑定方法执行；[001.json](constraint_transfer/constraint_transfer_e03/001.json) 保存 bundle、来源、区间、声明/断言 IR 和前置结果。

| 对象 | 原始响应/脚本 SHA-256 | 声明 | 断言 |
| --- | --- | ---: | ---: |
| 新 U02 原始 B | `7a65b85e641f0e71c426ddf299c6035838044ca765eade808e1d6e3bdcfd8d92` | 2 | 2 |
| 新 U06 原始 Δ | `c92548f94ba4604ef0b08c4a015e23561e1bb2c40a3f29f94fe7cce405eca1d9` | 0 | 0 |
| 新本地 merged_script | `58764a340fca08e306a510b68c81d47875be4def8353cefd08022bff1c3b09fc` | 2 | 2 |

B 保留 `folio_test_slab`、`object` 的 Int 声明及两条等于 0 的断言。Δ 是真实模型返回的注释代码块，没有新增声明/断言。其完整原文仍进入合并输入，未删除或补写。

新 U02 文本哈希恰好与历史 U02 相同。它仍是一次新请求：调用 ID=1188、有新 HTTP 请求/200 响应、新 response_id、新 Token 记录和账本条目；与历史 response_id 不同。不能仅凭相同文本哈希认定复用了缓存实验文件。历史 0231/0233/0234 只用于身份和事后对照。

### 实际发送的 U10 请求

- [05_request.json](transport/05_request.json)：在 `requests.Session.send` 边界记录真实 PreparedRequest 的完整请求体、解析后的 payload 与 SHA-256；没有保存 Authorization 或其他请求头。
- [1191.json](model_calls/1191.json)：原客户端记录的本次消息、完整响应、Token、返回模型及耗时。
- 两份记录的 messages 完全一致；实际 U10 消息恰好包含完整 merged_script 一次，B/Δ 代码片段均逐字可定位；其内容哈希与原 Prompt 构造事件一致。
- 独立核验：[request_response_verification.json](constraint_transfer/request_response_verification.json)；便于阅读的实际消息：[U10_actual_request_messages.json](constraint_transfer/U10_actual_request_messages.json)。

因此，本轮以真实传输记录验证 U10 输入，未用本地 merged_script 冒充模型请求。

### U10 真实响应及后置检查

- [05_response.json](transport/05_response.json)：真实 HTTP 200 响应；response_id、choices 与客户端调用记录一致。
- [U10_raw_response.txt](constraint_transfer/U10_raw_response.txt)：完整新响应；[U10_code_checked.py.txt](constraint_transfer/U10_code_checked.py.txt)：原 E03 解析后交给门检查的文本。
- [002.json](constraint_transfer/constraint_transfer_e03/002.json) 与 [U10_postcondition.json](constraint_transfer/U10_postcondition.json)：原 E02/E03 后置结果 **PASS / accepted=true**。
- 基础/新增断言缺失数、声明缺失数、类型冲突、身份冲突、重复声明、重复断言均为 0。
- 随后抛出停止异常，`reason=completed_before_solver`；没有执行返回脚本中的 import、Solver() 或 s.check()。

## 5. 覆盖限制与尚存问题

本样本的 Δ 只有注释，**没有验证真实模型面对非空 Δ 时也保留全部新增断言**。本次可靠结论是：基础 B 得到保留，Δ 原文进入真实 U10，真实输出符合本次结构成员契约。

U06 的注释声称空指针会触发提前 return，但没有将它表达为新增约束；U10 同样仅用注释描述“不可达”。结构 PASS 不能证明提前退出语义被建模，不能推出目标路径可行或不可行。

另观察到 U05 将 `s` 写为 Int 后使用 `s.add`；该原始响应完整保留，本轮没有执行或修正它。它作为原流程的中间消息传给 U06，不是本次执行的求解脚本。这是后续语义/输出协议审计的候选问题，不属于 E04 修复范围。

全程 `semantic_correctness=NOT_ASSESSED`、`polarity_correctness=NOT_ASSESSED`。没有调用安全 v1 产生 FILTER、KEEP、UNKNOWN；本文 PASS 是结构契约状态，完全不代表告警裁决。

## 6. 保护核验与九项验收回答

[preservation_check.json](preservation_check.json)：检查原有 4218 个文件，其中 **4217 个不可变文件字节未变**。唯一授权变动是累计预算账本追加 4 条新调用并更新总费用；旧条目及预算完全保持。上游、Prompt、E01、E02、E03 engine/bundle、安全 v1、固定样本和历史实验输出均未改。代码冻结哈希再次一致。

1. **是否真实调用 U02/U06/U10？** 是，三者均有新请求、HTTP 200 和新 response_id。
2. **分别多少次？** U02=1、U06=1、U10=1；原流程另有 U05=1。生成请求总数 4，服务 GET=1。
3. **U10 收到完整 B+Δ？** 是，实际 PreparedRequest 与客户端消息逐字对照通过。
4. **输出通过 E02？** 是，本次为 PASS；通过原 `validate_transfer_output` 执行，未改检查器。
5. **失败在哪一层？** 本次结构传递与停止验收没有失败；语义未评估、非空 Δ 未覆盖，不能将这些边界当作已验证通过。
6. **API 费用？** 可核实 Token 记账上界 0.007712 元，低于 2 元；账户实际实扣未由响应提供，无法精确报告。
7. **Z3 为 0？** 是；边界调用 0、导入 0、求解 0、模型生成 Python 执行 0、U01=0。
8. **历史基线未修改？** 是；累计账本按本次明确授权追加，旧记录未覆盖。未把原账本文件的必要字节变化隐藏为“全部文件不变”。
9. **提交和报告？** 本目录独立提交到 GitHub main；确切提交 SHA 和报告地址见最终交付，Git 历史可核查。

本阶段通过单样本结构传递验收，完成后停止，不进入 E05。
