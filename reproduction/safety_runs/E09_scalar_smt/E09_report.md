# E09：首个 SMT/Z3 标量验证原型

日期：2026-11-03。**局部标量实验成功：32位、64位两种显式有符号long合同均得到 A=SAT、B=UNSAT，SAT模型与独立整数计算一致。**

这是保存函数片段的有限语义编码实验。原始ABI、编译上下文、调用者可达性及完整项目语义仍为UNKNOWN；没有裁决或过滤原告警，原标签0保留。

## 1. 输入与保护

用户指定：`DBZ/all_cwe369.json:row=4:index=4`。沿用审计定位符：`benchmark/DBZ/all_cwe369.json:row=4:index=4`。原JSON没有`sample_id`字段；两者均是来源限定定位符，不冒称新增了原数据身份。

原文件：`E:/codexconversation/课题研究/reproduction/upstream/benchmark/DBZ/all_cwe369.json`。

| 内容 | 值 |
|---|---|
| 原零基row / index / label | 4 / 4 / 0 |
| dataset SHA-256 | `0275cd83a4c1cf617f0049d6dbb191dcc3d232e5545ca0139bab3aa45f747fd8` |
| UTF-8 function_body SHA-256 | `4ad8431edd6f874dcfb6b1c47d3d83607e7c3ce11f9521e45496eff794a5f9f6` |
| 审计candidate_samples.json SHA-256 | `2788dff05a5f611965fb9745bb62379bc76683639a5dedacc643b00fcf02aef0` |

`scalar_smt.py` 的 `load_inputs()` 在任何编码和求解前校验审计文件、原dataset字节、原index/label、唯一函数载荷及函数体哈希。不匹配直接抛出`InputMismatch`并停止。测试使用内存模拟验证拒绝路径，没有改坏原文件。

`experiment_results.json:/source` 保存原记录全文、源码、位置、Pointer、ID及哈希。原位置元数据为`linux-6.9.6/drivers/media/dvb-frontends/stb0899_algo.c`，region行110；这里没有据原TU复核它。保存片段的声明/guard/除法位置分别为局部行1/3/4，不能混同两种坐标。

本次基线：发布克隆HEAD=`c949e29467153aa82efcab5965b6aa7a8ce77691`，分支`codex/smt-dataset-audit-publish-20261103`，工作区干净；原本地main仍=`fb8e98e0771304ef97682a57f5fcf4969abb216b`。官方实现仓库仍冻结于`4efb4b9bf7e845e180451b43ba29a25e3edaa0e3`。本轮不切分支、不提交、不推送。

`preservation_baseline.json` / `preservation_check.json` 实测保护PASS：**8,151份既有非凭据文件、48个哈希组均未变**，包括R01–R05、旧实验、审计、预算账本和官方输入；Git状态也未变。排除E09新增目录、虚拟环境、Git内部、缓存和凭据类文件。保护PASS不是程序语义证明。

## 2. 局部C语义合同

```c
static long stb0899_calc_derot_time(long srate)
{
    if (srate > 0)
        return (100000 / (srate / 1000));
    else
        return 0;
}
```

合同详见`semantic_contract.json`：

- `srate`分别为32位、64位二进制补码有符号位向量。**这是两个实验假设，不是恢复的原ABI。** 两种合同值域分别为`[-2^31,2^31-1]`、`[-2^63,2^63-1]`。
- 整数除法向零截断。使用有符号`bvsdiv`、有符号比较；不使用`UDiv`或无界Int除法冒充C整数语义。
- 常量0、1000、100000均精确可表示；与long操作数共同运算时按通常算术转换使用共同的signed-long类型。这里无需猜测原int的宽度，也不模拟其他C整数类型。
- C除法的定义条件独立记录：分母非0，且不出现`LONG_MIN / -1`溢出。内层固定分母1000满足其分母要求；外层必须在内层商非0时才可作为C运算求值。
- `srate<=0`走else返回0，不在该C路径执行任一除法。
- Z3位向量运算是总化的；**分母为0时的Z3运算值不是C结果**。编码将值项与definedness分开。分母为0的参考执行记录`UNDEFINED_DIVISION_BY_ZERO`、`outer_evaluated=false`、`return_value=null`。

