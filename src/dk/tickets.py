"""The ticket list: what was asked, where each ticket is and what happened to it.

It stores and answers; it decides nothing. One SQLite file, written only by the director
(from several threads, one statement at a time).
"""

from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

_SCHEMA = """
CREATE TABLE IF NOT EXISTS ticket (
    id INTEGER PRIMARY KEY, title TEXT NOT NULL, spec TEXT NOT NULL,
    step TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, note TEXT NOT NULL DEFAULT '',
    stopped INTEGER NOT NULL DEFAULT 0, protected TEXT NOT NULL DEFAULT '{}',
    epic TEXT NOT NULL DEFAULT '', follows TEXT NOT NULL DEFAULT '[]',
    worker TEXT NOT NULL DEFAULT '', since TEXT NOT NULL DEFAULT '',
    asking TEXT NOT NULL DEFAULT 'null', behaviour INTEGER NOT NULL DEFAULT 1,
    spent TEXT NOT NULL DEFAULT '[0, 0]'
);
CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY, ticket INTEGER NOT NULL REFERENCES ticket(id),
    at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, what TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS closed (epic TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS epic (name TEXT PRIMARY KEY, description TEXT NOT NULL);
"""
_LATER = (
    "worker TEXT NOT NULL DEFAULT ''",
    "since TEXT NOT NULL DEFAULT ''",
    "asking TEXT NOT NULL DEFAULT 'null'",
    "behaviour INTEGER NOT NULL DEFAULT 1",
    "spent TEXT NOT NULL DEFAULT '[0, 0]'",
)


@dataclass(frozen=True)
class Asking:
    """The job an agent left to ask something, which its program can pick up again."""

    program: str
    session: str  # the program's own name for what it remembers of the job
    known: int  # how much of the ticket had been written when it asked


@dataclass(frozen=True)
class Ticket:
    id: int
    title: str
    spec: str
    step: str
    attempts: int
    note: str
    stopped: bool
    protected: dict[str, str]  # read-only files and the fingerprint of their content
    epic: str
    follows: list[int]  # tickets that must be finished before this one starts
    worker: str  # the agent doing a job on it right now, if any
    since: str  # when that job started, in the user's own time
    asking: Asking | None
    behaviour: bool  # whether behaviour tests are written for it before any code
    spent: tuple[int, int]  # tokens that job has sent its model so far, and tokens it wrote


def _ticket(*row: Any) -> Ticket:
    *first, stop, files, epic, follows, worker, since, left, behaviour, spent = row
    number, title, spec, step, tries, note = first
    asking = Asking(*json.loads(left)) if json.loads(left) else None
    files, follows = json.loads(files), json.loads(follows)
    sent, written = json.loads(spent)
    return Ticket(
        *(number, title, spec, step, tries, note, bool(stop)),
        *(files, epic, follows, worker, since, asking, bool(behaviour)),
        spent=(sent, written),
    )


