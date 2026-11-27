"""A ticket the user wants left for later is paused: nobody starts on it, and its work is
kept until it is sent on."""

from __future__ import annotations

from pathlib import Path

from conftest import Project
from test_stops import PRINCIPAL as ANSWERS
from test_stops import pi, says, seen  # noqa: F401
from test_talk import PRINCIPAL, notes

WRITES = (
    "number = prompt.split('Ticket #')[1][0]\n"
    "pathlib.Path(number + '.txt').write_text('x')\nprint('RESULT: done')"
)
ASKS = "print('RESULT: question: which language?')"


def test_a_paused_ticket_is_left_alone_until_it_is_sent_on(project: Project) -> None:
    project.configure(coder=WRITES)
    project.dk("add", "Later", "--spec", "x")
    project.dk("add", "Now", "--spec", "y")

    assert "#1 paused" in project.dk("pause", "1")
    project.dk("run")

    status = project.dk("status")
    assert "#1 stopped at specify  Later  paused by the user" in status and "#2 done" in status
    assert "started" not in project.dk("show", "1")

    project.dk("retry", "1")
    project.dk("run")

    assert "#1 done" in project.dk("status") and project.merged("1.txt") == "x"


def test_a_ticket_paused_while_an_agent_works_on_it_keeps_that_work(project: Project) -> None:
    coder = "import time\nif 'Ticket #1' in prompt:\n    time.sleep(1)\n" + WRITES
    talk = PRINCIPAL + (
        "dk('add', 'Later', '--spec', spec('x'), '--behaviour-tests')\n"
        "wait_for('coder-1 started')\n"
        "dk('pause', '1')\n"
        "dk('add', 'Now', '--spec', spec('y'), '--behaviour-tests')\n"
        "wait_for('#2 done', '2')\n"
    )
    project.configure(coder=coder, principal=talk)

    project.dk("talk")

    assert notes(project) == ""
    assert project.merged("2.txt") == "x" and project.merged("1.txt") is None
    assert "#1 stopped at check  Later  paused by the user" in project.dk("status")

    project.dk("retry", "1")
    project.dk("run")

    assert project.merged("1.txt") == "x"
    assert project.dk("show", "1").count("coder-1 started") == 1


def test_what_the_next_agent_was_to_be_told_survives_a_pause(project: Project) -> None:
    verifier = (
        "print('RESULT: approved' if 'again' in pathlib.Path('1.txt').read_text() "
        "else 'RESULT: rejected: write it again')"
    )
    coder = (
        "if 'write it again' in prompt and 'paused' not in prompt:\n"
        "    pathlib.Path('1.txt').write_text('again')\n    print('RESULT: done')\n"
        "else:\n    " + WRITES.replace("\n", "\n    ")
    )
    talk = PRINCIPAL + (
        "dk('add', 'Later', '--spec', spec('x'), '--behaviour-tests')\n"
        "wait_for('verifier-1 started')\n"
        "dk('pause', '1')\n"
        "wait_for('paused by the user')\n"
        "time.sleep(1.5)\n"
    )
    verifier = "import time; time.sleep(1)\n" + verifier
    project.configure(coder=coder, verifier=verifier, principal=talk)

    project.dk("talk")

    assert "#1 stopped at code  Later  [1 attempt]  paused by the user" in project.dk("status")

    project.dk("retry", "1")
    project.dk("run")

    assert project.merged("1.txt") == "again"
    assert project.dk("show", "1").count("coder-1 started") == 2


def test_a_question_asked_from_a_paused_ticket_waits_for_the_user(
    project: Project,
    pi: Path,  # noqa: F811
) -> None:
    """Sent on by the Principal's answer, the ticket would no longer be paused."""
    says(pi, "print('RESULT: done: use blue')")
    coder = (
        "import re, shlex, subprocess\n"
        "dk = shlex.split(re.search(r'`([^`]*-m dk[^`]*?) propose', prompt).group(1))\n"
        "subprocess.run([*dk, 'pause', '1'], capture_output=True)\n" + ASKS
    )
    project.configure(coder=coder, settings=ANSWERS)
    project.dk("add", "Vague", "--spec", "x")

    project.dk("run")

    assert "#1 stopped at code  Vague  question: which language?" in project.dk("status")
    assert seen(pi) == []


def test_only_a_ticket_that_would_go_on_can_be_paused(project: Project) -> None:
    project.configure(coder=ASKS)
    project.dk("add", "Vague", "--spec", "x")
    project.dk("add", "Other", "--spec", "y")
    project.dk("pause", "2")
    project.dk("run")

    assert "#1 is already stopped" in project.refused("pause", "1")
    assert "#2 is already stopped" in project.refused("pause", "2")
    project.dk("cancel", "2")
    assert "#2 is already cancelled" in project.refused("pause", "2")


def test_a_ticket_paused_before_anybody_worked_on_it_can_be_rewritten(project: Project) -> None:
    told = "pathlib.Path('told.txt').write_text(prompt)\nprint('RESULT: done')"
    project.configure(coder=told)
    project.dk("add", "Later", "--spec", "Say hello.")
    project.dk("pause", "1")

    assert "#1 edited" in project.dk("edit", "1", "--spec", "Say good morning.")

    assert "#1 stopped at specify  Later  paused by the user" in project.dk("status")
    project.dk("retry", "1")
    project.dk("run")
    assert "Say good morning." in str(project.merged("told.txt"))
