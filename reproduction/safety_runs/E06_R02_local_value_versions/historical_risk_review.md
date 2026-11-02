# R02 历史风险只读检查

这不是历史模型实验重跑。输入原文、source body 哈希、逐帧 libclang 诊断、新 R02 UNKNOWN 结果及旧报告哈希分别存于 `historical/` 和 `historical_results.json`。`historical_cases.json` 是输入清单及文本位置，不包含按 ID 改变算法的分支。行号均为**保存函数体内的一基行号**，不是工程文件绝对行。

| 历史输入 | 本次已核实的文本事实 | 不能证明的关系 | 新检查 |
| --- | --- | --- | --- |
| E04-ND `NPD/codeql/kernel69:row=23:index=42`，`__ip6_append_data` | 175–178 读取 `skb->len`；180–183 传 `&maxfraglen`；185 `skb_prev = skb`；239–250 重新赋值 skb；275–276 同时使用 skb_prev、skb | 原 TU、成员类型、宏、循环路径和调用效果缺失，不能批准旧复制值到目标的 reaching definition | UNKNOWN |
| A01 `NPD/codeql/kernel69:row=10:index=22`，`tcp_sendmsg_locked` | copied 初始化第 7 行、调用赋值第 64 行、第 88 行重置、第 241 行 `+=`；234–235 真分支目标 | 无原构建/宏与循环模型，不给所有 copied 使用同一时间版本；不重算或删除 E01 极性结论 | UNKNOWN |
| A04 `NPD/codeql/kernel69:row=12:index=24`，`tcp_set_allowed_congestion_control -> kfree` | 第 7 行链式初始化，第 13 行 `strsep(&clone,...)`，第 34 行 `kfree(saved_clone)`；callee 第 1 行 object 参数，第 10 行宏早退 | 不能证明克隆副作用、跨函数内存对象与历史 object/object_ptr/object_bv 的符号对应；不改 B/Δ | UNKNOWN |

## 精确来源

- E04-ND：`../E04_nonempty_delta_validation/sample_manifest.json#/frames/0`，与 `selected_source.c` 字节相等，body SHA-256 `4f652c2800b05d4fab8cf926af60a66c348cbdd8e5cc95f2620555feaf1e20a9`。
- A01：`../E02_base_constraint_preservation_static/evidence/audit_10_frozen_candidate/01/bundle.json#/context/frames/0`，body `0a179a0178f81a9211efd84d9baa3efce16afafb9dd8dbe54c47eb63e5064590`。
- A04 caller：同证据目录 `04/bundle.json#/context/frames/0`，body `58e06fa2a7bd4630d7cdeab57321ea5d34830a23a0c66231a42cbefe13a77033`；callee `/frames/1`，body `ce574246eb0cddd842776be658e862604e577e5dee1c5fc3333b9b4f32dccd39`。

## 原诊断保留，不冒充新验证

- E01 `e01_report.md:7`：A01 真分支与 `Not(copied == 0)` 冲突。E05 `E05_report.md:67` 同样记录该风险。
- E02 `historical_replay_report.md:31–38`：A04 原符号缺失/替代候选、Int/BitVec 类型冲突和增量丢失；E03 `A04_replay_report.md:35` 保留拒绝结果；E05 `E05_report.md:82` 明确不假定三个名称是已证明的同一对象。
- E04-ND `E04_ND_report.md:109`：时间版本未区分；E05 `E05_report.md:89–93`：成员替代诊断与状态传播不足并存。

上述为带哈希的缓存历史诊断，不是本次重新运行 E01–E05。新 R02 在构建门槛即停止可信追踪，3 样本/4 帧均 UNKNOWN、0 个已验证版本/读取。文本 locator 不当作 AST 语义证明。没有修改模型响应、变量名称、断言或历史结果。