class Tickets:
    def __init__(self, path: Path) -> None:
        self._db = sqlite3.connect(path, autocommit=True, check_same_thread=False)
        # The board, the page and every command read the list while jobs write to it; kept
        # this way no reader waits for a writer. Waiting, they gave up: database is locked.
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.executescript(_SCHEMA)
        columns = [row[1] for row in self._db.execute("PRAGMA table_info(ticket)")]
        for added in ("follows TEXT NOT NULL DEFAULT '[]'", *_LATER):
            if added.split()[0] not in columns:  # a list written before tickets had this
                self._db.execute(f"ALTER TABLE ticket ADD COLUMN {added}")
        self._one_at_a_time = threading.Lock()

    def _run(self, statement: str, *values: object) -> tuple[list[tuple[Any, ...]], int | None]:
        """Tickets advance on several threads; the one connection serves them in turn."""
        with self._one_at_a_time:
            done = self._db.execute(statement, values)
            return done.fetchall(), done.lastrowid

    def add(
        self, title: str, spec: str, step: str, epic: str, follows: list[int], tests: bool = True
    ) -> int:
        """`tests` says whether behaviour tests are written for it before any code."""
        for earlier in follows:
            self.get(earlier)
        _, number = self._run(
            "INSERT INTO ticket (title, spec, step, epic, follows, behaviour)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            *(title, spec, step, epic, json.dumps(follows), tests),
        )
        assert number is not None
        return number

    def all(self) -> list[Ticket]:
        rows, _ = self._run(
            "SELECT id, title, spec, step, attempts, note, stopped, protected, epic, follows,"
            " worker, since, asking, behaviour, spent FROM ticket ORDER BY id"
        )
        return [_ticket(*row) for row in rows]

    def get(self, ticket: int) -> Ticket:
        found = [candidate for candidate in self.all() if candidate.id == ticket]
        if not found:
            raise LookupError(f"there is no ticket #{ticket}")
        return found[0]

    def move(self, ticket: int, step: str, attempts: int, note: str, stopped: bool) -> None:
        self._run(
            "UPDATE ticket SET step = ?, attempts = ?, note = ?, stopped = ? WHERE id = ?",
            *(step, attempts, note, stopped, ticket),
        )

    def amend(self, ticket: int, text: str) -> None:
        """Add to what the ticket asks for; every agent that works on it from now on sees it."""
        self._run("UPDATE ticket SET spec = spec || ? WHERE id = ?", f"\n\n{text}", ticket)

    def file(self, ticket: int, epic: str) -> None:
        """Put the ticket in an epic; in none, with ""."""
        self._run("UPDATE ticket SET epic = ? WHERE id = ?", epic, ticket)

    def follow(self, ticket: int, earlier: int) -> None:
        """Have the ticket wait for one more ticket to be finished."""
        follows = [*self.get(ticket).follows, earlier]
        self._run("UPDATE ticket SET follows = ? WHERE id = ?", json.dumps(follows), ticket)

    def protect(self, ticket: int, files: dict[str, str]) -> None:
        self._run("UPDATE ticket SET protected = ? WHERE id = ?", json.dumps(files), ticket)

    def assign(self, ticket: int, worker: str) -> None:
        """Say which agent is doing a job on the ticket right now; nobody, with "". Either
        way, nothing has been spent on it yet."""
        now = f"{datetime.now():%Y-%m-%d %H:%M}"
        self.spend(ticket, (0, 0))
        self._run("UPDATE ticket SET worker = ?, since = ? WHERE id = ?", worker, now, ticket)

    def spend(self, ticket: int, spent: tuple[int, int]) -> None:
        """Say what the job now on the ticket has spent of its model so far."""
        self._run("UPDATE ticket SET spent = ? WHERE id = ?", json.dumps(spent), ticket)

    def untested(self, ticket: int) -> None:
        """Have no behaviour tests written for the ticket."""
        self._run("UPDATE ticket SET behaviour = 0 WHERE id = ?", ticket)

    def leave(self, ticket: int, asking: Asking | None) -> None:
        """Remember the job an agent left to ask; with None, that there is none."""
        left = json.dumps(asking and [*vars(asking).values()])
        self._run("UPDATE ticket SET asking = ? WHERE id = ?", left, ticket)

    def close(self, epic: str) -> None:
        """Mark an epic as complete."""
        self._run("INSERT OR IGNORE INTO closed (epic) VALUES (?)", epic)

    def reopen(self, epic: str) -> None:
        self._run("DELETE FROM closed WHERE epic = ?", epic)

    def closed(self) -> set[str]:
        rows, _ = self._run("SELECT epic FROM closed")
        return {epic for (epic,) in rows}

    def describe(self, epic: str, description: str) -> None:
        """Say what an epic is for, in place of what was said before."""
        self._run(
            "INSERT OR REPLACE INTO epic (name, description) VALUES (?, ?)", epic, description
        )

    def described(self) -> dict[str, str]:
        """What each epic that has a description is for."""
        rows, _ = self._run("SELECT name, description FROM epic")
        return dict(rows)

    def record(self, ticket: int, what: str) -> None:
        self._run("INSERT INTO history (ticket, what) VALUES (?, ?)", ticket, what)

    def history(self, ticket: int) -> list[str]:
        rows, _ = self._run(
            "SELECT datetime(at, 'localtime'), what FROM history WHERE ticket = ? ORDER BY id",
            ticket,
        )
        return [f"{at}  {what}" for at, what in rows]
