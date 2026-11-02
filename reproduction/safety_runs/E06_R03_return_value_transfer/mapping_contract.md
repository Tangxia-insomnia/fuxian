# R03 接口与记录合同（实现前确定）

入口 `return_transfer.analyze(path, dataset_id, position, build_status, caller, candidate_source_paths=())`。数据身份只命名证据，不参与算法特判。源字节由 R01 parse 固定并校验第二次 R01 解析哈希；不执行 C。`verify_proposal(report, proposal)` 检查明确关系候选，不修正候选。

- **CallContextRecord**：dataset_id、position、caller/callee 声明身份、两端 body SHA、source SHA、callsite、caller path、caller pre 环境、R01 参数 transfer 与 callee 实例入口版本；哈希为 call_context_id。每次调用独立，禁止摘要缓存。
- **ReturnValueRecord**：上述调用/数据身份、callee path、return event/位置/原式、Clang 返回类型、类别、来源 slot/当前版本、guard、状态/缺口、literal 源类型/位宽/符号性/范围。return_value_id 绑定调用实例及返回事件。
- **PathReturnRecord**：callee path、guard、return event/value、正常返回、caller 是否可续行、路径覆盖状态；非 void 落出或阻断路径必须 UNKNOWN，不能选一条已验证路径冒充全部。
- **ReturnTransferRecord**：caller pre version(s)、argument transfer(s)、callee entry version(s)、return value、接收 slot/新版本、caller post path、是否接收/忽略/void、类型证据、效果/路径完整性、body/source SHA 和逐段证据链。忽略返回值及 void 不产生 result version。

caller 的源 slot、callee 的参数 slot、caller 的接收 slot 三者独立。按值形参更新只更新 callee 实例环境。复制关系保留旧版本；接收后再赋值创建后续版本。多个 return 路径对应多个 caller post version，无 phi，不向 caller guard 注入 callee 条件。

六项指标分别记录：argument_entry、return_binding、caller_result、call_effect_coverage、return_path_completeness、complete_call。PASS 不向安全策略传递授权。N/A 表示该项不适用；UNKNOWN 不计成功。REJECT 用于与已验证证据明确冲突的候选版本/上下文/类型/路径集合；缺证据 UNKNOWN，禁止用 recovery AST 作否定证明。

历史源码可以有 literal_source_locator_only 的 return/call 原文记录，但类型、版本、guard 语义和完整效果仍 UNKNOWN；不会为其创建已验证 ReturnTransferRecord。旧诊断保留哈希引用，明确未重算旧极性或 B/Δ。
