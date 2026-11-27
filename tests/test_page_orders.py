"""From the page of `dk web` the user approves, sends back, answers and gives up, as with the
commands; nobody without the key the user was shown can."""

from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
from conftest import Project, Site
from test_behaviour_tests import HELLO, TESTER

WRONG = "not-the-key"


def order(project: Project, key: str = "", **asked: Any) -> tuple[int, dict[str, str]]:
    """Ask as the page does when the user presses a button; by default with the user's key."""
    tools = project.root.parent / "tools"
    headers = {"X-Key": key or (tools / "key.txt").read_text(), "Content-Type": "application/json"}
    address = (tools / "site.txt").read_text() + "api/order"
    request = Request(address, json.dumps(asked).encode(), headers)
    try:
        with urlopen(request) as answer:
            return answer.status, json.loads(answer.read())
    except HTTPError as error:
        return error.code, json.loads(error.read())


def waiting_for_approval(project: Project) -> None:
    project.configure(coder=HELLO, tester=TESTER)
    project.dk("add", "Greet", "--spec", "Say hello.")
    project.dk("run")


def test_the_user_is_given_a_key_that_nobody_could_guess(project: Project, site: Site) -> None:
    project.configure(coder=HELLO)
    key = (project.root.parent / "tools" / "key.txt").read_text()

    assert len(key) >= 20 and key not in site("/page.js") + json.dumps(site("/api/board"))


def test_behaviour_tests_are_approved_from_the_page(project: Project, site: Site) -> None:
    waiting_for_approval(project)

    status, answer = order(project, do="approve", ticket=1)
    project.dk("run")

    assert (status, answer) == (200, {"said": "#1 will continue at code on the next run"})
    assert project.merged("greeting.txt") == "hello\n"
    assert "approved by the user" in project.dk("show", "1")


def test_behaviour_tests_are_sent_back_from_the_page_with_what_must_change(
    project: Project, site: Site
) -> None:
    waiting_for_approval(project)

    status, answer = order(project, do="reject", ticket=1, note="say good morning")
    project.dk("run")

    assert status == 200 and "continue at specify" in answer["said"]
    assert "rejected by the user: say good morning" in project.dk("show", "1")
    assert "good morning" in site("/api/ticket/1")["tests"][0]["text"]


def test_sending_back_needs_a_note(project: Project, site: Site) -> None:
    waiting_for_approval(project)

    status, answer = order(project, do="reject", ticket=1, note="  ")

    assert status == 400 and "what must change" in answer["error"]
    assert "#1 stopped at approve" in project.dk("status")


def test_a_stopped_ticket_is_answered_from_the_page(project: Project, site: Site) -> None:
    asks = (
        "if 'use blue' in prompt:\n    pathlib.Path('colour.txt').write_text('blue')\n"
        "    print('RESULT: done')\nelse:\n    print('RESULT: question: which colour?')"
    )
    project.configure(coder=asks)
    project.dk("add", "Paint", "--spec", "Paint it.")
    project.dk("run")

    status, answer = order(project, do="retry", ticket=1, note="use blue")
    project.dk("run")

    assert (status, answer) == (200, {"said": "#1 will continue at code on the next run"})
    assert project.merged("colour.txt") == "blue"


def test_a_proposal_is_accepted_or_turned_down_from_the_page(project: Project, site: Site) -> None:
    project.configure(coder=HELLO, tester="print('RESULT: blocked: nothing a user can see')")
    for title in ("Greet", "Wave", "Bow"):
        project.dk("propose", title, "--spec", "Say hello.", "--epic", "Manners")

    accepted = order(project, do="approve", ticket=1)
    plain = order(project, do="approve", ticket=2, tests=False)
    refused = order(project, do="reject", ticket=3, note="not now")
    project.dk("run")

    assert [status for status, _ in (accepted, plain, refused)] == [200, 200, 200]
    assert "#1 accepted" in accepted[1]["said"] and "#3 turned down" in refused[1]["said"]
    status = project.dk("status")
    assert "#1 stopped at specify" in status and "#2 done" in status and "#3 cancelled" in status
    assert "turned down by the user: not now" in project.dk("show", "3")


def test_a_ticket_is_given_up_from_the_page(project: Project, site: Site) -> None:
    project.configure(coder=HELLO)
    project.dk("add", "Greet", "--spec", "Say hello.")

    status, answer = order(project, do="cancel", ticket=1)

    assert status == 200 and "#1 cancelled" in answer["said"]
    assert "#1 cancelled" in project.dk("status")


def test_a_ticket_is_paused_from_the_page_and_sent_on_again(project: Project, site: Site) -> None:
    project.configure(coder=HELLO)
    project.dk("add", "Greet", "--spec", "Say hello.")

    status, answer = order(project, do="pause", ticket=1)
    project.dk("run")

    assert status == 200 and "#1 paused" in answer["said"]
    assert "#1 stopped at specify  Greet  paused by the user" in project.dk("status")
    assert 'do: "pause"' in site("/page.js")

    order(project, do="retry", ticket=1)
    project.dk("run")

    assert "#1 done" in project.dk("status")


@pytest.mark.parametrize("key", [WRONG, " "])
def test_nobody_without_the_key_changes_anything(project: Project, site: Site, key: str) -> None:
    waiting_for_approval(project)

    status, answer = order(project, key, do="approve", ticket=1)

    assert status == 403 and "key" in answer["error"]
    assert "#1 stopped at approve" in project.dk("status")


def test_the_page_is_told_why_an_order_cannot_be_carried_out(project: Project, site: Site) -> None:
    project.configure(coder=HELLO)
    project.dk("add", "Greet", "--spec", "Say hello.")

    refusals = [
        order(project, do="retry", ticket=1, note="go"),
        order(project, do="approve", ticket=7),
        order(project, do="run", ticket=1),
        order(project, do="approve"),
        order(project, do="approve", ticket="one"),
    ]

    assert [status for status, _ in refusals] == [400] * 5
    errors = [answer["error"] for _, answer in refusals]
    assert "#1 is not stopped" in errors[0] and "no ticket #7" in errors[1]
    assert "run" in errors[2] and "ticket" in errors[3]
    assert "#1 specify" in project.dk("status") or "#1 code" in project.dk("status")


def test_what_is_not_an_order_is_refused(project: Project, site: Site) -> None:
    tools = project.root.parent / "tools"
    headers = {"X-Key": (tools / "key.txt").read_text()}
    for path, body in (("api/order", b"not json"), ("api/order", b"[1]"), ("api/board", b"{}")):
        request = Request((tools / "site.txt").read_text() + path, body, headers)
        with pytest.raises(HTTPError) as error:
            urlopen(request)
        assert error.value.code in (400, 404)
