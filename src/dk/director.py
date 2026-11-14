"""The director: the only piece that decides what happens next to a ticket.

It reads the ticket list, carries out the step each ticket is waiting for, and moves the
ticket according to the process. It never talks to a model or touches Git itself.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Collection
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field, replace
from pathlib import Path
from queue import Empty, Queue

from dk import briefs, checks, principal
from dk.config import Agent, Config, ConfigError
from dk.jobs import PRINCIPAL, Jobs, label
from dk.process import (
    CANCELLED,
    Failed,
    Outcome,
    Passed,
    Position,
    Skipped,
    Step,
    Stopped,
    advance,
    held_by,
    of,
    preparing,
    retry,
)
from dk.tickets import Ticket, Tickets
from dk.workspace import Workspace

_LOOK_EVERY = 0.05


def _position(ticket: Ticket) -> Position:
    return Position(ticket.step, ticket.attempts, ticket.note, ticket.stopped)


@dataclass(frozen=True)
class Director:
    config: Config
    tickets: Tickets
    workspace: Workspace
    logs: Path
    say: Callable[[str], None]

    notify: Callable[[str, str], object] = lambda title, body: None
    stop: threading.Event = field(default_factory=threading.Event)
    command: str = "dk"  # how an agent reaches this program

    _free: dict[str, Queue[Agent]] = field(default_factory=dict)
    _merging: threading.Lock = field(default_factory=threading.Lock)

    @property
    def jobs(self) -> Jobs:
        return Jobs(self.config, self.tickets, self.workspace, self.logs, self.stop, self.command)

    def run(self, keep_going: bool = False) -> None:
        """Take every unfinished ticket as far as it can go: as many are built at once as
        there are coders, and behaviour tests are prepared meanwhile. Each agent does one job
        at a time; merges happen one at a time.

        With `keep_going`, wait for tickets to be written or sent on, until `stop` is set."""
        for agent in self.config.agents:
            self._free.setdefault(agent.role, Queue()).put(agent)
        with ThreadPoolExecutor(len(self.config.agents) + 1) as together:
            active: dict[int, Future[None]] = {}
            while not self.stop.is_set():
                self._take_up(together, active)
                if not active and not keep_going:
                    break
                time.sleep(_LOOK_EVERY)
        for ticket in self.tickets.all():
            if ticket.step == CANCELLED:
                self.workspace.discard(ticket.id)

    def _take_up(self, together: ThreadPoolExecutor, active: dict[int, Future[None]]) -> None:
        """Start on tickets that can advance and are not being worked on; let go of those
        that have gone as far as they can."""
        for number in [number for number, job in active.items() if job.done()]:
            active.pop(number).result()
        tickets = self.tickets.all()
        for ticket in tickets:
            if self._may_start(ticket, tickets, active):
                ready, agent = self._reserve(ticket)
                if ready:
                    active[ticket.id] = together.submit(self._drive, ticket, agent)

    def _may_start(self, ticket: Ticket, tickets: list[Ticket], active: Collection[int]) -> bool:
        """As many tickets are built at once as there are coders, so that with one coder
        each is built on the one before it; preparing behaviour tests does not count."""
        steps = {other.id: other.step for other in tickets}
        waiting = _position(ticket).final or held_by(ticket.follows, steps)
        if ticket.id in active or waiting or len(active) > len(self.config.agents):
            return False
        roles = self._free.keys()
        building = sum(not preparing(steps[number], roles) for number in active)
        coders = max(len(self.config.with_role("coder")), 1)
        return preparing(ticket.step, roles) or building < coders

    def _reserve(self, ticket: Ticket) -> tuple[bool, Agent | None]:
        """Whether the ticket's step can start now, and the agent taken for it if it needs
        one. Taken here, in the order of the tickets, so that the earliest ticket goes first."""
        step = next(step for step in of(ticket.step) if step.name == ticket.step)
        if step.kind not in ("work", "review") or step.role not in self._free:
            return True, None
        try:
            return True, self._free[step.role].get_nowait()
        except Empty:
            return False, None

    def _drive(self, ticket: Ticket, agent: Agent | None) -> None:
        position = _position(ticket)
        helped = False  # the Principal answers a stop once; after that it is the user's
        while not position.final and not self.stop.is_set():
            steps = of(position.step)
            step = next(step for step in steps if step.name == position.step)
            outcome, agent = self._perform(step, ticket, position, agent), None
            if self.stop.is_set() or self.tickets.get(ticket.id).step == CANCELLED:
                return  # work cut short or no longer wanted is thrown away, not judged
            position = advance(steps, position, outcome, self.config.max_attempts)
            self.tickets.move(ticket.id, *vars(position).values())
            if not isinstance(outcome, Passed):
                self.tickets.record(ticket.id, f"{step.name}: {outcome.reason}")
            self.say(f"#{ticket.id} {step.name} {type(outcome).__name__.lower()}")
            if position.stopped:
                position, helped = self._halt(step, ticket, position, helped), True

    def _halt(self, step: Step, ticket: Ticket, position: Position, helped: bool) -> Position:
        """Where a ticket that stopped is left: sent on by the Principal, or with the user."""
        if step.kind != "user" and not helped:
            position = self._consult(ticket.id, position)
        if position.stopped:
            self.notify(f"#{ticket.id} {ticket.title} needs you", position.note)
        return position

    def _consult(self, number: int, position: Position) -> Position:
        """A ticket that stops goes to the Principal first. It sends the ticket on with an
        answer the project already holds, or explains the stop to the user."""
        able = [agent for agent in self.config.with_role(PRINCIPAL) if agent.program]
        if not able:
            return position
        ticket = self.tickets.get(number)
        brief = principal.stopped(
            number, ticket.title, ticket.spec, self.tickets.history(number)[-12:], position.note
        )
        agent = self._free[PRINCIPAL].get()
        try:
            reply = self.jobs.ask(agent, False, brief, ticket)
        finally:
            self._free[PRINCIPAL].put(agent)
        self.workspace.restore(number)
        if reply.kind == "done" and reply.text:
            self.tickets.amend(number, f"The Principal answered: {reply.text}")
            self.tickets.record(number, f"sent on by {agent.name}: {reply.text}")
            position = retry(position)
        elif reply.kind != "unclear":
            self.tickets.record(number, f"{agent.name}: {reply.text}")
            position = replace(position, note=f"{position.note}\n{agent.name}: {reply.text}")
        self.tickets.move(number, *vars(position).values())
        return position

    def _perform(
        self, step: Step, ticket: Ticket, position: Position, agent: Agent | None
    ) -> Outcome:
        logs = self.logs / f"ticket-{ticket.id}" / f"attempt-{position.attempts + 1}"
        if step.kind == "checks":
            return self._check(ticket, logs)
        if step.kind == "merge":
            with self._merging:
                return self._merge(ticket, logs)
        if step.role not in self._free:
            if step.required:
                raise ConfigError(f"no agent has the role '{step.role}'")
            self.tickets.record(ticket.id, f"{step.name} skipped: no {step.role}")
            return Skipped()
        if step.kind == "user":
            return Stopped(briefs.approval(ticket.id))
        work = self.jobs
        jobs = {"specify": work.specify, "vet": work.vet, "code": work.code, "audit": work.audit}
        job = jobs.get(step.name, work.review)
        agent = agent or self._free[step.role].get()
        try:
            return job(agent, self.tickets.get(ticket.id), position)
        finally:
            self._free[step.role].put(agent)

    def _check(self, ticket: Ticket, logs: Path) -> Outcome:
        copy = self.workspace.prepare(ticket.id)
        seconds = self.config.check_minutes * 60

        def starting(name: str) -> None:  # the board shows it as it shows a working agent
            self.tickets.assign(ticket.id, f"check {name}")

        try:
            failure = checks.run(self.config.checks, copy, logs, seconds, self.stop, starting)
        finally:
            self.tickets.assign(ticket.id, "")
        return Failed(failure) if failure else Passed()

    def _merge(self, ticket: Ticket, logs: Path) -> Outcome:
        """Bring in what was merged meanwhile, check the two together, then merge."""
        updated, clashes = self.workspace.update(ticket.id)
        if clashes:
            return Failed(briefs.clash(clashes))
        together = self._check(ticket, logs / "together") if updated else Passed()
        if not isinstance(together, Passed):
            return together
        trouble = self.workspace.merge(ticket.id, ticket.title)
        return Stopped(trouble) if trouble else Passed()

    def shown(self) -> dict[str, Path]:
        """For each agent that is given jobs, the file that fills with what it is doing."""
        return {
            label(agent): self.jobs.log(agent)
            for agent in self.config.agents
            if agent.role != PRINCIPAL or agent.program
        }
