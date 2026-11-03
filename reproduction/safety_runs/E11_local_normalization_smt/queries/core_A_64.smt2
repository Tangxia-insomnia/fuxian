(set-logic QF_BV)
(set-option :timeout 30000)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun e11_row2_out_min_v0_u64 () (_ BitVec 64))
(assert
 (= (_ bv0 64) e11_row2_out_min_v0_u64))
(check-sat)
