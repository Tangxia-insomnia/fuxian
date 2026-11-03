# E12：多变量路径条件组合与故障可达性 SMT 验证

## 1. 结果与认证范围

E12-1 和 E12-2 合并执行完成。本轮局部检查：`PASS`；研究状态：等待 GPT 最终审查。四个查询依次为 **Q1=SAT、Q2=UNSAT、Q3=SAT、Q4=SAT**，模型与独立四情况穷举一致。22/22 项测试通过；实际只有 4 次 solver.check，测试和独立参考均没有额外求解。

结论只涉及固定 `test_str_ne` 源码前缀：当第 296 行 `strcmp(s1, s2)` 真正被求值时，s2 的 NULL 状态不能为真。它不认证整个函数、strcmp 内部或非空对象的可读性；不裁决原告警。

```json
{"original_alert_decision": null, "filter_authority": false, "full_program_semantics": "UNKNOWN", "blind_test_claim": false}
```

## 2. 样本与冻结输入

- 论文数据文件：`reproduction/upstream/benchmark/NPD/cppcheck/cppcheck_openssl_nullpointer.json`。
- 样本定位：`NPD/cppcheck/cppcheck_openssl_nullpointer.json:row=3`；零基 row=3，JSON Pointer `/3`，函数字段 `/3/function_code`。
- 原始 function_name=`test_str_ne`、var_name=`s2`、result=0。原始 index **不存在**，未写成 index=3；原标签只作身份元数据，不参与公式。
- 数据集 SHA-256：`5a7e89ffb017ece94403f862a5cc8d33f478fc92360d4e957648d66aeee12d29`。
- 原始函数字符串 UTF-8 SHA-256：`8b2a929c68a079ae0d9ff1f504feffdaab1b20d23389b8f6c8527a371a81fbde`。
- E12-0 提交：`3d58641c8c62e80d60e82d137b03bcba7b8ed5cd`；五份 preflight 文件全部与该远端提交逐字节核对、固定哈希并只读使用。

`input_verification.json` 保留完整原始记录、location、index 缺失状态、五份输入文件哈希和源码对应结果。输入核验在任何求解器构造/check 之前完成；篡改或身份不一致即 UNKNOWN 停止，不替换备选样本。

## 3. 保存的上游源码对应

读取 E12-0 `preflight/source_manifest.json:/upstream_source_observation/raw_source_utf8`，**没有重新下载源码**。

- OpenSSL tag：`openssl-3.4.0`；固定 commit：`98acb6b02839c609ef5b837794e08d906d965335`。
- 文件：`test/testutil/tests.c`，17,153 字节。
- 文件 SHA-256：`ebad1a5844d1c24dcb8fd049047064effd3e297511005961959667d5939a347c`。
- 固定函数完整且唯一出现于 291–303 行，与原始函数字节一致。原始位置为第 296 行、第 34–36 列，context 294–298 行，均核对一致。

这只认证已保存源码和 benchmark 文本的对应。原始扫描 TU、编译环境、实际扫描提交及 checker/rule ID 继续 UNKNOWN。没有恢复构建或预处理环境，也没有验证 tag 签名。

## 4. 变量身份与保持关系

第 292 行分别声明 `const char *s1` 和 `const char *s2`，参数零基序号分别为 4、5；是两个独立参数身份，而不是按名字合并的一个变量。映射为两个独立 Bool：

| 变量 | C 含义 | SMT 标识 |
| --- | --- | --- |
| A | s1 == NULL | e12_test_str_ne_s1_is_null |
| B | s2 == NULL | e12_test_str_ne_s2_is_null |

入口到目标调用求值前没有指针参数重写、变量地址逃逸、其他调用、循环或 goto，因此分别引用各自入口值。`const char *` 并不保证指针变量不变；值保持来自已核对前缀中的实际无写入。未创建或修改 R02/R05 ID，未开展跨帧传播。

不假设指针位宽、不编码地址、不把 NULL 当成全零地址位模式，不假设两指针指向不同对象。有限空值抽象允许两个非空指针互相别名，但不验证内存别名、对象生命周期或读取合法性。

## 5. C 条件、极性和调用求值边界

```c
/* 294 */ if ((s1 == NULL) ^ (s2 == NULL))
/* 295 */   return 1;
/* 296 */ if (s1 == NULL || strcmp(s1, s2) == 0) {
```

两个相等比较各产生 int 0 或 1；对这两个整数执行按位 XOR，与本抽象的布尔 XOR 精确对应。不是对指针位模式异或。294 行条件为真时在 295 行返回，因此继续执行取 **NOT(XOR(A,B))**。

C 的 `||` 从左向右短路。只有左侧 `s1 == NULL` 为假才会对右侧 strcmp 求值，因此调用边界另需 **NOT(A)**。进入 296 行条件的求值，不代表调用 strcmp；两指针均空时会继续到该行，但在左侧短路。

不使用尚未产生的 `strcmp(...) == 0` 返回值作为调用发生前的条件。后续 test_fail_string_message、strlen 和 return 不纳入目标调用前缀，也不认证这些行为。

