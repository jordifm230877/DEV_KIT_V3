"""In a repository of several components, a check may name the paths it is for: it is run
on a ticket only when the ticket changed something there."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from conftest import Project

# The title of a ticket names the files its coder writes.
CODER = (
    "title = prompt.split('Ticket #')[1].splitlines()[0].split(': ', 1)[1]\n"
    "for name in title.split():\n"
    "    file = pathlib.Path(name)\n"
    "    file.parent.mkdir(parents=True, exist_ok=True)\n"
    "    file.write_text('new\\n')\n"
    "print('RESULT: done')"
)
MOVES = "pathlib.Path('login/old.txt').rename('auth/new.txt')\nprint('RESULT: done')"
TESTER = (
    "title = prompt.split('Ticket #')[1].splitlines()[0].split(': ', 1)[1]\n"
    "for name in title.split():\n"
    "    file = pathlib.Path(name).parent / 'features' / 'it.feature'\n"
    "    file.parent.mkdir(parents=True, exist_ok=True)\n"
    "    file.write_text('Feature: It\\n')\n"
    "print('RESULT: done')"
)
# Stands in for a component's own tests: it notes that it ran, and with what.
NOTES = """\
import pathlib, sys
with pathlib.Path(__file__).with_name("ran.txt").open("a") as ran:
    ran.write(" ".join(sys.argv[1:]) + "\\n")
"""


def _check(project: Project, table: str, name: str, *words: str) -> str:
    tools = project.root.parent / "tools"
    tools.mkdir(exist_ok=True)
    (tools / "notes.py").write_text(NOTES)
    command = json.dumps([sys.executable, str(tools / "notes.py"), name, *words])
    return f'[{table}.{name}]\nrun = {command}\npaths = ["{name}/**"]\n'


def components(project: Project) -> str:
    """The settings of a project of two components, each with its own check."""
    return _check(project, "checks", "auth") + _check(project, "checks", "login")


def ran(project: Project) -> list[str]:
    noted = Path(project.root.parent / "tools" / "ran.txt")
    return noted.read_text().splitlines() if noted.exists() else []


def test_a_ticket_runs_only_the_checks_of_what_it_changed(project: Project) -> None:
    project.configure(coder=CODER, settings=components(project))
    project.dk("add", "auth/a.txt", "--spec", "a")

    project.dk("run")

    assert ran(project) == ["auth"]
    shown = project.dk("show", "1")
    assert "#1 done" in project.dk("status")
    assert "checks: auth, unit; left out, nothing of theirs changed: login" in shown


def test_a_ticket_that_changed_two_components_runs_both_once(project: Project) -> None:
    project.configure(coder=CODER, settings=components(project))
    project.dk("add", "auth/a.txt login/deep/b.txt", "--spec", "a")

    project.dk("run")

    assert ran(project) == ["auth", "login"]
    assert "checks: auth, login, unit\n" in project.dk("show", "1") + "\n"


def test_a_file_moved_between_components_runs_the_checks_of_both(project: Project) -> None:
    (project.root / "login").mkdir()
    (project.root / "auth").mkdir()
    (project.root / "login" / "old.txt").write_text("a line\n" * 20)
    (project.root / "auth" / "kept.txt").write_text("kept\n")
    project.git("add", "-A")
    project.git("commit", "-qm", "two components")
    project.configure(coder=MOVES, settings=components(project))
    project.dk("add", "Move it", "--spec", "a")

    project.dk("run")

    assert ran(project) == ["auth", "login"]


def test_a_change_that_is_in_no_checks_paths_runs_every_check(project: Project) -> None:
    project.configure(coder=CODER, settings=components(project))
    project.dk("add", "auth/a.txt Makefile shared/b.txt", "--spec", "a")

    project.dk("run")

    assert ran(project) == ["auth", "login"]
    shown = project.dk("show", "1")
    assert "checks: all of them, as no check's paths hold Makefile, shared/b.txt" in shown


def test_a_ticket_that_changed_only_documents_runs_no_check_with_paths(project: Project) -> None:
    project.configure(coder=CODER, settings=components(project))
    project.dk("add", "docs/notes.md", "--spec", "a")

    project.dk("run")

    assert ran(project) == [] and "#1 done" in project.dk("status")
    assert "checks: unit; left out, nothing of theirs changed: auth, login" in project.dk(
        "show", "1"
    )


def test_work_merged_meanwhile_does_not_add_the_checks_of_other_tickets(project: Project) -> None:
    """The second to merge is checked again with what the first brought, by its own checks."""
    project.configure(coder=CODER, coders=2, settings=components(project))
    project.dk("add", "auth/a.txt", "--spec", "a")
    project.dk("add", "login/b.txt", "--spec", "b")

    project.dk("run")

    assert project.merged("auth/a.txt") and project.merged("login/b.txt")
    noted = sorted(ran(project))
    assert noted in (["auth", "auth", "login"], ["auth", "login", "login"])
    histories = project.dk("show", "1") + project.dk("show", "2")
    assert "left out, nothing of theirs changed: login" in histories
    assert "left out, nothing of theirs changed: auth" in histories
    assert "checks: all" not in histories


def test_behaviour_tests_go_to_the_runner_of_their_component(project: Project) -> None:
    runners = _check(project, "checks.behaviour", "auth", "{features}") + _check(
        project, "checks.behaviour", "login", "{features}"
    )
    project.configure(coder=CODER, tester=TESTER, settings=runners)
    project.dk("add", "auth/a.txt", "--spec", "a")
    project.dk("run")
    project.dk("approve", "1")

    project.dk("run")

    assert ran(project) == ["auth auth/features/it.feature"]
    shown = project.dk("show", "1")
    assert "#1 done" in project.dk("status")
    assert "checks: unit, behaviour auth; left out, nothing of theirs changed: behaviour login" in (
        shown
    )


def test_a_behaviour_test_of_no_runner_goes_to_them_all(project: Project) -> None:
    runners = _check(project, "checks.behaviour", "auth", "{features}") + _check(
        project, "checks.behaviour", "login", "{features}"
    )
    project.configure(coder=CODER, tester=TESTER, settings=runners)
    project.dk("add", "auth/a.txt shared/b.txt", "--spec", "a")
    project.dk("run")
    project.dk("approve", "1")

    project.dk("run")

    assert ran(project) == [
        "auth auth/features/it.feature shared/features/it.feature",
        "login shared/features/it.feature",
    ]


def test_a_project_whose_checks_name_no_paths_is_told_nothing_new(project: Project) -> None:
    project.configure(coder=CODER)
    project.dk("add", "auth/a.txt", "--spec", "a")

    project.dk("run")

    assert "checks:" not in project.dk("show", "1")


def test_a_check_is_given_only_its_command_and_its_paths(project: Project) -> None:
    """`cwd` was asked for and left out: it must not look as if it were heeded."""
    project.configure(coder=CODER, settings='[checks.auth]\nrun = ["true"]\ncwd = "auth"\n')

    refused = project.refused("run")

    assert "check 'auth'" in refused and "`run` and `paths`" in refused and "cwd" in refused


def test_a_check_with_paths_needs_its_command(project: Project) -> None:
    project.configure(coder=CODER, settings='[checks.auth]\npaths = ["auth/**"]\n')

    assert "check 'auth' has no `run`" in project.refused("run")
