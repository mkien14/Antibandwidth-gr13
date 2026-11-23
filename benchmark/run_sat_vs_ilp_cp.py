"""Run with python benchmark/run_sat_vs_ilp_cp.py; rerun to resume from CSV."""
import csv
import math
import multiprocessing as mp
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
import sys
from time import perf_counter, sleep

import psutil

# SETTINGS: change these values before running.
# INSTANCES = ["ibm32.mtx.rnd", "pores_1.mtx.rnd"]
METHODS = ["pairwise", "order", "scamo", "cplex_cp", "cplex_mip", "gurobi", "cp_sat"]
TIME_LIMIT = 300           # Seconds for startup + encoding + solving.
MEMORY_LIMIT_MB = 4096      # 4 GiB for the method process and its children.
RUNS = 1

ROOT = Path(__file__).resolve().parents[1]
INSTANCES = sorted(path.name for path in (ROOT / "data" / "hb").glob("*.rnd"))
# Keep the same settings when resuming. Use a new OUTPUT for different limits/solvers.
OUTPUT = ROOT / "benchmark" / "sat_vs_ilp_cp.csv"
FIELDS = ["instance", "method", "run", "best_k", "time_s", "memory_mb", "status"]


def worker(method, graph_path, log_path):
    """Run one method. All printed messages go to its log file."""
    sys.path.insert(0, str(ROOT / "src"))
    with open(log_path, "w", encoding="utf-8") as log:
        with redirect_stdout(log), redirect_stderr(log):
            try:
                from graph_io import load_graph
                n, edges = load_graph(graph_path)
                # Import only the selected solver, so a missing package does not
                # prevent the other methods from running.
                if method == "pairwise":
                    from pairwise_encoding import find_max_k
                    result = find_max_k(edges, n)
                elif method == "order":
                    from order_encoding import find_max_k
                    result = find_max_k(edges, n)
                elif method == "scamo":
                    from scamo_encoding import find_max_k
                    result = find_max_k(edges, n)
                elif method == "cplex_cp":
                    from cplexCP_encoding import solve_abp_cplex_cp
                    result = solve_abp_cplex_cp(edges, n, workers=1)
                elif method == "cplex_mip":
                    from cplexMIP_encoding import solve_abp_cplex_mip
                    result = solve_abp_cplex_mip(edges, n, workers=1)
                elif method == "gurobi":
                    from gurobi_encoding import solve_abp_gurobi
                    result = solve_abp_gurobi(edges, n, workers=1)
                elif method == "cp_sat":
                    from cpSAT_encoding import solve_abp_cp_sat
                    result = solve_abp_cp_sat(edges, n, workers=1)
                else:
                    raise ValueError(f"Unknown method: {method}")

                status = result["status"]
                if status.lower() == "optimal":
                    status = "Optimal"
                k, labels = result.get("max_k"), result.get("labels")
                if k is not None and labels is not None:
                    valid = (sorted(labels) == list(range(1, n + 1))
                             and all(abs(labels[u-1] - labels[v-1]) >= k for u, v in edges))
                    if not valid:
                        raise ValueError("Invalid labeling returned by solver")
                    if status == "Optimal" and min(abs(labels[u-1] - labels[v-1]) for u, v in edges) != k:
                        raise ValueError("Optimal objective differs from labeling value")
                    print(f"ABP SAT k={k} valid=True", flush=True)
                elif status == "Optimal":
                    raise ValueError("Solver claimed optimality without a labeling")
                print(f"ABP STATUS {status}", flush=True)
            except Exception as exc:
                message = str(exc)
                memory_error = isinstance(exc, MemoryError) or any(
                    word in message.lower() for word in ("out of memory", "allocator limit", "bad_alloc"))
                print(f"ABP ERROR {type(exc).__name__}: {message}", flush=True)
                print("ABP STATUS " + ("MemoryLimit" if memory_error else "Error"), flush=True)


def read_log(path):
    """Keep the highest checked k; ignore an incomplete final line."""
    best_k, status, error = None, None, ""
    if not Path(path).exists():
        return best_k, status, "Worker produced no log"
    with open(path, encoding="utf-8", errors="replace") as log:
        for line in log:
            if not line.endswith("\n"):
                continue
            if line.startswith("ABP SAT "):
                try:
                    fields = dict(item.split("=", 1) for item in line.split()[2:])
                    k = int(fields["k"])
                    if k < 1:
                        continue
                    if fields["valid"] == "True":
                        best_k = max(best_k or 0, k)
                    elif fields["valid"] == "False":
                        error = "Solver logged an invalid labeling"
                except (ValueError, KeyError):
                    continue
            elif line.startswith("ABP STATUS "):
                status = line[len("ABP STATUS "):].strip()
            elif line.startswith("ABP ERROR "):
                error = line[len("ABP ERROR "):].strip()
    return best_k, status, error


def stop_processes(process, children):
    """Stop the method and any native solver processes it started."""
    try:
        children += psutil.Process(process.pid).children(recursive=True)
    except psutil.NoSuchProcess:
        pass
    # Stop descendants first, while their parent is still identifiable.
    for child in reversed(children):
        try:
            child.kill()
        except psutil.NoSuchProcess:
            pass
    if process.is_alive():
        process.kill()
    process.join()
    psutil.wait_procs(children, timeout=1)


