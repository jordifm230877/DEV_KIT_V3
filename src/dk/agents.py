"""Give one job to one agent program and read its answer.

An agent is any command that takes instructions and prints a reply ending in a `RESULT:` line.
This piece knows how to start each kind of program; it knows nothing about the process.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from dk import child

INSTRUCTIONS = "{instructions}"
WHO = "DK_AGENT"  # set for every program an agent runs, so `dk` can tell it is not the user
Answer = Literal["done", "approved", "rejected", "blocked", "question"]
ANSWERS: tuple[Answer, ...] = ("done", "approved", "rejected", "blocked", "question")
_READ_ONLY = ("--tools", "read,bash,grep,find,ls")

_PROGRAMS = {
    "pi": ("pi", "-p", "--no-session", "--mode", "json", "--model", "{model}"),
}


_CONVERSATIONS = {
    "pi": ("pi", "--model", "{model}", "--append-system-prompt", INSTRUCTIONS),
}


class UnknownProgram(Exception):
    """The configuration names an agent program this piece cannot start."""


@dataclass(frozen=True)
class Reply:
    kind: Answer | Literal["unclear"]
    text: str = ""


def command(program: str, model: str, writes: bool) -> tuple[str, ...]:
    """The command line for a known agent program; a reviewer gets no tools that write."""
    if program not in _PROGRAMS:
        raise UnknownProgram(f"unknown agent program '{program}'; known: {', '.join(_PROGRAMS)}")
    base = tuple(part.replace("{model}", model) for part in _PROGRAMS[program])
    return (*base, *(() if writes else _READ_ONLY), "--", INSTRUCTIONS)


def conversation(program: str, model: str) -> tuple[str, ...]:
    """The command line that opens a known agent program for talking with the user."""
    if program not in _CONVERSATIONS:
        raise UnknownProgram(f"unknown agent program '{program}'; known: {', '.join(_PROGRAMS)}")
    return tuple(part.replace("{model}", model) for part in _CONVERSATIONS[program])


def read(output: str) -> Reply:
    """The answer is the last non-empty line, `RESULT: <answer>` or `RESULT: <answer>: <text>`."""
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if not lines or not lines[-1].startswith("RESULT:"):
        return Reply("unclear")
    kind, _, text = lines[-1].removeprefix("RESULT:").partition(":")
    for answer in ANSWERS:
        if kind.strip() == answer:
            return Reply(answer, text.strip())
    return Reply("unclear")


def _tool(event: dict[str, Any]) -> str:
    details = event.get("args") or {}
    return f"> {event.get('toolName')} {details.get('command') or details.get('path') or ''}\n"


def _spoken(event: dict[str, Any]) -> str:
    message = event.get("message") or {}
    if message.get("role") != "assistant":
        return ""
    texts = [part["text"] for part in message["content"] if part.get("type") == "text"]
    return "".join(text.rstrip("\n") + "\n" for text in texts)


def _pi(line: str) -> str:
    """One line of Pi's detailed output as something a person can follow, or nothing."""
    try:
        event = json.loads(line)
    except ValueError:
        return line
    if not isinstance(event, dict):
        return line
    shows = {"tool_execution_start": _tool, "message_end": _spoken}
    return shows.get(event.get("type", ""), lambda _: "")(event)


def reader(program: str) -> Callable[[str], str]:
    """How to turn each line a program prints into what is shown; by default, as it is."""
    return {"pi": _pi}.get(program, str)


def ask(
    argv: Sequence[str],
    instructions: str,
    cwd: Path,
    log: Path,
    seconds: float,
    title: str = "",
    plain: Callable[[str], str] = str,
    stop: threading.Event | None = None,
    name: str = "",
) -> Reply:
    """Run the agent to the end of its job, adding what it does to `log` as it happens.

    Instructions replace an `{instructions}` argument if there is one; otherwise they are
    the program's standard input. `plain` turns each printed line into what is shown.
    """
    by_argument = INSTRUCTIONS in argv
    argv = [instructions if part == INSTRUCTIONS else part for part in argv]
    said: list[str] = []
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a") as shown:
        shown.write(f"\n=== {title} ===\n" if title else "")

        def show(line: str) -> None:
            said.append(plain(line))
            shown.write(said[-1])
            shown.flush()

        feed = None if by_argument else instructions
        code = child.run(argv, cwd, show, seconds, stop, feed, {WHO: name})
    return read("".join(said)) if code == 0 else Reply("unclear")


def converse(argv: Sequence[str], brief: str, cwd: Path, name: str) -> int:
    """Hand the terminal to an agent for a conversation with the user, until it ends.

    The brief replaces an `{instructions}` argument if there is one; otherwise it is added
    as the last argument.
    """
    full = [brief if part == INSTRUCTIONS else part for part in argv]
    full += [] if INSTRUCTIONS in argv else [brief]
    interrupt = signal.signal(signal.SIGINT, signal.SIG_IGN)  # Ctrl-C belongs to the agent
    try:
        return subprocess.run(full, cwd=cwd, env={**os.environ, WHO: name}).returncode
    finally:
        signal.signal(signal.SIGINT, interrupt)
