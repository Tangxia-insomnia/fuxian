; benchmark generated from python API
(set-info :status unknown)
(declare-fun idev () Int)
(declare-fun net_loopback_dev () Int)
(declare-fun dev () Int)
(declare-fun fib6_is_reject () Int)
(declare-fun cfg_fc_ifindex () Int)
(assert
 (= idev 0))
(assert
 (let (($x33 (and (distinct idev 0) true)))
 (let (($x32 (= dev net_loopback_dev)))
 (let (($x31 (= fib6_is_reject 0)))
 (or $x31 $x32 $x33)))))
(assert
 (let (($x33 (and (distinct idev 0) true)))
(let (($x37 (= cfg_fc_ifindex 0)))
(or $x37 $x33))))
(check-sat)
