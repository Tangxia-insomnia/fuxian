# LLM4PFA 失败定位审计

审计日期：2026-10-29（Asia/Shanghai）。范围：当前补全版 NPD 扩展实验；离线审计，不新增功能，不调用模型，不重跑最终预测，不修改算法、提示词、标签或已有结果。以下“建议修复”均未实施。

## 结论与证据边界

当前效果不佳不能主要归因于指标算错或 Z3 求解器不可靠。最强证据指向：**条件提取遗漏、LLM→SMT 语义失真、上下文/输出契约造成的未分类**。同时，公开数据缺少精确 Source，两个真实缺陷误删标签的具体路径仍未完全核实，不能把全部差异归咎于 DeepSeek 或声称已恢复原论文算法。

原有 26.56% 是 241 条已标注误报中确认过滤 64 条。128 条已完成执行但保留，49 条未分类；只修执行阻塞、不改变已完成预测，最理想也只能达到 113/241=46.89%。所以恢复可执行性本身不足以解释/弥合与论文 NPD 72% 的差距。这个上界仅说明当前误差结构，不是同条件论文性能比较。

## 1. 固定版本与备份

- 官方仓库： https://github.com/LLM4PFA/LLM-Enhanced-Path-Feasibility-Analysis
- 上游 commit：`4efb4b9bf7e845e180451b43ba29a25e3edaa0e3`，detached HEAD；`git status --porcelain` 与 `git diff --name-only` 均为空。
- reproduction/ 本身不是 Git 仓库，补全目录没有可引用的 commit。已用 SHA-256 固定 completion/、scripts/、patches/、configs/ 等全部文件；不能虚构一个“补全版 commit”。相对 expanded_run_identity.json 的源代码和配置变化为 **0**。
- 采用配置：deepseek-flash，API https://api.deepseek.com/，temperature=1e-7，非 thinking，输出 3072 token，每样本最多 24 次调用；Z3 超时 5 秒、子进程 15 秒。模型别名不能证明后端快照永久固定。
- 备份：`audit/failure_audit_20261029/frozen_snapshot.zip`，2913 个文件，未压缩 28,655,452 字节。包含原始/处理后结果、旧阶段存档、配置、日志和上游已跟踪代码/数据；排除 .env、凭据、虚拟环境与 Git 对象库。ZIP 校验通过。
- ZIP SHA-256：`ea7820124f2db094091a655746341349c2e4b664d290f7e41c71ecd1324c0d00`。
- 新文件仅在 audit/、failure_audit.md 和独立 stage_08 日志。原始补丁在 patches/completed_pipeline.diff；它记录之前的补全，不是本次新增修改。

证据：[冻结清单](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/frozen_state.json)；[冻结检查点](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/checkpoint_01_freeze.md)。上游 model.py 在冻结源代码中可能含作者历史配置字面量，本报告不摘录、不使用它们；用户 .env 不进入备份。

## 2. 数据、标签和论文版本

使用 arXiv:2506.10322v1（2025-06-12），本地原文与 HTML 已冻结。上次审查的较新 main 为 37a1fdc99d59a8af176ae8c93fa4bf0adbeed997，README 改名 PATHAGENT；本次没有联网更新/切换代码，也不声称这是当前远端最新提交。历史基准上下文来自 29ca96e0d5f860d1f4ce07cd3e54e5e25732d1a1 的 baseline/NPD-*.json。

| 对象 | 统计与含义 |
|---|---|
| 论文 v1 | SAFP-Bench-C，NPD/UAF/BOF，364 告警、45 真实缺陷；GPT-4o-mini，temperature=0；基线 LLM4SA、LLMDFA |
| 采用 commit 的 README | 五类、443 告警、47 真实缺陷，统计范围已不同 |
| 公开 benchmark 文件 | 14 个 JSON，1,017 行；UBI/UUA 两文件内容完全相同，按文件去重后 954 行；这不意味着 954 个互不重复漏洞 |
| 本次 NPD 来源 | 8 文件，808 行；仅 278 条已有整数 0/1 标签进入评估：241 误报、37 真实缺陷 |
| 排除 NPD | 530 行无效/缺失：526 缺 result、4 条 -1；未推测或补标 |
| 其他类型 | UAF 25、BOF 42、DBZ 16、UBI 63，共 146 个去重文件行；没有运行缺陷类型对应完整流水线，不能使用 NPD 的 var==0 冒充 |
| 抽样 | 扩展阶段为全部有效标签记录，无按预测/可运行性挑选；复用原 25 条最终记录且不重复计数。先前 smoke=5，pilot=固定种子 20261025 的分层 10+10 |

