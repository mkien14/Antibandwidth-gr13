"""Check notebook drift, source selection, and truncated SAT logs offline."""
import ast
from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from sync_notebook import HERE, read_cells


class KaggleNotebookTests(unittest.TestCase):
    def setUp(self):
        self.cells = read_cells()

    def test_notebook_matches_copy_cells_and_has_no_outputs(self):
        notebook = json.loads((HERE / "abp_kaggle.ipynb").read_text(encoding="utf-8"))
        self.assertEqual(notebook["cells"], self.cells)
        for cell in notebook["cells"]:
            if cell["cell_type"] == "code":
                self.assertEqual(cell["outputs"], [])
                self.assertIsNone(cell["execution_count"])

    def source_environment(self, root):
        input_dir, work = root / "input", root / "working"
        input_dir.mkdir()
        work.mkdir()
        return dict(INPUT=input_dir, WORK=work, SETUP=work / "setup",
                    PROJECT=work / "abp_source", SOURCE_LOCATION=None,
                    EXPECTED_SCAMO_SHA256=hashlib.sha256(b"new scamo\n").hexdigest(),
                    Path=Path, BATCH_INDEX=0, BATCH_SIZE=6, RUNS=1,
                    METHODS=["pairwise", "order", "scamo", "cplex_cp", "cplex_mip", "gurobi", "cp_sat"],
                    TIME_LIMIT=300)

    def make_source(self, path, module=b"new scamo\n"):
        (path / "src").mkdir(parents=True)
        (path / "src" / "scamo_encoding.py").write_bytes(module)
        (path / "benchmark").mkdir()
        (path / "benchmark" / "run_sat_vs_ilp_cp.py").touch()
        (path / "data" / "hb").mkdir(parents=True)
        for i in range(24):
            (path / "data" / "hb" / f"graph{i:02d}.rnd").touch()

    def run_source_cell(self, env):
        with redirect_stdout(io.StringIO()):
            exec("".join(self.cells[3]["source"]), env)

    def test_source_selection_ignores_old_copy_and_preserves_results(self):
        with tempfile.TemporaryDirectory() as folder:
            env = self.source_environment(Path(folder))
            self.make_source(env["INPUT"] / "old" / "abp_source", b"old scamo\n")
            expected = env["INPUT"] / "new" / "abp_source"
            self.make_source(expected)
            result = env["WORK"] / "results.csv"
            result.write_bytes(b"preserved")
            self.run_source_cell(env)
            self.assertEqual(env["source"], expected)
            self.assertEqual(len(env["instances"]), 6)
            self.assertEqual(env["attempts"], 42)
            self.assertEqual(result.read_bytes(), b"preserved")
            self.assertEqual((env["PROJECT"] / "src" / "scamo_encoding.py").read_bytes(), b"new scamo\n")

    def test_ambiguous_or_wrong_source_does_not_silently_choose(self):
        with tempfile.TemporaryDirectory() as folder:
            env = self.source_environment(Path(folder))
            a, b = env["INPUT"] / "a", env["INPUT"] / "b"
            self.make_source(a)
            self.make_source(b)
            with self.assertRaises(ValueError):
                self.run_source_cell(env)
            env["SOURCE_LOCATION"] = a
            self.run_source_cell(env)
            (a / "src" / "scamo_encoding.py").write_bytes(b"wrong")
            with self.assertRaises(ValueError):
                self.run_source_cell(env)

    def test_source_zip_and_path_traversal(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            env = self.source_environment(root)
            source = root / "original"
            self.make_source(source)
            archive_path = env["INPUT"] / "abp_kaggle_source.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                for path in source.rglob("*"):
                    if path.is_file():
                        archive.write(path, "abp_source/" + path.relative_to(source).as_posix())
            self.run_source_cell(env)
            self.assertTrue((env["PROJECT"] / "benchmark" / "run_sat_vs_ilp_cp.py").is_file())
            with zipfile.ZipFile(archive_path, "a") as archive:
                archive.writestr("../escape.txt", "bad")
            with self.assertRaises(ValueError):
                env["extract_zip"](archive_path, root / "unpacked")
            self.assertFalse((root / "escape.txt").exists())

    def test_sat_diagnostics_keep_completed_totals_and_ignore_partial_line(self):
        tree = ast.parse("".join(self.cells[-1]["source"]))
        definitions = [node for node in tree.body if isinstance(node, (ast.Import, ast.FunctionDef))]
        env = {}
        exec(compile(ast.Module(body=definitions, type_ignores=[]), "diagnostics", "exec"), env)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "scamo.log"
            path.write_text("ABP ENCODING_TIME 10.5\nABP VARIABLES 100\n"
                            "ABP PHASE solving 100\nABP SOLVING_TIME 4\n"
                            "ABP SAT k=7 valid=True\nABP SAT k=99 valid=False\n"
                            "ABP PHASE solving 110\nABP SOLVING_TIME 50", encoding="utf-8")
            result = env["inspect_sat_log"](path)
            self.assertEqual(result, dict(encoding_reported_s=10.5, solving_reported_s=4.0,
                                         variables=100, last_phase="solving", last_valid_k=7))
            self.assertEqual(env["inspect_sat_log"](path.with_name("absent"))["last_phase"], "missing_log")

    def test_sat_diagnostics_detect_csv_log_disagreement(self):
        with tempfile.TemporaryDirectory() as folder:
            work = Path(folder)
            results = work / "results"
            log_folder = results / "logs" / "results"
            log_folder.mkdir(parents=True)
            csv_path = results / "results.csv"
            csv_path.write_text(
                "instance,method,run,best_k,time_s,memory_mb,status\n"
                "662_bus.mtx.rnd,scamo,1,,301.053,11247,Timeout\n",
                encoding="utf-8",
            )
            (log_folder / "662_bus.mtx.rnd.scamo.run1.log").write_text(
                "ABP SAT k=30 valid=True\nABP PHASE solving 100\n", encoding="utf-8"
            )
            env = dict(RESULTS=results, CSV_PATH=csv_path, WORK=work,
                       export_checkpoint=lambda: None, FileLink=lambda path: path,
                       display=lambda value: None)
            output = io.StringIO()
            with redirect_stdout(output):
                exec("".join(self.cells[-1]["source"]), env)
            self.assertIn("CSV và log không khớp", output.getvalue())
            self.assertIn("('662_bus.mtx.rnd', 'scamo', '1'), None, 30", output.getvalue())


if __name__ == "__main__":
    unittest.main()
