"""What each agent is told. One job, the three ways to answer, and nothing about the process."""

from __future__ import annotations

_ANSWER = """\
When you have finished, end your reply with exactly one of these lines:
RESULT: done
RESULT: blocked: <why this cannot be done>
RESULT: question: <what you need to know from the user>"""

_CODER = """\
You are a coder. Work only inside the current directory, which is your own copy of the project.

Ticket #{id}: {title}
{spec}
{rework}
Make the changes the ticket asks for, with tests where the project has them.
Do not commit and do not change anything outside this directory.

{answer}"""

_REWORK = """
Your previous work on this ticket is still here but was not accepted:
{reason}
"""


def coder(ticket: int, title: str, spec: str, rejected: str) -> str:
    rework = _REWORK.format(reason=rejected) if rejected else ""
    return _CODER.format(id=ticket, title=title, spec=spec, rework=rework, answer=_ANSWER)
