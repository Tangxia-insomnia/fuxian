# A02：真实缺陷标签与局部保护条件冲突，尚不能判定标签还是路径建模有误

样本 `NPD/codeql/kernel69:row=11:index=23`；标签 1（0=误报，1=真实缺陷）；预测 `filter`；状态 `success`。耗时 3.766s，费用估算上界 0.010898 元。

## 1. 原始告警、Source、Sink

与 A01 同函数且 skb 有多次赋值。没有原始 Source/完整 CodeQL codeFlow，无法知道标注指的是哪一版 skb。

## 2. 恢复调用链与实际使用代码

仅 tcp_sendmsg_locked；Sink 为 TCP_SKB_CB(skb)->end_seq += copy。宏体未恢复。

## 3. 实参与形参映射

无跨函数转换，tracked=skb。原告警 function_list=[tcp_write_queue_tail] 是函数提示，并非完整路径。

## 4. 关键条件

目标条件只有 goto new_segment，移除后为空；提前退出条件 !skb 被选中，源码确实存在 if (!skb) goto wait_for_space。

## 5. LLM 原始输出及解析

调用 73–76 依次给出 skb==0、["!(!skb)"]、skb!=0 及合并函数；双重否定翻译本身正确。

## 6. SMT、Z3 与判定

skb==0 ∧ skb!=0，Z3 UNSAT，filter。该保护只在特定分配分支内；当前实现未给不同赋值建立 SSA/路径版本，因此不能凭该式证明所有到达路径均不可能。

## 7. 结论与错误类型

相对标签属于第二条误删，但没有足够证据宣称模型推理错误或标签错误。局部代码看起来有非空保护；需要原始 Source、所有进入路径和宏定义才能裁决。保留原标签和预测。

确认类别：本条未确认具体执行错误。

待核实风险：数据或标签错误、关键条件提取错误。

每条公开记录均缺少精确 Source，作为数据完整性问题另行计数，不能等同于已证明标签错误。

最小修复建议（本次未实施）：先人工核验 Source、变量重赋值与局部保护的支配关系，保留独立 adjudication；未核实前不为追求指标添加或删除约束。

证据：[原始告警](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/samples/A02/original_alert.json)；[运行与调用索引](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/samples/A02/evidence_index.json)；[解析对照](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/samples/A02/parsed_model_outputs.json)；[参数映射](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/samples/A02/argument_parameter_mapping.json)。完整原提示词/输出在 calls/，原始 context、stdout、求解/错误在 recorded_raw/。无此步骤的失败样本明确标记未执行。
