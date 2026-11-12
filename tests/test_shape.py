"""The rules that keep the project small and its pieces separable."""

from __future__ import annotations

import ast
from pathlib import Path

SOURCE = Path(__file__).parent.parent / "src" / "dk"
MAX_LINES = 300
COMPOSERS = {"director", "cli"}  # the only pieces allowed to know about the others


def _pieces() -> list[Path]:
    return sorted(SOURCE.glob("*.py"))


def test_every_piece_can_be_read_in_one_sitting() -> None:
    long = {
        path.name: n for path in _pieces() if (n := len(path.read_text().splitlines())) > MAX_LINES
    }

    assert not long, f"split these pieces (limit {MAX_LINES} lines): {long}"


def test_pieces_do_not_depend_on_each_other() -> None:
    tangled = []
    for path in _pieces():
        if path.stem in COMPOSERS:
            continue
        for node in ast.walk(ast.parse(path.read_text())):
            names = (
                [node.module or ""]
                if isinstance(node, ast.ImportFrom)
                else [alias.name for alias in node.names]
                if isinstance(node, ast.Import)
                else []
            )
            tangled += [
                f"{path.name} imports {name}" for name in names if name.split(".")[0] == "dk"
            ]

    assert not tangled, tangled


def test_running_needs_nothing_installed_beyond_python() -> None:
    project = (SOURCE.parent.parent / "pyproject.toml").read_text()

    assert "\ndependencies = []\n" in project
