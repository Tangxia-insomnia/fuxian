# R01 历史风险案例实际结果

三条均 **UNKNOWN**。来源是 E02 冻结 bundle 的原始 code 字段，字节复制后与原 body_sha256 校验相等，未添加任何声明/宏/头文件。来源路径、bundle hash 和每个 frame hash 见 `historical/results.json`。AST 输出及完整诊断在各子目录的 `frame_*_ast.json`，错误恢复节点没有产生获批映射。

| 用途 | sample_id | 实际定位的调用点（保存函数体一基行号） | 解析诊断数量 |
| --- | --- | --- | --- |
| 首选 | NPD/codeql/kernel69:row=24:index=43 | ip6_finish_output2:77 `sock_confirm_neigh(skb, neigh)`；sock_confirm_neigh:8 `neigh_confirm(n)` | 三帧分别 78、9、6 |
| 备用 | NPD/codeql/libav:row=51:index=84 | mv_read_header:119 `read_index(pb, ast)`；122 `read_index(pb, vst)` | 两帧 148、15 |
| 转换/证据负例 A04 | NPD/codeql/kernel69:row=12:index=24 | tcp_set_allowed_congestion_control:34 `kfree(saved_clone)` | 两帧 22、13 |

任务中简写的 `sock_confirm_neigh(n) → neigh_confirm(n)`，实际源码是 **sock_confirm_neigh 函数内调用 `neigh_confirm(n)`**，不是原文存在一个单参数 `sock_confirm_neigh(n)` 调用。

可见文本提示的 neigh→n、n→n、ast/vst→st、saved_clone→object 均不是本轮已证明的 AST/类型关系。主案例依赖 struct neighbour、宏和全局；备用缺 AVIOContext/AVStream 等 typedef；A04 的 char*→const void* 转换超出本轮支持子集，又缺完整宏/构建。相同类型或变量拼写不作为身份依据。

本轮记录 4 对相邻 frame、5 个字面候选调用点；批准映射 0。函数文本定位来自明确标为 literal_locator 的辅助线索，不能算直接调用证明；dataset_id、position 与 bundle 不解绑。没有执行历史生成代码、模型调用或 Z3。没有重放 E01/E02/E03 运行器，也未改变其既有诊断。
