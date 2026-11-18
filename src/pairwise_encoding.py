
from time import perf_counter
from math import isfinite
from threading import Timer

from pysat.card import CardEnc, EncType
from pysat.solvers import Solver


def exactly_one(arr):
    return CardEnc.equals(lits=arr, encoding=EncType.pairwise)


def varmap(u, i, V):
    return u * V + i + 1


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


def _add_distance_constraints(solver, edges, V, k):
    clauses = 0

    for u, v in edges:
        u, v = u - 1, v - 1

        for i in range(V - k + 1):
            j = i + k - 1

            solver.add_clause([
                -varmap(u, i, V),
                -varmap(v, j, V),
            ])

            solver.add_clause([
                -varmap(u, j, V),
                -varmap(v, i, V),
            ])

            clauses += 2

    return clauses


def _decode_model(model, V):
    if model is None:
        return None

    positive = {lit for lit in model if lit > 0}
    labels = []

    for u in range(V):
        for i in range(V):
            if varmap(u, i, V) in positive:
                labels.append(i + 1)
                break

    return labels


def find_max_k(edges, V, time_limit=50):
    # Budget for all SAT calls combined, in seconds (encoding excluded).
    if not isfinite(time_limit) or time_limit <= 0:
        raise ValueError("time_limit must be a positive finite number")

    total_start = perf_counter()
    edges = list(edges)
    max_k = 0
    final_model = None
    encoding_time = 0.0
    solving_time = 0.0
    clauses = 0
    status = "Optimal"

    with Solver(name="g3") as solver:
        start = perf_counter()
        clauses += _add_assignment_constraints(solver, V)
        encoding_time += perf_counter() - start

        for k in range(1, V):
            remaining = time_limit - solving_time
            if remaining <= 0:
                status = "Timeout"
                break

            if k > 1:
                start = perf_counter()
                clauses += _add_distance_constraints(solver, edges, V, k)
                encoding_time += perf_counter() - start

            timer = Timer(remaining, solver.interrupt)
            timer.daemon = True
            start = perf_counter()
            timer.start()
            try:
                is_sat = solver.solve_limited(expect_interrupt=True)
            finally:
                elapsed = perf_counter() - start
                timer.cancel()
                timer.join()  # Finish any callback before clearing/deleting solver.
                solver.clear_interrupt()
                solving_time += elapsed

            if is_sat is None:
                status = "Timeout"
                break
            if not is_sat:
                break

            max_k = k
            final_model = solver.get_model()

        variables = solver.nof_vars()

    labels = _decode_model(final_model, V)

    return {
        "max_k": max_k,
        "labels": labels,
        "variables": variables,
        "clauses": clauses,
        "encoding_time": encoding_time,
        "solving_time": solving_time,
        "total_time": perf_counter() - total_start,
        "status": status,
        "optimal": status == "Optimal",
        "timed_out": status == "Timeout",
    }