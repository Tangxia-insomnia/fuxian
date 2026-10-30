# A10 过滤证据核查

本阶段结论：A10 继续为 **UNKNOWN，操作为保留告警**。取得了与公开告警函数逐字符一致的 Linux v6.9.6 历史源码；局部空指针保护、条件否定及原 SMT 合并均有源码支持。原始扫描的源码提交证明、构建配置和实际预处理结果仍缺失，尚不满足用户规定的完整独立复核提交条件。没有生成任何人工签字、可信分析器证明或六条件通过凭证。

这份材料是自动化一致性检查与辅助源码分析记录，不是独立人工语义证明。原审计将 A10 称为“正确过滤对照”，此处将其限制为“与公开 label=0 一致，且历史源码支持局部过滤理由”；原审计、基线预测和安全策略均未改写。

## 1. 固定状态与本阶段范围

- 官方复现仓库提交：`4efb4b9bf7e845e180451b43ba29a25e3edaa0e3`，原状态干净。
- 保留策略版本 `real-bugs-first-v1`、既有 16 项测试结果以及 10 条审计和 20 条留出集的既有离线输出；本阶段没有重跑这些测试或样本。
- 原始基线快照 SHA-256：`ea7820124f2db094091a655746341349c2e4b664d290f7e41c71ecd1324c0d00`。
- [阶段开始状态](<E:/codexconversation/课题研究/reproduction/safety_runs/20261029_a10_review/state_before.json>) 固定了 2913 个基线文件、52 个前阶段交付文件及两个附加清单的哈希；结束校验另存 `preservation_verification.json`。
- 所有新增输出仅写在本目录。核心算法、提示词、配置、最终判定规则、已有结果均未修改；未读取或写入 `.env`。
- 本阶段执行：公开历史源码只读 GET、A10 文件比对、**A10 原查询一次 Z3 重放**。无模型 API、无其他样本执行、无全量重跑。
- 沿用原配置记录：`deepseek-flash`，`https://api.deepseek.com/`；只引用配置，未连接模型。原累计 1187 次调用、估算费用上界 4.491330 元，本阶段增加 0 次/0 元。

## 2. 样本身份、版本和取得证据

样本 `NPD/codeql/kernel69:row=65:index=95`，来自官方 `benchmark/NPD/codeql/codeql_kernel69_nullpointer.json` 的第 65 个零基行（index=95）。整个文件 70 条；本阶段只核查该行，没有重算全基准指标。该行与冻结 A10 告警 JSON 完全相同。公开标签 `result=0` 在既有实验中解释为误报；本阶段没有独立确认该真值。

官方 README 第 9 行标明 Linux kernel v6.9.6；已保存的论文 arXiv:2506.10322v1 文本参考文献也出现 `Linux-kernel 6.9.6`。二者支持选择 v6.9.6，而不是当前主线源码。没有使用最新内核代码替代历史代码。

从 Linux stable 维护者仓库 `gregkh/linux` 取得标签链：

`refs/tags/v6.9.6` → tag object `185c18dcbe7edb086251c0a4fadb752f0b42aaaa` → commit **`9c5a72fbc90d829ffb761da64a73c23cd4e0503f`**。

标签日期 `2024-06-21T12:43:16Z`，GitHub 返回签名状态 `valid`；本机未做 GPG 验签。核心源码均另按上述完整 commit SHA 获取，标签版与提交版 `tdls.c` 字节相同。完整历史函数第 591–686 行与公开 `function_code` 逐字符相同，目标第 614 行也完全一致。这是很强的版本对应证据，仍不能替代作者原扫描数据库的 checkout/build attestation；相同函数可能存在于多个提交。

本次共保留 40 个 HTTP 200 公共源码/元数据响应、5 个 HTTP 404 响应及 19 个原 A10 文件副本。404 响应体明确排除出源码证据。每个下载的 URL、获取时间、HTTP 状态、字节数和 SHA-256 均在同名 `.metadata.json`；原 A10 副本逐一与冻结审计原件比对。

