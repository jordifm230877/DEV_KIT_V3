"""Starting a command every day at a set time, through the system's own timers: systemd
where there is a `systemctl`, else macOS's launchd.

It writes a small file or two for the user's own account and asks the system to mind them.
It knows nothing of what the command does.
"""

from __future__ import annotations

import hashlib
import os
import plistlib
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


def _name(project: Path) -> str:
    """What this project's daily start is called; other projects have their own."""
    mark = hashlib.sha256(str(project).encode()).hexdigest()[:8]
    return f"dk-night-{re.sub(r'[^A-Za-z0-9]+', '-', project.name)}-{mark}"


def _units(project: Path) -> tuple[Path, Path]:
    home = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "systemd" / "user"
    return home / f"{_name(project)}.service", home / f"{_name(project)}.timer"


def _job(project: Path) -> Path:
    """The file macOS reads for this project."""
    return Path.home() / "Library" / "LaunchAgents" / f"{_name(project)}.plist"


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


def _launchctl(*args: str) -> str:
    """What went wrong, or nothing."""
    done = subprocess.run(["launchctl", *args], capture_output=True, text=True)
    return "" if done.returncode == 0 else done.stderr.strip() or f"exit {done.returncode}"


def _forgotten(job: Path) -> None:
    """Have macOS drop the job; it is no trouble if it did not have it."""
    if job.exists():
        _launchctl("bootout", f"gui/{os.getuid()}/{job.stem}")
        job.unlink()


def _launchd(project: Path, at: str, argv: Sequence[str]) -> None:
    job = _job(project)
    _forgotten(job)  # launchctl refuses to load a job it already minds
    job.parent.mkdir(parents=True, exist_ok=True)
    hour, minute = at.split(":")
    with job.open("wb") as file:
        plistlib.dump(
            {
                "Label": job.stem,
                "ProgramArguments": list(argv),
                "EnvironmentVariables": {"PATH": os.environ.get("PATH", "")},
                "StartCalendarInterval": {"Hour": int(hour), "Minute": int(minute)},
            },
            file,
        )
    if wrong := _launchctl("bootstrap", f"gui/{os.getuid()}", str(job)):
        raise RuntimeError(f"launchctl bootstrap failed: {wrong}")


def _systemd(project: Path, at: str, argv: Sequence[str]) -> None:
    service, timer = _units(project)
    service.parent.mkdir(parents=True, exist_ok=True)
    path = _quoted([f"PATH={os.environ.get('PATH', '')}"])
    service.write_text(_SERVICE.format(project=project, path=path, command=_quoted(argv)))
    timer.write_text(_TIMER.format(project=project, at=at))
    _systemctl("daemon-reload")
    _systemctl("enable", "--now", timer.name)


def every_day(project: Path, at: str, argv: Sequence[str]) -> None:
    """Have `argv` started every day at `at` (HH:MM), with the programs found now."""
    if not _TIME.fullmatch(at):
        raise RuntimeError(f"'{at}' is not a time of day; write it as HH:MM, like 02:30")
    if shutil.which("systemctl"):
        _systemd(project, at, argv)
    elif shutil.which("launchctl"):
        _launchd(project, at, argv)
    else:
        raise RuntimeError(
            "this system has no systemctl or launchctl to start it every day; "
            "have your own scheduler run `dk night` instead"
        )


def never(project: Path) -> None:
    """Take the daily start away; no trouble if there was none."""
    _forgotten(_job(project))
    service, timer = _units(project)
    if timer.exists():
        _systemctl("disable", "--now", timer.name)
    for unit in (service, timer):
        unit.unlink(missing_ok=True)
    if shutil.which("systemctl"):
        _systemctl("daemon-reload")