## 6. 有限语义合同与故障条件

`semantic_contract.json` 冻结以下关系；实现只接受本样本、固定哈希和此二变量抽象：

```text
A = (s1 == NULL)
B = (s2 == NULL)
PC = NOT(XOR(A, B)) AND NOT(A)
Fault = B
core fault query = PC AND B
```

没有预加 NOT(B)，没有调用者前提或其他样本条件，没有把原标签当约束。SMT 逻辑为 QF_UF 的纯布尔子集，只有这两个 Bool 常量，无位向量、量词、指针地址或完整内存模型。

## 7. 四个求解查询

使用现有 Z3 `4.13.4`，包版本 `4.13.4.0`，每个查询 timeout=30000 ms。每个查询只执行一次 check。准确 SMT-LIB 原文及哈希、公式、模型、耗时、分类和独立状态同时保存在 `experiment_results.json` 与 `queries/*.json`，四个 `.smt2` 文件另行保存。

| 查询 | 公式 | Z3 状态 | 模型（A/B 为 NULL 状态） | check 耗时（秒） |
| --- | --- | --- | --- | --- |
| Q1 | `NOT(XOR(A, B)) AND NOT(A)` | SAT | `{"A": false, "B": false}` | 0.000672500 |
| Q2 | `NOT(XOR(A, B)) AND NOT(A) AND B` | UNSAT | `null` | 0.000065000 |
| Q3 | `NOT(A) AND B` | SAT | `{"A": false, "B": true}` | 0.000085900 |
| Q4 | `NOT(XOR(A, B)) AND B` | SAT | `{"A": true, "B": true}` | 0.000075500 |

Q1 为真实源码调用可达性；其唯一抽象输入为两个指针均非空。Q2 将故障 B 加到完整真实路径条件，结果 UNSAT，无模型。未生成 UNSAT 证书，也未声称独立检查了求解器证书；此处额外使用独立有限域穷举核对。

UNKNOWN 按 UNKNOWN 保存，不转换为 UNSAT；查询或独立验证不通过即保留失败并禁止发布。四个本次实际返回均不是 UNKNOWN。

## 8. 独立 Python 四情况穷举

`independent_reference.py` 仅导入 Python 标准库，不导入 Z3 或 SMT 实现，不读取标签/历史裁决。它先计算 int 0/1 的 XOR，再执行提前返回，最后按 OR 左侧决定是否调用；不是调用 SMT 公式来充当独立参考。

| A | B | 第一条件 int | 提前返回 | OR 左侧是否求值/其值 | strcmp |
| --- | --- | --- | --- | --- | --- |
| false | false | 0 | 否 | 是 / false | 执行 |
| false | true | 1 | 是 | 不求值 | 不执行 |
| true | false | 1 | 是 | 不求值 | 不执行 |
| true | true | 0 | 否 | 是 / true | 不执行 |

该四情况完全覆盖**两个布尔变量的抽象域**；独立解集分别为 Q1={(false,false)}、Q2=空集、Q3={(false,true)}、Q4={(true,true)}。与四个 Z3 状态及三个 SAT 模型均一致。穷举不是完整 C 指针、字符串或程序状态空间的穷举。

`independent_verification.json` 保存四条执行轨迹、每个查询的独立解集和状态、参考代码哈希。测试对四个公式各作四次具体替换，共记录 16 条公式/参考比较；另解析保存的 SMT-LIB，再按同一域核对，均不调用 solver.check。

## 9. 反事实与错误编码诊断

**Q3：COUNTERFACTUAL_XOR_GUARD_REMOVED。** 删除第一条 XOR/return 守卫，只保留 NOT(A) AND B，SAT 模型为 A=false、B=true。把该模型放回原源码，294 行为真，会提前返回，实际不会调用 strcmp。Q3 是反事实对照，不是原告警真实故障证据。

**Q4：INVALID_ENCODING_DIAGNOSTIC_ONLY。** 故意遗漏 296 行的 OR 短路约束，只用 NOT(XOR(A,B)) AND B，SAT 模型为 A=true、B=true。原源码此时在 296 行左侧为真而短路，实际不调用 strcmp。Q4 证明错误编码会产生伪调用路径，不能用作实际程序路径或真实故障。

两个诊断记录均标记 `real_source_path_encoding=false`，同时保存相应模型在真实源码参考解释器中的“不调用”轨迹。没有将它们混入 Q1/Q2 的真实路径结论。

## 10. 边界、错误输入和测试

`test_e12_nullness_smt.py`：**22/22 通过，0 失败、0 错误、0 额外求解**。整个测试套件阻断 Solver/SolverFor 构造；解析 SMT-LIB 不执行其中 check-sat。

