"""The user may trust an epic: the behaviour tests of its tickets go on to the coder once
a verifier has approved them, without waiting for the user."""

from __future__ import annotations

import pytest
from conftest import Project, Site
from test_page_orders import order

HELLO = "pathlib.Path('greeting.txt').write_text('hello\\n')\nprint('RESULT: done')"
TESTER = (
    "pathlib.Path('features').mkdir(exist_ok=True)\n"
    "pathlib.Path('features/greet.feature').write_text('Feature: Greeting\\n')\n"
    "print('RESULT: done')"
)
APPROVES = "print('RESULT: approved')"


def written(project: Project, epic: str = "Manners", **others: str) -> None:
    """A ticket of an epic, in a project whose verifier approves everything."""
    project.configure(coder=HELLO, tester=TESTER, **{"verifier": APPROVES, **others})
    project.dk("add", "Greet", "--spec", "Say hello.", "--epic", epic)


def test_a_ticket_of_a_trusted_epic_is_built_without_waiting_for_the_user(
    project: Project,
) -> None:
    written(project)

    said = project.dk("trust", "Manners")
    project.dk("run")

    assert "Manners" in said and "without your approval" in said
    assert "#1 done" in project.dk("status")
    assert project.merged("greeting.txt") == "hello\n"
    assert project.merged("features/greet.feature") == "Feature: Greeting\n"
    shown = project.dk("show", "1")
    assert "behaviour tests approved by a verifier alone: the user trusts Manners" in shown


def test_a_ticket_of_another_epic_still_waits_for_the_user(project: Project) -> None:
    written(project, epic="Gestures")
    project.dk("add", "Bow", "--spec", "Bow.", "--epic", "Manners")
    project.dk("trust", "Manners")

    project.dk("run")

    status = project.dk("status")
    assert "#1 stopped at approve" in status and "#2 done" in status


def test_without_a_verifier_a_trusted_epic_still_waits_for_the_user(project: Project) -> None:
    """Nobody would have read the behaviour tests before they were built."""
    project.configure(coder=HELLO, tester=TESTER)
    project.dk("add", "Greet", "--spec", "Say hello.", "--epic", "Manners")
    project.dk("trust", "Manners")

    project.dk("run")

    assert "#1 stopped at approve" in project.dk("status")
    assert "no verifier" in project.dk("show", "1")


def test_tickets_already_waiting_go_on_once_their_epic_is_trusted(project: Project) -> None:
    written(project)
    project.dk("run")
    waiting = project.dk("status")

    project.dk("trust", "Manners")
    project.dk("run")

    assert "#1 stopped at approve" in waiting
    assert "#1 done" in project.dk("status")


def test_trust_is_withdrawn(project: Project) -> None:
    written(project)
    project.dk("trust", "Manners")

    said = project.dk("trust", "Manners", "--withdraw")
    project.dk("run")

    assert "wait for your approval" in said
    assert "#1 stopped at approve" in project.dk("status")
    assert project.dk("trust") == "no epic is trusted\n"


def test_the_trusted_epics_are_listed(project: Project) -> None:
    written(project)
    project.dk("trust", "Manners")

    assert project.dk("trust") == "Manners\n"


def test_no_agent_can_trust_an_epic(project: Project, monkeypatch: pytest.MonkeyPatch) -> None:
    written(project, principal="pass")
    monkeypatch.setenv("DK_AGENT", "principal-1")

    assert "only the user" in project.refused("trust", "Manners")
    monkeypatch.delenv("DK_AGENT")
    assert project.dk("trust") == "no epic is trusted\n"


def test_an_epic_that_is_not_there_is_not_trusted(project: Project) -> None:
    written(project)

    assert "there is no epic 'Maners'" in project.refused("trust", "Maners")


def test_an_epic_is_trusted_from_the_page_and_shown_as_such(project: Project, site: Site) -> None:
    written(project)
    before = site("/api/board")["epics"][0]["trusted"]

    status, answer = order(project, do="trust", epic="Manners")
    project.dk("run")

    assert (before, status) == (False, 200) and "without your approval" in answer["said"]
    assert site("/api/board")["epics"][0]["trusted"] is True
    assert "#1 done" in project.dk("status")
    assert 'do: "trust"' in site("/page.js")


def test_trust_is_withdrawn_from_the_page(project: Project, site: Site) -> None:
    written(project)
    project.dk("trust", "Manners")

    status, answer = order(project, do="trust", epic="Manners", given=False)

    assert status == 200 and "wait for your approval again" in answer["said"]
    assert site("/api/board")["epics"][0]["trusted"] is False


def test_trust_is_not_given_from_the_page_without_the_key(project: Project, site: Site) -> None:
    written(project)

    status, _ = order(project, key="not-the-key", do="trust", epic="Manners")

    assert status == 403 and project.dk("trust") == "no epic is trusted\n"
