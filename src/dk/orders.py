"""What the user, or the Principal for them, asks of the ticket list with a command: write a
ticket, send one on, give it up, close an epic, decide on what waits.

A composer: it reads the settings and the process and writes the ticket list. It starts nothing.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from dk import agents, briefs, config, jobs, process
from dk.tickets import Ticket, Tickets


def _stopped(tickets: Tickets, number: int) -> tuple[Ticket, process.Position]:
    ticket = tickets.get(number)
    if not ticket.stopped:
        raise LookupError(f"#{number} is not stopped")
    return ticket, process.Position(ticket.step, ticket.attempts, ticket.note, ticket.stopped)


def _said(tickets: Tickets, number: int, what: str, words: str) -> None:
    """What the user says about a ticket becomes part of it, for every agent after."""
    if words:
        tickets.amend(number, f"The user added later: {words}")
    tickets.record(number, f"{what} by the user{': ' + words if words else ''}")


def retry(tickets: Tickets, number: int, answer: str) -> None:
    ticket, position = _stopped(tickets, number)
    tickets.move(number, *vars(process.retry(position)).values())
    _said(tickets, number, "sent on", answer)
    print(f"#{number} will continue at {ticket.step} on the next run")


def cancel(tickets: Tickets, number: int) -> None:
    ticket = tickets.get(number)
    position = process.Position(ticket.step, ticket.attempts, ticket.note, ticket.stopped)
    try:
        cancelled = process.cancel(position)
    except LookupError as error:
        raise LookupError(f"#{number} {error}") from None
    tickets.move(number, *vars(cancelled).values())
    tickets.record(number, "cancelled")
    print(f"#{number} cancelled; its unmerged work is thrown away on the next run")


def close(tickets: Tickets, epic: str) -> None:
    """Mark an epic as complete; only one whose tickets are all merged or given up."""
    inside = [ticket for ticket in tickets.all() if epic and ticket.epic == epic]
    if not inside:
        raise LookupError(f"there is no epic '{epic}'")
    unfinished = [t for t in inside if t.step not in (process.DONE, process.CANCELLED)]
    if unfinished:
        raise LookupError(f"#{unfinished[0].id} is not finished")
    tickets.close(epic)
    print(f"{epic} closed")


def reopen(tickets: Tickets, epic: str) -> None:
    if epic not in tickets.closed():
        raise LookupError(f"epic '{epic}' is not closed")
    tickets.reopen(epic)
    print(f"{epic} open again")


def decide(tickets: Tickets, number: int, approved: bool, reason: str) -> None:
    if os.environ.get(agents.WHO):
        raise LookupError("only the user can approve or reject; ask them to run this themselves")
    ticket, position = _stopped(tickets, number)
    if approved and not process.waiting(process.PROCESS, position):
        raise LookupError(f"#{number} is not waiting for your approval")
    if not approved and not ticket.protected:
        raise LookupError(f"#{number} has no behaviour tests to send back")
    decide = process.approve if approved else process.send_back
    decided = decide(process.PROCESS, position)
    tickets.move(number, *vars(decided).values())
    _said(tickets, number, "approved" if approved else "rejected", reason)
    print(f"#{number} will continue at {decided.step} on the next run")


def add(args: argparse.Namespace, tickets: Tickets) -> None:
    if args.epic in tickets.closed():
        raise LookupError(f"epic '{args.epic}' is closed; put the ticket in another epic")
    first = process.start(process.PROCESS, not args.no_behaviour_tests).step
    number = tickets.add(args.title, args.spec, first, args.epic, args.after)
    if args.no_behaviour_tests:
        tickets.record(number, "no behaviour tests: decided when the ticket was written")
    print(f"#{number} written")


def audit(args: argparse.Namespace, project: Path, tickets: Tickets) -> None:
    role = process.AUDIT[0].role
    if not config.load(project).with_role(role):
        raise config.ConfigError(f"no agent has the role '{role}'")
    title = f"{args.kind.capitalize()} audit"
    spec = f"{briefs.AUDITS[args.kind]}\n{args.note}".strip()
    number = tickets.add(title, spec, process.AUDIT[0].name, "", [])
    print(f"#{number} written; its report will be {jobs.report(title)}")
