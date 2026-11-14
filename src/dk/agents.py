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
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from dk import child

INSTRUCTIONS = "{instructions}"
WHO = "DK_AGENT"  # set for every program an agent runs, so `dk` can tell it is not the user
Answer = Literal["done", "approved", "rejected", "blocked", "question"]
ANSWERS: tuple[Answer, ...] = ("done", "approved", "rejected", "blocked", "question")
_FREE = {
    "claude": "--dangerously-skip-permissions",
    "codex": "--dangerously-bypass-approvals-and-sandbox",
}
# Pi and Codex read a project's AGENTS.md by themselves; Claude reads only CLAUDE.md.
_RULES = "If the current directory has an AGENTS.md, read it first: it holds this project's rules."


@dataclass(frozen=True)
class _Program:
    """How one kind of agent program is started; `{model}` stands for the agent's model."""

    job: tuple[str, ...]  # one job; the instructions follow as the last argument
    reading: tuple[str, ...]  # added for a job that must not change files
    talk: tuple[str, ...]  # a conversation with the user


PROGRAMS = {
    "pi": _Program(
        ("pi", "-p", "--no-session", "--mode", "json", "--model", "{model}"),
        ("--tools", "read,bash,grep,find,ls"),
        ("pi", "--model", "{model}", "--append-system-prompt", INSTRUCTIONS),
    ),
    "claude": _Program(
        ("claude", "-p", "--no-session-persistence", "--output-format", "stream-json")
        + ("--verbose", "--model", "{model}", _FREE["claude"])
        + ("--append-system-prompt", _RULES),
        ("--tools", "Read,Bash,Grep,Glob"),
        ("claude", "--model", "{model}", _FREE["claude"], "--append-system-prompt", INSTRUCTIONS),
    ),
    "codex": _Program(
        ("codex", "exec", "--ephemeral", "--json", "--skip-git-repo-check")
        + ("-m", "{model}", _FREE["codex"]),
        (),  # Codex has no list of tools to narrow
        ("codex", "-m", "{model}", _FREE["codex"], INSTRUCTIONS),
    ),
}


class UnknownProgram(Exception):
    """The configuration names an agent program this piece cannot start."""


@dataclass(frozen=True)
class Reply:
    kind: Answer | Literal["unclear"]
    text: str = ""


def _known(program: str) -> _Program:
    if program not in PROGRAMS:
        raise UnknownProgram(f"unknown agent program '{program}'; known: {', '.join(PROGRAMS)}")
    return PROGRAMS[program]


def command(program: str, model: str, writes: bool) -> tuple[str, ...]:
    """The command line for a known agent program; a reviewer gets no tools that write."""
    known = _known(program)
    base = tuple(part.replace("{model}", model) for part in known.job)
    return (*base, *(() if writes else known.reading), "--", INSTRUCTIONS)


def conversation(program: str, model: str) -> tuple[str, ...]:
    """The command line that opens a known agent program for talking with the user."""
    return tuple(part.replace("{model}", model) for part in _known(program).talk)


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
    if message.get("errorMessage"):  # the model or its provider refused the request
        texts.append(f"error: {message['errorMessage']}")
    return "".join(text.rstrip("\n") + "\n" for text in texts)


def _pi(event: dict[str, Any]) -> str:
    shows = {"tool_execution_start": _tool, "message_end": _spoken}
    return shows.get(event.get("type", ""), lambda _: "")(event)


def _claude(event: dict[str, Any]) -> str:
    if event.get("type") == "result" and event.get("is_error"):
        return f"error: {event.get('result') or event.get('subtype')}\n"
    if event.get("type") != "assistant":
        return ""
    return "".join(_part(part) for part in event.get("message", {}).get("content", []))


def _part(part: dict[str, Any]) -> str:
    """One piece of what Claude said: words, or the tool it reached for."""
    if part.get("type") == "text":
        return str(part["text"]).rstrip("\n") + "\n"
    if part.get("type") != "tool_use":
        return ""
    given = part.get("input") or {}
    what = next((given[key] for key in ("command", "file_path", "pattern") if key in given), "")
    return f"> {part.get('name')} {what}\n"


def _codex(event: dict[str, Any]) -> str:
    item = event.get("item") or {}
    step = (event.get("type"), item.get("type"))
    if step == ("item.started", "command_execution"):
        return f"> {item.get('command')}\n"
    if step == ("item.completed", "agent_message"):
        return str(item.get("text", "")).rstrip("\n") + "\n"
    failure = event.get("message") or (event.get("error") or {}).get("message")
    return f"error: {failure}\n" if step[0] in ("error", "turn.failed") and failure else ""


_READERS = {"pi": _pi, "claude": _claude, "codex": _codex}


def reader(program: str) -> Callable[[str], str]:
    """How to turn each line a program prints into what is shown; by default, as it is.

    The known programs print one event per line; a line that is not one is shown as it is.
    """
    if program not in _READERS:
        return str
    show = _READERS[program]

    def plain(line: str) -> str:
        try:
            event = json.loads(line)
        except ValueError:
            return line
        return show(event) if isinstance(event, dict) else line

    return plain


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
        shown.write(f"\n{datetime.now():%Y-%m-%d %H:%M}  === {title} ===\n" if title else "")

        def show(line: str) -> None:
            said.append(plain(line))
            shown.write(said[-1])
            shown.flush()

        feed = None if by_argument else instructions
        code = child.run(argv, cwd, show, seconds, stop, feed, {WHO: name})
    reply = read("".join(said)) if code == 0 else Reply("unclear")
    if reply.kind == "unclear":  # say what it last said, which is usually why
        last = [line.strip() for line in "".join(said).splitlines() if line.strip()][-1:]
        return Reply("unclear", "".join(last))
    return reply


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
