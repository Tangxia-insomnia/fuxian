def check_constraints():
    from z3 import Int, Solver, Or, sat

    # Variables from base script
    che = Int('che')

    # Variables from constraint set 2
    elem_type = Int('elem_type')
    TYPE_END = Int('TYPE_END')
    TYPE_DSE = Int('TYPE_DSE')

    s = Solver()

    # Base script constraint
    s.add(che == 0)

    # Constraint set 2 constraint
    s.add(Or(
        elem_type == TYPE_END,
        elem_type >= TYPE_DSE,
        che != 0
    ))

    return s.check() == sat