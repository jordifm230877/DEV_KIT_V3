"""An agent whose question stopped a ticket picks its job up where it left it, instead of
starting again without what it had understood."""

from __future__ import annotations

import pytest
from conftest import Programs, Project, team

ASKS_THEN_PAINTS = """
{started}
if "{again}" in sys.argv:
    pathlib.Path("colour.txt").write_text("painted\\n")
    say("RESULT: done")
else:
    say("RESULT: question: which colour?")
"""
SAY = {
    "pi": "emit(type='message_end', message={'role': 'assistant', "
    "'content': [{'type': 'text', 'text': text}]})",
    "claude": "claude_says({'type': 'text', 'text': text})",
    "codex": "emit(type='item.completed', item={'type': 'agent_message', 'text': text})",
}
STARTED = {
    "pi": "emit(type='session', version=3, id='s-1')",
    "claude": "emit(type='system', subtype='init', session_id='s-1')",
    "codex": "emit(type='thread.started', thread_id='s-1')",
}
AGAIN = {"pi": ["--session", "s-1"], "claude": ["--resume", "s-1"], "codex": ["resume", "s-1"]}


def asks(programs: Programs, program: str, body: str = ASKS_THEN_PAINTS) -> None:
    said = f"def say(text):\n    {SAY[program]}\n"
    programs.does(program, said + body.format(started=STARTED[program], again=AGAIN[program][0]))


@pytest.mark.parametrize("program", ["pi", "claude", "codex"])
def test_an_agent_that_asked_goes_on_from_where_it_was_with_the_answer(
    project: Project, programs: Programs, program: str
) -> None:
    asks(programs, program)
    team(project, program, "coder")
    project.dk("add", "Paint", "--spec", "Paint the wall of the shed.")
    project.dk("run")
    assert "which colour?" in project.dk("status")

    project.dk("retry", "1", "--note", "use blue")
    project.dk("run")

    assert project.merged("colour.txt") == "painted\n"
    first, second = programs.calls(program)
    at = second.index(AGAIN[program][0])
    assert second[at : at + 2] == AGAIN[program], "the job it had left is picked up again"
    assert at == 1 or program != "codex", "Codex takes it right after `exec`"
    assert "use blue" in second[-1]
    assert "Paint the wall" not in second[-1], "it is not told again what it already knows"
    assert "RESULT:" in second[-1]
    assert not {"--no-session", "--no-session-persistence", "--ephemeral"} & set(first)


def test_the_principals_answer_reaches_the_agent_in_the_job_it_had_left(
    project: Project, programs: Programs
) -> None:
    asks(programs, "claude")
    programs.does("pi", "print('RESULT: done: use blue')")
    principal = '[[agents]]\nname = "principal"\nrole = "principal"\nprogram = "pi"\nmodel = "m"\n'
    team(project, "claude", "coder", settings=principal)
    project.dk("add", "Paint", "--spec", "Paint the wall of the shed.")

    project.dk("run")

    assert project.merged("colour.txt") == "painted\n"
    _, second = programs.calls("claude")
    assert "--resume" in second and "use blue" in second[-1]


def test_a_job_that_cannot_be_picked_up_again_is_started_afresh(
    project: Project, programs: Programs
) -> None:
    lost = """
{started}
if "{again}" in sys.argv:
    sys.exit("no such session")
if "use blue" in prompt:
    pathlib.Path("colour.txt").write_text("painted\\n")
    say("RESULT: done")
else:
    say("RESULT: question: which colour?")
"""
    asks(programs, "claude", lost)
    team(project, "claude", "coder")
    project.dk("add", "Paint", "--spec", "Paint the wall of the shed.")
    project.dk("run")

    project.dk("retry", "1", "--note", "use blue")
    project.dk("run")

    assert project.merged("colour.txt") == "painted\n"
    third = programs.calls("claude")[2]
    assert "--resume" not in third and "Paint the wall" in third[-1]


def test_an_agent_of_another_program_starts_the_job_afresh(
    project: Project, programs: Programs
) -> None:
    asks(programs, "claude")
    team(project, "claude", "coder")
    project.dk("add", "Paint", "--spec", "Paint the wall of the shed.")
    project.dk("run")
    programs.does(
        "codex",
        "pathlib.Path('colour.txt').write_text('x')\n"
        + "emit(type='item.completed', item={'type': 'agent_message', 'text': 'RESULT: done'})",
    )
    team(project, "codex", "coder")

    project.dk("retry", "1", "--note", "use blue")
    project.dk("run")

    (call,) = programs.calls("codex")
    assert "resume" not in call and "Paint the wall" in call[-1]
