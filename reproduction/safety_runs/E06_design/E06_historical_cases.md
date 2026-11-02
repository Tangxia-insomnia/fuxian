# E06 历史案例与候选样本

本文件是已有源码和历史记录的审查，不是新语义回放结果。所有 body 行号均为保存的函数体一基行号，不冒充绝对源码文件行号。原标签不参与筛选和传播推断。完整 20 条身份、函数签名、目标位置、源码哈希和 bundle 来源见 [candidate_inventory.json](candidate_inventory.json)，文件级 SHA-256 见 [evidence_manifest.json](evidence_manifest.json)。

“候选”仅表示适合某项局部检查；缺少编译/状态证据的完整传播结论仍是 UNKNOWN。不能根据以下样本 ID 编写算法分支。

## 1. 三个既有重点案例

### A01：先作为极性/预处理/旧状态误传播的负向哨兵

- sample_id：`NPD/codeql/kernel69:row=10:index=22`，dataset `benchmark/NPD/codeql/codeql_kernel69_nullpointer.json`，position=10。
- 保存链：`tcp_sendmsg_locked`（单帧）。来源：`safety_runs/E02_base_constraint_preservation_static/evidence/audit_10_frozen_candidate/01/bundle.json#/context/frames/0`。
- body SHA-256：`0a179a0178f81a9211efd84d9baa3efce16afafb9dd8dbe54c47eb63e5064590`。
- 第 7 行 `copied = 0`，64 行 `copied = tcp_send_rcvq(...)`，88 行再次置 0，234 行 `if (!copied)`，235 行目标，241 行 `copied += copy`。目标处 copied 不能仅凭声明初始化确定，也不能与目标后的更新版本合并。
- skb 第 21/100/117 行有赋值/分配；124–126 行存在 `CONFIG_SKB_DECRYPTED` 预处理。不同执行点的 skb 不能用一个名字当同一值。
- 历史 U02 0224 的 `Not(copied == 0)` 与目标真边冲突。E05 新解析器仍因预处理 UNKNOWN，原 E01 保留了局部反向诊断。
- 适合验证：R02 的“状态未绑定时不自动沿用旧值”、R05 的冲突不删除；不适合作为首轮跨函数映射正向案例，因为本样本只有一帧。
- 证据缺口：精确预处理/CFG、调用效果、到目标的 reaching definition。当前不能形成完整传播 PASS。

### A04：直接参数转换与间接别名/宏边界

- sample_id：`NPD/codeql/kernel69:row=12:index=24`，同 dataset，position=12。
- 链：`tcp_set_allowed_congestion_control` → `kfree`。
- 来源：E02 `evidence/audit_10_frozen_candidate/04/bundle.json#/context/frames`。
- caller body SHA-256：`58e06fa2a7bd4630d7cdeab57321ea5d34830a23a0c66231a42cbefe13a77033`；callee：`ce574246eb0cddd842776be658e862604e577e5dee1c5fc3333b9b4f32dccd39`。
- caller 第 4 行声明 `char *saved_clone, *clone, *name`，第 7 行链式赋值 `saved_clone = clone = kstrdup(...)`，13 行 `strsep(&clone, " ")`，26 行 `strsep(&val, " ")`，34 行 `kfree(saved_clone)`；callee 第 1 行形参 `const void *object`。
- 可见的序号对应是第 1 实参 saved_clone → 第 1 形参 object；C 层需要核对 `char *` 到 `const void *` 的合法转换。callee 参数是另一个局部存储单元，入口值可对应，不是把两个声明合并。
- caller 的 saved_clone 和 clone 在第 7 行值相同，不代表 clone 被 `strsep(&clone)` 改写后仍值相同。该函数定义/效果未被本阶段补齐，不根据函数名推断。
- kfree 第 6 行 `x = (void *)object`，10–11 行宏判定后早退，13 行 `folio = virt_to_folio(object)`，14–15 行宏/调用目标。没有宏/完整构建证据，不能用普通 NULL 测试替代 `ZERO_OR_NULL_PTR`。
- 旧 U10/U01/U09 的 B 丢失、object/object_ptr/object_bv 问题由 E02/E03/E05 证据保留。SMT 改名不证明源码对象同一。
- 适合：R01 转换边界、R02 复制后独立更新、R04 地址传参负例；整个样本的状态/路径仍 UNKNOWN，不作为首轮正向基准。

### E04-ND：版本、成员和调用副作用的联合压力案例

