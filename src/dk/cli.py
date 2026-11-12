"""The `dk` command: write tickets, run them, see where they are."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from dk import agents, config, process
from dk.director import Director
from dk.tickets import Ticket, Tickets
from dk.workspace import Workspace

HOME = ".devkit"


def _line(ticket: Ticket) -> str:
    line = f"#{ticket.id} {ticket.step}  {ticket.title}"
    if ticket.attempts:
        line += f"  [{ticket.attempts} attempt{'s' if ticket.attempts > 1 else ''}]"
    if ticket.step == process.STOPPED:
        line += f"  {ticket.note.splitlines()[0]}"
    return line


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dk", description=__doc__)
    parser.add_argument("--project", type=Path, default=Path.cwd(), help="the project directory")
    commands = parser.add_subparsers(dest="command", required=True)
    add = commands.add_parser("add", help="write a new ticket")
    add.add_argument("title")
    add.add_argument("--spec", required=True, help="what is wanted and how to tell it is done")
    commands.add_parser("run", help="work on every unfinished ticket")
    commands.add_parser("status", help="list the tickets")
    show = commands.add_parser("show", help="one ticket and everything that happened to it")
    show.add_argument("ticket", type=int)
    return parser


def _execute(args: argparse.Namespace) -> None:
    project: Path = args.project.resolve()
    home = project / HOME
    home.mkdir(exist_ok=True)
    (home / ".gitignore").write_text("*\n")
    tickets = Tickets(home / "tickets.db")
    if args.command == "add":
        number = tickets.add(args.title, args.spec, process.start(process.PROCESS).step)
        print(f"#{number} written")
    elif args.command == "run":
        workspace = Workspace(project, home / "work")
        Director(config.load(project), tickets, workspace, home / "logs", print).run()
    elif args.command == "status":
        for ticket in tickets.all():
            print(_line(ticket))
    else:
        ticket = tickets.get(args.ticket)
        print(_line(ticket), ticket.spec, *tickets.history(ticket.id), sep="\n")


def main(argv: Sequence[str] | None = None) -> int:
    try:
        _execute(_parser().parse_args(argv))
    except (config.ConfigError, agents.UnknownProgram, LookupError, RuntimeError) as error:
        print(f"dk: {error}")
        return 1
    return 0
