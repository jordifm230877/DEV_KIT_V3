"""A proposal is put in an epic, or taken out of one, before the user decides on it; it is
accepted only inside an epic."""

from __future__ import annotations

import pytest
from conftest import Project

HELLO = "pathlib.Path('greeting.txt').write_text('hello\\n')\nprint('RESULT: done')"
SPEC = "Goal: be polite. Includes: greetings. Excludes: farewells."


def proposed(project: Project, *more: str) -> None:
    project.configure(coder=HELLO, principal="pass")
    project.dk("propose", "Greet", "--spec", "Say hello.", *more)


def test_a_proposal_is_moved_into_an_epic(project: Project) -> None:
    proposed(project)

    said = project.dk("move", "1", "--epic", "Manners")

    assert "#1 moved to Manners" in said
    assert project.dk("status").splitlines() == ["Manners", "  #1 proposed  Greet"]
    assert "moved to Manners by the user" in project.dk("show", "1")


def test_a_proposal_is_moved_out_of_its_epic(project: Project) -> None:
    proposed(project, "--epic", "Manners")

    said = project.dk("move", "1", "--no-epic")

    assert "#1 moved out of Manners" in said
    assert project.dk("status") == "#1 proposed  Greet\n"


def test_only_a_proposal_is_moved(project: Project) -> None:
    project.configure(coder=HELLO)
    project.dk("add", "Greet", "--spec", "Say hello.", "--epic", "Manners")

    assert "#1 is not a proposal" in project.refused("move", "1", "--epic", "Polish")
    assert "Epic: Manners" in project.dk("show", "1")


def test_a_proposal_is_not_moved_into_a_closed_epic(project: Project) -> None:
    project.configure(coder=HELLO)
    project.dk("add", "Log in", "--spec", "a", "--epic", "Accounts")
    project.dk("run")
    project.dk("close", "Accounts")
    project.dk("propose", "Log out", "--spec", "b")

    assert "epic 'Accounts' is closed" in project.refused("move", "2", "--epic", "Accounts")


def test_the_principal_moves_a_proposal_and_no_other_agent_does(
    project: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    proposed(project)
    monkeypatch.setenv("DK_AGENT", "coder-1")

    refused = project.refused("move", "1", "--epic", "Manners")

    monkeypatch.setenv("DK_AGENT", "principal-1")
    undescribed = project.refused("move", "1", "--epic", "Manners")
    project.dk("epic", "Manners", "--spec", SPEC)
    project.dk("move", "1", "--epic", "Manners")
    assert "only the user or the Principal" in refused
    assert "say first what the epic is for" in undescribed
    assert "moved to Manners by principal-1" in project.dk("show", "1")


def test_a_proposal_outside_every_epic_is_not_accepted(project: Project) -> None:
    proposed(project)

    refused = project.refused("approve", "1")
    project.dk("move", "1", "--epic", "Manners")
    project.dk("approve", "1")
    project.dk("run")

    assert 'dk move 1 --epic "NAME"' in refused
    assert project.merged("greeting.txt") == "hello\n"


def test_a_proposal_outside_every_epic_can_still_be_turned_down(project: Project) -> None:
    proposed(project)

    project.dk("reject", "1", "--note", "not worth it")

    assert "#1 cancelled" in project.dk("status")


def test_the_principal_is_told_how_to_move_a_proposal(project: Project) -> None:
    project.configure(coder=HELLO, principal="pathlib.Path('brief.txt').write_text(prompt)")

    project.dk("talk")

    brief = (project.root / "brief.txt").read_text()
    assert "move NUMBER" in brief and "inside an epic" in brief
    assert len(brief.split()) < 500


def test_a_ticket_is_written_only_in_an_epic(project: Project) -> None:
    project.configure(coder=HELLO)

    refused = project.refused("add", "Greet", "--spec", "Say hello.")

    assert '--epic "NAME"' in refused and "dk propose" in refused
    assert project.dk("status") == ""
