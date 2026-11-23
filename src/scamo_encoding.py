from time import perf_counter

from pysat.solvers import Solver

from sat_common import _add_assignment_constraints


class _CounterPool:
    """Share SCL prefix/suffix registers by their exact label interval.

    A register for [left, right) is the OR of the assignment variables in
    that interval. Its definition is emitted once for each non-isolated
    vertex, even when several block sizes use the same interval.
    """

    def __init__(self, V, edges, next_var):
        self.V = V
        self.vertices = sorted({u - 1 for edge in edges for u in edge})
        self.vertex_offsets = {u: i for i, u in enumerate(self.vertices)}
        self.base = next_var
        # IDs 0..V-1 denote the original one-hot assignment variables.
        self.intervals = [(i, i + 1) for i in range(V)]
        self.interval_ids = {}
        self.definitions = []
        self.encoded = 0

    @property
    def next_var(self):
        return self.base + len(self.definitions) * len(self.vertices)

    def join(self, previous, value):
        left = min(self.intervals[previous][0], self.intervals[value][0])
        right = max(self.intervals[previous][1], self.intervals[value][1])
        interval = (left, right)
        if interval not in self.interval_ids:
            self.interval_ids[interval] = len(self.intervals)
            self.intervals.append(interval)
            self.definitions.append((previous, value))
        return self.interval_ids[interval]

    def literal_base(self, register):
        """Return the base variable ID and whether it is an auxiliary ID.

        Assignment IDs are translated by vertex * V. Auxiliary IDs are
        translated by the vertex's position in self.vertices. This avoids
        storing a separate dictionary of all registers for every vertex.
        """
        if register < self.V:
            return register + 1, False
        return self.base + (register - self.V) * len(self.vertices), True

    def add_definitions(self, solver):
        if self.encoded == len(self.definitions):
            return 0
        recipes = []
        for index in range(self.encoded, len(self.definitions)):
            previous, value = self.definitions[index]
            previous_base, previous_aux = self.literal_base(previous)
            value_base, value_aux = self.literal_base(value)
            current_base, _ = self.literal_base(self.V + index)
            recipes.append((current_base, previous_base, previous_aux,
                            value_base, value_aux))

        for vertex_offset, u in enumerate(self.vertices):
            assignment_offset = u * self.V
            clauses = []
            for current_base, previous_base, previous_aux, value_base, value_aux in recipes:
                current = current_base + vertex_offset
                previous = previous_base + (vertex_offset if previous_aux else assignment_offset)
                value = value_base + (vertex_offset if value_aux else assignment_offset)
                # current <-> (previous OR value).
                clauses.append([-previous, current])
                clauses.append([-value, current])
                clauses.append([previous, value, -current])
            solver.append_formula(clauses)

        self.encoded = len(self.definitions)
        return 3 * len(recipes) * len(self.vertices)


def _build_counter(pool, variables):
    registers = [variables[0]]
    for value in variables[1:]:
        registers.append(pool.join(registers[-1], value))
    return registers


def _build_scamo_blocks(pool, width):
    """Build SCL blocks using persistent prefix/suffix counter definitions.

    The shared assignment constraints already enforce AMO over every
    vertex's labels, so internal and adjacent-block AMO clauses are redundant.
    Only the counters needed for the edge windows are constructed here.
    """
    blocks = [list(range(i, min(i + width, pool.V)))
              for i in range(0, pool.V, width)]
    registers = []
    for index, block in enumerate(blocks):
        is_first = index == 0
        is_last = index == len(blocks) - 1
        order = list(reversed(block)) if is_first and not is_last else block
        counter = _build_counter(pool, order)
        info = {"whole": counter[-1], "prefix": {}, "suffix": {}}
        direction = "suffix" if is_first and not is_last else "prefix"
        info[direction] = dict(enumerate(counter, start=1))
        if not is_first and not is_last:
            reverse_counter = _build_counter(pool, list(reversed(block)))
            info["suffix"] = dict(enumerate(reverse_counter, start=1))
        registers.append(info)
    return registers


def _window_registers(registers, start, width, block_width):
    """Cover a window by at most three whole/prefix/suffix block registers."""
    first_block, offset = divmod(start, block_width)
    last_block = (start + width - 1) // block_width
    if first_block == last_block:
        return [registers[first_block]["whole"]]

    if offset == 0:
        window = [registers[first_block]["whole"]]
    else:
        window = [registers[first_block]["suffix"][block_width - offset]]
    for block_index in range(first_block + 1, last_block):
        window.append(registers[block_index]["whole"])
    prefix_size = start + width - last_block * block_width
    window.append(registers[last_block]["prefix"][prefix_size])
    return window


def _new_window_pairs(pool, registers, width, block_width, last_k):
    pairs = set()
    for start in range(pool.V - width + 1):
        window = _window_registers(registers, start, width, block_width)
        if width == last_k + 1:
            # Only the first and last pieces can contain labels at the
            # newly forbidden distance k-1. All other pairs were covered.
            pairs.add((window[0], window[-1]))
            pairs.add((window[-1], window[0]))
            continue
        for left in window:
            a, b = pool.intervals[left]
            for right in window:
                c, d = pool.intervals[right]
                largest_distance = max(b - 1 - c, d - 1 - a)
                # If every label pair was forbidden at the previous k,
                # the old edge constraints already imply this clause.
                # This also works when the requested k skips thresholds.
                if largest_distance >= last_k:
                    pairs.add((left, right))
    # Deterministic clause order helps make repeated benchmark runs comparable.
    return sorted(pairs)


