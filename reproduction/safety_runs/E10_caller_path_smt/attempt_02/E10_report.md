# E10 第二次执行报告：真实调用者范围与受限标量验证

日期：2026-11-03T15:36:26.264588+08:00。样本：`DBZ/all_cwe369.json:row=4:index=4`；JSON Pointer：`/4/function_call/0`。

**结果：在固定源码、五个已审查 in-tree 配置、明确32/64位实验合同及正常执行到达目标的范围内，真实调用者的unsigned闭区间约束导出两次零分母查询均为UNSAT。独立区间计算一致，自有测试15/15通过。**

这是“定点源码审查形成关系摘要 + SMT验证标量推论”的结果。没有把字符串命中、静态审查或Z3当作完整C程序认证；没有运行真实内核、恢复原构建TU或机器认证全部别名/并发关系。完整程序语义仍UNKNOWN，交付等待研究审查。

## 1. 输入、版本与第一次记录保护

正式函数体SHA-256：

`4ad8431edd6f874dcfb6b1c47d3d83607e7c3ce11f9521e45496eff794a5f9f6`

重新读取原JSON的UTF-8函数字符串，未规范化空白、换行或内容；分别与E09 `semantic_contract.json:/source_body_sha256`、`experiment_results.json:/source/function_body_sha256`比对，三方一致。原index=4、result=0均保留。dataset SHA-256仍为`0275cd83a4c1cf617f0049d6dbb191dcc3d232e5545ca0139bab3aa45f747fd8`。见input_verification.json。

第一次E10的8份文件逐一保存摘要并复核字节相同；它们继续记录当时错误输入造成的UNKNOWN。本次全部新增位于attempt_02，没有改写第一次报告或E09。

远程Git引用核验：gregkh/linux的v6.9.6标签对象为`185c18dcbe7edb086251c0a4fadb752f0b42aaaa`，剥离提交精确为`9c5a72fbc90d829ffb761da64a73c23cd4e0503f`。未执行GPG签名验证。全部源文件从该提交的HTTPS URL获取，保留原字节、路径、SHA-256、计算所得Git blob SHA-1及关键行号。URL和远程引用提供版本关联；没有额外下载Merkle路径或声称独立核验每个blob与提交树的链路。

共获取**29份必要源码/构建引用文件，516,867字节**，未克隆内核。五份主要源码摘要如下，其余配置、tuner、I/O及同步支持源码的完整摘要和行号均在source_manifest.json。

| 源文件 | SHA-256 |
|---|---|
| `drivers/media/dvb-core/dvb_frontend.c` | `f2d0148e54187d6de8de6f603928b32fdd45fbdb902c01790b63de4989c2ee83` |
| `drivers/media/dvb-frontends/stb0899_algo.c` | `a9afae91789e1a7a614fcb26a7aee486d963172055309b58714c56925b8dac83` |
| `drivers/media/dvb-frontends/stb0899_drv.c` | `a4facbbcf760607f0237e4d782c0ffb9d91603d888207da8c28492a725c32fcd` |
| `drivers/media/dvb-frontends/stb0899_priv.h` | `95c53392925d537856a0e562ed027c777df596030eca0050e09789d0449d3d21` |
| `include/media/dvb_frontend.h` | `8ad14a20692ea18e888aa9746fbf5bd97df0e7d8543067ff95672bedd39a7c87` |

`stb0899_algo.c`第107–113行与原JSON函数体逐字节相同，声明在107行、故障除法在110行，与原告警region.startLine=110一致。没有用函数同名替代内容对应。见upstream_body_verification.json。

## 2. 调用链、类型与状态身份

以下行号均指固定提交保存在sources/9c5a72fbc90d829ffb761da64a73c23cd4e0503f下的原文件。为简洁，drv/algo/priv分别指drivers/media/dvb-frontends/stb0899_drv.c、stb0899_algo.c、stb0899_priv.h；core指drivers/media/dvb-core/dvb_frontend.c。53份完整证据片段保存在source_evidence.json。

