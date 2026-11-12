"""The `dk` command: write tickets, run them, see where they are."""

from __future__ import annotations

import argparse
import os
import shlex
import sys
import threading
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from functools import partial
from pathlib import Path

from dk import agents, briefs, config, process, screen
from dk.director import PRINCIPAL, Director
from dk.tickets import Ticket, Tickets
from dk.workspace import Workspace

HOME = ".devkit"


def _line(ticket: Ticket, steps: dict[int, str]) -> str:
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


def _status(tickets: list[Ticket]) -> None:
    """Tickets without an epic first, then each epic with its tickets."""
    steps = {ticket.id: ticket.step for ticket in tickets}
    for epic in sorted({ticket.epic for ticket in tickets}):
        if epic:
            print(epic)
        for ticket in tickets:
            if ticket.epic == epic:
                print(("  " if epic else "") + _line(ticket, steps))


def _retry(tickets: Tickets, number: int, answer: str) -> None:
    ticket = tickets.get(number)
    if not ticket.stopped:
        raise LookupError(f"#{number} is not stopped")
    position = process.Position(ticket.step, ticket.attempts, ticket.note, ticket.stopped)
    tickets.move(number, *vars(process.retry(position, answer)).values())
    tickets.record(number, f"sent on by the user{': ' + answer if answer else ''}")
    print(f"#{number} will continue at {ticket.step} on the next run")


def _cancel(tickets: Tickets, number: int) -> None:
    ticket = tickets.get(number)
    position = process.Position(ticket.step, ticket.attempts, ticket.note, ticket.stopped)
    try:
        cancelled = process.cancel(position)
    except LookupError as error:
        raise LookupError(f"#{number} {error}") from None
    tickets.move(number, *vars(cancelled).values())
    tickets.record(number, "cancelled")
    print(f"#{number} cancelled; its unmerged work is thrown away on the next run")


def _decide(tickets: Tickets, number: int, approved: bool, reason: str) -> None:
    if os.environ.get(agents.WHO):
        raise LookupError("only the user can approve or reject; ask them to run this themselves")
    ticket = tickets.get(number)
    position = process.Position(ticket.step, ticket.attempts, ticket.note, ticket.stopped)
    if not process.waiting(process.PROCESS, position):
        raise LookupError(f"#{number} is not waiting for your approval")
    decided = process.decide(process.PROCESS, position, approved, reason)
    tickets.move(number, *vars(decided).values())
    tickets.record(
        number, "approved by the user" if approved else f"rejected by the user: {reason}"
    )
    print(f"#{number} will continue at {decided.step} on the next run")


def _show(tickets: Tickets, workspace: Workspace, number: int) -> None:
    ticket = tickets.get(number)
    epic = [f"Epic: {ticket.epic}"] if ticket.epic else []
    steps = {other.id: other.step for other in tickets.all()}
    print(_line(ticket, steps), *epic, ticket.spec, *tickets.history(ticket.id), sep="\n")
    position = process.Position(ticket.step, ticket.attempts, ticket.note, ticket.stopped)
    if process.waiting(process.PROCESS, position):
        for name in sorted(ticket.protected):
            print(f"\n--- {name}", (workspace.prepare(number) / name).read_text(), sep="\n")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dk", description=__doc__)
    parser.add_argument("--project", type=Path, default=Path.cwd(), help="the project directory")
    commands = parser.add_subparsers(dest="command", required=True)
    add = commands.add_parser("add", help="write a new ticket")
    add.add_argument("title")
    add.add_argument("--spec", required=True, help="what is wanted and how to tell it is done")
    add.add_argument("--epic", default="", help="the larger piece of work this belongs to")
    add.add_argument(
        "--after",
        type=int,
        action="append",
        default=[],
        help="a ticket that must be merged before this one starts; may be repeated",
    )
    for name, text in (
        ("run", "work on every unfinished ticket"),
        ("talk", "talk with the Principal while the work goes on"),
    ):
        command = commands.add_parser(name, help=text)
        command.add_argument("--no-tabs", action="store_true", help="do not open Herdr tabs")
    commands.add_parser("status", help="list the tickets")
    show = commands.add_parser("show", help="one ticket and everything that happened to it")
    show.add_argument("ticket", type=int)
    retry = commands.add_parser("retry", help="send a stopped ticket on again")
    retry.add_argument("ticket", type=int)
    retry.add_argument("--note", default="", help="an answer or instruction for the agent")
    commands.add_parser("cancel", help="give a ticket up and throw its work away").add_argument(
        "ticket", type=int
    )
    commands.add_parser("approve", help="accept what waits for you").add_argument(
        "ticket", type=int
    )
    reject = commands.add_parser("reject", help="send back what waits for you")
    reject.add_argument("ticket", type=int)
    reject.add_argument("--note", required=True, help="what must change")
    return parser