重要统计差异：Cppcheck/Linux 公开文件 594 行中仅 65 个 label=0，3 个 -1、526 无标签，无法对应论文 83 条/8 个真实缺陷；这解释了当前有效标签集合少 8 个真实缺陷，但不能推断它们具体在哪些无标签行。CodeQL/OpenSSL 公开 50 行中有 1 个 -1，只评估 49 条/8 个真实缺陷；作者保存聚合指标为 9 个真实缺陷，论文附录为 8，版本/统计对应不确定。论文附录 Infer 的分项目 16+6=22，但该行 Total 印为 24，也有内部加总差异。

标签映射为 **result=0→误报，result=1→真实缺陷**，由数据计数与作者保存 real_bug_num/total_num 交叉佐证，没有发现整体颠倒。它是聚合级佐证，不是独立重标注；不能因此保证每条标签正确。每条公开 NPD 告警都没有显式精确 Source/codeFlow 字段；function_list、var_name、Sink 片段与候选赋值不等于完整 Source→Sink 证明。

数据哈希与原 manifest 全部一致。证据：[独立数据清点及标签核对](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/data_version_check.json)；原 labels 核对见 results/processed/expanded_label_audit.json。论文参考：https://arxiv.org/html/2506.10322v1#S4.T1 。

## 3. 当前实验结果与独立指标复算

| 真实类别 | 过滤 | 保留 | 未分类 | 合计 |
|---|---:|---:|---:|---:|
| 误报 | 64 | 128 | 49 | 241 |
| 真实缺陷 | 2 | 30 | 5 | 37 |
| 合计 | 66 | 158 | 54 | 278 |

成功 224/278=80.58%；上下文阻塞 39（误报 34、真实缺陷 5）；运行失败 15（全是误报）。独立脚本按逐条 JSON 重算并核对 CSV，没有调用原 evaluate() 来自证正确，结果与原指标一致。

- 误报过滤率：64/241=26.56%。
- 真实缺陷保留率：30/37=81.08%；误删率：2/37=5.41%；另 5/37=13.51% 未分类，保留率与误删率不能强行加到 100%。
- 以“误报，应过滤”为正类：Precision=64/(64+2)=96.97%；Recall=64/241=26.56%；F1=2PR/(P+R)=41.69%。
- 上述 Recall/F1 将未分类误报保留在分母，是覆盖率受罚口径；不是只在成功样本上计算的普通二分类指标。若只看已分类子集，误报过滤率为 64/192=33.33%，真实缺陷保留率 30/32=93.75%；这些只能作为补充，不能替换主指标隐藏失败。
- 平均最终尝试耗时 5.805s/全部选定；成功样本均值 6.425s。累计 1187 次调用、费用估算上界 4.491330 元，含之前 5 次失败尝试；本次审计新增模型调用 **0**、API 费用 **0**。该时间不是含所有重试的总摊销时间，费用是估算，不是账户账单。

论文同类 NPD 报告 FPR_R≈72%，但模型、有效数据范围、缺失模块补全、失败处理口径均不同。作者保存 CodeQL/Linux 聚合指标 confusion 四格加起来已等于 70，却另外报告 failed_num=7；无逐条记录，不能恢复其失败处理方式。不能直接用两份数字宣称同条件差距或框架无效。

证据：[独立复算](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/independent_metrics_check.json)。

## 4. 十条逐样本审计

采用固定的目的性诊断选样，**不是随机抽样，不用于估计全量各根因占比**：纳入全部两条真实缺陷误删、三条误报保留、一个阻塞、两个执行失败，以及一个真实缺陷保留和一个正确过滤对照。共 3 个真实缺陷标签、7 个误报标签，覆盖 Linux/Libav/OpenSSL、CodeQL/Infer。Cppcheck 相关失败另按全量日志核查。

只有 NPD 有本次完整运行证据，故十条都是 NPD。未另跑 UAF/BOF 来凑类型，也不把原来没有运行的阶段写为成功。

