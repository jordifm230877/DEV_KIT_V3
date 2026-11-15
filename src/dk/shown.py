"""Turn what an agent program prints, one event per line, into what a person reads.

It knows how Pi, Claude and Codex report their work; it starts nothing.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any


def _did(what: object) -> str:
    """A tool's use as shown; each further line of a script it ran is marked as part of it."""
    return "> " + str(what).replace("\n", "\n>   ") + "\n"


def _tool(event: dict[str, Any]) -> str:
    details = event.get("args") or {}
    return _did(f"{event.get('toolName')} {details.get('command') or details.get('path') or ''}")


def _spoken(event: dict[str, Any]) -> str:
    message = event.get("message") or {}
    if message.get("role") != "assistant":
        return ""
    texts = [part["text"] for part in message["content"] if part.get("type") == "text"]
    if message.get("errorMessage"):  # the model or its provider refused the request
        texts.append(f"error: {message['errorMessage']}")
    return "".join(text.rstrip("\n") + "\n" for text in texts)


def _pi(event: dict[str, Any]) -> str:
    shows = {"tool_execution_start": _tool, "message_end": _spoken}
    return shows.get(event.get("type", ""), lambda _: "")(event)


def _claude(event: dict[str, Any]) -> str:
    if event.get("type") == "result" and event.get("is_error"):
        return f"error: {event.get('result') or event.get('subtype')}\n"
    if event.get("type") != "assistant":
        return ""
    return "".join(_part(part) for part in event.get("message", {}).get("content", []))


_SHOWN = ("command", "file_path", "pattern", "query", "url")  # what says most about a tool's use


def _part(part: dict[str, Any]) -> str:
    """One piece of what Claude said: words, or the tool it reached for."""
    if part.get("type") == "text":
        return str(part["text"]).rstrip("\n") + "\n"
    if part.get("type") != "tool_use":
        return ""
    given = part.get("input") or {}
    what = next((given[key] for key in _SHOWN if key in given), "")
    return _did(f"{part.get('name')} {what}")


def _codex(event: dict[str, Any]) -> str:
    item = event.get("item") or {}
    step = (event.get("type"), item.get("type"))
    if step == ("item.started", "command_execution"):
        return _did(item.get("command"))
    if step == ("item.completed", "web_search") and item.get("query"):
        return f"> web search {item['query']}\n"
    if step == ("item.completed", "agent_message"):
        return str(item.get("text", "")).rstrip("\n") + "\n"
    return _failure(event) if step[0] in ("error", "turn.failed") else ""


def _failure(event: dict[str, Any]) -> str:
    failure = event.get("message") or (event.get("error") or {}).get("message")
    return f"error: {failure}\n" if failure else ""


_READERS = {"pi": _pi, "claude": _claude, "codex": _codex}


def reader(program: str) -> Callable[[str], str]:
    """How to turn each line a program prints into what is shown; by default, as it is.

    The known programs print one event per line; a line that is not one is shown as it is.
    """
    if program not in _READERS:
        return str
    show = _READERS[program]

    def plain(line: str) -> str:
        try:
            event = json.loads(line)
        except ValueError:
            return line
        return show(event) if isinstance(event, dict) else line

    return plain
