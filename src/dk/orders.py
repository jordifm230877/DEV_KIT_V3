"""What the user, or the Principal for them, asks of the ticket list with a command: write a
ticket, send one on, give it up, close an epic, decide on what waits.

A composer: it reads the process and writes the ticket list, and takes out of a ticket's
copy the behaviour tests it is to go on without. It starts nothing.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import os
from collections.abc import Callable

from dk import agents, forms, process
from dk.jobs import BEHAVIOUR_TESTS
from dk.process import CANCELLED
from dk.tickets import Ticket, Tickets
from dk.workspace import Workspace

Write = Callable[[str, str], tuple[str, str]]  # the user's editor: a title and a text, changed


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


def retry(tickets: Tickets, number: int, answer: str, drafts: Workspace | None = None) -> None:
    """Send a stopped ticket on; given the copies as `drafts`, as one that takes no
    behaviour tests."""
    ticket, position = _stopped(tickets, number)
    if drafts:
        _untested(tickets, ticket, drafts)
    tickets.move(number, *vars(process.retry(position)).values())
    _said(tickets, number, "sent on", answer)
    how = "without behaviour tests" if drafts else f"at {ticket.step}"
    print(f"#{number} will continue {how} on the next run")


def _untested(tickets: Tickets, ticket: Ticket, drafts: Workspace) -> None:
    """Have the ticket go on to the coder with no behaviour tests, and none kept read-only:
    what its test-writer wrote before was never approved, and leaves the ticket's copy."""
    if not process.unapproved(ticket.step):
        raise LookupError(
            f"#{ticket.id} is past its behaviour tests; "
            f'approved ones change only with: dk reject {ticket.id} --note "..."'
        )
    drafts.forget(ticket.id, BEHAVIOUR_TESTS)
    tickets.untested(ticket.id)
    tickets.protect(ticket.id, {})
    tickets.record(ticket.id, "no behaviour tests: decided when the ticket was sent on")


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
    for ticket in inside:
        position = process.Position(ticket.step, ticket.attempts, ticket.note, ticket.stopped)
        if process.waiting(process.PROCESS, position):
            tickets.move(ticket.id, ticket.step, ticket.attempts, ticket.note, False)
    print(f"behaviour tests of {epic} that a verifier approves go on without your approval")


def _answer(tickets: Tickets, number: int, accepted: bool, reason: str, tests: bool) -> None:
    """The user's word on a proposed ticket: it becomes a ticket like any other, or is given up.
    That it takes no behaviour tests is written before it becomes one: a run that is going
    takes the ticket up at once, as it then is."""
    first = process.start(process.PROCESS) if accepted else process.Position(CANCELLED)
    if accepted and not tickets.get(number).epic:
        raise LookupError(
            f'#{number} is in no epic; put it in one first: dk move {number} --epic "NAME"'
        )
    if accepted and not tests:
        tickets.untested(number)
    tickets.move(number, *vars(first).values())
    if not accepted:
        tickets.record(number, f"turned down by the user: {reason}")
        print(f"#{number} turned down")
        return
    tickets.record(number, "accepted by the user")
    if not tests:
        tickets.record(number, "no behaviour tests: decided when the ticket was accepted")
    print(f"#{number} accepted; it will start at {first.step} on the next run")


def decide(
    tickets: Tickets,
    number: int,
    approved: bool,
    reason: str,
    tests: bool = True,
    told: bool = False,
) -> None:
    """The user's word on what waits for them. In the conversation the Principal may pass
    it on (`told`), since the user is there; an agent on a job decides nothing."""
    who = os.environ.get(agents.WHO)
    if who and not told:
        raise LookupError("only the user can approve or reject; ask them to run this themselves")
    if tickets.get(number).step == process.PROPOSED:
        _answer(tickets, number, approved, reason, tests)
    elif not tests:
        raise LookupError(f"#{number} is not a proposal; --no-behaviour-tests is for accepting one")
    else:
        _behaviour_tests(tickets, number, approved, reason)
    if who:
        tickets.record(number, f"passed on by {who} in the conversation, on the user's word")


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
    """Refuse an epic that takes no ticket: a closed one, or one an agent has not described."""
    if epic in tickets.closed():
        raise LookupError(f"epic '{epic}' is closed; put the ticket in another epic")
    if os.environ.get(agents.WHO) and epic and epic not in tickets.described():
        raise LookupError(
            f'say first what the epic is for: epic "{epic}" --spec "{forms.form(forms.EPIC)}"'
        )


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


