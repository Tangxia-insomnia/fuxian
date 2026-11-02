# E04-ND：真实非空 Δ 传递补充实验

日期：2026-11-02。本次仍属于 E04，不进入 E05。

**核心结果：真实 U06 生成 3 条不同于实际 B 的逻辑断言；其中至少一条有直接源码条件依据。完整 B+Δ 进入真实 U10 请求，真实输出保留全部声明和断言，原 E02/E03 后置检查 PASS。**

同时检出模型语义缺陷：U02 将分支条件弱化为恒真式；U06 把 `skb->len` 错写为 `skb`，并混用赋值前后的变量状态。因此本轮结论是“非空结构传递得到验证，但存在语义缺陷”，不能声称整组 Δ 忠实表达程序语义或路径判断正确。

## 1. 实验前核验与选择依据

开始时 GitHub main=`88982dfb087ef8adbe399a3b17766d598f532332`，发布工作区干净。官方上游仍为 `4efb4b9bf7e845e180451b43ba29a25e3edaa0e3`。E03 与 E04 全部哈希清单核对通过，E02 checker 保持 `5a0d6532e73af8485113541fd3982f491ddeef0b6b44c7f856ad61d649a1916a`。

已阅读 E04 主报告、E03 报告、E02 检查器及当前 pipeline/Prompt/实验运行器，并只读检查历史调用。原 10 条审计样本中：A01 有历史非空 Δ，但伴随已知极性冲突；A04 为注释增量；其余多走提前退出合并分支、没有正常 U06，或有上下文/格式障碍。本次没有基于标签选择或向模型透露标签。

继续只读筛查原 `results/raw/completed/calls/` 中 41 条 U06 历史记录，并检查 4 个候选的源码与原提取结果。没有对候选运行模型或求解。筛查产物：[historical_candidate_scan.json](historical_candidate_scan.json)、[source_candidate_preflight.json](source_candidate_preflight.json)。最终在真实调用前固定一个样本，不根据新结果换样本：

| 字段 | 实际值 |
| --- | --- |
| dataset | `benchmark/NPD/codeql/codeql_kernel69_nullpointer.json` |
| dataset_id | `codeql_linux` |
| position（0 基） | 23 |
| row index | 42 |
| sample_id | `NPD/codeql/kernel69:row=23:index=42` |
| 函数 / frame | `__ip6_append_data` / 0 |
| 目标 | `skb_prev->csum = csum_sub(skb_prev->csum,` |
| 函数体 SHA-256 | `4f652c2800b05d4fab8cf926af60a66c348cbdd8e5cc95f2620555feaf1e20a9` |

源码直接声明 `unsigned int fraggap;`，并在 `if (fraggap)` 真分支内访问目标。历史 U06 曾产生 `fraggap` 的范围断言，说明有合理的新约束生成依据，但没有保证新模型会复现同样输出。实际结果确实不同于历史记录。

历史调用 0010/0011/0012/0013 仅用于选择、身份和事后对照；副本和 SHA 在 [selected_sample.json](selected_sample.json)。它们没有作为新响应或人工断言喂给模型。

## 2. 执行方式、保护和停止

新增 [run_nd.py](run_nd.py)，来自 E04 独立运行器的实验副本。仅改变样本身份/目标帧、证据引用、输出目录和本次预算上限；差异完整保存于 [driver_adaptation.diff](driver_adaptation.diff)。原 E04、官方 Prompt、pipeline、E01/E02/E03 核心代码及安全 v1 没有修改。

模型配置继续使用 `configs/completed_experiment.json`：deepseek-flash、原 API URL、temperature=0.0000001、max_tokens=3072、thinking disabled。GET `/models` 通过，模型实际返回 deepseek-flash。密钥仅从本地配置读取，未写入任何记录。

本次运行单函数的目标 frame=0，调用原 E03 生成的 `data_flow_analysis_pipeline`。没有模型输出代码执行，没有前序求解、跨函数状态修复或安全裁决。真实调用前停止测试 **10/10 通过**，然后冻结运行器、样本、源码和相关依赖 SHA：[candidate_freeze.json](candidate_freeze.json)。冻结后没有改动这些文件。

仍使用原 `assemble_transfer` 和 `validate_transfer_output`。后置检查完成后，实验停止钩子在求解 `try/except` 外抛出 BaseException；失败也立即停止，不进入 U01。Z3 导入、Solver 回调和子进程另有禁止钩子，实际均未触发。

