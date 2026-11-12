"""The development process as a list of steps, and the rules for moving along it.

Pure: no files, no programs, no clock. Changing the process means changing `PROCESS`.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Literal

DONE = "done"


@dataclass(frozen=True)
class Step:
    """`work` produces something, `review` judges it; the rest are done by the program."""

    name: str
    kind: Literal["work", "review", "checks", "merge"]
    role: str = ""
    required: bool = False  # a step whose role nobody has is skipped, unless required


PROCESS: tuple[Step, ...] = (
    Step("code", "work", "coder", required=True),
    Step("check", "checks"),
    Step("verify", "review", "verifier"),
    Step("qa", "review", "qa"),
    Step("merge", "merge"),
)


@dataclass(frozen=True)
class Passed:
    """The step is complete; the ticket moves on."""


@dataclass(frozen=True)
class Failed:
    """The work is not good enough; it goes back to whoever produced it."""

    reason: str


@dataclass(frozen=True)
class Lost:
    """The step produced nothing usable; the same step is done again."""

    reason: str


@dataclass(frozen=True)
class Stopped:
    """Only the user can decide what happens next."""

    reason: str


Outcome = Passed | Failed | Lost | Stopped


@dataclass(frozen=True)
class Position:
    """Where a ticket is: a step name or `DONE`, the failed attempts so far, and a note
    for whoever takes the step next. A stopped ticket waits at its step for the user."""

    step: str
    attempts: int = 0
    note: str = ""
    stopped: bool = False

    @property
    def final(self) -> bool:
        return self.stopped or self.step == DONE


def start(process: Sequence[Step]) -> Position:
    return Position(process[0].name)


def _rework(process: Sequence[Step], step: str) -> str:
    """The nearest step, at or before `step`, where work is produced."""
    names = [candidate.name for candidate in process]
    earlier = process[: names.index(step) + 1]
    return [candidate.name for candidate in earlier if candidate.kind == "work"][-1]


def advance(
    process: Sequence[Step], position: Position, outcome: Outcome, max_attempts: int
) -> Position:
    """Where the ticket goes after the step at `position` ended with `outcome`."""
    if isinstance(outcome, Stopped):
        return replace(position, note=outcome.reason, stopped=True)
    if isinstance(outcome, Passed):
        names = [step.name for step in process]
        following = names.index(position.step) + 1
        return Position(names[following] if following < len(names) else DONE, position.attempts)
    attempts = position.attempts + 1
    spent = attempts >= max_attempts
    if isinstance(outcome, Lost):
        note = outcome.reason if spent else position.note
        return Position(position.step, attempts, note, spent)
    return Position(_rework(process, position.step), attempts, outcome.reason, spent)


def retry(position: Position, answer: str) -> Position:
    """The user sends a stopped ticket on again, with a fresh set of attempts."""
    note = f"{position.note}\nThe user answers: {answer}" if answer else position.note
    return Position(position.step, 0, note)