| 审计 ID | 样本 ID（NPD/ 后缀） | 标签 | 输出 | 核心发现 |
|---|---|---:|---|---|
| A01 | `codeql/kernel69:row=10:index=22` | 1 | filter | 条件极性翻转导致伪造矛盾，真实缺陷标签样本被过滤 |
| A02 | `codeql/kernel69:row=11:index=23` | 1 | filter | 真实缺陷标签与局部保护条件冲突，尚不能判定标签还是路径建模有误 |
| A03 | `codeql/libav:row=3:index=8` | 0 | keep | 空格缩进丢失 switch/while 条件，枚举关系未编码 |
| A04 | `codeql/kernel69:row=12:index=24` | 0 | keep | 正确恢复 kfree 调用，但同一指针被拆成三个独立变量 |
| A05 | `codeql/kernel69:row=55:index=81` | 0 | 未分类 | 并非形参位置映射错，而是 !sta 条件被复合实参规则阻塞 |
| A06 | `infer/openssl:row=4:index=None` | 0 | 未分类 | 合法 JSON 已返回，但解析器取了前面的 C 代码块 |
| A07 | `codeql/openssl:row=41:index=43` | 0 | 未分类 | 长条件列表的 SMT 输出在 3072 token 上限处截断 |
| A08 | `codeql/libav:row=13:index=20` | 0 | keep | 两层参数名映射正确，但模型只看到了两个空指针假设 |
| A09 | `codeql/kernel69:row=34:index=55` | 1 | keep | 真实缺陷保留对照：求解与最终映射一致，但仍是近似可行 |
| A10 | `codeql/kernel69:row=65:index=95` | 0 | filter | 误报正确过滤对照：提前返回和空指针假设构成矛盾 |

每条的原始告警、完整实际代码、调用/参数、条件、原提示词及 LLM 原文、解析结果、生成脚本、SMT2、Z3/错误和费用均在对应 samples/Axx/。早期失败尝试与最终尝试分开索引；没有执行过的 SMT/模型步骤明确记为“未执行”。精确 Source 缺失明确记录，并附候选赋值，没有编造扫描器路径。

### A01：条件极性翻转导致伪造矛盾，真实缺陷标签样本被过滤

**Source / Sink 与代码链：** 仅 tcp_sendmsg_locked；Sink 为 TCP_SKB_CB(skb)->tcp_flags &= ~TCPHDR_PSH。宏体未展开，边界来自作者历史数据。

**Source 可恢复性：** 公开行没有精确 Source。代码候选为 tcp_write_queue_tail(sk)（函数内第 21/100 行）和 tcp_stream_alloc_skb（117 行）；不能将其中任意一处冒充已恢复的原始 Source。

**实参与形参：** 无跨函数实参→形参转换；tracked=skb。宏 TCP_SKB_CB 的内部参数语义未验证。

**关键条件：** 保存条件为 goto new_segment 和 if (!copied)，前者被原有适配逻辑移除。实际要求执行该分支时 copied==0。

**LLM 原文与解析：** 调用 224 却生成 Not(copied==0)，调用 225 正确生成 copied==0；调用 226/227 按“保留全部已有约束”把两者并存。不是 Z3 自己制造矛盾。

**SMT / Z3 / 最终判定：** 最终断言 copied!=0 ∧ skb==0 ∧ copied==0，Z3 UNSAT，result=False→filter。离线仅纠正极性后公式 SAT；这只证明原 UNSAT 不能作为过滤证据，不能证明完整 C 路径可行。

**审计结论：** 确认 SMT 条件翻译和合并错误；相对原标签为误删。该标签与 A02 同函数的局部非空检查仍有审查空间，未在本次改标。

完整证据：[逐条审计](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/samples/A01/audit.md)；[原始告警](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/samples/A01/original_alert.json)；[调用与求解索引](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/samples/A01/evidence_index.json)。

### A02：真实缺陷标签与局部保护条件冲突，尚不能判定标签还是路径建模有误

**Source / Sink 与代码链：** 仅 tcp_sendmsg_locked；Sink 为 TCP_SKB_CB(skb)->end_seq += copy。宏体未恢复。

**Source 可恢复性：** 与 A01 同函数且 skb 有多次赋值。没有原始 Source/完整 CodeQL codeFlow，无法知道标注指的是哪一版 skb。

**实参与形参：** 无跨函数转换，tracked=skb。原告警 function_list=[tcp_write_queue_tail] 是函数提示，并非完整路径。

**关键条件：** 目标条件只有 goto new_segment，移除后为空；提前退出条件 !skb 被选中，源码确实存在 if (!skb) goto wait_for_space。

**LLM 原文与解析：** 调用 73–76 依次给出 skb==0、["!(!skb)"]、skb!=0 及合并函数；双重否定翻译本身正确。

**SMT / Z3 / 最终判定：** skb==0 ∧ skb!=0，Z3 UNSAT，filter。该保护只在特定分配分支内；当前实现未给不同赋值建立 SSA/路径版本，因此不能凭该式证明所有到达路径均不可能。

**审计结论：** 相对标签属于第二条误删，但没有足够证据宣称模型推理错误或标签错误。局部代码看起来有非空保护；需要原始 Source、所有进入路径和宏定义才能裁决。保留原标签和预测。

