"""A ticket nobody has worked on yet can be rewritten, by the user or the Principal: one an
agent proposed, or one that has not started."""

from __future__ import annotations

import sys

import pytest
from conftest import Project, Site
from test_page_orders import order
from test_talk import PRINCIPAL, notes

HELLO = "pathlib.Path('greeting.txt').write_text('hello\\n')\nprint('RESULT: done')"
TESTER = (
    "pathlib.Path('features').mkdir(exist_ok=True)\n"
    "pathlib.Path('features/greet.feature').write_text('Feature: Greeting\\n')\n"
    "print('RESULT: done')"
)


def proposed(project: Project) -> None:
    project.configure(coder=HELLO, principal="pass")
    project.dk("propose", "Greet", "--spec", "Say hello.", "--epic", "Manners")


def test_a_proposed_ticket_is_rewritten(project: Project) -> None:
    proposed(project)

    said = project.dk("edit", "1", "--title", "Greet politely", "--spec", "Say good morning.")

    shown = project.dk("show", "1")
    assert "#1 edited" in said
    assert "#1 proposed  Greet politely" in shown and "\nSay good morning.\n" in shown
    assert "edited by the user; it said: Greet: Say hello." in shown


def test_the_title_alone_is_changed(project: Project) -> None:
    proposed(project)

    project.dk("edit", "1", "--title", "Greet politely")

    shown = project.dk("show", "1")
    assert "#1 proposed  Greet politely" in shown and "\nSay hello.\n" in shown


def test_the_user_rewrites_a_ticket_in_their_own_editor(
    project: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    proposed(project)
    editor = project.root.parent / "editor.py"
    editor.write_text(
        "import pathlib, sys\n"
        "file = pathlib.Path(sys.argv[-1])\n"
        "assert file.read_text() == 'Greet\\n\\nSay hello.\\n', file.read_text()\n"
        "file.write_text('Greet politely\\n\\nSay good morning.\\nAnd bow.\\n')\n"
    )
    monkeypatch.setenv("EDITOR", f"{sys.executable} {editor}")
    monkeypatch.delenv("VISUAL", raising=False)

    project.dk("edit", "1")

    shown = project.dk("show", "1")
    assert "#1 proposed  Greet politely" in shown and "Say good morning.\nAnd bow.\n" in shown


def test_a_ticket_that_has_not_started_is_rewritten_and_built_as_it_now_says(
    project: Project,
) -> None:
    says = "pathlib.Path('said.txt').write_text(prompt)\nprint('RESULT: done')"
    project.configure(coder=says)
    project.dk("add", "Greet", "--spec", "Say hello.", "--epic", "Manners")

    project.dk("edit", "1", "--spec", "Say good morning.")
    project.dk("run")

    told = project.merged("said.txt") or ""
    assert "Say good morning." in told and "Say hello." not in told


def test_a_ticket_somebody_has_worked_on_is_not_rewritten(project: Project) -> None:
    project.configure(coder=HELLO, tester=TESTER)
    project.dk("add", "Greet", "--spec", "Say hello.", "--epic", "Manners")
    project.dk("run")

    refused = project.refused("edit", "1", "--spec", "Say good morning.")

    assert "#1 has been worked on" in refused and "dk retry 1 --note" in refused
    assert "Say good morning." not in project.dk("show", "1")


def test_a_ticket_whose_first_agent_asked_something_is_not_rewritten(project: Project) -> None:
    """It stopped with no attempt counted and nobody at work on it: it has been read."""
    project.configure(coder=HELLO, tester="print('RESULT: question: in which language?')")
    project.dk("add", "Greet", "--spec", "Say hello.", "--epic", "Manners")
    project.dk("run")
    assert "#1 stopped at specify  Greet  question" in project.dk("status")

    assert "#1 has been worked on" in project.refused("edit", "1", "--spec", "Say good morning.")


def test_a_ticket_its_first_agent_is_at_work_on_is_not_rewritten(project: Project) -> None:
    slow = "import time; time.sleep(1)\n" + TESTER
    talk = PRINCIPAL + (
        "dk('add', 'Greet', '--spec', spec('Say hello.'), '--behaviour-tests')\n"
        "wait_for('tester-1 started')\n"
        "notes.write_text(str(dk('edit', '1', '--spec', spec('Say good morning.'))))\n"
    )
    project.configure(coder=HELLO, tester=slow, principal=talk)

    project.dk("talk")

    assert notes(project).startswith("(1,") and "Say good morning." not in project.dk("show", "1")


def test_a_finished_ticket_is_not_rewritten(project: Project) -> None:
    project.configure(coder=HELLO)
    project.dk("add", "Greet", "--spec", "Say hello.", "--epic", "Manners")
    project.dk("run")

    assert "#1 has been worked on" in project.refused("edit", "1", "--title", "Bow")


def test_the_principal_rewrites_a_ticket_under_its_three_headings(
    project: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    proposed(project)
    monkeypatch.setenv("DK_AGENT", "principal-1")

    refused = project.refused("edit", "1", "--spec", "Say good morning.")
    project.dk(
        *("edit", "1", "--spec"),
        "Wanted: a good morning. Acceptance criteria: - it is said. Out of scope: bows.",
    )

    shown = project.dk("show", "1")
    assert "Wanted: ..." in refused
    assert "Wanted:\na good morning." in shown and "edited by principal-1" in shown
    assert "--spec" in project.refused("edit", "1"), "no editor is opened for an agent"


def test_no_other_agent_rewrites_a_ticket(
    project: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    proposed(project)
    monkeypatch.setenv("DK_AGENT", "coder-1")

    refused = project.refused("edit", "1", "--spec", "Say nothing.")

    assert "only the user or the Principal" in refused


def test_a_ticket_is_rewritten_from_the_page(project: Project, site: Site) -> None:
    proposed(project)
    before = site("/api/ticket/1")["editable"]

    status, answer = order(project, do="edit", ticket=1, title="Bow", spec="Bow low.")

    after = site("/api/ticket/1")
    assert (before, status, answer) == (True, 200, {"said": "#1 edited"})
    assert (after["title"], after["spec"]) == ("Bow", "Bow low.")
    assert 'do: "edit"' in site("/ticket.js")


def test_the_page_says_which_tickets_cannot_be_rewritten(project: Project, site: Site) -> None:
    project.configure(coder=HELLO)
    project.dk("add", "Greet", "--spec", "Say hello.", "--epic", "Manners")
    project.dk("run")

    assert site("/api/ticket/1")["editable"] is False