def run_one(path, method, log_path):
    """Supervise one run; solver implementations have no internal timeout."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("", encoding="utf-8")  # Discard any log from an old run.
    process = mp.get_context("spawn").Process(target=worker, args=(method, path, log_path))
    started = perf_counter()
    process.start()
    status, peak_memory, children = None, 0, []
    known_children = {}
    try:
        while True:
            try:
                root = psutil.Process(process.pid)
                current_children = root.children(recursive=True)
                memory = root.memory_info().rss
                for child in current_children:
                    try:
                        known_children[child.pid] = child
                        memory += child.memory_info().rss
                    except psutil.NoSuchProcess:
                        pass
                children = list(known_children.values())
                peak_memory = max(peak_memory, memory / 1024**2)
            except psutil.NoSuchProcess:
                pass
            if peak_memory > MEMORY_LIMIT_MB:
                status = "MemoryLimit"
                break
            if perf_counter() - started >= TIME_LIMIT:
                status = "Timeout"
                break
            if not process.is_alive():
                break
            sleep(0.05)
    finally:
        stop_processes(process, children)
        elapsed = perf_counter() - started
        exitcode = process.exitcode
        process.close()
    best_k, logged_status, error = read_log(log_path)
    # Killing a native solver can itself produce an exception in its Python
    # wrapper. Preserve the resource limit already detected by the supervisor.
    if status is None:
        status = logged_status or "Error"
        if error and status != "MemoryLimit":
            status = "Error"
    if status == "Error":
        print("  " + (error or f"Worker exited unexpectedly ({exitcode}); see {log_path}"))
    return dict(best_k=best_k, status=status, time_s=elapsed, memory_mb=peak_memory)


def read_completed_runs(path):
    """Read completed (instance, method, run) keys without changing old results."""
    completed = set()
    if not path.exists():
        return completed, False
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None:
            return completed, False  # Empty file, possibly with only a UTF-8 BOM.
        if reader.fieldnames != FIELDS:
            raise ValueError(f"Unexpected CSV columns in {path}; select another OUTPUT")
        for row in reader:
            # A malformed row must not silently make us skip an unfinished run.
            if (None in row or any(value is None for value in row.values())
                    or not row["instance"] or not row["method"] or not row["status"]):
                raise ValueError(f"Incomplete result at CSV line {reader.line_num} in {path}")
            try:
                run = int(row["run"])
            except ValueError:
                raise ValueError(f"Invalid run number at CSV line {reader.line_num} in {path}") from None
            if run < 1:
                raise ValueError(f"Invalid run number at CSV line {reader.line_num} in {path}")
            # Timeout, MemoryLimit and Error are also finished benchmark attempts.
            completed.add((row["instance"], row["method"], run))
    return completed, True


def main():
    if not INSTANCES or not METHODS or not isinstance(RUNS, int) or RUNS < 1:
        raise ValueError("Select at least one instance, method and run")
    if not math.isfinite(TIME_LIMIT) or TIME_LIMIT <= 0 or not math.isfinite(MEMORY_LIMIT_MB) or MEMORY_LIMIT_MB <= 0:
        raise ValueError("Time and memory limits must be positive")
    paths = [ROOT / "data" / "hb" / name for name in INSTANCES]
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(path)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    completed, has_header = read_completed_runs(OUTPUT)
    print(f"Limits: {TIME_LIMIT}s, {MEMORY_LIMIT_MB} MiB | Existing results: {len(completed)}", flush=True)
    # A manually edited CSV may have no newline after its last complete row.
    needs_newline = False
    if has_header:
        with OUTPUT.open("rb") as existing:
            existing.seek(-1, 2)
            needs_newline = existing.read(1) not in (b"\n", b"\r")
    # Append new results and flush every row so completed runs survive Ctrl+C.
    with OUTPUT.open("a", newline="", encoding="utf-8-sig") as stream:
        if needs_newline:
            stream.write("\n")
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        if not has_header:
            writer.writeheader()
        stream.flush()
        try:
            for path in paths:
                for run in range(1, RUNS + 1):
                    for method in METHODS:
                        key = (path.name, method, run)
                        if key in completed:
                            print(f"Skip: {path.name} | {method} | run {run} (already in CSV)", flush=True)
                            continue
                        print(f"{path.name} | {method} | run {run}/{RUNS}", flush=True)
                        log_path = OUTPUT.parent / "logs" / OUTPUT.stem / f"{path.name}.{method}.run{run}.log"
                        started = perf_counter()
                        try:
                            result = run_one(path, method, log_path)
                        except Exception as exc:
                            # One failed method must not cancel the remaining comparisons.
                            print(f"  Error: {exc}", flush=True)
                            result = dict(best_k=None, status="Error",
                                          time_s=perf_counter()-started, memory_mb=None)
                        writer.writerow(dict(instance=path.name, method=method, run=run, **result))
                        stream.flush()
                        completed.add(key)
                        print(f"  {result['status']} | k={result['best_k']} | {result['time_s']:.3f}s", flush=True)
        except KeyboardInterrupt:
            print(f"\nStopped. Completed results are saved in {OUTPUT}.", flush=True)
            print("Run the same command to resume; an unfinished run starts again from the beginning.", flush=True)
            return
    print(f"Saved: {OUTPUT}")


if __name__ == "__main__":
    main()