完整证据：[逐条审计](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/samples/A02/audit.md)；[原始告警](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/samples/A02/original_alert.json)；[调用与求解索引](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/samples/A02/evidence_index.json)。

### A03：空格缩进丢失 switch/while 条件，枚举关系未编码

**Source / Sink 与代码链：** 仅 aac_decode_frame_int；Sink 为 decode_ics(ac, &che->ch[0], gb, 0, 0)。相同目标文本在第 55、69 行出现两次；提取器按文本循环选最后一次，没有使用告警源行号消歧。

**Source 可恢复性：** 候选为 ChannelElement *che=NULL 和 che=get_che(...)；精确告警 Source 未发布。

**实参与形参：** 在传参前已求值 &che->ch[0]，故终止于本函数的直接成员访问；未进入 decode_ics，无形参映射。

**关键条件：** 实际保存 target_conditions=[]；空格缩进仅在内存转为 Tab 后，同一原提取器返回 while(...!=TYPE_END) 和 if(elem_type==TYPE_LFE)。这同时暴露它选中了最后一个同文 Sink。

**LLM 原文与解析：** 调用 419–422 仅保留 che==0 和退出条件的否定；将 TYPE_END、TYPE_DSE 建成无约束 Int，未补回 case 条件。

**SMT / Z3 / 最终判定：** che==0 ∧ (elem_type==TYPE_END ∨ elem_type>=TYPE_DSE ∨ che!=0)，SAT，keep。诊断性补入“仍在循环且该 case 小于 TYPE_DSE”后 UNSAT；后一关系须从真实枚举定义核实，本次没有把假设写入原实验。

**审计结论：** 确认空格缩进处理错误、目标文本歧义和 SMT 缺少路径/常量关系；这条误报保留有直接可定位的证据。

完整证据：[逐条审计](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/samples/A03/audit.md)；[原始告警](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/samples/A03/original_alert.json)；[调用与求解索引](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/samples/A03/evidence_index.json)。

### A04：正确恢复 kfree 调用，但同一指针被拆成三个独立变量

**Source / Sink 与代码链：** tcp_set_allowed_congestion_control → kfree；最终历史边界为 free_large_kmalloc(folio,(void*)object)，未继续进入其实现。实际代码中 kfree 对 ZERO_OR_NULL_PTR(object) 先返回。

**Source 可恢复性：** 源码第 7 行 saved_clone=clone=kstrdup(val,GFP_USER)，第 8–9 行 !clone 返回；这是真实可见候选，不等于已恢复精确扫描 Source。

**实参与形参：** kfree(saved_clone) 的第 0 个实参→形参 object；保存 frame 与离线词法映射一致。位置映射没有错；saved_clone=clone 的值关系没有被约束化。

**关键条件：** caller 的 goto out 被移除，模型过滤提前退出约束得到 []；callee 提取 if(unlikely(!folio_test_slab(folio)))，另有 ZERO_OR_NULL_PTR 提前返回。

**LLM 原文与解析：** 调用 234 甚至生成未实际求解的布尔程序，被 worker 拒绝；235 修到可执行。238 最终把 object:Int、object_ptr:Int、object_bv:BitVec64 作为独立符号。

**SMT / Z3 / 最终判定：** 最终 object==0、object_ptr==0、object_bv!=0 可同时成立，所以 SAT→keep。离线只连接同一指针的三个表示就得到 UNSAT。Z3 原结果正确，编码身份关系错误。

**审计结论：** 确认变量身份/类型合并错误；模型文字已说空指针会提前返回，后续脚本却没有表达“到达 Sink”的要求。caller 的别名非空关系也是缺失项。

完整证据：[逐条审计](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/samples/A04/audit.md)；[原始告警](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/samples/A04/original_alert.json)；[调用与求解索引](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/samples/A04/evidence_index.json)。

### A05：并非形参位置映射错，而是 !sta 条件被复合实参规则阻塞

**Source / Sink 与代码链：** 历史候选为 ieee80211_mgd_probe_ap_send → ieee80211_check_fast_rx。原运行在预检查阶段阻塞，没有持久化实际 context，也没有模型调用；审计候选文件明确命名 NOT_EXECUTED。

**Source 可恢复性：** 候选 sta=sta_info_get(sdata,dst)，调用前有 if(!WARN_ON(!sta))；无精确扫描 Source。

**实参与形参：** sta→sta 的离线位置映射成功。repo.prepare 可恢复该转换；engine.prepare 随后对 if(!WARN_ON(!sta)) 调 called_function，因 WARN_ON 参数为 !sta 而非 sta，抛出 unsupported compound argument。

**关键条件：** 离线复查得到 if(dst) 与 if(!WARN_ON(!sta))。这是原提取器结果的审计重放，未冒充原运行已保存的条件。

