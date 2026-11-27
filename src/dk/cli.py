"""The `dk` command: write tickets, run them, see where they are."""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import io
import os
import secrets
import shlex
import sys
import threading
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from functools import partial
from pathlib import Path

from dk import (
    agents,
    arguments,
    audits,
    config,
    epics,
    forms,
    nightly,
    orders,
    preflight,
    principal,
    screen,
    starter,
    upkeep,
    views,
    web,
    writing,
)
from dk.director import Director
from dk.jobs import PRINCIPAL
from dk.tickets import Tickets
from dk.workspace import Workspace

HOME = ".devkit"
_ANYWHERE = ("init", "check", "follow")  # commands that need no project to be there yet


_NO_CHECKS = (
    "this project has no checks: nothing proves that a ticket's work is right; "
    "list them under [checks] in devkit.toml"
)


def _command(project: Path) -> str:
    """This program, as an agent types it: for the Principal's work and for proposals."""
    return shlex.join([sys.executable, "-m", "dk", "--project", str(project)])


def _director(project: Path, home: Path, tickets: Tickets, say: Callable[[str], None]) -> Director:
    herdr = os.environ.get("HERDR_BIN_PATH", "herdr")
    inside = "HERDR_WORKSPACE_ID" in os.environ
    notify = partial(screen.notify, herdr) if inside else (lambda title, body: None)
    workspace = Workspace(project, home / "work")
    logs = home / "logs"
    settings = config.load(project)
    if not settings.checks:  # a project begun from nothing had none: its tickets merged unproved
        say(_NO_CHECKS)

    def closed(epic: str) -> None:
        with contextlib.redirect_stdout(io.StringIO()) as printed:
            _closed(epic, project, tickets)
        say(printed.getvalue().strip())

    command = _command(project)
    return Director(settings, tickets, workspace, logs, say, notify, command=command, closed=closed)


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
    argv = agent.command or agents.conversation(
        agent.program, agent.model, director.config.web, agent.reasoning
    )
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
            # What is set for the agent's program does not reach every command it runs: Codex
            # runs them in a helper that outlives conversations. The command itself says it.
            brief = principal.conversation(f"{director.command} {arguments.TOLD}")
            agents.converse(argv, brief, project, agent.name)
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
        upkeep.auditor(project)
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
        upkeep.night(project, tickets, director.workspace)
        if not free:
            print(f"{BUSY}; it will carry these out")
            return
        with _watching(project, director.shown(), args.no_tabs):
            director.run()


def _closed(epic: str, project: Path, tickets: Tickets) -> None:
    tickets.close(epic)
    print(f"{epic} closed")
    upkeep.epic_closed(epic, project, tickets)


def _close(epic: str, project: Path, tickets: Tickets) -> None:
    """Close an epic: at once, or by a run of the whole test suite where the project has one."""
    suite = bool(config.load(project).suite)
    epics.close(tickets, epic, suite)
    if not suite:
        upkeep.epic_closed(epic, project, tickets)


def _trusted(project: Path) -> bool:
    """Whether the command comes from the user or the Principal, not another agent."""
    who = os.environ.get(agents.WHO, "")
    return not who or who in {agent.name for agent in config.load(project).with_role(PRINCIPAL)}


def _edit(args: argparse.Namespace, project: Path, tickets: Tickets) -> None:
    if not _trusted(project):
        raise LookupError("only the user or the Principal can edit a ticket")
    writing.edit(tickets, args.ticket, args.title, args.spec, forms.write)


def _web(port: int, project: Path, home: Path, tickets: Tickets) -> None:
    key = secrets.token_urlsafe(16)  # shown only here: an agent cannot approve its own work

    def started(address: str) -> None:
        print(f"the tickets of this project are at {address}", flush=True)
        print(f"to approve and answer from the page, open it once at {address}#{key}", flush=True)

    workspace = Workspace(project, home / "work")
    web.serve(
        *(port, lambda what: views.data(what, project, tickets, workspace), started),
        *(lambda order: orders.asked(tickets, order), key),
    )


def _known(project: Path, command: str) -> None:
    """Refuse a command given where no project is. Given by mistake in a folder of a network
    drive, one left a `.devkit` there and ended in a crash: database is locked."""
    marks = (config.FILE, ".git", HOME)
    if command not in _ANYWHERE and not any((project / mark).exists() for mark in marks):
        raise config.ConfigError(
            f"there is no project in {project}: go to the project's folder or name it with "
            "--project; `dk init` begins one"
        )


def _execute(args: argparse.Namespace) -> None:
    project: Path = args.project.resolve()
    _known(project, args.command)
    home = project / HOME
    home.mkdir(exist_ok=True)
    (home / ".gitignore").write_text("*\n")
    tickets = Tickets(home / "tickets.db")
    copies = Workspace(project, home / "work")
    commands: dict[str, Callable[[], None]] = {
        "add": lambda: writing.add(args, tickets),
        "propose": lambda: writing.propose(args, tickets),
        "move": lambda: writing.move(tickets, args.ticket, args.epic, _trusted(project)),
        "audit": lambda: upkeep.audit(args.kind, args.note, project, tickets, args.part),
        "document": lambda: upkeep.document(args.note, project, tickets),
        "night": lambda: _night(args, project, home, tickets),
        "check": lambda: _check(project, home),
        "init": lambda: print(*starter.write(project, args.model, args.program), sep="\n"),
        "run": lambda: _run(args, project, home, tickets),
        "talk": lambda: _talk(project, home, tickets, args.no_tabs),
        "status": lambda: (
            views.watch(project, tickets)
            if args.watch
            else views.status(tickets.all(), tickets.closed(), tickets.trusted())
        ),
        "follow": lambda: views.follow(args.log),
        "web": lambda: _web(args.port, project, home, tickets),
        "show": lambda: views.show(tickets, copies, args.ticket),
        "retry": lambda: orders.retry(
            tickets, args.ticket, args.note, copies if args.no_behaviour_tests else None
        ),
        "cancel": lambda: orders.leave(tickets, args.ticket),
        "pause": lambda: orders.leave(tickets, args.ticket, pause=True),
        "epic": lambda: epics.describe(tickets, args.name, args.spec),
        "close": lambda: _close(args.epic, project, tickets),
        "reopen": lambda: epics.reopen(tickets, args.epic),
        "edit": lambda: _edit(args, project, tickets),
        "trust": lambda: epics.trust(tickets, args.epic, not args.withdraw),
        "approve": lambda: orders.decide(
            tickets, args.ticket, True, "", not args.no_behaviour_tests, args.conversation
        ),
        "reject": lambda: orders.decide(
            tickets, args.ticket, False, args.note, told=args.conversation
        ),
    }
    commands[args.command]()


def main(argv: Sequence[str] | None = None) -> int:
    try:
        _execute(arguments.parser(list(audits.AUDITS), list(agents.PROGRAMS)).parse_args(argv))
    except (config.ConfigError, agents.UnknownProgram, LookupError, RuntimeError) as error:
        print(f"dk: {error}")
        return 1
    return 0
