"""The lessons a project keeps from its finished work, and what the agents that write, check
and read them are told. Words only; it starts nothing."""

from __future__ import annotations

import re

FILE = "docs/lessons.md"  # all that is kept of what the auditor leaves
LIMIT = 300  # words: the file is read before every ticket
READ = f"Read {FILE} first: what earlier work on this project taught.\n"
# How the history of a ticket says that its work was sent back, or that an agent stopped.
TROUBLE = re.compile(r"rejected the |: (blocked|question): ")

_LEARNER = """\
You draw lessons from finished work, in a throwaway copy of the project. Only {file} is kept.

{about}
Read what happened on each ticket named above: `{command} show N`.
Look for what went wrong more than once or cost the most work: what a verifier rejected,
where an agent was blocked or had to ask.
Write at most three lessons, or none: most epics teach nothing new. Each is one line of {file}:
`- What to do or not to do, concretely. (#N, #M)`
ending with the tickets it comes from. An agent starting any ticket of this project must be
able to follow it.
Write none that AGENTS.md or the file already says, none about what will not come up
again, none that only asks for care.
The file may hold {limit} words and is read before every ticket: to add to a full one, take
out the lessons that matter least, or that the project's code or rules now make needless.

End your reply with exactly one of these lines:
RESULT: done
{always}"""

_CHECKER = """\
You check the lessons a project is about to keep, in a copy of it.

{about}
See what changed: git diff {base} -- {file}

Reject unless every lesson added:
- names the tickets it comes from, and `{command} show N` shows that it happened there;
- says concretely what to do or not to do: one can tell whether an agent followed it;
- holds for later tickets of this project, not only for the one it comes from;
- neither repeats nor contradicts AGENTS.md or another lesson.
Reject more than three lessons added. A lesson taken out needs no reason.
A rejection names all that must change, not the first fault found.
Change no file: it would be thrown away.

End your reply with exactly one of these lines:
RESULT: approved
RESULT: rejected: <which lessons must go or change, and why>
{always}"""


def title(epic: str) -> str:
    return f"Lessons of {epic}"


def wanted(epic: str, troubled: list[int]) -> str:
    """What the ticket asks for; `troubled` are the tickets to learn from."""
    numbers = ", ".join(f"#{number}" for number in troubled)
    return (
        f"Draw the lessons of epic {epic}, now closed. On these tickets of it work was "
        f"rejected, or an agent was blocked or had to ask: {numbers}."
    )


def over(text: str) -> str:
    """Why the file cannot be kept as it is, if it has grown past its limit."""
    words = len(text.split())
    if words <= LIMIT:
        return ""
    return f"{FILE} has {words} words and may hold {LIMIT}: take out the lessons that matter least"


def brief(about: str, command: str, always: str) -> str:
    """`about` is the ticket as agents are told it, `always` the answers every agent may give."""
    return _LEARNER.format(about=about, file=FILE, command=command, limit=LIMIT, always=always)


def check(about: str, base: str, command: str, always: str) -> str:
    return _CHECKER.format(about=about, base=base, file=FILE, command=command, always=always)
