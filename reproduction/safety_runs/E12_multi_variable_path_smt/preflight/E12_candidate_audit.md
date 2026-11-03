# E12-0：多变量路径条件 SMT 案例筛选

## 1. 筛选结论

推荐 **2 条**，首选为 OpenSSL `test_str_ne`，备选为 `test_strn_ne`。不为凑满 3 条而加入仍需复杂宏、循环不变式或函数效果证据的案例。

| 顺序 | 原始数据定位 | 函数 | 告警元数据位置 | 推荐范围 |
| --- | --- | --- | --- | --- |
| 1，首选 | `NPD/cppcheck/cppcheck_openssl_nullpointer.json:row=3` | `test_str_ne` | `test/testutil/tests.c:296` | 两个指针的空值关系、异或提前返回和 OR 短路共同决定 strcmp 是否求值 |
| 2，备选 | 同一文件 `row=4` | `test_strn_ne` | `test/testutil/tests.c:324` | 同一指针对关系加 n1/n2 长度相等条件；只推荐空值投影 |

两个记录都**没有原始 index 字段**，不把 row 伪装成 index。`candidate_samples.json` 保留原始记录、原标签及 index 缺失状态。样本 ID 是本轮由文件路径和零基行号构造的定位符，不声称它是作者原有字段。

首选的研究价值是多个输入之间的关系与短路路径条件组合；它不依赖 E10 的调用者范围，也没有 E11 的归一化赋值。本轮没有生成或运行 SMT，没有实现实验代码。下文逻辑推导均为**源码静态审查与研究设计**，不是求解器结果。

## 2. 审计环境与范围

- 审计日期：2026-11-03；Windows，现有 Python 以 `-B` 运行标准库只读审计命令。
- 论文冻结仓库 `reproduction/upstream`：`4efb4b9bf7e845e180451b43ba29a25e3edaa0e3`。该提交是数据发布仓库的版本，不是被扫描项目的提交。
- 最新远端 main 和发布起点：`f4850309b19cd049ff38356881549bb33c615144`。开始时发布克隆工作区干净。
- `experiment/E12` 在本地和远端均不存在；再次检查后，从 fetch 到的上述 main 新建，未覆盖旧分支。
- 本轮只允许发布 `reproduction/safety_runs/E12_multi_variable_path_smt/preflight/`；不修改 main，不携带本地 main 的其他未发布提交。

对 NPD 的 **8 个 JSON、808 条记录出现**进行结构盘点，逐文件 SHA-256、字段并集、数量见 `source_manifest.json:/dataset_inventory`。808 不是去重后的告警数，也不是论文正式 443 条数据的替代口径。

| NPD 下的文件 | 保存记录数 |
| --- | ---: |
| codeql/codeql_kernel69_nullpointer.json | 70 |
| codeql/codeql_libav_nullpointer.json | 57 |
| codeql/codeql_openssl_nullpointer.json | 50 |
| cppcheck/cppcheck_linux_nullpointer.json | 594 |
| cppcheck/cppcheck_libav_nullpointer.json | 10 |
| cppcheck/cppcheck_openssl_nullpointer.json | 5 |
| infer/infer_libav_nullpointer.json | 6 |
| infer/infer_openssl_nullpointer.json | 16 |

优先核查 kernel69 的 70 条记录的元数据和条件线索，完整函数细读其中 9 条；另完整细读其他分组 14 条。合计 23 个记录的函数细读，包含相同函数对应不同位置的记录，**不是 23 个不同函数**。其余记录只有结构盘点或元数据筛选，不宣称已完成全部 808 条的语义审查。

排除 E10、E11 的 DBZ 样本及 E07/E08 的 kernel69 row=24/index=43。kernel69 中的 `bug_line_constraints`、`var_assign_conditions`、`pointer_null_postconditions`、`early_jump_constraints` 只作检索线索，未直接导入约束。首选和备选本身不含这些扩展字段，也没有可直接使用的 typed B/Δ。

整个筛选依据代码结构、变量与分支关系、未知效果和来源证据；没有以标签、历史预测或预期 SAT/UNSAT 作为排序条件。两条记录的原 result=0 仅原样保留，不用于推导程序性质。

## 3. 原始字节与上游对应

推荐样本所在数据集 SHA-256：

