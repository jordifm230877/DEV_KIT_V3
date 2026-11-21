"""The project's whole test suite is run when an epic is closed, and only then: the epic
closes once it passes, and what fails becomes a ticket of that epic."""

from __future__ import annotations

import json
import sys

from conftest import Project
from test_talk import PRINCIPAL

HELLO = "pathlib.Path('greeting.txt').write_text('hello\\n')\nprint('RESULT: done')"
# Its first ticket leaves the cake out; told that the suite fails, it bakes it.
FORGETS = (
    "fixing = 'the cake is missing' in prompt\n"
    "pathlib.Path('cake.txt' if fixing else 'greeting.txt').write_text('hello\\n')\n"
    "pathlib.Path(sys.argv[0]).with_name(f'told-{fixing}.txt').write_text(prompt)\n"
    "print('RESULT: done')"
)
SUITE = """\
import pathlib, sys
with pathlib.Path(__file__).with_name("suite-ran.txt").open("a") as ran:
    ran.write("ran\\n")
if not pathlib.Path("cake.txt").exists():
    sys.exit("the cake is missing")
"""


def suite(project: Project, needs_cake: bool) -> str:
    """The settings of a project that says what its whole test suite is."""
    tools = project.root.parent / "tools"
    tools.mkdir(exist_ok=True)
    (tools / "suite.py").write_text(SUITE if needs_cake else SUITE.split("if not")[0])
    return f"[checks.epic]\nall = {json.dumps([sys.executable, str(tools / 'suite.py')])}\n"


def runs(project: Project) -> int:
    ran = project.root.parent / "tools" / "suite-ran.txt"
    return len(ran.read_text().splitlines()) if ran.exists() else 0


def test_an_epic_closes_once_the_whole_test_suite_has_passed(project: Project) -> None:
    project.configure(coder=HELLO, settings=suite(project, needs_cake=False))
    project.dk("add", "Greet", "--spec", "Say hello.", "--epic", "Manners")
    project.dk("run")
    assert runs(project) == 0, "no ticket has the whole suite run on its work"

    said = project.dk("close", "Manners")
    waiting = project.dk("status")
    project.dk("run")

    assert "#2 written" in said and "whole test suite" in said
    assert "closed" not in waiting and "#2 suite  Close Manners" in waiting
    assert runs(project) == 1
    assert "Manners  closed" in project.dk("status")
    assert "epic 'Manners' is closed" in project.refused(
        "add", "Bow", "--spec", "b", "--epic", "Manners"
    )


def test_what_fails_in_the_suite_becomes_a_ticket_of_the_epic(project: Project) -> None:
    project.configure(coder=FORGETS, tester="pass", settings=suite(project, needs_cake=True))
    project.dk("add", "Greet", "--spec", "Say hello.", "--epic", "Manners", "--no-behaviour-tests")
    project.dk("run")
    project.dk("close", "Manners")

    project.dk("run")

    fix = project.dk("show", "3")
    assert "Epic: Manners" in fix and "the cake is missing" in fix
    assert "no behaviour tests" in fix, "it goes straight to the coder"
    assert "the whole test suite failed: #3 written" in project.dk("show", "2")
    assert project.merged("cake.txt") == "hello\n"
    assert runs(project) == 2, "it is run again once the fix is merged"
    assert "Manners  closed" in project.dk("status")


def test_an_epic_being_closed_is_not_closed_twice(project: Project) -> None:
    project.configure(coder=HELLO, settings=suite(project, needs_cake=False))
    project.dk("add", "Greet", "--spec", "Say hello.", "--epic", "Manners")
    project.dk("run")
    project.dk("close", "Manners")

    assert "#2 is not finished" in project.refused("close", "Manners")


def test_closing_an_epic_after_its_suite_has_its_work_documented(project: Project) -> None:
    documenter = "print('RESULT: done')"
    settings = suite(project, needs_cake=False)
    project.configure(coder=HELLO, documenter=documenter, settings=settings)
    project.dk("add", "Greet", "--spec", "Say hello.", "--epic", "Manners")
    project.dk("run")
    project.dk("close", "Manners")

    project.dk("run")

    assert "#3 done  Documentation" in project.dk("status")


def test_an_epic_whose_closing_is_given_up_while_the_suite_runs_stays_open(
    project: Project,
) -> None:
    settings = suite(project, needs_cake=True)
    slow = project.root.parent / "tools" / "suite.py"
    slow.write_text("import time\ntime.sleep(1)\n" + slow.read_text())
    talk = PRINCIPAL + (
        "dk('close', 'Manners')\ntime.sleep(0.5)\ndk('cancel', '2')\ntime.sleep(1.5)\n"
    )
    project.configure(coder=HELLO, principal=talk, settings=settings)
    project.dk("add", "Greet", "--spec", "Say hello.", "--epic", "Manners")
    project.dk("run")

    project.dk("talk")

    status = project.dk("status")
    assert runs(project) == 1 and "#2 cancelled" in status
    assert "closed" not in status and "#3" not in status, "nothing is written for a suite given up"
