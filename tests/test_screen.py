"""Inside Herdr, every agent gets a tab that shows what it is doing. Watching only."""

from __future__ import annotations

import pytest
from conftest import Herdr, Project

HELLO = "pathlib.Path('greeting.txt').write_text('hello\\n')\nprint('wrote it\\nRESULT: done')"
APPROVES = "print('RESULT: approved')"


def test_each_agent_gets_a_tab_showing_its_work_and_the_tabs_close_at_the_end(
    project: Project, herdr: Herdr
) -> None:
    project.configure(coder=HELLO, verifier=APPROVES)
    project.dk("add", "Greet", "--spec", "Say hello.")

    project.dk("run")

    calls = herdr.calls()
    created = [call for call in calls if call[:2] == ["tab", "create"]]
    assert [call[call.index("--label") + 1] for call in created] == ["coder-1", "verifier-1"]
    assert all(
        "--no-focus" in call and call[call.index("--workspace") + 1] == "w1" for call in created
    )
    shown = [call for call in calls if call[:2] == ["pane", "run"]]
    assert [call[2] for call in shown] == ["w1:p1", "w1:p3"]
    assert shown[0][-1].endswith(".devkit/logs/coder-1.log")
    assert [call[2] for call in calls if call[:2] == ["tab", "close"]] == ["w1:t1", "w1:t3"]
    assert project.merged("greeting.txt") == "hello\n"


def test_an_agents_tab_shows_which_ticket_it_is_on_and_what_it_says(project: Project) -> None:
    project.configure(coder=HELLO)
    project.dk("add", "Greet", "--spec", "Say hello.")

    project.dk("run")

    shown = (project.root / ".devkit" / "logs" / "coder-1.log").read_text()
    assert "#1 Greet" in shown and "code" in shown
    assert shown.index("#1 Greet") < shown.index("wrote it") < shown.index("RESULT: done")


def test_the_tabs_close_even_when_the_run_cannot_go_on(project: Project, herdr: Herdr) -> None:
    (project.root / "devkit.toml").write_text(
        '[[agents]]\nname = "coder-1"\nrole = "coder"\nprogram = "nope"\n'
    )
    project.dk("add", "Greet", "--spec", "x")

    project.refused("run")

    calls = herdr.calls()
    assert [call[2] for call in calls if call[:2] == ["tab", "close"]] == ["w1:t1"]


def test_trouble_with_herdr_does_not_stop_the_work(project: Project, herdr: Herdr) -> None:
    herdr.breaks()
    project.configure(coder=HELLO)
    project.dk("add", "Greet", "--spec", "Say hello.")

    project.dk("run")

    assert project.merged("greeting.txt") == "hello\n"
    assert not [call for call in herdr.calls() if call[:2] == ["tab", "close"]]


def test_no_tabs_are_opened_when_asked_not_to(project: Project, herdr: Herdr) -> None:
    project.configure(coder=HELLO)
    project.dk("add", "Greet", "--spec", "Say hello.")

    project.dk("run", "--no-tabs")

    assert herdr.calls() == []
    assert project.merged("greeting.txt") == "hello\n"


def test_outside_herdr_nothing_is_opened(
    project: Project, herdr: Herdr, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("HERDR_WORKSPACE_ID")
    project.configure(coder=HELLO)
    project.dk("add", "Greet", "--spec", "Say hello.")

    project.dk("run")

    assert herdr.calls() == []
