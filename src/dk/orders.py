"""What the user, or the Principal for them, asks of the ticket list with a command: write a
ticket, send one on, give it up, close an epic, decide on what waits.

A composer: it reads the settings and the process and writes the ticket list. It starts nothing.
"""

from __future__ import annotations

import argparse
import os
import re
from collections.abc import Callable
from pathlib import Path

from dk import agents, audits, config, jobs, process
from dk.process import CANCELLED
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


def _answer(tickets: Tickets, number: int, accepted: bool, reason: str, tests: bool) -> None:
    """The user's word on a proposed ticket: it becomes a ticket like any other, or is given up."""
    first = process.start(process.PROCESS) if accepted else process.Position(CANCELLED)
    tickets.move(number, *vars(first).values())
    if not accepted:
        tickets.record(number, f"turned down by the user: {reason}")
        print(f"#{number} turned down")
        return
    tickets.record(number, "accepted by the user")
    if not tests:
        tickets.untested(number)
        tickets.record(number, "no behaviour tests: decided when the ticket was accepted")
    print(f"#{number} accepted; it will start at {first.step} on the next run")


def decide(tickets: Tickets, number: int, approved: bool, reason: str, tests: bool = True) -> None:
    if os.environ.get(agents.WHO):
        raise LookupError("only the user can approve or reject; ask them to run this themselves")
    if tickets.get(number).step == process.PROPOSED:
        return _answer(tickets, number, approved, reason, tests)
    if not tests:
        raise LookupError(f"#{number} is not a proposal; --no-behaviour-tests is for accepting one")
    _behaviour_tests(tickets, number, approved, reason)


def _behaviour_tests(tickets: Tickets, number: int, approved: bool, reason: str) -> None:
    """The user's word on behaviour tests: they are approved, or go back to their writer."""
    ticket, position = _stopped(tickets, number)
    if approved and not process.waiting(process.PROCESS, position):
        raise LookupError(
            f"#{number} is not waiting for your approval; "
            f'answer what stopped it with: dk retry {number} --note "..."'
        )
    if not approved and not ticket.protected:
        raise LookupError(f"#{number} has no behaviour tests to send back")
    decide = process.approve if approved else process.send_back
    decided = decide(process.PROCESS, position)
    tickets.move(number, *vars(decided).values())
    _said(tickets, number, "approved" if approved else "rejected", reason)
    print(f"#{number} will continue at {decided.step} on the next run")


def _open(tickets: Tickets, epic: str) -> None:
    if epic in tickets.closed():
        raise LookupError(f"epic '{epic}' is closed; put the ticket in another epic")


def propose(args: argparse.Namespace, tickets: Tickets) -> None:
    """Suggest a ticket; whoever does is named, with the ticket they were on when they did,
    whose epic it joins unless another is given."""
    _open(tickets, args.epic)
    who = os.environ.get(agents.WHO, "")
    on = [ticket for ticket in tickets.all() if who and ticket.worker == who][:1]
    epic = args.epic or "".join(ticket.epic for ticket in on)
    number = tickets.add(args.title, args.spec, process.PROPOSED, epic, [])
    during = "".join(f" while on #{ticket.id} {ticket.title}" for ticket in on)
    tickets.record(number, f"proposed by {who or 'the user'}{during}")
    print(f"#{number} proposed; it waits for the user to accept it or turn it down")


TICKET = ("Wanted:", "Acceptance criteria:", "Out of scope:")
EPIC = ("Goal:", "Includes:", "Excludes:")


def _formed(text: str, headings: tuple[str, ...]) -> str:
    """What an agent wrote, laid out under the headings every such text has. The user
    writes as they like; an agent is refused a text that lacks a part."""
    if not os.environ.get(agents.WHO):
        return text
    first, *rest = re.split("(" + "|".join(map(re.escape, headings)) + ")", text)
    said = [body.strip() for body in rest[1::2]]
    if first.strip() or tuple(rest[::2]) != headings or not all(said):
        raise LookupError(f"write it as `{_form(headings)}`: each once, in this order, none empty")
    return "\n\n".join(f"{heading}\n{body}" for heading, body in zip(headings, said, strict=True))


def _form(headings: tuple[str, ...]) -> str:
    return " ".join(f"{heading} ..." for heading in headings)


def epic(tickets: Tickets, name: str, spec: str) -> None:
    """Say what an epic is for, or show what was said."""
    if spec:
        tickets.describe(name, _formed(spec, EPIC))
        print(f"{name} described")
    elif name in tickets.described():
        print(tickets.described()[name])
    else:
        raise LookupError(f"epic '{name}' has no description")


def add(args: argparse.Namespace, tickets: Tickets) -> None:
    _open(tickets, args.epic)
    spec = _formed(args.spec, TICKET)
    if os.environ.get(agents.WHO) and args.epic and args.epic not in tickets.described():
        raise LookupError(
            f'say first what the epic is for: epic "{args.epic}" --spec "{_form(EPIC)}"'
        )
    first = process.start(process.PROCESS).step
    tests = not args.no_behaviour_tests
    number = tickets.add(args.title, spec, first, args.epic, args.after, tests)
    if args.no_behaviour_tests:
        tickets.record(number, "no behaviour tests: decided when the ticket was written")
    print(f"#{number} written")


def auditor(project: Path) -> None:
    """Refuse when the project has nobody to carry out an audit."""
    role = process.AUDIT[0].role
    if not config.load(project).with_role(role):
        raise config.ConfigError(f"no agent has the role '{role}'")


def audit(kind: str, note: str, project: Path, tickets: Tickets) -> None:
    auditor(project)
    title = _audit_title(kind)
    spec = f"{audits.AUDITS[kind]}\n{note}".strip()
    number = tickets.add(title, spec, process.AUDIT[0].name, "", [])
    print(f"#{number} written; its report will be {jobs.report(title)}")


def _audit_title(kind: str) -> str:
    return f"{kind.capitalize()} audit"


def night(project: Path, tickets: Tickets, changed: Callable[[str], bool]) -> None:
    """Write an audit of every kind, except one still unfinished or one whose last report
    the project has not changed since; `changed` says so for a pattern of report files."""
    for kind in audits.AUDITS:
        title = _audit_title(kind)
        unfinished = [
            ticket.id
            for ticket in tickets.all()
            if ticket.title == title and ticket.step not in (process.DONE, CANCELLED)
        ]
        if unfinished:
            print(f"{title}: #{unfinished[0]} is still unfinished")
        elif not changed(jobs.report(title, "*")):
            print(f"{title}: nothing changed since its last report")
        else:
            audit(kind, "", project, tickets)
