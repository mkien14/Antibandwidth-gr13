from time import perf_counter
from docplex.mp.model import Model
from docplex.mp.progress import SolutionListener


def solve_abp_cplex_mip(edges, V, workers=1):
    total_start = perf_counter()
    start = perf_counter()
    print(f"ABP PHASE encoding {start}", flush=True)
    edges = list(edges)
    edge_set = {tuple(sorted((u - 1, v - 1))) for u, v in edges}

    # Encoding: permutation labels and pairwise ordering.
    model = Model(name="ABP")
    labels = model.integer_var_list(V, lb=1, ub=V, name="x")
    k = model.integer_var(lb=1, ub=V - 1, name="k")
    M = 2 * (V - 1)

    for u in range(V):
        for v in range(u + 1, V):
            order = model.binary_var(name=f"b_{u}_{v}")
            gap = k if (u, v) in edge_set else 1
            model.add_constraint(labels[u] - labels[v] >= gap - M * (1 - order))
            model.add_constraint(labels[v] - labels[u] >= gap - M * order)

    model.maximize(k)
    model.parameters.threads = workers
    model.parameters.mip.tolerances.mipgap = 0
    model.parameters.mip.tolerances.absmipgap = 0
    variables = model.number_of_variables
    constraints = model.number_of_constraints
    class IncumbentListener(SolutionListener):
        best_logged_k = 0

        def notify_solution(self, solution):
            value = round(solution.get_value(k))
            if value <= self.best_logged_k:
                return
            assignment = [round(solution.get_value(x)) for x in labels]
            valid = (sorted(assignment) == list(range(1, V + 1))
                     and all(abs(assignment[u - 1] - assignment[v - 1]) >= value for u, v in edges))
            print(f"ABP SAT k={value} valid={valid}", flush=True)
            if not valid:
                raise ValueError("Solver returned an invalid labeling")
            self.best_logged_k = value

    model.add_progress_listener(IncumbentListener())
    encoding_time = perf_counter() - start
    start = perf_counter()
    print(f"ABP ENCODING_TIME {encoding_time}\nABP VARIABLES {variables}\nABP PHASE solving {start}", flush=True)

    # Solving
    solution = model.solve(log_output=False)
    solving_time = perf_counter() - start
    print(f"ABP SOLVING_TIME {solving_time}\nABP PHASE decoding {perf_counter()}", flush=True)

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

    if assignment is not None:
        valid = (sorted(assignment) == list(range(1, V + 1))
                 and all(abs(assignment[u - 1] - assignment[v - 1]) >= max_k for u, v in edges))
        print(f"ABP SAT k={max_k} valid={valid}", flush=True)
        if not valid:
            raise ValueError("Solver returned an invalid labeling")
    model.end()
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
