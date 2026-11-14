"""Claude and Codex can be the agents, as Pi can: started for one job, or for the conversation."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest
from conftest import Project

PREAMBLE = """\
import json, pathlib, sys
here = pathlib.Path(__file__).parent
me = pathlib.Path(__file__).stem
with (here / f"{me}-calls.jsonl").open("a") as log:
    log.write(json.dumps(sys.argv[1:]) + "\\n")
prompt = sys.argv[-1]

def emit(**event):
    print(json.dumps(event))

def claude_says(*parts):
    emit(type="assistant", message={"role": "assistant", "content": list(parts)})
"""
CLAUDE_WORKS = """
pathlib.Path("greeting.txt").write_text("hello\\n")
emit(type="system", subtype="init", cwd="/somewhere")
claude_says({"type": "thinking", "thinking": ""})
claude_says({"type": "tool_use", "name": "Write", "input": {"file_path": "greeting.txt"}})
emit(type="user", message={"role": "user", "content": [{"type": "tool_result", "content": "ok"}]})
claude_says({"type": "text", "text": "Wrote the greeting.\\n\\nRESULT: done"})
emit(type="result", is_error=False, result="Wrote the greeting.\\n\\nRESULT: done")
"""
CODEX_WORKS = """
pathlib.Path("greeting.txt").write_text("hello\\n")
emit(type="thread.started", thread_id="t")
run = {"type": "command_execution", "command": "printf hello > greeting.txt"}
emit(type="item.started", item=run)
emit(type="item.completed", item={**run, "aggregated_output": "", "exit_code": 0})
emit(type="item.completed", item={"type": "agent_message", "text": "Wrote it.\\n\\nRESULT: done"})
emit(type="turn.completed", usage={})
"""
APPROVES = {
    "claude": 'claude_says({"type": "text", "text": "Fine.\\n\\nRESULT: approved"})',
    "codex": 'emit(type="item.completed", item={"type": "agent_message", '
    '"text": "RESULT: approved"})',
}


class Programs:
    """Stand-ins for the real programs on PATH; what each does is written by the test."""

    def __init__(self, folder: Path) -> None:
        self._folder = folder

    def does(self, name: str, body: str) -> None:
        script = self._folder / f"{name}.py"
        script.write_text(PREAMBLE + body + "\n")
        launcher = self._folder / name
        launcher.write_text(f'#!/bin/sh\nexec {sys.executable} {script} "$@"\n')
        launcher.chmod(0o755)

    def calls(self, name: str) -> list[list[str]]:
        log = self._folder / f"{name}-calls.jsonl"
        return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []


@pytest.fixture
def programs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Programs:
    folder = tmp_path / "bin"
    folder.mkdir()
    monkeypatch.setenv("PATH", f"{folder}{os.pathsep}{os.environ['PATH']}")
    return Programs(folder)


def team(project: Project, program: str, *roles: str) -> None:
    agents = "".join(
        f'[[agents]]\nname = "{role}-1"\nrole = "{role}"\nprogram = "{program}"\n'
        f'model = "some-model"\n\n'
        for role in roles
    )
    (project.root / "devkit.toml").write_text(f'{agents}[checks]\nunit = ["true"]\n')
    project.git("add", "devkit.toml")
    project.git("commit", "-qm", "configure devkit")


def log(project: Project, agent: str) -> str:
    return (project.root / ".devkit" / "logs" / f"{agent}.log").read_text()


@pytest.mark.parametrize(
    ("program", "works", "starts", "did"),
    [
        ("claude", CLAUDE_WORKS, ["-p"], "> Write greeting.txt"),
        ("codex", CODEX_WORKS, ["exec"], "> printf hello > greeting.txt"),
    ],
)
def test_a_coder_of_either_program_does_a_ticket_and_what_it_does_can_be_followed(
    project: Project, programs: Programs, program: str, works: str, starts: list[str], did: str
) -> None:
    programs.does(program, works)
    team(project, program, "coder")
    project.dk("add", "Greet", "--spec", "Create greeting.txt containing hello.")

    project.dk("run")

    assert project.merged("greeting.txt") == "hello\n"
    (call,) = programs.calls(program)
    assert call[: len(starts)] == starts
    assert call[call.index("some-model") - 1] in ("--model", "-m")
    assert "Create greeting.txt containing hello." in call[-1]
    shown = log(project, "coder-1")
    assert did in shown and "Wrote" in shown
    assert '"type"' not in shown, "the program's own event lines are not what a person reads"


def test_claude_and_codex_work_without_asking_for_permission(
    project: Project, programs: Programs
) -> None:
    for program, works in (("claude", CLAUDE_WORKS), ("codex", CODEX_WORKS)):
        programs.does(program, works)
        team(project, program, "coder")
        project.dk("add", f"Greet with {program}", "--spec", "Create greeting.txt.")
        project.dk("run")

    assert "--dangerously-skip-permissions" in programs.calls("claude")[0]
    assert "--dangerously-bypass-approvals-and-sandbox" in programs.calls("codex")[0]


def test_a_claude_agent_is_pointed_at_the_projects_rules(
    project: Project, programs: Programs
) -> None:
    """Pi and Codex read AGENTS.md by themselves; Claude reads only CLAUDE.md."""
    programs.does("claude", CLAUDE_WORKS)
    team(project, "claude", "coder")
    project.dk("add", "Greet", "--spec", "Create greeting.txt.")

    project.dk("run")

    (call,) = programs.calls("claude")
    assert "AGENTS.md" in call[call.index("--append-system-prompt") + 1]


@pytest.mark.parametrize("program", ["claude", "codex"])
def test_a_reviewer_of_either_program_judges_the_work(
    project: Project, programs: Programs, program: str
) -> None:
    works = CLAUDE_WORKS if program == "claude" else CODEX_WORKS
    programs.does(
        program,
        f"if prompt.startswith('You are a coder'):{indent(works)}\nelse:\n    {APPROVES[program]}",
    )
    team(project, program, "coder", "verifier")
    project.dk("add", "Greet", "--spec", "Create greeting.txt containing hello.")

    project.dk("run")

    shown = project.dk("show", "1")
    assert "#1 done" in shown and "verifier-1 started" in shown


def indent(body: str) -> str:
    return body.replace("\n", "\n    ")


def test_a_claude_reviewer_is_given_no_tools_that_edit_files(
    project: Project, programs: Programs
) -> None:
    programs.does(
        "claude",
        f"if '--tools' not in sys.argv:{indent(CLAUDE_WORKS)}\nelse:\n    {APPROVES['claude']}",
    )
    team(project, "claude", "coder", "verifier")
    project.dk("add", "Greet", "--spec", "Create greeting.txt containing hello.")

    project.dk("run")

    coder, verifier = programs.calls("claude")
    assert "--tools" not in coder
    allowed = verifier[verifier.index("--tools") + 1].split(",")
    assert "Read" in allowed and "Bash" in allowed
    assert not {"Edit", "Write", "NotebookEdit"} & set(allowed)
    assert "#1 done" in project.dk("status")


@pytest.mark.parametrize(
    ("program", "fails"),
    [
        ("claude", 'emit(type="result", is_error=True, result="Credit balance is too low")'),
        ("codex", 'emit(type="error", message="Credit balance is too low")'),
    ],
)
def test_what_a_program_says_when_it_fails_reaches_the_user(
    project: Project, programs: Programs, program: str, fails: str
) -> None:
    programs.does(program, f"{fails}\nsys.exit(1)")
    team(project, program, "coder")
    project.dk("add", "Greet", "--spec", "Create greeting.txt.")

    project.dk("run")

    assert "Credit balance is too low" in project.dk("status")


@pytest.mark.parametrize("program", ["claude", "codex"])
def test_the_conversation_can_be_with_either_program(
    project: Project, programs: Programs, program: str
) -> None:
    programs.does(program, "")
    team(project, program, "coder", "principal")

    project.dk("talk", "--no-tabs")

    (call,) = programs.calls(program)
    assert "-p" not in call and "exec" not in call, "a conversation, not one job"
    assert call[call.index("some-model") - 1] in ("--model", "-m")
    brief = next(part for part in call if "Your tool for tickets" in part)
    assert "retry NUMBER" in brief


def test_a_first_configuration_can_name_the_program(project: Project) -> None:
    project.dk("init", "--model", "sonnet", "--program", "claude")

    written = (project.root / "devkit.toml").read_text()
    assert written.count('program = "claude"') == 5 and '"pi"' not in written