**LLM 原文与解析：** 未执行；调用数 0。

**SMT / Z3 / 最终判定：** 未生成 SMT，也未执行 Z3；prediction=null，blocked_context。

**审计结论：** 确认上下文支持边界与条件中的函数识别规则造成阻塞；没有发现这条样本实参与形参位置映射错误。

完整证据：[逐条审计](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/samples/A05/audit.md)；[原始告警](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/samples/A05/original_alert.json)；[调用与求解索引](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/samples/A05/evidence_index.json)。

### A06：合法 JSON 已返回，但解析器取了前面的 C 代码块

**Source / Sink 与代码链：** 仅 ssl_ctrl；Sink 为 if(sc->handshake_func==ssl->method->ssl_connect)，已有完整函数保存。

**Source 可恢复性：** sc=NULL；在 BIO_CTRL_RESET 分支内由 SSL_CONNECTION_FROM_SSL_ONLY(ssl) 赋值并检查。没有显式 Source 定位。

**实参与形参：** 本样本无跨函数形参转换；tracked=sc。

**关键条件：** 实际 target_conditions=[]，遗漏 cmd==BIO_CTRL_RESET；仅改变内存代码的空格缩进后，原提取器能返回该 case 条件。

**LLM 原文与解析：** 1145 生成 sc==0；1146 输出解释、一个 ```c 块，最后有合法 ```json 数组。适配器正则的 json 标记可省略，误把第一个 C 代码块作为 JSON 解析。

**SMT / Z3 / 最终判定：** 仅有初始 Z3 片段，尚未形成可执行最终求解脚本；solver_attempts=0，JSONDecodeError，prediction=null。

**审计结论：** 确认输出解析缺陷；无需换模型即可定位。全量另外 4 个 JSONDecodeError 也都存在后置合法 JSON 数组，但解析成功不代表内容正确或最终可判定。

完整证据：[逐条审计](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/samples/A06/audit.md)；[原始告警](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/samples/A06/original_alert.json)；[调用与求解索引](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/samples/A06/evidence_index.json)。

### A07：长条件列表的 SMT 输出在 3072 token 上限处截断

**Source / Sink 与代码链：** 预恢复 req_main → X509_REQ_print_ex → X509_REQ_get_X509_PUBKEY，最终 Sink return req->req_info.pubkey；实际模型调用只到 frame 0，后两帧没有实际分析。

**Source 可恢复性：** req_main 中 req 初始化及 load_csr/构造等赋值候选均见原函数；没有原始扫描 Source 与完整 codeFlow。

**实参与形参：** 预检查 req→x（位置 1），x→req（位置 0），词法检查均与保存 frame 一致；不能把“准备成功”写成“跨三层实际执行成功”。

**关键条件：** frame 0 的目标条件为空；提前退出列表很长，838 保留大量与 req 关系不明确的条件，带来后续长解释。未对其正确性做完整人工证明。

**LLM 原文与解析：** 837 初始 req==0；838 输出 JSON 列表；839 逐项解释/生成 SMT，finish_reason=length，completion_tokens 达 3072，文本在注释中间截断。

**SMT / Z3 / 最终判定：** 只有不完整生成文本，无最终 solver 文件、无 Z3 查询、无最终判定；保留 failed/null，未用截断内容继续求解。

**审计结论：** 确认输出预算/格式不兼容；空格缩进遗漏分支是另一个已知上游问题，但不能据此断言修缩进必然解决截断。

完整证据：[逐条审计](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/samples/A07/audit.md)；[原始告警](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/samples/A07/original_alert.json)；[调用与求解索引](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/samples/A07/evidence_index.json)。

### A08：两层参数名映射正确，但模型只看到了两个空指针假设

**Source / Sink 与代码链：** radix_sort → radix_sort_pass，最终 Sink dst[pos]=data[i]；原始函数完整保存。

**Source 可恢复性：** radix_sort 第 4 行 tmp=av_malloc(sizeof(*tmp)*size)；未发布精确 Source 或分配失败标注约定。

**实参与形参：** radix_sort_pass(tmp,data,size,buckets[0],0) 的位置 0→dst，其他位置 data→data、size→size、buckets[0]→buckets、0→pass，检查正确。这不能证明跨过程值约束已经传播。

**关键条件：** callee 实际 target_conditions=[]，漏 for(i=0;i<size;i++)；仅改变内存缩进后原提取器返回该循环。

**LLM 原文与解析：** 457–460 四个请求只做 tmp==0、dst==0 及包装函数，没有把完整源码发给模型。磁盘上存在 context.json 不等于模型看到了代码。

