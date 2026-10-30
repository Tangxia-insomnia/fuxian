# 阶段 7：用户授权扩大实验

当前状态：8 组 NPD 全部 278 个有效标签样本已保存结果并通过核验；成功执行 224、上下文阻塞 39、运行失败 15。最终报告见 results/final_report.md。

用户于 2026-10-26 明确授权尝试扩大全量实验。继续沿用累计 10 元预算、原模型配置及补全版 NPD 算法。先覆盖官方 CodeQL/Linux 的全部 70 条，再核查其他 NPD 分组能否使用同一流程。

扩展只增加数据集/历史上下文路径参数和批量入口；提示词、空指针条件、原分析函数、求解修复次数均保持不变。原 25 条样本复用已保存最终结果（含 4 条阻塞），避免重复调用；早期失败尝试仍保留。

Infer/Libav 将函数字符串命名为 func_info，扩展读取时仅在内存映射到 function_code；不更改原始 JSON，不增加代码或条件。扩展参数化后原 10 项基础设施测试通过，实际输出见 results/raw/completed/expansion_regression_tests.txt。

其他缺陷类型需要相应的缺陷触发条件和实现，不能将空指针 `var == 0` 直接套用于 UAF、越界等类型；全部文件仍做范围清点并记录未运行原因。已有 -1、缺失标签不补标签、不纳入监督指标。

小样本最终报告、核验记录和源代码哈希先保存到 results/archive/before_expanded_experiment/。扩展后的上下文类新增可选参数，旧默认值保持原行为；完整基准对应关系仍不确定，不能声称复现全部论文。


## codeql_linux 预检查

全部 70 条，现有 0/1 标签 70 条，预检查就绪 53 条。清单和阻塞原因已保存；预检查不作为结果筛选条件。


## 补全版 expanded_codeql_linux 开始

时间：2026-10-26T00:46:41.191590+08:00。样本原始行号：[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69]。下列运行属于补全实现，原始实现诊断记录保留。


- 样本 `NPD/codeql/kernel69:row=0:index=0`：success；预测=filter；调用=4；Z3 成功=1；耗时=4.757s；费用保守上界=0.021292 元；错误=None。


- 样本 `NPD/codeql/kernel69:row=1:index=1`：success；预测=filter；调用=8；Z3 成功=2；耗时=19.984s；费用保守上界=0.063340 元；错误=None。


## codeql_linux 预检查

全部 70 条，现有 0/1 标签 70 条，预检查就绪 53 条。清单和阻塞原因已保存；预检查不作为结果筛选条件。


## codeql_libav 预检查

全部 57 条，现有 0/1 标签 57 条，预检查就绪 53 条。清单和阻塞原因已保存；预检查不作为结果筛选条件。


## codeql_openssl 预检查

全部 50 条，现有 0/1 标签 49 条，预检查就绪 49 条。清单和阻塞原因已保存；预检查不作为结果筛选条件。


## cppcheck_linux 预检查

全部 594 条，现有 0/1 标签 65 条，预检查就绪 47 条。清单和阻塞原因已保存；预检查不作为结果筛选条件。


## cppcheck_libav 预检查

全部 10 条，现有 0/1 标签 10 条，预检查就绪 10 条。清单和阻塞原因已保存；预检查不作为结果筛选条件。


## cppcheck_openssl 预检查

全部 5 条，现有 0/1 标签 5 条，预检查就绪 5 条。清单和阻塞原因已保存；预检查不作为结果筛选条件。


## infer_libav 预检查

全部 6 条，现有 0/1 标签 6 条，预检查就绪 6 条。清单和阻塞原因已保存；预检查不作为结果筛选条件。


## infer_openssl 预检查

全部 16 条，现有 0/1 标签 16 条，预检查就绪 16 条。清单和阻塞原因已保存；预检查不作为结果筛选条件。


- 样本 `NPD/codeql/kernel69:row=2:index=2`：success；预测=filter；调用=8；Z3 成功=2；耗时=19.775s；费用保守上界=0.062836 元；错误=None。


- 样本 `NPD/codeql/kernel69:row=3:index=3`：success；预测=filter；调用=5；Z3 成功=1；耗时=7.575s；费用保守上界=0.016074 元；错误=None。


- 样本 `NPD/codeql/kernel69:row=5:index=5`：blocked_context；预测=None；调用=0；Z3 成功=0；耗时=0.002s；费用保守上界=0.000000 元；错误=Expected one function definition, found 0。


- 样本 `NPD/codeql/kernel69:row=6:index=6`：blocked_context；预测=None；调用=0；Z3 成功=0；耗时=0.001s；费用保守上界=0.000000 元；错误=Expected one function definition, found 0。


- 样本 `NPD/codeql/kernel69:row=7:index=7`：success；预测=keep；调用=7；Z3 成功=2；耗时=8.135s；费用保守上界=0.018016 元；错误=None。


- 样本 `NPD/codeql/kernel69:row=9:index=21`：blocked_context；预测=None；调用=0；Z3 成功=0；耗时=0.014s；费用保守上界=0.000000 元；错误=Function skb_zcopy_pure: 0 distinct available definitions。


- 样本 `NPD/codeql/kernel69:row=10:index=22`：success；预测=filter；调用=4；Z3 成功=1；耗时=4.622s；费用保守上界=0.018030 元；错误=None。


- 样本 `NPD/codeql/kernel69:row=12:index=24`：success；预测=keep；调用=11；Z3 成功=3；耗时=11.912s；费用保守上界=0.020672 元；错误=None。


- 样本 `NPD/codeql/kernel69:row=14:index=29`：blocked_context；预测=None；调用=0；Z3 成功=0；耗时=0.016s；费用保守上界=0.000000 元；错误=Function IS_ERR_OR_NULL: 0 distinct available definitions。


- 样本 `NPD/codeql/kernel69:row=15:index=31`：success；预测=keep；调用=2；Z3 成功=1；耗时=1.267s；费用保守上界=0.001720 元；错误=None。


- 样本 `NPD/codeql/kernel69:row=17:index=36`：success；预测=keep；调用=2；Z3 成功=1；耗时=1.622s；费用保守上界=0.001888 元；错误=None。


- 样本 `NPD/codeql/kernel69:row=18:index=37`：success；预测=keep；调用=7；Z3 成功=2；耗时=8.203s；费用保守上界=0.020080 元；错误=None。


- 样本 `NPD/codeql/kernel69:row=19:index=38`：blocked_context；预测=None；调用=0；Z3 成功=0；耗时=0.005s；费用保守上界=0.000000 元；错误=Cannot uniquely locate intermediate call site。


- 样本 `NPD/codeql/kernel69:row=20:index=39`：success；预测=keep；调用=16；Z3 成功=6；耗时=15.993s；费用保守上界=0.019682 元；错误=None。


- 样本 `NPD/codeql/kernel69:row=24:index=43`：success；预测=keep；调用=14；Z3 成功=3；耗时=18.524s；费用保守上界=0.036526 元；错误=None。


- 样本 `NPD/codeql/kernel69:row=26:index=45`：blocked_context；预测=None；调用=0；Z3 成功=0；耗时=0.001s；费用保守上界=0.000000 元；错误=Expected one function definition, found 0。


- 样本 `NPD/codeql/kernel69:row=28:index=47`：blocked_context；预测=None；调用=0；Z3 成功=0；耗时=0.001s；费用保守上界=0.000000 元；错误=Expected one function definition, found 0。


- 样本 `NPD/codeql/kernel69:row=29:index=48`：success；预测=keep；调用=9；Z3 成功=3；耗时=10.759s；费用保守上界=0.026772 元；错误=None。


- 样本 `NPD/codeql/kernel69:row=30:index=49`：blocked_context；预测=None；调用=0；Z3 成功=0；耗时=0.003s；费用保守上界=0.000000 元；错误=Expected one function definition, found 0。


- 样本 `NPD/codeql/kernel69:row=32:index=52`：blocked_context；预测=None；调用=0；Z3 成功=0；耗时=0.003s；费用保守上界=0.000000 元；错误=Function rt6_is_dead: 0 distinct available definitions。


