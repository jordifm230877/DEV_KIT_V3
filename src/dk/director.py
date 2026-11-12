"""The director: the only piece that decides what happens next to a ticket.

It reads the ticket list, carries out the step each ticket is waiting for, and moves the
ticket according to the process. It never talks to a model or touches Git itself.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from queue import Queue

from dk import agents, briefs, checks
from dk.config import Agent, Config, ConfigError
from dk.process import (
    CANCELLED,
    PROCESS,
    Failed,
    Lost,
    Outcome,
    Passed,
    Position,
    Skipped,
    Step,
    Stopped,
    advance,
    held_by,
)
from dk.tickets import Ticket, Tickets
from dk.workspace import Workspace

BEHAVIOUR_TESTS = "*.feature"
PRINCIPAL = "principal"  # the one role that talks with the user instead of taking jobs


_LOOK_EVERY = 0.05


def _unclear(agent: Agent, reply: agents.Reply) -> Lost:
    last = f"; it last said: {reply.text}" if reply.text else ""
    return Lost(f"{agent.name} ended without a clear answer{last}")


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

    _free: dict[str, Queue[Agent]] = field(default_factory=dict)
    _merging: threading.Lock = field(default_factory=threading.Lock)

    def run(self, keep_going: bool = False) -> None:
        """Take every unfinished ticket as far as it can go, as many at once as there are
        coders. Each agent does one job at a time; merges happen one at a time.

        With `keep_going`, wait for tickets to be written or sent on, until `stop` is set."""
        for agent in self.config.agents:
            self._free.setdefault(agent.role, Queue()).put(agent)
        coders = len(self.config.with_role("coder"))
        with ThreadPoolExecutor(max(coders, 1)) as together:
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
        steps = {ticket.id: ticket.step for ticket in tickets}
        for ticket in tickets:
            waiting = _position(ticket).final or held_by(ticket.follows, steps)
            if ticket.id not in active and not waiting:
                active[ticket.id] = together.submit(self._drive, ticket)

    def _drive(self, ticket: Ticket) -> None:
        position = _position(ticket)
        while not position.final and not self.stop.is_set():
            step = next(step for step in PROCESS if step.name == position.step)
            outcome = self._perform(step, ticket, position)
            if self.stop.is_set() or self.tickets.get(ticket.id).step == CANCELLED:
                return  # work cut short or no longer wanted is thrown away, not judged
            position = advance(PROCESS, position, outcome, self.config.max_attempts)
            self.tickets.move(ticket.id, *vars(position).values())
            if not isinstance(outcome, Passed):
                self.tickets.record(ticket.id, f"{step.name}: {outcome.reason}")
            self.say(f"#{ticket.id} {step.name} {type(outcome).__name__.lower()}")
            if position.stopped:
                self.notify(f"#{ticket.id} {ticket.title} needs you", position.note)

    def _perform(self, step: Step, ticket: Ticket, position: Position) -> Outcome:
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
        job = {"tester": self._specify, "coder": self._code}.get(step.role, self._review)
        agent = self._free[step.role].get()
        try:
            return job(agent, self.tickets.get(ticket.id), position)
        finally:
            self._free[step.role].put(agent)

    def _check(self, ticket: Ticket, logs: Path) -> Outcome:
        copy = self.workspace.prepare(ticket.id)
        seconds = self.config.check_minutes * 60
        failure = checks.run(self.config.checks, copy, logs, seconds, self.stop)
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
            agent.name: self.logs / f"{agent.name}.log"
            for agent in self.config.agents
            if agent.role != PRINCIPAL
        }

    def _ask(self, agent: Agent, writes: bool, brief: str, ticket: Ticket) -> agents.Reply:
        argv = agent.command or agents.command(agent.program, agent.model, writes)
        copy = self.workspace.prepare(ticket.id)
        self.tickets.record(ticket.id, f"{agent.name} started")
        return agents.ask(
            argv,
            brief,
            copy,
            self.shown()[agent.name],
            self.config.agent_minutes * 60,
            title=f"#{ticket.id} {ticket.title} ({ticket.step})",
            plain=agents.reader(agent.program),
            stop=self.stop,
            name=agent.name,
        )

    def _fresh(self, ticket: Ticket, note: str) -> str:
        """Bring into the copy what the project gained since it was made. Returns the note
        for whoever works next, with the files to resolve if the two collide."""
        self.workspace.prepare(ticket.id)
        _, clashes = self.workspace.update(ticket.id)
        return f"{note}\n{briefs.clash(clashes)}".strip() if clashes else note

    def _produce(self, agent: Agent, brief: str, ticket: Ticket) -> Outcome:
        reply = self._ask(agent, True, brief, ticket)
        if reply.kind in ("blocked", "question"):
            return Stopped(f"{reply.kind}: {reply.text}")
        if reply.kind != "done":
            return _unclear(agent, reply)
        if not self.workspace.save(ticket.id, f"Ticket #{ticket.id}: {ticket.title}"):
            return Failed(f"{agent.name} said it was done but changed nothing")
        return Passed()

    def _specify(self, agent: Agent, ticket: Ticket, position: Position) -> Outcome:
        note = self._fresh(ticket, position.note)
        earlier = sorted(ticket.protected)
        brief = briefs.tester(ticket.id, ticket.title, ticket.spec, note, earlier)
        outcome = self._produce(agent, brief, ticket)
        if not isinstance(outcome, Passed):
            return outcome
        tests = self.workspace.fingerprints(ticket.id, BEHAVIOUR_TESTS)
        if not tests:
            return Failed(f"{agent.name} wrote no behaviour tests ({BEHAVIOUR_TESTS} files)")
        self.tickets.protect(ticket.id, tests)
        return Passed()

    def _code(self, agent: Agent, ticket: Ticket, position: Position) -> Outcome:
        tests = ticket.protected
        note = self._fresh(ticket, position.note)
        brief = briefs.coder(ticket.id, ticket.title, ticket.spec, note, sorted(tests))
        outcome = self._produce(agent, brief, ticket)
        changed = self.workspace.tampered(ticket.id, tests) if tests else []
        if isinstance(outcome, Passed) and changed:
            self.workspace.put_back(ticket.id, tests, changed)
            return Failed(briefs.tampering(changed))
        return outcome

    def _review(self, agent: Agent, ticket: Ticket, position: Position) -> Outcome:
        base = self.workspace.base(ticket.id)
        brief = briefs.reviewer(
            agent.role, ticket.id, ticket.title, ticket.spec, base, bool(ticket.protected)
        )
        reply = self._ask(agent, False, brief, ticket)
        self.workspace.restore(ticket.id)
        if reply.kind in ("blocked", "question"):
            return Stopped(f"{reply.kind}: {reply.text}")
        if reply.kind == "rejected":
            return Failed(f"{agent.name} rejected the work: {reply.text}")
        if reply.kind != "approved":
            return _unclear(agent, reply)
        return Passed()
