"""A ticket that stops goes to the Principal first: it answers what the project already
answers, or explains the stop to the user."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from conftest import Herdr, Project

PRINCIPAL = '[[agents]]\nname = "principal"\nrole = "principal"\nprogram = "pi"\nmodel = "m"\n'
ASKS = (
    "if 'use blue' not in prompt:\n"
    "    print('RESULT: question: which colour?'); sys.exit()\n"
    "pathlib.Path('colour.txt').write_text('blue\\n'); print('RESULT: done')"
)
ALWAYS_ASKS = "print('RESULT: question: which colour?')"


@pytest.fixture
def pi(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A stand-in for the Pi program on PATH; what it says is written by each test."""
    folder = tmp_path / "bin"
    folder.mkdir()
    script = folder / "pi.py"
    launcher = folder / "pi"
    launcher.write_text(f'#!/bin/sh\nexec {sys.executable} {script} "$@"\n')
    launcher.chmod(0o755)
    monkeypatch.setenv("PATH", f"{folder}{os.pathsep}{os.environ['PATH']}")
    return script


def says(pi: Path, body: str) -> None:
    pi.write_text(
        "import sys, pathlib\nprompt = sys.argv[-1]\n"
        "seen = pathlib.Path(__file__).with_name('seen.txt')\n"
        "seen.write_text((seen.read_text() if seen.exists() else '') + prompt + '\\n=====\\n')\n"
        f"{body}\n"
    )


def seen(pi: Path) -> list[str]:
    """The brief of each job the Principal was given."""
    path = pi.with_name("seen.txt")
    return path.read_text().split("\n=====\n")[:-1] if path.exists() else []


def test_the_principal_answers_what_is_already_decided_and_the_ticket_goes_on(
    project: Project, pi: Path
) -> None:
    says(pi, "print('RESULT: done: use blue, as docs/discovery.md says')")
    project.configure(coder=ASKS, settings=PRINCIPAL)
    project.dk("add", "Paint", "--spec", "Paint it.")

    project.dk("run")

    assert project.merged("colour.txt") == "blue\n"
    shown = project.dk("show", "1")
    assert "#1 done" in shown
    assert "sent on by principal: use blue, as docs/discovery.md says" in shown


def test_the_principal_explains_to_the_user_what_it_cannot_answer(
    project: Project, pi: Path
) -> None:
    says(pi, "print('RESULT: question: the colour was never decided; choose one')")
    project.configure(coder=ASKS, settings=PRINCIPAL)
    project.dk("add", "Paint", "--spec", "Paint it.")

    project.dk("run")

    status = project.dk("status")
    assert "#1 stopped at code" in status and "question: which colour?" in status
    shown = project.dk("show", "1")
    assert "principal: the colour was never decided; choose one" in shown


def test_the_principal_is_told_the_ticket_what_happened_and_why_it_stopped(
    project: Project, pi: Path
) -> None:
    says(pi, "print('RESULT: question: choose one')")
    project.configure(coder=ASKS, settings=PRINCIPAL)
    project.dk("add", "Paint", "--spec", "Paint it nicely.")

    project.dk("run")

    (brief,) = seen(pi)
    for part in ("Ticket #1: Paint", "Paint it nicely.", "coder-1 started", "which colour?"):
        assert part in brief
    assert "RESULT: done: " in brief and "RESULT: question: " in brief
    # It advised an exception for a coder; the program undid that coder's changes three times.
    assert "no note lets a coder change them" in brief
    # It sent a ticket with nothing for a user to see back to the test-writer, three times.
    assert "`--no-behaviour-tests` when it stopped for behaviour tests" in brief
    assert len(brief.split()) < 400


def test_the_principal_answers_a_stop_once_and_then_it_is_the_users(
    project: Project, pi: Path
) -> None:
    says(pi, "print('RESULT: done: use green')")
    project.configure(coder=ALWAYS_ASKS, settings=PRINCIPAL)
    project.dk("add", "Paint", "--spec", "Paint it.")

    project.dk("run")

    assert "#1 stopped at code" in project.dk("status")
    assert len(seen(pi)) == 1


