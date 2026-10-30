# A04：正确恢复 kfree 调用，但同一指针被拆成三个独立变量

样本 `NPD/codeql/kernel69:row=12:index=24`；标签 0（0=误报，1=真实缺陷）；预测 `keep`；状态 `success`。耗时 11.912s，费用估算上界 0.020672 元。

## 1. 原始告警、Source、Sink

源码第 7 行 saved_clone=clone=kstrdup(val,GFP_USER)，第 8–9 行 !clone 返回；这是真实可见候选，不等于已恢复精确扫描 Source。

## 2. 恢复调用链与实际使用代码

tcp_set_allowed_congestion_control → kfree；最终历史边界为 free_large_kmalloc(folio,(void*)object)，未继续进入其实现。实际代码中 kfree 对 ZERO_OR_NULL_PTR(object) 先返回。

## 3. 实参与形参映射

kfree(saved_clone) 的第 0 个实参→形参 object；保存 frame 与离线词法映射一致。位置映射没有错；saved_clone=clone 的值关系没有被约束化。

## 4. 关键条件

caller 的 goto out 被移除，模型过滤提前退出约束得到 []；callee 提取 if(unlikely(!folio_test_slab(folio)))，另有 ZERO_OR_NULL_PTR 提前返回。

## 5. LLM 原始输出及解析

调用 234 甚至生成未实际求解的布尔程序，被 worker 拒绝；235 修到可执行。238 最终把 object:Int、object_ptr:Int、object_bv:BitVec64 作为独立符号。

## 6. SMT、Z3 与判定

最终 object==0、object_ptr==0、object_bv!=0 可同时成立，所以 SAT→keep。离线只连接同一指针的三个表示就得到 UNSAT。Z3 原结果正确，编码身份关系错误。

## 7. 结论与错误类型

确认变量身份/类型合并错误；模型文字已说空指针会提前返回，后续脚本却没有表达“到达 Sink”的要求。caller 的别名非空关系也是缺失项。

确认类别：LLM变量状态推理错误、SMT约束生成或求解错误。

待核实风险：无额外归因。

每条公开记录均缺少精确 Source，作为数据完整性问题另行计数，不能等同于已证明标签错误。

最小修复建议（本次未实施）：为每个 C 实体固定一个符号与类型；禁止修复/合并时自由改名为独立变量；检查原约束与变量身份是否保持。

证据：[原始告警](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/samples/A04/original_alert.json)；[运行与调用索引](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/samples/A04/evidence_index.json)；[解析对照](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/samples/A04/parsed_model_outputs.json)；[参数映射](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/samples/A04/argument_parameter_mapping.json)。完整原提示词/输出在 calls/，原始 context、stdout、求解/错误在 recorded_raw/。无此步骤的失败样本明确标记未执行。
