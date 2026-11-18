from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "src"))

from graph_io import load_graph
from pairwise_encoding import find_max_k


def main():
    V, edges = load_graph(root / "data" / "hb" / "curtis54.mtx.rnd")
    result = find_max_k(edges, V, time_limit=5)

    print("Status:", result["status"])
    print("Antibandwidth:", result["max_k"])
    print("Variables:", result["variables"])
    print(f"Encoding: {result['encoding_time']:.4f} s")
    print(f"Solving: {result['solving_time']:.4f} s")
    print(f"Total: {result['total_time']:.4f} s")
    print("Labels:", result["labels"])


if __name__ == "__main__":
    main()