覆盖数据集字节篡改、函数 XOR 篡改、目标位置/函数/变量不匹配、缺失 index 被错误补造、原标签身份及不参与公式、保存源码哈希/commit、输入失败先于求解器和结果写入、备选/内存/指针 ABI 等不支持输入拒绝、两个参数身份、XOR 与 OR 区别、分支极性、提前返回、短路和目标求值边界、四公式与独立参考、Q3/Q4 分类、没有预加 NOT(B) 或返回值、精确 SMT-LIB/结果哈希、未生成证书、过滤权限关闭和求解次数。

本轮没有执行失败需要修复或重跑。所有结果、查询和审计输出独占新建；代码的失败路径会保留 UNKNOWN 记录并阻止发布，不能覆盖既有失败记录或换用 test_strn_ne。

## 11. 三类证据分别支持什么

| 证据层 | 本轮内容 | 支持范围 |
| --- | --- | --- |
| 源码静态语义依据 | 固定字节、声明、行号、C int XOR、return 和 OR 求值顺序 | 支持这段源码前缀到有限空值合同的映射，非原扫描 TU 认证 |
| Z3 求解 | 4 个准确布尔查询及 3 个 SAT 模型、1 个 UNSAT | 支持所编码公式的可满足性结论，不自行证明 C 建模完整 |
| Python 独立验证 | 4 种输入顺序执行、完整有限解集、模型核对 | 完整覆盖该二布尔抽象，非内存模型或 Z3 证书 |

三层一致才作为本轮局部实验检查通过；文件保护另行验收，不将其替代为语义依据。

## 12. 研究结论与未解决问题

可以正确组合两个变量的关联条件、提前返回和短路边界：仅知道两个空值相同不足以进入调用，仅知道 s1 非空也不足以排除 s2 为空；完整源码路径共同排除了空实参故障。Q3 和 Q4 各自展示缺失一种守卫时的反事实/伪路径。

该实验验证有限多变量空值路径机制，未重做 R01-R05；与 E10 的跨函数调用者范围、E11 的赋值归一化和值版本转换不同。本实现没有发展为通用 C-to-SMT 编译器，也没有扩大样本或研究备选。

仍未解决且不宣称已认证：

- 原始 checker/rule ID、原扫描 TU、编译环境、实际扫描提交：UNKNOWN。
- 非空对象的有效生命周期、可读范围、NUL 终止、悬空指针、完整地址/堆、内存破坏与并发：未验证。
- strcmp 返回值、实际实现及内部读取，整个 test_str_ne、后续日志/strlen、调用者或完整程序：未认证。
- 无独立检查的求解器 UNSAT 证书；独立穷举只覆盖明确二布尔抽象。
- 样本已接触过，盲测声明为 false；原标签不重标注，不提高或报告整体数据集准确率。

即使 Q2 为 UNSAT，也不能直接把原告警标为误报或 FILTER。原告警裁决保持 null，filter_authority=false，full_program_semantics=UNKNOWN。

## 13. 文件保护

创建任何 E12-1/E12-2 新文件之前建立 `preservation_baseline.json`，记录 8278 份既有非凭据文件。包含 E01-E11、完整 E12-0 preflight、原始数据、audit、R01-R05 和其他已有研究文件。

保护沿用 E10/E11：排除 .git、.venv、__pycache__、node_modules，排除 .env/.env.*、.key/.pem/.pfx/.p12 和声明的凭据名称模式；不记录凭据内容。`preservation_check.json` 单独记录原文件逐字节比较、范围外新增检查、preflight 哈希和 Git 状态。文件保护 PASS 只表示文件未变，不等于语义或告警通过。

本轮新增文件均在 E12 根目录或 queries 下，preflight 内不新增、不修改。未运行 E01-E11 历史回归、原分析器、Harness、LLM API、项目构建、源码或数据下载；没有安装或升级依赖。

## 14. Git 发布记录与交付

执行前及发布前检查分支 `experiment/E12`、HEAD `3d58641c8c62e80d60e82d137b03bcba7b8ed5cd`、远端 main `f4850309b19cd049ff38356881549bb33c615144`、工作区干净；五份 preflight 与远端对应。未 reset、修改旧提交或切换备选。受保护的本地 main `fb8e98e0771304ef97682a57f5fcf4969abb216b` 及其未发布历史保留，不并入本轮提交。

仅在 `acceptance_check.json` 全部局部标准通过时，向已有 `experiment/E12` 正常提交并推送本轮新增文件；不修改远端 main、不 force push。提交前检查 staged diff、文件清单和源文件/副本/Git blob 字节一致性；推送后核对分支 HEAD 与 main。实际发布 SHA 由最终回复/远端 Git 提交提供，冻结报告不改写为自引用提交号。

`publication_file_list.md` 列出本轮新文件；`artifact_hashes.json` 冻结全部新产物及受保护 preflight 的哈希。四个 SMT-LIB 文件对应 Q1–Q4，旁边 JSON 保留单次求解结果。实现和测试入口使用既有 Python -B 环境；由于结果独占创建，不应在本冻结目录重跑实验或覆盖测试，复核可读取已保存记录。

E12-1+E12-2 到此停止，等待 GPT 最终研究审查，不进入 E13，不修复或修改 E10/E11。