- 样本 `NPD/codeql/kernel69:row=33:index=53`：success；预测=keep；调用=9；Z3 成功=2；耗时=16.988s；费用保守上界=0.046106 元；错误=None。


- 样本 `NPD/codeql/kernel69:row=37:index=58`：success；预测=keep；调用=4；Z3 成功=1；耗时=7.431s；费用保守上界=0.014140 元；错误=None。


- 样本 `NPD/codeql/kernel69:row=38:index=59`：blocked_context；预测=None；调用=0；Z3 成功=0；耗时=0.018s；费用保守上界=0.000000 元；错误=Function IS_ERR_OR_NULL: 0 distinct available definitions。


- 样本 `NPD/codeql/kernel69:row=39:index=63`：success；预测=filter；调用=9；Z3 成功=3；耗时=12.775s；费用保守上界=0.018458 元；错误=None。


- 样本 `NPD/codeql/kernel69:row=40:index=64`：success；预测=filter；调用=4；Z3 成功=1；耗时=4.445s；费用保守上界=0.005362 元；错误=None。


- 样本 `NPD/codeql/kernel69:row=44:index=69`：success；预测=filter；调用=16；Z3 成功=4；耗时=26.772s；费用保守上界=0.060082 元；错误=None。


- 样本 `NPD/codeql/kernel69:row=49:index=75`：blocked_context；预测=None；调用=0；Z3 成功=0；耗时=0.008s；费用保守上界=0.000000 元；错误=Cannot uniquely locate intermediate call site。


- 样本 `NPD/codeql/kernel69:row=51:index=77`：success；预测=keep；调用=4；Z3 成功=1；耗时=4.011s；费用保守上界=0.012036 元；错误=None。


- 样本 `NPD/codeql/kernel69:row=52:index=78`：success；预测=filter；调用=11；Z3 成功=3；耗时=17.371s；费用保守上界=0.031982 元；错误=None。


- 样本 `NPD/codeql/kernel69:row=53:index=79`：success；预测=filter；调用=4；Z3 成功=1；耗时=4.052s；费用保守上界=0.007020 元；错误=None。


- 样本 `NPD/codeql/kernel69:row=54:index=80`：success；预测=keep；调用=10；Z3 成功=3；耗时=14.454s；费用保守上界=0.032054 元；错误=None。


- 样本 `NPD/codeql/kernel69:row=55:index=81`：blocked_context；预测=None；调用=0；Z3 成功=0；耗时=0.008s；费用保守上界=0.000000 元；错误=Tracked value passed via an unsupported compound argument。


- 样本 `NPD/codeql/kernel69:row=57:index=85`：success；预测=keep；调用=4；Z3 成功=1；耗时=3.832s；费用保守上界=0.007258 元；错误=None。


- 样本 `NPD/codeql/kernel69:row=58:index=88`：success；预测=keep；调用=11；Z3 成功=3；耗时=13.863s；费用保守上界=0.023440 元；错误=None。


- 样本 `NPD/codeql/kernel69:row=60:index=90`：success；预测=keep；调用=5；Z3 成功=1；耗时=5.512s；费用保守上界=0.009778 元；错误=None。


- 样本 `NPD/codeql/kernel69:row=61:index=91`：success；预测=keep；调用=5；Z3 成功=1；耗时=7.263s；费用保守上界=0.022240 元；错误=None。


- 样本 `NPD/codeql/kernel69:row=62:index=92`：success；预测=filter；调用=12；Z3 成功=3；耗时=15.187s；费用保守上界=0.023588 元；错误=None。


- 样本 `NPD/codeql/kernel69:row=63:index=93`：blocked_context；预测=None；调用=0；Z3 成功=0；耗时=0.002s；费用保守上界=0.000000 元；错误=Expected one function definition, found 0。


- 样本 `NPD/codeql/kernel69:row=64:index=94`：success；预测=keep；调用=3；Z3 成功=1；耗时=2.483s；费用保守上界=0.004520 元；错误=None。


- 样本 `NPD/codeql/kernel69:row=66:index=96`：success；预测=filter；调用=4；Z3 成功=1；耗时=4.802s；费用保守上界=0.007698 元；错误=None。


- 样本 `NPD/codeql/kernel69:row=67:index=97`：success；预测=keep；调用=4；Z3 成功=1；耗时=5.089s；费用保守上界=0.008460 元；错误=None。


- 样本 `NPD/codeql/kernel69:row=68:index=98`：success；预测=filter；调用=7；Z3 成功=2；耗时=8.713s；费用保守上界=0.031510 元；错误=None。


- 样本 `NPD/codeql/kernel69:row=69:index=99`：success；预测=keep；调用=4；Z3 成功=1；耗时=4.895s；费用保守上界=0.011984 元；错误=None。


## codeql_linux 预检查

全部 70 条，现有 0/1 标签 70 条，预检查就绪 53 条。清单和阻塞原因已保存；预检查不作为结果筛选条件。


## 补全版 expanded_codeql_linux 开始

时间：2026-10-26T00:52:01.096281+08:00。样本原始行号：[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69]。下列运行属于补全实现，原始实现诊断记录保留。


### codeql_linux 阶段保存完成

已记录 70 条，成功执行 53、阻塞 17、失败 0。分组 CSV/JSON、指标及原始输出均已保存后再进入下一组。


## codeql_libav 预检查

全部 57 条，现有 0/1 标签 57 条，预检查就绪 53 条。清单和阻塞原因已保存；预检查不作为结果筛选条件。


## 补全版 expanded_codeql_libav 开始

时间：2026-10-26T00:52:01.815197+08:00。样本原始行号：[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56]。下列运行属于补全实现，原始实现诊断记录保留。


- 样本 `NPD/codeql/libav:row=0:index=3`：blocked_context；预测=None；调用=0；Z3 成功=0；耗时=0.004s；费用保守上界=0.000000 元；错误=Expected one function definition, found 0。


- 样本 `NPD/codeql/libav:row=1:index=4`：blocked_context；预测=None；调用=0；Z3 成功=0；耗时=0.002s；费用保守上界=0.000000 元；错误=Expected one function definition, found 0。


- 样本 `NPD/codeql/libav:row=2:index=5`：blocked_context；预测=None；调用=0；Z3 成功=0；耗时=0.003s；费用保守上界=0.000000 元；错误=Expected one function definition, found 0。


- 样本 `NPD/codeql/libav:row=3:index=8`：success；预测=keep；调用=4；Z3 成功=1；耗时=4.942s；费用保守上界=0.010112 元；错误=None。


- 样本 `NPD/codeql/libav:row=4:index=9`：success；预测=keep；调用=6；Z3 成功=2；耗时=6.812s；费用保守上界=0.011414 元；错误=None。


- 样本 `NPD/codeql/libav:row=5:index=10`：success；预测=keep；调用=6；Z3 成功=2；耗时=6.765s；费用保守上界=0.011416 元；错误=None。


- 样本 `NPD/codeql/libav:row=6:index=11`：success；预测=keep；调用=4；Z3 成功=1；耗时=5.533s；费用保守上界=0.011362 元；错误=None。


- 样本 `NPD/codeql/libav:row=7:index=14`：success；预测=keep；调用=3；Z3 成功=1；耗时=1.932s；费用保守上界=0.007292 元；错误=None。


- 样本 `NPD/codeql/libav:row=8:index=15`：success；预测=keep；调用=3；Z3 成功=1；耗时=2.147s；费用保守上界=0.007388 元；错误=None。


- 样本 `NPD/codeql/libav:row=9:index=16`：success；预测=keep；调用=3；Z3 成功=1；耗时=2.218s；费用保守上界=0.007388 元；错误=None。


- 样本 `NPD/codeql/libav:row=10:index=17`：success；预测=keep；调用=3；Z3 成功=1；耗时=2.504s；费用保守上界=0.007388 元；错误=None。


- 样本 `NPD/codeql/libav:row=11:index=18`：success；预测=keep；调用=3；Z3 成功=1；耗时=2.328s；费用保守上界=0.007388 元；错误=None。


- 样本 `NPD/codeql/libav:row=12:index=19`：success；预测=keep；调用=3；Z3 成功=1；耗时=2.671s；费用保守上界=0.004742 元；错误=None。