def test_a_ticket_out_of_attempts_goes_to_the_principal_too(project: Project, pi: Path) -> None:
    says(pi, "print('RESULT: question: the check cannot pass; fix the check command')")
    hello = "pathlib.Path('a.txt').write_text('a')\nprint('RESULT: done')"
    project.configure(coder=hello, check="sys.exit(1)", max_attempts=1, settings=PRINCIPAL)
    project.dk("add", "Paint", "--spec", "Paint it.")

    project.dk("run")

    assert "principal: the check cannot pass; fix the check command" in project.dk("show", "1")


def test_behaviour_tests_waiting_for_approval_are_not_a_stop_to_explain(
    project: Project, pi: Path
) -> None:
    says(pi, "print('RESULT: done: approve them')")
    tester = (
        "pathlib.Path('features').mkdir(exist_ok=True)\n"
        "pathlib.Path('features/a.feature').write_text('Feature: A\\n')\nprint('RESULT: done')"
    )
    project.configure(coder=ALWAYS_ASKS, tester=tester, settings=PRINCIPAL)
    project.dk("add", "Paint", "--spec", "Paint it.")

    project.dk("run")

    assert "#1 stopped at approve" in project.dk("status")
    assert seen(pi) == []


def test_a_principal_that_gives_no_clear_answer_leaves_the_stop_as_it_was(
    project: Project, pi: Path
) -> None:
    says(pi, "print('hmm')")
    project.configure(coder=ALWAYS_ASKS, settings=PRINCIPAL)
    project.dk("add", "Paint", "--spec", "Paint it.")

    project.dk("run")

    status = project.dk("status")
    assert "#1 stopped at code" in status and "question: which colour?" in status


def test_an_answer_without_words_is_not_an_answer(project: Project, pi: Path) -> None:
    says(pi, "print('RESULT: done')")
    project.configure(coder=ALWAYS_ASKS, settings=PRINCIPAL)
    project.dk("add", "Paint", "--spec", "Paint it.")

    project.dk("run")

    assert "#1 stopped at code" in project.dk("status")
    assert "sent on" not in project.dk("show", "1")


def test_the_principal_cannot_change_the_tickets_work(project: Project, pi: Path) -> None:
    says(
        pi,
        "pathlib.Path('scribble.txt').write_text('x')\nprint('RESULT: done: use blue')",
    )
    project.configure(coder=ASKS, settings=PRINCIPAL)
    project.dk("add", "Paint", "--spec", "Paint it.")

    project.dk("run")

    assert "#1 done" in project.dk("status")
    assert project.merged("scribble.txt") is None


def test_what_the_principal_makes_of_stops_is_shown_in_a_tab_of_its_own(
    project: Project, pi: Path, herdr: Herdr
) -> None:
    says(pi, "print('the colour was never decided')\nprint('RESULT: question: choose one')")
    project.configure(coder=ALWAYS_ASKS, settings=PRINCIPAL)
    project.dk("add", "Paint", "--spec", "Paint it.")

    project.dk("run")

    calls = herdr.calls()
    labels = [call[call.index("--label") + 1] for call in calls if call[:2] == ["tab", "create"]]
    assert "team_forum" in labels and "principal" not in labels
    shown = (project.root / ".devkit" / "logs" / "team_forum.log").read_text()
    assert "#1 Paint" in shown and "the colour was never decided" in shown


def test_the_principal_is_told_when_an_answer_of_its_own_is_safe(
    project: Project, pi: Path
) -> None:
    says(pi, "print('RESULT: question: choose one')")
    project.configure(coder=ASKS, settings=PRINCIPAL)
    project.dk("add", "Paint", "--spec", "Paint it.")

    project.dk("run")

    (brief,) = seen(pi)
    for part in ("follows from", "cheap to put right", "what you base it on"):
        assert part in brief
    for the_users in ("what is built", "approved behaviour tests", "left open"):
        assert the_users in brief
