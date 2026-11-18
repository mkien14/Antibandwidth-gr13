from time import perf_counter
import gurobipy as gp
from gurobipy import GRB


def solve_abp_gurobi(edges, V, time_limit=10):
    total_start = perf_counter()
    edges = list(edges)
    edge_set = {tuple(sorted((u - 1, v - 1))) for u, v in edges}

    # Encoding: same linear formulation as CPLEX MIP.
    start = perf_counter()
    with gp.Env(empty=True) as env:
        env.setParam("OutputFlag", 0)
        env.start()
        with gp.Model("ABP", env=env) as model:
            labels = model.addVars(V, lb=1, ub=V, vtype=GRB.INTEGER, name="x")
            k = model.addVar(lb=0, ub=V - 1, vtype=GRB.INTEGER, name="k")
            M = 2 * (V - 1)

            for u in range(V):
                for v in range(u + 1, V):
                    order = model.addVar(vtype=GRB.BINARY, name=f"b_{u}_{v}")
                    gap = k if (u, v) in edge_set else 1
                    model.addConstr(labels[u] - labels[v] >= gap - M * (1 - order))
                    model.addConstr(labels[v] - labels[u] >= gap - M * order)

            model.setObjective(k, GRB.MAXIMIZE)
            model.Params.TimeLimit = time_limit
            model.Params.MIPGap = 0
            model.Params.MIPGapAbs = 0
            model.update()
            variables = model.NumVars
            constraints = model.NumConstrs
            encoding_time = perf_counter() - start

            # Solving
            start = perf_counter()
            model.optimize()
            solving_time = perf_counter() - start

            max_k = None
            assignment = None
            if model.SolCount > 0:
                max_k = round(k.X)
                assignment = [round(labels[i].X) for i in range(V)]

            status_names = {
                GRB.OPTIMAL: "Optimal",
                GRB.TIME_LIMIT: "Timeout",
                GRB.INFEASIBLE: "Infeasible",
                GRB.INF_OR_UNBD: "InfeasibleOrUnbounded",
                GRB.UNBOUNDED: "Unbounded",
                GRB.INTERRUPTED: "Interrupted",
                GRB.MEM_LIMIT: "MemoryLimit",
            }
            status = status_names.get(model.Status, f"Status_{model.Status}")

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