import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from graph_io import load_graph
from pairwise_encoding import find_max_k


def main():
    parser = argparse.ArgumentParser(description="Giải ABP bằng Pairwise SAT.")
    parser.add_argument(
        "instance",
        nargs="?",
        default="ibm32.mtx.rnd",
        help="Tên file dữ liệu trong data/hb (mặc định: ibm32.mtx.rnd).",
    )
    args = parser.parse_args()

    path = Path(__file__).resolve().parents[1] / "data" / "hb" / args.instance
    V, edges = load_graph(path)
    result = find_max_k(edges, V)

    print("Antibandwidth:", result["max_k"])
    print("Variables:", result["variables"])
    print("Clauses:", result["clauses"])
    print(f"Encoding: {result['encoding_time']:.4f} s")
    print(f"Solving: {result['solving_time']:.4f} s")
    print(f"Total: {result['total_time']:.4f} s")
    print("Labels:", result["labels"])


if __name__ == "__main__":
    main()