`parse_fragment()` 对整个保存函数作受限语法full-match，提取已核对的函数/参数、guard常量和两个除法常量，再由`encode_fragment()`实例化固定模板；同时以源码哈希和精确函数/常量限制准入。它没有用任意子串命中替代结构检查，也不是通用C解析器、原TU AST认证或完整C→SMT编译器。宏、cast、额外语句、其他运算/类型/函数均拒绝。

## 3. 查询及定义前提的位置

两组查询均检查“执行外层除法之前，分母是否可能为0”：

| 查询 | 来源与前提 | 故障条件 |
|---|---|---|
| A | 保存函数的`srate > 0`；内层除法定义性检查 | `trunc_zero(srate/1000) == 0` |
| B | A加上`srate >= 1000` | 同上 |

**B的`srate>=1000`由本实验人为加入，未从原工程提取或证明。** 它单独保存`experimental=true`、`proven_in_original_project=false`，不与函数原始guard混成“已知事实”。

核心故障查询不添加外层`denominator!=0`前提，否则会提前排除待检查的错误。外层执行前提保存在`outer_execution_precondition_smt2`，`outer_definedness_asserted_in_fault_query=false`。求解对象是故障到达前状态，没有把未定义C除法的返回值拿来求解。

逐次准确SMT-LIB保存在每个run的`formula_smt2`，可见`bvsdiv`、`bvslt/bvsle`。其中`(set-info :status unknown)`是Z3导出器在求解前写的元信息，不是该次求解最终状态；真正结果在run.status。

## 4. 实测结果

现有环境：`E:/codexconversation/课题研究/reproduction/.venv/Scripts/python.exe -B`；未安装依赖。Z3包/运行时版本均为 **4.13.4.0**，查询逻辑`QF_BV`，每次timeout为30,000ms。

| long合同 | 查询 | Z3结果 | 具体模型/说明 | 独立模型核对 |
|---:|---|---|---|---|
| 32位 | A | **SAT** | `srate=944`，内层商0 | MATCH |
| 32位 | B | **UNSAT** | 人为范围假设下不存在零分母模型 | 不适用：没有SAT模型 |
| 64位 | A | **SAT** | `srate=304`，内层商0 | MATCH |
| 64位 | B | **UNSAT** | 同上 | 不适用：没有SAT模型 |

两种合同的SAT/UNSAT结论一致，不要求Z3选择相同模型。参考计算用Python任意精度整数的`abs(n)//abs(d)`加符号，完全不调用Z3，也不使用可能损失64位精度的浮点除法。944和304均正且小于1000，参考商为0；外层不进行实际除法计算。

B在正数且不小于1000的范围内，向零截断的内层商至少为1，支持该局部UNSAT结论。保存的是**Z3报告的UNSAT**，没有请求、导出或独立检查证明证书；没有把数学范围说明当作原项目调用者证明。

`experiment_results.json`保存来源、完整语义合同、合同/实现哈希、ABI假设、变量/值域、准确查询、solver版本、结果、模型、独立核对、超时和限制。`filter_authority=false`、`original_alert_decision=null`、`full_program_semantics=UNKNOWN`贯穿结果。

## 5. E09自有测试

`test_scalar_smt.py` **13/13测试方法通过**，见`test_results.json`。其中子场景和差分数单列，不把它们说成真实告警通过数：

- 两种合同分别验证1→0、999→0、1000→1、1001→1；后两种参考外层返回100000，前两种未定义外层不求值。
- 0、-1、-999、-1000、各自LONG_MIN均不进入除法分支，返回0。
- 独立有符号除法helper与具体Z3化简比较，覆盖正负分母、向零截断、LONG_MIN/MAX和64位精度边界。尤其`-999/1000=0`、`-1001/1000=-1`，不能使用Python负数`//`的结果直接替代C截断。
- 额外对每种位宽的1–2001做具体内层除法差分，共**4,002对**均一致；不是枚举整个32/64位域。测试另保存36条边界/符号/极值观察。
- 分母0及`LONG_MIN/-1`的definedness为false，参考实现拒绝；不消费Z3在未定义点的总化值。
- 拒绝16/128位、bool/string位宽、unsigned/int/float/指针类型、floor语义、宽度混配、越界值、未审查语法/常量及未知查询。没有为错误输入触发SolverFor。
- 数据集/函数体hash门拒绝测试、故意错误的模型拒绝测试、B假设来源和局部权限检查均通过。
- 测试读取已保存的4个核心查询结果并重新核对模型，不再发起额外`solver.check()`；具体项仅使用Z3化简。没有原生C编译/运行，独立计算是按C规则实现的数学参考，不能冒称原工程执行对照。

