from time import perf_counter

from pysat.solvers import Solver


def varmap(u, i, V):
    return u * (V - 1) + i


def _add_window_clause(solver, u, v, left, right, V):

    clause = []

    if left > 1:
        clause.append(varmap(u, left - 1, V))
        clause.append(varmap(v, left - 1, V))

    if right < V:
        clause.append(-varmap(u, right, V))
        clause.append(-varmap(v, right, V))

    solver.add_clause(clause)


def _add_assignment_constraints(solver, V):

    clauses = 0

    for u in range(V):
        for i in range(1, V - 1):
            solver.add_clause([-varmap(u, i, V), varmap(u, i + 1, V)])
            clauses += 1

    for u in range(V):
        for v in range(u + 1, V):
            for i in range(1, V + 1):
                _add_window_clause(solver, u, v, i, i, V)
                clauses += 1

    return clauses

def _add_distance_constraints(solver, edges, V, k):
    clauses = 0

    for u, v in edges:
        u, v = u - 1, v - 1

        for left in range(1, V - k + 2):
            right = left + k - 1
            _add_window_clause(solver, u, v, left, right, V)
            clauses += 1

    return clauses


def find_max_k(edges, V):
    total_start = perf_counter()
    edges = list(edges)
    if V < 1:
        raise ValueError("Số đỉnh V phải >= 1.")
    for u, v in edges:
        if not (1 <= u <= V and 1 <= v <= V) or u == v:
            raise ValueError("Cạnh phải nối hai đỉnh khác nhau trong khoảng 1..V.")

    max_k = 0
    final_model = []
    encoding_time = 0.0
    solving_time = 0.0
    clauses = 0

    with Solver(name="g3") as solver:
        start = perf_counter()
        clauses += _add_assignment_constraints(solver, V)
        encoding_time += perf_counter() - start

        for k in range(1, V):
            if k > 1:
                start = perf_counter()
                clauses += _add_distance_constraints(solver, edges, V, k)
                encoding_time += perf_counter() - start

            start = perf_counter()
            is_sat = solver.solve()
            solving_time += perf_counter() - start

            if not is_sat:
                break

            max_k = k
            final_model = solver.get_model()

        variables = max(0, solver.nof_vars())

    positive = {literal for literal in final_model if literal > 0}
    labels = []
    for u in range(V):
        label = V
        for i in range(1, V):
            if varmap(u, i, V) in positive:
                label = i
                break
        labels.append(label)

    return {
        "max_k": max_k,
        "labels": labels,
        "variables": variables,
        "clauses": clauses,
        "encoding_time": encoding_time,
        "solving_time": solving_time,
        "total_time": perf_counter() - total_start,
    }
