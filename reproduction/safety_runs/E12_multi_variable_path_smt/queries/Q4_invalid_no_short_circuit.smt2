(set-logic QF_UF)
(set-option :timeout 30000)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun e12_test_str_ne_s2_is_null () Bool)
(declare-fun e12_test_str_ne_s1_is_null () Bool)
(assert
 (let (($x7 (xor e12_test_str_ne_s1_is_null e12_test_str_ne_s2_is_null)))
(let (($x8 (not $x7)))
(and $x8 e12_test_str_ne_s2_is_null))))
(check-sat)
