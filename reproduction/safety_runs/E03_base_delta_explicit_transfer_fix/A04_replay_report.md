# A04：指定缓存输入替换与输出检查

样本：`NPD/codeql/kernel69:row=12:index=24`，position=12，frame=1。本轮没有针对样本 ID 修改通用适配器；重放脚本中的案例选择仅用于本次指定验证。

## 来源

只读使用 E02 `evidence/audit_10_frozen_candidate/04/calls/`；每个调用的字节哈希同时匹配 E02 `hashes.json` 与 E03 `baseline_state.json`，并核对 sample_id、call_id、finish_reason。副本与确切哈希见 [merge_audit.json](merge_audit.json) 的 A04 `source_files`：

| 调用 | 功能 | 本轮副本 |
| --- | --- | --- |
| 0231 | U02，基础 B | [0231.json](evidence/A04/calls/0231.json) |
| 0233 | U06，新增 Δ | [0233.json](evidence/A04/calls/0233.json) |
| 0234 | U10，旧输入/旧输出 | [0234.json](evidence/A04/calls/0234.json) |
| 0235 | 旧 U01 修复 | [0235.json](evidence/A04/calls/0235.json) |
| 0238 | 旧 U09 | [0238.json](evidence/A04/calls/0238.json) |

B 原始响应 SHA-256：`7a65b85e641f0e71c426ddf299c6035838044ca765eade808e1d6e3bdcfd8d92`。

Δ 原始响应 SHA-256：`e00b45ed26f4306974524ede46cd8ad9ae95d7c03d390cec6d3175ed7c4894c1`。

新合并脚本 SHA-256：`ea4a29df384dd5ca27a8a0c09466cab7fdee0509c4f5aee443141f224d042120`。

## 输入与输出分开报告

| 对象 | 静态状态 | 证据及准入 |
| --- | --- | --- |
| 旧 U10 实际收到的输入 | FAIL | 解码后等于 Δ；缺 B 的 2 个声明和 2 个断言 |
| 新适配器合并后的 U10 参数 | PASS | 完整保留 B+Δ；离线观察器收到同一载荷 |
| 旧 U10 生成输出 | UNKNOWN | `python_expression_outside_subset:List`；拒绝进入后续求解 |
| 旧 U01 输出 | FAIL | 缺 2 个基础声明、2 个基础断言；2 个符号身份缺口 |
| 旧 U09 输出与其显式全输入对照 | FAIL | B 断言缺失为 0，但新增集合缺 1 条断言、缺 1 个声明、1 个身份冲突、1 个类型冲突 |

B 包含 `folio_test_slab`、`object` 两个 Int 声明及各自等于 0 的断言；Δ 是本次历史响应实际返回的无新增断言内容，没有据此凭空补出约束。新载荷保留 B，因此修复了“空新增内容导致基础约束消失”的输入缺陷。

原 U10 旧输出、实际交给检查器的解码文本、拒绝原因、旧 U01/U09 的完整检查均在 [postcondition_audit.json](postcondition_audit.json)。旧 U01 的 `object_ptr` 等符号不能冒充原 `object` 的已验证身份；本轮不自动改名。

U09 观察只使用其已保存的两个额外约束集合进行静态对照，未改 U07/U09 分支，未执行历史代码。不能因 U09 恢复了部分 B 就证明全流程传递正确。

## 验收结论与边界

本案例按预期发现旧输入丢失，并验证新输入保留、旧不支持输出被阻断。没有获得基于新载荷生成的真实 U10 响应，也没有运行 Z3；因此没有证明真实模型输出可通过或端到端缺陷分析已恢复。语义及极性均 `NOT_ASSESSED`，不产生安全裁决。