`5a7e89ffb017ece94403f862a5cc8d33f478fc92360d4e957648d66aeee12d29`

| 样本 | function_code UTF-8 SHA-256 | 固定上游函数范围 |
| --- | --- | --- |
| row=3 | `8b2a929c68a079ae0d9ff1f504feffdaab1b20d23389b8f6c8527a371a81fbde` | tests.c:291–303 |
| row=4 | `03ecf237266cacc843e602981702e8dbcca1f7aa08218e9991f19593b50bfa8f` | tests.c:319–331 |

作者 README 声明 OpenSSL v3.4.0。本轮只读取一份 17,153 字节的上游源码文件，未下载新数据集、克隆或构建项目：

- Repository：`openssl/openssl`。
- Tag：`openssl-3.4.0`；tag object `f8804ea82b87caef1e6d18cc387b962e97023bf3`。
- Peeled commit：`98acb6b02839c609ef5b837794e08d906d965335`。
- 文件：`test/testutil/tests.c`。
- 文件 SHA-256：`ebad1a5844d1c24dcb8fd049047064effd3e297511005961959667d5939a347c`。

先观察 tag 文件，再独立读取固定 commit URL 并核对相同字节哈希。两个原始 function_code 都在固定源码中恰好完整出现一次，无需修改空白或函数内容。告警元数据 296/324 行均对应原函数第 6 行。完整文件 UTF-8 文本、HTTP/远端 refs、Git blob SHA-1、取得时间和对应位置均保存于 `source_manifest.json:/upstream_source_observation`；不另创建 C 实验源码。

这是**确定的源码对应证据**；没有验证 tag GPG 签名，也没有证明原扫描实际使用了该 commit 或恢复其 TU、编译命令及预处理结果。不得把源码匹配扩写成原始扫描环境认证。

## 4. 首选：test_str_ne

原始记录：`upstream/benchmark/NPD/cppcheck/cppcheck_openssl_nullpointer.json:/3`；函数字段 `/3/function_code`；目标变量 `s2`。

```c
/* tests.c:291–293 */
int test_str_ne(const char *file, int line, const char *st1, const char *st2,
                const char *s1, const char *s2)
{
    if ((s1 == NULL) ^ (s2 == NULL))          /* 294 */
      return 1;                            /* 295 */
    if (s1 == NULL || strcmp(s1, s2) == 0) { /* 296 */
        test_fail_string_message(NULL, file, line, "string", st1, st2, "!=",
                                 s1, s1 == NULL ? 0 : strlen(s1),
                                 s2, s2 == NULL ? 0 : strlen(s2));
        return 0;
    }
    return 1;
}
```

### 类型、身份和值版本

`s1`、`s2` 分别为第 292 行两个独立声明的 `const char *` 参数，参数序号分别为 4、5（零基）。这是同一个固定函数中的参数身份依据，未伪造 AST USR、R02 ValueVersion 或 R05 context ID。

从入口到 296 行调用求值前，没有给 s1/s2 赋值、取其变量地址、分支合流赋新值或调用其他函数。因此可以直接引用各自的入口参数值，不需要创造归一化版本，也不需要推断其他函数效果。`const char *` 表示所指字符只读，本身不代表指针变量恒定；这里的值保持由实际无写入的源码前缀确认。

### 两个条件及其极性

1. 第 294 行对两个指针与 NULL 的比较结果执行**整数按位异或**。C 相等比较的结果是 int 0 或 1，所以这里的非零结果精确对应“恰有一个为空”。它不是对指针位模式直接做异或。第 295 行在该条件为真时返回；继续执行须取其**假分支**。
2. 第 296 行 `||` 从左到右短路。只有 `s1 == NULL` 为**假**时才会对 `strcmp(s1, s2)` 求值。不能把 `strcmp(...) == 0` 的返回结果当作“进入 strcmp”的先验路径条件。

设 A 表示入口 s1 为空，B 表示入口 s2 为空。到达比较调用需要“294 行异或为假”以及“A 为假”。两者共同约束 A、B，而非仅检查某一个指针。以下是人工源码分情况审查，没有运行程序、测试或求解器：

| A：s1 空 | B：s2 空 | 294 行条件 | 后续行为 |
| --- | --- | --- | --- |
| 是 | 是 | 假 | 296 行左侧为真，短路，不调用 strcmp |
| 是 | 否 | 真 | 295 行提前返回 |
| 否 | 是 | 真 | 295 行提前返回 |
| 否 | 否 | 假 | 296 行左侧为假，可以调用 strcmp |

