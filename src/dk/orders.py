"""What the user, or the Principal for them, asks of a ticket with a command or from the
page: send it on, give it up, pause it, decide on what waits.

A composer: it reads the process and writes the ticket list, and takes out of a ticket's
copy the behaviour tests it is to go on without. It starts nothing.
"""

from __future__ import annotations

import contextlib
import io
import os
from collections.abc import Callable

from dk import agents, epics, process, writing
from dk.jobs import BEHAVIOUR_TESTS
from dk.tickets import Ticket, Tickets
from dk.workspace import Workspace

_GIVEN_UP = "cancelled; its unmerged work is thrown away on the next run"
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


def leave(tickets: Tickets, number: int, pause: bool = False) -> None:
    """Give the ticket up; or `pause` it, left with its work until it is sent on."""
    ticket, change = tickets.get(number), process.pause if pause else process.cancel
    try:
        left = change(process.Position(ticket.step, ticket.attempts, ticket.note, ticket.stopped))
    except LookupError as error:
        raise LookupError(f"#{number} {error}") from None
    tickets.move(number, *vars(left).values())
    tickets.record(number, process.PAUSED if pause else "cancelled")
    print(f"#{number} " + (f"paused; `dk retry {number}` sends it on" if pause else _GIVEN_UP))


def _answer(tickets: Tickets, number: int, accepted: bool, reason: str, tests: bool) -> None:
    """The user's word on a proposed ticket: it becomes a ticket like any other, or is given up.
    That it takes no behaviour tests is written before it becomes one: a run that is going
    takes the ticket up at once, as it then is."""
    first = process.start(process.PROCESS) if accepted else process.Position(process.CANCELLED)
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


def asked(tickets: Tickets, order: object) -> str:
    """Carry out what the user asked for from the page, as the command of that name would.
    Returns what the command prints."""
    said = order if isinstance(order, dict) else {}
    do, number, note = said.get("do"), _ticket(said), str(said.get("note") or "").strip()
    title, spec = (str(said.get(part) or "") for part in ("title", "spec"))
    orders: dict[object, Callable[[], None]] = {
        "trust": lambda: epics.trust(
            tickets, str(said.get("epic")), said.get("given") is not False
        ),
        "edit": lambda: writing.edit(tickets, number, title, spec, None),
        "approve": lambda: decide(tickets, number, True, "", said.get("tests") is not False),
        "reject": lambda: decide(tickets, number, False, note),
        "retry": lambda: retry(tickets, number, note),
        "cancel": lambda: leave(tickets, number),
        "pause": lambda: leave(tickets, number, pause=True),
    }
    if do not in orders:
        raise LookupError(f"the page cannot ask for {do}")
    if do == "reject" and not note:
        raise LookupError("say what must change")
    with contextlib.redirect_stdout(io.StringIO()) as printed:
        orders[do]()
    return printed.getvalue().strip()


def _ticket(said: dict[object, object]) -> int:
    """The number of the ticket an order from the page is about."""
    number, epic = said.get("ticket"), said.get("epic")
    if said.get("do") == "trust" and isinstance(epic, str) and epic:
        return 0  # it is about an epic, not a ticket
    if not isinstance(number, int):
        raise LookupError("say which ticket, by its number")
    return number
