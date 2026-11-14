"""The jobs agents are given on a ticket: what each is told, and what its answer means.

It asks the agent, saves or throws away what it left in the ticket's copy, and says how the
step ended. It never decides where the ticket goes next.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from dk import agents, briefs
from dk.config import Agent, Config
from dk.process import Failed, Lost, Outcome, Passed, Position, Skipped, Stopped
from dk.tickets import Ticket, Tickets
from dk.workspace import Workspace

BEHAVIOUR_TESTS = "*.feature"
PRINCIPAL = "principal"  # the one role that talks with the user instead of taking jobs
FORUM = "team_forum"  # where the Principal's look at stopped tickets is shown


def _unclear(agent: Agent, reply: agents.Reply) -> Lost:
    last = f"; it last said: {reply.text}" if reply.text else ""
    return Lost(f"{agent.name} ended without a clear answer{last}")


def report(title: str) -> str:
    """Where in the project the report of an audit with this title is written."""
    return f"docs/audits/{date.today()}-{title.lower().replace(' ', '-')}.md"


def label(agent: Agent) -> str:
    return FORUM if agent.role == PRINCIPAL else agent.name


@dataclass
class Jobs:
    config: Config
    tickets: Tickets
    workspace: Workspace
    logs: Path
    stop: threading.Event

    def log(self, agent: Agent) -> Path:
        """The file that fills with what the agent is doing."""
        return self.logs / f"{label(agent)}.log"

    def ask(self, agent: Agent, writes: bool, brief: str, ticket: Ticket) -> agents.Reply:
        argv = agent.command or agents.command(agent.program, agent.model, writes, self.config.web)
        copy = self.workspace.prepare(ticket.id)
        self.tickets.record(ticket.id, f"{agent.name} started")
        self.tickets.assign(ticket.id, agent.name)
        try:
            return agents.ask(
                *(argv, brief, copy, self.log(agent)),
                self.config.agent_minutes * 60,
                title=f"#{ticket.id} {ticket.title} ({ticket.step})",
                plain=agents.reader(agent.program),
                stop=self.stop,
                name=agent.name,
            )
        finally:
            self.tickets.assign(ticket.id, "")

    def _fresh(self, ticket: Ticket, note: str) -> str:
        """Bring into the copy what the project gained since it was made. Returns the note
        for whoever works next, with the files to resolve if the two collide."""
        self.workspace.prepare(ticket.id)
        _, clashes = self.workspace.update(ticket.id)
        return f"{note}\n{briefs.clash(clashes)}".strip() if clashes else note

    def _produce(self, agent: Agent, brief: str, ticket: Ticket, only: str = "") -> Outcome:
        """Have the agent do work and save it; with `only`, nothing but that one file."""
        reply = self.ask(agent, True, brief, ticket)
        if only:
            self.workspace.keep_only(ticket.id, only)
        if reply.kind in ("blocked", "question"):
            return Stopped(f"{reply.kind}: {reply.text}")
        if reply.kind != "done":
            return _unclear(agent, reply)
        if not self.workspace.save(ticket.id, f"Ticket #{ticket.id}: {ticket.title}"):
            missing = f"wrote no report at {only}" if only else "changed nothing"
            return Failed(f"{agent.name} said it was done but {missing}")
        return Passed()

    def audit(self, agent: Agent, ticket: Ticket, position: Position) -> Outcome:
        """Have the project looked over; of what the auditor leaves, only its report is kept."""
        where = report(ticket.title)
        tools = self.config.audit_tools
        brief = briefs.auditor(ticket.id, ticket.title, ticket.spec, position.note, where, tools)
        return self._produce(agent, brief, ticket, where)

    def specify(self, agent: Agent, ticket: Ticket, position: Position) -> Outcome:
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

    def code(self, agent: Agent, ticket: Ticket, position: Position) -> Outcome:
        tests = ticket.protected
        note = self._fresh(ticket, position.note)
        brief = briefs.coder(
            ticket.id, ticket.title, ticket.spec, note, sorted(tests), self.config.quality_rules
        )
        outcome = self._produce(agent, brief, ticket)
        changed = self.workspace.tampered(ticket.id, tests) if tests else []
        if isinstance(outcome, Passed) and changed:
            self.workspace.put_back(ticket.id, tests, changed)
            return Failed(briefs.tampering(changed))
        return outcome

    def vet(self, agent: Agent, ticket: Ticket, position: Position) -> Outcome:
        """Have the behaviour tests looked over before the user is asked to approve them."""
        if not ticket.protected:
            return Skipped()
        tests = sorted(ticket.protected)
        brief = briefs.vetting(ticket.id, ticket.title, ticket.spec, tests)
        return self._judge(agent, brief, ticket, "behaviour tests")

    def review(self, agent: Agent, ticket: Ticket, position: Position) -> Outcome:
        base = self.workspace.base(ticket.id)
        brief = briefs.reviewer(
            *(agent.role, ticket.id, ticket.title, ticket.spec, base),
            *(bool(ticket.protected), self.config.quality_rules),
        )
        return self._judge(agent, brief, ticket, "work")

    def _judge(self, agent: Agent, brief: str, ticket: Ticket, what: str) -> Outcome:
        reply = self.ask(agent, False, brief, ticket)
        self.workspace.restore(ticket.id)
        if reply.kind in ("blocked", "question"):
            return Stopped(f"{reply.kind}: {reply.text}")
        if reply.kind == "rejected":
            return Failed(f"{agent.name} rejected the {what}: {reply.text}")
        if reply.kind != "approved":
            return _unclear(agent, reply)
        return Passed()
