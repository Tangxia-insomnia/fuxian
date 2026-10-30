# A01：条件极性翻转导致伪造矛盾，真实缺陷标签样本被过滤

样本 `NPD/codeql/kernel69:row=10:index=22`；标签 1（0=误报，1=真实缺陷）；预测 `filter`；状态 `success`。耗时 4.622s，费用估算上界 0.018030 元。

## 1. 原始告警、Source、Sink

公开行没有精确 Source。代码候选为 tcp_write_queue_tail(sk)（函数内第 21/100 行）和 tcp_stream_alloc_skb（117 行）；不能将其中任意一处冒充已恢复的原始 Source。

## 2. 恢复调用链与实际使用代码

仅 tcp_sendmsg_locked；Sink 为 TCP_SKB_CB(skb)->tcp_flags &= ~TCPHDR_PSH。宏体未展开，边界来自作者历史数据。

## 3. 实参与形参映射

无跨函数实参→形参转换；tracked=skb。宏 TCP_SKB_CB 的内部参数语义未验证。

## 4. 关键条件

保存条件为 goto new_segment 和 if (!copied)，前者被原有适配逻辑移除。实际要求执行该分支时 copied==0。

## 5. LLM 原始输出及解析

调用 224 却生成 Not(copied==0)，调用 225 正确生成 copied==0；调用 226/227 按“保留全部已有约束”把两者并存。不是 Z3 自己制造矛盾。

## 6. SMT、Z3 与判定

最终断言 copied!=0 ∧ skb==0 ∧ copied==0，Z3 UNSAT，result=False→filter。离线仅纠正极性后公式 SAT；这只证明原 UNSAT 不能作为过滤证据，不能证明完整 C 路径可行。

## 7. 结论与错误类型

确认 SMT 条件翻译和合并错误；相对原标签为误删。该标签与 A02 同函数的局部非空检查仍有审查空间，未在本次改标。

确认类别：LLM变量状态推理错误、SMT约束生成或求解错误。

待核实风险：数据或标签错误。

每条公开记录均缺少精确 Source，作为数据完整性问题另行计数，不能等同于已证明标签错误。

最小修复建议（本次未实施）：统一条件极性与符号表；已有约束和新增约束冲突时追溯代码来源，不能把生成器自相矛盾直接作为不可达证据。先修此样本级错误，不改真实标签。

证据：[原始告警](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/samples/A01/original_alert.json)；[运行与调用索引](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/samples/A01/evidence_index.json)；[解析对照](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/samples/A01/parsed_model_outputs.json)；[参数映射](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/samples/A01/argument_parameter_mapping.json)。完整原提示词/输出在 calls/，原始 context、stdout、求解/错误在 recorded_raw/。无此步骤的失败样本明确标记未执行。