**SMT / Z3 / 最终判定：** 第一层 tmp==0 SAT，第二层 dst==0 SAT，最后 keep。缺少 size>0 与分配返回值的语义，无法证明真实运行中的缺陷成立。

**审计结论：** 确认遗漏循环条件和“无代码语义”的空约束路径。源码对分配失败未显式检查，而标签为误报；是否排除 OOM、size 是否可能为 0，需要原数据标注依据，不能武断改标。

完整证据：[逐条审计](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/samples/A08/audit.md)；[原始告警](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/samples/A08/original_alert.json)；[调用与求解索引](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/samples/A08/evidence_index.json)。

### A09：真实缺陷保留对照：求解与最终映射一致，但仍是近似可行

**Source / Sink 与代码链：** 仅 fib6_nh_init；Sink if(idev->cnf.disable_ipv6)。

**Source 可恢复性：** idev 初始 NULL，后有 in6_dev_get 和 ip6_validate_gw 等更新；没有精确 Source 定位，函数代码可见。

**实参与形参：** 无跨函数调用链转换。条件中的函数以未解释函数/整数近似，不等于实际分析过其函数体。

**关键条件：** 目标外层条件为空；提取多个 goto out 等约束，过滤后保留两条含 idev 的复合条件。

**LLM 原文与解析：** 最终尝试调用 49–54；两次生成的 __import__ 被受限 worker 拒绝，最后使用标准 Int/Or 约束。早期失败尝试的调用 20–26 单独列出，未混入最终证据。

**SMT / Z3 / 最终判定：** idev==0 加两个析取约束可满足，最终 SAT→keep，与原 label=1 一致。该结果只验证近似模型可行，不证明完整源码语义。

**审计结论：** 未发现最终保留/过滤映射错误；这是成功对照。修复重试曾改变未解释函数的建模方式，说明“能执行”检查未保证语义保持，列作风险。

完整证据：[逐条审计](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/samples/A09/audit.md)；[原始告警](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/samples/A09/original_alert.json)；[调用与求解索引](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/samples/A09/evidence_index.json)。

### A10：误报正确过滤对照：提前返回和空指针假设构成矛盾

**Source / Sink 与代码链：** 仅 ieee80211_tdls_add_setup_cfm_ies；Sink sta->tdls_chandef=link->conf->chanreq.oper。

**Source 可恢复性：** sta=sta_info_get(sdata,peer)，精确扫描 Source 仍缺；有明确可见保护。

**实参与形参：** 无跨函数转换，tracked=sta。

**关键条件：** 目标条件为空；提前退出含 WARN_ON_ONCE(!sta || !ap_sta)，源码保护位于 Sink 之前。

**LLM 原文与解析：** 最终调用 59–62，得到 ["!(WARN_ON_ONCE(!sta || !ap_sta))"]，按宏返回条件值语义转为 Not(Or(sta==0,ap_sta==0))。先前失败尝试调用 34–40 单独留档。

**SMT / Z3 / 最终判定：** sta==0 ∧ Not(sta==0 ∨ ap_sta==0)，UNSAT→filter，与 label=0 一致；此局部保护与该成员访问相对应。

**审计结论：** 正确过滤对照，未发现最终逻辑/指标问题。宏定义未从整工程展开，因此仍应在报告中保留语义假设。

完整证据：[逐条审计](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/samples/A10/audit.md)；[原始告警](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/samples/A10/original_alert.json)；[调用与求解索引](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/samples/A10/evidence_index.json)。

## 5. 失败分类及数量

下面“确认”指在十条审计样本中观察到该问题，可重复归类，不能相加当成十条或外推到 278 条。待核实项不计为确认根因。

| 类别 | 十条中确认涉及数 | 另有待核实数 |
|---|---:|---:|
| 数据或标签错误 | 10 | 3 |
| 函数代码或调用链恢复错误 | 2 | 0 |
| 实参与形参映射错误 | 0 | 0 |
| 关键条件提取错误 | 4 | 1 |
| LLM变量状态推理错误 | 2 | 0 |
| SMT约束生成或求解错误 | 3 | 1 |
| 最终判定逻辑错误 | 0 | 0 |
| 指标计算错误 | 0 | 0 |
| 模型替换或输出格式不兼容 | 2 | 0 |

“数据或标签”确认数 10 指**全部缺精确 Source**，不是十条错标；已证明错标数为 **0**，A01/A02/A08 有标注或变量路径边界待复核。“实参与形参映射错误”确认数为 0：A04、A07、A08 的位置/参数名检查正确，A05 是条件解析支持边界，不能误诊为参数顺序错。跨过程约束传播存在静态代码风险，另见下文。最终 result=True→keep、False→filter 与最后成功求解在全量 224 条成功记录上一致；未发现全局标签映射、布尔翻转或指标算术错误。

