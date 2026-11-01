# E02 历史证据静态重放报告

日期：2026-11-02。这里的“重放”仅指重新读取既存输入/输出并进行静态成员检查；**没有执行历史 Python、没有运行 Z3、没有调用模型，也没有作告警安全裁决**。

## 1. 证据绑定与检查口径

以原固定 10 条清单中的 `final_attempt_call_ids`、安全 v1 已冻结的 evidence bundle 和 evidence_bindings 为起点。核对 bundle 哈希、各原始 artifact 哈希、sample_id、最后一次尝试的 API 次数和调用 ID；审计样本的调用副本还与全局调用记录逐 JSON 比较。固定 20 条同样使用冻结 bundle/原始 sample_result 的最终尝试记录，未重新抽样。

所有读取的响应、solver 记录以及传给检查器的 B/Δ/Final 均复制到 [evidence/](evidence/)。`audit_10_results.json` 和 `fixed_20_results.json` 的 `source_provenance`、`call_selection`、逐阶段 `input_path`/SHA-256、输入 IR 与输出诊断组成追踪链。额外核对历史 solver source 与所选调用响应：审计集 13 份、固定回归集 30 份均匹配。只是匹配保存的代码文本，未运行它们。

原始代码的 `if (!copied)` 等 C 条件不由 E02 解释。E02 的断言标识为 SMT 结构化表达式，身份为字面 SMT symbol + sort；代码行号是历史响应代码块中的行，不是 C 文件绝对行。

## 2. A04：U06 → U10 丢失确实被发现

样本 `NPD/codeql/kernel69:row=12:index=24`，帧 1 的基础片段来自调用 0231：

```python
folio_test_slab=Int('folio_test_slab')
object=Int('object')
s.add(folio_test_slab == 0)
s.add(object == 0)
```

证据副本：[0231.json](evidence/audit_10_frozen_candidate/04/calls/0231.json)、[0233.json](evidence/audit_10_frozen_candidate/04/calls/0233.json)、[0234.json](evidence/audit_10_frozen_candidate/04/calls/0234.json)、[0235.json](evidence/audit_10_frozen_candidate/04/calls/0235.json)、[0238.json](evidence/audit_10_frozen_candidate/04/calls/0238.json)。逐阶段结果见 [audit_10_results.json](audit_10_results.json) 中 `rows[3].stages`，从零开始索引。

| 阶段 | 静态检查结果 | 具体证据 |
| --- | --- | --- |
| U06 输出 Δ | 只有注释，没有新增声明/断言 | 0233 的 `/choices/0/message/content`；空增量是实际输出，非伪造补齐 |
| U10 实际接收输入 | **FAIL**：基础断言缺 2 条、声明缺 2 项 | stage 3 / call 234；prompt 的 `Input Z3 script` 与 Δ 原文匹配，不含 B |
| U10 输出 | **UNKNOWN / UNSUPPORTED** | stage 4；含 Python 列表/循环及常量 `object_ptr=0`，超出支持子集，不擅自执行或伪造 IR |
| U01 修复相对于原 B+Δ | **FAIL**：基础断言缺 2 条、声明缺 2 项，身份映射缺口 2 项 | stage 5 / call 235；仅有 `object_ptr`，缺 `object`、`folio_test_slab` |
| 修复前后直接比较探针 | UNKNOWN | stage 6；前一版本不可可靠解析，不能宣称证明了完整前后语义差异 |
| U09 全部输入与输出 | **FAIL**：基础断言成员恢复，但新增断言缺 1 条、声明缺 1 项、类型冲突 1 项、身份缺口 1 项 | stage 7 / call 238；G 中 `object` 是 BitVec:64，B 中是 Int；Final 将 G 的符号改成 `object_bv` |
| U09 仅基础成员诊断探针 | 基础断言/声明缺失数均为 0；整体仍 UNKNOWN | stage 8；输出另有未纳入该探针的断言。这个窄探针不参与全链状态汇总 |