[完整来源、路径、行范围与 SHA-256 索引](<E:/codexconversation/课题研究/reproduction/safety_runs/20261029_a10_review/evidence_inventory.md>)；机器可读索引：[evidence_inventory.json](<E:/codexconversation/课题研究/reproduction/safety_runs/20261029_a10_review/derived/evidence_inventory.json>)。全部以下源码 URL 的公共前缀为 `https://raw.githubusercontent.com/gregkh/linux/9c5a72fbc90d829ffb761da64a73c23cd4e0503f/`，后接表内仓库路径。

| 历史源码本地路径 | 核查行号 | SHA-256 |
|---|---|---|
| [net/mac80211/tdls.c](<E:/codexconversation/课题研究/reproduction/safety_runs/20261029_a10_review/fetched/pinned/net/mac80211/tdls.c>) | 591–686；目标614；调用741–764 | `ecb95e3e463fced7cf9cf79e88d9e7c7e3d140c3d52560c45bbf5b49b28f5d4d` |
| [include/asm-generic/bug.h](<E:/codexconversation/课题研究/reproduction/safety_runs/20261029_a10_review/fetched/pinned/include/asm-generic/bug.h>) | 95–128、146–148、157–184 | `b93635af28401ed276db4c322161fb2ff5b9f43b2f50284df87d0ec4e6ead0b9` |
| [include/linux/once_lite.h](<E:/codexconversation/课题研究/reproduction/safety_runs/20261029_a10_review/fetched/pinned/include/linux/once_lite.h>) | 13–34 | `d170b54b2ed415db7b23068388cb7503985bd32e25a7c150c5ba7c8aa7e6a28e` |
| [include/linux/compiler.h](<E:/codexconversation/课题研究/reproduction/safety_runs/20261029_a10_review/fetched/pinned/include/linux/compiler.h>) | 17–78 | `fe2503c4bf43395aefac4f34bab81603dda4de2c6d0143614741e186e8b0e47a` |
| [include/linux/bug.h](<E:/codexconversation/课题研究/reproduction/safety_runs/20261029_a10_review/fetched/pinned/include/linux/bug.h>) | 5 | `3ea0aa87ccf827f7896d092d49346d3e78dce21f8deef3c790648eb24bb82602` |
| [net/mac80211/sta_info.h](<E:/codexconversation/课题研究/reproduction/safety_runs/20261029_a10_review/fetched/pinned/net/mac80211/sta_info.h>) | 650、718、818–821 | `95fe68f9d3d94197072ad3aad86992569b14457581054b18389ae28cf74d1345` |
| [net/mac80211/sta_info.c](<E:/codexconversation/课题研究/reproduction/safety_runs/20261029_a10_review/fetched/pinned/net/mac80211/sta_info.c>) | 204–223 | `8e44a353a7815c2fd871c51a1528f4674d90aaaa7a7d139eeda73fb8e1ecc577` |
| [net/mac80211/ieee80211_i.h](<E:/codexconversation/课题研究/reproduction/safety_runs/20261029_a10_review/fetched/pinned/net/mac80211/ieee80211_i.h>) | 1022–1024、1069 | `c7b41a6974ceb4d761a262cac41286c81fea210325f6052dc0cb573818b28f23` |
| [include/net/mac80211.h](<E:/codexconversation/课题研究/reproduction/safety_runs/20261029_a10_review/fetched/pinned/include/net/mac80211.h>) | 238–241、705、740 | `3cd92649b7239941cd728913474bb64a0c5e983d6cf6a0813451eb8774a9a0bb` |
| [include/net/cfg80211.h](<E:/codexconversation/课题研究/reproduction/safety_runs/20261029_a10_review/fetched/pinned/include/net/cfg80211.h>) | 819–827 | `0c67e4bb718abb055e2bdb1ea88c254a91e62a2140b95e770cd96bcdac743ca2` |
| [include/asm-generic/Kbuild](<E:/codexconversation/课题研究/reproduction/safety_runs/20261029_a10_review/fetched/pinned/include/asm-generic/Kbuild>) | 3–5、11 | `c7e76ef918b60b82c8a789e475e3df2e122b08f597432dbea10b76af6c1c4ecd` |
| [scripts/Makefile.asm-generic](<E:/codexconversation/课题研究/reproduction/safety_runs/20261029_a10_review/fetched/pinned/scripts/Makefile.asm-generic>) | 17–20、28–30、40–41 | `a7565c82d39dd8aade86cec008ef8d8468e02f07d8ca709f8ba8850b5eeca427` |