- sample_id：`NPD/codeql/kernel69:row=23:index=42`，position=23；链仅保存 `__ip6_append_data` 目标帧。
- 来源：`safety_runs/E04_nonempty_delta_validation/selected_source.c`、`sample_manifest.json` 和 `model_calls/1192–1195.json`。
- body SHA-256：`4f652c2800b05d4fab8cf926af60a66c348cbdd8e5cc95f2620555feaf1e20a9`。
- 175–178 行：两分支分别将 fraggap 赋为 `skb->len - maxfraglen` 或 0；181–183 行传 `&mtu`、`&maxfraglen` 给 `ip6_append_data_mtu`；185 行 `skb_prev = skb`；240–247 行 skb 分配/重赋值；251–252 行空检查/goto；271 行 fraggap 真边；275 行目标 `skb_prev->csum`。
- E05 已诊断 U02 恒真弱化、U06 把成员 `skb->len` 写成指针 `skb`。不能以这些局部发现宣称完整状态已恢复。
- 需验证的版本关系：185 行的 skb_prev 保存的是该点的 skb 值，不能绑定到 240/246 行重赋值后的 skb；176 行读到的 maxfraglen 与潜在调用后版本要区分；fraggap 两个来源属于不同路径，不能无条件同时加入。
- 适合：R02 的旧/新值隔离、R04 的缺副作用摘要阻断、R05 的不同路径分离。不适合作为 R01 正向完整传播样本。
- 缺口：被调方效果、循环/goto CFG、成员定义、unsigned 位宽/溢出、原构建。完整状态仍 UNKNOWN。

## 2. 固定 20 条全部审查

以下序号只是原 manifest 顺序，不是新抽样。统计为 2 条三帧、1 条二帧、15 条单帧、2 条无帧；共 23 帧、5 条相邻边。

| 原序号 | sample_id | 保存调用链 | 推荐用途/边界 |
| --- | --- | --- | --- |
| 1 | `NPD/codeql/openssl:row=30:index=31` | make_ocsp_response → OCSP_copy_nonce → OCSP_BASICRESP_add_ext | 两条直接边；返回值/早退/成员地址参数，R03–R05；typedef、宏和库效果缺失 |
| 2 | `NPD/codeql/kernel69:row=33:index=53` | ip6_route_info_create | 单帧成员/分配状态候选；不能据此验证跨函数 |
| 3 | `NPD/codeql/openssl:row=6:index=7` | cms_main | 条件中函数调用，缺 callee/效果，UNKNOWN |
| 4 | `NPD/infer/openssl:row=11:index=None` | ossl_quic_tls_is_cert_request | 单帧成员访问，跨函数证据不足 |
| 5 | `NPD/codeql/openssl:row=20:index=21` | engine_main | 被跟踪表达式为复合函数结果，不是普通声明变量；负向边界 |
| 6 | `NPD/codeql/kernel69:row=17:index=36` | ipv6_route_native_seq_show | 单帧，成员/上下文边界 |
| 7 | `NPD/codeql/kernel69:row=15:index=31` | udp_gro_receive_segment | 单帧成员条件，宏/类型边界 |
| 8 | `NPD/codeql/libav:row=50:index=83` | mpegts_write_header | 单帧成员/赋值，跨函数证据不足 |
| 9 | `NPD/cppcheck/linux:row=63:index=None` | dwarf_lookup_cie | 单帧迭代/成员，适合 UNKNOWN 哨兵 |
| 10 | `NPD/cppcheck/openssl:row=2:index=None` | list_insert_sorted | cmp(p,n) 函数指针与循环；不自动映射为唯一直接函数 |
| 11 | `NPD/codeql/openssl:row=15:index=16` | ec_main | 外部函数及 opaque 类型不足，UNKNOWN |
| 12 | `NPD/codeql/libav:row=51:index=84` | mv_read_header → read_index | 明确第 2 实参映射；同一 callee 两调用点，适合 R01/R05 |
| 13 | `NPD/cppcheck/linux:row=13:index=None` | 无已保存帧 | 保留缺上下文负例，不补造源码 |
| 14 | `NPD/codeql/libav:row=32:index=47` | check_intra_mode | memcpy 指针/间接表达式；无跨帧证据 |
| 15 | `NPD/infer/openssl:row=1:index=None` | opt_provider_path | 嵌套调用与缺少 callee，不猜库效果 |
| 16 | `NPD/codeql/kernel69:row=26:index=45` | 无已保存帧 | 保留缺上下文负例 |
| 17 | `NPD/codeql/kernel69:row=24:index=43` | ip6_finish_output2 → sock_confirm_neigh → neigh_confirm | 最短的直接标识符参数边优先候选；宏/共享状态使完整语义仍 UNKNOWN |
| 18 | `NPD/codeql/libav:row=19:index=26` | epic_decode_from_cache | 单帧成员写入/别名边界 |
| 19 | `NPD/codeql/openssl:row=16:index=17` | ecparam_main | 外部调用/opaque 类型，UNKNOWN |
| 20 | `NPD/codeql/libav:row=35:index=51` | swap_sample_fmts_on_filter | 多级成员表达式；不按共享根名字合并 |