自动部分校验确切字节、位置、锚点和配置表；控制流、别名和效果结论来自显式静态源码审查，不冒称通用AST/别名证明器。

| 关系 | 来源与依据 |
|---|---|
| 输入/缓存类型 | include/media/dvb_frontend.h:592–605的dtv_frontend_properties.symbol_rate声明为u32；priv144–148的stb0899_params.srate也是u32。通用类型头的u32→__u32→unsigned int定义另存；实际架构未恢复，两个实验数据模型明确采用32位int/u32。 |
| 状态身份 | drv1616–1635独立分配demod状态，设置state->frontend.demodulator_priv=state并返回内嵌frontend；1417从该成员恢复state。关系来自同一分配对象，不能按变量名称拼接。 |
| 输入复制 | drv1418、1421、1426：i_params=&state->params，props=&fe->dtv_property_cache，随后i_params->srate=props->symbol_rate。 |
| 外层控制流 | drv1433范围判断，1452–1454的SYS_DVBS/SYS_DSS分支内，1484调用stb0899_dvbs_algo(state)。SYS_DVBS2在1502之后走另一算法。 |
| 传入同一state | algo489–493接受按值传入的state指针，params=&state->params；前缀中state和params没有重绑。 |
| 目标实参 | algo557为stb0899_calc_derot_time(params->srate)。实参来自params.srate，不能替换成不同字段internal->srate。 |

priv197–212将internal与params声明为两个不同非union成员；tuner_priv来自独立的STB6100/TDA8261分配。带宽输出指针&internal->tuner_bw与params.srate不是同一字段。对象关系在source_evidence.json:/typed_object_relations逐项附有来源。

## 3. INRANGE真实定义与unsigned语义

priv38–39实际定义为：

```c
#define INRANGE(val, x, y) (((x <= val) && (val <= y)) || \
                           ((y <= val) && (val <= x)) ? 1 : 0)
```

调用点x=1,000,000、y=45,000,000。两端点不同且递增；对同一个稳定u32值，反向合取45000000<=val<=1000000不可能成立，剩下**闭区间1000000<=val<=45000000**。宏多次读取字段，其稳定性需要后续写入和同步审查支持。

两个明示Linux标量模型均使用32位int，两个无后缀十进制常量可表示为int；与u32的unsigned int比较时，通常算术转换将其转为unsigned int。SMT使用bvuge/bvule，没有用signed比较替代。目标signed-long的srate>0则保留signed比较。

端点从固定源码唯一guard提取，来源为F_INRANGE/F_BRANCH，不是E09人为添加的srate>=1000。本轮没有从标签、自然语言告警或未经核验的更上层调用者引入数值前提。

## 4. 中间写入、回调与I/O审查

区间从drv1433范围判断到algo557读取实参，覆盖相关helper和五份配置。P_PRIVATE_FIELD/P_CALLBACKS/P_TRANSPORT保存结论；字段保持关系在有限源码范围内静态审查得到，Z3本身不证明该关系。

