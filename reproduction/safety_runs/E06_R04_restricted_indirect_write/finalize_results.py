"""Final acceptance and report from saved evidence only; no analysis reruns."""
import json
from r03_adapter import ROOT,REPRO,r01,counts,offline_boundary
from run_r04 import save,verify_frozen
from r04_protection import preservation


def load(n):return json.loads((ROOT/n).read_text('utf-8'))


def main():
    offline_boundary.install();manifest=verify_frozen();protected=preservation()
    save(ROOT/'preservation_check.json',protected)
    s=load('synthetic_test_results.json');a=load('pre_freeze_evidence_check.json');h=load('historical_results.json');f=load('fixed_20_results.json')
    regressions={key:load(path) for key,path in [('R01','r01_core_recheck/test_results.json'),('R02','r02_core_recheck/synthetic_test_results.json'),
        ('R03','r03_core_recheck/synthetic_test_results.json'),('R03_boundary','r03_boundary_recheck/test_results.json')]}
    orig=json.loads((REPRO/'safety_runs/20261029_v1/fixed_holdout.json').read_text('utf-8'))
    bytest={t['test']:t for t in s['tests']}
    checks={'all_synthetic_expected':s['all_passed'] and s['passed']==s['total']==257 and s['fixture_count']==68,
        'wrong_targets_objects_contexts_rejected':sum(t['actual']=='REJECT' and t['expected']=='REJECT' for t in s['tests'])==10,
        'escape_and_unknown_effects_blocked':a['all_passed'] and a['unknown_attempts_confirmed_blocked']==37,
        'old_value_preserved':bytest['S03_old_copy_preserved']['passed'],
        'new_version_exact_object':bytest['S01_full_chain_distinct_identities']['passed'] and a['all_passed'],
        'pointer_local_rebind_not_caller_write':bytest['S04_rebind_no_caller_version']['passed'] and bytest['S04_pointer_local_version_only']['passed'],
        'independent_context_memory_versions':bytest['S06_updates_only_own_target']['passed'] and bytest['S07_same_site_distinct_paths']['passed'] and a['all_passed'],
        'all_prior_regressions_pass':all(regressions[k]['all_passed'] and regressions[k]['passed']==regressions[k]['total']==n for k,n in [('R01',41),('R02',110),('R03',201),('R03_boundary',15)]),
        'fixed20_complete_no_exception':f['complete_new_run'] and f['metrics']['completed_samples']==20 and f['metrics']['runtime_errors']==0 and not (ROOT/'fixed_20/failure.json').exists(),
        'fixed20_original_order':[r['sample_id'] for r in f['rows']]==[r['sample_id'] for r in orig['samples']],
        'fixed20_single_fresh_run':load('fixed_20/run_start.json')['attempt']==1 and f['old_results_reused']==0,
        'historical_diagnoses_preserved':len(h['rows'])==4 and all(r['status']=='UNKNOWN' for r in h['rows']) and all(not d['recomputed_or_promoted_by_R04'] for r in h['rows'] for d in r['prior_diagnoses_preserved']),
        'existing_files_and_budget_unchanged':protected['status']=='PASS',
        'no_forbidden_external_operations':not any(d.get('external_operations') for d in [s,h['metrics'],f['metrics']]+list(regressions.values())) and not offline_boundary.EVENTS,
        'frozen_code_inputs_dependencies_unchanged':True,'no_R05_or_safety_integration':manifest['R05_started'] is False and manifest['safety_integration'] is False}
    accepted=all(checks.values());acceptance={'status':'PASS' if accepted else 'REJECT','checks':checks,
        'publication_permitted_by_user_if_all_pass':accepted,'FILTER_authority':False,'stop_after_R04':True}
    save(ROOT/'acceptance_check.json',acceptance)
    metrics={'candidate':manifest['candidate'],'synthetic_scenarios':68,'synthetic_checks':257,'checks_met_expectations':s['passed'],
        'scenario_status_counts':s['scenario_status_counts'],'check_status_counts':s['check_status_counts'],
        'relation_metrics':s['relation_metrics'],'relation_analysis_count':s['relation_analysis_count'],
        'context_isolation_counts':a['context_isolation_counts'],'escape_event_status_counts':a['escape_event_status_counts'],
        'escape_reason_counts':a['escape_reason_counts'],'unknown_attempt_block_counts':a['unknown_attempt_block_counts'],
        'regressions':{k:{'passed':v['passed'],'total':v['total'],'check_conformity_counts':{'PASS':v['passed'],'REJECT':v['total']-v['passed'],'UNKNOWN':0,'N/A':0}} for k,v in regressions.items()},
        'historical':h['metrics'],'fixed20':f['metrics'],'protected_existing_files':protected['protected_existing_files'],
        'real_historical_reliable_indirect_write_coverage':0.0,'LLM_calls':0,'Harness_calls':0,'Z3_calls':0,'SMT_generated':0,'tokens':0,'API_cost_CNY':0,
        'historical_or_model_generated_code_executions':0,'C_program_executions':0,'filtering_actions':0,
        'real_bug_retention_rate':'NOT_MEASURED','false_deletion_rate':'NOT_MEASURED','false_positive_filter_rate':'NOT_MEASURED','accepted':accepted}
    save(ROOT/'metrics.json',metrics)
    rows=[('合成源码场景',s['scenario_status_counts'])]+list(s['relation_metrics'].items())+[
        ('调用上下文隔离',a['context_isolation_counts']),('显式逃逸/未知效果事件',a['escape_event_status_counts']),
        ('所有已进入分析的未知调用均阻断',a['unknown_attempt_block_counts']),('历史4样本',h['metrics']['status_counts']),('固定20样本',f['metrics']['status_counts'])]
    table='\n'.join(f"| {name} | {v['PASS']} | {v['REJECT']} | {v['UNKNOWN']} | {v['N/A']} |" for name,v in rows)
    rates={k: {'PASS_over_all_requests':v['PASS']/sum(v.values()) if sum(v.values()) else None,
               'PASS_over_applicable':v['PASS']/(sum(v.values())-v['N/A']) if sum(v.values())>v['N/A'] else None} for k,v in s['relation_metrics'].items()}
    save(ROOT/'rate_denominators.json',{'rates':rates,'UNKNOWN_is_not_success':True,'records_do_not_share_one_denominator':True})
    report=f'''# E06-R04 受限指针间接写入与副作用传播报告

日期：2026-11-02（Asia/Shanghai）。最终状态：**{'离线验收通过，满足用户限定发布条件' if accepted else '验收失败，禁止提交和推送'}**。

## 基线与研究性质

起始 main/远端 `6b81c59da00c4cf91989a2320a9aa92818a3b791`，发布工作区干净。论文保持 arXiv:2506.10322v1、官方冻结 `4efb4b9bf7e845e180451b43ba29a25e3edaa0e3`，未升级 PATHAGENT。本轮是项目独立补全及新增确定性安全证据层，不是作者公开的完整实现，不宣称严格复现论文全部结果。

## 实现和接口边界

实现 CallerPre → AddressEvidence → ArgumentTransfer → CalleePointerEntry → IndirectWrite → CallerPost。R01 原本对 &x 参数映射 UNKNOWN；R04 只读复用其中已验证的直接 callee、同 TU 唯一定义和声明事实，独立增加取址映射，保留原 R01 UNKNOWN 输出。R02 提供局部值版本和路径环境，R03 的 create_context/ReturnTrace 提供上下文隔离及正常返回记录，均未修改。

支持直接 &自动局部标量、恰好一个单级指针形参、完整唯一 void callee、直线体、最多一次 *原形参=定型简单 literal；支持 p=0 仅局部重绑和写后 p=0。写前重绑后解引用不复用入口目标。callee 不调用其他函数，不支持分支/循环、指针副本、一般别名/多级指针/成员/数组/union/全局/共享/volatile/atomic、宏、复杂转换、重分配或生命周期分析。NULL 的宏拼写未被自动补全，合成中用 C 字面0验证空指针转换。

caller 复用受限单个 if 并分别保存两条语法路径，callee 保持直线。最多16调用上下文，超预算 UNKNOWN。没有 phi、路径可满足性证明或 R05 组合；没有函数摘要缓存和跨调用点状态复用。

MemoryObject 按 caller 声明/slot/body SHA 标识；PointerTarget 按 callee 实例指针入口版本标识，两者不合并。每个对象的 memory-current 按 caller 路径独立维护；旧 MemoryVersion 和 R02 ValueVersion 全部保留。完整效果未覆盖时先前局部写入可以 PASS，但**不提交 caller 新版本**，当前值和内存绑定均失效，路径停止。对象离开词法作用域后移除其当前内存绑定，历史账本仍保留；未实现一般生命周期推断。

R02 记录中的通用 call_effects_verified 等字段继续保留原层含义；R04 的独立 effect_coverage、对象/内存版本与证据链给出新增证明，不宣称 R02 原接口已升级。原 B/Δ、SMT/Prompt、安全门槛均原样。

## 测试和计数

最终 **68个源码场景、257/257检查符合预期**；源码整体 PASS19、REJECT0、UNKNOWN48、N/A1。10个明确错误候选均 REJECT，涵盖把 p slot 当对象、错误局部对象、合并地址/上下文、否认已验证前缀写入、错误类型/值/指针版本/旧内存版本/caller新版本。未知程序语义仍 UNKNOWN，REJECT 针对错误关系候选，不裁决程序缺陷。

原回归按顺序完成：R01 **41/41**、R02 **110/110**、R03 **201/201**、R03 边界 **15/15**。这些是期望符合数，不能与传播 PASS 数混用。仅使用 final_candidate_01；开发运行不累加。68场景包括清单67项及两个 caller 的1项场景，共69次分析纳入关系统计；重复解析、不同 dataset/position 检查不累加。资源边界场景包含16次已验证调用和第17次阻断，因此调用数量与源码场景数量不同。

对保存证据另做 {sum(a['check_status_counts'].values())} 项图与版本检查，均 PASS；核对69个隔离上下文及69个指针入口版本，未重新解析源码或重跑固定20。

| 指标 | PASS | REJECT | UNKNOWN | N/A |
| --- | ---: | ---: | ---: | ---: |
{table}

地址证据、入口映射、入口唯一目标、caller新版本以**79个实际进入 caller 解释器的调用请求**为分母，未建立后续证据的请求保留 UNKNOWN。地址71/79；入口69/79；caller新版本39/79（适用项39/76）。parse/build/前缀阻断而未到调用点的程序仍保留在68场景总分母中，不靠关系子集取代整体 UNKNOWN。

局部间接写以51条识别的写入记录为单位（44 PASS、7 UNKNOWN）；其中5条局部 PASS 没有完整调用效果，未产生 caller 新版本。完整调用、逃逸覆盖和上下文内阻断以69个建立的调用上下文为单位（完整调用42/69）。初始 memory snapshot 不计写入。15条显式逃逸/未覆盖效果事件全部 UNKNOWN，含全局保存、返回、转传、局部副本、指针运算等，未当成功传播。37个未知调用请求的值与内存环境阻断均有事件证据；其程序结论 UNKNOWN，此防护检查 PASS 不等于调用传播 PASS。各分母及适用率见 rate_denominators.json。

## 四个历史风险：全部 UNKNOWN

A04：保存 clone/saved_clone 复制、strsep(&clone) 的源码及原 object/object_ptr/object_bv、B/Δ 诊断哈希。&clone 是指针对象地址，超出单级标量目标支持范围；真实类型/定义/效果仍未验证，不创建唯一目标或内存新版本。

E04-ND：保存 &maxfraglen、skb_prev=skb、后续 skb 重绑定及成员替换风险。取址文本不是唯一目标或完整副作用证据，不将旧 skb 状态绑定到新 skb，不声称已处理重分配。A01 原极性冲突诊断保持；R04 不重新裁决。OpenSSL 保持 R03 的未接收返回值、提前 return、嵌套返回及未知成员地址效果边界；R03 原记录只保存不可变哈希引用，不拼成本轮结果，也未晋升 PASS。

本轮新历史检查4/4完成、7份保存函数体均 UNKNOWN。75个 & 源码候选仅为文本定位，**不是75条地址绑定或写入成功**。没有补 TU、头文件、宏或类型，没有用同名外部函数替代缺失定义。

## 冻结与原固定20单次执行

候选 `{manifest['candidate']}` 冻结于 `{manifest['frozen_at']}`，manifest SHA-256 `{r01.digest((ROOT/'candidate_manifest.json').read_bytes())}`。冻结 {len(manifest['frozen_files_sha256'])} 份原文件/新源码/配置/输入/证据；Python、libclang DLL及绑定文件独立哈希核验。既有libclang 18.1.1/DLL与R01原哈希一致，未安装或升级依赖。

原固定20在冻结后仅运行一次，**{f['metrics']['completed_samples']}/20完整完成，异常{f['metrics']['runtime_errors']}**：PASS {f['metrics']['status_counts']['PASS']}、REJECT {f['metrics']['status_counts']['REJECT']}、UNKNOWN {f['metrics']['status_counts']['UNKNOWN']}、N/A {f['metrics']['status_counts']['N/A']}。共{f['metrics']['frame_count']}份保存函数体、{f['metrics']['edge_count']}条保存相邻边，均未批准地址/指针目标/写入/caller后版本。按原顺序保留全部样本，未重抽、删UNKNOWN、拼接其他阶段结果或修改输入。这是已接触回归集，**不是盲测**。单次本机离线耗时约{f['metrics']['elapsed_seconds']:.3f}秒。

固定输入SHA-256 `c4ef793abe5f00437f52c27b6fe545dfa613ed661eb441362e1315f1ed98243d`；审计10输入SHA-256 `6980a64dd1d499188ccc83002bfdf3255196f1c17e462eaab44d83db67aa366b`。真实历史可靠间接写入传播覆盖率仍为 **0%**，UNKNOWN不计成功。真实缺陷保留率、误删率及误报过滤率均未测，没有真实告警过滤。

## 保护、失败记录和停止点

{protected['protected_existing_files']:,}份原有非凭据文件及预算账本保持字节不变，目录外新增0；E01–E05、R01/RF、R02、R03、Engine、Prompt、U02/U06/U10、MCP、安全v1和原始数据均未修改。模型/Harness/Z3调用、新SMT、Token、费用、历史/模型生成脚本执行、C程序执行均为 **0**。实际执行了本轮确定性Python分析和测试；audit防护无外部操作记录，不冒称OS沙箱。

冻结前development_01出现Cursor与None比较异常，完整失败记录保留；仅修复R04独立层。development_02/03及最终候选如实留存，后续收紧作用域当前内存绑定和完整请求分母，增加资源边界检查，不累加开发测试。此外，冻结脚本在manifest生成前发现同名protection导入冲突，误载R03保护器并将R04新目录视为越界；失败记录保存在pre_freeze_runner_failure.json。仅重命名本轮保护器并修正导入，语义实现和既有模块未变，固定20尚未开始。没有冻结后修补候选或重跑固定20。详见development_notes.md。

验收判据逐项见acceptance_check.json。全部条件通过后，仅复制R04新目录到发布克隆、核对字节及暂存范围后提交推送main；发布身份由Git提交提供，不事后改写自引用SHA。**本轮到此停止，未进入R05。** 所有局部PASS均不授予FILTER权限。
'''
    with (ROOT/'E06_R04_report.md').open('x',encoding='utf-8',newline='\n') as out:out.write(report)
    hashes={p.relative_to(ROOT).as_posix():r01.digest(p.read_bytes()) for p in ROOT.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name not in {'hashes.json','delivery_verification.json'}}
    save(ROOT/'hashes.json',{'files_sha256':dict(sorted(hashes.items())),'excludes':['hashes.json','delivery_verification.json']})
    print(json.dumps({'acceptance':acceptance['status'],'protected':protected['protected_existing_files'],'fixed20':f['metrics']['status_counts'],
        'failed_checks':[k for k,v in checks.items() if not v]}))
    if not accepted:raise SystemExit(1)


if __name__=='__main__':main()
