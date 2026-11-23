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
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Literal

from dk import child

INSTRUCTIONS = "{instructions}"
WHO = "DK_AGENT"  # set for every program an agent runs, so `dk` can tell it is not the user
# Claude keeps no notes of its own between jobs: a verifier's grew unread to 13,500 words,
# and a habit written there cost a ticket hours. What a project learns is in its lessons.
_ALWAYS = {"CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1"}
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
    reading: str  # the tools of a job that must not change files; none if it has no such list
    web: str  # the tools that reach the web, which such a job keeps
    offline: tuple[str, ...]  # what takes the web away
    talk: tuple[str, ...]  # a conversation with the user
    again: str  # what, followed by a session, picks up the job that session remembers
    reasoning: tuple[str, ...]  # what sets how hard it thinks; `{reasoning}` stands for how


PROGRAMS = {
    "pi": _Program(
        ("pi", "-p", "--mode", "json", "--model", "{model}"),
        "read,bash,grep,find,ls",
        "codex_search,*web*",  # Pi reaches the web through an extension, if one is installed
        ("--exclude-tools", "codex_search,*web*"),
        ("pi", "--model", "{model}", "--append-system-prompt", INSTRUCTIONS),
        "--session",
        ("--thinking", "{reasoning}"),
    ),
    "claude": _Program(
        ("claude", "-p", "--output-format", "stream-json")
        + ("--verbose", "--model", "{model}", _FREE["claude"])
        + ("--append-system-prompt", _RULES),
        "Read,Bash,Grep,Glob",
        "WebSearch,WebFetch",
        ("--disallowedTools", "WebSearch,WebFetch"),
        ("claude", "--model", "{model}", _FREE["claude"], "--append-system-prompt", INSTRUCTIONS),
        "--resume",
        ("--effort", "{reasoning}"),
    ),
    "codex": _Program(
        ("codex", "exec", "--json", "--skip-git-repo-check") + ("-m", "{model}", _FREE["codex"]),
        *("", ""),  # Codex has no list of tools to narrow, and searches the web as it comes
        ("-c", 'web_search="disabled"'),
        ("codex", "-m", "{model}", _FREE["codex"], INSTRUCTIONS),
        "resume",
        ("-c", 'model_reasoning_effort="{reasoning}"'),
    ),
}


class UnknownProgram(Exception):
    """The configuration names an agent program this piece cannot start."""


@dataclass(frozen=True)
class Reply:
    kind: Answer | Literal["unclear"]
    text: str = ""
    late: bool = False  # it was cut off for taking too long, and `text` says after how long
    session: str = ""  # the program's name for what it remembers of the job, if it keeps any


def _known(program: str) -> _Program:
    if program not in PROGRAMS:
        raise UnknownProgram(f"unknown agent program '{program}'; known: {', '.join(PROGRAMS)}")
    return PROGRAMS[program]


def _thinking(known: _Program, reasoning: str) -> tuple[str, ...]:
    """What tells the program how hard to think; nothing leaves it to its own default."""
    return tuple(part.replace("{reasoning}", reasoning) for part in known.reasoning if reasoning)


def command(
    program: str,
    model: str,
    writes: bool,
    web: bool = True,
    session: str = "",
    reasoning: str = "",
) -> tuple[str, ...]:
    """The command line for a known agent program; a reviewer gets no tools that write.
    With `session`, the job that session remembers is picked up again."""
    known = _known(program)
    again = (known.again, session) if session else ()  # right after the program and its mode
    base = tuple(
        part.replace("{model}", model) for part in (*known.job[:2], *again, *known.job[2:])
    )
    tools = ",".join(filter(None, (known.reading, known.web if web else "")))
    narrowed = () if writes or not known.reading else ("--tools", tools)
    less = () if web else known.offline
    return (*base, *_thinking(known, reasoning), *narrowed, *less, "--", INSTRUCTIONS)


def conversation(
    program: str, model: str, web: bool = True, reasoning: str = ""
) -> tuple[str, ...]:
    """The command line that opens a known agent program for talking with the user."""
    known = _known(program)
    options = (*_thinking(known, reasoning), *(() if web else known.offline))
    talk = (known.talk[0], *options, *known.talk[1:])
    return tuple(part.replace("{model}", model) for part in talk)


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


def _session(line: str) -> str:
    """The name a known program gives, as it starts, to what it will remember of the job."""
    try:
        event = json.loads(line)
    except ValueError:
        return ""
    if not isinstance(event, dict):
        return ""
    named = event.get("id") if event.get("type") == "session" else None  # how Pi says it
    return str(named or event.get("session_id") or event.get("thread_id") or "")


def _noting(sessions: list[str], plain: Callable[[str], str]) -> Callable[[str], str]:
    """`plain`, which also adds to `sessions` the first session a line names."""

    def shown(line: str) -> str:
        if not sessions and (session := _session(line)):
            sessions.append(session)
        return plain(line)

    return shown


_ENDED = ("ended", "stopped")  # how a job that was not cut off for time is closed


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
    sessions: list[str] = []
    plain = _noting(sessions, plain)
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a") as shown:
        shown.write(f"\n{datetime.now():%Y-%m-%d %H:%M}  === {title} ===\n" if title else "")

        def show(line: str) -> None:
            said.append(plain(line))
            shown.write(said[-1])
            shown.flush()

        feed = None if by_argument else instructions
        code = child.run(argv, cwd, show, seconds, stop, feed, {WHO: name, **_ALWAYS})
        late = code is None and not (stop and stop.is_set())
        how = f"cut off after {seconds / 60:g} minutes" if late else _ENDED[code is None]
        shown.write(f"{datetime.now():%Y-%m-%d %H:%M}  === {how} ===\n" if title else "")
    reply = Reply("unclear", how, late=True) if late else _heard("".join(said), code)
    return replace(reply, session="".join(sessions))


def _heard(said: str, code: int | None) -> Reply:
    reply = read(said) if code == 0 else Reply("unclear")
    if reply.kind == "unclear":  # say what it last said, which is usually why
        last = [line.strip() for line in said.splitlines() if line.strip()][-1:]
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
        return subprocess.run(full, cwd=cwd, env={**os.environ, WHO: name, **_ALWAYS}).returncode
    finally:
        signal.signal(signal.SIGINT, interrupt)
