; benchmark generated from python API
(set-info :status unknown)
(declare-fun folio_test_slab () Int)
(declare-fun object () Int)
(declare-fun object_ptr () Int)
(declare-fun object_bv () (_ BitVec 64))
(assert
 (= folio_test_slab 0))
(assert
 (= object 0))
(assert
 (= object_ptr 0))
(assert
 (and (distinct object_bv (_ bv0 64)) true))
(check-sat)
