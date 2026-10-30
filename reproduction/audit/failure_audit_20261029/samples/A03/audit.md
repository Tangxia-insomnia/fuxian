# A03：空格缩进丢失 switch/while 条件，枚举关系未编码

样本 `NPD/codeql/libav:row=3:index=8`；标签 0（0=误报，1=真实缺陷）；预测 `keep`；状态 `success`。耗时 4.942s，费用估算上界 0.010112 元。

## 1. 原始告警、Source、Sink

候选为 ChannelElement *che=NULL 和 che=get_che(...)；精确告警 Source 未发布。

## 2. 恢复调用链与实际使用代码

仅 aac_decode_frame_int；Sink 为 decode_ics(ac, &che->ch[0], gb, 0, 0)。相同目标文本在第 55、69 行出现两次；提取器按文本循环选最后一次，没有使用告警源行号消歧。

## 3. 实参与形参映射

在传参前已求值 &che->ch[0]，故终止于本函数的直接成员访问；未进入 decode_ics，无形参映射。

## 4. 关键条件

实际保存 target_conditions=[]；空格缩进仅在内存转为 Tab 后，同一原提取器返回 while(...!=TYPE_END) 和 if(elem_type==TYPE_LFE)。这同时暴露它选中了最后一个同文 Sink。

## 5. LLM 原始输出及解析

调用 419–422 仅保留 che==0 和退出条件的否定；将 TYPE_END、TYPE_DSE 建成无约束 Int，未补回 case 条件。

## 6. SMT、Z3 与判定

che==0 ∧ (elem_type==TYPE_END ∨ elem_type>=TYPE_DSE ∨ che!=0)，SAT，keep。诊断性补入“仍在循环且该 case 小于 TYPE_DSE”后 UNSAT；后一关系须从真实枚举定义核实，本次没有把假设写入原实验。

## 7. 结论与错误类型

确认空格缩进处理错误、目标文本歧义和 SMT 缺少路径/常量关系；这条误报保留有直接可定位的证据。

确认类别：函数代码或调用链恢复错误、关键条件提取错误、SMT约束生成或求解错误。

待核实风险：无额外归因。

每条公开记录均缺少精确 Source，作为数据完整性问题另行计数，不能等同于已证明标签错误。

最小修复建议（本次未实施）：先使条件提取不依赖 Tab，并使用行位置定位同文 Sink；枚举值必须来自固定版本定义，缺失则记录未知，不猜值。

证据：[原始告警](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/samples/A03/original_alert.json)；[运行与调用索引](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/samples/A03/evidence_index.json)；[解析对照](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/samples/A03/parsed_model_outputs.json)；[参数映射](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/samples/A03/argument_parameter_mapping.json)。完整原提示词/输出在 calls/，原始 context、stdout、求解/错误在 recorded_raw/。无此步骤的失败样本明确标记未执行。
