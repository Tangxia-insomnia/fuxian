# 阶段 4：小规模实验

当前更新（2026-10-26）：已实际执行固定 20 条补全版实验，16 条成功执行、4 条上下文阻塞，最终运行失败 0 条；另有 1 次执行器问题导致的失败尝试，修复重跑且原始记录保留。未进入全量基准。逐样本记录在本文后半部分，结果见 results/processed/completed_pilot.json。

初始状态（补写前）：未运行（先决条件不满足）。

阶段 3 只完成 5 条样本的离线组件诊断，没有端到端成功运行。依照“先最小样本成功，再 20 条”的门槛，本阶段不抽取或调用 20 条模型实验，也不将 5 条组件诊断混作 pilot。

- 计划数量：约 20；实际选定 pilot 数量：0；端到端尝试：0；成功：0；运行失败：0；阶段阻塞：是。
- 预测分布、平均端到端耗时：不可计算。
- API 调用：0；费用：0 元，预算上限 10 元。
- 阻塞：原始内部工具模块/运行缓存不全；原始模块加载失败；当前进程无 DEEPSEEK_APIkey；用户模型未做接口与定价核验。
- `results/processed/pilot_status.json` 保存机器可读状态；不存在伪造的 20 条预测。

继续条件：取得缺失官方模块或其可核验的官方替代文件、补齐必要上下文和解引用数据；验证 3–5 条真实端到端运行成功；然后配置本地模型凭据、核实模型/价格并确保累计费用不超过 10 元。若需重写核心分析逻辑，不在此次简单复现范围内。


## 补全版 pilot 开始

时间：2026-10-26T00:29:00.174489+08:00。样本原始行号：[4, 8, 11, 13, 16, 22, 25, 27, 31, 36, 41, 42, 43, 45, 46, 47, 48, 50, 56, 59]。下列运行属于补全实现，原始实现诊断记录保留。


- 样本 `NPD/codeql/kernel69:row=4:index=4`：blocked_context；预测=None；调用=0；Z3 成功=0；耗时=0.002s；费用保守上界=0.000000 元；错误=Expected one function definition, found 0。


- 样本 `NPD/codeql/kernel69:row=8:index=11`：success；预测=keep；调用=10；Z3 成功=2；耗时=17.201s；费用保守上界=0.047858 元；错误=None。


- 样本 `NPD/codeql/kernel69:row=11:index=23`：success；预测=filter；调用=4；Z3 成功=1；耗时=3.766s；费用保守上界=0.010898 元；错误=None。


- 样本 `NPD/codeql/kernel69:row=13:index=27`：failed；预测=None；调用=7；Z3 成功=0；耗时=25.168s；费用保守上界=0.091924 元；错误=RuntimeError: Z3 repair attempts exhausted: NameError: name 'Function' is not defined。


- 样本 `NPD/codeql/kernel69:row=16:index=34`：success；预测=keep；调用=8；Z3 成功=2；耗时=13.136s；费用保守上界=0.024856 元；错误=None。


- 样本 `NPD/codeql/kernel69:row=22:index=41`：success；预测=keep；调用=6；Z3 成功=2；耗时=7.019s；费用保守上界=0.010552 元；错误=None。


- 样本 `NPD/codeql/kernel69:row=25:index=44`：success；预测=filter；调用=12；Z3 成功=3；耗时=15.984s；费用保守上界=0.029516 元；错误=None。


- 样本 `NPD/codeql/kernel69:row=27:index=46`：success；预测=keep；调用=8；Z3 成功=2；耗时=13.974s；费用保守上界=0.042684 元；错误=None。


- 样本 `NPD/codeql/kernel69:row=31:index=51`：blocked_context；预测=None；调用=0；Z3 成功=0；耗时=0.006s；费用保守上界=0.000000 元；错误=Function ip6_route_mpath_should_notify: 0 distinct available definitions。


- 样本 `NPD/codeql/kernel69:row=36:index=57`：success；预测=keep；调用=7；Z3 成功=2；耗时=12.958s；费用保守上界=0.026608 元；错误=None。


- 样本 `NPD/codeql/kernel69:row=41:index=65`：success；预测=filter；调用=4；Z3 成功=1；耗时=4.267s；费用保守上界=0.005462 元；错误=None。


- 样本 `NPD/codeql/kernel69:row=42:index=67`：success；预测=keep；调用=8；Z3 成功=2；耗时=15.822s；费用保守上界=0.037850 元；错误=None。


- 样本 `NPD/codeql/kernel69:row=43:index=68`：blocked_context；预测=None；调用=0；Z3 成功=0；耗时=0.005s；费用保守上界=0.000000 元；错误=Cannot uniquely locate intermediate call site。


- 样本 `NPD/codeql/kernel69:row=45:index=71`：success；预测=filter；调用=16；Z3 成功=4；耗时=30.067s；费用保守上界=0.075580 元；错误=None。


- 样本 `NPD/codeql/kernel69:row=46:index=72`：success；预测=filter；调用=10；Z3 成功=2；耗时=24.061s；费用保守上界=0.067234 元；错误=None。


- 样本 `NPD/codeql/kernel69:row=47:index=73`：success；预测=keep；调用=3；Z3 成功=1；耗时=2.184s；费用保守上界=0.003394 元；错误=None。


- 样本 `NPD/codeql/kernel69:row=48:index=74`：success；预测=filter；调用=10；Z3 成功=3；耗时=11.292s；费用保守上界=0.017012 元；错误=None。


- 样本 `NPD/codeql/kernel69:row=50:index=76`：blocked_context；预测=None；调用=0；Z3 成功=0；耗时=0.007s；费用保守上界=0.000000 元；错误=Cannot uniquely locate intermediate call site。


- 样本 `NPD/codeql/kernel69:row=56:index=84`：success；预测=keep；调用=7；Z3 成功=2；耗时=8.550s；费用保守上界=0.021792 元；错误=None。


- 样本 `NPD/codeql/kernel69:row=59:index=89`：success；预测=keep；调用=5；Z3 成功=1；耗时=5.248s；费用保守上界=0.015788 元；错误=None。


## 补全版 pilot 开始

时间：2026-10-26T00:34:01.237983+08:00。样本原始行号：[4, 8, 11, 13, 16, 22, 25, 27, 31, 36, 41, 42, 43, 45, 46, 47, 48, 50, 56, 59]。下列运行属于补全实现，原始实现诊断记录保留。


- 样本 `NPD/codeql/kernel69:row=13:index=27`：success；预测=keep；调用=4；Z3 成功=1；耗时=12.104s；费用保守上界=0.032254 元；错误=None。


## 补全版阶段汇总

已记录 20 条；最终成功 16、失败 0、阻塞 4；先前失败尝试 1，保留在 attempt_history。机器可读结果见 results/processed/completed_pilot.json。
