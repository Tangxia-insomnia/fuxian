def check_constraints():
    from z3 import Int, Solver, sat
    saved_clone = Int('saved_clone')
    s = Solver()
    s.add(saved_clone == 0)
    return s.check() == sat