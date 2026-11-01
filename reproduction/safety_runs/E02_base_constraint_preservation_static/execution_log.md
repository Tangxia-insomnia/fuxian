# E02 实际执行记录

日期：2026-11-02（Asia/Shanghai）。所有 Python 命令使用 `C:/Users/22803/anaconda3/python.exe -B`，没有加载 `.env` 或调用历史项目模块。

1. 检查发布仓库 main 与上游 detached HEAD，均干净。发布基线 `3c419dda0d2f0367d25ca8dba38b86a4f475014e`；上游 `4efb4b9bf7e845e180451b43ba29a25e3edaa0e3`。确认 E02 目录此前不存在。
2. 验证两个固定清单 SHA-256，均与用户指定值一致。在 E02 中建立 `baseline_state.json`，记录原有 3516 个非凭据文件哈希。排除缓存、虚拟环境、Git 元数据和 `.env*`。
3. 新增独立 SMT-LIB S-expression 解析器及历史 Python AST 读取器；不执行输入。检查声明、字面 SMT 身份、sort、断言成员、增量、重复项和最后静态查询快照。
4. 合成开发第 1/2 轮为 30/30、32/32；输入与完整输出保留在 synthetic_cases 和 synthetic_development_01/02.json。
5. 在 32/32 合成验证后运行第一轮 10 条调试检查。发现纯模型打印诊断超出读取子集，且把“仅基础成员”诊断探针混入了全流程状态。增加受限的纯打印诊断支持，诊断探针从全流程汇总中分开。没有执行生成代码。
6. 增加诊断分支不得藏断言的合成测试，34/34 通过；第二轮调试输出与前一轮分别保留。未读取 20 条回归样本的模型响应来调试检查器。
7. 提交冻结前增加查询时点声明快照、保留额外声明的来源检查、保留字校验；37/37 合成测试通过。最终 10 条调试结果：PASS 3、FAIL 2、UNKNOWN 4、NOT_APPLICABLE 1。开发结果文件未覆盖：旧 synthetic_test_results/audit_10_results 重命名为 development 文件，原 evidence 目录仍在，其链接不变；最终候选另写 evidence/audit_10_frozen_candidate。
8. 下一步先执行 `run_e02.py freeze`，记录检查器、runner、测试、配置和合成输入哈希；只有冻结成功后才执行一次 `run_e02.py fixed_20`。实际后续记录在文件末尾追加。

以上开发迭代仅发生于新 E02 目录，不修改算法、不重新生成历史约束；固定 20 条是已经接触过的回归集，不是盲测。

9. `run_e02.py freeze` 成功；时间 `2026-11-02T01:06:38.382155+08:00`。冻结 4 个代码/配置文件和 37 个合成输入。冻结清单还绑定正式调试/合成结果哈希。
10. `run_e02.py fixed_20` 只执行一次，01:06:39 启动、01:06:45 完成：PASS 10、FAIL 2、UNKNOWN 6、NOT_APPLICABLE 2。正式结果含 43 个主转换阶段，17 个 UNKNOWN；没有因这些结果扩大语法支持或重跑。
11. 仅从已写出的 JSON 汇总 metrics、历史案例报告和 E02 报告，未再次调用检查器处理固定集。两个诊断探针类型排除出主转换计数；重复阶段缺失出现次数和按样本/帧/成员去重数分别记录。
12. 对已保存历史 solver source 和选定响应做文本来源匹配：审计 13 份、回归 30 份全部匹配；没有执行其中代码。检查最终样本的 snapshot/source/input 哈希；通过。
13. 再检查原有 3516 个文件哈希和冻结 41 项代码/配置/输入哈希，均未变；JSON、Python AST、本地报告链接通过。静态审阅新代码没有 z3/network/历史项目模块导入，也没有 eval/exec/compile 调用。恶意合成输入的副作用文件不存在。
14. 发布前生成 preservation_check.json 与 hashes.json，只复制和提交 E02 目录。Git 提交/推送结果由提交本身及最终回复记录，避免写入自引用 commit/hash。未启动 Harness、模型或 Z3，API 费用为 0；没有新安全裁决。
