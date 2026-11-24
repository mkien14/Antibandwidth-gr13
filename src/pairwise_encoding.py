from time import perf_counter

from pysat.card import CardEnc, EncType
from pysat.solvers import Solver


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


def find_max_k(edges, V):
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
            labels = [next(i + 1 for i in range(V) if varmap(u, i, V) in positive) for u in range(V)]
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
