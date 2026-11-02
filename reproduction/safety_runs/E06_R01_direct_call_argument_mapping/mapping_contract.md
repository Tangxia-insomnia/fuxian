# 已实现的局部合同与边界

本文件描述 R01 当前独立代码，不声称整体候选已验收。定位依据为 `mapper.py` 中的同名函数；代码 SHA-256 在 `freeze_manifest.json`。

## 输入与 AST 门槛

`analyze()` 接收源文件、dataset_id、非负 position、构建证据状态及可选定义候选文件。读取的同一 UTF-8 字节快照以 unsaved_files 交给已有 libclang，同时计算 SHA-256。参数身份不由样本 ID 或标签决定。

唯一可批准环境是明确标注的自包含合成 TU。分析参数为 `config.json` 中的 C11、`-nostdinc` 等，使用环境的默认目标平台；类型大小来自实际 AST，不默认 int/指针位宽。没有模拟原项目 build。预处理指令、warning/error 及未核验构建均阻断批准。诊断在每份报告根 `diagnostics` 保存，调用记录通过 `diagnostics_ref` 引用。

`CallExpr.referenced` 必须为 FunctionDecl，调用文本是普通函数名调用，且同 TU 恰好一个定义。额外 TU 仅用于发现定义歧义，不供应正向跨 TU 绑定。函数指针/回调、宏、缺定义、多定义候选、varargs 和零参数无传值关系均 UNKNOWN。真实保存片段有诊断时只输出候选位置，绝不批准恢复 AST 身份。

## 三种身份

`declaration()` 记录 Clang canonical USR、声明位置/范围、链接身份，并绑定源 SHA-256、路径、数据身份和构建状态。

- caller-slot：调用方局部/参数的词法声明身份。
- callee-slot：被调用函数参数的词法声明身份，与 caller-slot 分离。
- transfer：callsite_id、参数序号及两端 slot 的关系。

词法形参 slot 可被不同调用点引用；各次静态入口值关系通过不同 transfer_id 隔离。本轮不建立动态调用实例、递归运行栈或值版本。相同 caller 实参传给多个形参时共享实参 slot，保留不同形参 slot 与 transfer；同名不同词法范围通过声明位置区分。

“converted_callsite_value_equals_parameter_entry_value”是有条件的按值传递关系，不是存储单元等同，也不证明指针指向同一存活对象。没有向 SMT 导出任何等式。

## 参数和类型

`identifier_reference()` 仅接纳局部/参数标识符及括号/隐式 AST 包装；不接纳显式 cast、成员、取址、全局/static/extern 实参及一般表达式。参数依据 CallExpr 和定义的参数序号一一配对，不依据名称。

`conversion()` 支持实际 AST 后转换类型与形参规范类型一致时的以下子集：

1. 已知基本标量规范种类/大小相同；或受支持的单层标量指针同类型。
2. signed char/short/int/long/long long 中大小严格增加的带符号整数拓宽；转换后 AST 类型必须有证据。
3. 单层受支持指针添加 pointee const，不允许丢 const。
4. 以 canonical record 声明身份相等检查结构体指针；测试验证了 struct 指针。当前代码使用 Clang RECORD 类别，未额外限定 StructDecl，因此 **union 指针边界尚未验证，不能据此宣称已批准 union 支持**；这是下一候选需要收紧并测试的范围风险。聚合体按值不支持。

volatile/restrict、间接多级指针、void* 转换、窄化、未知/不支持类型或转换均不批准；明确错误的候选映射 REJECT，解析诊断本身只阻断批准，不把恢复类型当冲突证明。实际表达式、前后类型、转换种类、声明范围和函数源码哈希全部保留。

`verify_proposal()` 检查声明支持的候选字段：实参/形参序号、两端 slot 和转换种类。缺字段 UNKNOWN；与已验证 AST 关系冲突 REJECT。它不验证任意 C 语义描述或其他自定义字段。

## 没有实现的能力

没有 SSA、赋值状态、返回值、间接写、别名、外部副作用、跨函数路径条件合成、SMT、求解或安全裁决。没有恢复真实构建和预处理。`run_regression.py` 还未可靠处理 null 上下文，因此本候选整体未验收。