| 操作 | 实际效果与边界 |
|---|---|
| set_delivery | drv1290–1388修改局部寄存器镜像及设备I/O，不写params.srate。 |
| set_mclk/get_mclk | drv539–569更新internal.master_clk和设备寄存器；internal与params不同。 |
| I2C gate/read/write | drv1222–1246、213–265、484–532使用局部消息buffer；不传params.srate地址。write_regs先复制到局部buffer。 |
| stb0899_set_srate | algo66–99接收按值标量，计算局部变量并写寄存器，不修改缓存字段；do_div只操作按值局部n。 |
| algo489–557 | 写internal成员及局部reg/bclc/clnI；SETFIELD_VAL宏只写传入的局部寄存器lvalue；没有params.srate写入。 |
| STB6100带宽包装 | stb6100_cfg.h:51–87修改cache.bandwidth_hz、临时将cache.frequency置0并恢复，确实有副作用。实际set_params仅在frequency>0时调频，因此这个带宽前缀跳过调频分支。 |
| STB6100实际实现 | stb6100.c:241–296、502–549修改独立tuner状态、设备寄存器和带宽输出；此处输出指向internal.tuner_bw，不是params.srate。 |
| 潜在get_frontend回入 | stb6100.c:324–342调频可能调用fe->ops.get_frontend，但不在上述带宽前缀执行；固定drv1553–1564绑定也仅写属性cache/输出。不能笼统说全部tuner操作无cache副作用。 |
| TDA8261 | 带宽setter为NULL；tda8261_cfg.h:43–49只写*bandwidth=40000000。调频/读频位于目标调用之后。 |
| 适配器I/O | 另审查Mantis、SAA7146、AZ6027、PCTV传输实现。其写入对象为传输状态、设备及所供消息buffer。SAA cleanup甚至回写write消息，但本前缀buffer仍为局部数组。未传params字段地址。 |

五个配置逐项提取真实回调，不根据tuner同名推断效果：

| 配置源文件 | 初始化对象/位置 | tuner | 带宽set/get | gain |
|---|---|---|---|---|
| `drivers/media/pci/ttpci/budget-av.c` | `knc1_dvbs2_config`，第1100行 | TDA8261 | `NULL` / `tda8261_get_bandwidth` | NULL |
| `drivers/media/pci/ttpci/budget-ci.c` | `tt3200_config`，第1256行 | STB6100 | `stb6100_set_bandwidth` / `stb6100_get_bandwidth` | NULL |
| `drivers/media/pci/mantis/mantis_vp1041.c` | `vp1041_stb0899_config`，第254行 | STB6100 | `stb6100_set_bandwidth` / `stb6100_get_bandwidth` | NULL |
| `drivers/media/usb/dvb-usb/az6027.c` | `az6027_stb0899_config`，第254行 | STB6100 | `stb6100_set_bandwidth` / `stb6100_get_bandwidth` | NULL |
| `drivers/media/usb/dvb-usb/pctv452e.c` | `stb0899_config`，第857行 | STB6100 | `stb6100_set_bandwidth` / `stb6100_get_bandwidth` | NULL |

每份配置均核对了attach语句；STB6100/TDA8261安装在同一个frontend实例上。三份Kconfig提供这五个驱动的STB0899和tuner选择关系。覆盖题目要求的五份配置及固定实现，没有克隆全树或执行全仓库穷尽引用扫描；不将结论泛化到任意新配置。

## 5. 并发及同步边界

- core3040将fepriv.sem初始化为1，856–892的启动逻辑复用已有前端线程。
- 工作线程695获得该信号量，747调用ops.search；循环释放点681位于获取锁之前。所查search前缀及回调没有释放前端信号量。
- native ioctl在2071获取同一信号量，2100调用handle_ioctl，2102释放。compat property路径2245–2250使用同一信号量，其余转native路径。DTV_SYMBOL_RATE赋值位于1928–1929的setter中。
- STB6100在287、293存在msleep，且注释提醒其他线程可能开始；睡眠允许调度，但不释放持有的fepriv.sem，不能据此断言这些ioctl可覆盖当前参数。
- core270–279阻塞event helper确实释放/重取信号量，但位于不同的event ioctl路径，不是search前缀的callee；没有忽略这个释放点。
- budget-av.c:201–227的CI reset可能调用dvb_frontend_reinitialise；core351–358仅置标志并唤醒工作线程，实际初始化发生在工作线程获得sem后，没有在CI调用中直接重入search或写params.srate。
- dvb-usb-dvb.c:276–325仅包装init/sleep，没有替换search或上述tuner映射。priv中的search_lock没有实际用于本结论，不能用锁声明冒充保护证据。

