; benchmark generated from python API
(set-info :status unknown)
(declare-fun e10_input_symbol_rate_u32 () (_ BitVec 32))
(declare-fun e10_assigned_params_srate_u32 () (_ BitVec 32))
(declare-fun e10_guard_params_srate_u32 () (_ BitVec 32))
(declare-fun e10_target_params_srate_u32 () (_ BitVec 32))
(declare-fun e10_target_srate_signed_long_32 () (_ BitVec 32))
(declare-fun e10_SYS_DVBS_or_SYS_DSS_branch () Bool)
(assert
 (= e10_assigned_params_srate_u32 e10_input_symbol_rate_u32))
(assert
 (= e10_guard_params_srate_u32 e10_assigned_params_srate_u32))
(assert
 (and (bvuge e10_guard_params_srate_u32 (_ bv1000000 32)) (bvule e10_guard_params_srate_u32 (_ bv45000000 32))))
(assert
 (= e10_target_params_srate_u32 e10_guard_params_srate_u32))
(assert
 (= e10_target_srate_signed_long_32 e10_target_params_srate_u32))
(assert
 e10_SYS_DVBS_or_SYS_DSS_branch)
(assert
 (bvslt (_ bv0 32) e10_target_srate_signed_long_32))
(assert
 (and (and (distinct (_ bv1000 32) (_ bv0 32)) true) (not (and (= (_ bv2147483648 32) e10_target_srate_signed_long_32) (= (_ bv1000 32) (_ bv4294967295 32))))))
(assert
 (let ((?x21 (bvsdiv e10_target_srate_signed_long_32 (_ bv1000 32))))
(= (_ bv0 32) ?x21)))
(check-sat)
