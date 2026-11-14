"""The `dk` command: write tickets, run them, see where they are."""

from __future__ import annotations

import argparse
import os
import shlex
import sys
import threading
import time
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from functools import partial
from pathlib import Path

from dk import agents, briefs, config, preflight, process, screen, starter
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


def _status(tickets: list[Ticket], hidden: Sequence[str] = ()) -> None:
    """Tickets without an epic first, then each epic with its tickets; none at a hidden step."""
    steps = {ticket.id: ticket.step for ticket in tickets}
    listed = [ticket for ticket in tickets if ticket.step not in hidden]
    for epic in sorted({ticket.epic for ticket in listed}):
        if epic:
            print(epic)
        for ticket in listed:
            if ticket.epic == epic:
                print(("  " if epic else "") + _line(ticket, steps))


def _board(team: Sequence[config.Agent], tickets: list[Ticket]) -> None:
    """What each agent is doing, the tickets not yet finished, and a count of the rest."""
    busy = {ticket.worker: ticket for ticket in tickets if ticket.worker}
    print("Agents")
    for agent in team:
        on = busy.get(agent.name)
        doing = f"#{on.id} {on.title} ({on.step})" if on else "free"
        if on or agent.role != PRINCIPAL:  # the Principal is in the conversation otherwise
            print(f"  {agent.name:<12} {doing}")
    print("Tickets")
    _status(tickets, (process.DONE, process.CANCELLED))
    steps = [ticket.step for ticket in tickets]
    print(f"{steps.count(process.DONE)} finished, {steps.count(process.CANCELLED)} cancelled")


def _watch(project: Path, tickets: Tickets) -> None:
    """Show the board again every two seconds, until interrupted."""
    try:
        while True:
            print("\033[2J\033[H", end="")
            _board(config.load(project).agents, tickets.all())
            sys.stdout.flush()
            time.sleep(2)
    except KeyboardInterrupt:
        return


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


def _retry(tickets: Tickets, number: int, answer: str) -> None:
    ticket, position = _stopped(tickets, number)
    tickets.move(number, *vars(process.retry(position)).values())
    _said(tickets, number, "sent on", answer)
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
    init = commands.add_parser("init", help="write a first devkit.toml and AGENTS.md")
    init.add_argument("--model", required=True, help="the model every agent starts with")
    commands.add_parser("check", help="find what would stop the first ticket")
    status = commands.add_parser("status", help="list the tickets")
    status.add_argument("--watch", action="store_true", help="keep showing agents and tickets")
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
def _watching(project: Path, shown: dict[str, Path], no_tabs: bool) -> Iterator[None]:
    """Inside Herdr, a tab for the board and one for each of these files, while the work goes on."""
    inside = os.environ.get("HERDR_WORKSPACE_ID", "")
    board = (sys.executable, "-m", "dk", "--project", str(project), "status", "--watch")
    everything: dict[str, Path | Sequence[str]] = {"status": board, **shown}
    watched = everything if inside and not no_tabs else {}
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
    with _watching(project, {"tickets": progress, **director.shown()}, no_tabs):
        behind.start()
        try:
            agents.converse(argv, briefs.principal(command), project, agent.name)
        finally:
            director.stop.set()
            behind.join()
    if trouble:
        raise trouble[0]


def _check(project: Path, home: Path) -> None:
    workspace = Workspace(project, home / "work")
    found = preflight.run(config.load(project), project, workspace, home / "logs", PRINCIPAL)
    for fine, what in found:
        print(f"{'ok      ' if fine else 'PROBLEM '} {what}")
    wrong = sum(not fine for fine, _ in found)
    if wrong:
        raise LookupError(f"{wrong} thing{'s' if wrong > 1 else ''} to fix before starting")


def _add(args: argparse.Namespace, tickets: Tickets) -> None:
    first = process.start(process.PROCESS).step
    number = tickets.add(args.title, args.spec, first, args.epic, args.after)
    print(f"#{number} written")


def _run(args: argparse.Namespace, project: Path, home: Path, tickets: Tickets) -> None:
    director = _director(project, home, tickets, print)
    with _watching(project, director.shown(), args.no_tabs):
        director.run()


def _execute(args: argparse.Namespace) -> None:
    project: Path = args.project.resolve()
    home = project / HOME
    home.mkdir(exist_ok=True)
    (home / ".gitignore").write_text("*\n")
    tickets = Tickets(home / "tickets.db")
    commands: dict[str, Callable[[], None]] = {
        "add": lambda: _add(args, tickets),
        "check": lambda: _check(project, home),
        "init": lambda: print(*starter.write(project, args.model), sep="\n"),
        "run": lambda: _run(args, project, home, tickets),
        "talk": lambda: _talk(project, home, tickets, args.no_tabs),
        "status": lambda: _watch(project, tickets) if args.watch else _status(tickets.all()),
        "show": lambda: _show(tickets, Workspace(project, home / "work"), args.ticket),
        "retry": lambda: _retry(tickets, args.ticket, args.note),
        "cancel": lambda: _cancel(tickets, args.ticket),
        "approve": lambda: _decide(tickets, args.ticket, True, ""),
        "reject": lambda: _decide(tickets, args.ticket, False, args.note),
    }
    commands[args.command]()


def main(argv: Sequence[str] | None = None) -> int:
    try:
        _execute(_parser().parse_args(argv))
    except (config.ConfigError, agents.UnknownProgram, LookupError, RuntimeError) as error:
        print(f"dk: {error}")
        return 1
    return 0
