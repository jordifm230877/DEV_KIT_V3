"""What the user or an agent asks to have written in the ticket list: a ticket, a proposal,
a ticket rewritten, a proposal moved to an epic.

A composer: it reads the process and the forms and writes the ticket list. It starts nothing.
"""

from __future__ import annotations

import argparse
import os
from collections.abc import Callable

from dk import agents, forms, process
from dk.tickets import Ticket, Tickets

Write = Callable[[str, str], tuple[str, str]]  # the user's editor: a title and a text, changed


def agent() -> str:
    """The agent that asks, or "" for the user."""
    return os.environ.get(agents.WHO, "")


def _open(tickets: Tickets, epic: str) -> None:
    """Refuse an epic that takes no ticket: a closed one, or one an agent has not described."""
    if epic in tickets.closed():
        raise LookupError(f"epic '{epic}' is closed; put the ticket in another epic")
    if os.environ.get(agents.WHO) and epic and epic not in tickets.described():
        raise LookupError(
            f'say first what the epic is for: epic "{epic}" --spec "{forms.form(forms.EPIC)}"'
        )


def add(args: argparse.Namespace, tickets: Tickets) -> None:
    spec = forms.formed(args.spec, forms.TICKET, agent())
    if os.environ.get(agents.WHO) and not (args.behaviour_tests or args.no_behaviour_tests):
        raise LookupError(
            "say whether a user of the product sees the change: "
            "--behaviour-tests or --no-behaviour-tests"
        )
    if not args.epic:
        raise LookupError(
            'say which epic the ticket belongs to: --epic "NAME"; '
            "`dk propose` writes one that waits for you outside every epic"
        )
    _open(tickets, args.epic)
    tests, first = not args.no_behaviour_tests, process.PROCESS[0].name
    number = tickets.add(args.title, spec, first, args.epic, args.after, tests)
    if args.no_behaviour_tests:
        tickets.record(number, "no behaviour tests: decided when the ticket was written")
    print(f"#{number} written")


def propose(args: argparse.Namespace, tickets: Tickets) -> None:
    """Suggest a ticket; whoever does is named, with the ticket they were on when they did,
    whose epic it joins unless another is given."""
    if args.epic in tickets.closed():
        raise LookupError(f"epic '{args.epic}' is closed; put the ticket in another epic")
    who, spec = agent(), forms.formed(args.spec, forms.TICKET, agent())
    on = [ticket for ticket in tickets.all() if who and ticket.worker == who][:1]
    epic = args.epic or "".join(ticket.epic for ticket in on)
    number = tickets.add(args.title, spec, process.PROPOSED, epic, [])
    during = "".join(f" while on #{ticket.id} {ticket.title}" for ticket in on)
    tickets.record(number, f"proposed by {who or 'the user'}{during}")
    print(f"#{number} proposed; it waits for the user to accept it or turn it down")


def move(tickets: Tickets, number: int, epic: str, allowed: bool) -> None:
    """Put a proposal in an epic, or with "" in none. `allowed` says whether whoever asks
    is the user or the Principal."""
    if not allowed:
        raise LookupError("only the user or the Principal can move a proposal")
    ticket = tickets.get(number)
    if ticket.step != process.PROPOSED:
        raise LookupError(f"#{number} is not a proposal; only a proposal is moved")
    _open(tickets, epic)
    tickets.file(number, epic)
    where = f"to {epic}" if epic else f"out of {ticket.epic or 'no epic'}"
    tickets.record(number, f"moved {where} by {os.environ.get(agents.WHO) or 'the user'}")
    print(f"#{number} moved {where}")


def edit(tickets: Tickets, number: int, title: str, spec: str, write: Write | None) -> None:
    """Rewrite a ticket nobody has worked on; with no new words, in the user's editor (`write`)."""
    old = tickets.get(number)
    if not process.untouched(old.step, old.attempts, old.stopped, old.worker):
        raise LookupError(f"#{number} has been worked on; to add to it: dk retry {number} --note")
    title, spec = _words(old, title, spec, write)
    spec = forms.formed(spec, forms.TICKET, agent()) if spec else old.spec
    tickets.rewrite(number, title or old.title, spec)
    was = f"edited by {agent() or 'the user'}; it said: {old.title}: {old.spec}"
    tickets.record(number, " ".join(was.split()))
    print(f"#{number} edited")


def _words(old: Ticket, title: str, spec: str, write: Write | None) -> tuple[str, str]:
    """The new title and text: those given, or what the user writes in their editor."""
    if title or spec:
        return title, spec
    if agent() or not write:
        raise LookupError("say the new text with --spec, the new title with --title")
    return write(old.title, old.spec)
