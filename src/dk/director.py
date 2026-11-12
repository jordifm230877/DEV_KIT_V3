"""The director: the only piece that decides what happens next to a ticket.

It reads the ticket list, carries out the step each ticket is waiting for, and moves the
ticket according to the process. It never talks to a model or touches Git itself.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from dk import agents, briefs, checks
from dk.config import Config
from dk.process import PROCESS, Failed, Outcome, Passed, Position, Step, Stopped, advance
from dk.tickets import Ticket, Tickets
from dk.workspace import Workspace


@dataclass(frozen=True)
class Director:
    config: Config
    tickets: Tickets
    workspace: Workspace
    logs: Path
    say: Callable[[str], None]

    def run(self) -> None:
        """Take every unfinished ticket, in order, as far as it can go."""
        for ticket in self.tickets.all():
            position = Position(ticket.step, ticket.attempts, ticket.note)
            while not position.final:
                step = next(step for step in PROCESS if step.name == position.step)
                outcome = self._perform(step, ticket, position)
                position = advance(PROCESS, position, outcome, self.config.max_attempts)
                self.tickets.move(ticket.id, position.step, position.attempts, position.note)
                self._report(ticket, step, outcome, position)

    def _report(self, ticket: Ticket, step: Step, outcome: Outcome, position: Position) -> None:
        result = type(outcome).__name__.lower()
        reason = "" if isinstance(outcome, Passed) else f": {outcome.reason}"
        self.tickets.record(ticket.id, f"{step.name} {result}{reason}")
        self.say(f"#{ticket.id} {step.name} {result} -> {position.step}")

    def _perform(self, step: Step, ticket: Ticket, position: Position) -> Outcome:
        logs = self.logs / f"ticket-{ticket.id}" / f"attempt-{position.attempts + 1}"
        if step.kind == "agent":
            return self._work(step, ticket, position, logs)
        if step.kind == "checks":
            seconds = self.config.check_minutes * 60
            failure = checks.run(
                self.config.checks, self.workspace.prepare(ticket.id), logs, seconds
            )
            return Failed(failure) if failure else Passed()
        trouble = self.workspace.merge(ticket.id, ticket.title)
        return Stopped(trouble) if trouble else Passed()

    def _work(self, step: Step, ticket: Ticket, position: Position, logs: Path) -> Outcome:
        agent = self.config.with_role(step.role)
        argv = agent.command or agents.command(agent.program, agent.model)
        instructions = briefs.coder(ticket.id, ticket.title, ticket.spec, position.note)
        copy = self.workspace.prepare(ticket.id)
        self.tickets.record(ticket.id, f"{agent.name} started")
        reply = agents.ask(
            argv, instructions, copy, logs / f"{agent.name}.log", self.config.agent_minutes * 60
        )
        if reply.kind == "unclear":
            return Failed(f"{agent.name} ended without a clear answer")
        if reply.kind != "done":
            return Stopped(f"{reply.kind}: {reply.text}")
        if not self.workspace.save(ticket.id, f"Ticket #{ticket.id}: {ticket.title}"):
            return Failed(f"{agent.name} said it was done but changed nothing")
        return Passed()
