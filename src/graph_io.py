from pathlib import Path


def load_graph(path: str | Path) -> tuple[int, list[tuple[int, int]]]:
    with open(path, encoding="utf-8-sig") as file:
        next(file)
        n, _, m = map(int, next(file).split())
        edges = [
            tuple(map(int, line.split()))
            for line in file
            if line.strip()
        ]

    return n, edges
