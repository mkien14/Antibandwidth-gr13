from time import perf_counter
from ortools.sat.python import cp_model


def solve_abp_cp_sat(edges, V, time_limit=10):
    total_start = perf_counter()
    edges = list(edges)

    # Encoding
    start = perf_counter()
    model = cp_model.CpModel()
    labels = [model.new_int_var(1, V, f"x_{i}") for i in range(V)]
    k = model.new_int_var(0, V - 1, "k")
    model.add_all_different(labels)

    for index, (u, v) in enumerate(edges):
        gap = model.new_int_var(0, V - 1, f"gap_{index}")
        model.add_abs_equality(gap, labels[u - 1] - labels[v - 1])
        model.add(gap >= k)

    model.maximize(k)
    variables = V + 1 + len(edges)
    constraints = 1 + 2 * len(edges)
    encoding_time = perf_counter() - start

    # Solving
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.log_search_progress = False
    start = perf_counter()
    solve_status = solver.solve(model)
    solving_time = perf_counter() - start

    max_k = None
    assignment = None
    if solve_status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        max_k = solver.value(k)
        assignment = [solver.value(x) for x in labels]

    status_names = {
        cp_model.OPTIMAL: "Optimal",
        cp_model.FEASIBLE: "Timeout",
        cp_model.UNKNOWN: "Timeout",
        cp_model.INFEASIBLE: "Infeasible",
        cp_model.MODEL_INVALID: "ModelInvalid",
    }
    status = status_names[solve_status]

    return {
        "max_k": max_k,
        "labels": assignment,
        "variables": variables,
        "clauses": None,
        "constraints": constraints,
        "encoding_time": encoding_time,
        "solving_time": solving_time,
        "total_time": perf_counter() - total_start,
        "status": status,
    }