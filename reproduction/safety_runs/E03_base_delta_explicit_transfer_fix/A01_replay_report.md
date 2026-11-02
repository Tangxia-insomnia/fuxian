# A01：结构完整性与极性风险对照

样本：`NPD/codeql/kernel69:row=10:index=22`，position=10，frame=0。本轮仅选择此案例核验缓存；适配器没有样本 ID 特判。

来源：E02 `evidence/audit_10_frozen_candidate/01/calls/`。U02=[0224](evidence/A01/calls/0224.json)、U06=[0226](evidence/A01/calls/0226.json)、旧 U10=[0227](evidence/A01/calls/0227.json)。副本逐字匹配 E02 哈希清单和 E03 基线，调用身份核验通过。

- B 原始 SHA-256：`40ac6b25a23bc603368628b14fe3a48818c278f2b2e5f8da96d19cfa8dfb8f7f`。
- Δ 原始 SHA-256：`f26bf12e1f1e4a820f65a2c2f3704ced7063d7051c223e52ebdea1fd6e9f0182`。
- 新合并脚本 SHA-256：`3c2ea5b0bd2a3991f822db296b4ddc8d51fd0bbc0bb3d22b72b5f64f1eec0898`。

| 对象 | 结果 |
| --- | --- |
| 旧 U10 输入 | 等于 Δ；FAIL，缺 2 个基础声明和 2 个基础断言 |
| 新 U10 参数 | PASS，完整保留 B 和 Δ；仅离线参数观察 |
| 缓存旧 U10 输出 | 结构 PASS，符合后续阶段的结构准入；未实际求解 |
| 语义正确性 | NOT_ASSESSED |
| 条件极性正确性 | NOT_ASSESSED |

B 的 `Not(copied == 0)`、`skb == 0` 与 Δ 的 `copied == 0` 均保留，原始代码没有删除或取反。相反条件在结构上可以同时完整出现；E03 不证明它们忠实表达 `if (!copied)` 的真实分支语义，不以结构 PASS 批准过滤。

本案例验证“保留错误的 B 仍可能通过结构检查”的边界，而不是修复极性。E01、真实缺陷优先安全 v1 及原始数据均未修改。本轮未运行 E01，也没有生成新的安全裁决。

完整原文、提取 IR、合并区间、哈希和检查结果见 [merge_audit.json](merge_audit.json)、[postcondition_audit.json](postcondition_audit.json)。旧 U10 输出是原旧输入的缓存响应，不是新 B+Δ 的实际模型响应。
