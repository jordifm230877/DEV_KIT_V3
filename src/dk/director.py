"""The director: the only piece that decides what happens next to a ticket.

It reads the ticket list, carries out the step each ticket is waiting for, and moves the
ticket according to the process. It never talks to a model or touches Git itself.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from queue import Queue

from dk import agents, briefs, checks
from dk.config import Agent, Config, ConfigError
from dk.process import PROCESS, Failed, Lost, Outcome, Passed, Position, Step, Stopped, advance
from dk.tickets import Ticket, Tickets
from dk.workspace import Workspace


@dataclass(frozen=True)
class Director:
    config: Config
    tickets: Tickets
    workspace: Workspace
    logs: Path
    say: Callable[[str], None]

    _free: dict[str, Queue[Agent]] = field(default_factory=dict)
    _merging: threading.Lock = field(default_factory=threading.Lock)

    def run(self) -> None:
        """Take every unfinished ticket as far as it can go, as many at once as there are
        coders. Each agent does one job at a time; merges happen one at a time."""
        for agent in self.config.agents:
            self._free.setdefault(agent.role, Queue()).put(agent)
        coders = len(self.config.with_role("coder"))
        with ThreadPoolExecutor(max(coders, 1)) as together:
            list(together.map(self._drive, self.tickets.all()))

    def _drive(self, ticket: Ticket) -> None:
        position = Position(ticket.step, ticket.attempts, ticket.note, ticket.stopped)
        while not position.final:
            step = next(step for step in PROCESS if step.name == position.step)
            outcome = self._perform(step, ticket, position)
            position = advance(PROCESS, position, outcome, self.config.max_attempts)
            self.tickets.move(ticket.id, *vars(position).values())
            if not isinstance(outcome, Passed):
                self.tickets.record(ticket.id, f"{step.name}: {outcome.reason}")
            self.say(f"#{ticket.id} {step.name} {type(outcome).__name__.lower()}")

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
            return Passed()
        agent = self._free[step.role].get()
        try:
            if step.kind == "work":
                return self._work(agent, ticket, position, logs)
            return self._review(agent, ticket, logs)
        finally:
            self._free[step.role].put(agent)

    def _check(self, ticket: Ticket, logs: Path) -> Outcome:
        copy = self.workspace.prepare(ticket.id)
        failure = checks.run(self.config.checks, copy, logs, self.config.check_minutes * 60)
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

    def _ask(
        self, agent: Agent, writes: bool, brief: str, ticket: Ticket, logs: Path
    ) -> agents.Reply:
        argv = agent.command or agents.command(agent.program, agent.model, writes)
        copy = self.workspace.prepare(ticket.id)
        self.tickets.record(ticket.id, f"{agent.name} started")
        seconds = self.config.agent_minutes * 60
        return agents.ask(argv, brief, copy, logs / f"{agent.name}.log", seconds)

    def _work(self, agent: Agent, ticket: Ticket, position: Position, logs: Path) -> Outcome:
        brief = briefs.coder(ticket.id, ticket.title, ticket.spec, position.note)
        reply = self._ask(agent, True, brief, ticket, logs)
        if reply.kind in ("blocked", "question"):
            return Stopped(f"{reply.kind}: {reply.text}")
        if reply.kind != "done":
            return Lost(f"{agent.name} ended without a clear answer")
        if not self.workspace.save(ticket.id, f"Ticket #{ticket.id}: {ticket.title}"):
            return Failed(f"{agent.name} said it was done but changed nothing")
        return Passed()

    def _review(self, agent: Agent, ticket: Ticket, logs: Path) -> Outcome:
        base = self.workspace.base(ticket.id)
        brief = briefs.reviewer(agent.role, ticket.id, ticket.title, ticket.spec, base)
        reply = self._ask(agent, False, brief, ticket, logs)
        self.workspace.restore(ticket.id)
        if reply.kind in ("blocked", "question"):
            return Stopped(f"{reply.kind}: {reply.text}")
        if reply.kind == "rejected":
            return Failed(f"{agent.name} rejected the work: {reply.text}")
        if reply.kind != "approved":
            return Lost(f"{agent.name} ended without a clear answer")
        return Passed()
