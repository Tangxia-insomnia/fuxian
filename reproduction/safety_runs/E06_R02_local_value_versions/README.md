# E06-R02 局部值版本证据层

这是独立离线复现模块，不接入原 LLM4PFA Engine、MCP、模型或安全裁决。总体结果和限制见 `E06_R02_report.md`；发布验收见 `acceptance_check.json`。

## 依赖与启动

从 reproduction 的父目录启动，使用已有 `.venv` 和 libclang 18.1.1，不安装依赖。PowerShell 示例（输出目录必须是全新目录）：

```powershell
& '.\reproduction\.venv\Scripts\python.exe' -B `
  '.\reproduction\safety_runs\E06_R02_local_value_versions\test_value_version.py' `
  --output '.\reproduction\safety_runs\E06_R02_local_value_versions\reruns\synthetic_new_01'

& '.\reproduction\.venv\Scripts\python.exe' -B `
  '.\reproduction\safety_runs\E06_R01_direct_call_argument_mapping\test_mapper.py' `
  --output '.\reproduction\safety_runs\E06_R02_local_value_versions\reruns\r01_new_01'
```

上述命令只重核受控合成逻辑，不能把其结果当作新的历史真实传播实验。发布材料的原始合成输出不会被覆盖。

已实际执行的候选顺序：

```text
test_value_version.py --output <本目录>/synthetic_runs/final_candidate_01
原 R01 test_mapper.py --output <本目录>/r01_core_recheck
run_r02.py historical
freeze_candidate.py
run_r02.py fixed20
finalize_results.py
```

`historical/`、`fixed_20/`、冻结和结果文件均用排他创建保护；本候选的固定 20 已运行一次，不允许在本候选上重跑或挑结果。后续修改必须新候选/新目录并获得授权，不能删除本轮输出绕过保护。汇总脚本只读取已完成结果，不重新执行候选。

## 输入、输出和合同

- 输入：自包含测试 C 文件，或已保存历史 frame 原始字节；必须绑定 dataset_id/position 与真实 build_status。
- 输出：逐函数局部 slot、版本、读取、定义事件、路径环境、源码位置/哈希及 PASS/REJECT/UNKNOWN/NOT_APPLICABLE。
- `mapping_contract.md` 定义 R01 slot/transfer 与 R02 版本边界；`R02_design_and_scope.md` 保存开发前范围。
- `synthetic_fixtures/cases.json` 保存源码 SHA/预期；`synthetic_runs/` 保留启动失败、开发轮和最终轮全部输入依据与结果。
- `historical_results.json` / `historical/` 保存 3 个风险样本，旧诊断与新 UNKNOWN 明确分开。
- `candidate_manifest.json` 冻结代码/配置/依赖/输入和前置测试证据 SHA；`fixed_20_results.json` / `fixed_20/` 是一次全新固定回归。
- `metrics.json` 分开统计合成检查、源码状态、候选 REJECT、版本/读取与真实样本；`preservation_check.json` 核验原有文件。

最终合成 110/110 符合预期，R01 41/41；历史 3 UNKNOWN，固定 20 UNKNOWN。局部 PASS 不代表告警可过滤；本模块没有 FILTER/KEEP 接口，没有 SMT 或求解。
