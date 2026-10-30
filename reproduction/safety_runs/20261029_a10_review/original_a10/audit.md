# A10：误报正确过滤对照：提前返回和空指针假设构成矛盾

样本 `NPD/codeql/kernel69:row=65:index=95`；标签 0（0=误报，1=真实缺陷）；预测 `filter`；状态 `success`。耗时 6.103s，费用估算上界 0.009494 元。

## 1. 原始告警、Source、Sink

sta=sta_info_get(sdata,peer)，精确扫描 Source 仍缺；有明确可见保护。

## 2. 恢复调用链与实际使用代码

仅 ieee80211_tdls_add_setup_cfm_ies；Sink sta->tdls_chandef=link->conf->chanreq.oper。

## 3. 实参与形参映射

无跨函数转换，tracked=sta。

## 4. 关键条件

目标条件为空；提前退出含 WARN_ON_ONCE(!sta || !ap_sta)，源码保护位于 Sink 之前。

## 5. LLM 原始输出及解析

最终调用 59–62，得到 ["!(WARN_ON_ONCE(!sta || !ap_sta))"]，按宏返回条件值语义转为 Not(Or(sta==0,ap_sta==0))。先前失败尝试调用 34–40 单独留档。

## 6. SMT、Z3 与判定

sta==0 ∧ Not(sta==0 ∨ ap_sta==0)，UNSAT→filter，与 label=0 一致；此局部保护与该成员访问相对应。

## 7. 结论与错误类型

正确过滤对照，未发现最终逻辑/指标问题。宏定义未从整工程展开，因此仍应在报告中保留语义假设。

确认类别：本条未确认具体执行错误。

待核实风险：无额外归因。

每条公开记录均缺少精确 Source，作为数据完整性问题另行计数，不能等同于已证明标签错误。

最小修复建议（本次未实施）：保留为最小回归样本，后续修复不能破坏这条已经正确的判定。

证据：[原始告警](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/samples/A10/original_alert.json)；[运行与调用索引](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/samples/A10/evidence_index.json)；[解析对照](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/samples/A10/parsed_model_outputs.json)；[参数映射](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/samples/A10/argument_parameter_mapping.json)。完整原提示词/输出在 calls/，原始 context、stdout、求解/错误在 recorded_raw/。无此步骤的失败样本明确标记未执行。
