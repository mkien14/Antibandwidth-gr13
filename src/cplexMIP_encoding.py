from time import perf_counter
from docplex.mp.model import Model


def solve_abp_cplex_mip(edges, V, time_limit=10):
    total_start = perf_counter()
    edges = list(edges)
    edge_set = {tuple(sorted((u - 1, v - 1))) for u, v in edges}

    # Encoding: permutation labels and pairwise ordering.
    start = perf_counter()
    model = Model(name="ABP")
    labels = model.integer_var_list(V, lb=1, ub=V, name="x")
    k = model.integer_var(lb=0, ub=V - 1, name="k")
    M = 2 * (V - 1)

    for u in range(V):
        for v in range(u + 1, V):
            order = model.binary_var(name=f"b_{u}_{v}")
            gap = k if (u, v) in edge_set else 1
            model.add_constraint(labels[u] - labels[v] >= gap - M * (1 - order))
            model.add_constraint(labels[v] - labels[u] >= gap - M * order)

    model.maximize(k)
    model.set_time_limit(time_limit)
    model.parameters.mip.tolerances.mipgap = 0
    model.parameters.mip.tolerances.absmipgap = 0
    variables = model.number_of_variables
    constraints = model.number_of_constraints
    encoding_time = perf_counter() - start

    # Solving
    start = perf_counter()
    solution = model.solve(log_output=False)
    solving_time = perf_counter() - start

    max_k = None
    assignment = None
    if solution is not None:
        max_k = round(solution.get_value(k))
        assignment = [round(solution.get_value(x)) for x in labels]

    # Preserve non-time-limit failures instead of calling everything Timeout.
    details = model.solve_details
    raw_status = details.status
    if details.status_code in (101, 102):
        status = "Optimal"
    elif details.status_code in (107, 108):
        status = "Timeout"
    else:
        status = raw_status

    model.end()
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