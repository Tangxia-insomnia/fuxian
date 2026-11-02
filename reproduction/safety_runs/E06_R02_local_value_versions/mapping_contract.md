# R01 / R02 证据合同

本合同属于独立 R02 适配，不修改 R01，也不接入生产 Engine。

## 身份与值

只读复用 `../E06_R01_direct_call_argument_mapping/mapper.py` 的 AST、声明、类型、位置及哈希接口。`r01_adapter.py` 使用完全相同的数据集、位置、源路径、源字节哈希及 build namespace，给声明建立新 `local-slot`，并保留原 `caller-slot` 与参数的 `callee-slot` 别名。角色 slot 不合并。

`ValueVersion` 身份由 namespace、声明 slot、path、定义事件及序号构成，不能通过变量名称建立关系。`display_name` 只供阅读。入口参数有 @0；无初始化的自动局部没有已验证值；初始化和每次支持的赋值建立新记录。旧记录不删除。复制记录源 slot、源版本和读取证据，不证明指针所指对象、别名、生命周期或被指内存内容。

读取通过 AST `referenced` 声明和当前路径环境绑定版本。错误 slot / 版本 / 其他分支的版本候选为 REJECT；没有可靠读取证据为 UNKNOWN。不同作用域、函数、数据集、源码或路径不能按名字合并。

## 状态与控制流

每条路径独立 `slot_id -> value_version_id` 环境及计数。最多单个 if、两条语法路径；不证明路径可满足性。guard 保存原文、方向、读取 ID、源范围，不翻转条件、不生成 SMT、不推断非空。后续读取分别沿两条路径追踪，不建立 phi。return 只停止本地路径，不形成返回摘要。

未知调用、取址逃逸、间接/成员/数组写及其他不支持语义使当前环境失效并停止该路径；此前记录仍保留。对 `p=unknown()` 可另存 UNKNOWN 赋值事件，但不得依其继续。调用实参先整体检查：有复杂/副作用实参或间接 callee 时不批准任何实参读取，避免 C 未规定的实参求值顺序产生伪 reaching definition。

对于简单直接调用，只能给**调用前读取**附加 R01 `transfer_id`，并验证源字节、数据集、位置及精确范围相同。caller/callee slot 不相等；不创建 callee 的版本，不推断调用效果。即使 pre-call link 为 PASS，整次调用效果仍 UNKNOWN。

## 类型和来源

仅支持受控自包含 C TU、无预处理及 warning/error、已知基本标量/有限指针类型和受支持转换。结构体指针复制不等于结构体内容建模。union、void/多级指针、聚合体复制、volatile/restrict/atomic、算术、复杂 CFG 等不支持。调用方必须如实提供 build_status；`synthetic-self-contained` 是受控测试契约，不是原工程构建证明。

真实保存片段统一 `saved-source-only`：可记录 libclang 诊断，不信任恢复 AST 创建版本。缺原构建、宏和类型时 UNKNOWN。单帧仍适用局部检查；不能套用 R01 的跨帧 N/A。context=null 仅在 RF 原始缺失来源核验后判为证据不足；字段缺失、错误格式、哈希错误是运行失败，保留 traceback 并停止，不伪装 UNKNOWN。

PASS 只表示已声明子集中的局部版本/读取检查通过；REJECT 表示候选与可靠证据冲突；UNKNOWN 表示证据不足或超出范围；NOT_APPLICABLE（报告显示 N/A）限没有实际版本/读取任务的受控空函数。本模块没有 SMT、Z3 或 FILTER/KEEP 接口。