- 样本 `NPD/codeql/libav:row=13:index=20`：success；预测=keep；调用=4；Z3 成功=2；耗时=3.390s；费用保守上界=0.003422 元；错误=None。


- 样本 `NPD/codeql/libav:row=14:index=21`：success；预测=keep；调用=3；Z3 成功=1；耗时=2.099s；费用保守上界=0.006350 元；错误=None。


- 样本 `NPD/codeql/libav:row=15:index=22`：success；预测=keep；调用=3；Z3 成功=1；耗时=2.078s；费用保守上界=0.003254 元；错误=None。


- 样本 `NPD/codeql/libav:row=16:index=23`：success；预测=keep；调用=6；Z3 成功=2；耗时=6.532s；费用保守上界=0.009046 元；错误=None。


- 样本 `NPD/codeql/libav:row=17:index=24`：success；预测=keep；调用=3；Z3 成功=1；耗时=1.731s；费用保守上界=0.003254 元；错误=None。


- 样本 `NPD/codeql/libav:row=18:index=25`：success；预测=keep；调用=3；Z3 成功=1；耗时=2.315s；费用保守上界=0.003312 元；错误=None。


- 样本 `NPD/codeql/libav:row=19:index=26`：success；预测=keep；调用=3；Z3 成功=1；耗时=1.979s；费用保守上界=0.002446 元；错误=None。


- 样本 `NPD/codeql/libav:row=20:index=27`：success；预测=keep；调用=4；Z3 成功=1；耗时=6.809s；费用保守上界=0.012674 元；错误=None。


- 样本 `NPD/codeql/libav:row=21:index=28`：success；预测=keep；调用=4；Z3 成功=1；耗时=6.904s；费用保守上界=0.012898 元；错误=None。


- 样本 `NPD/codeql/libav:row=22:index=29`：failed；预测=None；调用=7；Z3 成功=0；耗时=21.523s；费用保守上界=0.072680 元；错误=RuntimeError: Z3 repair attempts exhausted: Z3Exception: Z3 sort expected。


- 样本 `NPD/codeql/libav:row=23:index=30`：success；预测=keep；调用=3；Z3 成功=1；耗时=4.917s；费用保守上界=0.006924 元；错误=None。


- 样本 `NPD/codeql/libav:row=24:index=31`：success；预测=keep；调用=3；Z3 成功=1；耗时=2.448s；费用保守上界=0.002444 元；错误=None。


- 样本 `NPD/codeql/libav:row=25:index=32`：success；预测=keep；调用=4；Z3 成功=1；耗时=4.272s；费用保守上界=0.007946 元；错误=None。


- 样本 `NPD/codeql/libav:row=26:index=33`：success；预测=keep；调用=4；Z3 成功=1；耗时=4.401s；费用保守上界=0.010444 元；错误=None。


- 样本 `NPD/codeql/libav:row=27:index=34`：success；预测=keep；调用=3；Z3 成功=1；耗时=2.427s；费用保守上界=0.007234 元；错误=None。


- 样本 `NPD/codeql/libav:row=28:index=35`：success；预测=keep；调用=3；Z3 成功=1；耗时=2.510s；费用保守上界=0.007234 元；错误=None。


- 样本 `NPD/codeql/libav:row=29:index=37`：failed；预测=None；调用=7；Z3 成功=0；耗时=8.189s；费用保守上界=0.022122 元；错误=RuntimeError: Z3 repair attempts exhausted: ValueError: Returned boolean disagrees with last solver result。


- 样本 `NPD/codeql/libav:row=30:index=38`：success；预测=keep；调用=8；Z3 成功=2；耗时=14.087s；费用保守上界=0.025474 元；错误=None。


- 样本 `NPD/codeql/libav:row=31:index=46`：success；预测=keep；调用=3；Z3 成功=1；耗时=2.715s；费用保守上界=0.002574 元；错误=None。


- 样本 `NPD/codeql/libav:row=32:index=47`：success；预测=keep；调用=2；Z3 成功=1；耗时=1.602s；费用保守上界=0.001702 元；错误=None。


- 样本 `NPD/codeql/libav:row=33:index=48`：success；预测=keep；调用=2；Z3 成功=1；耗时=1.768s；费用保守上界=0.001702 元；错误=None。


- 样本 `NPD/codeql/libav:row=34:index=49`：success；预测=keep；调用=2；Z3 成功=1；耗时=1.614s；费用保守上界=0.001814 元；错误=None。


- 样本 `NPD/codeql/libav:row=35:index=51`：success；预测=keep；调用=4；Z3 成功=1；耗时=5.597s；费用保守上界=0.009244 元；错误=None。


- 样本 `NPD/codeql/libav:row=36:index=52`：success；预测=keep；调用=4；Z3 成功=1；耗时=8.308s；费用保守上界=0.013382 元；错误=None。


- 样本 `NPD/codeql/libav:row=37:index=53`：success；预测=keep；调用=4；Z3 成功=1；耗时=7.141s；费用保守上界=0.012728 元；错误=None。


- 样本 `NPD/codeql/libav:row=38:index=54`：success；预测=keep；调用=4；Z3 成功=2；耗时=3.602s；费用保守上界=0.003506 元；错误=None。


- 样本 `NPD/codeql/libav:row=39:index=62`：blocked_context；预测=None；调用=0；Z3 成功=0；耗时=0.001s；费用保守上界=0.000000 元；错误=Expected one function definition, found 0。


- 样本 `NPD/codeql/libav:row=40:index=68`：success；预测=keep；调用=2；Z3 成功=1；耗时=1.463s；费用保守上界=0.001720 元；错误=None。


- 样本 `NPD/codeql/libav:row=41:index=69`：success；预测=keep；调用=2；Z3 成功=1；耗时=1.300s；费用保守上界=0.001720 元；错误=None。


- 样本 `NPD/codeql/libav:row=42:index=72`：success；预测=keep；调用=3；Z3 成功=1；耗时=3.572s；费用保守上界=0.005050 元；错误=None。


- 样本 `NPD/codeql/libav:row=43:index=73`：success；预测=keep；调用=4；Z3 成功=1；耗时=7.897s；费用保守上界=0.020718 元；错误=None。


- 样本 `NPD/codeql/libav:row=44:index=74`：success；预测=keep；调用=4；Z3 成功=1；耗时=5.234s；费用保守上界=0.008908 元；错误=None。


- 样本 `NPD/codeql/libav:row=45:index=75`：success；预测=keep；调用=4；Z3 成功=1；耗时=7.891s；费用保守上界=0.015270 元；错误=None。


- 样本 `NPD/codeql/libav:row=46:index=76`：success；预测=keep；调用=5；Z3 成功=1；耗时=7.584s；费用保守上界=0.017130 元；错误=None。


- 样本 `NPD/codeql/libav:row=47:index=78`：success；预测=keep；调用=4；Z3 成功=1；耗时=4.739s；费用保守上界=0.009418 元；错误=None。


- 样本 `NPD/codeql/libav:row=48:index=79`：success；预测=keep；调用=3；Z3 成功=1；耗时=2.565s；费用保守上界=0.003142 元；错误=None。


- 样本 `NPD/codeql/libav:row=49:index=80`：success；预测=keep；调用=3；Z3 成功=1；耗时=2.076s；费用保守上界=0.003142 元；错误=None。


- 样本 `NPD/codeql/libav:row=50:index=83`：success；预测=keep；调用=3；Z3 成功=1；耗时=2.009s；费用保守上界=0.007458 元；错误=None。


- 样本 `NPD/codeql/libav:row=51:index=84`：success；预测=keep；调用=6；Z3 成功=2；耗时=8.598s；费用保守上界=0.017688 元；错误=None。


- 样本 `NPD/codeql/libav:row=52:index=85`：success；预测=keep；调用=6；Z3 成功=2；耗时=5.991s；费用保守上界=0.013846 元；错误=None。


- 样本 `NPD/codeql/libav:row=53:index=86`：success；预测=keep；调用=3；Z3 成功=1；耗时=2.708s；费用保守上界=0.010660 元；错误=None。


## 全部 NPD 组的离线核验

8 组 278 个有效标签记录均已完成无需模型的预检查；239 条就绪，39 条上下文阻塞。该就绪数不等于最终成功数。标签交叉核查见 results/processed/expanded_label_audit.json；结果字段的 -1/缺失保持未知。


