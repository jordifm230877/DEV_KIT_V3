"""What the user is shown: the ticket list, the board that redraws itself, one ticket.

A composer: it reads the ticket list, the configuration, the process and a ticket's copy.
"""

from __future__ import annotations

import sys
import time
from collections.abc import Collection, Iterator, Sequence
from pathlib import Path

from dk import config, paint, process, spent
from dk.jobs import PRINCIPAL
from dk.tickets import Ticket, Tickets
from dk.workspace import Workspace

_LOOK_EVERY = 0.1
Row = tuple[str, str]  # what kind of line it is, and its words


def line(ticket: Ticket, steps: dict[int, str]) -> str:
    where = f"stopped at {ticket.step}" if ticket.stopped else ticket.step
    line = f"#{ticket.id} {where}  {ticket.title}"
    if ticket.attempts:
        line += f"  [{ticket.attempts} attempt{'s' if ticket.attempts > 1 else ''}]"
    if ticket.stopped:
        line += f"  {ticket.note.splitlines()[0]}"
    held = process.held_by(ticket.follows, steps)
    if held and ticket.step != process.CANCELLED:
        line += "  waits for " + ", ".join(f"#{number}" for number in held)
    return line


def _counted(tickets: list[Ticket]) -> str:
    steps = [ticket.step for ticket in tickets]
    return f"{steps.count(process.DONE)} done, {steps.count(process.CANCELLED)} cancelled"


def _kind(ticket: Ticket, steps: dict[int, str]) -> str:
    if ticket.stopped or ticket.step == process.PROPOSED:
        return "stopped" if ticket.stopped else "proposed"
    return "held" if process.held_by(ticket.follows, steps) else "ticket"


def _rows(tickets: list[Ticket], hidden: Sequence[str], closed: Collection[str]) -> Iterator[Row]:
    steps = {ticket.id: ticket.step for ticket in tickets}
    listed = [ticket for ticket in tickets if ticket.step not in hidden]
    for epic in sorted({ticket.epic for ticket in listed}):
        inside = [ticket for ticket in listed if ticket.epic == epic]
        if epic in closed:
            yield "closed", f"{epic}  closed: {_counted(inside)}"
            continue
        if epic:
            yield "epic", epic
        for ticket in inside:
            yield _kind(ticket, steps), ("  " if epic else "") + line(ticket, steps)


def status(tickets: list[Ticket], hidden: Sequence[str] = (), closed: Collection[str] = ()) -> None:
    """Tickets without an epic first, then each epic with its tickets; none at a hidden step.
    A closed epic takes one line."""
    for _, text in _rows(tickets, hidden, closed):
        print(text)


def _working(team: Sequence[config.Agent], tickets: list[Ticket]) -> Iterator[Row]:
    """A line for each agent, and one for each check the program itself is running."""
    busy = {ticket.worker: ticket for ticket in tickets if ticket.worker}
    names = [agent.name for agent in team if agent.role != PRINCIPAL or agent.name in busy]
    for name in [*names, *(doing for doing in busy if doing not in names)]:
        on = busy.get(name)
        doing = f"#{on.id} {on.title} ({on.step})  since {on.since}" if on else "free"
        used = spent.said(on.spent) if on else ""
        yield "busy" if on else "free", f"  {name:<12} {doing}{used and '  ' + used}"


def board(team: Sequence[config.Agent], tickets: list[Ticket]) -> None:
    """What each agent is doing, the tickets not yet finished, and a count of the rest; in
    colour, so that what needs the user stands out. The Principal is listed only while it
    has a job: otherwise it is in the conversation."""
    rows: list[Row] = [("heading", "Agents"), *_working(team, tickets)]
    rows += [("heading", "Tickets"), *_rows(tickets, (process.DONE, process.CANCELLED), ())]
    steps = [ticket.step for ticket in tickets]
    done, cancelled = steps.count(process.DONE), steps.count(process.CANCELLED)
    rows.append(("count", f"{done} finished, {cancelled} cancelled"))
    for kind, text in rows:
        print(paint.part(kind, text))


def watch(project: Path, tickets: Tickets) -> None:
    """Show the board again every two seconds, until interrupted."""
    try:
        while True:
            print("\033[2J\033[H", end="")
            board(config.load(project).agents, tickets.all())
            sys.stdout.flush()
            time.sleep(2)
    except KeyboardInterrupt:
        return


