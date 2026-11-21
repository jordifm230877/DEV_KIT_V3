"""After the coder, the program runs the checks of every ticket and the behaviour tests of
that ticket alone; the project says how its behaviour tests are run."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from conftest import Project

TESTER = (
    "number = prompt.split('Ticket #')[1].split(':')[0]\n"
    "pathlib.Path('features').mkdir(exist_ok=True)\n"
    "pathlib.Path(f'features/t{number}.feature').write_text('Feature: Greeting\\n')\n"
    "print('RESULT: done')"
)
HELLO = "pathlib.Path('greeting.txt').write_text('hello\\n')\nprint('RESULT: done')"
LEARNS = (
    "said = 'hello' if 'it must say hello' in prompt else 'hi'\n"
    "pathlib.Path('greeting.txt').write_text(said + '\\n')\nprint('RESULT: done')"
)
# Stands in for the project's own runner: it notes the files it was given.
RUNNER = """\
import pathlib, sys
with pathlib.Path(__file__).with_name("ran.txt").open("a") as ran:
    ran.write(" ".join(sys.argv[1:]) + "\\n")
if "hello" not in pathlib.Path("greeting.txt").read_text():
    sys.exit("it must say hello")
"""


def behaviour(project: Project) -> str:
    """The settings of a project that says how its behaviour tests are run."""
    tools = project.root.parent / "tools"
    tools.mkdir(exist_ok=True)
    (tools / "runner.py").write_text(RUNNER)
    command = json.dumps([sys.executable, str(tools / "runner.py"), "{features}"])
    return f"[checks.behaviour]\nrun = {command}\n"


def ran(project: Project) -> list[str]:
    noted = Path(project.root.parent / "tools" / "ran.txt")
    return noted.read_text().splitlines() if noted.exists() else []


def built(project: Project, title: str, number: str) -> None:
    project.dk("add", title, "--spec", "Say hello.")
    project.dk("run")
    project.dk("approve", number)
    project.dk("run")


def test_only_the_behaviour_tests_of_the_ticket_are_run_on_its_work(project: Project) -> None:
    project.configure(coder=HELLO, tester=TESTER, settings=behaviour(project))

    built(project, "Greet", "1")
    built(project, "Greet again", "2")

    assert ran(project) == ["features/t1.feature", "features/t2.feature"]
    assert "#2 done" in project.dk("status")


def test_no_behaviour_test_is_run_for_a_ticket_that_takes_none(project: Project) -> None:
    project.configure(coder=HELLO, tester=TESTER, settings=behaviour(project))
    project.dk("add", "Greet", "--spec", "Say hello.", "--no-behaviour-tests")

    project.dk("run")

    assert ran(project) == []
    assert "#1 done" in project.dk("status")


def test_work_that_fails_its_behaviour_tests_returns_to_the_coder(project: Project) -> None:
    project.configure(coder=LEARNS, tester=TESTER, settings=behaviour(project))

    built(project, "Greet", "1")

    assert project.merged("greeting.txt") == "hello\n"
    assert "[1 attempt]" in project.dk("status")
    assert "behaviour run failed" in project.dk("show", "1")


def test_a_command_takes_the_behaviour_tests_inside_one_of_its_words(project: Project) -> None:
    """As `make test FEATURES="a b"` does: the files go where the word names them."""
    settings = behaviour(project).replace('"{features}"', '"ONLY={features}"')
    project.configure(coder=HELLO, tester=TESTER, settings=settings)

    built(project, "Greet", "1")

    assert ran(project) == ["ONLY=features/t1.feature"]
