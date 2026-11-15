"""Count what a job spends of its model, from what the agent's program prints as it works:
the tokens sent to the model, and the tokens the model wrote.

It knows how Pi, Claude and Codex report them. Each call to the model sends again all that
was said before it, so what was sent adds up to far more than the job ever held at once.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

Spent = tuple[int, int]  # tokens sent to the model, and tokens it wrote
_Calls = dict[object, Spent]  # what each call to the model spent
_PI = ("input", "cacheRead", "cacheWrite", "output")
_CLAUDE = ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")
_CODEX = ("input_tokens", "output_tokens")  # what it had kept is already in what it was sent


def _of(usage: object, *names: str) -> Spent:
    """What one report says was spent; the last name is that of what the model wrote."""
    said = usage if isinstance(usage, dict) else {}
    *sent, written = (int(said.get(name) or 0) for name in names)
    return sum(sent), written


def _pi(event: dict[str, Any], calls: _Calls) -> None:
    if event.get("type") == "turn_end":
        calls[len(calls)] = _of((event.get("message") or {}).get("usage"), *_PI)


def _claude(event: dict[str, Any], calls: _Calls) -> None:
    """Each call is reported as it happens, more than once; the job's total, as it ends."""
    message = event.get("message") or {}
    if event.get("type") == "assistant":
        calls[message.get("id")] = _of(message.get("usage"), *_CLAUDE, "output_tokens")
    if event.get("type") == "result":
        calls.clear()
        calls[""] = _of(event.get("usage"), *_CLAUDE, "output_tokens")


def _codex(event: dict[str, Any], calls: _Calls) -> None:
    if event.get("type") == "turn.completed":
        calls[len(calls)] = _of(event.get("usage"), *_CODEX)


_COUNTS = {"pi": _pi, "claude": _claude, "codex": _codex}


def counter(program: str) -> Callable[[str], Spent]:
    """What to give each line a program prints, to be told what its job has spent so far.
    A program that is not known, or says nothing of it, has spent nothing."""
    count = _COUNTS.get(program)
    calls: _Calls = {}

    def spent(line: str) -> Spent:
        try:
            event = json.loads(line)
        except ValueError:
            event = None
        if count and isinstance(event, dict):
            count(event, calls)
        return sum(sent for sent, _ in calls.values()), sum(wrote for _, wrote in calls.values())

    return spent


def _short(count: int) -> str:
    for least, unit in ((1_000_000, "M"), (1_000, "k")):
        if count >= least:
            return f"{count / least:.1f}{unit}"
    return str(count)


def said(spent: Spent) -> str:
    """What was spent, in words; nothing if nothing was."""
    return f"{_short(spent[0])} tokens in, {_short(spent[1])} out" if any(spent) else ""
