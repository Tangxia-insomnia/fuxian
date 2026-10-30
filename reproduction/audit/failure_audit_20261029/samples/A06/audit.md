# A06：合法 JSON 已返回，但解析器取了前面的 C 代码块

样本 `NPD/infer/openssl:row=4:index=None`；标签 0（0=误报，1=真实缺陷）；预测 `None`；状态 `failed`。耗时 2.528s，费用估算上界 0.006582 元。

## 1. 原始告警、Source、Sink

sc=NULL；在 BIO_CTRL_RESET 分支内由 SSL_CONNECTION_FROM_SSL_ONLY(ssl) 赋值并检查。没有显式 Source 定位。

## 2. 恢复调用链与实际使用代码

仅 ssl_ctrl；Sink 为 if(sc->handshake_func==ssl->method->ssl_connect)，已有完整函数保存。

## 3. 实参与形参映射

本样本无跨函数形参转换；tracked=sc。

## 4. 关键条件

实际 target_conditions=[]，遗漏 cmd==BIO_CTRL_RESET；仅改变内存代码的空格缩进后，原提取器能返回该 case 条件。

## 5. LLM 原始输出及解析

1145 生成 sc==0；1146 输出解释、一个 ```c 块，最后有合法 ```json 数组。适配器正则的 json 标记可省略，误把第一个 C 代码块作为 JSON 解析。

## 6. SMT、Z3 与判定

仅有初始 Z3 片段，尚未形成可执行最终求解脚本；solver_attempts=0，JSONDecodeError，prediction=null。

## 7. 结论与错误类型

确认输出解析缺陷；无需换模型即可定位。全量另外 4 个 JSONDecodeError 也都存在后置合法 JSON 数组，但解析成功不代表内容正确或最终可判定。

确认类别：关键条件提取错误、模型替换或输出格式不兼容。

待核实风险：无额外归因。

每条公开记录均缺少精确 Source，作为数据完整性问题另行计数，不能等同于已证明标签错误。

最小修复建议（本次未实施）：明确只解析 json 标记的代码块并校验 schema；禁止把 C/Python 块当 JSON。先离线回放 5 条响应，不调用模型。

证据：[原始告警](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/samples/A06/original_alert.json)；[运行与调用索引](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/samples/A06/evidence_index.json)；[解析对照](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/samples/A06/parsed_model_outputs.json)；[参数映射](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/samples/A06/argument_parameter_mapping.json)。完整原提示词/输出在 calls/，原始 context、stdout、求解/错误在 recorded_raw/。无此步骤的失败样本明确标记未执行。