def _add_distance_constraints(solver, edges, V, width, next_var, counter_cache=None):
    """Strengthen one solver monotonically; never remove old constraints.

    A cache belongs to one graph and one solver. The interval register pool
    survives every block change, including k=4, 8, 16, ... .
    """
    if not 1 <= width <= V:
        raise ValueError("The threshold must be between 1 and V")
    edges = tuple(edges)
    if counter_cache is None:
        counter_cache = {}
    if "pool" not in counter_cache:
        counter_cache.update(pool=_CounterPool(V, edges, next_var),
                             solver=solver, edges=edges, last_k=1)
    pool = counter_cache["pool"]
    if counter_cache["solver"] is not solver or pool.V != V or counter_cache["edges"] != edges:
        raise ValueError("A counter cache must belong to the same solver and graph")
    if next_var != pool.next_var:
        raise ValueError("next_var does not match the counter cache")
    last_k = counter_cache["last_k"]
    if width < last_k:
        raise ValueError("Incremental thresholds must not decrease")
    if width == last_k:
        return next_var, 0
    if not edges:
        counter_cache["last_k"] = width
        return next_var, 0

    block_width = 1 << (width.bit_length() - 1)
    if counter_cache.get("block_width") != block_width:
        counter_cache["blocks"] = _build_scamo_blocks(pool, block_width)
        counter_cache["block_width"] = block_width
    pairs = _new_window_pairs(pool, counter_cache["blocks"], width, block_width, last_k)
    clauses = pool.add_definitions(solver)

    pair_bases = []
    for left, right in pairs:
        left_base, left_aux = pool.literal_base(left)
        right_base, right_aux = pool.literal_base(right)
        pair_bases.append((left_base, left_aux, right_base, right_aux))
    for u, v in edges:
        u_assignment, v_assignment = (u - 1) * V, (v - 1) * V
        u_aux, v_aux = pool.vertex_offsets[u - 1], pool.vertex_offsets[v - 1]
        solver.append_formula([
            [-(left + (u_aux if left_aux else u_assignment)),
             -(right + (v_aux if right_aux else v_assignment))]
            for left, left_aux, right, right_aux in pair_bases
        ])
    clauses += len(pairs) * len(edges)
    counter_cache["last_k"] = width
    return pool.next_var, clauses


def _upper_bound(edges, V):
    """Match sorted graph degrees to possible label degrees at threshold k.

    A label i has at most max(0, i-k) + max(0, V-i-k+1) possible neighbors.
    If sorted degrees do not fit these sorted capacities, k is impossible.
    """
    degrees = [0] * V
    for u, v in edges:
        degrees[u - 1] += 1
        degrees[v - 1] += 1
    degrees.sort(reverse=True)
    lower, upper = 1, V - 1
    while lower < upper:
        k = (lower + upper + 1) // 2
        capacities = sorted(
            (max(0, i - k) + max(0, V - i - k + 1) for i in range(1, V + 1)),
            reverse=True,
        )
        if all(degree <= capacity for degree, capacity in zip(degrees, capacities)):
            lower = k
        else:
            upper = k - 1
    return upper


def _decode_model(model, V):
    labels = [0] * V
    assignment_variables = V * V
    for literal in model:
        if 0 < literal <= assignment_variables:
            u, i = divmod(literal - 1, V)
            labels[u] = i + 1
    return labels


def find_max_k(edges, V):
    """Print intermediate results; benchmark controls total time and memory."""
    total_start = perf_counter()
    edges = list(edges)
    if V < 1 or any(not (1 <= u <= V and 1 <= v <= V) or u == v for u, v in edges):
        raise ValueError("Invalid graph")
    edges = sorted({(min(u, v), max(u, v)) for u, v in edges})
    max_k = 0
    labels = None
    encoding_time = 0.0
    solving_time = 0.0
    clauses = 0
    next_var = V * V + 1
    counter_cache = {}
    start = perf_counter()
    print(f"ABP PHASE encoding {start}", flush=True)
    upper_bound = _upper_bound(edges, V)
    print(f"ABP UPPER_BOUND {upper_bound}", flush=True)
    with Solver(name="g3") as solver:
        clauses += _add_assignment_constraints(solver, V)
        encoding_time += perf_counter() - start
        print(f"ABP ENCODING_TIME {encoding_time}", flush=True)
        k = 1
        # V=1 uses the convention max_k=0; its only labeling is [1].
        if V == 1:
            labels = [1]
        while k <= upper_bound:
            start = perf_counter()
            print(f"ABP PHASE encoding {start}", flush=True)
            if k > 1:
                next_var, added = _add_distance_constraints(
                    solver, edges, V, k, next_var, counter_cache
                )
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
            labels = _decode_model(solver.get_model(), V)
            actual_k = min((abs(labels[u - 1] - labels[v - 1]) for u, v in edges),
                           default=V - 1)
            valid = sorted(labels) == list(range(1, V + 1)) and actual_k >= k
            print(f"ABP SAT k={actual_k} valid={valid}", flush=True)
            if not valid:
                raise ValueError("Solver returned an invalid labeling")
            max_k = actual_k
            # The decoded model already proves every threshold <= actual_k.
            # The cache still records the encoded k, not this incidental value.
            k = actual_k + 1
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
