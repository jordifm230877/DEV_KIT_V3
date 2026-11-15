"""A ticket nobody wants any more is cancelled: no more work on it, its work thrown away."""

from __future__ import annotations

from conftest import Project
from test_talk import PRINCIPAL

HELLO = "pathlib.Path('greeting.txt').write_text('hello\\n')\nprint('RESULT: done')"
ASKS = "print('RESULT: question: which language?')"


def branches(project: Project) -> str:
    return project.git("branch", "--list", "ticket/*")


def test_a_cancelled_ticket_is_not_worked_on_again_and_its_work_is_thrown_away(
    project: Project,
) -> None:
    project.configure(coder="pathlib.Path('draft.txt').write_text('x')\n" + ASKS)
    project.dk("add", "Vague", "--spec", "Do the thing.")
    project.dk("run")
    assert "ticket/1" in branches(project)

    assert "#1 cancelled" in project.dk("cancel", "1")
    project.dk("run")

    assert "#1 cancelled  Vague" in project.dk("status")
    shown = project.dk("show", "1")
    assert shown.count("coder-1 started") == 1 and "cancelled" in shown.splitlines()[-1]
    assert branches(project) == ""
    assert not (project.root / ".devkit" / "work" / "ticket-1").exists()


def test_a_ticket_can_be_cancelled_before_anyone_starts_on_it(project: Project) -> None:
    project.configure(coder=HELLO)
    project.dk("add", "Unwanted", "--spec", "x")
    project.dk("add", "Greet", "--spec", "Say hello.")

    project.dk("cancel", "1")
    project.dk("run")

    status = project.dk("status")
    assert "#1 cancelled" in status and "#2 done" in status
    assert "started" not in project.dk("show", "1")


def test_a_cancelled_ticket_cannot_be_sent_on_or_cancelled_again(project: Project) -> None:
    project.configure(coder=ASKS)
    project.dk("add", "Vague", "--spec", "x")
    project.dk("run")
    project.dk("cancel", "1")

    assert "#1 is not stopped" in project.refused("retry", "1")
    assert "#1 is already cancelled" in project.refused("cancel", "1")


def test_finished_work_cannot_be_cancelled(project: Project) -> None:
    project.configure(coder=HELLO)
    project.dk("add", "Greet", "--spec", "Say hello.")
    project.dk("run")

    assert "#1 is already done" in project.refused("cancel", "1")
    assert project.merged("greeting.txt") == "hello\n"


def test_a_ticket_cancelled_while_an_agent_works_on_it_is_never_merged(project: Project) -> None:
    coder = (
        "number = prompt.split('Ticket #')[1][0]\n"
        "if number == '1':\n"
        "    import time; time.sleep(1)\n"
        "pathlib.Path(number + '.txt').write_text('x')\nprint('RESULT: done')"
    )
    talk = PRINCIPAL + (
        "dk('add', 'Unwanted', '--spec', spec('x'))\n"
        "wait_for('coder-1 started')\n"
        "dk('cancel', '1')\n"
        "dk('add', 'Wanted', '--spec', spec('y'))\n"
        "wait_for('#2 done', '2')\n"
    )
    project.configure(coder=coder, principal=talk)

    project.dk("talk")

    assert project.merged("2.txt") == "x" and project.merged("1.txt") is None
    assert "#1 cancelled" in project.dk("status")
    assert branches(project) == ""
