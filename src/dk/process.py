"""The development process as a list of steps, and the one rule for moving along it.

Pure: no files, no programs, no clock. Changing the process means changing `PROCESS`.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

DONE = "done"
STOPPED = "stopped"


@dataclass(frozen=True)
class Step:
    name: str
    kind: Literal["agent", "checks", "merge"]
    role: str = ""


PROCESS: tuple[Step, ...] = (
    Step("code", "agent", "coder"),
    Step("check", "checks"),
    Step("merge", "merge"),
)


@dataclass(frozen=True)
class Passed:
    """The step is complete; the ticket moves on."""


@dataclass(frozen=True)
class Failed:
    """The work is not good enough; it goes back to be redone."""

    reason: str


@dataclass(frozen=True)
class Stopped:
    """Only the user can decide what happens next."""

    reason: str


Outcome = Passed | Failed | Stopped


@dataclass(frozen=True)
class Position:
    """Where a ticket is: a step name, `DONE` or `STOPPED`, plus failed attempts so far."""

    step: str
    attempts: int = 0
    note: str = ""

    @property
    def final(self) -> bool:
        return self.step in (DONE, STOPPED)


def start(process: Sequence[Step]) -> Position:
    return Position(process[0].name)


def advance(
    process: Sequence[Step], position: Position, outcome: Outcome, max_attempts: int
) -> Position:
    """Where the ticket goes after the step at `position` ended with `outcome`."""
    if isinstance(outcome, Stopped):
        return Position(STOPPED, position.attempts, outcome.reason)
    if isinstance(outcome, Failed):
        attempts = position.attempts + 1
        step = STOPPED if attempts >= max_attempts else process[0].name
        return Position(step, attempts, outcome.reason)
    names = [step.name for step in process]
    following = names.index(position.step) + 1
    step = names[following] if following < len(names) else DONE
    return Position(step, position.attempts)
