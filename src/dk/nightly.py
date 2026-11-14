"""Starting a command every day at a set time, through the system's own timers (systemd).

It writes two small files for the user's own account and asks the system to mind them. It
knows nothing of what the command does.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path

_TIME = re.compile(r"([01]\d|2[0-3]):[0-5]\d")
_SERVICE = """\
[Unit]
Description=DevKit night shift for {project}

[Service]
Type=oneshot
Environment={path}
ExecStart={command}
"""
_TIMER = """\
[Unit]
Description=DevKit night shift for {project}, every day at {at}

[Timer]
OnCalendar=*-*-* {at}:00

[Install]
WantedBy=timers.target
"""


def _units(project: Path) -> tuple[Path, Path]:
    """The two files for this project; other projects have their own."""
    home = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "systemd" / "user"
    mark = hashlib.sha256(str(project).encode()).hexdigest()[:8]
    name = f"dk-night-{re.sub(r'[^A-Za-z0-9]+', '-', project.name)}-{mark}"
    return home / f"{name}.service", home / f"{name}.timer"


def _quoted(argv: Sequence[str]) -> str:
    """The command as the system's timer files want it written."""
    marked = (
        re.sub(r'(["\\])', r"\\\1", part).replace("%", "%%").replace("$", "$$") for part in argv
    )
    return " ".join(f'"{part}"' for part in marked)


def _systemctl(*args: str) -> None:
    done = subprocess.run(["systemctl", "--user", *args], capture_output=True, text=True)
    if done.returncode != 0:
        raise RuntimeError(f"systemctl {args[0]} failed: {done.stderr.strip()}")


def every_day(project: Path, at: str, argv: Sequence[str]) -> None:
    """Have `argv` started every day at `at` (HH:MM), with the programs found now."""
    if not _TIME.fullmatch(at):
        raise RuntimeError(f"'{at}' is not a time of day; write it as HH:MM, like 02:30")
    if not shutil.which("systemctl"):
        raise RuntimeError(
            "this system has no systemctl to start it every day; "
            "have your own scheduler run `dk night` instead"
        )
    service, timer = _units(project)
    service.parent.mkdir(parents=True, exist_ok=True)
    path = _quoted([f"PATH={os.environ.get('PATH', '')}"])
    service.write_text(_SERVICE.format(project=project, path=path, command=_quoted(argv)))
    timer.write_text(_TIMER.format(project=project, at=at))
    _systemctl("daemon-reload")
    _systemctl("enable", "--now", timer.name)


def never(project: Path) -> None:
    """Take the daily start away; no trouble if there was none."""
    service, timer = _units(project)
    if timer.exists():
        _systemctl("disable", "--now", timer.name)
    for unit in (service, timer):
        unit.unlink(missing_ok=True)
    if shutil.which("systemctl"):
        _systemctl("daemon-reload")
