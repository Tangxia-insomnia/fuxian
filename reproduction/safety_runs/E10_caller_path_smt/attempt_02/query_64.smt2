; benchmark generated from python API
(set-info :status unknown)
(declare-fun e10_input_symbol_rate_u32 () (_ BitVec 32))
(declare-fun e10_assigned_params_srate_u32 () (_ BitVec 32))
(declare-fun e10_guard_params_srate_u32 () (_ BitVec 32))
(declare-fun e10_target_params_srate_u32 () (_ BitVec 32))
(declare-fun e10_target_srate_signed_long_64 () (_ BitVec 64))
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
 (= e10_target_srate_signed_long_64 ((_ zero_extend 32) e10_target_params_srate_u32)))
(assert
 e10_SYS_DVBS_or_SYS_DSS_branch)
(assert
 (bvslt (_ bv0 64) e10_target_srate_signed_long_64))
(assert
 (and (and (distinct (_ bv1000 64) (_ bv0 64)) true) (not (and (= (_ bv9223372036854775808 64) e10_target_srate_signed_long_64) (= (_ bv1000 64) (_ bv18446744073709551615 64))))))
(assert
 (let ((?x74 (bvsdiv e10_target_srate_signed_long_64 (_ bv1000 64))))
(= (_ bv0 64) ?x74)))
(check-sat)
