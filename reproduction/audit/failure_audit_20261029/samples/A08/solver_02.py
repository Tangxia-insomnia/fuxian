def check_constraints():
    from z3 import Int, Solver, sat
    dst = Int('dst')
    s = Solver()
    s.add(dst == 0)
    return s.check() == sat