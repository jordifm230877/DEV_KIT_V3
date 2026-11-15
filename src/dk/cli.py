"""The `dk` command: write tickets, run them, see where they are."""

from __future__ import annotations

import argparse
import fcntl
import os
import shlex
import sys
import threading
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from functools import partial
from pathlib import Path

from dk import (
    agents,
    briefs,
    config,
    nightly,
    orders,
    preflight,
    principal,
    screen,
    starter,
    views,
    web,
)
from dk.director import Director
from dk.jobs import PRINCIPAL
from dk.tickets import Tickets
from dk.workspace import Workspace

HOME = ".devkit"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dk", description=__doc__)
    parser.add_argument("--project", type=Path, default=Path.cwd(), help="the project directory")
    commands = parser.add_subparsers(dest="command", required=True)
    add = commands.add_parser("add", help="write a new ticket")
    add.add_argument("title")
    add.add_argument("--spec", required=True, help="what is wanted and how to tell it is done")
    add.add_argument("--epic", default="", help="the larger piece of work this belongs to")
    add.add_argument(
        "--no-behaviour-tests",
        action="store_true",
        help="for a ticket that changes nothing a user of the product can see",
    )
    add.add_argument(
        "--after",
        type=int,
        action="append",
        default=[],
        help="a ticket that must be merged before this one starts; may be repeated",
    )
    propose = commands.add_parser("propose", help="suggest a ticket; the user decides on it")
    propose.add_argument("title")
    propose.add_argument("--spec", required=True, help="what is wanted and why")
    propose.add_argument("--epic", default="", help="the larger piece of work this belongs to")
    audit = commands.add_parser("audit", help="have the whole project audited; leaves a report")
    audit.add_argument("kind", choices=list(briefs.AUDITS))
    audit.add_argument("--note", default="", help="what to look at in particular")
    for name, text in (
        ("night", "audit everything that changed, and go on with unfinished tickets"),
        ("run", "work on every unfinished ticket"),
        ("talk", "talk with the Principal while the work goes on"),
    ):
        command = commands.add_parser(name, help=text)
        command.add_argument("--no-tabs", action="store_true", help="do not open Herdr tabs")
        if name == "night":
            command.add_argument("--at", default="", help="start it every day at this time, HH:MM")
            command.add_argument("--off", action="store_true", help="no longer start it every day")
    init = commands.add_parser("init", help="write a first devkit.toml and AGENTS.md")
    init.add_argument("--model", required=True, help="the model every agent starts with")
    init.add_argument(
        "--program", default="pi", choices=list(agents.PROGRAMS), help="their program"
    )
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
    site = commands.add_parser("web", help="show the agents and the tickets in a browser")
    site.add_argument("--port", type=int, default=8642, help="where on this computer; 0 for any")
    follow = commands.add_parser("follow", help="show a file of an agent's work, in colour")
    follow.add_argument("log", type=Path)
    commands.add_parser("close", help="mark an epic as complete").add_argument("epic")
    commands.add_parser("reopen", help="open a closed epic again").add_argument("epic")
    approve = commands.add_parser("approve", help="accept what waits for you")
    approve.add_argument("ticket", type=int)
    approve.add_argument(
        "--no-behaviour-tests", action="store_true", help="for a proposed ticket you accept"
    )
    reject = commands.add_parser("reject", help="send back what waits for you")
    reject.add_argument("ticket", type=int)
    reject.add_argument("--note", required=True, help="what must change")
    return parser


def _command(project: Path) -> str:
    """This program, as an agent types it: for the Principal's work and for proposals."""
    return shlex.join([sys.executable, "-m", "dk", "--project", str(project)])


def _director(project: Path, home: Path, tickets: Tickets, say: Callable[[str], None]) -> Director:
    herdr = os.environ.get("HERDR_BIN_PATH", "herdr")
    inside = "HERDR_WORKSPACE_ID" in os.environ
    notify = partial(screen.notify, herdr) if inside else (lambda title, body: None)
    workspace = Workspace(project, home / "work")
    logs = home / "logs"
    return Director(
        config.load(project), tickets, workspace, logs, say, notify, command=_command(project)
    )


