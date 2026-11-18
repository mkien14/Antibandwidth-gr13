from threading import Timer

from pysat.card import CardEnc, EncType


def varmap(u, i, V):
    return u * V + i + 1


def exactly_one(variables):
    return CardEnc.equals(lits=variables, encoding=EncType.pairwise)


def _add_assignment_constraints(solver, V):
    clauses = 0

    for u in range(V):
        variables = [varmap(u, i, V) for i in range(V)]
        cnf = exactly_one(variables)
        solver.append_formula(cnf.clauses)
        clauses += len(cnf.clauses)

    for i in range(V):
        variables = [varmap(u, i, V) for u in range(V)]
        cnf = exactly_one(variables)
        solver.append_formula(cnf.clauses)
        clauses += len(cnf.clauses)

    return clauses


def solve_with_timeout(solver, timeout):
    if timeout is None:
        return solver.solve()

    if timeout <= 0:
        return None

    timer = Timer(timeout, solver.interrupt)
    timer.daemon = True
    timer.start()
    try:
        return solver.solve_limited()
    finally:
        timer.cancel()
        solver.clear_interrupt()
