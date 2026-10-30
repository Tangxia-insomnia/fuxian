# A05：并非形参位置映射错，而是 !sta 条件被复合实参规则阻塞

样本 `NPD/codeql/kernel69:row=55:index=81`；标签 0（0=误报，1=真实缺陷）；预测 `None`；状态 `blocked_context`。耗时 0.008s，费用估算上界 0.000000 元。

## 1. 原始告警、Source、Sink

候选 sta=sta_info_get(sdata,dst)，调用前有 if(!WARN_ON(!sta))；无精确扫描 Source。

## 2. 恢复调用链与实际使用代码

历史候选为 ieee80211_mgd_probe_ap_send → ieee80211_check_fast_rx。原运行在预检查阶段阻塞，没有持久化实际 context，也没有模型调用；审计候选文件明确命名 NOT_EXECUTED。

## 3. 实参与形参映射

sta→sta 的离线位置映射成功。repo.prepare 可恢复该转换；engine.prepare 随后对 if(!WARN_ON(!sta)) 调 called_function，因 WARN_ON 参数为 !sta 而非 sta，抛出 unsupported compound argument。

## 4. 关键条件

离线复查得到 if(dst) 与 if(!WARN_ON(!sta))。这是原提取器结果的审计重放，未冒充原运行已保存的条件。

## 5. LLM 原始输出及解析

未执行；调用数 0。

## 6. SMT、Z3 与判定

未生成 SMT，也未执行 Z3；prediction=null，blocked_context。

## 7. 结论与错误类型

确认上下文支持边界与条件中的函数识别规则造成阻塞；没有发现这条样本实参与形参位置映射错误。

确认类别：函数代码或调用链恢复错误。

待核实风险：无额外归因。

每条公开记录均缺少精确 Source，作为数据完整性问题另行计数，不能等同于已证明标签错误。

最小修复建议（本次未实施）：先区分“布尔条件包装中的变量”与“跨函数实际传递的指针”；针对已知宏做有证据的语义处理，不能简单将 !sta 当成 sta，也不放开所有复合表达式。

证据：[原始告警](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/samples/A05/original_alert.json)；[运行与调用索引](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/samples/A05/evidence_index.json)；[解析对照](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/samples/A05/parsed_model_outputs.json)；[参数映射](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/samples/A05/argument_parameter_mapping.json)。完整原提示词/输出在 calls/，原始 context、stdout、求解/错误在 recorded_raw/。无此步骤的失败样本明确标记未执行。
