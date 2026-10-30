def check_constraints():
    from z3 import Int, Solver, sat
    tmp = Int('tmp')
    s = Solver()
    s.add(tmp == 0)
    return s.check() == sat