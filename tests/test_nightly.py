"""The night shift can start by itself every day, through the system's own timers."""

from __future__ import annotations

import json
import os
import plistlib
import shutil
import sys
from pathlib import Path

import pytest
from conftest import Project

HELLO = "pathlib.Path('greeting.txt').write_text('hello\\n')\nprint('RESULT: done')"
FAKE = """\
import json, pathlib, sys
with pathlib.Path(__file__).with_name("calls.jsonl").open("a") as log:
    log.write(json.dumps(sys.argv[1:]) + "\\n")
"""


class Timers:
    """A stand-in for the system's timers: a `systemctl` that only notes what it is asked."""

    def __init__(
        self, folder: Path, monkeypatch: pytest.MonkeyPatch, program: str = "systemctl"
    ) -> None:
        self._bin, self.units = folder / "bin", folder / "config" / "systemd" / "user"
        self._bin.mkdir()
        (self._bin / "fake.py").write_text(FAKE)
        launcher = self._bin / program
        launcher.write_text(f'#!/bin/sh\nexec {sys.executable} {self._bin / "fake.py"} "$@"\n')
        launcher.chmod(0o755)
        monkeypatch.setenv("PATH", f"{self._bin}{os.pathsep}{os.environ['PATH']}")
        monkeypatch.setenv("XDG_CONFIG_HOME", str(folder / "config"))

    def asked(self) -> list[list[str]]:
        log = self._bin / "calls.jsonl"
        return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []

    def unit(self, kind: str) -> str:
        (found,) = self.units.glob(f"dk-night-project-*.{kind}")
        return found.read_text()


@pytest.fixture
def timers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Timers:
    return Timers(tmp_path, monkeypatch)


def test_a_night_shift_can_be_set_to_start_every_day(project: Project, timers: Timers) -> None:
    project.configure(coder=HELLO, auditor="print('RESULT: done')")

    said = project.dk("night", "--at", "02:30")

    assert "every day at 02:30" in said and "--off" in said
    assert "OnCalendar=*-*-* 02:30:00" in timers.unit("timer")
    service = timers.unit("service")
    assert f'"-m" "dk" "--project" "{project.root}" "night"' in service
    assert f'Environment="PATH={os.environ["PATH"]}"' in service, "agents are found at night too"
    name = next(timers.units.glob("*.timer")).name
    assert timers.asked() == [
        ["--user", "daemon-reload"],
        ["--user", "enable", "--now", name],
    ]
    assert project.dk("status") == "", "setting the time starts nothing now"


def test_the_daily_night_shift_can_be_taken_away(project: Project, timers: Timers) -> None:
    project.configure(coder=HELLO, auditor="print('RESULT: done')")
    project.dk("night", "--at", "02:30")
    name = next(timers.units.glob("*.timer")).name

    said = project.dk("night", "--off")

    assert "no longer" in said
    assert timers.asked()[2:] == [["--user", "disable", "--now", name], ["--user", "daemon-reload"]]
    assert list(timers.units.iterdir()) == []


def test_taking_away_a_night_shift_that_was_never_set_is_no_trouble(
    project: Project, timers: Timers
) -> None:
    project.configure(coder=HELLO, auditor="print('RESULT: done')")

    assert "no longer" in project.dk("night", "--off")


@pytest.mark.parametrize("time", ["25:00", "2", "02:60", "tonight"])
def test_the_time_must_be_a_time_of_day(project: Project, timers: Timers, time: str) -> None:
    project.configure(coder=HELLO, auditor="print('RESULT: done')")

    assert "HH:MM" in project.refused("night", "--at", time)
    assert timers.asked() == []


def test_a_daily_night_shift_needs_an_auditor(project: Project, timers: Timers) -> None:
    project.configure(coder=HELLO)

    assert "no agent has the role 'auditor'" in project.refused("night", "--at", "02:30")
    assert timers.asked() == []


def test_a_system_without_such_timers_says_what_to_do(
    project: Project, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project.configure(coder=HELLO, auditor="print('RESULT: done')")
    monkeypatch.setenv("PATH", str(tmp_path / "nothing-here"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))

    refused = project.refused("night", "--at", "02:30")

    assert "systemctl" in refused and "your own scheduler" in refused
    assert not (tmp_path / "config").exists()


@pytest.fixture
def mac(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Timers:
    """A computer whose timers are macOS's: a `launchctl` and no `systemctl`."""
    timers = Timers(tmp_path, monkeypatch, "launchctl")
    (tmp_path / "bin" / "git").symlink_to(str(shutil.which("git")))
    monkeypatch.setenv("PATH", str(tmp_path / "bin"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    return timers


def test_on_macos_the_night_shift_starts_every_day_too(
    project: Project, mac: Timers, tmp_path: Path
) -> None:
    project.configure(coder=HELLO, auditor="print('RESULT: done')")

    said = project.dk("night", "--at", "02:05")

    (file,) = (tmp_path / "home" / "Library" / "LaunchAgents").glob("dk-night-project-*.plist")
    job = plistlib.loads(file.read_bytes())
    assert "every day at 02:05" in said
    assert job["Label"] == file.stem
    assert job["StartCalendarInterval"] == {"Hour": 2, "Minute": 5}
    assert job["ProgramArguments"][1:] == ["-m", "dk", "--project", str(project.root), "night"]
    assert job["EnvironmentVariables"] == {"PATH": str(tmp_path / "bin")}
    assert mac.asked() == [["bootstrap", f"gui/{os.getuid()}", str(file)]]
    assert not (tmp_path / "config").exists()


def test_on_macos_a_new_time_takes_the_place_of_the_old(
    project: Project, mac: Timers, tmp_path: Path
) -> None:
    """launchctl refuses to load a job it already minds."""
    project.configure(coder=HELLO, auditor="print('RESULT: done')")
    project.dk("night", "--at", "02:05")

    project.dk("night", "--at", "04:00")

    (file,) = (tmp_path / "home" / "Library" / "LaunchAgents").iterdir()
    assert plistlib.loads(file.read_bytes())["StartCalendarInterval"] == {"Hour": 4, "Minute": 0}
    domain = f"gui/{os.getuid()}"
    assert mac.asked()[1:] == [
        ["bootout", f"{domain}/{file.stem}"],
        ["bootstrap", domain, str(file)],
    ]


def test_on_macos_the_daily_night_shift_can_be_taken_away(
    project: Project, mac: Timers, tmp_path: Path
) -> None:
    project.configure(coder=HELLO, auditor="print('RESULT: done')")
    project.dk("night", "--at", "02:05")
    (file,) = (tmp_path / "home" / "Library" / "LaunchAgents").iterdir()

    said = project.dk("night", "--off")

    assert "no longer" in said and not file.exists()
    assert mac.asked()[1:] == [["bootout", f"gui/{os.getuid()}/{file.stem}"]]
    assert "no longer" in project.dk("night", "--off"), "twice is no trouble"
