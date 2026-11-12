"""The ticket list: what was asked, where each ticket is and what happened to it.

It stores and answers; it decides nothing. One SQLite file, one writer (the director).
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS ticket (
    id INTEGER PRIMARY KEY, title TEXT NOT NULL, spec TEXT NOT NULL,
    step TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, note TEXT NOT NULL DEFAULT ''
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


class Tickets:
    def __init__(self, path: Path) -> None:
        self._db = sqlite3.connect(path, autocommit=True)
        self._db.executescript(_SCHEMA)

    def add(self, title: str, spec: str, step: str) -> int:
        row = self._db.execute(
            "INSERT INTO ticket (title, spec, step) VALUES (?, ?, ?)", (title, spec, step)
        )
        assert row.lastrowid is not None
        return row.lastrowid

    def all(self) -> list[Ticket]:
        rows = self._db.execute(
            "SELECT id, title, spec, step, attempts, note FROM ticket ORDER BY id"
        )
        return [Ticket(*row) for row in rows]

    def get(self, ticket: int) -> Ticket:
        found = [candidate for candidate in self.all() if candidate.id == ticket]
        if not found:
            raise LookupError(f"there is no ticket #{ticket}")
        return found[0]

    def move(self, ticket: int, step: str, attempts: int, note: str) -> None:
        self._db.execute(
            "UPDATE ticket SET step = ?, attempts = ?, note = ? WHERE id = ?",
            (step, attempts, note, ticket),
        )

    def record(self, ticket: int, what: str) -> None:
        self._db.execute("INSERT INTO history (ticket, what) VALUES (?, ?)", (ticket, what))

    def history(self, ticket: int) -> list[str]:
        rows = self._db.execute(
            "SELECT at, what FROM history WHERE ticket = ? ORDER BY id", (ticket,)
        )
        return [f"{at}  {what}" for at, what in rows]
