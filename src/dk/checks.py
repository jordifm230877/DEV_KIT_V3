"""Run the project's own checks. The program runs them, so no agent can claim they passed."""

from __future__ import annotations

import os
import signal
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path

_TAIL_LINES = 30


def run(checks: Mapping[str, Sequence[str]], cwd: Path, logs: Path, seconds: float) -> str | None:
    """Run each check in order. Returns None if all pass, else what failed and its last output."""
    logs.mkdir(parents=True, exist_ok=True)
    for name, argv in checks.items():
        log = logs / f"check-{name}.log"
        with log.open("wb") as output:
            child = subprocess.Popen(
                list(argv),
                cwd=cwd,
                stdin=subprocess.DEVNULL,
                stdout=output,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            try:
                code: int | str = child.wait(timeout=seconds)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()
                code = "took too long"
        if code != 0:
            tail = "\n".join(log.read_text(errors="replace").splitlines()[-_TAIL_LINES:])
            return f"{name} failed:\n{tail}"
    return None