带原始行号的完整目标函数及相关片段见 [numbered_source_excerpts.md](<E:/codexconversation/课题研究/reproduction/safety_runs/20261029_a10_review/derived/numbered_source_excerpts.md>)；函数原文另存 [historical_function.c](<E:/codexconversation/课题研究/reproduction/safety_runs/20261029_a10_review/derived/historical_function.c>)。定位比对结果见 [location_and_version_checks.json](<E:/codexconversation/课题研究/reproduction/safety_runs/20261029_a10_review/derived/location_and_version_checks.json>)。

## 3. 告警位置和局部控制流

函数：`ieee80211_tdls_add_setup_cfm_ies`。告警文件 `net/mac80211/tdls.c`，第 614 行，startColumn=2/endColumn=5，跟踪指针为 **sta**：

```c
604 sband = ieee80211_get_link_sband(link);
605 if (WARN_ON_ONCE(!sband))
606     return;
608 sta = sta_info_get(sdata, peer);
609 ap_sta = sta_info_get(sdata, sdata->vif.cfg.ap_addr);
611 if (WARN_ON_ONCE(!sta || !ap_sta))
612     return;
614 sta->tdls_chandef = link->conf->chanreq.oper;
```

第 614 行之前只有顺序代码和上述两个提前返回。函数原文没有能够绕过第 611–612 行到达 614 的标签、goto 或其他入口；第二个检查与目标之间无重新赋值和显式函数调用。目标之后的其他分支不能改变“第一次到达第 614 行”的前置条件。此结论针对取得的历史函数文本，未产生原始编译后的 CFG。

同一赋值文本还出现在本文件第 441 行的另一个函数中；只按整文件字符串搜索无法唯一定位。以**函数名 + 文件路径 + 第 614 行 + 公开函数全文**定位后，本函数内目标唯一，不将另一个函数的同文语句作为 A10 证据。

原发布行没有完整 SARIF `codeFlow` 或明确的扫描 Source 位置。第 608 行是本地可见的 `sta` 赋值来源，不能冒称为作者扫描器报告的 Source。原模型实际只看到本函数一层上下文；本次补查的调用者没有参与原预测。

## 4. WARN_ON_ONCE 的版本化语义

取得的历史 `include/asm-generic/bug.h` 展示三种相关分支：

| 条件 | 源码位置 | 返回值对可达性的含义 |
|---|---|---|
| `CONFIG_BUG` 且有 `__WARN_FLAGS` | `bug.h:95–116` | 保存 `!!condition` 到 `__ret_warn_on`，最后返回其布尔值；告警副作用不改变该值。 |
| `CONFIG_BUG` 通用回退 | `bug.h:146–148` → `once_lite.h:26–34` | `DO_ONCE_LITE_IF` 保存并返回原条件，只有告警调用由 `__ONCE_LITE_IF` 限制为一次。 |
| `!CONFIG_BUG` | `bug.h:157–184` | 退化为 `WARN_ON(condition)`，保存并返回 `!!condition`。 |

特别是 `once_lite.h:13–23` 的一次性标志控制副作用，**外层** 26–34 行返回的是 `__ret_do_once`，不是 `__ret_once`。“只警告一次”不会让第二次遇到空指针时的条件返回 false。`compiler.h:17–78` 中所查 `unlikely`/分支统计包装也保留条件真值。若告警处理发生 panic 而不返回，目标只会更不可达；此处没有模拟告警输出/终止等全部副作用。

