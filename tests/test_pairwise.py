import argparse
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "src"))

from graph_io import load_graph
from pairwise_encoding import find_max_k


def main():
    parser = argparse.ArgumentParser(description="Solve an ABP instance with Pairwise SAT.")
    parser.add_argument(
        "instance",
        nargs="?",
        default="curtis54.mtx.rnd",
        help="Input file under data/hb (default: curtis54.mtx.rnd).",
    )
    parser.add_argument(
        "--time-limit",
        type=float,
        default=5,
        help="Cumulative SAT solving time limit in seconds (default: 5).",
    )
    args = parser.parse_args()

    path = root / "data" / "hb" / args.instance
    V, edges = load_graph(path)
    result = find_max_k(edges, V, time_limit=args.time_limit)

    print("Instance:", args.instance)
    print("Status:", result["status"])
    print("Antibandwidth:", result["max_k"])
    print("Variables:", result["variables"])
    print("Clauses:", result["clauses"])
    print(f"Encoding: {result['encoding_time']:.4f} s")
    print(f"Solving: {result['solving_time']:.4f} s")
    print(f"Total: {result['total_time']:.4f} s")
    print("Labels:", result["labels"])


if __name__ == "__main__":
    main()
