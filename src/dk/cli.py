"""The `dk` command: write tickets, run them, see where they are."""

from __future__ import annotations

import argparse
import os
from collections.abc import Sequence
from pathlib import Path

from dk import agents, config, process, screen
from dk.director import Director
from dk.tickets import Ticket, Tickets
from dk.workspace import Workspace

HOME = ".devkit"


def _line(ticket: Ticket) -> str:
    where = f"stopped at {ticket.step}" if ticket.stopped else ticket.step
    line = f"#{ticket.id} {where}  {ticket.title}"
    if ticket.attempts:
        line += f"  [{ticket.attempts} attempt{'s' if ticket.attempts > 1 else ''}]"
    if ticket.stopped:
        line += f"  {ticket.note.splitlines()[0]}"
    return line


def _status(tickets: list[Ticket]) -> None:
    """Tickets without an epic first, then each epic with its tickets."""
    for epic in sorted({ticket.epic for ticket in tickets}):
        if epic:
            print(epic)
        for ticket in tickets:
            if ticket.epic == epic:
                print(("  " if epic else "") + _line(ticket))


def _retry(tickets: Tickets, number: int, answer: str) -> None:
    ticket = tickets.get(number)
    if not ticket.stopped:
        raise LookupError(f"#{number} is not stopped")
    position = process.Position(ticket.step, ticket.attempts, ticket.note, ticket.stopped)
    tickets.move(number, *vars(process.retry(position, answer)).values())
    tickets.record(number, f"sent on by the user{': ' + answer if answer else ''}")
    print(f"#{number} will continue at {ticket.step} on the next run")


def _decide(tickets: Tickets, number: int, approved: bool, reason: str) -> None:
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
    print(_line(ticket), *epic, ticket.spec, *tickets.history(ticket.id), sep="\n")
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
    run = commands.add_parser("run", help="work on every unfinished ticket")
    run.add_argument("--no-tabs", action="store_true", help="do not open Herdr tabs")
    commands.add_parser("status", help="list the tickets")
    show = commands.add_parser("show", help="one ticket and everything that happened to it")
    show.add_argument("ticket", type=int)
    retry = commands.add_parser("retry", help="send a stopped ticket on again")
    retry.add_argument("ticket", type=int)
    retry.add_argument("--note", default="", help="an answer or instruction for the agent")
    commands.add_parser("approve", help="accept what waits for you").add_argument(
        "ticket", type=int
    )
    reject = commands.add_parser("reject", help="send back what waits for you")
    reject.add_argument("ticket", type=int)
    reject.add_argument("--note", required=True, help="what must change")
    return parser


def _run(director: Director, no_tabs: bool) -> None:
    """Do the work; inside Herdr, with a tab per agent to watch it."""
    inside = os.environ.get("HERDR_WORKSPACE_ID", "")
    watched = director.shown() if inside and not no_tabs else {}
    with screen.tabs(os.environ.get("HERDR_BIN_PATH", "herdr"), inside, watched):
        director.run()


def _execute(args: argparse.Namespace) -> None:
    project: Path = args.project.resolve()
    home = project / HOME
    home.mkdir(exist_ok=True)
    (home / ".gitignore").write_text("*\n")
    tickets = Tickets(home / "tickets.db")
    workspace = Workspace(project, home / "work")
    if args.command == "add":
        first = process.start(process.PROCESS).step
        number = tickets.add(args.title, args.spec, first, args.epic)
        print(f"#{number} written")
    elif args.command == "run":
        director = Director(config.load(project), tickets, workspace, home / "logs", print)
        _run(director, args.no_tabs)
    elif args.command == "status":
        _status(tickets.all())
    elif args.command == "show":
        _show(tickets, workspace, args.ticket)
    elif args.command == "retry":
        _retry(tickets, args.ticket, args.note)
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
