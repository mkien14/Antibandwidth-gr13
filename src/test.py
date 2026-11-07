from pathlib import Path

from graph_io import load_graph
from anti_bandwith import find_max_k

path = Path(__file__).resolve().parents[1] / "data" / "hb" / "ibm32.mtx.rnd"
V, edges = load_graph(path)
result = find_max_k(edges, V)

print("Antibandwidth:", result["max_k"])
print("Variables:", result["variables"])
print("Clauses:", result["clauses"])
print(f"Encoding: {result['encoding_time']:.4f} s")
print(f"Solving: {result['solving_time']:.4f} s")
print(f"Total: {result['total_time']:.4f} s")
print("Labels:", result["labels"])