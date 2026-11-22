import itertools
import io
from contextlib import redirect_stdout
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pysat.solvers import Solver

from sat_common import _add_assignment_constraints, varmap
from scamo_encoding import _add_distance_constraints, find_max_k


def brute_force(edges, V):
    best = 0
    for labels in itertools.permutations(range(1, V + 1)):
        value = min(abs(labels[u - 1] - labels[v - 1]) for u, v in edges)
        best = max(best, value)
    return best


def fixed_label_assumptions(labels, V):
    assumptions = []
    for u in range(V):
        for label in range(1, V + 1):
            literal = varmap(u, label - 1, V)
            assumptions.append(literal if labels[u] == label else -literal)
    return assumptions


class ScamoEncodingTests(unittest.TestCase):
    def test_optimum_matches_brute_force_for_small_graphs(self):
        for V in range(2, 5):
            possible_edges = list(itertools.combinations(range(1, V + 1), 2))
            for mask in range(1, 1 << len(possible_edges)):
                edges = [
                    edge
                    for i, edge in enumerate(possible_edges)
                    if mask & (1 << i)
                ]

                with self.subTest(V=V, edges=edges):
                    result = find_max_k(edges, V)
                    self.assertEqual(result["max_k"], brute_force(edges, V))
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
        V = 2
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

                    for labels in itertools.product(range(1, V + 1), repeat=V):
                        is_sat = solver.solve(
                            assumptions=fixed_label_assumptions(labels, V)
                        )
                        expected = abs(labels[0] - labels[1]) >= width
                        self.assertEqual(is_sat, expected, (width, labels))

    def test_log_reports_feasible_labeling(self):
        output = io.StringIO()
        with redirect_stdout(output):
            result = find_max_k([(1, 2)], 2)
        self.assertIn("ABP SAT k=1", output.getvalue())
        self.assertEqual(sorted(result["labels"]), [1, 2])


if __name__ == "__main__":
    unittest.main()
