"""What each agent is told. One job, the ways to answer, and nothing about the process."""

from __future__ import annotations

_TICKET = """\
Ticket #{id}: {title}
{spec}
"""

_NOTE = """
Notes from earlier work on this ticket:
{note}
"""

_ALWAYS = """\
RESULT: blocked: <why this cannot be done>
RESULT: question: <what you need to know from the user>"""

_CODER = """\
You are a coder. Work only inside the current directory, which is your own copy of the project.

{ticket}{note}
Make the changes the ticket asks for, with tests where the project has them.
Do not commit and do not change anything outside this directory.

When you have finished, end your reply with exactly one of these lines:
RESULT: done
{always}"""

_REVIEWER = """\
You are {who}. The current directory is a copy of the project with the work for this ticket.

{ticket}
See what was changed with: git diff {base}

{task}
Do not change any file; anything you change is thrown away.

End your reply with exactly one of these lines:
RESULT: approved
RESULT: rejected: <what must change, concretely>
{always}"""

_TASKS = {
    "verifier": (
        "a verifier",
        "Read the changes. Reject work that does not do what the ticket asks, that cheats "
        "(for example code written only to satisfy a test), that changes things the ticket "
        "did not ask for, or that is carelessly written.",
    ),
    "qa": (
        "a QA tester",
        "Try the result the way a user would: run it and check each thing the ticket asks "
        "for. Reject it if anything the ticket asks for does not actually work.",
    ),
}


def _ticket(ticket: int, title: str, spec: str) -> str:
    return _TICKET.format(id=ticket, title=title, spec=spec)


def coder(ticket: int, title: str, spec: str, note: str) -> str:
    notes = _NOTE.format(note=note) if note else ""
    return _CODER.format(ticket=_ticket(ticket, title, spec), note=notes, always=_ALWAYS)


def reviewer(role: str, ticket: int, title: str, spec: str, base: str) -> str:
    who, task = _TASKS[role]
    return _REVIEWER.format(
        who=who, ticket=_ticket(ticket, title, spec), base=base, task=task, always=_ALWAYS
    )