在已审查写入者、五个配置、正常存活前端执行的范围内，没有未解决的params.srate覆盖路径，因此生成target_read_u32==guard_u32摘要。这个判断依赖显式源码审查和通常内核分配、消息buffer、信号量语义；未证明所有硬件故障、未定义行为、任意模块写内存或全部内核竞态均不存在。

**stb0899_attach在drv1641通过EXPORT_SYMBOL_GPL导出。out-of-tree配置、替换回调、未知直接调用者均不在认证范围。** 缺少字段保持/同步证据时返回UNKNOWN/拒绝，不求解该范围；测试覆盖该降级门。

## 6. 数据流、ABI合同与查询

caller_path_contract.json冻结出处及边界；caller_path_smt.py在求解前核验合同自身摘要、29份源文件、53份证据片段、E09 helper摘要、三方原函数体及upstream对应关系。没有重新运行E09实验或R01–R05。

分别建立32位unsigned输入、赋值后字段、guard读取、目标读取，以及signed-long实参：

```text
assigned_u32 = input_symbol_rate_u32
checked_u32 = assigned_u32
UGE(checked_u32, 1000000) AND ULE(checked_u32, 45000000)
target_read_u32 = checked_u32       [源码效果/同步审查摘要]
long32 = target_read_u32            [范围内可表示，保持位模式]
long64 = ZeroExt(32, target_read_u32)
selected_SYS_DVBS_or_SYS_DSS
signed_long_srate > 0
inner_division_defined
bvsdiv(signed_long_srate, 1000) == 0
```

32位long的区间上界45,000,000小于LONG_MAX，因此实际传入值可表示，没有擅自固定一般超范围u32→signed long的实现定义行为。64位long采用零扩展。两者都是参数化实验合同；原程序实际ABI仍UNKNOWN。

复用E09只读的typed signed_division和精确整数参考，不重写除法规则。内层bvsdiv向零截断；C definedness要求分母非0且排除LONG_MIN/-1。**故障查询不加入外层分母非0前提**，不消费Z3在分母0处的总化返回值。

准确SMT-LIB分别保存在query_32.smt2/query_64.smt2；对应JSON保存相同文本、出处、耗时及状态。set-info :status unknown是求解前导出器元数据，不是最终求解结果。

## 7. SMT结果与独立数学核对

现有Z3 4.13.4.0，QF_BV，timeout30,000ms。**总计2次solver.check，无失败/重跑的SMT查询；测试新增check为0。**

| long位宽 | 零分母查询 | 实测秒数 | 独立区间核对 |
|---:|---|---:|---|
| 32 | UNSAT | 0.006993600 | MATCH_NONZERO_DENOMINATOR |
| 64 | UNSAT | 0.007317200 | MATCH_NONZERO_DENOMINATOR |

UNSAT没有SAT模型，model明确为null。未申请或独立检查UNSAT证明证书；“独立计算一致”不等于独立核验了Z3证明对象。

独立参考使用Python任意精度整数abs(n)//abs(d)加符号，不使用浮点或负数直接//。正区间除以正1000的商单调：

```text
1000000 <= srate <= 45000000
1000 <= trunc_zero(srate / 1000) <= 45000
```

商下界1000严格大于0，与两次UNSAT一致；外层返回范围为[2,100]。该数学区间推论验证给定来源及保持前提的标量蕴含，不证明整个调用前缀一定执行成功，也不证明前缀中的其他算术安全。

**E09原局部A=SAT完整保留**：32位模型944、64位模型304均使局部内层商为0，但都不通过真实caller范围。E09的B仍是历史人为假设，没有被改成已提取事实。

## 8. 测试及边界结果

自有测试**15/15方法通过**。8个要求输入在两位宽各检查一次，共16条保存观察；另有每位宽13个具体公式代入，共26条，包含2^31和UINT32_MAX，检查unsigned/signed区别。不是历史告警通过数或全域穷举。

