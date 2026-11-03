(set-logic QF_UF)
(set-option :timeout 30000)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun e12_test_str_ne_s2_is_null () Bool)
(declare-fun e12_test_str_ne_s1_is_null () Bool)
(assert
 (let (($x9 (not e12_test_str_ne_s1_is_null)))
(and $x9 e12_test_str_ne_s2_is_null)))
(check-sat)
