from time import perf_counter
from ortools.sat.python import cp_model


def solve_abp_cp_sat(edges, V, workers=1):
    total_start = perf_counter()
    start = perf_counter()
    print(f"ABP PHASE encoding {start}", flush=True)
    edges = list(edges)

    # Encoding
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
    class IncumbentCallback(cp_model.CpSolverSolutionCallback):
        def on_solution_callback(self):
            value = self.value(k)
            assignment = [self.value(x) for x in labels]
            valid = (sorted(assignment) == list(range(1, V + 1))
                     and all(abs(assignment[u - 1] - assignment[v - 1]) >= value for u, v in edges))
            print(f"ABP SAT k={value} valid={valid}", flush=True)
            if not valid:
                raise ValueError("Solver returned an invalid labeling")

    # Solving
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = workers
    solver.parameters.log_search_progress = False
    encoding_time = perf_counter() - start
    start = perf_counter()
    print(f"ABP ENCODING_TIME {encoding_time}\nABP VARIABLES {variables}\nABP PHASE solving {start}", flush=True)
    callback = IncumbentCallback()
    solve_status = solver.solve(model, solution_callback=callback)
    solving_time = perf_counter() - start
    print(f"ABP SOLVING_TIME {solving_time}\nABP PHASE decoding {perf_counter()}", flush=True)

    max_k = None
    assignment = None
    if solve_status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        max_k = solver.value(k)
        assignment = [solver.value(x) for x in labels]

    status_names = {
        cp_model.OPTIMAL: "Optimal",
        cp_model.FEASIBLE: "Feasible",
        cp_model.UNKNOWN: "Unknown",
        cp_model.INFEASIBLE: "Infeasible",
        cp_model.MODEL_INVALID: "ModelInvalid",
    }
    status = status_names[solve_status]

    if assignment is not None:
        valid = (sorted(assignment) == list(range(1, V + 1))
                 and all(abs(assignment[u - 1] - assignment[v - 1]) >= max_k for u, v in edges))
        print(f"ABP SAT k={max_k} valid={valid}", flush=True)
        if not valid:
            raise ValueError("Solver returned an invalid labeling")
    print(f"ABP PHASE done {perf_counter()}", flush=True)
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
