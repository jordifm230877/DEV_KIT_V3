"""Run another program to its end, within a time limit, and able to be stopped.

Shared groundwork for the pieces that start programs. It knows nothing about agents or checks.
"""

from __future__ import annotations

import contextlib
import os
import signal
import subprocess
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

_LOOK_EVERY = 0.05
_GRACE = 10.0  # seconds a program has to tidy up once it is told to end


def _gone(child: subprocess.Popen[str]) -> bool:
    """Whether the program and everything it started have ended."""
    child.poll()  # an ended program still counts until it has been asked after
    try:
        os.killpg(child.pid, 0)
    except ProcessLookupError:
        return True
    return False


def _end(child: subprocess.Popen[str]) -> None:
    """Warn the program and what it started, so that they can tidy up; end whatever is
    still there `_GRACE` seconds later. Ended outright, a real project's check left its
    container running while the next check started."""
    with contextlib.suppress(ProcessLookupError):
        os.killpg(child.pid, signal.SIGTERM)
        warned = time.monotonic()
        while not _gone(child) and time.monotonic() - warned < _GRACE:
            time.sleep(_LOOK_EVERY)
        os.killpg(child.pid, signal.SIGKILL)


def _cut_off(
    child: subprocess.Popen[str], seconds: float, stop: threading.Event | None, cut: threading.Event
) -> None:
    """Watch the program; end it, and say so, if it runs too long or `stop` is set."""
    deadline = time.monotonic() + seconds
    while child.poll() is None:
        if time.monotonic() > deadline or (stop is not None and stop.is_set()):
            cut.set()
            _end(child)
            return
        time.sleep(_LOOK_EVERY)


def run(
    argv: Sequence[str],
    cwd: Path,
    show: Callable[[str], object],
    seconds: float,
    stop: threading.Event | None = None,
    feed: str | None = None,
    env: Mapping[str, str] | None = None,
) -> int | None:
    """Give each line the program prints to `show`. Returns its exit code, or None if it
    was cut off for taking longer than `seconds` or because `stop` was set."""
    child = subprocess.Popen(
        list(argv),
        cwd=cwd,
        env={**os.environ, **(env or {})},
        stdin=subprocess.DEVNULL if feed is None else subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        text=True,
        errors="replace",
    )
    cut = threading.Event()
    threading.Thread(target=_cut_off, args=(child, seconds, stop, cut), daemon=True).start()
    if child.stdin is not None:
        with contextlib.suppress(BrokenPipeError):
            child.stdin.write(feed or "")
            child.stdin.close()
    assert child.stdout is not None
    for line in child.stdout:
        show(line)
    code = child.wait()
    return None if cut.is_set() else code