全量日志可确定的失败/弱证据分布：

- **39 条上下文阻塞**：缺函数/宏定义 23，lizard 识别不到单一函数 11，中间调用位置无法唯一定位 4，复合参数/条件 1。缺定义中 kvm_for_each_vcpu 占 13；宏被当作需要查函数也是边界问题，不是都要下载整个工程。
- **15 条执行失败**：JSON 解析 5、输出截断 4、worker 不支持生成操作 2、Z3 sort 错 1、返回布尔与求解不一致 1、Int 位运算错 1、网络超时 1。失败记录未被删除或算作预测正确。
- **301 个已保存 frame**：171 为空格缩进，169 的 target_conditions 为空；130 含 Tab，其中 72 为空。空条件不一定都错误，但三个受控缩进探针已证明该实现会漏掉有效 case/循环条件。
- **70/128 条保留误报**的最后一次查询只有 tracked_var==0（所有标签合计 88 条）。这是缺少有效路径语义的证据模式；不证明 70 条全由缩进导致，也不证明其前置 frame 完全没有约束。
- **301/301 个 frame** 的 variable_assignments.text 都是函数首行：因为传入 var_assignment_statement=None，assignment_line_index 保持 0。这说明不能把该字段当作已恢复 Source；不等于额外证明每条最终判定错误。
- **23 个 frame** 的目标文本在函数中重复出现。提取器按字符串找最后一个命中，未用原告警行号选择具体语句；A03 已见具体歧义。
- **7 条记录**的求解脚本为同名 C 实体创建 Int 和 BitVec 两种符号；6 条是保留误报，1 条是保留真实缺陷。同名跨 sort 导致原始导出的 SMT2 文本无法直接重新载入，原受限 worker 重放仍全部得到原 SAT。这同时暴露语义身份分裂和可追溯格式缺陷；A04 的不同名字版本另有明确实例。
- 224 条成功记录的最终边界中，145 是可见直接解引用，79 是历史宏/调用边界。不能把这 79 条都当“已到达真实缺陷语句”；但仅凭边界类型不能断定结果错。

本次离线重新装载全部 310 个已成功保存的查询：303 个可直接载入，结果全与日志一致；7 个因同名跨 sort 无法直接解析，改用**原始受限 worker 执行原脚本**重放，全与保存结果一致。没有改写 SMT2 以掩盖错误。初次审计脚本遇到该重载异常后，改成显式保留重放错误并执行原 worker；只修改了新建审计脚本。

证据：[全量诊断](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/population_diagnostics.json)；[空格/Tab 与重复目标统计](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/extraction_population_patterns.json)；[五条格式失败](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/format_failures_audit.json)；[七条同名跨 sort 重放](E:/codexconversation/课题研究/reproduction/audit/failure_audit_20261029/same_symbol_sort_audit.json)。

## 6. 最主要的三个问题与最小修复建议

### 优先级 1：关键条件与变量来源没有可靠恢复

证据最充分的是空格缩进：上游 extract_util_plus.py 的 extract_conditions_around_target_with_lines 使用 len(line)-len(line.lstrip('\t'))，空格代码都被算为同一级。在 A03/A06/A08 的内存副本中只转换领先空格，原提取器即从 [] 变为具体 case/循环条件。对同文 Sink 又存在 last-match 歧义。Source 为 None 导致赋值字段变成函数首行；没有真实赋值版本和别名关系。

另一个已确认的静态数据流问题：data_flow_analysis_pipeline 在每个递归 frame 开始用新提取的 target_conditions/early_jump_constraints 覆盖调用者传入值；上下文分析分支 llm_response 只记 response_list，除 Not satisfied 提前退出外，没有加入后续约束合并消息；多层工具调用路径在采用代码中被注释。48 条已有多帧上下文（46 成功、2 执行失败）可能涉及这一边界，**本次没有证明它导致其中多少条错误**。

最小修复拆开做：先修不依赖缩进样式的条件定位与行号消歧，仅离线对照提取列表；然后审查 Source 缺失/变量重赋值，不再把函数头当有效来源。不要直接重写全 C 分析器，也不要未经审查把调用者/被调用者全部约束盲目相 AND。

### 优先级 2：生成和合并脚本的语义保持没有保障

A01 已确认 if(!copied) 极性错误，引入伪矛盾；A04 同指针被拆成 object、object_ptr、object_bv，真矛盾变成假可满足。7 条同名跨 sort 个案进一步支持类型/符号表问题。Z3 正确解答了被提交的公式，问题发生在 C→约束及约束→合并函数之间。

