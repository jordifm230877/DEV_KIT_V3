"""What each job spends of its model is counted from what the agent's program reports: the
tokens sent to the model and the tokens it wrote."""

from __future__ import annotations

import json
import re

import pytest
from conftest import Programs, Project, Site, team

# What each program reports as it works: 1 500 tokens sent in all, and how many written.
PI = """
used = lambda sent, kept, written: emit(type="turn_end", message={"role": "assistant",
    "usage": {"input": sent, "cacheRead": kept, "cacheWrite": 100, "output": written}})
emit(type="message_update", usage={"input": 9, "output": 9})
used(300, 500, 10)
used(200, 300, 20)
"""
CLAUDE = """
def used(call, sent, kept, written):
    usage = {"input_tokens": sent, "cache_read_input_tokens": kept,
             "cache_creation_input_tokens": 100, "output_tokens": written}
    emit(type="assistant", message={"id": call, "role": "assistant", "content": [], "usage": usage})
used("m1", 300, 500, 1)
used("m1", 300, 500, 1)  # the same call, reported again with each part of what it said
used("m2", 200, 300, 2)
"""
CLAUDE_ENDS = """
emit(type="result", subtype="success", usage={"input_tokens": 500,
    "cache_read_input_tokens": 800, "cache_creation_input_tokens": 200, "output_tokens": 30})
"""
CODEX = """
emit(type="turn.completed",
     usage={"input_tokens": 1500, "cached_input_tokens": 900, "output_tokens": 30})
"""
WORKS = {"pi": PI, "claude": CLAUDE + CLAUDE_ENDS, "codex": CODEX}
DONE = "pathlib.Path('greeting.txt').write_text('hello\\n')\nprint('RESULT: done')\n"
# In the middle of its job, the program asks the site what the user's browser would, and
# the terminal for the ticket list the user would see.
LOOKS = """
import subprocess
from urllib.request import urlopen
sys.stdout.flush()
tools = here.parent / "tools"
with urlopen((tools / "site.txt").read_text() + "api/board") as answer:
    (tools / "board.json").write_bytes(answer.read())
"""


def history(project: Project) -> str:
    return project.dk("show", "1")


@pytest.mark.parametrize("program", ["pi", "claude", "codex"])
def test_a_tickets_history_says_what_each_job_spent(
    project: Project, programs: Programs, program: str
) -> None:
    programs.does(program, WORKS[program] + DONE)
    team(project, program, "coder")
    project.dk("add", "Greet", "--spec", "Say hello.")

    project.dk("run")

    assert "coder-1 used 1.5k tokens in, 30 out" in history(project)


@pytest.mark.parametrize(("program", "work", "written"), [("pi", PI, 30), ("claude", CLAUDE, 3)])
def test_the_board_says_what_a_job_has_spent_so_far(
    project: Project, programs: Programs, site: Site, program: str, work: str, written: int
) -> None:
    programs.does(program, work + LOOKS + DONE)
    team(project, program, "coder")
    project.dk("add", "Greet", "--spec", "Say hello.")

    project.dk("run")

    seen = json.loads((project.root.parent / "tools" / "board.json").read_text())
    assert seen["agents"][0]["spent"] == f"1.5k tokens in, {written} out"
    assert site("/api/board")["agents"][0]["spent"] == "", "nothing once it has ended"


def test_the_view_in_the_terminal_says_what_a_job_has_spent_so_far(
    project: Project, programs: Programs
) -> None:
    watches = """
import subprocess, time
sys.stdout.flush()
out = here / "board.txt"
with out.open("w") as screen:
    view = subprocess.Popen(
        [sys.executable, "-m", "dk", "--project", {root!r}, "status", "--watch"], stdout=screen
    )
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and "Tickets" not in out.read_text():
        time.sleep(0.05)
    view.terminate()
    view.wait()
"""
    programs.does("pi", PI + watches.format(root=str(project.root)) + DONE)
    team(project, "pi", "coder")
    project.dk("add", "Greet", "--spec", "Say hello.")

    project.dk("run")

    board = project.root.parent / "bin" / "board.txt"
    working = next(line for line in board.read_text().splitlines() if "coder-1" in line)
    assert re.search(r"since \S+ \S+  1\.5k tokens in, 30 out", working)


def test_each_job_is_counted_from_nothing(project: Project, programs: Programs) -> None:
    programs.does("pi", PI + "print('RESULT: question: which colour?')")
    team(project, "pi", "coder")
    project.dk("add", "Greet", "--spec", "Say hello.")
    project.dk("run")
    programs.does("pi", PI + DONE)

    project.dk("retry", "1", "--note", "blue")
    project.dk("run")

    assert history(project).count("coder-1 used 1.5k tokens in, 30 out") == 2


def test_large_and_small_counts_are_said_in_few_figures(
    project: Project, programs: Programs
) -> None:
    programs.does(
        "codex",
        'emit(type="turn.completed", usage={"input_tokens": 2340000, "output_tokens": 999})\n'
        'emit(type="turn.completed", usage={"input_tokens": 0, "output_tokens": 1})\n' + DONE,
    )
    team(project, "codex", "coder")
    project.dk("add", "Greet", "--spec", "Say hello.")

    project.dk("run")

    assert "coder-1 used 2.3M tokens in, 1.0k out" in history(project)


def test_a_program_that_reports_no_tokens_has_nothing_said_of_them(project: Project) -> None:
    project.configure(coder=DONE)
    project.dk("add", "Greet", "--spec", "Say hello.")

    project.dk("run")

    assert "used" not in history(project) and "tokens" not in history(project)
