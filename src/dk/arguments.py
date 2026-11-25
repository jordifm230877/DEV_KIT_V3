"""The `dk` command: write tickets, run them, see where they are."""

from __future__ import annotations

import argparse
from pathlib import Path


def parser(audits: list[str], programs: list[str]) -> argparse.ArgumentParser:
    """`audits` are the kinds of audit there are, `programs` the agent programs known."""
    parser = argparse.ArgumentParser(prog="dk", description=__doc__)
    parser.add_argument("--project", type=Path, default=Path.cwd(), help="the project directory")
    commands = parser.add_subparsers(dest="command", required=True)
    add = commands.add_parser("add", help="write a new ticket")
    add.add_argument("title")
    add.add_argument("--spec", required=True, help="what is wanted and how to tell it is done")
    add.add_argument("--epic", default="", help="the epic it belongs to; every ticket has one")
    tests = add.add_mutually_exclusive_group()
    tests.add_argument(
        "--behaviour-tests",
        action="store_true",
        help="for a ticket that changes what a user of the product sees; so it is, unsaid",
    )
    tests.add_argument(
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
    move = commands.add_parser("move", help="put a proposed ticket in an epic, or take it out")
    move.add_argument("ticket", type=int)
    where = move.add_mutually_exclusive_group(required=True)
    where.add_argument("--epic", default="", help="the epic it joins")
    where.add_argument("--no-epic", action="store_true", help="it belongs to no epic")
    audit = commands.add_parser("audit", help="have the whole project audited; leaves a report")
    audit.add_argument("kind", choices=audits)
    audit.add_argument("--note", default="", help="what to look at in particular")
    document = commands.add_parser("document", help="have the documentation brought up to date")
    document.add_argument("--note", default="", help="what to write or correct in particular")
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
    init.add_argument("--program", default="pi", choices=programs, help="their program")
    commands.add_parser("check", help="find what would stop the first ticket")
    status = commands.add_parser("status", help="list the tickets")
    status.add_argument("--watch", action="store_true", help="keep showing agents and tickets")
    show = commands.add_parser("show", help="one ticket and everything that happened to it")
    show.add_argument("ticket", type=int)
    retry = commands.add_parser("retry", help="send a stopped ticket on again")
    retry.add_argument("ticket", type=int)
    retry.add_argument("--note", default="", help="an answer or instruction for the agent")
    retry.add_argument(
        "--no-behaviour-tests",
        action="store_true",
        help="go on to the coder: the ticket changes nothing a user of the product can see",
    )
    commands.add_parser("cancel", help="give a ticket up and throw its work away").add_argument(
        "ticket", type=int
    )
    site = commands.add_parser("web", help="show the agents and the tickets in a browser")
    site.add_argument("--port", type=int, default=8642, help="where on this computer; 0 for any")
    follow = commands.add_parser("follow", help="show a file of an agent's work, in colour")
    follow.add_argument("log", type=Path)
    epic = commands.add_parser("epic", help="say what an epic is for, or show it")
    epic.add_argument("name")
    epic.add_argument("--spec", default="", help="its goal, what it includes and what it excludes")
    commands.add_parser("close", help="mark an epic as complete").add_argument("epic")
    commands.add_parser("reopen", help="open a closed epic again").add_argument("epic")
    trust = commands.add_parser("trust", help="have an epic's behaviour tests go on unapproved")
    trust.add_argument("epic", nargs="?", default="", help="none: say which are trusted")
    trust.add_argument("--withdraw", action="store_true", help="they wait for you again")
    approve = commands.add_parser("approve", help="accept what waits for you")
    approve.add_argument("ticket", type=int)
    approve.add_argument(
        "--no-behaviour-tests", action="store_true", help="for a proposed ticket you accept"
    )
    reject = commands.add_parser("reject", help="send back what waits for you")
    reject.add_argument("ticket", type=int)
    reject.add_argument("--note", required=True, help="what must change")
    return parser
