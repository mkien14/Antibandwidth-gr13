"""Count incremental distance clauses without allocating a SAT solver.

This audit uses every threshold 2..k. It is not a runtime benchmark and
does not reproduce model-dependent threshold jumps in find_max_k.
The counts include submitted clauses, before any SAT solver simplification.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from graph_io import load_graph
from scamo_encoding import _CounterPool, _build_scamo_blocks, _new_window_pairs


def audit(path, thresholds):
    V, edges = load_graph(path)
    edges = sorted({tuple(sorted(edge)) for edge in edges})
    if not thresholds or any(k < 2 or k > V for k in thresholds):
        raise ValueError("Thresholds must be in 2..V")
    # The benchmarked SCAMO version uses the shared pairwise permutation CNF.
    assignment_clauses = V * V * (V - 1) + 2 * V
    pool = _CounterPool(V, edges, V * V + 1)
    previous_width, clauses = 0, 0
    counts = []
    for k in range(2, max(thresholds) + 1):
        width = 1 << (k.bit_length() - 1)
        if width != previous_width:
            blocks = _build_scamo_blocks(pool, width)
            previous_width = width
        clauses += len(_new_window_pairs(pool, blocks, k, width, k - 1)) * len(edges)
        if k in thresholds:
            auxiliary = pool.next_var - pool.base
            counts.append(dict(
                k=k, scamo_auxiliary_variables=auxiliary,
                scamo_distance_clauses=clauses + 3 * auxiliary,
                pairwise_distance_clauses=2 * len(edges) * sum(V - j + 1 for j in range(2, k + 1)),
            ))
    return dict(instance=path.name, vertices=V, edges=len(edges),
                mode="consecutive_thresholds_without_solving",
                assignment_variables=V * V,
                scamo_assignment_auxiliary_variables=0,
                scamo_assignment_clauses=assignment_clauses,
                pairwise_assignment_clauses=assignment_clauses,
                counts=counts)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instance", default="494_bus.mtx.rnd")
    parser.add_argument("--thresholds", nargs="+", type=int, default=[34, 77, 163])
    args = parser.parse_args()
    print(json.dumps(audit(ROOT / "data" / "hb" / args.instance, args.thresholds), indent=2))
