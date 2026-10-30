def check_constraints():
    from z3 import Solver, Int, BitVec, sat

    # Base script variables and constraints
    folio_test_slab = Int('folio_test_slab')
    object = Int('object')

    s = Solver()
    s.add(folio_test_slab == 0)
    s.add(object == 0)

    # Constraint set 1: object_ptr is NULL (ZERO_OR_NULL_PTR true)
    object_ptr = Int('object_ptr')
    s.add(object_ptr == 0)

    # Constraint set 2: object (as BitVec 64) must be non-null
    object_bv = BitVec('object_bv', 64)
    s.add(object_bv != 0)

    result = s.check()
    return result == sat