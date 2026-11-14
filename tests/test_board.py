"""A view that keeps itself up to date: what each agent is doing and the tickets not finished."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

from conftest import Herdr, Project

HELLO = "pathlib.Path('greeting.txt').write_text('hello\\n')\nprint('RESULT: done')"
# A coder that, in the middle of its job, looks at the view the way the user's tab does.
LOOKS = """
import subprocess, time
out = pathlib.Path(sys.argv[0]).with_name("board.txt")
with out.open("w") as screen:
    view = subprocess.Popen(
        [sys.executable, "-m", "dk", "--project", {root!r}, "status", "--watch"], stdout=screen
    )
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and "Tickets" not in out.read_text():
        time.sleep(0.05)
    view.terminate()
    view.wait()
pathlib.Path('greeting.txt').write_text('hello\\n')
print('RESULT: done')
"""


def board(project: Project) -> str:
    return (project.root.parent / "tools" / "board.txt").read_text()


def watch(project: Project) -> str:
    """The first screen of the view, as the user would see it."""
    command = [sys.executable, "-m", "dk", "--project", str(project.root), "status", "--watch"]
    view = subprocess.Popen(command, stdout=subprocess.PIPE, text=True)
    assert view.stdout is not None
    lines: list[str] = []
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and not any("finished" in line for line in lines):
        lines.append(view.stdout.readline())
    view.terminate()
    view.wait()
    return "".join(lines)


def test_the_view_says_which_agent_is_on_which_ticket(project: Project) -> None:
    project.configure(
        coder=LOOKS.format(root=str(project.root)), verifier="print('RESULT: approved')"
    )
    project.dk("add", "Greet", "--spec", "Say hello.")

    project.dk("run")

    seen = board(project)
    assert seen.index("Agents") < seen.index("coder-1") < seen.index("Tickets")
    working = next(line for line in seen.splitlines() if "coder-1" in line)
    assert "#1 Greet" in working and "code" in working
    idle = next(line for line in seen.splitlines() if "verifier-1" in line)
    assert "free" in idle and "#1" not in idle


def test_nobody_is_shown_working_once_the_work_has_ended(project: Project) -> None:
    project.configure(coder=HELLO)
    project.dk("add", "Greet", "--spec", "Say hello.")
    project.dk("run")

    seen = watch(project)

    assert "free" in next(line for line in seen.splitlines() if "coder-1" in line)


def test_the_view_lists_unfinished_tickets_and_only_counts_the_rest(project: Project) -> None:
    project.configure(coder=HELLO)
    project.dk("add", "Greet", "--spec", "Say hello.")
    project.dk("run")
    project.dk("add", "Old idea", "--spec", "x")
    project.dk("cancel", "2")
    project.dk("add", "Wave", "--spec", "Wave.", "--after", "1")

    seen = watch(project)

    assert "#3 specify  Wave" in seen
    assert "Greet" not in seen and "Old idea" not in seen
    assert "1 finished, 1 cancelled" in seen


def test_the_view_has_a_tab_of_its_own(project: Project, herdr: Herdr) -> None:
    project.configure(coder=HELLO)
    project.dk("add", "Greet", "--spec", "Say hello.")

    project.dk("run")

    calls = herdr.calls()
    labels = [call[call.index("--label") + 1] for call in calls if call[:2] == ["tab", "create"]]
    assert labels == ["status", "coder-1"]
    shown = [call for call in calls if call[:2] == ["pane", "run"]]
    assert shown[0][-2:] == ["status", "--watch"] and str(project.root) in shown[0]
    assert Path(shown[0][3]).name.startswith("python")


BOLD, DIM, OFF = "\033[1m", "\033[2m", "\033[0m"
GREEN, YELLOW, CYAN = "\033[32m", "\033[33m", "\033[36m"


def test_the_view_uses_colour_to_tell_what_needs_the_user(project: Project) -> None:
    project.configure(coder="print('RESULT: question: which colour?')")
    project.dk("add", "Paint", "--spec", "Paint it.", "--epic", "Walls")
    project.dk("run")
    project.dk("add", "Frame", "--spec", "Frame it.", "--epic", "Walls", "--after", "1")
    project.dk("add", "Sweep", "--spec", "Sweep.")

    seen = watch(project).splitlines()

    def shown(part: str) -> str:
        return next(line for line in seen if part in line)

    assert shown("Agents").endswith(f"{BOLD}{CYAN}Agents{OFF}")
    assert shown("Tickets") == f"{BOLD}{CYAN}Tickets{OFF}"
    assert shown("coder-1").startswith(DIM) and "free" in shown("coder-1")
    assert shown("Walls") == f"{BOLD}Walls{OFF}"
    assert shown("#1 stopped").startswith(f"{BOLD}{YELLOW}  #1 stopped at code")
    assert shown("#2").startswith(f"{DIM}  #2 specify") and "waits for #1" in shown("#2")
    assert shown("#3") == "#3 specify  Sweep"
    assert shown("finished") == f"{DIM}0 finished, 0 cancelled{OFF}"


def test_the_view_shows_a_working_agent_in_green(project: Project) -> None:
    project.configure(coder=LOOKS.format(root=str(project.root)))
    project.dk("add", "Greet", "--spec", "Say hello.")

    project.dk("run")

    working = next(line for line in board(project).splitlines() if "coder-1" in line)
    assert working.startswith(GREEN) and working.endswith(OFF)


def test_the_plain_list_has_no_colour(project: Project) -> None:
    project.configure(coder="print('RESULT: question: which colour?')")
    project.dk("add", "Paint", "--spec", "Paint it.", "--epic", "Walls")
    project.dk("run")

    assert "\033" not in project.dk("status")
