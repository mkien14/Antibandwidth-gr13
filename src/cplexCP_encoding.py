from time import perf_counter
from docplex.cp.model import CpoModel
from docplex.cp.solver.cpo_callback import CpoCallback


def solve_abp_cplex_cp(edges, V, workers=1):
    total_start = perf_counter()
    start = perf_counter()
    print(f"ABP PHASE encoding {start}", flush=True)
    edges = list(edges)

    # Encoding

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

    class IncumbentCallback(CpoCallback):
        def invoke(self, solver, event, result):
            if event == "Solution" and result.is_solution():
                value = result.get_value(k)
                assignment = [result.get_value(x) for x in labels]
                valid = (sorted(assignment) == list(range(1, V + 1))
                         and all(abs(assignment[u - 1] - assignment[v - 1]) >= value for u, v in edges))
                print(f"ABP SAT k={value} valid={valid}", flush=True)
                if not valid:
                    raise ValueError("Solver returned an invalid labeling")

    model.add_solver_callback(IncumbentCallback())
    encoding_time = perf_counter() - start
    start = perf_counter()
    print(f"ABP ENCODING_TIME {encoding_time}\nABP VARIABLES {V + 1}\nABP PHASE solving {start}", flush=True)

    # Solving

    solution = model.solve(
        Workers=workers,
        LogVerbosity="Quiet"
    )

    solving_time = perf_counter() - start
    print(f"ABP SOLVING_TIME {solving_time}\nABP PHASE decoding {perf_counter()}", flush=True)

    max_k = None
    assignment = None

    if solution.is_solution():
        max_k = solution.get_value(k)
        assignment = [
            solution.get_value(labels[i])
            for i in range(V)
        ]

    if assignment is not None:
        valid = (sorted(assignment) == list(range(1, V + 1))
                 and all(abs(assignment[u - 1] - assignment[v - 1]) >= max_k for u, v in edges))
        print(f"ABP SAT k={max_k} valid={valid}", flush=True)
        if not valid:
            raise ValueError("Solver returned an invalid labeling")
    status = solution.get_solve_status()
    variables = V + 1
    print(f"ABP PHASE done {perf_counter()}", flush=True)
    return {
        "max_k": max_k,
        "labels": assignment,
        "variables": variables,
        "clauses": None,
        "encoding_time": encoding_time,
        "solving_time": solving_time,
        "total_time": perf_counter() - total_start,
        "status": status,
    }
