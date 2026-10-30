# A08：两层参数名映射正确，但模型只看到了两个空指针假设

样本 `NPD/codeql/libav:row=13:index=20`；标签 0（0=误报，1=真实缺陷）；预测 `keep`；状态 `success`。耗时 3.390s，费用估算上界 0.003422 元。

## 1. 原始告警、Source、Sink

radix_sort 第 4 行 tmp=av_malloc(sizeof(*tmp)*size)；未发布精确 Source 或分配失败标注约定。

## 2. 恢复调用链与实际使用代码

radix_sort → radix_sort_pass，最终 Sink dst[pos]=data[i]；原始函数完整保存。

## 3. 实参与形参映射

radix_sort_pass(tmp,data,size,buckets[0],0) 的位置 0→dst，其他位置 data→data、size→size、buckets[0]→buckets、0→pass，检查正确。这不能证明跨过程值约束已经传播。

## 4. 关键条件

callee 实际 target_conditions=[]，漏 for(i=0;i<size;i++)；仅改变内存缩进后原提取器返回该循环。

## 5. LLM 原始输出及解析

457–460 四个请求只做 tmp==0、dst==0 及包装函数，没有把完整源码发给模型。磁盘上存在 context.json 不等于模型看到了代码。

## 6. SMT、Z3 与判定

第一层 tmp==0 SAT，第二层 dst==0 SAT，最后 keep。缺少 size>0 与分配返回值的语义，无法证明真实运行中的缺陷成立。

## 7. 结论与错误类型

确认遗漏循环条件和“无代码语义”的空约束路径。源码对分配失败未显式检查，而标签为误报；是否排除 OOM、size 是否可能为 0，需要原数据标注依据，不能武断改标。

确认类别：关键条件提取错误。

待核实风险：数据或标签错误。

每条公开记录均缺少精确 Source，作为数据完整性问题另行计数，不能等同于已证明标签错误。

最小修复建议（本次未实施）：先恢复循环条件与输入/分配语义边界；未知保留未知。不要仅为了匹配标签添加 tmp!=0，或把 av_malloc 一概当永不失败。

证据：[原始告警](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/samples/A08/original_alert.json)；[运行与调用索引](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/samples/A08/evidence_index.json)；[解析对照](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/samples/A08/parsed_model_outputs.json)；[参数映射](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/samples/A08/argument_parameter_mapping.json)。完整原提示词/输出在 calls/，原始 context、stdout、求解/错误在 recorded_raw/。无此步骤的失败样本明确标记未执行。
