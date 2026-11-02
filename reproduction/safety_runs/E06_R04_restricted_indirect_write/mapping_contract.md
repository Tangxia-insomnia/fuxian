# R04 证据接口合同

`indirect_write.analyze(path, dataset_id, position, build_status, caller, candidate_source_paths=())` 返回独立确定性证据。输入身份只命名证据，不作样本规则。源快照与 R01 二次解析 SHA 必须一致。缺原始构建的历史片段一律 UNKNOWN，不创建已验证对象/指针/写入版本。

- MemoryObjectRecord：数据位置、对象 ID、所属函数、声明身份/范围、类型/作用域/body SHA、自动存储与受控路径无先前逃逸依据、状态/缺口。对象与指针 slot 分离。
- AddressEvidence：直接取址 AST、引用声明、caller slot/当前值版本、目标对象、精确范围和地址类型；无全局名称推测。
- PointerTargetRecord：callee 实例 slot/入口值版本、地址证据、对象、context、caller path、转换、唯一性与源码依据。入口关系仅绑定该实例入口指针值；形参后续重绑不继承目标。
- MemoryVersionRecord：对象、独立版本 ID/前驱、caller 值版本、实际 write event、值/类型/context/path/源码/body SHA、状态。初始快照不是写入，明确单列。所有旧版本保留。
- IndirectWriteRecord：caller pre、对象、指针声明/入口及写入点当前版本、原式、定型 literal/转换、callee body/context、写入事件、caller post/内存版本及效果覆盖状态。局部写入 PASS 不等于完整调用 PASS。
- EffectTransferRecord：CallerPre→AddressEvidence→ArgumentTransfer→PointerEntry→IndirectWrite→CallerPost 的 ID 链、前后值/内存环境、完整效果/正常返回/唯一目标/逃逸状态，未支持时不提交后状态。

`verify_proposal` 检查候选对象、指针/值/内存版本、调用上下文、地址及 write/no-write 声明。可靠引用冲突 REJECT；未知程序语义仍 UNKNOWN。若已验证的直线前缀存在局部写入而候选否认该写入，可 REJECT 这项具体否定声明，即使完整调用效果 UNKNOWN；不能借此批准其他关系。仅有未验证或不可达的写入语法库存不能触发此项否定。缺字段 UNKNOWN。

各项地址、入口、唯一目标、局部写、caller 新版本、逃逸覆盖、未知效果阻断、隔离与完整调用分别统计 PASS/REJECT/UNKNOWN/N/A，明确单位。UNKNOWN 不计成功；N/A 只表示无对应请求，例如已证只有局部重绑时没有 caller 新写版本。无原约束/SMT改名、弱化或导出。