身份缺口的严格含义：要求保留的符号消失，同时出现新的候选替代符号，记录中没有可靠映射。检查器**没有推断** `object_ptr` 就是 `object`，也不宣称 `folio_test_slab` 与它存在别名关系。2 项是缺失符号的诊断计数，不是证明了两个 C 对象被重命名。

U09 的完整比较显式纳入 B、原 Δ、前次修复输出和 U07 输出 G，避免只看 B 被恢复就批准整条传递。其结构化缺失增量是 `(distinct object (_ bv0 64))`；Final 中是另一符号 `object_bv`。存在语法结构和 sort 冲突，不需要运行求解器就可拒绝“完整保留”的声明。

## 3. A01：保留完整性与极性严格分开

样本 `NPD/codeql/kernel69:row=10:index=22`。证据副本：[0224.json](evidence/audit_10_frozen_candidate/01/calls/0224.json)、[0226.json](evidence/audit_10_frozen_candidate/01/calls/0226.json)、[0227.json](evidence/audit_10_frozen_candidate/01/calls/0227.json)。

U02 的 B 含 `Not(copied == 0)`、`skb == 0`；U06 的 Δ 加 `copied == 0`。

- U10 输入传递：**FAIL**，只收到 Δ，缺 B 的 2 条断言和 2 项声明。
- U10 输出：**静态保留 PASS**，模型输出中重新出现 B 和 Δ 的全部结构成员。
- 极性与 C 语义：**NOT_ASSESSED**。历史 E01 已报告 `if (!copied)` 真分支与 `Not(copied == 0)` 冲突；E02 不重新运行、不修改 E01，也不将该最终脚本标成安全。
- 全链静态状态：FAIL，因为一个已核实的传递缺口不会被后续“猜回旧约束”抹去。

没有删除 `Not(copied == 0)` 或 `copied == 0`，没有为获得 SAT 调整任何输入。合成 T26 也专门验证：矛盾公式可以通过**保留契约**，但语义状态必须始终是 NOT_ASSESSED。

## 4. 10 条调试集逐条结果

| 审计 ID | 静态全链状态 | 说明 |
| --- | --- | --- |
| A01 | FAIL | U10 接收内容丢 B；最终结构保留通过，不代表极性正确 |
| A02 | PASS | 显式 U09 全输入成员保留；未评估 Source/赋值或缺陷语义 |
| A03 | UNKNOWN | 增量中存在不支持的 Python 表达式/接收器关系 |
| A04 | FAIL | 输入丢 B、修复身份缺口、U09 类型与身份冲突 |
| A05 | NOT_APPLICABLE | 没有模型调用，不存在可检查的 B/Δ/Final 转换 |
| A06 | UNKNOWN | 有部分历史调用，但没有完整转换证据 |
| A07 | UNKNOWN | 调用输出中止，未形成完整可检查转换 |
| A08 | PASS | 两个帧的 base-only 路径保留；仅检查结构 |
| A09 | UNKNOWN | 范围/修复代码含当前子集不支持的构造 |
| A10 | PASS | 显式 U09 约束成员保留；宏语义和独立复核仍未由 E02 证明 |

上述 PASS 不是安全通过，不改变任何历史告警处理或安全 v1 状态。特别是 A10 只证明保存公式的成员传递，不回答原宏构建/展开证据问题。

## 5. 冻结后回归集观察

固定第 1 条 `NPD/codeql/openssl:row=30:index=31` 在 call 781 的 U09 输入/输出间出现 `bs` 的 Bool/Int 冲突；固定第 17 条 `NPD/codeql/kernel69:row=24:index=43` 在 call 275 的 U10 输入丢 2 条基础断言，输出还缺 2 条增量断言并引入不同符号。它们都由通用逻辑检出，检查器没有样本 ID 分支。

其他 UNKNOWN 包括未绑定名称、复杂函数调用、普通 If 控制流、域外 symbol 拼写、返回协议或代码块外文本。冻结后未扩大语法支持、未调整任何代码、未重跑该回归集。这些限制记录在 [metrics.json](metrics.json) 的 `unsupported_parse_error_occurrences`。