由此可提出下一阶段问题：**完整前缀条件与“调用求值时 s2 为空”能否同时成立？** 本轮仅提出和审查问题，不生成 SMT-LIB，也不填写求解状态为 UNSAT。

### 危险操作及完整性边界

目标是第 296 行字符串比较调用的空实参风险。当前可确认的研究范围是**该调用是否可能携带 NULL 实参**，不是对 libc 内部解引用、字符串终止性或读取范围的完整认证。可以采用每个已声明指针对应一个空值布尔量的有限抽象，无需设定原始指针位宽或把 NULL 当成全零地址位模式。

两指针可指向同一对象；不假定它们互不别名。空值关系无法证明非空对象仍存活、可读取、以 NUL 终止，也无法排除越界、悬空指针、并发或内存破坏。`test_fail_string_message` 和 strlen 调用在目标表达式求值之后；不把它们的效果前移，也不认证这些调用。

相关前缀没有循环、goto、复杂宏或未知函数副作用。NULL 按标准空指针常量理解；原始 TU/预处理上下文仍 UNKNOWN。后续实验应明确采用经过源码核对的标准 C 标量、按位异或和短路合同。

## 5. 备选：test_strn_ne

原始记录 `/4`，函数 `/4/function_code`；固定源码第 319–331 行。s1/s2 均为 `const char *`，n1/n2 声明为相同的 `size_t`，均为未在目标前重写的入口参数。参数身份和声明位置见 `candidate_samples.json:/recommended_candidates/1/variables`。

```c
/* tests.c:322–324 */
if ((s1 == NULL) ^ (s2 == NULL))
    return 1;
if (n1 != n2 || s1 == NULL || strncmp(s1, s2, n1) == 0) {
```

到达 strncmp 求值前，必须同时满足异或提前返回未发生、n1 与 n2 相等、s1 非空。长度相等条件是 OR 的第一个操作数取假，不是把“不等”误当作进入调用的条件。不能加入尚未返回的 strncmp 结果作为调用可达性前提。

它提供四变量、多短路条件的扩展空间，但与首选属于相近模式，故只列备选。当前没有恢复 size_t 的底层 typedef 或真实 ABI；相同已声明类型的相等关系不需要臆造数值范围。后续若研究字节数、n1=0 的库契约、对象大小或内存访问，必须另行核验。此处不把“长度相等且参数非空”宣称为整个 strncmp 调用安全。`OPENSSL_strnlen` 在后面的分支体中，不参与目标调用前缀。

## 6. kernel69 优先候选为何未列首选

重点文件 SHA-256：`5385ae52f09cc927dbc5e29f17229ccaaa68467e1614cbf73d219fd1f46713a3`。`candidate_samples.json:/priority_kernel70_screening` 保留全部 70 条的行号/index、目标位置、函数哈希、条件字段数量及实际审查级别，没有删除 UNKNOWN 或按标签筛选。

| row / 原 index | 函数 | 本轮暂不推荐原因 |
| --- | --- | --- |
| 16 / 34 | inet6_validate_link_af | dev/idev 关系有价值，但目标为 helper 调用，还涉及属性数组、解析函数和模式检查；认证所需额外效果/类型证据会把首轮变成跨函数工作 |
| 32 / 52 | rt6_multipath_rebalance | WARN_ON_ONCE 的活动定义未恢复，目标前还有 helper 调用 |
| 40 / 64 | ieee80211_nan_func_match | WARN_ON、spin-lock、idr 查找的宏/构建环境未恢复 |
| 41 / 65 | ieee80211_nan_func_terminated | 与上一条相同，非首个多变量条件案例的最小依赖集合 |
| 42 / 67 | ieee80211_chsw_switch_vifs | 嵌套链表循环、未知 old_ctx 返回和堆对象关系 |
| 19 / 38 | icmpv6_ndo_send | skb 克隆、指针算术、writable-buffer 效果和别名 |
| 36 / 57 | rt6_device_match | 多条路径、循环、RCU 字段和 helper 返回值版本 |
| 65 / 95 | ieee80211_tdls_add_setup_cfm_ies | 三指针守卫很有潜力，但 WARN_ON_ONCE 活动定义未恢复，不能按宏名称默认其语义 |
| 66 / 96 | 同上另一位置 | 除宏缺口外，目标前存在传入对象的调用及堆字段/生命周期问题 |

