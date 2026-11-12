"""The agent piece on its own: starting a program, handing it a job, reading its answer."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from dk import agents


def test_pi_is_started_for_one_job_with_the_chosen_model() -> None:
    argv = agents.command("pi", "some/model")

    assert argv[0] == "pi" and "-p" in argv
    assert argv[argv.index("--model") + 1] == "some/model"
    assert argv[-2:] == ("--", agents.INSTRUCTIONS)


def test_instructions_can_be_handed_over_as_an_argument(tmp_path: Path) -> None:
    echo = "import sys; print(sys.argv[1]); print('RESULT: done')"
    log = tmp_path / "logs" / "agent.log"

    reply = agents.ask(
        [sys.executable, "-c", echo, agents.INSTRUCTIONS], "build the thing", tmp_path, log, 30
    )

    assert reply == agents.Reply("done")
    assert "build the thing" in log.read_text()


@pytest.mark.parametrize(
    ("output", "reply"),
    [
        ("work\nRESULT: done\n\n", agents.Reply("done")),
        ("RESULT: blocked: no access: denied", agents.Reply("blocked", "no access: denied")),
        ("RESULT: question:  which one? ", agents.Reply("question", "which one?")),
        ("RESULT: done\nand then more talk", agents.Reply("unclear")),
        ("RESULT: finished", agents.Reply("unclear")),
        ("", agents.Reply("unclear")),
    ],
)
def test_only_a_final_result_line_counts_as_an_answer(output: str, reply: agents.Reply) -> None:
    assert agents.read(output) == reply
