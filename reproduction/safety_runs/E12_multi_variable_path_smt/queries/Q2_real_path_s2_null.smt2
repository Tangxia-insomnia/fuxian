(set-logic QF_UF)
(set-option :timeout 30000)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun e12_test_str_ne_s2_is_null () Bool)
(declare-fun e12_test_str_ne_s1_is_null () Bool)
(assert
 (let (($x9 (not e12_test_str_ne_s1_is_null)))
(let (($x7 (xor e12_test_str_ne_s1_is_null e12_test_str_ne_s2_is_null)))
(let (($x8 (not $x7)))
(let (($x10 (and $x8 $x9)))
(and $x10 e12_test_str_ne_s2_is_null))))))
(check-sat)