- 样本 `NPD/codeql/libav:row=54:index=95`：success；预测=keep；调用=8；Z3 成功=2；耗时=8.433s；费用保守上界=0.015804 元；错误=None。


- 样本 `NPD/codeql/libav:row=55:index=96`：success；预测=keep；调用=3；Z3 成功=1；耗时=1.949s；费用保守上界=0.002928 元；错误=None。


- 样本 `NPD/codeql/libav:row=56:index=97`：success；预测=keep；调用=4；Z3 成功=1；耗时=9.594s；费用保守上界=0.026686 元；错误=None。


### codeql_libav 阶段保存完成

已记录 57 条，成功执行 51、阻塞 4、失败 2。分组 CSV/JSON、指标及原始输出均已保存后再进入下一组。


## codeql_openssl 预检查

全部 50 条，现有 0/1 标签 49 条，预检查就绪 49 条。清单和阻塞原因已保存；预检查不作为结果筛选条件。


## 补全版 expanded_codeql_openssl 开始

时间：2026-10-26T00:56:16.733438+08:00。样本原始行号：[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49]。下列运行属于补全实现，原始实现诊断记录保留。


- 样本 `NPD/codeql/openssl:row=0:index=0`：success；预测=keep；调用=7；Z3 成功=2；耗时=7.702s；费用保守上界=0.022632 元；错误=None。


- 样本 `NPD/codeql/openssl:row=1:index=1`：success；预测=keep；调用=6；Z3 成功=2；耗时=6.912s；费用保守上界=0.031302 元；错误=None。


- 样本 `NPD/codeql/openssl:row=2:index=2`：success；预测=keep；调用=13；Z3 成功=5；耗时=16.621s；费用保守上界=0.053146 元；错误=None。


- 样本 `NPD/codeql/openssl:row=3:index=3`：success；预测=keep；调用=11；Z3 成功=3；耗时=18.567s；费用保守上界=0.097568 元；错误=None。


- 样本 `NPD/codeql/openssl:row=4:index=5`：success；预测=keep；调用=3；Z3 成功=1；耗时=3.302s；费用保守上界=0.004824 元；错误=None。


- 样本 `NPD/codeql/openssl:row=5:index=6`：success；预测=keep；调用=4；Z3 成功=1；耗时=5.632s；费用保守上界=0.027200 元；错误=None。


- 样本 `NPD/codeql/openssl:row=6:index=7`：success；预测=keep；调用=4；Z3 成功=1；耗时=6.664s；费用保守上界=0.032710 元；错误=None。


- 样本 `NPD/codeql/openssl:row=7:index=8`：success；预测=keep；调用=5；Z3 成功=1；耗时=7.646s；费用保守上界=0.037246 元；错误=None。


- 样本 `NPD/codeql/openssl:row=8:index=9`：success；预测=keep；调用=9；Z3 成功=3；耗时=10.267s；费用保守上界=0.041038 元；错误=None。


- 样本 `NPD/codeql/openssl:row=9:index=10`：success；预测=keep；调用=4；Z3 成功=1；耗时=5.867s；费用保守上界=0.034098 元；错误=None。


- 样本 `NPD/codeql/openssl:row=10:index=11`：failed；预测=None；调用=7；Z3 成功=0；耗时=40.014s；费用保守上界=0.182646 元；错误=RuntimeError: Z3 repair attempts exhausted: TypeError: unsupported operand type(s) for &: 'ArithRef' and 'ArithRef'。


- 样本 `NPD/codeql/openssl:row=11:index=12`：success；预测=keep；调用=4；Z3 成功=1；耗时=4.348s；费用保守上界=0.028688 元；错误=None。


- 样本 `NPD/codeql/openssl:row=12:index=13`：success；预测=keep；调用=8；Z3 成功=2；耗时=11.980s；费用保守上界=0.024996 元；错误=None。


- 样本 `NPD/codeql/openssl:row=13:index=14`：failed；预测=None；调用=7；Z3 成功=0；耗时=10.982s；费用保守上界=0.030788 元；错误=RuntimeError: Z3 repair attempts exhausted: ValueError: Unsupported generated-code operation。


- 样本 `NPD/codeql/openssl:row=14:index=15`：success；预测=keep；调用=6；Z3 成功=2；耗时=12.192s；费用保守上界=0.031110 元；错误=None。


- 样本 `NPD/codeql/openssl:row=15:index=16`：success；预测=keep；调用=4；Z3 成功=1；耗时=6.034s；费用保守上界=0.013482 元；错误=None。


- 样本 `NPD/codeql/openssl:row=16:index=17`：success；预测=keep；调用=4；Z3 成功=1；耗时=12.645s；费用保守上界=0.036140 元；错误=None。


- 样本 `NPD/codeql/openssl:row=17:index=18`：success；预测=keep；调用=5；Z3 成功=2；耗时=3.870s；费用保守上界=0.009574 元；错误=None。


- 样本 `NPD/codeql/openssl:row=18:index=19`：success；预测=keep；调用=4；Z3 成功=1；耗时=4.892s；费用保守上界=0.012652 元；错误=None。


- 样本 `NPD/codeql/openssl:row=19:index=20`：success；预测=keep；调用=4；Z3 成功=1；耗时=6.500s；费用保守上界=0.013882 元；错误=None。


- 样本 `NPD/codeql/openssl:row=20:index=21`：success；预测=keep；调用=6；Z3 成功=1；耗时=11.069s；费用保守上界=0.029844 元；错误=None。


- 样本 `NPD/codeql/openssl:row=21:index=22`：success；预测=keep；调用=5；Z3 成功=1；耗时=9.280s；费用保守上界=0.015488 元；错误=None。


- 样本 `NPD/codeql/openssl:row=22:index=23`：success；预测=keep；调用=2；Z3 成功=1；耗时=1.645s；费用保守上界=0.001606 元；错误=None。


- 样本 `NPD/codeql/openssl:row=23:index=24`：success；预测=keep；调用=4；Z3 成功=2；耗时=4.346s；费用保守上界=0.003404 元；错误=None。


- 样本 `NPD/codeql/openssl:row=25:index=26`：success；预测=filter；调用=6；Z3 成功=2；耗时=6.144s；费用保守上界=0.005896 元；错误=None。


- 样本 `NPD/codeql/openssl:row=26:index=27`：success；预测=keep；调用=3；Z3 成功=1；耗时=3.096s；费用保守上界=0.005182 元；错误=None。


- 样本 `NPD/codeql/openssl:row=27:index=28`：success；预测=keep；调用=3；Z3 成功=1；耗时=2.887s；费用保守上界=0.005182 元；错误=None。


- 样本 `NPD/codeql/openssl:row=28:index=29`：success；预测=keep；调用=3；Z3 成功=1；耗时=2.385s；费用保守上界=0.005182 元；错误=None。


- 样本 `NPD/codeql/openssl:row=29:index=30`：success；预测=keep；调用=3；Z3 成功=1；耗时=2.436s；费用保守上界=0.005182 元；错误=None。


- 样本 `NPD/codeql/openssl:row=30:index=31`：success；预测=keep；调用=9；Z3 成功=3；耗时=11.003s；费用保守上界=0.015678 元；错误=None。


- 样本 `NPD/codeql/openssl:row=31:index=32`：success；预测=filter；调用=4；Z3 成功=1；耗时=7.615s；费用保守上界=0.025170 元；错误=None。


- 样本 `NPD/codeql/openssl:row=32:index=33`：success；预测=filter；调用=6；Z3 成功=1；耗时=12.996s；费用保守上界=0.045094 元；错误=None。


- 样本 `NPD/codeql/openssl:row=33:index=34`：success；预测=keep；调用=4；Z3 成功=1；耗时=6.676s；费用保守上界=0.024298 元；错误=None。


- 样本 `NPD/codeql/openssl:row=34:index=36`：success；预测=keep；调用=3；Z3 成功=1；耗时=1.889s；费用保守上界=0.003608 元；错误=None。


- 样本 `NPD/codeql/openssl:row=35:index=37`：success；预测=keep；调用=4；Z3 成功=1；耗时=5.943s；费用保守上界=0.012112 元；错误=None。


