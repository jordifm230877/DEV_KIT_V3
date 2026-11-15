"""`dk web`: the agents, the epics, the tickets and their behaviour tests in a browser."""

from __future__ import annotations

import json
import socket
from urllib.error import HTTPError

import pytest
from conftest import Project, Site
from test_behaviour_tests import APPROVED_TEXT, HELLO, TESTER

# A coder that, in the middle of its job, asks the site what the user's browser would.
LOOKS = """
from urllib.request import urlopen
here = pathlib.Path(sys.argv[0]).parent
with urlopen((here / "site.txt").read_text() + "api/board") as answer:
    (here / "board.json").write_bytes(answer.read())
pathlib.Path('greeting.txt').write_text('hello\\n')
print('RESULT: done')
"""


def refused(site: Site, path: str) -> tuple[int, str]:
    with pytest.raises(HTTPError) as error:
        site(path)
    return error.value.code, error.value.read().decode()


def test_the_board_lists_the_agents_and_the_tickets_of_each_epic(
    project: Project, site: Site
) -> None:
    project.configure(coder=HELLO, verifier="print('RESULT: approved')")
    project.dk("add", "Sign in", "--spec", "a", "--epic", "Access")
    project.dk("add", "Sign out", "--spec", "b", "--epic", "Access", "--after", "1")
    project.dk("add", "List items", "--spec", "c", "--epic", "Vault", "--after", "2")
    project.dk("add", "Tidy", "--spec", "d")

    board = site("/api/board")

    assert board["agents"] == [
        {"name": "coder-1", "role": "coder", "ticket": None, "since": "", "spent": ""},
        {"name": "verifier-1", "role": "verifier", "ticket": None, "since": "", "spent": ""},
    ]
    loose, access, vault = board["epics"]
    assert [epic["name"] for epic in board["epics"]] == ["", "Access", "Vault"]
    assert [ticket["id"] for ticket in access["tickets"]] == [1, 2]
    assert [ticket["title"] for ticket in loose["tickets"]] == ["Tidy"]
    first, second = access["tickets"]
    assert (first["kind"], first["step"], first["waits"]) == ("ticket", "examine", [])
    assert (second["kind"], second["follows"], second["waits"]) == ("held", [1], [1])
    assert (access["follows"], vault["follows"]) == ([], ["Access"])
    assert (access["done"], access["closed"]) == (0, False)


def test_the_board_has_what_each_epic_is_for(project: Project, site: Site) -> None:
    project.configure(coder=HELLO)
    project.dk("epic", "Access", "--spec", "Goal: people get in.")
    project.dk("add", "Sign in", "--spec", "a", "--epic", "Access")
    project.dk("add", "Tidy", "--spec", "d")

    loose, access = site("/api/board")["epics"]

    assert (loose["description"], access["description"]) == ("", "Goal: people get in.")


def test_the_board_says_what_is_finished_and_which_epics_are_closed(
    project: Project, site: Site
) -> None:
    project.configure(coder=HELLO)
    project.dk("add", "Greet", "--spec", "a", "--epic", "Access")
    project.dk("add", "Never", "--spec", "b", "--epic", "Access")
    project.dk("cancel", "2")
    project.dk("run")
    project.dk("close", "Access")

    (access,) = site("/api/board")["epics"]

    assert [ticket["kind"] for ticket in access["tickets"]] == ["done", "cancelled"]
    assert (access["done"], access["closed"]) == (1, True)
    assert access["tickets"][1]["waits"] == []


def test_the_board_says_which_agent_is_on_which_ticket(project: Project, site: Site) -> None:
    project.configure(coder=LOOKS)
    project.dk("add", "Greet", "--spec", "Say hello.")

    project.dk("run")

    seen = json.loads((project.root.parent / "tools" / "board.json").read_text())
    (coder,) = seen["agents"]
    assert (coder["name"], coder["ticket"]) == ("coder-1", 1) and coder["since"]
    assert seen["epics"][0]["tickets"][0]["worker"] == "coder-1"
    assert site("/api/board")["agents"][0]["ticket"] is None


def test_the_board_says_why_a_ticket_stopped(project: Project, site: Site) -> None:
    project.configure(coder="print('RESULT: question: which language?')")
    project.dk("add", "Vague", "--spec", "Do the thing.")
    project.dk("run")

    (ticket,) = site("/api/board")["epics"][0]["tickets"]

    assert (ticket["kind"], ticket["note"]) == ("stopped", "question: which language?")


def test_a_tickets_page_has_what_was_asked_what_happened_and_its_behaviour_tests(
    project: Project, site: Site
) -> None:
    project.configure(coder=HELLO, tester=TESTER)
    project.dk("add", "Greet", "--spec", "Say hello.", "--epic", "Access")
    project.dk("run")

    ticket = site("/api/ticket/1")

    assert (ticket["title"], ticket["spec"], ticket["epic"]) == ("Greet", "Say hello.", "Access")
    assert (ticket["kind"], ticket["approval"]) == ("stopped", True)
    assert any("tester-1 started" in line for line in ticket["history"])
    assert ticket["tests"] == [{"name": "features/greet.feature", "text": APPROVED_TEXT}]


def test_the_behaviour_tests_of_a_merged_ticket_can_still_be_read(
    project: Project, site: Site
) -> None:
    project.configure(coder=HELLO, tester=TESTER)
    project.dk("add", "Greet", "--spec", "Say hello.")
    project.dk("run")
    project.dk("approve", "1")
    project.dk("run")

    ticket = site("/api/ticket/1")

    assert (ticket["kind"], ticket["approval"]) == ("done", False)
    assert ticket["tests"] == [{"name": "features/greet.feature", "text": APPROVED_TEXT}]


def test_asking_for_what_is_not_there_says_so(project: Project, site: Site) -> None:
    project.configure(coder=HELLO)

    assert refused(site, "/api/ticket/7") == (404, '{"error": "there is no ticket #7"}')
    assert refused(site, "/api/nothing")[0] == 404
    assert refused(site, "/nothing.html")[0] == 404
    assert refused(site, "/../devkit.toml")[0] == 404


def test_the_page_and_its_parts_are_served(project: Project, site: Site) -> None:
    project.configure(coder=HELLO)

    page = site("/")

    assert "<title>DevKit</title>" in page
    assert "api/" in site("/page.js") and "body" in site("/page.css")


def test_the_site_answers_other_computers_of_the_network(project: Project, site: Site) -> None:
    """The user looks at the board from another computer; it answered only its own."""
    project.configure(coder=HELLO)
    address = (project.root.parent / "tools" / "site.txt").read_text()
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        probe.connect(("192.0.2.1", 9))  # sends nothing; says which address reaches outside
        mine = probe.getsockname()[0]

    assert address.startswith(f"http://{mine}:"), "the address it gives is one others can use"
    assert site("/api/board")["agents"][0]["name"] == "coder-1"