本阶段没有重新调用 MCP、检索新增定义或运行固定集检查器；没有将上述条件标记为已通过传播测试。

## 3. 最值得优先准备的三条真实候选

### 首选：固定序号 17 的局部调用边

`ip6_finish_output2` 第 77 行 `sock_confirm_neigh(skb, neigh);`，第 2 实参 neigh 对应 `sock_confirm_neigh` 的形参 n；后者第 8 行 `neigh_confirm(n);`，第 1 实参 n 对应 `neigh_confirm` 的形参 n。即使同名 n，也须保留不同 frame/声明/slot 身份。

body SHA-256 依次为：`90b47239055d70d6940ddc13e68fc1f3e80746d0d735ccb383f25c4c6471a940`、`f1da49e2aae11fd06c3bb6761f4ce114038e33b2972c382a709fbc3694b12c55`、`468f1bceeb2bb427c7a70f1345ed27aa19925bbfcf2197e94b7f6476cc260be9`。

首轮只考察“如果执行这个已定位调用点，入口参数值怎样对应”，不证明该调用点可达。callee 的 `if (n)` 第 3 行可作后续目标路径条件，但 READ_ONCE/WRITE_ONCE、jiffies 和共享写入不在首轮范围。`struct neighbour` 同拼写仍需声明/构建证据确认类型身份；初始材料不足时局部类型绑定也必须 UNKNOWN，不能拿拼写相同冒充证明。

### 备用：固定序号 12 的参数序号与调用点区分

`mv_read_header` 第 119 行 `read_index(pb, ast);`，形参 `AVIOContext *pb, AVStream *st` 位于 `read_index` 第 1 行；第 2 实参 ast → st，第 1 实参 pb → pb。caller 第 122 行还有 `read_index(pb, vst);`，必须有不同 callsite_id/context，不能因 callee 相同复用 ast 的前提。

body SHA-256：caller `46dee8cc0b2c4fa52c15df0d9917878f43ccc59f3782cc6850f71eaceb32bb18`，callee `9724748f31ef6473e29e23af904257a18b7539cf1d1fbc32db941a8f38d8b1c3`。

第 18/85 行 ast 分配、第 19/86 行空检查以及 118 行 nb_audio_tracks 条件属于不同路径；缺外部函数摘要、typedef 与全路径证明，完整传播仍 UNKNOWN。callee 循环/流读取也超出首轮。

### 后续：固定序号 1 的返回值/副作用/提前退出

`make_ocsp_response` 第 112 行 `OCSP_copy_nonce(bs, req);`，bs → resp（第 1 参数）；`OCSP_copy_nonce` 第 11 行 `return OCSP_BASICRESP_add_ext(resp, req_ext, -1);`，resp → x。第 8–9 行 req_idx<0 返回 2 的路径不能带入第 11 行路径；caller 第 112 行没有接收返回值，不能凭 callee 的成功/失败返回约束擅自约束 caller 后续。

body SHA-256：`0710255ad6325f07f68ca2e2b35754df6a9c26fbf063e37b6c9f66555683feca`、`499cdf9bcc70527e68a41f7407467a408c1fe64c229d186e17158c1a97e28f24`、`2d430324a39502c9653fa8bc64736b541098f2452ca8d0ddb2c509464d28b924`。

末帧第 3 行 `&(x->tbsResponseData.responseExtensions)` 是成员地址和潜在间接修改，不能当成参数 x 的标量赋值。适合作后几轮边界案例，不能在缺类型/定义时自动补全。

## 4. 候选使用结论

现有材料足以设计和定位上述局部关系，但没有一条被本阶段认证为完整跨函数传播正向案例。优先用真实候选验证证据缺口会显式阻断；正式实现的正向单元测试应使用明确标记的合成自包含 C 程序，真实材料继续保留 UNKNOWN，直到原始证据和支持范围满足要求。