辅助检查该历史提交的 21 个架构目录：16 个实际 `arch/*/include/asm/bug.h` 均包含通用 `bug.h`，未发现这些文件直接定义 `WARN_ON_ONCE`；parisc、powerpc、sh、s390 有 `WARN_ON` 定义，也以保存的 `!!x` 为结果。其余 hexagon、microblaze、nios2、um、xtensa 路径返回 404，相应 Kbuild 已保存。通用 `Kbuild:11` 将 bug.h 列为 mandatory；`Makefile.asm-generic:17–30,40–41` 为非 um 缺少的 mandatory 头产生通用 wrapper；um 自己的 `Kbuild:3` 指定 generic bug.h。

此架构盘点只是所取头文件和生成规则的辅助证据，**没有**证明所有传递包含、编译命令行覆盖、生成头文件与原扫描构建一致。没有原架构、`.config` 和预处理 `tdls.i`，就不能宣称已看到该扫描翻译单元实际采用的宏展开。明细：[architecture_macro_inventory.json](<E:/codexconversation/课题研究/reproduction/safety_runs/20261029_a10_review/derived/architecture_macro_inventory.json>)。

## 5. 变量身份、类型、赋值与调用传递

| 对象 | 取得的源码证据 | 核查范围与结果 |
|---|---|---|
| `sta`, `ap_sta` | `tdls.c:600,608–614` | 同一作用域的 `struct sta_info *` 局部变量，分别赋 lookup 结果；第二个 guard 后至目标没有重赋值。 |
| lookup 返回值 | `sta_info.h:818–821`; `sta_info.c:204–223` | `sta_info_get` 返回 `struct sta_info *`；找到匹配项返回指针，否则返回 NULL。因此空值是合法返回状态，确实需要检查。 |
| `sband` | `tdls.c:601,604–606` | `struct ieee80211_supported_band *`，第一个 guard 检查它；原 SMT 未包含。 |
| `sta->tdls_chandef` | `sta_info.h:718` | `struct cfg80211_chan_def` 成员。目标 NPD 假设针对访问这个成员时 `sta` 为 NULL。 |
| `link`, `sdata`, `conf` | `tdls.c:592,597`; `ieee80211_i.h:1022–1024,1069` | `link` 为 `struct ieee80211_link_data *`，成员 `sdata` 为 sub_if 指针，成员 `conf` 为 `struct ieee80211_bss_conf *`。没有证明这几个指针的全部安全性。 |
| RHS 类型 | `mac80211.h:238–241,705,740`; `cfg80211.h:819–827` | `conf->chanreq` 是 `struct ieee80211_chan_req`，`oper` 为 `struct cfg80211_chan_def`；与左侧成员同类型。 |

`sta` 和 `ap_sta` 可能指向同一对象，原 SMT 没有强加“二者必须不同”。本查询只检查空/非空，不使用地址大小比较、地址运算、整数溢出或结构体布局；将指针抽象为 Int、以 0 表示 NULL，对这两条布尔约束可表达所需空值关系，但不构成通用 C 指针模型。

guard 与 sink 使用的是同一个局部 `sta`；该局部指针地址在可见代码中没有逃逸给其他调用。共享对象内容的变化与“局部指针值被改成 NULL”是两件事。`sta_info_get` 的注释要求调用者持有 RCU 读区或锁，本阶段没有证明完整调用链的锁/生命周期正确，不能从本 null-check 结论推广为无 UAF 或整个语句无其他缺陷。

补充调用处为 `ieee80211_tdls_add_ies` 的 `WLAN_TDLS_SETUP_CONFIRM` 分支，`status_code==0` 时在 762–764 行调用。六个实参依序映射到同名形参：`link, skb, peer, initiator, extra_ies, extra_ies_len`。**sta 不是形参，而是被调函数内局部 lookup 结果**，原运行没有需要回溯的 sta 实参映射。本次补查映射见 [call_argument_mapping.json](<E:/codexconversation/课题研究/reproduction/safety_runs/20261029_a10_review/derived/call_argument_mapping.json>)；没有宣称恢复完整扫描调用链。

## 6. 原提取结果、LLM 输出与逐条 SMT 对应

