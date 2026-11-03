(set-logic QF_BV)
(set-option :timeout 30000)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun e11_row2_out_min_v0_u64 () (_ BitVec 64))
(declare-fun e11_row2_out_min_v1_u64 () (_ BitVec 64))
(declare-fun e11_row2_out_min_use189_u64 () (_ BitVec 64))
(assert
 (let ((?x18 (ite (= (_ bv0 64) e11_row2_out_min_v0_u64) (_ bv1 64) e11_row2_out_min_v0_u64)))
 (= e11_row2_out_min_v1_u64 ?x18)))
(assert
 (= e11_row2_out_min_use189_u64 e11_row2_out_min_v1_u64))
(assert
 (= (_ bv18446744073709551615 64) e11_row2_out_min_v0_u64))
(check-sat)
