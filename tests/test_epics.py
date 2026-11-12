"""Tickets can belong to an epic, the larger piece of work they were split from."""

from __future__ import annotations

from conftest import Project


def test_the_status_groups_tickets_under_their_epic(project: Project) -> None:
    project.dk("add", "Log in", "--spec", "a", "--epic", "Accounts")
    project.dk("add", "Fix typo", "--spec", "b")
    project.dk("add", "Log out", "--spec", "c", "--epic", "Accounts")

    lines = project.dk("status").splitlines()

    assert lines == [
        "#2 specify  Fix typo",
        "Accounts",
        "  #1 specify  Log in",
        "  #3 specify  Log out",
    ]


def test_a_ticket_shows_its_epic(project: Project) -> None:
    project.dk("add", "Log in", "--spec", "a", "--epic", "Accounts")

    assert "Epic: Accounts" in project.dk("show", "1")
