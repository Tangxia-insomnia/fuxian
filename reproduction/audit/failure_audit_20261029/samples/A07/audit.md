# A07：长条件列表的 SMT 输出在 3072 token 上限处截断

样本 `NPD/codeql/openssl:row=41:index=43`；标签 0（0=误报，1=真实缺陷）；预测 `None`；状态 `failed`。耗时 17.797s，费用估算上界 0.063226 元。

## 1. 原始告警、Source、Sink

req_main 中 req 初始化及 load_csr/构造等赋值候选均见原函数；没有原始扫描 Source 与完整 codeFlow。

## 2. 恢复调用链与实际使用代码

预恢复 req_main → X509_REQ_print_ex → X509_REQ_get_X509_PUBKEY，最终 Sink return req->req_info.pubkey；实际模型调用只到 frame 0，后两帧没有实际分析。

## 3. 实参与形参映射

预检查 req→x（位置 1），x→req（位置 0），词法检查均与保存 frame 一致；不能把“准备成功”写成“跨三层实际执行成功”。

## 4. 关键条件

frame 0 的目标条件为空；提前退出列表很长，838 保留大量与 req 关系不明确的条件，带来后续长解释。未对其正确性做完整人工证明。

## 5. LLM 原始输出及解析

837 初始 req==0；838 输出 JSON 列表；839 逐项解释/生成 SMT，finish_reason=length，completion_tokens 达 3072，文本在注释中间截断。

## 6. SMT、Z3 与判定

只有不完整生成文本，无最终 solver 文件、无 Z3 查询、无最终判定；保留 failed/null，未用截断内容继续求解。

## 7. 结论与错误类型

确认输出预算/格式不兼容；空格缩进遗漏分支是另一个已知上游问题，但不能据此断言修缩进必然解决截断。

确认类别：关键条件提取错误、模型替换或输出格式不兼容。

待核实风险：无额外归因。

每条公开记录均缺少精确 Source，作为数据完整性问题另行计数，不能等同于已证明标签错误。

最小修复建议（本次未实施）：先修条件提取与筛选，再让转换步骤只返回所需脚本；单独比较输出上限/格式，不在原基线覆盖重试，也不默认增大所有请求。

证据：[原始告警](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/samples/A07/original_alert.json)；[运行与调用索引](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/samples/A07/evidence_index.json)；[解析对照](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/samples/A07/parsed_model_outputs.json)；[参数映射](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/samples/A07/argument_parameter_mapping.json)。完整原提示词/输出在 calls/，原始 context、stdout、求解/错误在 recorded_raw/。无此步骤的失败样本明确标记未执行。
