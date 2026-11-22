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
    """Print intermediate results; benchmark controls total time and memory."""
    total_start = perf_counter()
    edges = list(edges)
    if V < 1 or any(not (1 <= u <= V and 1 <= v <= V) or u == v for u, v in edges):
        raise ValueError("Invalid graph")
    max_k = 0
    labels = [1] if V == 1 else None
    encoding_time = 0.0
    solving_time = 0.0
    clauses = 0
    start = perf_counter()
    print(f"ABP PHASE encoding {start}", flush=True)
    with Solver(name="g3") as solver:
        clauses += _add_assignment_constraints(solver, V)
        encoding_time += perf_counter() - start
        print(f"ABP ENCODING_TIME {encoding_time}", flush=True)
        for k in range(1, V):
            start = perf_counter()
            print(f"ABP PHASE encoding {start}", flush=True)
            if k > 1:
                clauses += _add_distance_constraints(solver, edges, V, k)
            encoding_time += perf_counter() - start
            variables = max(0, solver.nof_vars())
            start = perf_counter()
            print(f"ABP ENCODING_TIME {encoding_time}\nABP VARIABLES {variables}\nABP PHASE solving {start}", flush=True)
            is_sat = solver.solve()
            solving_time += perf_counter() - start
            print(f"ABP SOLVING_TIME {solving_time}\nABP PHASE decoding {perf_counter()}", flush=True)
            if not is_sat:
                print(f"ABP UNSAT k={k}", flush=True)
                break
            positive = {lit for lit in solver.get_model() if lit > 0}
            labels = [next((i for i in range(1, V) if varmap(u, i, V) in positive), V) for u in range(V)]
            max_k = k
            valid = (sorted(labels) == list(range(1, V + 1))
                     and all(abs(labels[u - 1] - labels[v - 1]) >= k for u, v in edges))
            print(f"ABP SAT k={k} valid={valid}", flush=True)
            if not valid:
                raise ValueError("Solver returned an invalid labeling")
        variables = max(0, solver.nof_vars())
    print(f"ABP PHASE done {perf_counter()}", flush=True)
    return {
        "max_k": max_k,
        "labels": labels,
        "variables": variables,
        "clauses": clauses,
        "encoding_time": encoding_time,
        "solving_time": solving_time,
        "total_time": perf_counter() - total_start,
        "status": "optimal",
    }