作者原 prompt_templates.py 也存在相互矛盾的指令：通用 z3_prompt_extend 要求 !ptr→ptr==0，但 get_z3_by_goto 写“!ptr to ptr!=0”。bug_line_constraints_prompt_step2 又要求保留全部旧约束并添加新版本，可能让旧的翻译错误保留。该矛盾是文本事实，不证明每个错误都由它造成。

最小修复：首先统一 ! 的真值规则，并为每个变量固定符号/类型；限制合并和语法修复阶段改变约束身份，保留每条约束的代码位置。先做 A01/A04 与七个跨 sort 脚本的离线保真检查，再考虑模型调用。不要先换更贵模型来掩盖语义缺陷。

### 优先级 3：可用上下文和输出契约不足，造成 54 条未分类

上下文阻塞 39、运行失败 15。其中 5 条 JSONDecodeError 都是 regex 抢到 C 块，响应后面已有合法 JSON；4 条输出截断与 3072 token 上限/解释性输出相关。A05 是 WARN_ON(!sta) 条件被复合实参规则误挡，而不是位置映射错。用户替换了模型，但没有相同配置/数据下 GPT-4o-mini 的本地对照，**不能把主要根因定为 DeepSeek 能力弱**。

最小修复：先按标记严格选择 json 代码块并校验数组，不扩大 API 使用；对常见宏/条件建立有出处的有限语义适配；只对确认截断的请求单独设计受预算约束的输出策略。仍然缺代码的样本保持不确定，不默认可行或过滤。

## 7. 修复前后对比计划（尚未执行）

| 步骤 | 单独改变什么 | 样本与验证方式 | 判定目标 |
|---|---|---|---|
| B0 | 不改任何内容 | 当前 278 条冻结基线 | 保留原 64/241、2/37、54 未分类与所有原始日志 |
| R1 | 仅修 JSON 块选择 | 先离线重放五条既有原文 | 5 条能正确解析既有 JSON，非 JSON 拒绝；不宣称五条已完成预测 |
| R2 | 仅修条件提取/同文行定位 | 十条审计集加固定未参与调试的有效标签留出集 | 人工核对提取的 case/循环/提前退出，而非只看过滤率上升 |
| R3 | 仅修符号、类型及否定规则 | A01/A04、七个跨 sort 脚本、A09/A10 对照 | 条件与变量身份一致，反例公式解释明确；不把诊断公式结果算作新实验 |
| R4 | Source/跨 frame 传播 | 只在已核实 Source 和完整调用点的子集上 | 正确实参位置与值约束传播分开验证；未知来源不强行推断 |
| R5 | 冻结修复配置后小规模重跑 | 使用固定 20 条留出清单，并另报十条调试集 | 同模型/预算/数据下逐条配对，失败样本不删除，单独列 changed_predictions |
| R6 | 小规模稳定后才扩展 | 相同 278 个 ID、逐组配对 | 比较过滤率、真实缺陷误删/保留、未分类、费用与耗时；不把调试集提升当泛化结论 |

每步使用独立 revision/run_id 和新输出目录，保存差异、提示词 hash、错误及累计费用；不覆盖 B0。新模型调用继续共享原 10 元总预算，已估算用去 4.491330 元，余额上界约 5.508670 元；本阶段没有触发后续重跑。留出集应在任何新修复前固定，十条目的选样只用于定位；真实缺陷两条误删需先复核数据证据，不能通过改标签“修复指标”。

仅做格式修复/让脚本成功不算解决主要问题。回归验收必须同时检查语义证据、真实缺陷误删变化和未分类；如果只把更多错误编码跑通，指标可能更差。

## 8. 本次交付与复查命令

- 本报告：reproduction/failure_audit.md。
- 审计快照、数据/指标独立核对、十条完整证据、只读探针与人工分类：audit/failure_audit_20261029/。
- 只读诊断脚本：collect_audit.py、offline_probes.py；人工报告生成：write_report.py。freeze.py 首次创建备份后拒绝覆盖；write_report.py 同样拒绝覆盖已有报告。
- 未修改 completion/、upstream/、configs/、scripts/ 或旧 results/；未启动 DSH 或其他新增功能。

最终交付校验可运行（不调用模型）：

```powershell
.\.venv\Scripts\python.exe -B audit/failure_audit_20261029/verify_audit.py
```

本次最小探针仅改变内存中的代码缩进/诊断公式，结果在独立文件，**不是修复后的模型预测或新指标**。建议下一步先批准并实施 R1/R2/R3 中选定的一项，报告完成后本阶段停止。
