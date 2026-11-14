"""Colour for the lines of an agent's work or of the board, as a terminal shows them.

Only for the eye: the files that keep the work stay plain text, and this piece knows nothing
about agents or tickets beyond how their lines begin.
"""

from __future__ import annotations

import re
from collections.abc import Callable

_OFF = "\033[0m"
_BOLD, _PLAIN, _DIM = "\033[1m", "\033[22m", "\033[2m"
_RED, _GREEN, _YELLOW, _CYAN, _NO_COLOUR = (
    "\033[31m",
    "\033[32m",
    "\033[33m",
    "\033[36m",
    "\033[39m",
)

_ANSWERS = {"done": _GREEN, "approved": _GREEN, "rejected": _RED}  # any other answer waits
_WHOLE = (  # how a line begins, and the colour of all of it
    ("> ", _DIM),
    ("error:", _RED),
    ("#", _BOLD),
)
_BOARD = {  # the kinds of line on the board; any other kind is left as it is
    "heading": _BOLD + _CYAN,
    "epic": _BOLD,
    "busy": _GREEN,
    "stopped": _BOLD + _YELLOW,
    **dict.fromkeys(("free", "held", "closed", "count"), _DIM),
}
_TITLE = re.compile(r"(\d{4}-\d\d-\d\d \d\d:\d\d  )?=== ")  # a job, with when it started
_STRONG = re.compile(r"\*\*(\S(?:.*?\S)?)\*\*")
_CODE = re.compile(r"`([^`]+)`")


def line(text: str) -> str:
    """The line with colour: titles, tools, errors and the answer whole; emphasis within."""
    if text.startswith("RESULT:"):
        answer = text.removeprefix("RESULT:").partition(":")[0].strip()
        return f"{_BOLD}{_ANSWERS.get(answer, _YELLOW)}{text}{_OFF}"
    if _TITLE.match(text):
        return f"{_BOLD}{_CYAN}{text}{_OFF}"
    for start, colour in _WHOLE:
        if text.startswith(start):
            return f"{colour}{text}{_OFF}"
    text = _STRONG.sub(rf"{_BOLD}\1{_PLAIN}", text)
    return _CODE.sub(rf"{_CYAN}\1{_NO_COLOUR}", text)


def work() -> Callable[[str], str]:
    """Colours an agent's work line by line, remembering whether a block of code (between
    two ``` lines) is open; a block left open ends where the next job begins."""
    inside = False

    def painted(text: str) -> str:
        nonlocal inside
        fence = text.lstrip().startswith("```")
        if fence:
            inside = not inside
            return f"{_DIM}{text}{_OFF}"
        if _TITLE.match(text):
            inside = False
        return f"{_CYAN}{text}{_OFF}" if inside else line(text)

    return painted


def part(kind: str, text: str) -> str:
    """A line of the board with the colour of its kind."""
    return f"{_BOARD[kind]}{text}{_OFF}" if kind in _BOARD else text
