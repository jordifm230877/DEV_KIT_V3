"""Claude and Codex can be the agents, as Pi can: started for one job, or for the conversation."""

from __future__ import annotations

import pytest
from conftest import Programs, Project, team

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
    assert {"WebSearch", "WebFetch"} < set(allowed), "a reviewer may look things up"
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


PI_WORKS = "\npathlib.Path('greeting.txt').write_text('hello\\n')\nprint('RESULT: done')"
PI_REVIEWS = (
    f"if '--tools' not in sys.argv:{indent(PI_WORKS)}\nelse:\n    print('RESULT: approved')"
)
REVIEWS = {
    "pi": PI_REVIEWS,
    "claude": f"if '--tools' not in sys.argv:{indent(CLAUDE_WORKS)}\nelse:\n"
    f"    {APPROVES['claude']}",
    "codex": f"if prompt.startswith('You are a coder'):{indent(CODEX_WORKS)}\nelse:\n"
    f"    {APPROVES['codex']}",
}
NO_WEB = {
    "pi": ["--exclude-tools", "codex_search,*web*"],
    "claude": ["--disallowedTools", "WebSearch,WebFetch"],
    "codex": ["-c", 'web_search="disabled"'],
}


def test_a_pi_reviewer_keeps_the_tools_that_reach_the_web(
    project: Project, programs: Programs
) -> None:
    """Pi reaches the web through an extension, which a list of tools would leave out."""
    programs.does("pi", PI_REVIEWS)
    team(project, "pi", "coder", "verifier")
    project.dk("add", "Greet", "--spec", "Create greeting.txt containing hello.")

    project.dk("run")

    _, verifier = programs.calls("pi")
    allowed = verifier[verifier.index("--tools") + 1].split(",")
    assert "codex_search" in allowed and "*web*" in allowed
    assert not {"edit", "write"} & set(allowed)


def judged(project: Project, programs: Programs, program: str, settings: str) -> list[list[str]]:
    """How the coder and then the verifier of one ticket were started."""
    programs.does(program, REVIEWS[program])
    team(project, program, "coder", "verifier", settings=settings)
    project.dk("add", "Greet", "--spec", "Create greeting.txt containing hello.")
    project.dk("run")
    assert "#1 done" in project.dk("status")
    return programs.calls(program)


@pytest.mark.parametrize("program", ["pi", "claude", "codex"])
def test_the_web_is_within_reach_when_the_project_says_nothing(
    project: Project, programs: Programs, program: str
) -> None:
    flag, value = NO_WEB[program]

    for call in judged(project, programs, program, ""):
        assert flag not in call or call[call.index(flag) + 1] != value


@pytest.mark.parametrize("program", ["pi", "claude", "codex"])
def test_a_project_can_turn_the_web_off_for_its_agents(
    project: Project, programs: Programs, program: str
) -> None:
    flag, value = NO_WEB[program]

    coder, verifier = judged(project, programs, program, "web = false\n")

    for call in (coder, verifier):
        assert call[call.index(flag) + 1] == value
        assert call[-2] == "--", "the instructions still come last"
    tools = verifier[verifier.index("--tools") + 1] if program != "codex" else ""
    assert "web" not in tools.lower() and "search" not in tools


@pytest.mark.parametrize("program", ["pi", "claude", "codex"])
def test_a_conversation_has_no_web_either_when_the_project_turns_it_off(
    project: Project, programs: Programs, program: str
) -> None:
    programs.does(program, "")
    team(project, program, "coder", "principal", settings="web = false\n")

    project.dk("talk", "--no-tabs")

    (call,) = programs.calls(program)
    flag, value = NO_WEB[program]
    assert call[call.index(flag) + 1] == value
    assert any("Your tool for tickets" in part for part in call), "it is still given its brief"


