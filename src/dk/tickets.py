"""The ticket list: what was asked, where each ticket is and what happened to it.

It stores and answers; it decides nothing. One SQLite file, written only by the director
(from several threads, one statement at a time).
"""

from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_SCHEMA = """
CREATE TABLE IF NOT EXISTS ticket (
    id INTEGER PRIMARY KEY, title TEXT NOT NULL, spec TEXT NOT NULL,
    step TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, note TEXT NOT NULL DEFAULT '',
    stopped INTEGER NOT NULL DEFAULT 0, protected TEXT NOT NULL DEFAULT '{}',
    epic TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY, ticket INTEGER NOT NULL REFERENCES ticket(id),
    at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, what TEXT NOT NULL
);
"""


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


class Tickets:
    def __init__(self, path: Path) -> None:
        self._db = sqlite3.connect(path, autocommit=True, check_same_thread=False)
        self._db.executescript(_SCHEMA)
        self._one_at_a_time = threading.Lock()

    def _run(self, statement: str, *values: object) -> tuple[list[tuple[Any, ...]], int | None]:
        """Tickets advance on several threads; the one connection serves them in turn."""
        with self._one_at_a_time:
            done = self._db.execute(statement, values)
            return done.fetchall(), done.lastrowid

    def add(self, title: str, spec: str, step: str, epic: str) -> int:
        _, number = self._run(
            "INSERT INTO ticket (title, spec, step, epic) VALUES (?, ?, ?, ?)",
            *(title, spec, step, epic),
        )
        assert number is not None
        return number

    def all(self) -> list[Ticket]:
        rows, _ = self._run(
            "SELECT id, title, spec, step, attempts, note, stopped, protected, epic FROM ticket"
            " ORDER BY id"
        )
        return [
            Ticket(number, title, spec, step, attempts, note, bool(stop), json.loads(files), epic)
            for number, title, spec, step, attempts, note, stop, files, epic in rows
        ]

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

    def protect(self, ticket: int, files: dict[str, str]) -> None:
        self._run("UPDATE ticket SET protected = ? WHERE id = ?", json.dumps(files), ticket)

    def record(self, ticket: int, what: str) -> None:
        self._run("INSERT INTO history (ticket, what) VALUES (?, ?)", ticket, what)

    def history(self, ticket: int) -> list[str]:
        rows, _ = self._run("SELECT at, what FROM history WHERE ticket = ? ORDER BY id", ticket)
        return [f"{at}  {what}" for at, what in rows]
