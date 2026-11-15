"""The agent piece on its own: starting a program, handing it a job, reading its answer."""

from __future__ import annotations

import re
import sys
import threading
from datetime import datetime
from pathlib import Path

import pytest

from dk import agents


def test_pi_is_started_for_one_job_with_the_chosen_model() -> None:
    argv = agents.command("pi", "some/model", writes=True)

    assert argv[0] == "pi" and "-p" in argv
    assert argv[argv.index("--model") + 1] == "some/model"
    assert argv[-2:] == ("--", agents.INSTRUCTIONS)
    assert "--tools" not in argv


def test_a_pi_reviewer_gets_no_tools_that_write() -> None:
    argv = agents.command("pi", "some/model", writes=False)

    tools = argv[argv.index("--tools") + 1].split(",")
    assert "read" in tools and not {"edit", "write"} & set(tools)
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
        ("RESULT: approved", agents.Reply("approved")),
        ("RESULT: rejected: says hi", agents.Reply("rejected", "says hi")),
        ("RESULT: done\nand then more talk", agents.Reply("unclear")),
        ("RESULT: finished", agents.Reply("unclear")),
        ("", agents.Reply("unclear")),
    ],
)
def test_only_a_final_result_line_counts_as_an_answer(output: str, reply: agents.Reply) -> None:
    assert agents.read(output) == reply


PI_EVENTS = [
    {"type": "session", "version": 3, "id": "x"},
    {"type": "message_end", "message": {"role": "system", "content": ""}},
    {
        "type": "message_end",
        "message": {"role": "user", "content": [{"type": "text", "text": "the brief"}]},
    },
    {"type": "tool_execution_start", "toolName": "bash", "args": {"command": "echo hi"}},
    {"type": "tool_execution_start", "toolName": "edit", "args": {"path": "wc.py", "edits": []}},
    {"type": "message_update", "assistantMessageEvent": {"type": "text_delta"}},
    {
        "type": "message_end",
        "message": {
            "role": "assistant",
            "content": [
                {"type": "toolCall", "name": "bash"},
                {"type": "text", "text": "All good.\n\nRESULT: done"},
            ],
        },
    },
    {"type": "agent_settled", "aborted": False},
]


def test_pis_detailed_output_is_shown_as_readable_lines(tmp_path: Path) -> None:
    import json

    emit = f"for event in {PI_EVENTS!r}:\n    print(__import__('json').dumps(event))"
    assert json.loads(json.dumps(PI_EVENTS)) == PI_EVENTS
    log = tmp_path / "agent.log"

    reply = agents.ask(
        [sys.executable, "-c", emit], "x", tmp_path, log, 30, plain=agents.reader("pi")
    )

    assert reply == agents.Reply("done", session="x"), "and it says what it will remember"
    assert log.read_text().splitlines() == [
        "> bash echo hi",
        "> edit wc.py",
        "All good.",
        "",
        "RESULT: done",
    ]


def test_pi_is_asked_for_its_detailed_output() -> None:
    argv = agents.command("pi", "some/model", writes=True)

    assert argv[argv.index("--mode") + 1] == "json"


def test_output_that_is_not_what_pi_normally_prints_is_shown_as_it_is() -> None:
    plain = agents.reader("pi")

    assert plain("Error: not logged in\n") == "Error: not logged in\n"
    assert plain("[1, 2]\n") == "[1, 2]\n"


def test_each_job_is_added_below_the_ones_before_under_its_own_heading(tmp_path: Path) -> None:
    log = tmp_path / "agent.log"
    say = [sys.executable, "-c", "import sys; print(sys.stdin.read()); print('RESULT: done')"]

    agents.ask(say, "first job", tmp_path, log, 30, title="#1 One")
    reply = agents.ask(say, "second job", tmp_path, log, 30, title="#2 Two")

    shown = log.read_text()
    assert shown.index("#1 One") < shown.index("first job") < shown.index("#2 Two")
    assert reply == agents.Reply("done")


def test_an_earlier_jobs_answer_is_not_taken_for_this_ones(tmp_path: Path) -> None:
    log = tmp_path / "agent.log"
    agents.ask([sys.executable, "-c", "print('RESULT: done')"], "x", tmp_path, log, 30)

    reply = agents.ask([sys.executable, "-c", "pass"], "x", tmp_path, log, 30)

    assert reply == agents.Reply("unclear")


def test_an_error_pi_got_from_the_model_is_shown_and_reported(tmp_path: Path) -> None:
    refused = {
        "type": "message_end",
        "message": {
            "role": "assistant",
            "content": [],
            "stopReason": "error",
            "errorMessage": "400: this model is not available in your region",
        },
    }
    emit = f"print(__import__('json').dumps({refused!r}))"
    log = tmp_path / "agent.log"

    reply = agents.ask(
        [sys.executable, "-c", emit], "x", tmp_path, log, 30, plain=agents.reader("pi")
    )

    assert reply == agents.Reply(
        "unclear", "error: 400: this model is not available in your region"
    )
    assert "error: 400: this model is not available in your region" in log.read_text()


SLOW = [sys.executable, "-c", "import time; print('working', flush=True); time.sleep(60)"]


def test_a_job_ends_with_a_line_that_says_it_is_over(tmp_path: Path) -> None:
    log = tmp_path / "agent.log"

    agents.ask([sys.executable, "-c", "print('RESULT: done')"], "x", tmp_path, log, 30, title="#1")

    assert re.fullmatch(
        r"\d{4}-\d\d-\d\d \d\d:\d\d  === ended ===", log.read_text().splitlines()[-1]
    )


def test_a_job_cut_off_for_time_says_so_where_its_work_is_shown(tmp_path: Path) -> None:
    log = tmp_path / "agent.log"

    agents.ask(SLOW, "x", tmp_path, log, 0.6, title="#1")

    assert log.read_text().splitlines()[-2:] == [
        "working",
        _at("=== cut off after 0.01 minutes ==="),
    ]


def test_a_job_stopped_with_the_conversation_says_so(tmp_path: Path) -> None:
    log = tmp_path / "agent.log"
    stop = threading.Event()
    stop.set()

    agents.ask(SLOW, "x", tmp_path, log, 30, title="#1", stop=stop)

    assert log.read_text().splitlines()[-1] == _at("=== stopped ===")


def _at(words: str) -> str:
    return f"{datetime.now():%Y-%m-%d %H:%M}  {words}"
