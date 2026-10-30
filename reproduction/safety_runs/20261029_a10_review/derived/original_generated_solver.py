def check_constraints():
    from z3 import Int, Solver, Not, Or, sat

    # Base script variables and constraints
    sta = Int('sta')

    # Constraint set 2 variables (ap_sta referenced in the constraint)
    ap_sta = Int('ap_sta')

    s = Solver()

    # Base script constraint
    s.add(sta == 0)

    # Constraint set 2: !(WARN_ON_ONCE(!sta || !ap_sta))
    #   <=> (sta != 0) && (ap_sta != 0)
    s.add(Not(Or(sta == 0, ap_sta == 0)))

    return s.check() == sat