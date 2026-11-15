"""What agents write has a fixed form: a ticket and an epic each say three things, under
headings that are always the same. The user, typing by hand, writes as they like."""

from __future__ import annotations

import pytest
from conftest import Project
from test_behaviour_tests import HELLO
from test_examine import KEEPS

TICKET = "Wanted: a greeting. Acceptance criteria: - it says hello. Out of scope: goodbyes."
EPIC = "Goal: polite software. Includes: greetings. Excludes: small talk."
LAID_OUT = "Goal:\npolite software.\n\nIncludes:\ngreetings.\n\nExcludes:\nsmall talk."


@pytest.fixture
def agent(project: Project, monkeypatch: pytest.MonkeyPatch) -> None:
    """What follows is typed by an agent, as the Principal does in the conversation."""
    project.configure(coder=HELLO)
    monkeypatch.setenv("DK_AGENT", "principal")


@pytest.mark.usefixtures("agent")
def test_a_ticket_an_agent_writes_is_laid_out_under_its_three_headings(project: Project) -> None:
    project.dk("add", "Greet", "--spec", TICKET)

    shown = project.dk("show", "1")

    laid_out = "Wanted:\na greeting.\n\nAcceptance criteria:\n- it says hello.\n\nOut of scope:\n"
    assert laid_out + "goodbyes.\n" in shown


@pytest.mark.usefixtures("agent")
@pytest.mark.parametrize(
    "spec",
    [
        "Say hello.",
        "Wanted: a greeting. Out of scope: goodbyes.",
        "Wanted: a greeting. Acceptance criteria: Out of scope: goodbyes.",
        "Acceptance criteria: it says hello. Wanted: a greeting. Out of scope: goodbyes.",
        "First of all. " + TICKET,
        TICKET + " Wanted: and more.",
    ],
)
def test_an_agent_is_refused_a_ticket_that_lacks_a_part(project: Project, spec: str) -> None:
    said = project.refused("add", "Greet", "--spec", spec)

    assert "Wanted: ... Acceptance criteria: ... Out of scope: ..." in said
    assert project.dk("status") == ""


def test_the_user_writes_a_ticket_as_they_like(project: Project) -> None:
    project.configure(coder=HELLO)

    project.dk("add", "Greet", "--spec", "Say hello.", "--epic", "Manners")

    assert "Say hello." in project.dk("show", "1")


@pytest.mark.usefixtures("agent")
def test_an_epic_is_described_and_the_description_can_be_read_and_replaced(
    project: Project,
) -> None:
    assert "Manners described" in project.dk("epic", "Manners", "--spec", EPIC)
    assert project.dk("epic", "Manners") == LAID_OUT + "\n"

    project.dk("epic", "Manners", "--spec", EPIC.replace("small talk", "jokes"))

    assert project.dk("epic", "Manners") == LAID_OUT.replace("small talk", "jokes") + "\n"
    assert "has no description" in project.refused("epic", "Other")


@pytest.mark.usefixtures("agent")
def test_an_agent_is_refused_an_epic_that_lacks_a_part(project: Project) -> None:
    said = project.refused("epic", "Manners", "--spec", "Goal: polite software.")

    assert "Goal: ... Includes: ... Excludes: ..." in said
    assert "has no description" in project.refused("epic", "Manners")


@pytest.mark.usefixtures("agent")
def test_an_agent_describes_an_epic_before_it_writes_tickets_for_it(project: Project) -> None:
    said = project.refused("add", "Greet", "--spec", TICKET, "--epic", "Manners")
    assert 'epic "Manners" --spec' in said and "Goal: ... Includes: ... Excludes: ..." in said

    project.dk("epic", "Manners", "--spec", EPIC)

    assert "#1 written" in project.dk("add", "Greet", "--spec", TICKET, "--epic", "Manners")


def test_the_examiner_is_told_what_the_tickets_epic_is_for(project: Project) -> None:
    project.configure(coder=HELLO, examiner=KEEPS)
    project.dk("epic", "Manners", "--spec", EPIC)
    project.dk("add", "Greet", "--spec", "Say hello.", "--epic", "Manners")
    project.dk("add", "Tidy", "--spec", "Sweep.")

    project.dk("run")

    seen = (project.root.parent / "tools" / "seen.txt").read_text()
    assert "Sweep." in seen and "epic" not in seen.split("Read AGENTS.md")[0]
    project.dk("cancel", "2")
    project.dk("add", "Bow", "--spec", "Bow politely.", "--epic", "Manners")
    project.dk("run")
    seen = (project.root.parent / "tools" / "seen.txt").read_text()
    assert f"Its epic, Manners:\n{EPIC}\n" in seen