- 样本 `NPD/codeql/openssl:row=36:index=38`：success；预测=keep；调用=4；Z3 成功=1；耗时=6.199s；费用保守上界=0.012232 元；错误=None。


- 样本 `NPD/codeql/openssl:row=37:index=39`：success；预测=keep；调用=4；Z3 成功=1；耗时=4.953s；费用保守上界=0.014640 元；错误=None。


- 样本 `NPD/codeql/openssl:row=38:index=40`：success；预测=filter；调用=5；Z3 成功=1；耗时=11.672s；费用保守上界=0.044566 元；错误=None。


- 样本 `NPD/codeql/openssl:row=39:index=41`：success；预测=filter；调用=4；Z3 成功=1；耗时=9.200s；费用保守上界=0.038612 元；错误=None。


- 样本 `NPD/codeql/openssl:row=40:index=42`：success；预测=keep；调用=12；Z3 成功=3；耗时=36.781s；费用保守上界=0.109960 元；错误=None。


- 样本 `NPD/codeql/openssl:row=41:index=43`：failed；预测=None；调用=3；Z3 成功=0；耗时=17.797s；费用保守上界=0.063226 元；错误=ModelFailure: Response incomplete: finish_reason=length。


- 样本 `NPD/codeql/openssl:row=42:index=44`：success；预测=keep；调用=6；Z3 成功=2；耗时=9.800s；费用保守上界=0.022000 元；错误=None。


- 样本 `NPD/codeql/openssl:row=43:index=45`：success；预测=keep；调用=4；Z3 成功=1；耗时=4.778s；费用保守上界=0.013822 元；错误=None。


- 样本 `NPD/codeql/openssl:row=44:index=46`：failed；预测=None；调用=3；Z3 成功=0；耗时=17.408s；费用保守上界=0.093072 元；错误=ModelFailure: Response incomplete: finish_reason=length。


- 样本 `NPD/codeql/openssl:row=45:index=47`：success；预测=filter；调用=4；Z3 成功=1；耗时=5.547s；费用保守上界=0.032640 元；错误=None。


- 样本 `NPD/codeql/openssl:row=46:index=48`：failed；预测=None；调用=7；Z3 成功=0；耗时=11.162s；费用保守上界=0.056112 元；错误=RuntimeError: Z3 repair attempts exhausted: ValueError: Unsupported generated-code operation。


- 样本 `NPD/codeql/openssl:row=47:index=49`：success；预测=keep；调用=4；Z3 成功=1；耗时=5.184s；费用保守上界=0.019090 元；错误=None。


- 样本 `NPD/codeql/openssl:row=48:index=50`：failed；预测=None；调用=2；Z3 成功=0；耗时=9.696s；费用保守上界=0.100504 元；错误=ModelFailure: Response incomplete: finish_reason=length。


- 样本 `NPD/codeql/openssl:row=49:index=51`：failed；预测=None；调用=2；Z3 成功=0；耗时=9.719s；费用保守上界=0.100504 元；错误=ModelFailure: Response incomplete: finish_reason=length。


### codeql_openssl 阶段保存完成

已记录 49 条，成功执行 42、阻塞 0、失败 7。分组 CSV/JSON、指标及原始输出均已保存后再进入下一组。


## cppcheck_linux 预检查

全部 594 条，现有 0/1 标签 65 条，预检查就绪 47 条。清单和阻塞原因已保存；预检查不作为结果筛选条件。


## 补全版 expanded_cppcheck_linux 开始

时间：2026-10-26T01:03:49.547846+08:00。样本原始行号：[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 50, 51, 52, 53, 54, 55, 56, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67]。下列运行属于补全实现，原始实现诊断记录保留。


- 样本 `NPD/cppcheck/linux:row=0:index=None`：success；预测=filter；调用=4；Z3 成功=1；耗时=3.237s；费用保守上界=0.004130 元；错误=None。


- 样本 `NPD/cppcheck/linux:row=1:index=None`：success；预测=filter；调用=4；Z3 成功=1；耗时=3.407s；费用保守上界=0.004132 元；错误=None。


- 样本 `NPD/cppcheck/linux:row=2:index=None`：success；预测=filter；调用=4；Z3 成功=1；耗时=3.051s；费用保守上界=0.004144 元；错误=None。


- 样本 `NPD/cppcheck/linux:row=3:index=None`：success；预测=filter；调用=4；Z3 成功=1；耗时=3.552s；费用保守上界=0.004362 元；错误=None。


- 样本 `NPD/cppcheck/linux:row=4:index=None`：success；预测=filter；调用=4；Z3 成功=1；耗时=3.649s；费用保守上界=0.004278 元；错误=None。


- 样本 `NPD/cppcheck/linux:row=5:index=None`：success；预测=filter；调用=4；Z3 成功=1；耗时=2.953s；费用保守上界=0.004200 元；错误=None。


- 样本 `NPD/cppcheck/linux:row=6:index=None`：success；预测=filter；调用=4；Z3 成功=1；耗时=4.362s；费用保守上界=0.004258 元；错误=None。


- 样本 `NPD/cppcheck/linux:row=7:index=None`：success；预测=filter；调用=4；Z3 成功=1；耗时=3.513s；费用保守上界=0.004308 元；错误=None。


- 样本 `NPD/cppcheck/linux:row=8:index=None`：blocked_context；预测=None；调用=0；Z3 成功=0；耗时=0.002s；费用保守上界=0.000000 元；错误=Function for_each_pci_dev: 0 distinct available definitions。


- 样本 `NPD/cppcheck/linux:row=9:index=None`：blocked_context；预测=None；调用=0；Z3 成功=0；耗时=0.001s；费用保守上界=0.000000 元；错误=Function kvm_for_each_vcpu: 0 distinct available definitions。


- 样本 `NPD/cppcheck/linux:row=10:index=None`：blocked_context；预测=None；调用=0；Z3 成功=0；耗时=0.001s；费用保守上界=0.000000 元；错误=Function kvm_for_each_vcpu: 0 distinct available definitions。


- 样本 `NPD/cppcheck/linux:row=11:index=None`：blocked_context；预测=None；调用=0；Z3 成功=0；耗时=0.001s；费用保守上界=0.000000 元；错误=Function kvm_for_each_vcpu: 0 distinct available definitions。


- 样本 `NPD/cppcheck/linux:row=12:index=None`：blocked_context；预测=None；调用=0；Z3 成功=0；耗时=0.001s；费用保守上界=0.000000 元；错误=Function kvm_for_each_vcpu: 0 distinct available definitions。


- 样本 `NPD/cppcheck/linux:row=13:index=None`：blocked_context；预测=None；调用=0；Z3 成功=0；耗时=0.001s；费用保守上界=0.000000 元；错误=Function kvm_for_each_vcpu: 0 distinct available definitions。


- 样本 `NPD/cppcheck/linux:row=14:index=None`：blocked_context；预测=None；调用=0；Z3 成功=0；耗时=0.002s；费用保守上界=0.000000 元；错误=Function kvm_for_each_vcpu: 0 distinct available definitions。


- 样本 `NPD/cppcheck/linux:row=15:index=None`：blocked_context；预测=None；调用=0；Z3 成功=0；耗时=0.001s；费用保守上界=0.000000 元；错误=Function kvm_for_each_vcpu: 0 distinct available definitions。


- 样本 `NPD/cppcheck/linux:row=16:index=None`：blocked_context；预测=None；调用=0；Z3 成功=0；耗时=0.001s；费用保守上界=0.000000 元；错误=Function kvm_for_each_vcpu: 0 distinct available definitions。


- 样本 `NPD/cppcheck/linux:row=17:index=None`：blocked_context；预测=None；调用=0；Z3 成功=0；耗时=0.001s；费用保守上界=0.000000 元；错误=Function kvm_for_each_vcpu: 0 distinct available definitions。


- 样本 `NPD/cppcheck/linux:row=18:index=None`：blocked_context；预测=None；调用=0；Z3 成功=0；耗时=0.001s；费用保守上界=0.000000 元；错误=Function kvm_for_each_vcpu: 0 distinct available definitions。


