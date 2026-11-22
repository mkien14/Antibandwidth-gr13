
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
