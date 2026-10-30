; benchmark generated from python API
(set-info :status unknown)
(declare-fun che () Int)
(declare-fun TYPE_DSE () Int)
(declare-fun elem_type () Int)
(declare-fun TYPE_END () Int)
(assert
 (= che 0))
(assert
 (let (($x28 (= elem_type TYPE_END)))
(or $x28 (>= elem_type TYPE_DSE) (and (distinct che 0) true))))
(check-sat)
