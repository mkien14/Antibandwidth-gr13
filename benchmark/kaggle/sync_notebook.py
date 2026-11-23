"""Generate the notebook from cells_to_copy.txt; use --check to detect drift."""
import argparse
import hashlib
import json
from pathlib import Path
import re


HERE = Path(__file__).resolve().parent


def read_cells(path=HERE / "cells_to_copy.txt"):
    blocks = re.findall(r"^```(python|markdown)\n(.*?)^```[ \t]*$",
                        path.read_text(encoding="utf-8"), re.M | re.S)
    if not blocks:
        raise ValueError("No notebook cells found")
    cells = []
    for index, (language, source) in enumerate(blocks):
        kind = "code" if language == "python" else "markdown"
        if kind == "code":
            compile(source, f"cell-{index + 1}", "exec")
        cell = dict(cell_type=kind, id=f"abp-{index + 1:02d}", metadata={},
                    source=source.splitlines(keepends=True))
        if kind == "code":
            cell.update(execution_count=None, outputs=[])
        cells.append(cell)
    return cells


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    cells = read_cells()
    scamo = HERE.parents[1] / "src" / "scamo_encoding.py"
    expected_hash = hashlib.sha256(scamo.read_bytes()).hexdigest()
    config = "".join(cells[1]["source"])
    if f'EXPECTED_SCAMO_SHA256 = "{expected_hash}"' not in config:
        raise SystemExit("Update EXPECTED_SCAMO_SHA256 in cells_to_copy.txt first")
    notebook = dict(cells=cells, metadata={
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python"},
    }, nbformat=4, nbformat_minor=5)
    target = HERE / "abp_kaggle.ipynb"
    if args.check:
        if json.loads(target.read_text(encoding="utf-8")) != notebook:
            raise SystemExit("Notebook differs from cells_to_copy.txt; run sync_notebook.py")
        print(f"OK: {len(cells)} cells match; SCAMO SHA256 {expected_hash}")
    else:
        target.write_text(json.dumps(notebook, ensure_ascii=False, indent=1) + "\n",
                          encoding="utf-8")
        print(f"Updated {target.name}: {len(cells)} cells; outputs cleared")


if __name__ == "__main__":
    main()
