"""Give one job to one agent program and read its answer.

An agent is any command that takes instructions and prints a reply ending in a `RESULT:` line.
This piece knows how to start each kind of program; it knows nothing about the process.
"""

from __future__ import annotations

import os
import signal
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

INSTRUCTIONS = "{instructions}"
Answer = Literal["done", "blocked", "question"]
ANSWERS: tuple[Answer, ...] = ("done", "blocked", "question")

_PROGRAMS = {
    "pi": ("pi", "-p", "--no-session", "--model", "{model}", "--", INSTRUCTIONS),
}


class UnknownProgram(Exception):
    """The configuration names an agent program this piece cannot start."""


@dataclass(frozen=True)
class Reply:
    kind: Literal["done", "blocked", "question", "unclear"]
    text: str = ""


def command(program: str, model: str) -> tuple[str, ...]:
    """The command line for a known agent program."""
    if program not in _PROGRAMS:
        raise UnknownProgram(f"unknown agent program '{program}'; known: {', '.join(_PROGRAMS)}")
    return tuple(part.replace("{model}", model) for part in _PROGRAMS[program])


def read(output: str) -> Reply:
    """The answer is the last non-empty line: `RESULT: done|blocked: why|question: what`."""
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if not lines or not lines[-1].startswith("RESULT:"):
        return Reply("unclear")
    kind, _, text = lines[-1].removeprefix("RESULT:").partition(":")
    for answer in ANSWERS:
        if kind.strip() == answer:
            return Reply(answer, text.strip())
    return Reply("unclear")


def ask(argv: Sequence[str], instructions: str, cwd: Path, log: Path, seconds: float) -> Reply:
    """Run the agent to the end of its job. Its output goes to `log` as it is produced.

    Instructions replace an `{instructions}` argument if there is one; otherwise they are
    the program's standard input.
    """
    by_argument = INSTRUCTIONS in argv
    argv = [instructions if part == INSTRUCTIONS else part for part in argv]
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("wb") as output:
        child = subprocess.Popen(
            argv,
            cwd=cwd,
            stdin=subprocess.DEVNULL if by_argument else subprocess.PIPE,
            stdout=output,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            child.communicate(None if by_argument else instructions.encode(), timeout=seconds)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            child.wait()
            return Reply("unclear")
    if child.returncode != 0:
        return Reply("unclear")
    return read(log.read_text(errors="replace"))
