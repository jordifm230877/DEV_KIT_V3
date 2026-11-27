"""A program that is cut off, for taking too long or because the user stopped the work, is
warned first, so that it can tidy up what it started; one that goes on regardless is ended."""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest
from conftest import Project
from test_cancel import HELLO

from dk import child

# Tidies up when it is warned, taking a moment over it, as removing a container does.
TIDIES = (
    "import signal, time\n"
    "def tidy(*_):\n"
    "    time.sleep(0.3)\n"
    "    pathlib.Path(sys.argv[0]).with_name('tidied.txt').write_text('yes')\n"
    "    sys.exit(1)\n"
    "signal.signal(signal.SIGTERM, tidy)\n"
    "time.sleep(60)"
)


def test_a_check_that_is_cut_off_can_tidy_up_first(project: Project) -> None:
    """A real project's check was killed outright: its container went on running while
    the next check started (terastation ticket #182, 2026-11-27)."""
    project.configure(coder=HELLO, check=TIDIES, max_attempts=1, settings="check_minutes = 0.01")
    project.dk("add", "Greet", "--spec", "Create greeting.txt.")

    project.dk("run")

    assert "cut off after 0.01 minutes" in project.dk("show", "1")
    assert (project.root.parent / "tools" / "tidied.txt").read_text() == "yes"


def test_a_program_that_ignores_the_warning_is_ended(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(child, "_GRACE", 0.5)
    deaf = "import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(60)"
    began = time.monotonic()

    code = child.run([sys.executable, "-c", deaf], tmp_path, str, seconds=0.3)

    assert code is None and 0.8 <= time.monotonic() - began < 10


def test_what_the_program_started_may_finish_tidying_after_it_ends(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`make` ends at the warning before the recipe under it has tidied up."""
    monkeypatch.setattr(child, "_GRACE", 5)
    under = "trap 'sleep 0.5; echo yes > tidied.txt; exit 1' TERM; sleep 60 & wait"
    leader = f"import subprocess, time; subprocess.Popen(['sh', '-c', {under!r}]); time.sleep(60)"

    child.run([sys.executable, "-c", leader], tmp_path, str, seconds=0.5)

    assert (tmp_path / "tidied.txt").read_text() == "yes\n"


def test_a_program_that_ends_at_the_warning_is_not_waited_for(tmp_path: Path) -> None:
    began = time.monotonic()

    code = child.run([sys.executable, "-c", "import time; time.sleep(60)"], tmp_path, str, 0.3)

    assert code is None and time.monotonic() - began < 5
