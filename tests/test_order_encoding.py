import itertools
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pysat.solvers import Solver

from pairwise_encoding import find_max_k as find_pairwise
from order_encoding import (
    _add_assignment_constraints,
    _add_distance_constraints,
    find_max_k,
    varmap,
)


def brute_force(edges, V):
    best = 0
    for labels in itertools.permutations(range(1, V + 1)):
        value = min(abs(labels[u - 1] - labels[v - 1]) for u, v in edges)
        best = max(best, value)
    return best


def fix_labels(labels, V):
    assumptions = []
    for u, label in enumerate(labels):
        for i in range(1, V):
            literal = varmap(u, i, V)
            assumptions.append(literal if label <= i else -literal)
    return assumptions


class OrderEncodingTests(unittest.TestCase):
    def check_result(self, edges, V):
        result = find_max_k(edges, V)
        pairwise = find_pairwise(edges, V)
        expected = brute_force(edges, V)

        self.assertEqual(result["max_k"], expected)
        self.assertEqual(result["max_k"], pairwise["max_k"])
        self.assertEqual(sorted(result["labels"]), list(range(1, V + 1)))
        actual = min(
            abs(result["labels"][u - 1] - result["labels"][v - 1])
            for u, v in edges
        )
        self.assertEqual(actual, expected)
        self.assertEqual(set(result), set(pairwise))
        self.assertEqual(result["variables"], V * (V - 1))
        for name in ("encoding_time", "solving_time", "total_time"):
            self.assertGreaterEqual(result[name], 0)
        self.assertGreaterEqual(
            result["total_time"],
            result["encoding_time"] + result["solving_time"],
        )

    def test_all_nonempty_graphs_up_to_four_vertices(self):
        for V in range(2, 5):
            possible = list(itertools.combinations(range(1, V + 1), 2))
            for mask in range(1, 1 << len(possible)):
                edges = [edge for i, edge in enumerate(possible) if mask & (1 << i)]
                with self.subTest(V=V, edges=edges):
                    self.check_result(edges, V)

    def test_five_vertex_examples(self):
        examples = [
            [(1, 2), (2, 3), (3, 4), (4, 5)],
            [(1, 2), (2, 3), (3, 4), (4, 5), (5, 1)],
            [(1, 2), (1, 3), (1, 4), (1, 5)],
            list(itertools.combinations(range(1, 6), 2)),
            [(1, 2), (3, 4)],
        ]
        for edges in examples:
            with self.subTest(edges=edges):
                self.check_result(edges, 5)

    def test_assignment_accepts_exactly_the_permutations(self):
        V = 4
        with Solver(name="g3") as solver:
            _add_assignment_constraints(solver, V)
            for labels in itertools.product(range(1, V + 1), repeat=V):
                is_sat = solver.solve(assumptions=fix_labels(labels, V))
                self.assertEqual(is_sat, len(set(labels)) == V, labels)

    def test_distance_at_each_threshold_including_domain_boundaries(self):
        V = 4
        for k in range(1, V + 1):
            with Solver(name="g3") as solver:
                _add_assignment_constraints(solver, V)
                _add_distance_constraints(solver, [(1, 2)], V, k)
                for a, b in itertools.product(range(1, V + 1), repeat=2):
                    is_sat = solver.solve(assumptions=fix_labels([a, b], V))
                    self.assertEqual(is_sat, abs(a - b) >= k, (k, a, b))

    def test_single_vertex(self):
        result = find_max_k([], 1)
        self.assertEqual(result["max_k"], 0)
        self.assertEqual(result["labels"], [1])
        self.assertEqual(result["variables"], 0)

    def test_invalid_graph_is_rejected(self):
        for V, edges in [(0, []), (3, [(0, 1)]), (3, [(1, 4)]), (3, [(2, 2)])]:
            with self.subTest(V=V, edges=edges):
                with self.assertRaises(ValueError):
                    find_max_k(edges, V)


if __name__ == "__main__":
    unittest.main()
