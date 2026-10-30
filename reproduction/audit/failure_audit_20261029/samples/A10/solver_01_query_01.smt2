; benchmark generated from python API
(set-info :status unknown)
(declare-fun sta () Int)
(declare-fun ap_sta () Int)
(assert
 (= sta 0))
(assert
 (not (or (= sta 0) (= ap_sta 0))))
(check-sat)
