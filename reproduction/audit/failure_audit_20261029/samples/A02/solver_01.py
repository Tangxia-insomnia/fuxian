def check_constraints():
    from z3 import Int, Solver, sat
    skb = Int('skb')
    s = Solver()
    s.add(skb == 0)
    s.add(skb != 0)
    return s.check() == sat