保留原成功尝试调用 59–62 的完整提示词及响应于 `original_a10/calls/`，没有发起新调用。59 生成空指针假设，60 选择第二个提前返回的否定，61 转为 Z3，62 合并；原实际求解只有一个成功事件。之前失败尝试 34–40 不是本次重放输入，也不能混作该成功查询的证据。

`original_a10/frame_00_conditions.json` 保存了两个提前返回，但 `variable_assignments.text` 为 `static void`，不是 sta 赋值，这是**已观察到的提取异常**。第 608–609 行的 lookup 赋值没有进入最终 SMT。A10 的局部保护理由无需假定 lookup 恒空/恒非空，因此该异常目前没有使这两条断言变成错误；仍不能把原抽取器称为完整、可靠的变量状态恢复。

| 原断言 | 角色与具体来源 | 否定、变量和合并核查 |
|---|---|---|
| `(= sta 0)` | **缺陷假设**。`tdls.c:614` 对 `sta` 解引用；官方流水线第 174 行构造 `var_name + " == 0"`；调用59/生成Python第13行。 | 这是“假设目标处发生 NPD”，**不是**源码存在 `sta=0`，也不是把第608行 lookup 强制解释为空。 |
| `(not (or (= sta 0) (= ap_sta 0)))` | **可达性必要条件**。`tdls.c:611–612` 的提前返回；宏来源见第4节；调用60–62/生成Python第17行。 | 继续执行应否定整个 `!sta || !ap_sta`；等价 `sta!=0 && ap_sta!=0`。没有发现否定极性错误，使用同一 `sta` 和 `ap_sta` 符号，没有发现变量被拆分或合并时丢弃这条约束。 |

逐条 JSON（包含源码 SHA、源行号、生成脚本行号与原调用号）：[assertion_source_mapping.json](<E:/codexconversation/课题研究/reproduction/safety_runs/20261029_a10_review/derived/assertion_source_mapping.json>)。宏文件的 URL、行号和 SHA 由上述源码表及完整索引配套提供。

原查询未编码 `sband!=NULL`、调用处 `action_code/status_code` 限制、lookup 的完整语义、其他指针有效性及生命周期，所以**不是完整路径编码**。若局部 guard 确实支配该 sink，舍弃其他真实必要条件会扩大可达集合；一个健全的必要条件子集已与缺陷假设矛盾，可以足以排除这一条 sta NPD 路径，不能因“漏了 sband”就反推本次 UNSAT 错误。反过来，若 guard 的宏语义或支配关系未正确对应原扫描程序，SMT 内部再一致也不能证明过滤正确；本阶段仍保留这个原构建对应缺口。

调用61的旧提示词中还存在通用指导 `!ptr to ptr!=0`，它单独看并不符合 C 空指针否定语义；但该次实际响应把 `!sta` 正确转成了 `sta==0`，不能将潜在提示词问题误报为 A10 已发生的否定错误。本阶段未修改提示词。

## 7. 原 SMT2 与实际 Z3 结果

从 `recorded_raw/solver_01.json` 的 `queries[0].smt2` 直接提取原字符串，未执行模型生成的 Python：

```smt2
(declare-fun sta () Int)
(declare-fun ap_sta () Int)
(assert (= sta 0))
(assert (not (or (= sta 0) (= ap_sta 0))))
(check-sat)
```

日志内原文另存 [original_query.smt2](<E:/codexconversation/课题研究/reproduction/safety_runs/20261029_a10_review/derived/original_query.smt2>)，SHA-256 **`ed917dc8e8b6698a7e2b60e2cae82f27416843699f6935aa3ab4fc0fdfe8f9e3`**。这是被实际重放的字节内容；上面的展示省略原注释和 `set-info`，不作为另一份原查询。原生成脚本、原日志和 CRLF 导出副本都保留在原副本目录。

实际本地 **Z3 4.13.4.0**，超时上限 5000 ms，`check()` 耗时 0.000703800 s，返回 **UNSAT**，与原日志一致。只执行了此 A10 查询一次，没有派生查询、其他样本求解或模型执行。输出见 [z3_replay.json](<E:/codexconversation/课题研究/reproduction/safety_runs/20261029_a10_review/derived/z3_replay.json>)。

