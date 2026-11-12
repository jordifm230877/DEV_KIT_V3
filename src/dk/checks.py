"""Run the project's own checks. The program runs them, so no agent can claim they passed."""

from __future__ import annotations

import threading
from collections.abc import Mapping, Sequence
from pathlib import Path

from dk import child

_TAIL_LINES = 30


def run(
    checks: Mapping[str, Sequence[str]],
    cwd: Path,
    logs: Path,
    seconds: float,
    stop: threading.Event | None = None,
) -> str | None:
    """Run each check in order. Returns None if all pass, else what failed and its last output."""
    logs.mkdir(parents=True, exist_ok=True)
    for name, argv in checks.items():
        log = logs / f"check-{name}.log"
        with log.open("w") as output:
            code = child.run(argv, cwd, output.write, seconds, stop)
        if code != 0:
            tail = "\n".join(log.read_text().splitlines()[-_TAIL_LINES:])
            return f"{name} failed:\n{tail}"
    return None
