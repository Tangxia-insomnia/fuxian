; benchmark generated from python API
(set-info :status unknown)
(declare-fun copied () Int)
(declare-fun skb () Int)
(assert
 (let (($x8 (= copied 0)))
 (not $x8)))
(assert
 (= skb 0))
(assert
 (= copied 0))
(check-sat)
