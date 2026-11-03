# E10：真实调用路径约束认证——入口哈希冲突停止报告

记录时间：2026-11-03T14:37:21.988518+08:00。

**研究结果：UNKNOWN；入口哈希校验失败，按本轮第三节的停止条件终止。E10 未实现、未验收通过。**

## 1. 已确认的本地证据

样本：`DBZ/all_cwe369.json:row=4:index=4`。原记录的 index=4、result=0，未修改。

原始文件：`reproduction/upstream/benchmark/DBZ/all_cwe369.json`；目标函数字段 JSON Pointer：`/4/function_call/0`。函数体按原字符串 UTF-8 编码计算 SHA-256，不进行空白、换行或内容规范化。

| 核验对象 | SHA-256 |
|---|---|
| 本轮 E10 指定的函数体哈希 | `4ad8431edd6f874dcfb1b6c47d3d83607e7c3ce11f9521e45496eff794a5f9f6` |
| 原始 JSON 函数体实算哈希 | `4ad8431edd6f874dcfb6b1c47d3d83607e7c3ce11f9521e45496eff794a5f9f6` |
| E09 semantic_contract.json 的 source_body_sha256 | `4ad8431edd6f874dcfb6b1c47d3d83607e7c3ce11f9521e45496eff794a5f9f6` |
| E09 experiment_results.json 的 source.function_body_sha256 | `4ad8431edd6f874dcfb6b1c47d3d83607e7c3ce11f9521e45496eff794a5f9f6` |
| SMT_dataset_audit/candidate_samples.json 对应 function_body_sha256 | `4ad8431edd6f874dcfb6b1c47d3d83607e7c3ce11f9521e45496eff794a5f9f6` |
| 原始 dataset 文件哈希 | `0275cd83a4c1cf617f0049d6dbb191dcc3d232e5545ca0139bab3aa45f747fd8` |

两份函数体摘要都是64位十六进制字符串，但本轮指定值的 `cfb1b6c47` 与实际的 `cfb6b1c47` 不同。**原始数据、既有审计和 E09 三者一致；没有证据表明它们发生了变化。** 不能默默将本轮摘要替换成推测的正确值。

输入校验仅支持保存字节及原身份的一致性，不构成对上游源码、版本或调用路径的认证。

## 2. 停止依据与未完成范围

本轮第三节要求：“如果版本、哈希或源码位置不一致，立即停止并报告 UNKNOWN。” 已在读取本地输入时发现哈希冲突，因此不再获取或检查上游调用链。

指定的 `gregkh/linux`、`v6.9.6`、commit `9c5a72fbc90d829ffb761da64a73c23cd4e0503f` 仅记录为待核验目标，未声称版本已验证。五份已命名源码、五个 in-tree 配置及 tuner 回调均未获取或认证，详见 source_manifest.json。

尚未审查：INRANGE 展开与 unsigned 转换、实参与形参和 state 别名、范围检查后的中间写入与回调、工作线程和 ioctl 同步。没有提取任何已认证 caller constraint。out-of-tree 配置不在拟认证范围内，也没有得到任何安全结论。

未创建 caller_path_smt.py 或 test_caller_path_smt.py，避免将未实施的原型包装成已交付实现；experiment_results.json 和 test_results.json 明确标注 NOT_RUN。边界测试0次，SMT/Z3求解0次，LLM/Harness/原分析器/旧回归运行均0次，网络源码获取0次。

## 3. E09 与 E10 的性质边界

既有 E09 的32/64位局部 A=SAT、带人为假设的 B=UNSAT 作为只读历史引用保留，没有重新运行。它们不能替代 E10 的真实路径认证。

E10 的32/64位真实 in-tree 路径性质均为 UNKNOWN，没有生成新 SMT 公式、模型或 UNSAT 结果，也未进行独立算术对照。原始 ABI 未恢复，完整程序及 out-of-tree 调用者未知。

`original_alert_decision=null`；`filter_authority=false`；`full_program_semantics=UNKNOWN`。本轮没有过滤授权。

## 4. 文件保护与交付

发布克隆 HEAD：`26e3ea8f718420fd80783902aa9835e79ee674ac`；当前分支：`codex/e09-scalar-smt-publish-20261103`；本地 main：`fb8e98e0771304ef97682a57f5fcf4969abb216b`。开始与结束工作区均干净，Git状态未变；没有提交或推送。

preservation_baseline.json 在首次新增产物前建立快照；preservation_check.json 对既有非凭据文件复核：**PASS，8,160份文件、47个哈希组，变化组0个**。保护检查只说明文件与Git未变，不是研究验收PASS。覆盖与排除规则完整记录于这两份文件中。

本次仅独占新建 E10_report.md、failure_record.json、caller_path_contract.json、source_manifest.json、experiment_results.json、test_results.json、preservation_baseline.json、preservation_check.json。所有缺失阶段均如实标记，没有生成占位测试通过结果。

## 5. 继续的必要条件

先由研究方明确本轮应采用的函数体摘要，解决任务输入与已冻结证据的冲突；在此之前保持停止。该输入问题解决后仍需执行全部源码版本、调用链、中间修改、并发及SMT验收，不能将本报告的文件保护PASS视为E10通过。

本轮第六项边界要求“验收前不自动提交或推送”，优先于先前一般发布偏好；没有发布本次未通过实验，也未进入下一阶段。