def _director(project: Path, home: Path, tickets: Tickets, say: Callable[[str], None]) -> Director:
    herdr = os.environ.get("HERDR_BIN_PATH", "herdr")
    inside = "HERDR_WORKSPACE_ID" in os.environ
    notify = partial(screen.notify, herdr) if inside else (lambda title, body: None)
    workspace = Workspace(project, home / "work")
    return Director(config.load(project), tickets, workspace, home / "logs", say, notify)


@contextmanager
def _watching(shown: dict[str, Path], no_tabs: bool) -> Iterator[None]:
    """Inside Herdr, a tab for each of these files while the work goes on."""
    inside = os.environ.get("HERDR_WORKSPACE_ID", "")
    watched = shown if inside and not no_tabs else {}
    with screen.tabs(os.environ.get("HERDR_BIN_PATH", "herdr"), inside, watched):
        yield


def _talk(project: Path, home: Path, tickets: Tickets, no_tabs: bool) -> None:
    """Open the conversation with the Principal; the work goes on behind it until it ends."""
    progress = home / "logs" / "tickets.log"
    progress.parent.mkdir(parents=True, exist_ok=True)

    def say(line: str) -> None:
        with progress.open("a") as log:
            log.write(line + "\n")

    director = _director(project, home, tickets, say)
    principals = director.config.with_role(PRINCIPAL)
    if not principals:
        raise config.ConfigError(f"no agent has the role '{PRINCIPAL}'")
    agent = principals[0]
    argv = agent.command or agents.conversation(agent.program, agent.model)
    command = shlex.join([sys.executable, "-m", "dk", "--project", str(project)])
    trouble: list[Exception] = []

    def work() -> None:
        try:
            director.run(keep_going=True)
        except Exception as error:  # reported when the conversation ends
            trouble.append(error)

    behind = threading.Thread(target=work)
    with _watching({"tickets": progress, **director.shown()}, no_tabs):
        behind.start()
        try:
            agents.converse(argv, briefs.principal(command), project, agent.name)
        finally:
            director.stop.set()
            behind.join()
    if trouble:
        raise trouble[0]


def _execute(args: argparse.Namespace) -> None:
    project: Path = args.project.resolve()
    home = project / HOME
    home.mkdir(exist_ok=True)
    (home / ".gitignore").write_text("*\n")
    tickets = Tickets(home / "tickets.db")
    if args.command == "add":
        first = process.start(process.PROCESS).step
        number = tickets.add(args.title, args.spec, first, args.epic, args.after)
        print(f"#{number} written")
    elif args.command == "run":
        director = _director(project, home, tickets, print)
        with _watching(director.shown(), args.no_tabs):
            director.run()
    elif args.command == "talk":
        _talk(project, home, tickets, args.no_tabs)
    elif args.command == "status":
        _status(tickets.all())
    elif args.command == "show":
        _show(tickets, Workspace(project, home / "work"), args.ticket)
    elif args.command == "retry":
        _retry(tickets, args.ticket, args.note)
    elif args.command == "cancel":
        _cancel(tickets, args.ticket)
    else:
        approved = args.command == "approve"
        _decide(tickets, args.ticket, approved, "" if approved else args.note)


def main(argv: Sequence[str] | None = None) -> int:
    try:
        _execute(_parser().parse_args(argv))
    except (config.ConfigError, agents.UnknownProgram, LookupError, RuntimeError) as error:
        print(f"dk: {error}")
        return 1
    return 0