SEARCHES = {
    "claude": 'claude_says({"type": "tool_use", "name": "WebSearch", '
    '"input": {"query": "cargo-audit latest"}})' + CLAUDE_WORKS,
    "codex": 'emit(type="item.completed", item={"type": "web_search", "query": ""})\n'
    'emit(type="item.completed", item={"type": "web_search", "query": "cargo-audit latest"})'
    + CODEX_WORKS,
}


@pytest.mark.parametrize("program", ["claude", "codex"])
def test_what_an_agent_looks_up_on_the_web_can_be_followed(
    project: Project, programs: Programs, program: str
) -> None:
    programs.does(program, SEARCHES[program])
    team(project, program, "coder")
    project.dk("add", "Greet", "--spec", "Create greeting.txt containing hello.")

    project.dk("run")

    looked = [line for line in log(project, "coder-1").splitlines() if "cargo-audit" in line]
    assert looked in (["> WebSearch cargo-audit latest"], ["> web search cargo-audit latest"])
    assert "> web search \n" not in log(project, "coder-1"), "an empty search says nothing"


SCRIPT = "python - <<'PY'\\nimport json\\n    print(json)\\nPY"
RUNS_A_SCRIPT = {
    "pi": f'emit(type="tool_execution_start", toolName="bash", args={{"command": "{SCRIPT}"}})'
    + PI_WORKS,
    "claude": 'claude_says({"type": "tool_use", "name": "Bash", '
    f'"input": {{"command": "{SCRIPT}"}}}})' + CLAUDE_WORKS,
    "codex": 'emit(type="item.started", '
    f'item={{"type": "command_execution", "command": "{SCRIPT}"}})' + CODEX_WORKS,
}


@pytest.mark.parametrize("program", ["pi", "claude", "codex"])
def test_every_line_of_a_command_an_agent_runs_is_marked_as_the_command(
    project: Project, programs: Programs, program: str
) -> None:
    """Otherwise the lines of a script look like the agent's own words."""
    programs.does(program, RUNS_A_SCRIPT[program])
    team(project, program, "coder")
    project.dk("add", "Greet", "--spec", "Create greeting.txt containing hello.")

    project.dk("run")

    shown = log(project, "coder-1")
    assert "python - <<'PY'\n>   import json\n>       print(json)\n>   PY\n" in shown


def test_a_first_configuration_can_name_the_program(project: Project) -> None:
    project.dk("init", "--model", "sonnet", "--program", "claude")

    written = (project.root / "devkit.toml").read_text()
    assert written.count('program = "claude"') == 4 and '"pi"' not in written


HOW_EACH_IS_TOLD = [
    ("pi", ["--thinking", "high"]),
    ("claude", ["--effort", "high"]),
    ("codex", ["-c", 'model_reasoning_effort="high"']),
]
REASONS = 'reasoning = "high"\n'


def within(call: list[str], wanted: list[str]) -> bool:
    return any(call[at : at + len(wanted)] == wanted for at in range(len(call)))


@pytest.mark.parametrize(("program", "told"), HOW_EACH_IS_TOLD)
def test_an_agent_is_started_with_the_reasoning_it_is_set_to(
    project: Project, programs: Programs, program: str, told: list[str]
) -> None:
    programs.does(program, "print('RESULT: done')")
    team(project, program, "coder", "principal", each=REASONS)
    project.dk("add", "Greet", "--spec", "Create greeting.txt.")

    project.dk("run")
    project.dk("talk", "--no-tabs")

    job, talk = programs.calls(program)[0], programs.calls(program)[-1]
    assert within(job, told) and job.index(told[0]) < job.index("--")
    assert within(talk, told) and "Your tool for tickets" in talk[-1]


@pytest.mark.parametrize(("program", "told"), HOW_EACH_IS_TOLD)
def test_an_agent_with_no_reasoning_set_is_left_to_its_programs_own(
    project: Project, programs: Programs, program: str, told: list[str]
) -> None:
    programs.does(program, "print('RESULT: done')")
    team(project, program, "coder")
    project.dk("add", "Greet", "--spec", "Create greeting.txt.")

    project.dk("run")

    assert told[0] not in programs.calls(program)[0][:-1]
