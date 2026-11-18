from time import perf_counter

from pysat.solvers import Solver
from sat_common import _add_assignment_constraints, solve_with_timeout, varmap


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


def find_max_k(edges, V, timeout=None):
    """Find the optimum, limiting cumulative solver time when requested.

    Encoding time is excluded from ``timeout`` and ``solving_time``.
    """
    total_start = perf_counter()
    edges = list(edges)

    if V < 1:
        raise ValueError("Số đỉnh V phải >= 1.")
    if timeout is not None and timeout < 0:
        raise ValueError("Timeout phải >= 0 giây hoặc None.")
    for u, v in edges:
        if not (1 <= u <= V and 1 <= v <= V) or u == v:
            raise ValueError("Cạnh phải nối hai đỉnh khác nhau trong khoảng 1..V.")

    max_k = 0
    final_model = []
    encoding_time = 0.0
    solving_time = 0.0
    clauses = 0
    status = "optimal"
    next_var = V * V + 1

    with Solver(name="g3") as solver:
        start = perf_counter()
        clauses += _add_assignment_constraints(solver, V)
        encoding_time += perf_counter() - start

        for k in range(1, V):
            if k > 1:
                start = perf_counter()
                next_var, added = _add_distance_constraints(
                    solver, edges, V, k, next_var
                )
                clauses += added
                encoding_time += perf_counter() - start

            start = perf_counter()
            remaining_time = (
                None if timeout is None else timeout - solving_time
            )
            is_sat = solve_with_timeout(solver, remaining_time)
            solving_time += perf_counter() - start

            if is_sat is None:
                status = "timeout"
                break

            if not is_sat:
                break

            max_k = k
            final_model = solver.get_model()

        variables = solver.nof_vars()

    positive = {literal for literal in final_model if literal > 0}
    labels = []
    for u in range(V):
        for i in range(V):
            if varmap(u, i, V) in positive:
                labels.append(i + 1)
                break

    return {
        "max_k": max_k,
        "labels": labels,
        "variables": variables,
        "clauses": clauses,
        "encoding_time": encoding_time,
        "solving_time": solving_time,
        "total_time": perf_counter() - total_start,
        "status": status,
        "timeout": timeout,
    }