def propose(args: argparse.Namespace, tickets: Tickets) -> None:
    """Suggest a ticket; whoever does is named, with the ticket they were on when they did,
    whose epic it joins unless another is given."""
    if args.epic in tickets.closed():
        raise LookupError(f"epic '{args.epic}' is closed; put the ticket in another epic")
    who, spec = _agent(), forms.formed(args.spec, forms.TICKET, _agent())
    on = [ticket for ticket in tickets.all() if who and ticket.worker == who][:1]
    epic = args.epic or "".join(ticket.epic for ticket in on)
    number = tickets.add(args.title, spec, process.PROPOSED, epic, [])
    during = "".join(f" while on #{ticket.id} {ticket.title}" for ticket in on)
    tickets.record(number, f"proposed by {who or 'the user'}{during}")
    print(f"#{number} proposed; it waits for the user to accept it or turn it down")


def _agent() -> str:  # the agent that asks, or "" for the user
    return os.environ.get(agents.WHO, "")


def edit(tickets: Tickets, number: int, title: str, spec: str, write: Write | None) -> None:
    """Rewrite a ticket nobody has worked on; with no new words, in the user's editor (`write`)."""
    old = tickets.get(number)
    if not process.untouched(old.step, old.attempts, old.stopped, old.worker):
        raise LookupError(f"#{number} has been worked on; to add to it: dk retry {number} --note")
    if not (title or spec) and (_agent() or not write):
        raise LookupError("say the new text with --spec, the new title with --title")
    if write and not (title or spec):
        title, spec = write(old.title, old.spec)
    spec = forms.formed(spec, forms.TICKET, _agent()) if spec else old.spec
    tickets.rewrite(number, title or old.title, spec)
    was = f"edited by {_agent() or 'the user'}; it said: {old.title}: {old.spec}"
    tickets.record(number, " ".join(was.split()))
    print(f"#{number} edited")


def epic(tickets: Tickets, name: str, spec: str) -> None:
    """Say what an epic is for, or show what was said."""
    if spec:
        tickets.describe(name, forms.formed(spec, forms.EPIC, _agent()))
        print(f"{name} described")
    elif name in tickets.described():
        print(tickets.described()[name])
    else:
        raise LookupError(f"epic '{name}' has no description")


def add(args: argparse.Namespace, tickets: Tickets) -> None:
    spec = forms.formed(args.spec, forms.TICKET, _agent())
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
    first = process.start(process.PROCESS).step
    tests = not args.no_behaviour_tests
    number = tickets.add(args.title, spec, first, args.epic, args.after, tests)
    if args.no_behaviour_tests:
        tickets.record(number, "no behaviour tests: decided when the ticket was written")
    print(f"#{number} written")


def asked(tickets: Tickets, order: object) -> str:
    """Carry out what the user asked for from the page, as the command of that name would.
    Returns what the command prints."""
    said = order if isinstance(order, dict) else {}
    do, number, note = said.get("do"), said.get("ticket"), str(said.get("note") or "").strip()
    epic = said.get("epic")
    if do == "trust" and isinstance(epic, str) and epic:
        number = 0  # it is about an epic, not a ticket
    if not isinstance(number, int):
        raise LookupError("say which ticket, by its number")
    title, spec = (str(said.get(part) or "") for part in ("title", "spec"))
    orders: dict[object, Callable[[], None]] = {
        "trust": lambda: trust(tickets, str(epic), said.get("given") is not False),
        "edit": lambda: edit(tickets, number, title, spec, None),
        "approve": lambda: decide(tickets, number, True, "", said.get("tests") is not False),
        "reject": lambda: decide(tickets, number, False, note),
        "retry": lambda: retry(tickets, number, note),
        "cancel": lambda: cancel(tickets, number),
    }
    if do not in orders:
        raise LookupError(f"the page cannot ask for {do}")
    if do == "reject" and not note:
        raise LookupError("say what must change")
    with contextlib.redirect_stdout(io.StringIO()) as printed:
        orders[do]()
    return printed.getvalue().strip()
