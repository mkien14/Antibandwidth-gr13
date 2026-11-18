from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "src"))

from graph_io import load_graph

from cplexCP_encoding import solve_abp_cplex_cp

V, edges = load_graph(root / "data" / "hb" / "ibm32.mtx.rnd")
result = solve_abp_cplex_cp(edges, V)

print("Status:", result["status"])
print("Antibandwidth:", result["max_k"])
print("Variables:", result["variables"])
print(f"Encoding: {result['encoding_time']:.4f} s")
print(f"Solving: {result['solving_time']:.4f} s")
print(f"Total: {result['total_time']:.4f} s")
print("Labels:", result["labels"])