- 样本 `NPD/cppcheck/linux:row=19:index=None`：blocked_context；预测=None；调用=0；Z3 成功=0；耗时=0.001s；费用保守上界=0.000000 元；错误=Function kvm_for_each_vcpu: 0 distinct available definitions。


- 样本 `NPD/cppcheck/linux:row=20:index=None`：blocked_context；预测=None；调用=0；Z3 成功=0；耗时=0.001s；费用保守上界=0.000000 元；错误=Function kvm_for_each_vcpu: 0 distinct available definitions。


- 样本 `NPD/cppcheck/linux:row=21:index=None`：blocked_context；预测=None；调用=0；Z3 成功=0；耗时=0.001s；费用保守上界=0.000000 元；错误=Function kvm_for_each_vcpu: 0 distinct available definitions。


- 样本 `NPD/cppcheck/linux:row=22:index=None`：success；预测=filter；调用=4；Z3 成功=1；耗时=3.200s；费用保守上界=0.004382 元；错误=None。


- 样本 `NPD/cppcheck/linux:row=23:index=None`：success；预测=filter；调用=5；Z3 成功=1；耗时=4.063s；费用保守上界=0.005634 元；错误=None。


- 样本 `NPD/cppcheck/linux:row=24:index=None`：success；预测=filter；调用=4；Z3 成功=1；耗时=2.978s；费用保守上界=0.004250 元；错误=None。


- 样本 `NPD/cppcheck/linux:row=25:index=None`：success；预测=filter；调用=4；Z3 成功=1；耗时=3.799s；费用保守上界=0.004260 元；错误=None。


- 样本 `NPD/cppcheck/linux:row=26:index=None`：success；预测=filter；调用=4；Z3 成功=1；耗时=3.759s；费用保守上界=0.004382 元；错误=None。


- 样本 `NPD/cppcheck/linux:row=27:index=None`：success；预测=filter；调用=4；Z3 成功=1；耗时=2.937s；费用保守上界=0.004304 元；错误=None。


- 样本 `NPD/cppcheck/linux:row=28:index=None`：success；预测=filter；调用=4；Z3 成功=1；耗时=3.768s；费用保守上界=0.004250 元；错误=None。


- 样本 `NPD/cppcheck/linux:row=29:index=None`：success；预测=filter；调用=5；Z3 成功=1；耗时=3.996s；费用保守上界=0.005634 元；错误=None。


- 样本 `NPD/cppcheck/linux:row=30:index=None`：success；预测=filter；调用=4；Z3 成功=1；耗时=3.762s；费用保守上界=0.004382 元；错误=None。


- 样本 `NPD/cppcheck/linux:row=31:index=None`：success；预测=keep；调用=2；Z3 成功=1；耗时=1.759s；费用保守上界=0.001606 元；错误=None。


- 样本 `NPD/cppcheck/linux:row=32:index=None`：success；预测=filter；调用=4；Z3 成功=1；耗时=2.798s；费用保守上界=0.004260 元；错误=None。


- 样本 `NPD/cppcheck/linux:row=33:index=None`：success；预测=filter；调用=5；Z3 成功=1；耗时=4.021s；费用保守上界=0.005634 元；错误=None。


- 样本 `NPD/cppcheck/linux:row=34:index=None`：blocked_context；预测=None；调用=0；Z3 成功=0；耗时=0.002s；费用保守上界=0.000000 元；错误=Function for_each_node_by_name: 0 distinct available definitions。


- 样本 `NPD/cppcheck/linux:row=35:index=None`：success；预测=filter；调用=5；Z3 成功=1；耗时=7.434s；费用保守上界=0.025994 元；错误=None。


- 样本 `NPD/cppcheck/linux:row=36:index=None`：success；预测=filter；调用=7；Z3 成功=2；耗时=9.479s；费用保守上界=0.023898 元；错误=None。


- 样本 `NPD/cppcheck/linux:row=37:index=None`：blocked_context；预测=None；调用=0；Z3 成功=0；耗时=0.002s；费用保守上界=0.000000 元；错误=Function list_for_each_entry_reverse: 0 distinct available definitions。


- 样本 `NPD/cppcheck/linux:row=38:index=None`：blocked_context；预测=None；调用=0；Z3 成功=0；耗时=0.002s；费用保守上界=0.000000 元；错误=Function list_for_each_entry_reverse: 0 distinct available definitions。


- 样本 `NPD/cppcheck/linux:row=39:index=None`：blocked_context；预测=None；调用=0；Z3 成功=0；耗时=0.001s；费用保守上界=0.000000 元；错误=Function for_each_node_by_name: 0 distinct available definitions。


- 样本 `NPD/cppcheck/linux:row=40:index=None`：success；预测=filter；调用=4；Z3 成功=1；耗时=3.522s；费用保守上界=0.004314 元；错误=None。


- 样本 `NPD/cppcheck/linux:row=41:index=None`：success；预测=filter；调用=4；Z3 成功=1；耗时=3.814s；费用保守上界=0.003462 元；错误=None。


- 样本 `NPD/cppcheck/linux:row=42:index=None`：success；预测=filter；调用=4；Z3 成功=1；耗时=3.940s；费用保守上界=0.003722 元；错误=None。


- 样本 `NPD/cppcheck/linux:row=43:index=None`：success；预测=filter；调用=5；Z3 成功=1；耗时=3.778s；费用保守上界=0.004818 元；错误=None。


- 样本 `NPD/cppcheck/linux:row=44:index=None`：success；预测=filter；调用=4；Z3 成功=1；耗时=3.151s；费用保守上界=0.003544 元；错误=None。


- 样本 `NPD/cppcheck/linux:row=45:index=None`：success；预测=filter；调用=4；Z3 成功=1；耗时=3.598s；费用保守上界=0.003634 元；错误=None。


- 样本 `NPD/cppcheck/linux:row=46:index=None`：success；预测=keep；调用=3；Z3 成功=1；耗时=2.380s；费用保守上界=0.002404 元；错误=None。


- 样本 `NPD/cppcheck/linux:row=47:index=None`：success；预测=filter；调用=4；Z3 成功=1；耗时=3.062s；费用保守上界=0.004200 元；错误=None。


- 样本 `NPD/cppcheck/linux:row=50:index=None`：success；预测=filter；调用=4；Z3 成功=1；耗时=2.987s；费用保守上界=0.003746 元；错误=None。


- 样本 `NPD/cppcheck/linux:row=51:index=None`：success；预测=filter；调用=4；Z3 成功=1；耗时=3.637s；费用保守上界=0.003784 元；错误=None。


- 样本 `NPD/cppcheck/linux:row=52:index=None`：success；预测=filter；调用=4；Z3 成功=1；耗时=3.578s；费用保守上界=0.004262 元；错误=None。


- 样本 `NPD/cppcheck/linux:row=53:index=None`：success；预测=filter；调用=4；Z3 成功=1；耗时=3.573s；费用保守上界=0.004172 元；错误=None。


- 样本 `NPD/cppcheck/linux:row=54:index=None`：success；预测=filter；调用=4；Z3 成功=1；耗时=2.972s；费用保守上界=0.003800 元；错误=None。


- 样本 `NPD/cppcheck/linux:row=55:index=None`：success；预测=filter；调用=4；Z3 成功=1；耗时=4.147s；费用保守上界=0.004148 元；错误=None。


- 样本 `NPD/cppcheck/linux:row=56:index=None`：success；预测=keep；调用=3；Z3 成功=1；耗时=2.237s；费用保守上界=0.003302 元；错误=None。


- 样本 `NPD/cppcheck/linux:row=58:index=None`：success；预测=filter；调用=4；Z3 成功=1；耗时=4.583s；费用保守上界=0.003746 元；错误=None。


- 样本 `NPD/cppcheck/linux:row=59:index=None`：failed；预测=None；调用=2；Z3 成功=0；耗时=2.860s；费用保守上界=0.004348 元；错误=JSONDecodeError: Expecting value: line 1 column 1 (char 0)。


- 样本 `NPD/cppcheck/linux:row=60:index=None`：success；预测=keep；调用=2；Z3 成功=1；耗时=1.585s；费用保守上界=0.001776 元；错误=None。


