"""An agent that finds work nobody asked for proposes a ticket; it waits for the user, who
alone accepts it or turns it down."""

from __future__ import annotations

import pytest
from conftest import Project

HELLO = "pathlib.Path('greeting.txt').write_text('hello\\n')\nprint('RESULT: done')"


def proposed(project: Project, *more: str) -> str:
    project.configure(coder=HELLO)
    return project.dk("propose", "Greet", "--spec", "Say hello.", "--epic", "Manners", *more)


def test_a_proposed_ticket_is_listed_and_not_worked_on(project: Project) -> None:
    said = proposed(project)

    project.dk("run")

    assert "#1 proposed" in said and "waits for the user" in said
    assert project.dk("status").splitlines() == ["Manners", "  #1 proposed  Greet"]
    assert project.merged("greeting.txt") is None


def test_the_user_accepts_a_proposal_and_it_becomes_a_ticket_like_any_other(
    project: Project,
) -> None:
    proposed(project)

    said = project.dk("approve", "1")
    project.dk("run")

    assert "#1 accepted" in said
    assert project.merged("greeting.txt") == "hello\n"
    assert "accepted by the user" in project.dk("show", "1")


def test_a_proposal_can_be_accepted_as_one_that_needs_no_behaviour_tests(project: Project) -> None:
    tester = "print('RESULT: blocked: nothing a user can see')"
    project.configure(coder=HELLO, tester=tester)
    project.dk("propose", "Greet", "--spec", "Say hello.", "--epic", "Manners")

    project.dk("approve", "1", "--no-behaviour-tests")
    project.dk("run")

    assert "#1 done" in project.dk("status")
    assert "no behaviour tests" in project.dk("show", "1")


def test_only_a_proposal_is_accepted_without_behaviour_tests(project: Project) -> None:
    project.configure(coder="print('RESULT: question: which?')")
    project.dk("add", "Greet", "--spec", "Say hello.")
    project.dk("run")

    assert "#1 is not a proposal" in project.refused("approve", "1", "--no-behaviour-tests")


def test_the_user_turns_a_proposal_down_with_the_reason(project: Project) -> None:
    proposed(project)

    said = project.dk("reject", "1", "--note", "not worth it")
    project.dk("run")

    assert "#1 turned down" in said
    assert "#1 cancelled" in project.dk("status")
    assert "turned down by the user: not worth it" in project.dk("show", "1")
    assert project.merged("greeting.txt") is None


def test_no_agent_can_accept_a_proposal_and_it_says_who_made_it(
    project: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    project.configure(coder=HELLO)
    monkeypatch.setenv("DK_AGENT", "auditor-1")

    project.dk("propose", "Greet", "--spec", "Say hello.", "--epic", "Manners")

    assert "only the user" in project.refused("approve", "1")
    assert "only the user" in project.refused("reject", "1", "--note", "no")
    assert "proposed by auditor-1" in project.dk("show", "1")
    assert project.dk("status").splitlines() == ["Manners", "  #1 proposed  Greet"]


def test_a_closed_epic_takes_no_proposals(project: Project) -> None:
    project.configure(coder=HELLO)
    project.dk("add", "Log in", "--spec", "a", "--epic", "Accounts")
    project.dk("run")
    project.dk("close", "Accounts")

    refused = project.refused("propose", "Log out", "--spec", "b", "--epic", "Accounts")

    assert "epic 'Accounts' is closed" in refused


def test_the_board_shows_a_proposal_as_waiting_for_the_user(project: Project) -> None:
    from dk import config, views
    from dk.tickets import Tickets

    proposed(project)
    tickets = Tickets(project.root / ".devkit" / "tickets.db")

    views.board(config.load(project.root).agents, tickets.all())

    assert "\033[33m  #1 proposed  Greet\033[0m" in project._capsys.readouterr().out


def test_the_principal_is_told_that_proposals_are_the_users_to_accept(project: Project) -> None:
    project.configure(coder=HELLO, principal="pathlib.Path('brief.txt').write_text(prompt)")

    project.dk("talk")

    brief = (project.root / "brief.txt").read_text()
    assert "proposed" in brief and "only the user" in brief
    assert len(brief.split()) < 450
