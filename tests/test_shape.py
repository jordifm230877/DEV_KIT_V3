"""The rules that keep the project small and its pieces separable."""

from __future__ import annotations

import ast
from pathlib import Path

SOURCE = Path(__file__).parent.parent / "src" / "dk"
MAX_LINES = 300
COMPOSERS = {
    "director",
    "jobs",
    "orders",
    "preflight",
    "views",
    "cli",
    "__main__",
}  # the only pieces allowed to know the others
GROUNDWORK = {"dk.child"}  # shared by any piece; knows about none of them


def _pieces() -> list[Path]:
    return sorted(SOURCE.glob("*.py"))


def test_every_piece_can_be_read_in_one_sitting() -> None:
    long = {
        path.name: n for path in _pieces() if (n := len(path.read_text().splitlines())) > MAX_LINES
    }

    assert not long, f"split these pieces (limit {MAX_LINES} lines): {long}"


def _imported(node: ast.AST) -> list[str]:
    if isinstance(node, ast.ImportFrom) and node.module == "dk":
        return [f"dk.{alias.name}" for alias in node.names]
    if isinstance(node, ast.ImportFrom):
        return [node.module or ""]
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    return []


def test_pieces_do_not_depend_on_each_other() -> None:
    tangled = []
    for path in _pieces():
        if path.stem in COMPOSERS:
            continue
        for node in ast.walk(ast.parse(path.read_text())):
            tangled += [
                f"{path.name} imports {name}"
                for name in _imported(node)
                if name.split(".")[0] == "dk" and name not in GROUNDWORK
            ]

    assert not tangled, tangled


def test_the_groundwork_knows_no_piece() -> None:
    for name in GROUNDWORK:
        source = (SOURCE / f"{name.split('.')[1]}.py").read_text()
        uses = [found for node in ast.walk(ast.parse(source)) for found in _imported(node)]

        assert not [found for found in uses if found.split(".")[0] == "dk"]


def test_running_needs_nothing_installed_beyond_python() -> None:
    project = (SOURCE.parent.parent / "pyproject.toml").read_text()

    assert "\ndependencies = []\n" in project
