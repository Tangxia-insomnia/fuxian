def check_constraints():
    from z3 import Int, Solver, Or, Not, sat

    idev = Int('idev')
    cfg_fc_ifindex = Int('cfg_fc_ifindex')
    cfg_fc_flags = Int('cfg_fc_flags')
    dev = Int('dev')
    addr_type = Int('addr_type')
    net_loopback_dev = Int('net_loopback_dev')
    fib6_is_reject = Int('fib6_is_reject')

    s = Solver()

    # Base script constraint
    s.add(idev == 0)

    # Constraint set 2 - Constraint 1
    # fib6_is_reject modeled as Int (0 = false, 1 = true)
    s.add(Or(
        fib6_is_reject == 0,
        dev == net_loopback_dev,
        idev != 0
    ))

    # Constraint set 2 - Constraint 2
    s.add(Or(
        cfg_fc_ifindex == 0,
        idev != 0
    ))

    return s.check() == sat