- 样本 `NPD/cppcheck/linux:row=61:index=None`：success；预测=keep；调用=2；Z3 成功=1；耗时=1.530s；费用保守上界=0.001776 元；错误=None。


- 样本 `NPD/cppcheck/linux:row=62:index=None`：success；预测=keep；调用=2；Z3 成功=1；耗时=1.684s；费用保守上界=0.001776 元；错误=None。


- 样本 `NPD/cppcheck/linux:row=63:index=None`：success；预测=filter；调用=4；Z3 成功=1；耗时=3.518s；费用保守上界=0.004226 元；错误=None。


- 样本 `NPD/cppcheck/linux:row=64:index=None`：success；预测=filter；调用=4；Z3 成功=1；耗时=3.861s；费用保守上界=0.004490 元；错误=None。


- 样本 `NPD/cppcheck/linux:row=65:index=None`：success；预测=filter；调用=4；Z3 成功=1；耗时=4.185s；费用保守上界=0.004682 元；错误=None。


- 样本 `NPD/cppcheck/linux:row=66:index=None`：success；预测=keep；调用=6；Z3 成功=1；耗时=7.249s；费用保守上界=0.016290 元；错误=None。


- 样本 `NPD/cppcheck/linux:row=67:index=None`：success；预测=filter；调用=8；Z3 成功=2；耗时=9.934s；费用保守上界=0.035958 元；错误=None。


### cppcheck_linux 阶段保存完成

已记录 65 条，成功执行 46、阻塞 18、失败 1。分组 CSV/JSON、指标及原始输出均已保存后再进入下一组。


## cppcheck_libav 预检查

全部 10 条，现有 0/1 标签 10 条，预检查就绪 10 条。清单和阻塞原因已保存；预检查不作为结果筛选条件。


## 补全版 expanded_cppcheck_libav 开始

时间：2026-10-26T01:06:46.681956+08:00。样本原始行号：[0, 1, 2, 3, 4, 5, 6, 7, 8, 9]。下列运行属于补全实现，原始实现诊断记录保留。


- 样本 `NPD/cppcheck/libav:row=0:index=None`：success；预测=keep；调用=3；Z3 成功=1；耗时=2.221s；费用保守上界=0.007366 元；错误=None。


- 样本 `NPD/cppcheck/libav:row=1:index=None`：success；预测=keep；调用=3；Z3 成功=1；耗时=2.363s；费用保守上界=0.006590 元；错误=None。


- 样本 `NPD/cppcheck/libav:row=2:index=None`：success；预测=keep；调用=2；Z3 成功=1；耗时=1.544s；费用保守上界=0.001702 元；错误=None。


- 样本 `NPD/cppcheck/libav:row=3:index=None`：success；预测=keep；调用=2；Z3 成功=1；耗时=1.661s；费用保守上界=0.001760 元；错误=None。


- 样本 `NPD/cppcheck/libav:row=4:index=None`：success；预测=keep；调用=2；Z3 成功=1；耗时=1.364s；费用保守上界=0.001760 元；错误=None。


- 样本 `NPD/cppcheck/libav:row=5:index=None`：success；预测=keep；调用=3；Z3 成功=1；耗时=4.906s；费用保守上界=0.010178 元；错误=None。


- 样本 `NPD/cppcheck/libav:row=6:index=None`：success；预测=keep；调用=2；Z3 成功=1；耗时=1.704s；费用保守上界=0.001702 元；错误=None。


- 样本 `NPD/cppcheck/libav:row=7:index=None`：success；预测=keep；调用=3；Z3 成功=1；耗时=2.238s；费用保守上界=0.003960 元；错误=None。


- 样本 `NPD/cppcheck/libav:row=8:index=None`：success；预测=keep；调用=3；Z3 成功=1；耗时=2.138s；费用保守上界=0.003748 元；错误=None。


- 样本 `NPD/cppcheck/libav:row=9:index=None`：success；预测=keep；调用=4；Z3 成功=1；耗时=4.728s；费用保守上界=0.007872 元；错误=None。


### cppcheck_libav 阶段保存完成

已记录 10 条，成功执行 10、阻塞 0、失败 0。分组 CSV/JSON、指标及原始输出均已保存后再进入下一组。


## cppcheck_openssl 预检查

全部 5 条，现有 0/1 标签 5 条，预检查就绪 5 条。清单和阻塞原因已保存；预检查不作为结果筛选条件。


## 补全版 expanded_cppcheck_openssl 开始

时间：2026-10-26T01:07:11.885326+08:00。样本原始行号：[0, 1, 2, 3, 4]。下列运行属于补全实现，原始实现诊断记录保留。


- 样本 `NPD/cppcheck/openssl:row=0:index=None`：success；预测=keep；调用=4；Z3 成功=1；耗时=6.132s；费用保守上界=0.028216 元；错误=None。


- 样本 `NPD/cppcheck/openssl:row=1:index=None`：success；预测=keep；调用=3；Z3 成功=1；耗时=2.436s；费用保守上界=0.067430 元；错误=None。


- 样本 `NPD/cppcheck/openssl:row=2:index=None`：success；预测=keep；调用=4；Z3 成功=1；耗时=3.688s；费用保守上界=0.003740 元；错误=None。


- 样本 `NPD/cppcheck/openssl:row=3:index=None`：failed；预测=None；调用=2；Z3 成功=0；耗时=3.157s；费用保守上界=0.004716 元；错误=JSONDecodeError: Expecting value: line 1 column 1 (char 0)。


- 样本 `NPD/cppcheck/openssl:row=4:index=None`：success；预测=keep；调用=3；Z3 成功=1；耗时=2.956s；费用保守上界=0.002360 元；错误=None。


### cppcheck_openssl 阶段保存完成

已记录 5 条，成功执行 4、阻塞 0、失败 1。分组 CSV/JSON、指标及原始输出均已保存后再进入下一组。


## infer_libav 预检查

全部 6 条，现有 0/1 标签 6 条，预检查就绪 6 条。清单和阻塞原因已保存；预检查不作为结果筛选条件。


## 补全版 expanded_infer_libav 开始

时间：2026-10-26T01:07:30.350719+08:00。样本原始行号：[0, 1, 2, 3, 4, 5]。下列运行属于补全实现，原始实现诊断记录保留。


- 样本 `NPD/infer/libav:row=0:index=None`：success；预测=keep；调用=2；Z3 成功=1；耗时=1.559s；费用保守上界=0.001720 元；错误=None。


- 样本 `NPD/infer/libav:row=1:index=None`：success；预测=keep；调用=4；Z3 成功=1；耗时=5.051s；费用保守上界=0.007954 元；错误=None。


- 样本 `NPD/infer/libav:row=2:index=None`：success；预测=keep；调用=4；Z3 成功=1；耗时=6.512s；费用保守上界=0.012154 元；错误=None。


- 样本 `NPD/infer/libav:row=3:index=None`：success；预测=keep；调用=5；Z3 成功=2；耗时=4.264s；费用保守上界=0.004470 元；错误=None。


- 样本 `NPD/infer/libav:row=4:index=None`：success；预测=keep；调用=4；Z3 成功=1；耗时=4.857s；费用保守上界=0.005434 元；错误=None。


- 样本 `NPD/infer/libav:row=5:index=None`：success；预测=keep；调用=7；Z3 成功=1；耗时=11.864s；费用保守上界=0.031266 元；错误=None。


### infer_libav 阶段保存完成

已记录 6 条，成功执行 6、阻塞 0、失败 0。分组 CSV/JSON、指标及原始输出均已保存后再进入下一组。


## infer_openssl 预检查

全部 16 条，现有 0/1 标签 16 条，预检查就绪 16 条。清单和阻塞原因已保存；预检查不作为结果筛选条件。


## 补全版 expanded_infer_openssl 开始

时间：2026-10-26T01:08:04.594277+08:00。样本原始行号：[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]。下列运行属于补全实现，原始实现诊断记录保留。


- 样本 `NPD/infer/openssl:row=0:index=None`：success；预测=keep；调用=4；Z3 成功=1；耗时=6.579s；费用保守上界=0.013510 元；错误=None。


- 样本 `NPD/infer/openssl:row=1:index=None`：success；预测=keep；调用=2；Z3 成功=1；耗时=1.915s；费用保守上界=0.001702 元；错误=None。


