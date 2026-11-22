from time import perf_counter
from pysat.solvers import Solver
from sat_common import _add_assignment_constraints, varmap


def _add_clause(solver, clause):
    solver.add_clause(clause)
    return 1


def _build_counter(solver, variables, next_var, at_most_one):
    registers = [variables[0]]
    clauses = 0

    for i in range(1, len(variables)):
        current = next_var
        next_var += 1
        previous = registers[-1]
        value = variables[i]

        clauses += _add_clause(solver, [-value, current])
        clauses += _add_clause(solver, [-previous, current])
        clauses += _add_clause(solver, [value, previous, -current])

        if at_most_one:
            clauses += _add_clause(solver, [-value, -previous])

        registers.append(current)

    return registers, next_var, clauses


def _build_scamo_blocks(solver, variables, width, next_var):
    blocks = [variables[i:i + width] for i in range(0, len(variables), width)]
    registers = []
    clauses = 0

    for block_index, block in enumerate(blocks):
        is_only_block = len(blocks) == 1
        is_first = block_index == 0
        is_last = block_index == len(blocks) - 1

        amo_order = list(reversed(block)) if is_first and not is_only_block else list(block)
        amo_registers, next_var, added = _build_counter(
            solver, amo_order, next_var, at_most_one=True
        )
        clauses += added

        block_info = {"whole": amo_registers[-1], "prefix": {}, "suffix": {}}
        if is_first and not is_only_block:
            for size, register in enumerate(amo_registers, start=1):
                block_info["suffix"][size] = register
        else:
            for size, register in enumerate(amo_registers, start=1):
                block_info["prefix"][size] = register

        if not is_first and not is_last:
            reverse_registers = [block[-1]]
            for i in range(1, len(block)):
                if i == len(block) - 1:
                    register = block_info["whole"]
                else:
                    register = next_var
                    next_var += 1

                previous = reverse_registers[-1]
                value = block[-1 - i]
                clauses += _add_clause(solver, [-value, register])
                clauses += _add_clause(solver, [-previous, register])
                clauses += _add_clause(solver, [value, previous, -register])
                reverse_registers.append(register)

            for size, register in enumerate(reverse_registers, start=1):
                block_info["suffix"][size] = register

        registers.append(block_info)

    for i in range(len(blocks) - 1):
        right_size = min(width - 1, len(blocks[i + 1]))
        for right_part_size in range(1, right_size + 1):
            left_part_size = width - right_part_size
            left_register = registers[i]["suffix"][left_part_size]
            right_register = registers[i + 1]["prefix"][right_part_size]
            clauses += _add_clause(solver, [-left_register, -right_register])

    return registers, next_var, clauses


def _window_registers(registers, start, width):
    block_index, offset = divmod(start, width)

    if offset == 0:
        return [registers[block_index]["whole"]]

    suffix_size = width - offset
    prefix_size = offset
    return [
        registers[block_index]["suffix"][suffix_size],
        registers[block_index + 1]["prefix"][prefix_size],
    ]


def _add_distance_constraints(solver, edges, V, width, next_var):
    clauses = 0
    vertex_registers = []

    for u in range(V):
        variables = [varmap(u, i, V) for i in range(V)]
        registers, next_var, added = _build_scamo_blocks(
            solver, variables, width, next_var
        )
        vertex_registers.append(registers)
        clauses += added

    for u, v in edges:
        u, v = u - 1, v - 1
        for left in range(V - width + 1):
            u_window = _window_registers(vertex_registers[u], left, width)
            v_window = _window_registers(vertex_registers[v], left, width)

            # The AMZ condition for a window split across two blocks is a
            # conjunction of zero-register literals. Distribute the OR
            # between the two endpoint AMZ conditions into CNF clauses.
            for u_register in u_window:
                for v_register in v_window:
                    clauses += _add_clause(
                        solver, [-u_register, -v_register]
                    )

    return next_var, clauses


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
    next_var = V * V + 1
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
                next_var, added = _add_distance_constraints(solver, edges, V, k, next_var)
                clauses += added
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
