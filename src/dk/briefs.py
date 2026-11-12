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
{tests}Do not commit and do not change anything outside this directory.

When you have finished, end your reply with exactly one of these lines:
RESULT: done
{always}"""

_PROTECTED = """\
These behaviour tests are approved by the user and read-only: {files}.
Make them pass, writing the code that connects their sentences to the product.
If one of them is wrong, do not change it: answer blocked and say why.
"""

_TESTER = """\
You write behaviour tests. The current directory is your own copy of the project.

{ticket}{note}
Describe the behaviour this ticket asks for as Gherkin scenarios in .feature files under
features/. Write one scenario for each thing the ticket asks for, in plain words that someone
who does not program can check. Write only .feature files: no code and no step definitions.
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
        " Check too that the code connecting the behaviour tests (.feature files) to the "
        "product really exercises the product.",
    ),
    "qa": (
        "a QA tester",
        "Try the result the way a user would: run it and check each thing the ticket asks "
        "for. Reject it if anything the ticket asks for does not actually work.",
        "",
    ),
}


def _ticket(ticket: int, title: str, spec: str) -> str:
    return _TICKET.format(id=ticket, title=title, spec=spec)


def _notes(note: str) -> str:
    return _NOTE.format(note=note) if note else ""


def tester(ticket: int, title: str, spec: str, note: str) -> str:
    return _TESTER.format(ticket=_ticket(ticket, title, spec), note=_notes(note), always=_ALWAYS)


def coder(ticket: int, title: str, spec: str, note: str, protected: list[str]) -> str:
    tests = _PROTECTED.format(files=", ".join(protected)) if protected else ""
    return _CODER.format(
        ticket=_ticket(ticket, title, spec), note=_notes(note), tests=tests, always=_ALWAYS
    )


def reviewer(role: str, ticket: int, title: str, spec: str, base: str, behaviour: bool) -> str:
    who, task, with_behaviour_tests = _TASKS[role]
    return _REVIEWER.format(
        who=who,
        ticket=_ticket(ticket, title, spec),
        base=base,
        task=task + (with_behaviour_tests if behaviour else ""),
        always=_ALWAYS,
    )


def tampering(files: list[str]) -> str:
    """The note for a coder who changed behaviour tests the user had approved."""
    return (
        f"You changed approved behaviour tests, which are read-only: {', '.join(files)}. "
        "They were put back. Make them pass as they are, or answer blocked if one is wrong."
    )


def clash(files: list[str]) -> str:
    """The note for a coder whose work collides with what was merged in the meantime."""
    return (
        "The project changed while this ticket was being worked on, and these files now "
        f"contain conflict markers (<<<<<<<): {', '.join(files)}. "
        "Edit them so that both changes work, and remove the markers."
    )


def approval(ticket: int) -> str:
    """What the user is told when the behaviour tests wait for their decision."""
    return (
        f"the behaviour tests are ready for you: read them with `dk show {ticket}`, then "
        f'`dk approve {ticket}` or `dk reject {ticket} --note "what to change"`'
    )
