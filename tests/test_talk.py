"""The user talks to the Principal while the work goes on behind the conversation."""

from __future__ import annotations

import time

import pytest
from conftest import Herdr, Project

HELLO = "pathlib.Path('greeting.txt').write_text('hello\\n')\nprint('RESULT: done')"
# A stand-in Principal: it finds the `dk` command in its brief and uses it like a model would.
PRINCIPAL = """
import re, shlex, subprocess, time
DK = shlex.split(re.search(r"`([^`]*-m dk[^`]*)`", prompt).group(1))
notes = pathlib.Path(sys.argv[0]).with_name("principal-notes.txt")

def dk(*args):
    if args[0] == "add" and "--epic" not in args:  # every ticket is written in an epic
        dk("epic", "Work", "--spec", "Goal: g. Includes: i. Excludes: e.")
        args = (*args, "--epic", "Work")
    done = subprocess.run([*DK, *args], capture_output=True, text=True)
    return done.returncode, done.stdout

def spec(wanted):
    return f"Wanted: {wanted} Acceptance criteria: - it is so. Out of scope: the rest."

def wait_for(text, ticket="1"):
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if text in dk("show", ticket)[1]:
            return
        time.sleep(0.05)
    notes.write_text(f"never saw: {text}")
    sys.exit(0)
"""


def notes(project: Project) -> str:
    path = project.root.parent / "tools" / "principal-notes.txt"
    return path.read_text() if path.exists() else ""


def test_a_ticket_the_principal_writes_is_done_while_the_conversation_is_open(
    project: Project,
) -> None:
    talk = PRINCIPAL + (
        "dk('epic', 'Manners', '--spec', 'Goal: g. Includes: i. Excludes: e.')\n"
        "dk('add', 'Greet', '--spec', spec('Say hello.'), '--behaviour-tests',"
        " '--epic', 'Manners')\n"
        "wait_for('#1 done')\n"
        "notes.write_text('saw it done')"
    )
    project.configure(coder=HELLO, principal=talk)

    project.dk("talk")

    assert notes(project) == "saw it done"
    assert project.merged("greeting.txt") == "hello\n"


def test_the_principal_is_told_its_role_and_not_how_the_process_works(project: Project) -> None:
    project.configure(coder=HELLO, principal="pathlib.Path('brief.txt').write_text(prompt)")

    project.dk("talk")

    brief = (project.root / "brief.txt").read_text()
    for word in (
        "add",
        "--after",
        "status",
        "show",
        "retry",
        "cancel",
        "close",
        "reopen",
        'epic "NAME" --spec "Goal: ... Includes: ... Excludes: ..."',
        '--spec "Wanted: ... Acceptance criteria: ... Out of scope: ..."',
        "the epic first",
        "--no-behaviour-tests",
        'retry NUMBER --note "TEXT" [--no-behaviour-tests]',
        "when it stopped for behaviour tests no user would see",
        "audit security|performance",
        'document [--note "FOCUS"]',
    ):
        assert word in brief
    assert "Before closing an epic" in brief and "the user decides" in brief
    # Tickets that listed `cargo test` as a criterion made each reviewer run all of it again.
    assert "never an acceptance criterion" in brief
    # A project begun from nothing has no checks when `dk init` runs, and nobody added them.
    assert "first ticket adds its checks to devkit.toml and AGENTS.md" in brief
    # It passed on a note allowing a coder to change approved tests; the program undid them.
    assert "no note lets its coder change them" in brief
    # It advised `reject` on a ticket for tests a merged ticket had left; there was none to send.
    # Told that only a test-writer changes those, it refused a ticket to delete old scenarios.
    assert "once it is merged, any later ticket may change or remove them" in brief
    # Left to say nothing, it sent work no user sees to the test-writer: 27 scenarios refused.
    assert "--behaviour-tests | --no-behaviour-tests" in brief and "say which" in brief
    assert len(brief.split()) < 450


def test_the_principal_explores_itself_and_keeps_tickets_for_changes(project: Project) -> None:
    project.configure(coder=HELLO, principal="pathlib.Path('brief.txt').write_text(prompt)")

    project.dk("talk")

    brief = (project.root / "brief.txt").read_text()
    assert brief.index("Explore") < brief.index("never tickets") < brief.index("Plan")
    # Told only to read and ask, it proposed two tickets to try things out on a throwaway
    # server, one of them to "record decisions with the user": no coder talks with the user.
    assert "try things out with throwaway scripts and data" in brief
    assert brief.index("Finding out and deciding") < brief.index("never tickets")
    # One file for everything reached 13,500 words that every examiner read for every ticket.
    assert "`docs/decisions.md`" in brief and "rewrite it" in brief
    assert "`docs/discovery/DATE-topic.md`" in brief
    assert "docs/discovery.md` is yours to split" in brief
    # Told only where not to write it, it wrote what it found about one ticket there anyway.
    about_one = brief[brief.index("about one ticket") :]
    assert about_one.index("`retry` note") < about_one.index("docs/discovery.md` is yours")


