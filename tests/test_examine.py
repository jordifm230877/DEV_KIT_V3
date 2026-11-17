"""An examiner reads each ticket before any work and stops it over what would be guessed."""

from __future__ import annotations

from conftest import Project
from test_behaviour_tests import HELLO, TESTER

APPROVES = "print('RESULT: approved')"
ASKS = (
    "if 'use blue' in prompt:\n"
    "    print('RESULT: approved')\n"
    "else:\n"
    "    print('RESULT: question: which colour is the wall?')"
)
KEEPS = "pathlib.Path(sys.argv[0]).with_name('seen.txt').write_text(prompt)\n" + APPROVES
IN_TURN = (
    "pathlib.Path('log.txt').open('a').write(prompt.split('Ticket #')[1][0])\nprint('RESULT: done')"
)


def started(project: Project, number: int = 1) -> list[str]:
    """The agents that worked on the ticket, in the order they started."""
    shown = project.dk("show", str(number)).splitlines()
    return [line.split()[2] for line in shown if line.endswith(" started")]


def test_a_ticket_is_examined_before_anyone_works_on_it(project: Project) -> None:
    project.configure(coder=HELLO, examiner=APPROVES)
    project.dk("add", "Greet", "--spec", "Say hello.")

    project.dk("run")

    assert "#1 done" in project.dk("status")
    assert started(project) == ["examiner-1", "coder-1"]


def test_a_doubt_stops_the_ticket_until_it_is_answered(project: Project) -> None:
    project.configure(coder=HELLO, examiner=ASKS)
    project.dk("add", "Paint", "--spec", "Paint the wall.")
    project.dk("run")
    status = project.dk("status")
    assert "#1 stopped at examine" in status and "which colour is the wall?" in status
    assert started(project) == ["examiner-1"], "nobody works on a ticket that is not clear"

    project.dk("retry", "1", "--note", "use blue")
    project.dk("run")

    assert "#1 done" in project.dk("status")
    assert started(project) == ["examiner-1", "examiner-1", "coder-1"]


def test_an_examiner_that_rejects_the_ticket_stops_it_too(project: Project) -> None:
    project.configure(coder=HELLO, examiner="print('RESULT: rejected: it is two tickets')")
    project.dk("add", "Paint", "--spec", "Paint the wall and mend the roof.")

    project.dk("run")

    status = project.dk("status")
    assert "#1 stopped at examine" in status and "it is two tickets" in status


def test_the_examiner_is_told_the_ticket_and_what_makes_one_unclear(project: Project) -> None:
    project.configure(coder=HELLO, examiner=KEEPS)
    project.dk("add", "Paint", "--spec", "Paint the wall of the shed.")

    project.dk("run")

    seen = (project.root.parent / "tools" / "seen.txt").read_text()
    assert "Ticket #1: Paint" in seen and "Paint the wall of the shed." in seen
    for looked_for in ("would have to guess", "nobody could check", "contradict", "more than one"):
        assert looked_for in seen
    assert "RESULT: approved" in seen and "RESULT: question:" in seen
    assert "docs/decisions.md" in seen and "discovery" not in seen
    assert len(seen.split()) < 200


def test_what_an_examiner_changes_is_thrown_away(project: Project) -> None:
    meddles = "pathlib.Path('meddled.txt').write_text('x')\n" + APPROVES
    project.configure(coder=HELLO, examiner=meddles)
    project.dk("add", "Greet", "--spec", "Say hello.")

    project.dk("run")

    assert "#1 done" in project.dk("status")
    assert project.merged("meddled.txt") is None


def test_a_ticket_without_behaviour_tests_is_examined_and_then_coded(project: Project) -> None:
    project.configure(coder=HELLO, tester=TESTER, examiner=APPROVES)
    project.dk("add", "Greet", "--spec", "Say hello.", "--no-behaviour-tests")

    project.dk("run")

    assert "#1 done" in project.dk("status")
    assert started(project) == ["examiner-1", "coder-1"]


def test_a_proposed_ticket_is_examined_once_it_is_accepted(project: Project) -> None:
    project.configure(coder=HELLO, tester=TESTER, examiner=APPROVES)
    project.dk("propose", "Greet", "--spec", "Say hello.")
    assert "it will start at examine" in project.dk("approve", "1", "--no-behaviour-tests")

    project.dk("run")

    assert started(project) == ["examiner-1", "coder-1"]


def test_tickets_without_behaviour_tests_are_still_built_one_on_the_other(
    project: Project,
) -> None:
    project.configure(coder=IN_TURN, tester=TESTER, examiner=APPROVES)
    project.dk("add", "First", "--spec", "a", "--no-behaviour-tests")
    project.dk("add", "Second", "--spec", "b", "--no-behaviour-tests")

    project.dk("run")

    assert project.merged("log.txt") == "12"
    assert project.dk("show", "2").count("coder-1 started") == 1