@contextmanager
def _watching(project: Path, shown: dict[str, Path], no_tabs: bool) -> Iterator[None]:
    """Inside Herdr, a tab for the board and one for each of these files, while the work goes on."""
    inside = os.environ.get("HERDR_WORKSPACE_ID", "")
    dk = (sys.executable, "-m", "dk", "--project", str(project))
    follows = {name: (*dk, "follow", str(log)) for name, log in shown.items()}
    everything = {"status": (*dk, "status", "--watch"), **follows}
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
    argv = agent.command or agents.conversation(agent.program, agent.model, director.config.web)
    trouble: list[Exception] = []

    def work() -> None:
        try:
            director.run(keep_going=True)
        except Exception as error:  # reported when the conversation ends
            trouble.append(error)

    behind = threading.Thread(target=work)
    herdr = os.environ.get("HERDR_BIN_PATH", "herdr")
    mine = "" if no_tabs else os.environ.get("HERDR_TAB_ID", "")
    watching = _watching(project, director.shown(), no_tabs)
    with _alone(home, BUSY), watching, screen.named(herdr, mine, "Principal"):
        behind.start()
        try:
            agents.converse(argv, principal.conversation(director.command), project, agent.name)
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


BUSY = "work is already going on in this project (`dk run`, `dk talk` or `dk night`)"


@contextmanager
def _alone(home: Path, or_else: str = "") -> Iterator[bool]:
    """Hold the project's work for this program. Says whether it got it; when another
    program has it, refuses with `or_else` if there is one."""
    with (home / "running").open("w") as working:
        try:
            fcntl.flock(working, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            if or_else:
                raise RuntimeError(or_else) from None
            yield False
        else:
            yield True


def _run(args: argparse.Namespace, project: Path, home: Path, tickets: Tickets) -> None:
    director = _director(project, home, tickets, print)
    with _alone(home, BUSY), _watching(project, director.shown(), args.no_tabs):
        director.run()


def _nightly(at: str, project: Path) -> None:
    """Set or take away the daily start of the night shift; nothing is started now."""
    if at:
        orders.auditor(project)
        nightly.every_day(
            project, at, [sys.executable, "-m", "dk", "--project", str(project), "night"]
        )
        print(f"the night shift will start every day at {at}; `dk night --off` ends that")
    else:
        nightly.never(project)
        print("the night shift no longer starts by itself")


def _night(args: argparse.Namespace, project: Path, home: Path, tickets: Tickets) -> None:
    if args.at or args.off:
        return _nightly(args.at, project)
    director = _director(project, home, tickets, print)
    with _alone(home) as free:
        orders.night(project, tickets, director.workspace.changed_since)
        if not free:
            print(f"{BUSY}; it will carry these out")
            return
        with _watching(project, director.shown(), args.no_tabs):
            director.run()


def _execute(args: argparse.Namespace) -> None:
    project: Path = args.project.resolve()
    home = project / HOME
    home.mkdir(exist_ok=True)
    (home / ".gitignore").write_text("*\n")
    tickets = Tickets(home / "tickets.db")
    commands: dict[str, Callable[[], None]] = {
        "add": lambda: orders.add(args, tickets),
        "propose": lambda: orders.propose(args, tickets),
        "audit": lambda: orders.audit(args.kind, args.note, project, tickets),
        "night": lambda: _night(args, project, home, tickets),
        "check": lambda: _check(project, home),
        "init": lambda: print(*starter.write(project, args.model, args.program), sep="\n"),
        "run": lambda: _run(args, project, home, tickets),
        "talk": lambda: _talk(project, home, tickets, args.no_tabs),
        "status": lambda: (
            views.watch(project, tickets)
            if args.watch
            else views.status(tickets.all(), closed=tickets.closed())
        ),
        "follow": lambda: views.follow(args.log),
        "web": lambda: web.serve(
            args.port,
            lambda what: views.data(what, project, tickets, Workspace(project, home / "work")),
            lambda address: print(f"the tickets of this project are at {address}", flush=True),
        ),
        "show": lambda: views.show(tickets, Workspace(project, home / "work"), args.ticket),
        "retry": lambda: orders.retry(tickets, args.ticket, args.note),
        "cancel": lambda: orders.cancel(tickets, args.ticket),
        "close": lambda: orders.close(tickets, args.epic),
        "reopen": lambda: orders.reopen(tickets, args.epic),
        "approve": lambda: orders.decide(
            tickets, args.ticket, True, "", not args.no_behaviour_tests
        ),
        "reject": lambda: orders.decide(tickets, args.ticket, False, args.note),
    }
    commands[args.command]()


def main(argv: Sequence[str] | None = None) -> int:
    try:
        _execute(_parser().parse_args(argv))
    except (config.ConfigError, agents.UnknownProgram, LookupError, RuntimeError) as error:
        print(f"dk: {error}")
        return 1
    return 0
