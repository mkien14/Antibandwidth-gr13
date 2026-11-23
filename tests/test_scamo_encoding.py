import itertools
import io
from contextlib import redirect_stdout
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pysat.solvers import Solver

from sat_common import _add_assignment_constraints, varmap
from scamo_encoding import (
    _add_distance_constraints, _decode_model, _upper_bound, find_max_k,
)


def brute_force(edges, V):
    best = 0
    for labels in itertools.permutations(range(1, V + 1)):
        value = min(abs(labels[u - 1] - labels[v - 1]) for u, v in edges)
        best = max(best, value)
    return best


class ScamoEncodingTests(unittest.TestCase):
    def test_optimum_matches_brute_force_for_small_graphs(self):
        for V in range(2, 6):
            possible_edges = list(itertools.combinations(range(1, V + 1), 2))
            for mask in range(1, 1 << len(possible_edges)):
                edges = [
                    edge
                    for i, edge in enumerate(possible_edges)
                    if mask & (1 << i)
                ]

                with self.subTest(V=V, edges=edges), redirect_stdout(io.StringIO()):
                    result = find_max_k(edges, V)
                    optimum = brute_force(edges, V)
                    self.assertEqual(result["max_k"], optimum)
                    self.assertGreaterEqual(_upper_bound(edges, V), optimum)
                    self.assertEqual(result["status"], "optimal")
                    self.assertEqual(
                        sorted(result["labels"]), list(range(1, V + 1))
                    )

                    actual = min(
                        abs(result["labels"][u - 1] - result["labels"][v - 1])
                        for u, v in edges
                    )
                    self.assertEqual(actual, result["max_k"])

    def test_distance_encoding_matches_each_threshold(self):
        # A fresh encoding must be correct even without earlier thresholds.
        V = 9
        for width in range(1, V + 1):
            with self.subTest(width=width):
                with Solver(name="g3") as solver:
                    _add_assignment_constraints(solver, V)
                    _add_distance_constraints(
                        solver,
                        [(1, 2)],
                        V,
                        width,
                        next_var=V * V + 1,
                    )

                    for a, b in itertools.product(range(1, V + 1), repeat=2):
                        is_sat = solver.solve(
                            assumptions=[varmap(0, a - 1, V), varmap(1, b - 1, V)]
                        )
                        expected = abs(a - b) >= width
                        self.assertEqual(is_sat, expected, (width, a, b))

    def test_incremental_thresholds_match_label_distance(self):
        # Cover full/partial blocks and windows intersecting three blocks.
        for V in (2, 5, 8, 9, 16, 17):
            with Solver(name="g3") as solver:
                _add_assignment_constraints(solver, V)
                cache = {}
                next_var = V * V + 1
                for k in range(1, V + 1):
                    next_var, _ = _add_distance_constraints(
                        solver, [(1, 2)], V, k, next_var, cache
                    )
                    for a, b in itertools.product(range(1, V + 1), repeat=2):
                        is_sat = solver.solve(assumptions=[
                            varmap(0, a - 1, V), varmap(1, b - 1, V)
                        ])
                        self.assertEqual(is_sat, abs(a - b) >= k, (V, k, a, b))

    def test_counters_are_reused_between_block_changes(self):
        V = 17
        cache = {}
        next_var = V * V + 1
        with Solver(name="g3") as solver:
            _add_assignment_constraints(solver, V)
            for k in range(2, V + 1):
                previous_var = next_var
                next_var, _ = _add_distance_constraints(
                    solver, [(1, 2)], V, k, next_var, cache
                )
                if k in (2, 4, 8, 16):
                    self.assertGreater(next_var, previous_var)
                else:
                    self.assertEqual(next_var, previous_var, k)
                self.assertEqual(
                    _add_distance_constraints(solver, [(1, 2)], V, k, next_var, cache),
                    (next_var, 0),
                )
            with self.assertRaises(ValueError):
                _add_distance_constraints(solver, [(1, 2)], V, 2, next_var, cache)

    def test_template_mapping_with_isolated_vertex_zero(self):
        V = 17
        cache = {}
        next_var = V * V + 1
        with Solver(name="g3") as solver:
            _add_assignment_constraints(solver, V)
            for k in (2, 3, 7, 8, 13, 16, 17):
                next_var, _ = _add_distance_constraints(
                    solver, [(3, V)], V, k, next_var, cache
                )
                for a, b in itertools.product(range(1, V + 1), repeat=2):
                    is_sat = solver.solve(assumptions=[
                        varmap(2, a - 1, V), varmap(V - 1, b - 1, V)
                    ])
                    self.assertEqual(is_sat, abs(a - b) >= k, (k, a, b))

    def test_every_permutation_after_skipping_thresholds(self):
        # Fix all labels so an incorrect constraint cannot be hidden by a
        # different placement of a third vertex. Include isolated vertices.
        V = 6
        cases = [
            [(1, 2), (2, 3), (3, 4)],
            [(2, 4), (4, 6), (2, 6)],
            [(1, 6), (2, 5), (3, 4)],
        ]
        for edges in cases:
            with self.subTest(edges=edges), Solver(name="g3") as solver:
                _add_assignment_constraints(solver, V)
                cache, next_var = {}, V * V + 1
                for k in (2, 3, 5, 6):
                    next_var, _ = _add_distance_constraints(
                        solver, edges, V, k, next_var, cache
                    )
                    for labels in itertools.permutations(range(1, V + 1)):
                        expected = all(abs(labels[u - 1] - labels[v - 1]) >= k
                                       for u, v in edges)
                        actual = solver.solve(assumptions=[
                            varmap(u, label - 1, V) for u, label in enumerate(labels)
                        ])
                        self.assertEqual(actual, expected, (edges, k, labels))

    def test_register_ids_survive_block_changes(self):
        V, edges = 17, [(2, 17)]
        with Solver(name="g3") as solver:
            _add_assignment_constraints(solver, V)
            cache, next_var = {}, V * V + 1
            saved_ids = {}
            saved_literals = {}
            for k in (2, 4, 8, 16):
                next_var, _ = _add_distance_constraints(
                    solver, edges, V, k, next_var, cache
                )
                pool = cache["pool"]
                for interval, register in saved_ids.items():
                    self.assertEqual(pool.interval_ids[interval], register)
                    self.assertEqual(pool.literal_base(register), saved_literals[interval])
                saved_ids = pool.interval_ids.copy()
                saved_literals = {interval: pool.literal_base(register)
                                  for interval, register in saved_ids.items()}
                # Only the two edge endpoints need auxiliary counters.
                self.assertEqual(pool.vertices, [1, 16])
                self.assertEqual(next_var - V * V - 1, 2 * len(pool.definitions))

    def test_cache_cannot_be_reused_for_another_graph_or_solver(self):
        V, edges = 5, [(1, 2)]
        with Solver(name="g3") as first, Solver(name="g3") as second:
            _add_assignment_constraints(first, V)
            cache = {}
            next_var, _ = _add_distance_constraints(first, edges, V, 2, V * V + 1, cache)
            with self.assertRaises(ValueError):
                _add_distance_constraints(second, edges, V, 3, next_var, cache)
            with self.assertRaises(ValueError):
                _add_distance_constraints(first, [(2, 3)], V, 3, next_var, cache)
            with self.assertRaises(ValueError):
                _add_distance_constraints(first, edges, V, 3, next_var + 1, cache)

    def test_search_keeps_one_solver_and_can_prove_a_degree_bound(self):
        V = 7
        edges = [(1, v) for v in range(2, V + 1)]
        output = io.StringIO()
        with patch("scamo_encoding.Solver", wraps=Solver) as factory, redirect_stdout(output):
            result = find_max_k(edges, V)
        self.assertEqual(factory.call_count, 1)
        self.assertEqual(result["max_k"], 1)
        self.assertEqual(result["status"], "optimal")
        self.assertIn("ABP UPPER_BOUND 1", output.getvalue())
        self.assertNotIn("ABP UNSAT", output.getvalue())

    def test_decoder_ignores_auxiliaries_and_model_order(self):
        self.assertEqual(_decode_model([20, -2, 4, -3, 1, -10], 2), [1, 2])

    def test_duplicate_reversed_edges_and_empty_graph_conventions(self):
        with redirect_stdout(io.StringIO()):
            result = find_max_k([(1, 2), (2, 1), (1, 2)], 4)
            single = find_max_k([], 1)
            empty = find_max_k([], 5)
        self.assertEqual(result["max_k"], 3)
        self.assertEqual(single["max_k"], 0)
        self.assertEqual(single["labels"], [1])
        self.assertEqual(empty["max_k"], 4)
        self.assertEqual(sorted(empty["labels"]), [1, 2, 3, 4, 5])

    def test_optimum_on_larger_small_graphs(self):
        V = 6
        cases = [
            [(u, u + 1) for u in range(1, V)],
            [(u, u + 1) for u in range(1, V)] + [(V, 1)],
            [(1, u) for u in range(2, V + 1)],
            [(1, 2)],
            list(itertools.combinations(range(1, V + 1), 2)),
        ]
        for edges in cases:
            with self.subTest(edges=edges), redirect_stdout(io.StringIO()):
                result = find_max_k(edges, V)
                self.assertEqual(result["max_k"], brute_force(edges, V))

    def test_log_reports_feasible_labeling(self):
        output = io.StringIO()
        with redirect_stdout(output):
            result = find_max_k([(1, 2)], 2)
        self.assertIn("ABP SAT k=1", output.getvalue())
        self.assertEqual(sorted(result["labels"]), [1, 2])


if __name__ == "__main__":
    unittest.main()
