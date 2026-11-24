"""Validate the canonical notebook or export its cells for local copying."""

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
NOTEBOOK = HERE / "abp_kaggle.ipynb"


def read_cells(path=NOTEBOOK):
    """Read notebook cells, checking that each Python cell is syntactically valid."""
    cells = json.loads(path.read_text(encoding="utf-8"))["cells"]
    for index, cell in enumerate(cells, 1):
        if cell["cell_type"] == "code":
            compile("".join(cell["source"]), f"cell-{index}", "exec")
    return cells


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="validate notebook and source hash")
    parser.add_argument("--export", action="store_true", help="write an ignored local cells_to_copy.txt")
    args = parser.parse_args()
    if not (args.check or args.export):
        parser.error("choose --check or --export")
    cells = read_cells()
    scamo = HERE.parents[2] / "src" / "scamo_encoding.py"
    expected_hash = hashlib.sha256(scamo.read_bytes()).hexdigest()
    config = "".join(cells[1]["source"])
    if f'EXPECTED_SCAMO_SHA256 = "{expected_hash}"' not in config:
        raise SystemExit("SCAMO hash in notebook differs from local source")
    if args.export:
        content = "\n".join(
            f"```{'python' if cell['cell_type'] == 'code' else 'markdown'}\n"
            f"{''.join(cell['source']).rstrip()}\n```\n"
            for cell in cells
        )
        (HERE / "cells_to_copy.txt").write_text(content, encoding="utf-8")
        print("Exported local cells_to_copy.txt")
    print(f"OK: {len(cells)} cells; SCAMO SHA256 {expected_hash}")


if __name__ == "__main__":
    main()
