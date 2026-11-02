# E06-R01：直接调用与入口参数映射（候选未通过完整验收）

这是独立复现适配模块，不是原作者实现，也未接入 engine、MCP 或安全裁决。最终报告见 [E06_R01_report.md](E06_R01_report.md)。

**本轮停止原因：冻结后固定集第 13 条 `context=null` 引发运行器异常。** 代码和冻结材料保持原样；没有修复后重跑，未提交或推送。本目录保留开发失败、成功合成测试和不完整固定集记录。

## 环境与入口

- 已有 Python 3.11.5 / libclang 18.1.1；没有安装依赖。真实加载与 AST 重复解析证据在 `environment/result.json`。
- `mapper.py`：唯一直接调用、序号、声明身份、受限类型及入口值关系。
- `test_mapper.py`：八类必需场景及附加不变量；最终记录 `synthetic_runs/attempt_05_freeze_candidate/test_results.json`，41/41。
- `run_regression.py`：保存源码的离线案例适配器；存在上述 null 处理缺陷。不要把它作为已验收的批处理接口使用。
- `offline_boundary.py`：R01 测试用 Python audit hook，阻止 socket 网络操作及子进程执行；不是操作系统沙箱，不接入生产 `offline_guard`。
- `freeze_manifest.json`：固定集运行前的候选、配置和输入哈希。
- `fixed_20/results.json`：全部 20 条的执行状态，包括未完成项；不是 20 条均已检查。

当时使用的命令（在 `reproduction/` 中，以下为历史执行记录）：

```powershell
& .\.venv\Scripts\python.exe -B .\safety_runs\E06_R01_direct_call_argument_mapping\environment_probe.py
& .\.venv\Scripts\python.exe -B .\safety_runs\E06_R01_direct_call_argument_mapping\test_mapper.py --output .\safety_runs\E06_R01_direct_call_argument_mapping\synthetic_runs\attempt_05_freeze_candidate
& .\.venv\Scripts\python.exe -B .\safety_runs\E06_R01_direct_call_argument_mapping\run_regression.py historical
# 冻结 SHA-256 后，只执行过一次：
& .\.venv\Scripts\python.exe -B .\safety_runs\E06_R01_direct_call_argument_mapping\run_regression.py fixed20
```

输出目录通过独占创建保护，不支持覆盖重跑。合成测试可在另一个新结果目录独立重现；本次已经停止，没有在固定集失败后再测试或改代码。固定集后续修订必须另立候选和明确标注已接触的数据，不冒充本轮一次性验证。

## 解释边界

PASS 只表示：**若执行该源调用点**，所支持实参的值经过记录的转换进入对应参数。它不证明调用可达、不证明指针对象/别名/生命周期、不追踪赋值前后版本、不证明函数副作用。不同源码 slot 不合并；不同调用点由 transfer_id 隔离。没有告警裁决接口。

真实保存片段一律标为 `saved-source-only`。不添加缺失头文件、宏、typedef；Clang 恢复节点不用于批准映射。缺少原始构建证据强制 UNKNOWN。B、Δ 和模型输出从未读取为传播前提，更未修改。

账本、历史输入和原核心文件保护详见 `preservation_check.json`。本轮模型调用、Token、费用、Z3 和生成代码执行均为 0。
