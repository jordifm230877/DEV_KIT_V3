"""What the user, or the Principal for them, asks about an epic: say what it is for, close
it, open it again, trust it.

A composer: it reads the process and writes the ticket list. It starts nothing.
"""

from __future__ import annotations

import os

from dk import agents, forms, process
from dk.tickets import Ticket, Tickets


def close(tickets: Tickets, epic: str, suite: bool) -> None:
    """Mark an epic as complete; only one whose tickets are all merged or given up. Where
    the project has a whole test suite (`suite`), write its run instead, which closes it."""
    inside = [ticket for ticket in tickets.all() if epic and ticket.epic == epic]
    if not inside:
        raise LookupError(f"there is no epic '{epic}'")
    unfinished = [t for t in inside if t.step not in (process.DONE, process.CANCELLED)]
    if unfinished:
        raise LookupError(f"#{unfinished[0].id} is not finished")
    if suite:
        wanted = f"Run the project's whole test suite; {epic} closes when it passes."
        number = tickets.add(f"Close {epic}", wanted, process.CLOSING[0].name, epic, [])
        print(f"#{number} written; {epic} closes when the whole test suite passes")
        return
    tickets.close(epic)
    print(f"{epic} closed")


def reopen(tickets: Tickets, epic: str) -> None:
    if epic not in tickets.closed():
        raise LookupError(f"epic '{epic}' is not closed")
    tickets.reopen(epic)
    print(f"{epic} open again")


def trust(tickets: Tickets, epic: str, given: bool) -> None:
    """The user trusts an epic, or no longer does; with no epic, say which are trusted.
    Tickets of it that wait for approval are taken up again, to go on as the rest will."""
    if not epic:
        return print(*sorted(tickets.trusted()) or ["no epic is trusted"], sep="\n")
    if os.environ.get(agents.WHO):
        raise LookupError("only the user can trust an epic; ask them to run this themselves")
    inside = [ticket for ticket in tickets.all() if ticket.epic == epic]
    if not inside and epic not in tickets.described():
        raise LookupError(f"there is no epic '{epic}'")
    tickets.trust(epic, given)
    if not given:
        return print(f"behaviour tests of {epic} wait for your approval again")
    _taken_up(tickets, inside)
    print(f"behaviour tests of {epic} that a verifier approves go on without your approval")


def _taken_up(tickets: Tickets, inside: list[Ticket]) -> None:
    """Those of these tickets that wait for the user's approval no longer wait."""
    for ticket in inside:
        position = process.Position(ticket.step, ticket.attempts, ticket.note, ticket.stopped)
        if process.waiting(process.PROCESS, position):
            tickets.move(ticket.id, ticket.step, ticket.attempts, ticket.note, False)


def describe(tickets: Tickets, name: str, spec: str) -> None:
    """Say what an epic is for, or show what was said."""
    if spec:
        tickets.describe(name, forms.formed(spec, forms.EPIC, os.environ.get(agents.WHO, "")))
        print(f"{name} described")
    elif name in tickets.described():
        print(tickets.described()[name])
    else:
        raise LookupError(f"epic '{name}' has no description")
