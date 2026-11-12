"""One Herdr tab per agent, each showing the file that fills with what the agent does.

Watching only: nothing typed in a tab reaches an agent, and trouble with Herdr never stops
the work.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path


def _herdr(herdr: str, *args: str) -> str | None:
    """Herdr's answer, or None if it could not do it."""
    try:
        done = subprocess.run([herdr, *args], capture_output=True, text=True, timeout=10)
    except OSError, subprocess.TimeoutExpired:
        return None
    return done.stdout if done.returncode == 0 else None


def _open(herdr: str, workspace: str, name: str, shown: Path) -> str | None:
    shown.parent.mkdir(parents=True, exist_ok=True)
    shown.touch()
    answer = _herdr(herdr, "tab", "create", "--workspace", workspace, "--label", name, "--no-focus")
    try:
        made = json.loads(answer or "")["result"]
        tab, pane = made["tab"]["tab_id"], made["root_pane"]["pane_id"]
    except ValueError, KeyError, TypeError:
        return None
    _herdr(herdr, "pane", "run", pane, "tail", "-n", "+1", "-F", str(shown))
    return str(tab)


def notify(herdr: str, title: str, body: str) -> None:
    """Tell the user, wherever they are in Herdr, that something needs them."""
    _herdr(herdr, "notification", "show", title, "--body", body, "--sound", "request")


@contextmanager
def tabs(herdr: str, workspace: str, shown: Mapping[str, Path]) -> Iterator[None]:
    """Open a tab for each named file while the work goes on, and close them afterwards."""
    opened = [_open(herdr, workspace, name, path) for name, path in shown.items()]
    try:
        yield
    finally:
        for tab in opened:
            if tab:
                _herdr(herdr, "tab", "close", tab)