这 9 条均完整阅读保存的函数，但没有获取并认证它们的固定上游源码或编译环境。结论是本轮不优先选择，**不是证明它们不适合任何后续研究**。没有重新运行旧分析模块来补齐证据。

其他 12 条细读但不推荐的记录及逐条理由，保存在 `candidate_samples.json:/considered_but_not_recommended`：包括带 callback 的 list_insert_sorted、使用输出参数的 print_keyspec、需要指针来源和循环的 util_do_cmds、链表/数组/增量指针相关的 Libav 函数，以及 BUG_ON 依赖或目标位于后续条件之前的 Linux 函数。尤其 regmap_get_reg_endian/val_endian 的目标解引用在后续条件之前，不能用后面的提前返回保护前面的危险操作。

## 7. 原始告警来源审计

原始 JSON 给出了 var_name、function_name、function_code、location 和 result。推荐记录**没有**原始 rule ID、checker 名称、版本、扫描命令或原始消息字段。冻结 README 声明使用 CodeQL、Infer、CppCheck；结合作者分组可以登记为“作者归类的 Cppcheck/OpenSSL 数据”，不能登记为已独立认证的行级工具告警。

在本地冻结源码、审计和数据集审计材料中，未找到可绑定这两个位置的原始 SARIF/XML 扫描记录、具体查询/检查器实现或规则 ID。现有模型输出、项目补全结果和聚合 CSV 指标不是原始扫描证据。不猜测其 rule ID，不把作者标签转换为认证结论。真实规则与扫描来源保持 **UNKNOWN**。

这两函数曾出现在历史 `audit/failure_audit_20261029/population_diagnostics.json` 的 assignment_extractor_diagnostics 第 275、276 条中。本轮不读取或移用历史裁决构建约束，不声称是盲测新样本；确切 JSON Pointer 和文件哈希见 `source_manifest.json:/known_prior_exposure`。

## 8. 是否具备进入下一阶段研究设计的条件

首选具备开展**受限调用入口空值路径实验设计**的条件：完整真实函数、固定上游逐字节对应、两个独立指针参数、异或与 OR 两个条件、提前返回和短路极性均有可追溯源码，前缀无未知效果或赋值桥接缺口。需要新增的将是本案例有限空值合同、受控对照和独立验证，而不是重做 R01-R05 或 C 到 SMT 编译器。

下阶段若获准，应先冻结两变量空值抽象及 `^` 的 0/1 整数语义，区分“进入 if 条件”和“实际对 strcmp 求值”，再检验完整路径下空实参故障问题，并保留删去某个守卫后的对照。此处没有实现上述内容，也没有推断任何求解器运行结果。

当前认证边界包括：原扫描规则/TU/实际提交未认证；非空不等于内存安全；不能扩展到测试函数整体、调用者、库内部、所有字符串操作或原告警裁决。

```json
{"original_alert_decision": null, "filter_authority": false, "full_program_semantics": "UNKNOWN", "solver_status": "NOT_RUN"}
```

## 9. 文件保护、交付和 Git

为满足提交前保护检查，除规定的三个审计文档外，增加两份只读检查产物：`preservation_baseline.json`、`preservation_check.json`。本轮共 **5 个新增审计文件**，没有 Python/C 实验代码或 SMT 文件。基线记录 8,273 份既有非凭据文件；最终比较结果、排除规则、Git 起点和本地 main 保持检查见保护记录。文件保护不代表语义 PASS。

发布流程为独立克隆中的 `experiment/E12` 分支，仅复制本 preflight 目录，核对差异、逐字节内容和远端分支状态后正常提交推送该分支。远端 main 保持原起点，不 force push、不覆盖已有分支、不混入其他本地未发布提交。确切提交 SHA 和文件链接由发布完成后的回复提供，不改写本报告以插入其自身提交号。

没有调用 Z3、SMT、分析器、编译器、LLM API 或 DeepSeek Harness，没有运行历史回归或安装依赖。只读取原始数据、已有材料和一份小型固定上游源码。完成 E12-0 后停止，等待 GPT 研究审查，不自动开发或求解 E12。
