# E06-R03 开发前审查与支持范围

日期：2026-11-02。发布基线 `8d03eae13a7ea835e61877fc351703eb69b06da4`；官方冻结 `4efb4b9bf7e845e180451b43ba29a25e3edaa0e3`，论文 arXiv:2506.10322v1。本目录是项目新增安全证据实现，不是作者公开算法或完整论文结果复现。

## 开发前审查

已阅读 E06 六份指定设计材料、R01 mapper/合同/测试/报告、R01-RF 输入适配器，以及 R02 的 value_version、state_environment、r01_adapter、合同、测试、历史结果和报告。publication main 起点干净。R01 原候选的固定集失败由独立 RF 后续处理，不能把原 R01 报告改写成成功。

1. R01 通过 CallExpr.referenced、canonical USR、同 TU 唯一定义、调用原文和类型转换证据绑定调用。额外 TU 只用于否定唯一性。实参/形参序号映射不合并 slot。
2. R02 FunctionTrace 的 version/read/slot/statement/compound 和 StateEnvironment 可只读导入；参数入口版本、不可变赋值版本和路径 current 环境已有实现。其 return 仅终止当前函数，任何调用都是失效屏障，不能直接用于 R03 caller 续行。
3. R02 没有受承诺的跨帧 API；R03 新建子类和适配层，复用局部读写规则及环境，不改 R01/R02 文件或模块全局配置。callee 的 namespace 增加 call_context_id，caller pre 通过具体版本 ID 与 R01 transfer 显式关联。
4. 每个调用点、caller 路径、数据位置独立重分析 callee；不缓存摘要。上下文绑定两端声明、body SHA、callsite、pre 环境和参数映射。词法声明身份与调用实例身份分别保存。
5. callee return 保存 PathReturnRecord 后只结束 callee 路径。caller 以独立 post path 继续；忽略返回值时不产生接收版本，且不把 callee guard 加入 caller guard。

## 本轮范围

只批准自包含、无预处理、无 warning/error 的受控 C11 TU。历史片段只保留原文定位和 UNKNOWN，不补类型/头文件/宏，不拼接成完整 TU。每函数最多一个 if；callee 不展开任何内部调用；不实现 CFG、phi、循环、递归、R04 或 R05。

返回式只支持当前局部/形参标识符或 Clang 已定型的简单整数/浮点 literal，以及 AST 可验证的字面 0 空指针转换。保留类型、位宽、符号性、原文和范围，不求算术值，不导出数学 Int。显式 cast、算术、负数一元表达式等从严 UNKNOWN。类型使用 R01 conversion 和 R02 supported_type，进一步保留边界；不从拼写相同批准类型。

caller 支持声明初始化、简单局部赋值和独立调用语句。实参仅 R01 支持的局部标识符；零参数调用以独立无参数合同核验唯一直接定义。接收目标为局部标量/受支持指针；成员/数组/非局部目标 UNKNOWN。

仅有受支持局部读写和完整正常返回路径时，调用效果覆盖可 PASS（表示这个语法子集没有外部内存效果，不是通用副作用分析）。未知调用、间接/全局/static/成员/数组写、地址逃逸、volatile/atomic、asm、未知控制流或任一路径未覆盖时，整个调用 UNKNOWN，caller 当前绑定全部失效并停止后续推断。已识别局部 return 证据可以单独保存，不据此放行调用。

全局保守资源上限：每次 caller 分析最多 16 个调用上下文、累计8个返回路径转移记录（因此最终路径不会超过8）；超限显式 UNKNOWN，保留全部阻断记录，绝不截去未验证路径来批准。无路径可满足性证明，无摘要缓存、模型、Harness、Z3、SMT 或 FILTER 权限。

## 验收顺序

合成测试 → 原 R01 41 项 → 原 R02 110 项 → 四个历史风险检查 → 文件/依赖保护 → 冻结 → 原固定20独立执行一次。冻结后异常或候选缺陷立即记录并停止，不修补重跑同一候选。所有输出只新增本目录。