| 输入 | caller闭区间 | 局部反事实内层商 | 当前路径目标执行/返回 |
|---:|---|---:|---|
| 304 | 不通过 | 0 | 不调用，反事实除零不代表实际到达 |
| 944 | 不通过 | 0 | 不调用 |
| 999 | 不通过 | 0 | 不调用 |
| 999999 | 不通过 | 999 | 不调用 |
| 1000000 | 通过 | 1000 | 抽象路径模型返回100 |
| 45000000 | 通过 | 45000 | 抽象路径模型返回2 |
| 45000001 | 不通过 | 45000 | 不调用 |
| 0 | 不通过 | 不进入局部除法分支 | 不调用 |

保存的target_call_reached/actual_target_result指抽象标量路径可进入性及参考结果，不是内核运行轨迹/硬件实测；counterfactual_local_result明确标注局部反事实，不与被caller拒绝的实际路径混淆。

其他检查包括：宏及闭区间的有限对照、未知效果/未知同步/out-of-tree的UNKNOWN门、DVB-S2不属此路径、故意破坏字段保持关系时公式不接受、错误位宽/类型/除法语义拒绝、signed转换超范围拒绝、分母0及LONG_MIN/-1定义性、E09局部SAT及合同哈希冲突在求解前停止。没有原生C编译或内核运行。

## 9. 失败记录与执行计数

完整保留开发/获取失败：acquisition_tuner_types.json保存三个Kconfig被下载helper扩展门拒绝，以及误请求stb0899.h得到404。实际源码include为stb0899_drv.h，后续仍在同一提交获取正确头文件，并单独记录Kconfig；没有换版本或用其他源码冒充。

记录脚本第一次把87行头文件的片段末行误写为88，在生成合同/求解前报错。原脚本及development_failure_01.json不变，v2仅改正这一端点，development_revision_01.json保存差异和摘要。另一次报告helper创建命令因嵌套引号产生SyntaxError，在创建该helper或报告前即终止，见development_failure_02.json。以上是记录工具错误，不是C/Z3语义失配，也没有因此改变源码、合同或实验条件。

SMT只运行一次双位宽实验、自有测试只执行一次；所有查询/结果/失败记录均独占新建，没有覆盖旧结果。详细命令顺序与获取计数见execution_log.md。

## 10. 保护、验收与研究结论

第二次新增前建立preservation_baseline.json。最终保护检查：**PASS；8,168份既有非凭据文件、48个哈希组未变；第一次E10的8份文件逐字节相同。** 原始数据、标签、E09、R01–R05、历史结果和预算账本均在覆盖范围内；排除虚拟环境、Git内部、缓存、凭据类文件及本次attempt_02。保护PASS不等于语义认证/研究验收PASS。

Git HEAD仍为26e3ea8f718420fd80783902aa9835e79ee674ac，分支codex/e09-scalar-smt-publish-20261103，工作区干净；本地main未移动。**本轮未提交或推送**。LLM、Harness、原分析器、R01–R05执行和624项旧回归均0；未安装依赖、未构建完整内核。

acceptance_check.json逐条映射9项标准并注明静态审查/SMT/独立计算等证据等级。交付READY_FOR_RESEARCH_REVIEW，研究验收等待审查。

当前可支持的结论：**五个固定配置已审查、正常执行到达目标的路径上，真实caller闭区间能替代E09人为假设；在两种明确ABI合同下，目标外层分母为0的标量条件不可满足。**

仍不能宣称原告警获得完整程序认证、所有可能调用者安全、原标签已被重新证明、R05自动处理了真实完整路径，或整个调用前缀没有其他缺陷。源码审查摘要不同于自动机器证明，原构建和实际ABI也未恢复。

始终保持original_alert_decision=null、filter_authority=false、full_program_semantics=UNKNOWN。完成后停止，等待研究审查，不进入下一阶段。
