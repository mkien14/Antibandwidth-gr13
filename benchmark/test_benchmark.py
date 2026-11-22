"""Tests use fake workers only; no optimization solver is run."""
import csv
import io
from contextlib import redirect_stdout
from pathlib import Path
import sys
import tempfile
from time import perf_counter, sleep
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_sat_vs_ilp_cp as runner


def dummy_worker(method, path, log_path):
    with open(log_path, "w", encoding="utf-8") as log:
        log.write("ABP SAT k=2 valid=True\n")
        log.flush()
        if method == "child":
            import subprocess
            child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(20)"])
            log.write(f"CHILD {child.pid}\n")
            log.flush()
        if method == "error":
            log.write("ABP ERROR RuntimeError: genuine solver failure\nABP STATUS Error\n")
        elif method == "finish":
            log.write("ABP STATUS Optimal\n")
        else:
            sleep(20)


class BenchmarkTests(unittest.TestCase):
    def test_log_keeps_highest_checked_k(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "run.log"
            path.write_text("ABP SAT k=0 valid=False\nABP SAT k=2 valid=True\n"
                            "ABP SAT k=1 valid=True\nABP SAT k=999 valid=", encoding="utf-8")
            self.assertEqual(runner.read_log(path), (2, None, ""))

    def test_log_preserves_error_and_memory_status(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "run.log"
            path.write_text("ABP ERROR MemoryError: allocator limit\nABP STATUS MemoryLimit\n", encoding="utf-8")
            k, status, error = runner.read_log(path)
            self.assertIsNone(k)
            self.assertEqual(status, "MemoryLimit")
            self.assertIn("allocator limit", error)

    def test_timeout_keeps_incumbent(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(runner, "worker", dummy_worker), \
             patch.object(runner, "TIME_LIMIT", 1.5):
            result = runner.run_one(Path(folder) / "unused", "sleep", Path(folder) / "run.log")
            self.assertEqual(result["status"], "Timeout")
            self.assertEqual(result["best_k"], 2)
            self.assertLess(result["time_s"], 6)

    def test_memory_limit_stops_worker(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(runner, "worker", dummy_worker), \
             patch.object(runner, "MEMORY_LIMIT_MB", 0.001):
            result = runner.run_one(Path(folder) / "unused", "sleep", Path(folder) / "run.log")
            self.assertEqual(result["status"], "MemoryLimit")
            self.assertIsNone(result["best_k"])

    def test_completed_worker(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(runner, "worker", dummy_worker), \
             patch.object(runner, "TIME_LIMIT", 5):
            result = runner.run_one(Path(folder) / "unused", "finish", Path(folder) / "run.log")
            self.assertEqual(result["status"], "Optimal")
            self.assertEqual(result["best_k"], 2)

    def test_main_overwrites_and_keeps_only_simple_csv(self):
        response = dict(best_k=9, status="Optimal", time_s=1, memory_mb=32)
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "results.csv"
            output.write_text("old results", encoding="utf-8")
            with patch.object(runner, "OUTPUT", output), patch.object(runner, "METHODS", ["order"]), patch.object(runner, "INSTANCES", ["ibm32.mtx.rnd"]), patch.object(runner, "RUNS", 1), \
                 patch.object(runner, "run_one", return_value=response) as run, redirect_stdout(io.StringIO()):
                runner.main()
                runner.main()
            self.assertEqual(run.call_count, 2)
            with output.open(encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["best_k"], "9")
            self.assertFalse(list(Path(folder).glob("*.json")))


    def test_timeout_also_stops_native_child(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(runner, "worker", dummy_worker), \
             patch.object(runner, "TIME_LIMIT", 1.5):
            log = Path(folder) / "run.log"
            result = runner.run_one(Path(folder) / "unused", "child", log)
            self.assertEqual(result["status"], "Timeout")
            pid = int(next(line.split()[1] for line in log.read_text().splitlines() if line.startswith("CHILD ")))
            self.assertFalse(runner.psutil.pid_exists(pid))


    def test_cleanup_exception_does_not_override_resource_status(self):
        for limit, memory, expected in [(1.5, 2048, "Timeout"), (5, 0.001, "MemoryLimit")]:
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as folder:
                log = Path(folder) / "run.log"
                original_stop = runner.stop_processes

                def stop_with_wrapper_error(process, children):
                    original_stop(process, children)
                    with log.open("a", encoding="utf-8") as stream:
                        stream.write("ABP ERROR CpoSolverException: local solver stopped (rc=15)\nABP STATUS Error\n")

                with patch.object(runner, "worker", dummy_worker), \
                     patch.object(runner, "TIME_LIMIT", limit), \
                     patch.object(runner, "MEMORY_LIMIT_MB", memory), \
                     patch.object(runner, "stop_processes", side_effect=stop_with_wrapper_error):
                    result = runner.run_one(Path(folder) / "unused", "sleep", log)
                self.assertEqual(result["status"], expected)
                if expected == "Timeout":
                    self.assertEqual(result["best_k"], 2)

    def test_genuine_solver_error_is_still_error(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(runner, "worker", dummy_worker), \
             patch.object(runner, "TIME_LIMIT", 5), redirect_stdout(io.StringIO()):
            result = runner.run_one(Path(folder) / "unused", "error", Path(folder) / "run.log")
            self.assertEqual(result["status"], "Error")


if __name__ == "__main__":
    unittest.main()
