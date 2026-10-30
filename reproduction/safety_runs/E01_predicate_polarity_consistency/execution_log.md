# E01 执行日志

2026-10-30T11:08:43.072966+08:00：固定输入和既有文件；原reproduction目录不是Git仓库，记录官方上游与已发布快照commit，不虚构补全版commit。

固定清单SHA匹配；保护文件数 3413；开始前账本1187次，估算上界4.491330元。尚未执行候选代码/测试/固定回归集。

2026-10-30T11:20:58.557377+08:00：合成测试：151/151；文件 test_results.json；API 0。

2026-10-30T11:22:14.454728+08:00：合成测试：156/156；文件 test_results.json；API 0。

2026-10-30T11:22:16.395289+08:00：audit 完成：10 条；判定 {'UNKNOWN': 10}；局部冲突样本 1；验收检查 [{'test': 'A01_saved_wrong_polarity_detected', 'passed': True}, {'test': 'A10_macro_not_falsely_flagged', 'passed': True}, {'test': 'A10_stays_UNKNOWN', 'passed': True}, {'test': 'A02_real_bug_not_filtered', 'passed': True}, {'test': 'A04_identity_not_bypassed', 'passed': True}]；API 0。

2026-10-30T11:22:52.747233+08:00：候选代码、合成测试及审计结果已冻结；随后才运行固定20条回归集，不根据回归结果调参。

2026-10-30T11:22:54.735428+08:00：holdout 完成：20 条；判定 {'UNKNOWN': 20}；局部冲突样本 0；验收检查 []；API 0。

2026-10-30T11:23:04.808731+08:00：E01 完成并停止：所有保护文件逐字节哈希未变；固定清单未变；候选冻结校验通过；API 0；未进入R02/R03。