def follow(log: Path) -> None:
    """Show a file of an agent's work in colour, and what is added to it, until interrupted."""
    try:
        while not log.exists():
            time.sleep(_LOOK_EVERY)
        painted = paint.work()
        with log.open() as work:
            pending = ""
            while True:
                pending += work.readline()
                if pending.endswith("\n"):
                    print(painted(pending[:-1]), flush=True)
                    pending = ""
                else:
                    time.sleep(_LOOK_EVERY)
    except KeyboardInterrupt:
        return


def _facts(ticket: Ticket, steps: dict[int, str]) -> dict[str, object]:
    """A ticket as the page shows it in a list."""
    over = ticket.step in (process.DONE, process.CANCELLED)
    kind = ticket.step if over else _kind(ticket, steps)
    return {
        **{name: getattr(ticket, name) for name in ("id", "title", "step", "attempts", "epic")},
        **{name: getattr(ticket, name) for name in ("follows", "worker", "since")},
        "kind": kind,
        "note": ticket.note if ticket.stopped else "",
        "waits": process.held_by(ticket.follows, steps) if kind == "held" else [],
    }


def _epics(
    tickets: list[Ticket], closed: Collection[str], described: dict[str, str]
) -> Iterator[dict[str, object]]:
    """Each epic with its tickets; it follows the epics that tickets of its own follow."""
    steps = {ticket.id: ticket.step for ticket in tickets}
    home = {ticket.id: ticket.epic for ticket in tickets}
    for epic in sorted({ticket.epic for ticket in tickets}):
        inside = [ticket for ticket in tickets if ticket.epic == epic]
        ahead = {home[number] for ticket in inside for number in ticket.follows}
        yield {
            "name": epic,
            "closed": epic in closed,
            "description": described.get(epic, ""),
            "done": [ticket.step for ticket in inside].count(process.DONE),
            "follows": sorted(ahead - {epic, ""}),
            "tickets": [_facts(ticket, steps) for ticket in inside],
        }


def _team(team: Sequence[config.Agent], tickets: list[Ticket]) -> Iterator[dict[str, object]]:
    """Each agent and the ticket it is on, and each check the program itself is running."""
    busy = {ticket.worker: ticket for ticket in tickets if ticket.worker}
    roles = {agent.name: agent.role for agent in team}
    idle = [name for name, role in roles.items() if role != PRINCIPAL and name not in busy]
    for name in sorted([*busy, *idle], key=[*roles, *busy].index):
        on = busy.get(name)
        yield {
            "name": name,
            "role": roles.get(name, ""),
            "ticket": on.id if on else None,
            "since": on.since if on else "",
            "spent": spent.said(on.spent) if on else "",
        }


def data(what: str, project: Path, tickets: Tickets, workspace: Workspace) -> object:
    """What the page asks for: `board`, or `ticket/N`."""
    kind, _, number = what.partition("/")
    listed = tickets.all()
    if what == "board":
        agents = [*_team(config.load(project).agents, listed)]
        return {"agents": agents, "epics": [*_epics(listed, tickets.closed(), tickets.described())]}
    if kind != "ticket" or not number.isdigit():
        raise LookupError(f"there is nothing called {what}")
    ticket = tickets.get(int(number))
    position = process.Position(ticket.step, ticket.attempts, ticket.note, ticket.stopped)
    files = sorted(ticket.protected)
    return {
        **_facts(ticket, {other.id: other.step for other in listed}),
        "spec": ticket.spec,
        "history": tickets.history(ticket.id),
        "approval": process.waiting(process.PROCESS, position),
        "tests": [{"name": name, "text": workspace.text(ticket.id, name)} for name in files],
    }


def show(tickets: Tickets, workspace: Workspace, number: int) -> None:
    ticket = tickets.get(number)
    epic = [f"Epic: {ticket.epic}"] if ticket.epic else []
    steps = {other.id: other.step for other in tickets.all()}
    print(line(ticket, steps), *epic, ticket.spec, *tickets.history(ticket.id), sep="\n")
    position = process.Position(ticket.step, ticket.attempts, ticket.note, ticket.stopped)
    if process.waiting(process.PROCESS, position):
        for name in sorted(ticket.protected):
            print(f"\n--- {name}", (workspace.prepare(number) / name).read_text(), sep="\n")