没有发现实际编码与参考C除法语义不一致；故意构造的错误输入/模型属于预期拒绝测试，不是被隐藏的实测语义失配。

## 6. 开发失败与执行次数

首次开发运行在第一次`solver.check()`返回后，因把`CheckSatResult`用作Python字典键而报`TypeError: unhashable type: 'CheckSatResult'`。该次没有生成完整实验结果、没有记录模型核对；求解返回状态未在异常前保存，因此失败记录不猜测它的值。

`development_failure_01.json`保留异常、代码哈希、查询位置及1次已完成check。修复仅将封装改为读取`str(answer)`，未修改C语义编码；之后完整运行4组查询成功并执行自有测试。没有发生需按语义停止条件终止的C/Z3失配，也没有冻结后重跑固定20。

准确计数：**solver.check总计5次 = 开发失败时1次 + 完整实验4次**；测试额外check为0。Z3具体化简与这5次查询分开，不称“Z3仅调用4次”。LLM、Harness、原分析器、R05 Builder/Validator、624项旧回归执行均为0；费用0元。

## 7. 七个研究问题

| 问题 | 回答 |
|---|---|
| 1. 成功实现有限C整数除法编码？ | **是，在明确32/64位signed-long合同、受限完整源模板和definedness边界内。** 不是完整C语言认证。 |
| 2. Z3正确识别两组SAT/UNSAT？ | **是，4个核心结果符合局部义务。** A有已核对模型，B为无证书的solver UNSAT。 |
| 3. 两种合同一致？ | **是，均A=SAT、B=UNSAT。** 不代表已经确定原ABI，也不代表所有其他C程序对位宽不敏感。 |
| 4. 独立计算可验证吗？ | **SAT模型与具体算术可以。** 精确整数参考和4,002对有限差分一致；未作全域穷举或独立UNSAT证书检查。 |
| 5. 尚未覆盖什么？ | 原TU/构建/真实ABI、调用者范围和可达性、其他类型/算术/提升情形、一般CFG/循环、宏/typedef、指针数组、内存、副作用和跨函数。 |
| 6. 可复用于下一标量告警吗？ | **可复用哈希门、typed位向量/definedness、整数参考和结果封装机制。** 当前源码准入固定于本函数，下一样本必须独立定义语义范围及来源，不能直接换sample ID声称通用支持。 |
| 7. 值得扩大支持范围吗？ | **值得逐项、受限扩大标量合同。** 先审查一个相近纯标量义务、明确类型/定义性和反例测试，再谈接入更多程序证据；本轮不实施，不扩到一般内存或跨帧。 |

原标签0表示作者数据中的原标注，未改动。A说明保存函数内部guard不足以排除某些局部输入；真实调用者可能不允许这些输入。B只说明人为范围足以改变局部性质。因此本次不判断原标签错误、不提高数据集准确率统计，也不授权过滤原告警。R01–R05和E08对真实程序证据不足的结论均保留。

## 8. 交付与复查

全部新增位于`E:/codexconversation/课题研究/reproduction/safety_runs/E09_scalar_smt/`：

- 要求的`E09_report.md`、`scalar_smt.py`、`semantic_contract.json`、`experiment_results.json`、`test_scalar_smt.py`；
- 必要记录`test_results.json`、`development_failure_01.json`、`preservation_baseline.json`、`preservation_check.json`。

已完成命令：

```powershell
& 'E:\codexconversation\课题研究\reproduction\.venv\Scripts\python.exe' -B 'E:\codexconversation\课题研究\reproduction\safety_runs\E09_scalar_smt\scalar_smt.py'
& 'E:\codexconversation\课题研究\reproduction\.venv\Scripts\python.exe' -B 'E:\codexconversation\课题研究\reproduction\safety_runs\E09_scalar_smt\test_scalar_smt.py'
```

成功结果采用独占新建；不要覆盖本次产物来隐藏后续运行。原数据/R01–R05/旧结果只读，未提交、推送或自动启动下一阶段。

**E09完成后停止，等待研究审查。**
