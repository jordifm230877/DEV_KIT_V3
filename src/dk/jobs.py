"""The jobs agents are given on a ticket: what each is told, and what its answer means.

It asks the agent, saves or throws away what it left in the ticket's copy, and says how the
step ended. It never decides where the ticket goes next.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from dk import agents, audits, briefs, documents, shown, spent
from dk.config import Agent, Config
from dk.process import (
    DONE,
    PROCESS,
    Failed,
    Lost,
    Outcome,
    Passed,
    Position,
    Skipped,
    Stopped,
    of,
)
from dk.tickets import Asking, Ticket, Tickets
from dk.workspace import Workspace

BEHAVIOUR_TESTS = "*.feature"
PRINCIPAL = "principal"  # the one role that talks with the user instead of taking jobs
FORUM = "team_forum"  # where the Principal's look at stopped tickets is shown


def _unclear(agent: Agent, reply: agents.Reply) -> Lost:
    if reply.late:
        limit = "the limit for one job (`minutes` of the agent or `agent_minutes` in devkit.toml)"
        return Lost(f"{agent.name} was {reply.text}, {limit}; what it had done is kept")
    last = f"; it last said: {reply.text}" if reply.text else ""
    return Lost(f"{agent.name} ended without a clear answer{last}")


def report(title: str, day: object = None) -> str:
    """Where in the project the report of an audit with this title is written; with `day`
    "*", the pattern of every such report."""
    return f"docs/audits/{day or date.today()}-{title.lower().replace(' ', '-')}.md"


def label(agent: Agent) -> str:
    return FORUM if agent.role == PRINCIPAL else agent.name


@dataclass
class Jobs:
    config: Config
    tickets: Tickets
    workspace: Workspace
    logs: Path
    stop: threading.Event
    command: str = "dk"  # how an agent reaches this program, to propose a ticket

    def log(self, agent: Agent) -> Path:
        """The file that fills with what the agent is doing."""
        return self.logs / f"{label(agent)}.log"

    def ask(
        self, agent: Agent, writes: bool, brief: str, ticket: Ticket, session: str = ""
    ) -> agents.Reply:
        argv = agent.command or agents.command(
            agent.program, agent.model, writes, self.config.web, session
        )
        copy = self.workspace.prepare(ticket.id)
        self.tickets.record(ticket.id, f"{agent.name} started")
        self.tickets.assign(ticket.id, agent.name)
        count, show = spent.counter(agent.program), shown.reader(agent.program)
        used = [(0, 0)]

        def plain(line: str) -> str:
            if (now := count(line)) != used[-1]:  # the board shows it as it grows
                used.append(now)
                self.tickets.spend(ticket.id, now)
            return show(line)

        try:
            return agents.ask(
                *(argv, brief, copy, self.log(agent)),
                (agent.minutes or self.config.agent_minutes) * 60,
                title=f"#{ticket.id} {ticket.title} ({ticket.step})",
                plain=plain,
                stop=self.stop,
                name=agent.name,
            )
        finally:
            if any(used[-1]):
                self.tickets.record(ticket.id, f"{agent.name} used {spent.said(used[-1])}")
            self.tickets.assign(ticket.id, "")

    def _resumed(
        self, agent: Agent, writes: bool, brief: str, ticket: Ticket, note: str = ""
    ) -> agents.Reply:
        """Ask the agent; if a job was left on this ticket to ask something and the agent's
        program can pick it up, it goes on from there with what was added to the ticket."""
        left = ticket.asking if ticket.asking and ticket.asking.program == agent.program else None
        if left and not agent.command:
            brief = briefs.answered(ticket.spec[left.known :], note)
        reply = self.ask(agent, writes, brief, ticket, left.session if left else "")
        asked = reply.kind in ("blocked", "question") and reply.session
        now = Asking(agent.program, reply.session, len(ticket.spec)) if asked else None
        self.tickets.leave(ticket.id, now)
        return reply

    def _fresh(self, ticket: Ticket, note: str) -> str:
        """Bring into the copy what the project gained since it was made. Returns the note
        for whoever works next, with the files to resolve if the two collide."""
        self.workspace.prepare(ticket.id)
        _, clashes = self.workspace.update(ticket.id)
        return f"{note}\n{briefs.clash(clashes)}".strip() if clashes else note

    def _work(
        self, agent: Agent, brief: str, ticket: Ticket, only: tuple[str, ...] = (), note: str = ""
    ) -> Outcome | None:
        """Have the agent do work; with `only`, nothing but what is at those paths is left
        of it. Returns why the work is not done, or None when the agent says that it is."""
        reply = self._resumed(agent, True, brief, ticket, note)
        if only:
            self.workspace.keep_only(ticket.id, *only)
        if reply.kind in ("blocked", "question"):
            return Stopped(f"{reply.kind}: {reply.text}")
        if reply.kind != "done":
            return _unclear(agent, reply)
        if reply.text:  # for the user and the Principal; no reviewer is shown it
            self.tickets.record(ticket.id, f"{agent.name} noted: {reply.text}")
        return None

    def _saved(self, ticket: Ticket) -> bool:
        """Record what an agent left. Returns whether the ticket has any work to show."""
        return self.workspace.save(ticket.id, f"Ticket #{ticket.id}: {ticket.title}")

    def _produce(
        self, agent: Agent, brief: str, ticket: Ticket, only: str = "", note: str = ""
    ) -> Outcome:
        """Have the agent do work that must leave something; with `only`, that one file."""
        trouble = self._work(agent, brief, ticket, (only,) if only else (), note)
        if trouble or self._saved(ticket):
            return trouble or Passed()
        missing = f"wrote no report at {only}" if only else "changed nothing"
        return Failed(f"{agent.name} said it was done but {missing}")

    def document(self, agent: Agent, ticket: Ticket, position: Position) -> Outcome:
        """Have the documentation brought up to date; of what the documenter leaves, only
        its two folders are kept. Finding nothing to change is a job done."""
        about = briefs.about(ticket.id, ticket.title, ticket.spec, position.note) + briefs.LONG
        brief = documents.brief(about, briefs.ALWAYS)
        trouble = self._work(agent, brief, ticket, documents.FOLDERS)
        if not trouble and not self._saved(ticket):
            self.tickets.record(ticket.id, f"{agent.name} found the documentation up to date")
        return trouble or Passed()

    def audit(self, agent: Agent, ticket: Ticket, position: Position) -> Outcome:
        """Have the project looked over; of what the auditor leaves, only its report is kept."""
        where = report(ticket.title)
        known = [
            other.title
            for other in self.tickets.all()
            if other.step != DONE and of(other.step) is PROCESS
        ]
        about = briefs.about(ticket.id, ticket.title, ticket.spec, position.note) + briefs.LONG
        tools = self.config.audit_tools
        brief = audits.brief(about, where, tools, self.command, known, briefs.ALWAYS)
        return self._produce(agent, brief, ticket, where)

    def specify(self, agent: Agent, ticket: Ticket, position: Position) -> Outcome:
        note = self._fresh(ticket, position.note)
        earlier = sorted(ticket.protected)
        brief = briefs.tester(ticket.id, ticket.title, ticket.spec, note, earlier)
        outcome = self._produce(agent, brief, ticket, note=note)
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
            *(ticket.id, ticket.title, ticket.spec, note, sorted(tests)),
            *(self.config.quality_rules, self.command),
        )
        outcome = self._produce(agent, brief, ticket, note=note)
        changed = self.workspace.tampered(ticket.id, tests) if tests else []
        if isinstance(outcome, Passed) and changed:
            self.workspace.put_back(ticket.id, tests, changed)
            return Failed(briefs.tampering(changed))
        return outcome

    def examine(self, agent: Agent, ticket: Ticket, position: Position) -> Outcome:
        """Have the ticket read before any work; a doubt stops it for whoever can answer."""
        described = self.tickets.described().get(ticket.epic, "")
        about = briefs.about(ticket.id, ticket.title, ticket.spec)
        brief = briefs.examiner(about, ticket.epic, described)
        outcome = self._judge(agent, brief, ticket, "ticket")
        return Stopped(outcome.reason) if isinstance(outcome, Failed) else outcome

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
        reply = self._resumed(agent, False, brief, ticket)
        self.workspace.restore(ticket.id)
        if reply.kind in ("blocked", "question"):
            return Stopped(f"{reply.kind}: {reply.text}")
        if reply.kind == "rejected":
            return Failed(f"{agent.name} rejected the {what}: {reply.text}")
        if reply.kind != "approved":
            return _unclear(agent, reply)
        return Passed()