def test_the_principal_approves_in_the_conversation_where_the_user_tells_it_to(
    project: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The user told it to approve a ticket; it was refused and gave them a command to type."""
    tester = (
        "pathlib.Path('features').mkdir(exist_ok=True)\n"
        "pathlib.Path('features/greet.feature').write_text('Feature: Greeting\\n')\n"
        "print('RESULT: done')"
    )
    talk = PRINCIPAL + (
        "dk('add', 'Greet', '--spec', spec('Say hello.'), '--behaviour-tests')\n"
        "wait_for('stopped at approve')\n"
        "code, said = dk('approve', '1')\n"
        "notes.write_text(f'{code} {said}')"
    )
    project.configure(coder=HELLO, tester=tester, principal=talk)

    project.dk("talk")

    assert notes(project).startswith("0 "), notes(project)
    assert "#1 stopped at approve" not in project.dk("status")
    shown = project.dk("show", "1")
    assert "approved by the user" in shown and "in the conversation, on the user's word" in shown
    # Outside the conversation the user is not there: a Principal on a job decides nothing.
    project.dk("add", "Bow", "--spec", "Bow.", "--epic", "Manners")
    project.dk("run")
    monkeypatch.setenv("DK_AGENT", "principal-1")
    assert "only the user" in project.refused("approve", "2")


def test_no_agent_can_approve_or_reject(project: Project, monkeypatch: pytest.MonkeyPatch) -> None:
    who = "pathlib.Path('who.txt').write_text(__import__('os').environ['DK_AGENT'])"
    project.configure(coder=who + "\nprint('RESULT: done')")
    project.dk("add", "Greet", "--spec", "Say hello.")
    project.dk("run")
    assert project.merged("who.txt") == "coder-1"

    monkeypatch.setenv("DK_AGENT", "coder-1")

    assert "only the user" in project.refused("approve", "1")
    assert "only the user" in project.refused("reject", "1", "--note", "no")


def test_an_answer_given_during_the_conversation_lets_the_ticket_continue(
    project: Project,
) -> None:
    asks = (
        "if 'Catalan' in prompt:\n"
        "    pathlib.Path('greeting.txt').write_text('hola\\n'); print('RESULT: done')\n"
        "else:\n"
        "    print('RESULT: question: which language?')"
    )
    talk = PRINCIPAL + (
        "dk('add', 'Greet', '--spec', spec('Say hello.'), '--behaviour-tests')\n"
        "wait_for('which language?')\n"
        "dk('retry', '1', '--note', 'Catalan')\n"
        "wait_for('#1 done')\n"
    )
    project.configure(coder=asks, principal=talk)

    project.dk("talk")

    assert project.merged("greeting.txt") == "hola\n"


def test_closing_the_conversation_stops_the_work_without_judging_it(project: Project) -> None:
    slow = "import time; time.sleep(60)\nprint('RESULT: done')"
    talk = (
        PRINCIPAL
        + "dk('add', 'Slow', '--spec', spec('x'), '--behaviour-tests')\n"
        + "wait_for('coder-1 started')\n"
    )
    project.configure(coder=slow, principal=talk)
    started = time.monotonic()

    project.dk("talk")

    assert time.monotonic() - started < 20
    status = project.dk("status")
    assert "#1 code" in status and "attempt" not in status and "stopped" not in status


def test_talking_needs_a_principal(project: Project) -> None:
    project.configure(coder=HELLO)

    assert "no agent has the role 'principal'" in project.refused("talk")


def test_inside_herdr_the_user_is_told_when_a_ticket_needs_them(
    project: Project, herdr: Herdr
) -> None:
    talk = (
        PRINCIPAL
        + "dk('add', 'Vague', '--spec', spec('x'), '--behaviour-tests')\n"
        + "wait_for('stopped at code')\n"
    )
    project.configure(coder="print('RESULT: question: which language?')", principal=talk)

    project.dk("talk")

    calls = herdr.calls()
    told = [call for call in calls if call[:2] == ["notification", "show"]]
    assert len(told) == 1 and "#1 Vague" in told[0][2]
    assert "which language?" in told[0][told[0].index("--body") + 1]
    labels = [call[call.index("--label") + 1] for call in calls if call[:2] == ["tab", "create"]]
    assert labels == ["status", "coder-1"], "the board already lists the tickets"
    progress = (project.root / ".devkit" / "logs" / "tickets.log").read_text()
    assert "#1" in progress, "what happened is still kept in a file"


def renames(herdr: Herdr) -> list[list[str]]:
    return [call[2:] for call in herdr.calls() if call[:2] == ["tab", "rename"]]


def test_inside_herdr_the_conversations_tab_is_named_and_gets_its_name_back(
    project: Project, herdr: Herdr, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HERDR_TAB_ID", "w1:t0")
    project.configure(coder=HELLO, principal="pass")

    project.dk("talk")

    assert renames(herdr) == [["w1:t0", "Principal"], ["w1:t0", "1"]]


def test_the_conversations_tab_keeps_its_name_when_tabs_are_not_wanted(
    project: Project, herdr: Herdr, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HERDR_TAB_ID", "w1:t0")
    project.configure(coder=HELLO, principal="pass")

    project.dk("talk", "--no-tabs")

    assert renames(herdr) == []


def test_a_herdr_that_cannot_name_the_tab_does_not_stop_the_conversation(
    project: Project, herdr: Herdr, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HERDR_TAB_ID", "w1:t0")
    herdr.breaks()
    project.configure(coder=HELLO, principal="pathlib.Path('talked.txt').write_text('x')")

    project.dk("talk")

    assert (project.root / "talked.txt").exists()
    assert renames(herdr) == [["w1:t0", "Principal"]], "no earlier name was learnt to give back"


def test_outside_a_herdr_tab_nothing_is_asked_of_herdr(project: Project, herdr: Herdr) -> None:
    project.configure(coder=HELLO, principal="pass")

    project.dk("talk", "--no-tabs")

    assert herdr.calls() == []
