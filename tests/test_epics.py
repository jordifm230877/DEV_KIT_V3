"""Tickets can belong to an epic, the larger piece of work they were split from."""

from __future__ import annotations

from conftest import Project


def test_the_status_groups_tickets_under_their_epic(project: Project) -> None:
    project.dk("add", "Log in", "--spec", "a", "--epic", "Accounts")
    project.dk("add", "Fix typo", "--spec", "b")
    project.dk("add", "Log out", "--spec", "c", "--epic", "Accounts")

    lines = project.dk("status").splitlines()

    assert lines == [
        "#2 examine  Fix typo",
        "Accounts",
        "  #1 examine  Log in",
        "  #3 examine  Log out",
    ]


def test_a_ticket_shows_its_epic(project: Project) -> None:
    project.dk("add", "Log in", "--spec", "a", "--epic", "Accounts")

    assert "Epic: Accounts" in project.dk("show", "1")


HELLO = "pathlib.Path('greeting.txt').write_text('hello\\n')\nprint('RESULT: done')"


def finished_epic(project: Project) -> None:
    """An epic with one ticket merged and one given up, and a ticket outside it."""
    project.configure(coder=HELLO)
    project.dk("add", "Log in", "--spec", "a", "--epic", "Accounts")
    project.dk("run")
    project.dk("add", "Log out", "--spec", "c", "--epic", "Accounts")
    project.dk("cancel", "2")
    project.dk("add", "Fix typo", "--spec", "b", "--epic", "Polish")


def test_a_finished_epic_can_be_closed_and_then_takes_one_line(project: Project) -> None:
    finished_epic(project)

    said = project.dk("close", "Accounts")

    assert "Accounts" in said and "closed" in said
    assert project.dk("status").splitlines() == [
        "Accounts  closed: 1 done, 1 cancelled",
        "Polish",
        "  #3 examine  Fix typo",
    ]
    assert "Epic: Accounts" in project.dk("show", "1"), "its tickets can still be read"


def test_an_epic_with_unfinished_tickets_cannot_be_closed(project: Project) -> None:
    finished_epic(project)

    assert "#3 is not finished" in project.refused("close", "Polish")
    assert "closed" not in project.dk("status")


def test_only_an_epic_that_exists_can_be_closed(project: Project) -> None:
    finished_epic(project)

    assert "there is no epic 'Acounts'" in project.refused("close", "Acounts")


def test_a_closed_epic_takes_no_more_tickets(project: Project) -> None:
    finished_epic(project)
    project.dk("close", "Accounts")

    refused = project.refused("add", "Reset password", "--spec", "d", "--epic", "Accounts")

    assert "epic 'Accounts' is closed" in refused
    assert "Reset password" not in project.dk("status")


def test_a_closed_epic_can_be_opened_again(project: Project) -> None:
    finished_epic(project)
    project.dk("close", "Accounts")

    said = project.dk("reopen", "Accounts")

    assert "Accounts" in said and "open" in said
    assert "closed" not in project.dk("status")
    project.dk("add", "Reset password", "--spec", "d", "--epic", "Accounts")
    assert "Reset password" in project.dk("status")


def test_only_a_closed_epic_can_be_opened_again(project: Project) -> None:
    finished_epic(project)

    assert "epic 'Polish' is not closed" in project.refused("reopen", "Polish")