上限：最多 8 次生成请求、另至多 1 次模型列表检查；新增费用保守上界 0.5 元，同时遵守原累计 10 元账本。实际只运行一次、没有重试或更换样本。

## 3. 真实调用、Token 和费用

| 阶段 | 新调用 ID | 次数 | 输入 Token | 输出 Token | 耗时/秒 | 配置费率记账上界/元 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| U02 | 1192 | 1 | 268 | 55 | 0.666532 | 0.000976 |
| U05 | 1193 | 1 | 4342 | 259 | 1.387339 | 0.010756 |
| U06 | 1194 | 1 | 4959 | 232 | 1.660000 | 0.011774 |
| U10 | 1195 | 1 | 714 | 187 | 1.119955 | 0.002924 |
| 合计 | — | 4 | 10283 | 733 | 4.833826 | **0.026430** |

另有 1 次成功 GET `/models`，共 5 次 HTTP 请求。总 Token=11016，输入 cache hit=4736、cache miss=5547。实验脚本总计时约 5.952 秒。

**费用不是实扣账单。**0.026430 元为实际返回 Token 按原配置输入 2 元/百万、输出 8 元/百万计算的保守上界，低于 0.5 元。接口不返回账户实扣费用；没有用未经核实的缓存折扣费率编造实扣金额，`actual_account_billed_cny=null`。

累计账本旧 1191 条保持不变，只追加 1192–1195 四条；总记账上界从约 4.499042 元增至 4.525472 元。[metrics.json](metrics.json) 保存完整使用量和费用口径。

## 4. 实际 B 与真实新增 Δ

U02 新 B 原文含：

```python
fraggap=Int('fraggap')
skb_prev=Int('skb_prev')
s.add(Or(fraggap == 0, fraggap != 0))
s.add(skb_prev == 0)
```

U06 真实新增断言为：

```python
s.add(Or(And(skb == 0, fraggap == 0),
         And(skb != 0, fraggap == skb - maxfraglen)))
s.add(fraggap != 0)
s.add(skb != 0)
```

Δ 还新增 `skb`、`maxfraglen` 两个 Int 声明。三条断言均不是 B 的已有结构成员，且都进入 U10 输出。特别是 B 的 `Or(fraggap == 0, fraggap != 0)` 恒真，允许 fraggap=0；新增 `fraggap != 0` 排除了 0，是实际逻辑限制，不能归类为注释、仅声明、恒真或重复基础约束。这个简单比较没有使用求解器。

