"""The development process as a list of steps, and the rules for moving along it.

Pure: no files, no programs, no clock. Changing the process means changing `PROCESS`.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Literal

DONE = "done"
CANCELLED = "cancelled"  # the user no longer wants the ticket
PROPOSED = "proposed"  # an agent suggests the ticket; nothing happens until the user accepts


@dataclass(frozen=True)
class Step:
    """`work` produces something, `review` judges it, `user` waits for the user's decision;
    the rest are done by the program."""

    name: str
    kind: Literal["work", "review", "user", "checks", "merge"]
    role: str = ""
    required: bool = False  # a step whose role nobody has is skipped, unless required
    behaviour: bool = False  # about behaviour tests; skipped for a ticket that takes none


PROCESS: tuple[Step, ...] = (
    Step("examine", "review", "examiner"),
    Step("specify", "work", "tester", behaviour=True),
    Step("vet", "review", "verifier", behaviour=True),
    Step("approve", "user", "tester", behaviour=True),
    Step("code", "work", "coder", required=True),
    Step("check", "checks"),
    Step("verify", "review", "verifier"),
    Step("qa", "review", "qa"),
    Step("merge", "merge"),
)
# An audit is carried like a ticket: an auditor writes a report, which joins the project.
AUDIT: tuple[Step, ...] = (
    Step("audit", "work", "auditor", required=True),
    Step("report", "merge"),
)


def of(step: str) -> tuple[Step, ...]:
    """The process that a ticket at this step is going through."""
    return AUDIT if step in [known.name for known in AUDIT] else PROCESS


@dataclass(frozen=True)
class Passed:
    """The step is complete; the ticket moves on."""


@dataclass(frozen=True)
class Skipped(Passed):
    """Nobody is there to do the step; the ticket moves on without it."""


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
    """Where a ticket is: a step name, `DONE` or `CANCELLED`, the failed attempts so far, and a note
    for whoever takes the step next. A stopped ticket waits at its step for the user."""

    step: str
    attempts: int = 0
    note: str = ""
    stopped: bool = False

    @property
    def final(self) -> bool:
        return self.stopped or self.step in (DONE, CANCELLED, PROPOSED)


def start(process: Sequence[Step]) -> Position:
    """Where a new ticket begins."""
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


def retry(position: Position) -> Position:
    """The user sends a stopped ticket on again, with a fresh set of attempts."""
    return Position(position.step, 0, position.note)


def held_by(follows: Sequence[int], steps: Mapping[int, str]) -> list[int]:
    """Which of the tickets this one follows still hold it back; `steps` says where every
    ticket is. A merged ticket no longer does, nor one that was given up."""
    return [number for number in follows if steps[number] not in (DONE, CANCELLED)]


def preparing(step: str, roles: Collection[str], behaviour: bool = True) -> bool:
    """Whether work from this step ends with the user's decision before anything is built;
    `roles` are those somebody has, for a step whose role nobody has is skipped, and so
    are the steps about behaviour tests for a ticket that takes none (`behaviour` false)."""
    names = [one.name for one in PROCESS]
    ahead = PROCESS[names.index(step) :] if step in names else ()
    asked = [one for one in ahead if one.role in roles and (behaviour or not one.behaviour)]
    decisive = (one for one in ahead if one.required or (one.kind == "user" and one in asked))
    return any(one.kind == "user" for one in [*decisive][:1])


def building(step: str, roles: Collection[str], behaviour: bool = True) -> bool:
    """Whether a ticket at this step takes up a coder. An audit does not: counted as one, it
    kept every approved ticket waiting for as long as it lasted."""
    return of(step) is PROCESS and not preparing(step, roles, behaviour)


def cancel(position: Position) -> Position:
    """The ticket is given up, wherever it was; finished work stays finished."""
    if position.step in (DONE, CANCELLED):
        raise LookupError(f"is already {position.step}")
    return Position(CANCELLED, position.attempts)


def waiting(process: Sequence[Step], position: Position) -> bool:
    """Whether the ticket is at a step that is the user's own decision."""
    kinds = {step.name: step.kind for step in process}
    return position.stopped and kinds.get(position.step) == "user"


def approve(process: Sequence[Step], position: Position) -> Position:
    """The user accepts what waits for them; the ticket moves on."""
    return advance(process, replace(position, stopped=False), Passed(), 1)


def send_back(process: Sequence[Step], position: Position) -> Position:
    """The user returns what they were asked to approve, or approved earlier and now find
    wrong, to whoever wrote it. It is the user's choice, not a failed attempt."""
    names = [step.name for step in process]
    asked = [step.name for step in process[: names.index(position.step) + 1] if step.kind == "user"]
    return Position(_rework(process, asked[-1]), position.attempts)
