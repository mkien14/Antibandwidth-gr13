from time import perf_counter
from docplex.cp.model import CpoModel


def solve_abp_cplex_cp(edges, V, time_limit=10):
    total_start = perf_counter()
    edges = list(edges)

    # Encoding
    start = perf_counter()

    model = CpoModel()

    labels = [
        model.integer_var(min=1, max=V, name=f"x_{i}")
        for i in range(V)
    ]

    k = model.integer_var(min=0, max=V - 1, name="k")

    model.add(model.all_diff(labels))

    for u, v in edges:
        model.add(model.abs(labels[u - 1] - labels[v - 1]) >= k)

    model.add(model.maximize(k))

    encoding_time = perf_counter() - start

    # Solving
    start = perf_counter()

    solution = model.solve(
        TimeLimit=time_limit,
        LogVerbosity="Quiet"
    )

    solving_time = perf_counter() - start

    max_k = None
    assignment = None

    if solution.is_solution():
        max_k = solution.get_value(k)
        assignment = [
            solution.get_value(labels[i])
            for i in range(V)
        ]

    # Status
    if solution.get_solve_status() == "Optimal":
        status = "Optimal"
    else:
        status = "Timeout"

    return {
        "max_k": max_k,
        "labels": assignment,
        "variables": V + 1,
        "clauses": None,
        "encoding_time": encoding_time,
        "solving_time": solving_time,
        "total_time": perf_counter() - total_start,
        "status": status,
    }