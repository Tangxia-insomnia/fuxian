# R02 开发前审查与范围

基线：a8e39f0d8c703594a456e2c531e0ae8e00a0f39f。已阅读 E06 设计五份重点文件、R01 mapper/合同/测试、RF 运行器/来源解释/验收结果。本轮是独立复现适配，不声称作者原实现已经公开这些细节。

## 只读复用与接口不足

R01 `mapper.py` 的 parse、declaration、type_info、raw/span、stable_id 可提供准确声明和源范围。R01 的 caller-slot 与 callee-slot 是不同角色的词法身份，transfer_id 属于具体调用点/参数。本轮新增 local-slot，以同一声明为依据保留 R01 两端别名；ValueVersion 引用 local-slot，不合并两种 R01 slot。可对调用前实参读取附加 transfer_id 旁证，但不传播到 callee 状态，不验证函数效果。

R01 没有赋值/读取时间点、状态环境或 CFG 接口；在新目录适配，不改旧模块。真实 AST 探针 `ast_probe.c` 实际解析成功：DeclStmt/VarDecl 初始化、BinaryOperator 赋值、DeclRefExpr 引用、IfStmt/CompoundStmt 可读取，诊断为空。运算符需结合 AST 子节点边界与 token 识别，不能用变量名字/最后一个文本赋值推断。

## 明确支持子集

自包含、无预处理、无 warning/error 的 C TU；已知类型的自动局部/参数；简单初始化、标识符复制及已知字面量；连续简单 `=`；括号；无副作用标量/指针测试；void 丢弃读取和局部 return 读取。空函数单独 N/A。类型/转换须有 AST 证据；不计算一般算术，unsigned 算术尤其 UNKNOWN。

每函数最多一个 if、最多两条语法路径；保留 true/false 标签、原条件、读取版本和源码，不做条件取反、不推导指针非空、不做路径可满足性判断。if 后继续逐路径执行，保持两个环境，不建立 phi，不选一条路径作为合流结果。return 终止自己的路径，未返回路径继续；不做函数返回值传播。

未知调用的实参读取可记录在调用前；调用效果不支持则全环境失效并停止该路径。`p=unknown()` 仅记录已知赋值事件与未知新版本，不沿用旧 p 的性质，不建立返回摘要。取址逃逸、间接/成员/数组写、volatile/atomic/global/static、复杂表达式、循环/goto/switch/多 if 均 UNKNOWN。未知 barrier 不改/删旧版本，只使当前映射失效。

复制只保存源版本 ID；不把同值等同于 slot、内存对象、别名或生命周期。成员读取超出支持，但 AST 明确的成员与根变量身份冲突可以单独 REJECT 候选；这不是整函数语义 PASS。

## 历史与实验合同

缺原始构建、宏、类型/完整 TU 的保存片段，在前端门槛即 UNKNOWN；不注入 typedef/宏/头文件，不凭恢复 AST 创建已验证版本。先通用合成测试、R01 41 项回归和历史风险检查，再冻结，一次全新 R02 固定 20 回归。单帧对局部版本检查仍然适用，不能沿用 R01 的跨帧 N/A。两条 null 继续采用已核验 RF 来源规则，不重建缺失上下文。

禁止 LLM、Harness、Z3、新 SMT、生成代码执行、生产接入、安全裁决及 R03–R05。未知不是成功。当前文件为实施范围，不是测试已经完成的结果。
