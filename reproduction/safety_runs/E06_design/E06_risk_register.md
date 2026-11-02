# E06 技术风险与 UNKNOWN 边界

下列为设计风险登记，不是已实现的自动检测能力。优先保护真实缺陷；“短期放弃自动判断”表示保留告警及缺口，仍可做人工审查或源码检索。

| 风险 | 现有证据/触发条件 | 可能的错误后果 | 建议处理及解除条件 |
| --- | --- | --- | --- |
| 原扫描构建不可确认 | A01 ifdef、A04 宏；本地未找到精确 build markers | 在错误宏配置下证明不存在的路径不可行 | 完整语义 UNKNOWN；取得原版本 TU/头文件/flags/宏、校验哈希后另验，不能新构建冒充原扫描 |
| 仅按名称或文本唯一选 callee | context.py 的文本/lizard 映射；样本链优先 | 把 macro/function-pointer/static 同名函数当同一个 | R01 要求直接调用和声明绑定；缺声明/链接证据 UNKNOWN，保留检索 selection_tier 范围 |
| 把值相同当 slot 相同 | actual p 与 callee item；A04 saved_clone/clone | callee 局部赋值错误更新 caller | 区分 slot、value version、region；仅入口值对应，不合并存储单元 |
| 旧值/新值混用 | E04-ND skb_prev、skb；A01 copied | 引入伪矛盾导致错误 UNSAT，或丢真实关系 | R02 def-use 版本；旧约束不删，当前定义不明则 UNKNOWN |
| 下层覆盖 caller P | pipeline.py:159–162、420–433 | 丢失或重造跨帧条件 | 分离 CallerPre 与 LocalPath，逐条来源合同；候选丢失即 REJECT |
| 默认未知函数无副作用 | A04 strsep、ND ip6_append_data_mtu | 沿用已经失效的值/内存状态 | 未覆盖 effect UNKNOWN；known write 与 no-effect 候选冲突 REJECT，不按名称猜摘要 |
| 复杂别名和地址逃逸 | `&p`、指针多级、全局可达引用 | 错误唯一 points-to/强更新 | R04 首版只支持唯一 local slot 的直接可见写；其他 UNKNOWN，未做 whole-program alias 分析 |
| 分配、重分配与生命周期 | malloc/realloc/free、内核分配器 | 错把非空、旧指针有效或地址复用当事实 | 先只记新版本事件；无独立分配/生命周期契约则 UNKNOWN |
| 成员/聚合体/联合体/位域 | ND skb->len；OpenSSL 嵌套成员地址 | 将对象根和成员合并，或类型布局错误 | 缺真实声明/布局 UNKNOWN；聚合体按值、union punning、位域短期不自动判断 |
| 整数/指针转换 | unsigned fraggap、void*、跨位宽转换 | 数学 Int 代替 C 产生伪证明 | 只支持明确类型子集和受验证转换；位宽/溢出/UB/指针整数转换短期 UNKNOWN |
| 路径合流与循环 | mv_read_header 多分支、A01/ND goto/loop | 相互排斥约束直接相与，假定某次迭代 | 无环受限路径先拆开；循环/复杂 CFG/递归超过支持即 UNKNOWN，不删路径求通过 |
| return 的作用域错误 | OCSP_copy_nonce 早退；process 示例 | 以为 callee return 导致 caller 退出 | 区分 callee Sink 路径和 caller after-call；摘要覆盖所有支持返回路径 |
| 参数表达式求值顺序 | 复杂实参、嵌套调用、同表达式含写入 | 不存在的“调用前值”映射 | 首轮仅简单无副作用标识符/明确支持字面量；未序列化的读写冲突 UNKNOWN |
| 函数指针、回调、varargs | list_insert_sorted 的 cmp；复杂 libc/API | 错误 callee 集/类型 | 短期 UNKNOWN；不能通过 token 看到名称就按直接调用处理 |
| 并发、原子、volatile、全局变量 | neigh_confirm 的 jiffies/READ_ONCE/WRITE_ONCE | 共享状态被当普通局部不变值 | 短期不自动判断；未来需专门内存模型，不复用简单 SSA 成功结论 |
| 异常控制转移/隐藏效果 | longjmp、inline asm、未建模宏控制流 | 漏路径/修改 | 短期 UNKNOWN，不能默认正常返回或无副作用 |
| 解析器 recovery AST | 缺头文件/typedef；libclang 有包无构建 | 编译器猜出的类型被当真 | 保留全部诊断；相关 warning/error/recovery、缺源码导致语义不完整即 UNKNOWN；不自动注入 stub 修复真实源码 |
| 摘要跨前提/版本复用 | 论文 Memory；现代码仅函数名缓存 | 把另一调用的状态传播过来 | 初期禁用结果缓存；后期严格 key 与新上下文实例化、精确 precondition 匹配 |
| 改名破坏原 B+Δ 合同 | A04 object/object_ptr；未来版本符号 | 完整性检查被绕过或语义歧义被隐藏 | 原始文本不可变；派生 IR 需逐 atom 来源/版本映射；不能假称原 E02 已证明改名正确 |
| 对调试样本过拟合 | 审计 10/固定20已接触 | 样本特判/低估未知率 | 只写通用规则；固定样本不变，冻结后一次回归，记录所有不适用/UNKNOWN |
| 误把局部 PASS 当过滤证据 | E05 全局覆盖 0，局部诊断存在 | 误删真实缺陷 | 传播层无 FILTER 接口；安全 v1 和独立语义/源证据要求保持；UNSAT 也不直接过滤 |

## 优先级

最高优先级是调用点/声明/当前值版本以及原前提不丢；随后处理可见的受限返回/写入，最后才组合路径。构建和前端证据是贯穿各轮的入口门槛，不能等待最终过滤时再补。

## 短期明确不自动判断

不透明库/宏副作用、任意 points-to、未证别名的强更新、重分配生命周期、回调/间接调用、全局共享/并发、复杂循环/递归/异常转移、未知 ABI/typedef/成员布局以及 unsigned 溢出/UB。缺证据时可持续检索或提交人工审查，但不靠名称/模型置信度补齐，更不为了提高 PASS/过滤率缩小真实路径集合。
