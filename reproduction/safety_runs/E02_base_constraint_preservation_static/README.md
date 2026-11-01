# E02：基础约束保留契约静态验证

这是独立验证目录，没有修复或接入原算法。使用 Python 3.11 标准库；无第三方依赖。论文/官方代码固定为 arXiv:2506.10322v1 / `4efb4b9bf7e845e180451b43ba29a25e3edaa0e3`。

主要入口：[E02_report.md](E02_report.md)、[historical_replay_report.md](historical_replay_report.md)、[metrics.json](metrics.json)。

## 能力与结果协议

[checker.py](checker.py) 提供 `check_contract(B, delta, Final, formats=..., refs=..., extra_deltas=...)`。

- `PASS`：在支持子集内，基础和新增声明/断言的结构成员完整、sort 与字面 SMT 身份一致，未出现未解释的额外成员。不是语义正确、可求解或安全的证明。
- `FAIL`：发现明确的结构保留/身份/sort 契约违反。并不证明等价变形不存在，也不代表缺陷真假。
- `UNKNOWN`：不支持、证据缺失或额外成员来源未确认。`parse_errors` 显式标注 UNSUPPORTED 原因。
- `NOT_APPLICABLE`：样本未发生约束生成调用，无可检查转换；只在数据集汇总层使用。

`semantic_correctness` 与 `polarity_correctness` 始终为 NOT_ASSESSED；`alert_safety_decision` 始终为 null。本目录不输出任何新告警安全裁决。

## 结构化解析边界

SMT-LIB reader 处理 S-expression、分号注释、受限引用符号、declare-const/零参 declare-fun、Int/Bool/Real/显式宽度 BitVec、assert、let、标量比较/算术/布尔运算和查询边界。`let` 是词法展开；不按交换律重排、不做逻辑等价或可满足性判断。`check-sat` 只记静态边界，绝不执行。

历史输出主要是 Z3Py。AST reader 只读取显式声明、受限标量表达式、add、Solver 创建、最后一次静态 check 的断言/声明快照和受限返回结构。不会导入 z3、eval、exec 或运行输入。Python 片段的 `s.add` 约定外部已有 `s`，在静态 IR 中标注 implicit_receiver；不是实际创建求解器。纯打印模型诊断可识别，普通条件控制流、循环、push/pop、check assumptions、数组/量词、复杂函数、动态索引等均不支持。

同一 SMT symbol+sort 可被显式不同 Python 别名引用；没有证据的改名不推断等价。不同 C 作用域、别名、重赋值和跨函数对象身份不能靠该字面身份得到证明。基础/增量的声明可用于解读最终缺声明的引用，但不会因此被算作 Final 已声明。

重复断言按成员存在检查，另计重复次数，保留原输入与 IR，不删除断言。重复同 sort 声明被记录；PASS 也不说明重复声明符合某个 SMT 执行器的语法要求。额外声明/断言在没有明确增量来源时记 UNKNOWN。U09 的两个增量集显式提供，不能只检查 B。

## 文件与证据

| 文件/目录 | 内容 |
| --- | --- |
| baseline_state.json | 开始前 Git、固定输入哈希、3516 个原有文件哈希 |
| checker.py / test_checker.py / run_e02.py | 静态检查器、合成测试、只读历史证据检查 runner |
| experiment_config.json / candidate_freeze.json | 检查契约与冻结候选/输入哈希 |
| synthetic_cases/ / synthetic_test_results.json | 最终 37 项通用输入与逐项结果 |
| synthetic_development_*.json / audit_10_development_* | 冻结前开发输出，不计作冻结回归结果 |
| evidence/ | 历史记录副本与每次检查的 B、Δ、Final、来源；开发/最终候选分目录保留 |
| audit_10_results.json / fixed_20_results.json | 固定逐样本/逐转换结果，包含 IR、缺失项、冲突和时间 |
| fixed_20_started.json | 冻结后唯一一次回归启动记录，防止无声重跑 |
| metrics.json / execution_log.md | 计数口径、统计与实际执行过程 |
| preservation_check.json / hashes.json | 最终保护检查及输出文件哈希清单 |

## 本轮实际执行顺序

在工作区根目录 `E:\codexconversation\课题研究`，使用 `C:/Users/22803/anaconda3/python.exe -B` 执行以下脚本：

```powershell
python -B reproduction/safety_runs/E02_base_constraint_preservation_static/test_checker.py
python -B reproduction/safety_runs/E02_base_constraint_preservation_static/run_e02.py audit_10
python -B reproduction/safety_runs/E02_base_constraint_preservation_static/run_e02.py freeze
python -B reproduction/safety_runs/E02_base_constraint_preservation_static/run_e02.py fixed_20
```

这些命令的正式输出已存在，runner 使用独占创建，**不要原地重跑回归命令**。未来若需另一个实验，须使用另一个经明确授权的新目录，不覆盖本轮记录，也不称为未接触过的独立验证。

可仅重复通用合成检查，给一个尚不存在的输出文件名；它不重读固定 20 条响应：

```powershell
python -B reproduction/safety_runs/E02_base_constraint_preservation_static/test_checker.py synthetic_recheck_unique_name.json
```

单个 SMT-LIB 文件的静态调用示例：

```powershell
python -B reproduction/safety_runs/E02_base_constraint_preservation_static/checker.py --base B.smt2 --delta delta.smt2 --final Final.smt2 --format smtlib
```

示例文件需由调用者提供；现有测试输入在 synthetic_cases/*.json。既有历史转换输入 JSON 可逐项交给 Python API 重核，但该操作不属于本次固定集的唯一正式运行。

## 禁止混淆

没有新 SMT2 求解结果，没有模型费用，没有 Harness 启动，没有修改 E01/安全 v1。静态通过率不是路径准确率、过滤率或真实缺陷保留率。所有历史调用成本、历史 SAT/UNSAT 仅作为原文件内容留存，没有在本轮产生或用于新告警判定。
