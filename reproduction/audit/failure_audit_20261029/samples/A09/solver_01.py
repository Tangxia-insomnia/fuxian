def check_constraints():
    from z3 import Int, Solver, Function, IntSort, BoolSort, Or, Not

    idev = Int('idev')
    cfg_fc_ifindex = Int('cfg_fc_ifindex')
    cfg_fc_flags = Int('cfg_fc_flags')
    dev = Int('dev')
    addr_type = Int('addr_type')
    net_loopback_dev = Int('net_loopback_dev')
    fib6_is_reject = Function('fib6_is_reject', IntSort(), IntSort(), IntSort(), BoolSort())

    s = Solver()

    # Base script constraint
    s.add(idev == 0)

    # Constraint set 2 - Constraint 1
    s.add(Or(
        Not(fib6_is_reject(cfg_fc_flags, dev, addr_type)),
        dev == net_loopback_dev,
        idev != 0
    ))

    # Constraint set 2 - Constraint 2
    s.add(Or(
        cfg_fc_ifindex == 0,
        idev != 0
    ))

    return s.check() == __import__('z3').sat