初次提取脚本的“字节完全一致”检查失败，查明审计导出 `.smt2` 使用 CRLF（203字节），日志 payload 为 LF（194字节）。换行归一后全文相同；分别保留 SHA 和差异记录于 `inspection_attempt_01.json`、`derived/smt_serialization_comparison.json`。修正的只是本目录提取脚本对序列化差异的检查，没有修改任何原始查询、算法或预测。第一次检查在创建 derived 目录和调用 Z3 前即停止。

UNSAT 的直接逻辑原因是 `sta==0` 与第二条蕴含的 `sta!=0` 冲突。这证明保存的公式无解；它本身不证明公式忠实编码了原扫描翻译单元。

## 8. 独立复核就绪性与未完成项

| 验收项 | 本次得到的支持 | 仍欠缺的证据 |
|---|---|---|
| 源码版本 | 固定 v6.9.6 提交；函数逐字符、行号和目标吻合 | 作者原 CodeQL DB 的 checkout commit/源码归档身份绑定；不能只以相同函数认定整个构建相同 |
| 目标定位 | 文件+函数+614行+sta 及目标表达式一致 | 原始 SARIF 规则/完整 Source-codeFlow 未公开在本地材料中 |
| 控制流 | 两个 return；guard 与 sink 之间无可见绕过/重赋值 | 原扫描预处理翻译单元及对应 CFG |
| 变量状态 | 局部声明、lookup赋值、同一 sta 身份、六参数映射及类型证据 | 原构建类型配置对应；完整调用链生命周期未核实（后者不等同于当前局部null保护错误） |
| 约束语义 | 两条断言有来源；历史宏各所查分支保留条件真值；否定/合并未发现错误 | 原架构、`.config`、编译器/flags/include路径、生成头文件与实际宏展开；原提取有赋值占位异常，未形成完整程序模型 |
| SMT | 原公式原文提取、哈希固定、一次实际UNSAT重放 | 求解器一致性只覆盖公式；不补足上面的语义/版本缺口 |

**完整独立复核提交条件：尚不具备。** 已形成可供读者逐条检查的初步材料，但源版本绑定与实际构建证据未闭合，不把材料齐备程度冒称为用户要求的全部核验通过。本报告不是 `manual_source_review` 或 `trusted_analyzer` 凭证，没有 reviewer 身份、人工签字或六条件全部 verified 的伪造记录。

本阶段决定 **UNKNOWN / KEEP**，`filter_evidence_complete=false`，不记为过滤成功，不改变原 label、不将 A10 加入获批自动过滤集合。既有 safety-v1 的 A10 记录仍为 `missing_semantic_review`；本阶段只引用这条冻结结果，未重跑策略或更新它的六项状态。详见 [review_status.json](<E:/codexconversation/课题研究/reproduction/safety_runs/20261029_a10_review/review_status.json>)。

## 9. 下一步最值得补的内容及停止点

优先补齐 **A10 原扫描构建的可追溯证据**：先寻找或向作者索取 CodeQL 数据库的源码提交/归档标识、对应架构与 `.config`、编译命令，以及目标翻译单元的预处理文本和完整告警 Source-codeFlow。将新证据与本次固定函数、宏和断言绑定后，才考虑提交独立人工复核。若原扫描材料无法获得，应保留当前版本不确定性和 UNKNOWN；另行使用一个明确记录构建环境的新基准也只能标为新的实验，不能倒填为原告警的历史证明。

不应先放宽 FILTER 门槛或重写约束来让 A10 通过。A10 暂未发现实参与形参错配、变量身份拆分或当前两条约束的否定错误；最主要缺口是证据来源与实际预处理程序的绑定，而非 Z3 的求解能力。提取器的 `static void` 赋值占位异常可列为之后的小修复候选，本阶段未修复。

至此停止。未启动下一阶段修复、其他样本或任何新实验。
