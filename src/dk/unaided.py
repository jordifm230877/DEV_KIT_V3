"""The steps the program carries out itself, with no agent: the checks of a ticket, the
whole test suite when an epic is closed, and the merge.

A composer: it runs the project's checks in the ticket's copy and writes the ticket list.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from dk import briefs, checks
from dk.config import Config
from dk.process import CANCELLED, PROCESS, Failed, Outcome, Passed, Stopped, Waiting, start
from dk.tickets import Ticket, Tickets
from dk.workspace import Workspace


@dataclass(frozen=True)
class Unaided:
    config: Config
    tickets: Tickets
    workspace: Workspace
    stop: threading.Event
    closed: Callable[[str], object]  # told the epic whose suite passed
    merging: threading.Lock  # merges happen one at a time

    def check(self, ticket: Ticket, logs: Path) -> Outcome:
        mine = sorted(self.tickets.get(ticket.id).protected)
        settings, changed = self.config, self.workspace.changed(ticket.id)
        every, said = checks.chosen(
            settings.checks, settings.behaviour, settings.owns, changed, mine
        )
        if said:
            self.tickets.record(ticket.id, said)
        failure = self._checked(ticket, every, logs)
        return Failed(failure) if failure else Passed()

    def suite(self, ticket: Ticket, logs: Path) -> Outcome:
        """Run the whole test suite on the project as it is now; the epic closes if it
        passes, and what fails becomes a ticket of the epic that this run then waits for.

        The copy of a run that failed is kept until the next one, for whoever fixes it: a
        real suite named only a log in its copy, which had been thrown away."""
        self.workspace.discard(ticket.id)
        failure = None
        try:
            failure = self._checked(ticket, self.config.suite, logs)
        finally:
            if not failure:
                self.workspace.discard(ticket.id)
        if self.stop.is_set() or self.tickets.get(ticket.id).step == CANCELLED:
            return Waiting("cut short or given up")  # its result is not judged
        if not failure:
            self.closed(ticket.epic)
            return Passed()
        spec = briefs.suite_failed(ticket.epic, failure, logs, self.workspace.prepare(ticket.id))
        first = start(PROCESS).step
        fix = self.tickets.add(
            "Make the whole test suite pass", spec, first, ticket.epic, [], False
        )
        self.tickets.record(fix, "no behaviour tests: written by the program for a failing suite")
        self.tickets.follow(ticket.id, fix)
        return Waiting(f"the whole test suite failed: #{fix} written")

    def _checked(self, ticket: Ticket, every: dict[str, tuple[str, ...]], logs: Path) -> str | None:
        """Run these checks in the ticket's copy. Returns None, or what failed."""
        copy = self.workspace.prepare(ticket.id)
        seconds = self.config.check_minutes * 60

        def starting(name: str) -> None:  # the board shows it as it shows a working agent
            self.tickets.assign(ticket.id, f"check {name}")

        try:
            return checks.run(every, copy, logs, seconds, self.stop, starting)
        finally:
            self.tickets.assign(ticket.id, "")

    def merge(self, ticket: Ticket, logs: Path) -> Outcome:
        """Bring in what was merged meanwhile, check the two together, then merge; one
        ticket at a time."""
        with self.merging:
            return self._merged(ticket, logs)

    def _merged(self, ticket: Ticket, logs: Path) -> Outcome:
        came, clashes = self.workspace.update(ticket.id)
        if clashes:
            return Failed(briefs.clash(clashes))
        together = self.check(ticket, logs / "together") if checks.concern(came) else Passed()
        if not isinstance(together, Passed):
            return together
        trouble = self.workspace.merge(ticket.id, ticket.title)
        return Stopped(trouble) if trouble else Passed()
