# R01-RF：空上下文问题定位与结构契约

本轮只修正历史证据运行器。原 R01 `mapper.py`、类型/身份检查、配置和全部历史结果不改动。以下来源行号均指现有代码的一基行号，文件 SHA-256 在本轮 baseline/candidate 清单中。

## 1. null 的实际来源

`safety/replay.py:49` 的 `load_bundle()` 导出历史证据；第 59 行明确使用：

```python
'context': read(context_file) if context_file.exists() else None
```

因此在这一导出格式里，**字段存在且为 null 表示没有已保存的 context.json 文件**。仅凭 null 本身不能推出失败原因、源码完全不存在或无需检查。官方告警中的 `location.context` 是另一种对象（源码片段位置），不能与本 bundle 根 `context` 混为一谈。

`completion/context.py:141` 的 prepare() 正常返回含 frames 的对象；恢复失败抛出 ContextUnavailable。`scripts/run_completed.py:106` 将该异常记录为 blocked_context。`completion/engine.py:182` 只在进入实际运行后保存 context.json。旧导出器随后将未保存上下文的情况转为显式 null。以上代码本轮仅阅读，没有导入执行。

固定第 13、16 条都同时满足下列证据，故属于**合法的证据缺失记录**：

| 固定序号 | sample_id | 原始错误 | 原始 context.json |
| --- | --- | --- | --- |
| 13 | NPD/cppcheck/linux:row=13:index=None | Function kvm_for_each_vcpu: 0 distinct available definitions | 不存在 |
| 16 | NPD/codeql/kernel69:row=26:index=45 | Expected one function definition, found 0 | 不存在 |

两条原 `sample_result.json` 都为 blocked_context；原绑定清单、规范 bundle 摘要、原文件 SHA-256 和实际文件缺失互相对应。新运行器按通用绑定规则检查这些事实，没有针对序号/样本 ID 特判。仍保留原始错误；本轮不重新恢复上下文，也不使用 alert.function_code 替代缺失 frames。

## 2. 结构不能混同

| 输入 | 本轮处理 | 理由 |
| --- | --- | --- |
| context=null，且原绑定/状态/错误/缺文件全部核实 | 合法缺证据；UNKNOWN；frame_count=null | 不适用不成立，原分析材料确实缺失 |
| context=null，但无来源/状态冲突 | DataShapeError，保存错误并停止 | 不能猜测 null 的含义 |
| context 字段缺失 | DataShapeError | 导出器始终产生该键；缺失可能是损坏或未知格式 |
| context={} | DataShapeError: FRAMES_FIELD_MISSING | 不是含零帧的有效对象 |
| context=[] / 字符串 / 数字 / 布尔 | DataShapeError | 字段类型不符合格式 |
| context={"frames":[]} | 明确空 frames；按原规则 UNKNOWN | 与 null 保持不同结构状态，不作强制转换 |
| context.frames=null / {} 或损坏 frame/code/hash | DataShapeError，保存错误并停止 | 格式错误不能伪装成空证据 |
| 正常含有效 frames 的对象 | 原 R01 流程与原判定不变 | 单帧仍 N/A；多帧缺构建仍 UNKNOWN |

没有使用 `context or {}`、`get('context') or ...` 等将缺失/null/空容器统一处理的写法。

## 3. 原因与影响范围

旧 `run_regression.py:66` 在进入 `if not frames` 之前就执行 `bundle['context']['frames']`，假设每份 bundle 都有可下标的 context。原开发合成测试验证的是 C 映射核心，没覆盖导出格式的 null；运行器只有“frames 空数组”的后置分支。因此第 13 条在进入任何 AST 分析前抛出 TypeError。

本次新增的是**输入结构与来源验证**，不是修改 R01 PASS/REJECT/UNKNOWN 语义。`mapper.analyze()` 的输入是已落盘源文件及数据/构建身份，不接受 bundle.context，所以本次错误不涉及 R01 核心参数映射算法。

## 4. 最小补丁内容

新副本 `run_regression.py` 引用旧目录的原 mapper/config/offline_boundary，不复制或修改它们。增加 context_state() 明确分支；只有显式 null 才调用 null_context_provenance() 核对历史来源。新增 execute_specs() 把真正运行错误的类型、消息和完整 traceback 单独保存后重新抛出，立即停止，不生成 UNKNOWN/N/A 来掩盖异常。

其他差异仅为独立输出目录、新冻结清单和第二次完整运行的标识/统计。原来正常样本的源码解析、候选调用定位、类型检查和单帧/多帧判定代码保留；完整差异见 runner_patch.diff。

## 5. 旧异常的保存边界

旧 `fixed_20/13/failure.json` 和包含前 12 条结果的整个旧 R01 目录保持字节不变。旧文件保存了异常类型、消息、位置和上下文，**没有单独保存当时完整 stderr 文件**。本轮运行器测试对同一旧下标表达式做合成重现，保存新 traceback，并明确标为新重现，不冒充原始 stderr。新候选若出现异常则保存完整 traceback 并停止。

旧 R01 报告另列的 union/RECORD 等范围限制继续保留，没有在本轮修改、扩大支持或进行新的核心修复。此次回归只验收原来声明并测试的 R01 子集与运行器空证据处理，不证明通用 C 语义覆盖。
