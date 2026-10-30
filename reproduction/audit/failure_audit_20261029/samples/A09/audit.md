# A09：真实缺陷保留对照：求解与最终映射一致，但仍是近似可行

样本 `NPD/codeql/kernel69:row=34:index=55`；标签 1（0=误报，1=真实缺陷）；预测 `keep`；状态 `success`。耗时 8.634s，费用估算上界 0.021550 元。

## 1. 原始告警、Source、Sink

idev 初始 NULL，后有 in6_dev_get 和 ip6_validate_gw 等更新；没有精确 Source 定位，函数代码可见。

## 2. 恢复调用链与实际使用代码

仅 fib6_nh_init；Sink if(idev->cnf.disable_ipv6)。

## 3. 实参与形参映射

无跨函数调用链转换。条件中的函数以未解释函数/整数近似，不等于实际分析过其函数体。

## 4. 关键条件

目标外层条件为空；提取多个 goto out 等约束，过滤后保留两条含 idev 的复合条件。

## 5. LLM 原始输出及解析

最终尝试调用 49–54；两次生成的 __import__ 被受限 worker 拒绝，最后使用标准 Int/Or 约束。早期失败尝试的调用 20–26 单独列出，未混入最终证据。

## 6. SMT、Z3 与判定

idev==0 加两个析取约束可满足，最终 SAT→keep，与原 label=1 一致。该结果只验证近似模型可行，不证明完整源码语义。

## 7. 结论与错误类型

未发现最终保留/过滤映射错误；这是成功对照。修复重试曾改变未解释函数的建模方式，说明“能执行”检查未保证语义保持，列作风险。

确认类别：本条未确认具体执行错误。

待核实风险：SMT约束生成或求解错误。

每条公开记录均缺少精确 Source，作为数据完整性问题另行计数，不能等同于已证明标签错误。

最小修复建议（本次未实施）：把该样本纳入回归集，修类型与符号身份时核对约束是否保持；不要把所有 SAT 宣称为真实缺陷证明。

证据：[原始告警](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/samples/A09/original_alert.json)；[运行与调用索引](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/samples/A09/evidence_index.json)；[解析对照](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/samples/A09/parsed_model_outputs.json)；[参数映射](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/samples/A09/argument_parameter_mapping.json)。完整原提示词/输出在 calls/，原始 context、stdout、求解/错误在 recorded_raw/。无此步骤的失败样本明确标记未执行。