- 样本 `NPD/infer/openssl:row=2:index=None`：success；预测=keep；调用=2；Z3 成功=1；耗时=1.691s；费用保守上界=0.001702 元；错误=None。


- 样本 `NPD/infer/openssl:row=3:index=None`：success；预测=keep；调用=6；Z3 成功=1；耗时=6.842s；费用保守上界=0.012496 元；错误=None。


- 样本 `NPD/infer/openssl:row=4:index=None`：failed；预测=None；调用=2；Z3 成功=0；耗时=2.528s；费用保守上界=0.006582 元；错误=JSONDecodeError: Expecting value: line 1 column 1 (char 0)。


- 样本 `NPD/infer/openssl:row=5:index=None`：success；预测=keep；调用=4；Z3 成功=2；耗时=3.665s；费用保守上界=0.003382 元；错误=None。


- 样本 `NPD/infer/openssl:row=6:index=None`：failed；预测=None；调用=4；Z3 成功=0；耗时=14.165s；费用保守上界=0.037764 元；错误=ReadTimeout: HTTPSConnectionPool(host='api.deepseek.com', port=443): Read timed out. (read timeout=10)。


- 样本 `NPD/infer/openssl:row=7:index=None`：success；预测=keep；调用=8；Z3 成功=2；耗时=15.003s；费用保守上界=0.033770 元；错误=None。


- 样本 `NPD/infer/openssl:row=8:index=None`：success；预测=keep；调用=4；Z3 成功=1；耗时=6.830s；费用保守上界=0.010026 元；错误=None。


- 样本 `NPD/infer/openssl:row=9:index=None`：failed；预测=None；调用=2；Z3 成功=0；耗时=3.142s；费用保守上界=0.005018 元；错误=JSONDecodeError: Expecting value: line 1 column 1 (char 0)。


- 样本 `NPD/infer/openssl:row=10:index=None`：success；预测=keep；调用=3；Z3 成功=1；耗时=2.115s；费用保守上界=0.005376 元；错误=None。


- 样本 `NPD/infer/openssl:row=11:index=None`：success；预测=keep；调用=2；Z3 成功=1；耗时=1.267s；费用保守上界=0.001702 元；错误=None。


- 样本 `NPD/infer/openssl:row=12:index=None`：success；预测=keep；调用=4；Z3 成功=1；耗时=4.091s；费用保守上界=0.006108 元；错误=None。


- 样本 `NPD/infer/openssl:row=13:index=None`：failed；预测=None；调用=2；Z3 成功=0；耗时=2.156s；费用保守上界=0.011978 元；错误=JSONDecodeError: Expecting value: line 1 column 1 (char 0)。


- 样本 `NPD/infer/openssl:row=14:index=None`：success；预测=keep；调用=5；Z3 成功=1；耗时=7.571s；费用保守上界=0.012826 元；错误=None。


- 样本 `NPD/infer/openssl:row=15:index=None`：success；预测=keep；调用=3；Z3 成功=1；耗时=4.247s；费用保守上界=0.005806 元；错误=None。


### infer_openssl 阶段保存完成

已记录 16 条，成功执行 12、阻塞 0、失败 4。分组 CSV/JSON、指标及原始输出均已保存后再进入下一组。


## 扩展实验实际结果（2026-10-26T01:09:38.819214+08:00）

本次覆盖 8 组 NPD 文件的全部 278 条现有 0/1 标签记录。最终成功执行 224 条、阻塞 39 条、执行失败 15 条，处理成功率 80.58%。复用原先 25 条最终记录，其余新增结果均单独保存；没有按可运行性或预测正确性筛选记录。

| 分组 | 已选定 | 成功执行 | 阻塞 | 运行失败 | 误报过滤率 | 真实缺陷保留率 |
|---|---:|---:|---:|---:|---:|---:|
| codeql_linux | 70 | 53 | 17 | 0 | 39.58% | 72.73% |
| codeql_libav | 57 | 51 | 4 | 2 | 0.00% | 50.00% |
| codeql_openssl | 49 | 42 | 0 | 7 | 14.63% | 100.00% |
| cppcheck_linux | 65 | 46 | 18 | 1 | 60.00% | NA |
| cppcheck_libav | 10 | 10 | 0 | 0 | 0.00% | 100.00% |
| cppcheck_openssl | 5 | 4 | 0 | 1 | 0.00% | NA |
| infer_libav | 6 | 6 | 0 | 0 | 0.00% | NA |
| infer_openssl | 16 | 12 | 0 | 4 | 0.00% | 100.00% |

| 实际类别 | 过滤 | 保留 | 未分类 |
|---|---:|---:|---:|
| 误报 | 64 | 128 | 49 |
| 真实缺陷 | 2 | 30 | 5 |

正类定义为“应过滤的误报”。全体选定样本含误报 241 条、真实缺陷 37 条。
误报过滤率=64/241=26.56%；真实缺陷保留率=30/37=81.08%；真实缺陷误删率=2/37=5.41%。
Precision=A/(A+C)=96.97%，Recall=A/N_FP=26.56%，F1=2PR/(P+R)=41.69%。
未分类记录保持未知、未当作过滤或保留，且不从分母中删除。未知结果使过滤率可能范围为 26.56%–46.89%，真实缺陷保留率为 81.08%–94.59%；当前比例只统计已确认结果。

最终尝试平均耗时（含上下文阻塞）：5.805 秒/条；成功执行样本平均 6.425 秒/条。复用样本使用其原实际耗时，并非本轮复用读取耗时。逐样本耗时与费用在 CSV/JSON 中。
本轮新增实际模型调用 996 次，新增费用保守上界 3.586168 元；全部阶段和早期失败累计 1187 次，费用上界 4.491330 元，未超过原累计 10 元限制。这是使用官方较高费率计算的估算上界，不是账户账单。


- 13 条：`Function kvm_for_each_vcpu: 0 distinct available definitions`
- 11 条：`Expected one function definition, found 0`
- 5 条：`JSONDecodeError: Expecting value: line 1 column 1 (char 0)`
- 4 条：`Cannot uniquely locate intermediate call site`
- 4 条：`ModelFailure: Response incomplete: finish_reason=length`
- 2 条：`Function IS_ERR_OR_NULL: 0 distinct available definitions`
- 2 条：`RuntimeError: Z3 repair attempts exhausted: ValueError: Unsupported generated-code operation`
- 2 条：`Function for_each_node_by_name: 0 distinct available definitions`
- 2 条：`Function list_for_each_entry_reverse: 0 distinct available definitions`
- 1 条：`Function ip6_route_mpath_should_notify: 0 distinct available definitions`
- 1 条：`Function skb_zcopy_pure: 0 distinct available definitions`
- 1 条：`Function rt6_is_dead: 0 distinct available definitions`
- 1 条：`Tracked value passed via an unsupported compound argument`
- 1 条：`RuntimeError: Z3 repair attempts exhausted: Z3Exception: Z3 sort expected`
- 1 条：`RuntimeError: Z3 repair attempts exhausted: ValueError: Returned boolean disagrees with last solver result`
- 1 条：`RuntimeError: Z3 repair attempts exhausted: TypeError: unsupported operand type(s) for &: 'ArithRef' and 'ArithRef'`
- 1 条：`Function for_each_pci_dev: 0 distinct available definitions`
- 1 条：`ReadTimeout: HTTPSConnectionPool(host='api.deepseek.com', port=443): Read timed out. (read timeout=10)`


## 扩展交付核验完成（2026-10-26T01:12:21.446086+08:00）

278 个样本均有结果记录，224 成功、39 上下文阻塞、15 运行失败。实际核验通过：原始数据标签/索引、CSV/JSON、逐样本模型和 SMT 证据、每次调用与费用账本、指标重算均一致；原先 25 条无重复累计。1187 次调用累计保守费用上界 4.491330 元，无未完成预留；上游 Git clean；扫描 2797 个交付文件未发现本地用户密钥。详细核验输出见 results/raw/completed/expanded_verification.json；源码/配置/数据哈希见 configs/expanded_run_identity.json。10 项本地测试输出见 results/raw/completed/expansion_regression_tests.txt。
