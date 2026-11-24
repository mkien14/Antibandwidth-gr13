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

    def test_interrupt_stops_worker_and_closes_process(self):
        stopped = []
        original_stop = runner.stop_processes

        def record_stop(process, children):
            stopped.append((process.pid, process))
            original_stop(process, children)

        with tempfile.TemporaryDirectory() as folder, patch.object(runner, "worker", dummy_worker), \
             patch.object(runner, "sleep", side_effect=KeyboardInterrupt), \
             patch.object(runner, "stop_processes", side_effect=record_stop):
            with self.assertRaises(KeyboardInterrupt):
                runner.run_one(Path(folder) / "unused", "sleep", Path(folder) / "run.log")
        self.assertEqual(len(stopped), 1)
        pid, process = stopped[0]
        self.assertFalse(runner.psutil.pid_exists(pid))
        with self.assertRaises(ValueError):
            process.is_alive()  # The multiprocessing handle was closed as well.


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


class ResumeTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        data = self.root / "data" / "hb"
        data.mkdir(parents=True)
        for name in ("first.rnd", "second.rnd"):
            (data / name).touch()  # run_one is mocked, so no graph is loaded.
        self.output = self.root / "results.csv"
        self.response = dict(best_k=9, status="Optimal", time_s=1, memory_mb=32)
        self.enterContext(patch.object(runner, "ROOT", self.root))
        self.enterContext(patch.object(runner, "OUTPUT", self.output))
        self.enterContext(patch.object(runner, "INSTANCES", ["first.rnd"]))
        self.enterContext(patch.object(runner, "METHODS", ["pairwise", "order"]))
        self.enterContext(patch.object(runner, "RUNS", 1))
        self.run = self.enterContext(patch.object(runner, "run_one", return_value=self.response))
        self.console = io.StringIO()
        self.enterContext(redirect_stdout(self.console))

    def write_results(self, rows):
        with self.output.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=runner.FIELDS)
            writer.writeheader()
            writer.writerows(rows)

    def read_results(self):
        with self.output.open(encoding="utf-8-sig", newline="") as stream:
            return list(csv.DictReader(stream))

    def test_rerun_preserves_results_without_duplicates(self):
        runner.main()
        first_contents = self.output.read_bytes()
        runner.main()
        self.assertEqual(self.run.call_count, 2)
        self.assertEqual(self.output.read_bytes(), first_contents)
        self.assertEqual(len(self.read_results()), 2)
        self.assertIn("Skip:", self.console.getvalue())
        self.assertFalse(list(self.root.glob("*.json")))

    def test_resume_uses_instance_method_and_run_and_preserves_old_log(self):
        old_row = dict(instance="first.rnd", method="pairwise", run=1,
                       best_k=7, status="Optimal", time_s=0.5, memory_mb=16)
        self.write_results([old_row])
        old_log = self.root / "logs" / "results" / "first.rnd.pairwise.run1.log"
        old_log.parent.mkdir(parents=True)
        old_log.write_text("original log", encoding="utf-8")
        with patch.object(runner, "INSTANCES", ["first.rnd", "second.rnd"]), \
             patch.object(runner, "RUNS", 2):
            runner.main()
        rows = self.read_results()
        self.assertEqual(self.run.call_count, 7)
        self.assertEqual(len(rows), 8)
        keys = {(row["instance"], row["method"], row["run"]) for row in rows}
        self.assertEqual(len(keys), 8)
        self.assertEqual(rows[0]["best_k"], "7")
        self.assertEqual(rows[0]["time_s"], "0.5")
        self.assertEqual(old_log.read_text(encoding="utf-8"), "original log")

    def test_timeout_memory_limit_and_error_are_completed_attempts(self):
        methods = ["pairwise", "order", "scamo", "gurobi"]
        statuses = ["Optimal", "Timeout", "MemoryLimit", "Error"]
        rows = [dict(instance="first.rnd", method=method, run=1, best_k=None,
                     status=status, time_s=10, memory_mb=None)
                for method, status in zip(methods, statuses)]
        rows[0]["best_k"] = 9
        self.write_results(rows)
        original = self.output.read_bytes()
        with patch.object(runner, "METHODS", methods):
            runner.main()
        self.run.assert_not_called()
        self.assertEqual(self.output.read_bytes(), original)

    def test_interrupt_keeps_finished_rows_and_retries_unfinished_run(self):
        self.run.side_effect = [self.response, KeyboardInterrupt, self.response]
        runner.main()
        rows = self.read_results()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["method"], "pairwise")
        self.assertIn("Stopped.", self.console.getvalue())
        runner.main()
        runner.main()
        self.assertEqual([call.args[1] for call in self.run.call_args_list],
                         ["pairwise", "order", "order"])
        self.assertEqual(len(self.read_results()), 2)

    def test_empty_files_and_header_only_files_get_one_header(self):
        for contents in (b"", b"\xef\xbb\xbf", (",".join(runner.FIELDS) + "\r\n").encode()):
            with self.subTest(contents=contents):
                self.output.write_bytes(contents)
                self.run.reset_mock()
                runner.main()
                runner.main()
                self.assertEqual(self.run.call_count, 2)
                self.assertEqual(len(self.read_results()), 2)
                raw = self.output.read_bytes()
                self.assertEqual(raw.count(b"instance,method,run,"), 1)
                self.assertLessEqual(raw.count(b"\xef\xbb\xbf"), 1)

    def test_complete_last_row_without_newline_is_preserved(self):
        self.write_results([dict(instance="first.rnd", method="pairwise", run=1, **self.response)])
        self.output.write_bytes(self.output.read_bytes().rstrip(b"\r\n"))
        runner.main()
        self.assertEqual(self.run.call_count, 1)
        self.assertEqual([row["method"] for row in self.read_results()], ["pairwise", "order"])

    def test_invalid_csv_is_not_overwritten_or_appended(self):
        bad_contents = [
            "old results\n",
            ",".join(runner.FIELDS) + "\nfirst.rnd,pairwise,1,9,1,32,\n",
            ",".join(runner.FIELDS) + "\nfirst.rnd,pairwise,1,9",
        ]
        for contents in bad_contents:
            with self.subTest(contents=contents):
                self.output.write_text(contents, encoding="utf-8")
                original = self.output.read_bytes()
                with self.assertRaises(ValueError):
                    runner.main()
                self.assertEqual(self.output.read_bytes(), original)
        self.run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