| 新断言 | 保存源码的函数体行号 | 来源核对结果 |
| --- | --- | --- |
| 两分支 `Or(And(...), And(...))` | [175](selected_source.c#L175)–178，另见 180–185、239–252 | 有赋值分支来源，但 **不忠实**：源码是 `skb->len - maxfraglen`；模型误用指针 `skb`。同时未区分 skb、maxfraglen 的时间版本 |
| `fraggap != 0` | [271](selected_source.c#L271)–275；类型声明在 170 | 与目标所在 `if (fraggap)` 真分支局部文本一致；构成本次至少一条有直接来源的新限制 |
| `skb != 0` | [251](selected_source.c#L251)–252，目标在 275 | 前面的空指针提前跳转支持目标处非空；但模型注释从早期 skb 推导，未证明跨赋值身份 |

原提取器/模型注释使用的条件行号为 270；保存的函数体实际为 271。本报告以冻结源码的 1 基行号引用，未为统一行号修改原提取器或 Prompt。

每条断言的原始文本、原文 SHA-256、E02 公式及其哈希、U06 行号、源码片段和片段哈希，完整保存在 [new_assertions.json](constraint_transfer/new_assertions.json)。这些是本次事后源码文本核对，不是伪造的独立人工语义证明。

| 约束对象 | SHA-256 |
| --- | --- |
| U02 原始响应 B | `beff74bf8da49808fb5577082e033e25a93e957dc73fa51a800253364ac99cd3` |
| U06 原始响应 Δ | `2400bd4f63661a904b52a137651a0c86eb4239e95ac5432e98169aae23bc3c69` |
| 本地 B+Δ | `f24166bace83c56c44b6d0a4e2285a49ab78e5443dbbefa812709c146e13adcb` |

## 5. 合并、实际请求及输出分别验收

1. **本地合并**：[001.json](constraint_transfer/constraint_transfer_e03/001.json)。原适配器确定性保留 B 的 2 项声明/2 条断言，以及 Δ 的 2 项声明/3 条断言。前置 PASS；无结构重复、声明类型冲突、符号身份缺口或意外覆盖。没有删除 B 的恒真断言，也没有修正 Δ 的错误表达式。
2. **实际 U10 请求**：[05_request.json](transport/05_request.json) 在 `requests.Session.send` 边界捕获完整 PreparedRequest body，未保存请求头。实际消息包含完整合并脚本一次，B/Δ 均逐字存在；与原客户端 [1195.json](model_calls/1195.json) 中的 messages 一致。核验见 [request_response_verification.json](constraint_transfer/request_response_verification.json)。
3. **真实 U10 响应**：[05_response.json](transport/05_response.json) 与客户端 response_id/choices 一致；[U10_raw_response.txt](constraint_transfer/U10_raw_response.txt) 保存完整原文。不是本地 merged_script，也不是历史 U10 输出。
4. **原检查器后置结果**：[002.json](constraint_transfer/constraint_transfer_e03/002.json) 为 **PASS / accepted=true**。全部 4 项声明和 5 条断言保留；基础/新增断言缺失、声明缺失、结构身份/类型冲突、重复项均为 0。随后立即停止，未运行 Solver。

## 6. 类型、身份和极性风险

- **基础条件弱化**：原 U02 输入包含 `if (fraggap)`，真实模型却生成恒真 Or。Δ 之后补回非零条件；这不能证明 U02 条件翻译可靠。实际 Δ 并不是历史记录中预期的 unsigned 范围约束。
- **字段与指针混用**：`skb->len` 被表示为 `skb`，E02 的 SMT 字面符号/sort 检查无法识别此 C 语义错误。结构身份冲突计数为 0，不代表 C 变量身份正确。
- **跨赋值状态未区分**：175–178 使用旧 skb；185 赋给 skb_prev；239–250 重新分配 skb，180–183 也可能通过地址参数修改 maxfraglen。模型公式仍使用单个符号。
- **C 类型不完整**：源码 `fraggap` 是 unsigned int，模型用无宽度 Int，没有完整建模机器位宽、截断或溢出。

没有在本阶段修复这些问题，没有修改 E01，也未作极性或程序路径证明。E02/E03 仍报告 `semantic_correctness=NOT_ASSESSED`、`polarity_correctness=NOT_ASSESSED`。逻辑相容性未求解，不声称排除了所有公式冲突。

## 7. 历史保护和提交范围

[preservation_check.json](preservation_check.json)：原 4311 个文件中，4310 个不可变文件字节完全一致；唯一授权变动为原累计账本追加四条并更新费用。旧条目、原预算、历史 API 文件、E01/E02/E03/E04、原上游、Prompt、安全 v1、固定数据均未改。

本轮只提交 E04-ND 新目录。实际本机累计账本继续使用原路径；前后完整快照随本目录保存，发布副本的旧根账本不在本次提交范围。后续不能把那个旧副本误当作已计入 E04/本轮费用。

## 8. 十项交付回答

1. 数据集为 codeql_kernel69_nullpointer.json，position=23，index=42，frame=0，函数 __ip6_append_data。
2. 是，真实 U06 生成 3 条新增逻辑断言。
3. 原文及逐条来源见第 4 节；其中 `fraggap != 0` 有直接真分支来源，第一条则有明确字段建模错误，不能把整组 Δ 称为语义正确。
4. B+Δ 完整确定性合并，4 个声明、5 条断言均保留。
5. 是，以真实 HTTP 请求体和客户端消息对照证明，不用本地脚本代替请求。
6. 真实 U10 输出通过未修改的 E02/E03，PASS。
7. 存在字段/指针身份、时间版本、无符号位宽及基础条件弱化风险，详见第 6 节；没有作修复。
8. 生成请求 4 次，另服务 GET 1 次；总 11016 Token；记账费用上界 0.026430 元，实扣账单不可核实。
9. Z3 为 0，模型生成代码执行为 0，U01 为 0，无 FILTER/KEEP/UNKNOWN 安全裁决。
10. 本目录独立提交并推送 main，确切 commit 和完整报告链接由最终交付提供，Git 历史可核查。

本轮非空结构传递目标完成；整组约束语义正确性没有通过验证，并记录了实际缺陷。完成后停止，不进入 E05。
