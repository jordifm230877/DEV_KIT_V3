"""An agent's tab shows its work in colour; the file kept on disk stays plain text."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

from conftest import Herdr, Project

BOLD, PLAIN, DIM, OFF = "\033[1m", "\033[22m", "\033[2m", "\033[0m"
RED, GREEN, YELLOW, CYAN, NO_COLOUR = "\033[31m", "\033[32m", "\033[33m", "\033[36m", "\033[39m"
HELLO = "pathlib.Path('greeting.txt').write_text('hello\\n')\nprint('**wrote** it\\nRESULT: done')"


def followed(log: Path, later: str = "") -> list[str]:
    """What `dk follow` shows of a file: what is there, then what is added while it looks."""
    command = [sys.executable, "-m", "dk", "--project", str(log.parent), "follow", str(log)]
    view = subprocess.Popen(command, stdout=subprocess.PIPE, text=True)
    assert view.stdout is not None
    wanted = len(log.read_text().splitlines()) if log.exists() else 0
    lines = [view.stdout.readline().rstrip("\n") for _ in range(wanted)]
    if later:
        time.sleep(0.3)
        with log.open("a") as more:
            more.write(later)
        lines += [view.stdout.readline().rstrip("\n") for _ in later.splitlines()]
    view.terminate()
    view.wait()
    return lines


def test_the_parts_of_an_agents_work_are_told_apart_by_colour(tmp_path: Path) -> None:
    log = tmp_path / "coder-1.log"
    log.write_text(
        "=== #1 Greet (code) ===\n> bash ls -la\nI will write the file.\nerror: no credit\n"
    )

    title, tool, words, error = followed(log)

    assert title == f"{BOLD}{CYAN}=== #1 Greet (code) ==={OFF}"
    assert tool == f"{DIM}> bash ls -la{OFF}"
    assert words == "I will write the file."
    assert error == f"{RED}error: no credit{OFF}"


def test_a_title_that_says_when_the_job_started_is_a_title_too(tmp_path: Path) -> None:
    log = tmp_path / "coder-1.log"
    log.write_text("2026-11-14 17:09  === #1 Greet (code) ===\n2026-11-14 17:09  I began.\n")

    title, words = followed(log)

    assert title == f"{BOLD}{CYAN}2026-11-14 17:09  === #1 Greet (code) ==={OFF}"
    assert words == "2026-11-14 17:09  I began."


def test_emphasis_an_agent_writes_is_shown_and_its_marks_are_not(tmp_path: Path) -> None:
    log = tmp_path / "coder-1.log"
    log.write_text("It **must** pass `cargo test` first.\n## Summary\n2 * 3 * 4 and a `lone tick\n")

    words, heading, untouched = followed(log)

    assert words == f"It {BOLD}must{PLAIN} pass {CYAN}cargo test{NO_COLOUR} first."
    assert heading == f"{BOLD}## Summary{OFF}"
    assert untouched == "2 * 3 * 4 and a `lone tick"


def test_the_answer_is_coloured_by_what_it_means(tmp_path: Path) -> None:
    log = tmp_path / "coder-1.log"
    log.write_text(
        "RESULT: done\nRESULT: approved\nRESULT: rejected: no test\n"
        "RESULT: blocked: no network\nRESULT: question: which colour?\n"
    )

    done, approved, rejected, blocked, question = followed(log)

    assert done == f"{BOLD}{GREEN}RESULT: done{OFF}"
    assert approved == f"{BOLD}{GREEN}RESULT: approved{OFF}"
    assert rejected == f"{BOLD}{RED}RESULT: rejected: no test{OFF}"
    assert blocked == f"{BOLD}{YELLOW}RESULT: blocked: no network{OFF}"
    assert question == f"{BOLD}{YELLOW}RESULT: question: which colour?{OFF}"


def test_what_an_agent_does_later_is_shown_as_it_happens(tmp_path: Path) -> None:
    log = tmp_path / "coder-1.log"
    log.write_text("=== #1 Greet (code) ===\n")

    lines = followed(log, later="> bash ls\nRESULT: done\n")

    assert lines[1:] == [f"{DIM}> bash ls{OFF}", f"{BOLD}{GREEN}RESULT: done{OFF}"]


def test_a_file_that_does_not_exist_yet_is_waited_for(tmp_path: Path) -> None:
    log = tmp_path / "logs" / "coder-1.log"
    log.parent.mkdir()

    assert followed(log, later="RESULT: done\n") == [f"{BOLD}{GREEN}RESULT: done{OFF}"]


def test_the_tabs_show_colour_and_the_files_stay_plain(project: Project, herdr: Herdr) -> None:
    project.configure(coder=HELLO)
    project.dk("add", "Greet", "--spec", "Say hello.")

    project.dk("run")

    log = project.root / ".devkit" / "logs" / "coder-1.log"
    shown = [call[3:] for call in herdr.calls() if call[:2] == ["pane", "run"]]
    assert shown[1][-2:] == ["follow", str(log)]
    assert "\033" not in log.read_text() and "**wrote** it" in log.read_text()
    assert f"{BOLD}wrote{PLAIN} it" in followed(log)
