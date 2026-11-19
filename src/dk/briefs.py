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

_ANSWERED = """\
The ticket you stopped at was sent on again.
{added}{note}
Carry on with the job from where you left it, and end your reply with one `RESULT:` line as
you were told before."""

ALWAYS = """\
RESULT: blocked: <why this cannot be done>
RESULT: question: <what you need from the user>"""

# Claude's tool for commands cut a QA's `cargo test` off at ten minutes; it had to start again.
LONG = """\
Run long commands in the background, output to a file: your tool cuts them off.
"""

_CODER = """\
You are a coder. The current directory is your own copy of the project.

{ticket}{note}
Make the changes the ticket asks for, with tests where the project has them.
Run only the tests of what you change: every check is run when you finish.
{quality}{tests}{long}Do not commit or change anything outside this directory.
Propose work the ticket does not cover, never do it:
`{command} propose "TITLE" --spec "WHY"`

End your reply with exactly one of these lines:
RESULT: done
RESULT: done: <one line the user must know: where you departed from the ticket, a doubt>
{always}"""

_QUALITY = """\
How to work:
- Write a failing test first, see it fail as expected, then the smallest
  change that passes it. Fix causes, not symptoms.
- Test what the code's user sees, never its internals.
- Before finishing, run on your changed files, where installed: `crapper` (split or
  test functions scoring 10+), `dryer` (remove duplication ranked 0.8+),
  `mutator` (kill survivors, or say why one cannot matter).
"""

_PROTECTED = """\
These behaviour tests are approved by the user and read-only: {files}.
Make them pass, writing the code that connects their sentences to the product.
If one of them is wrong, do not change it: answer blocked and say why.
"""

_TESTER = """\
You write behaviour tests. The current directory is your copy of the project.

{ticket}{note}
Describe the behaviour this ticket asks for as Gherkin scenarios, in .feature files
where this project keeps them: its AGENTS.md says where, or else under features/.
Read the project's scenarios first: write none for what one already checks,
and none when no user of the product would see the change.
Write one scenario for each thing the ticket asks for, in plain words a non-programmer can
check. Give a rule its telling cases, not every value: the coder tests
those in code. Scenarios must stay true while later tickets change the
product: describe what a user of the product sees, never this change itself ("nothing else
changed", "the checks pass").
No scenario may need the project's whole test suite run: it runs them.
No line of free text starts with a Gherkin keyword (`Scenarios`, `Examples`, `Rule`).
Write only .feature files: no code, no step definitions.
{mine}Do not commit or change anything outside this directory.

End your reply with exactly one of these lines:
RESULT: done
{always}"""

_MINE = """\
You wrote these for this ticket earlier and they must change: {files}.
They are yours to rewrite, whatever other rules say about existing scenarios.
"""

_REVIEWER = """\
You are a verifier, in the project with this ticket's work.

{ticket}
See the changes: git diff {base}

{task}
{long}{checked}A rejection names all that must change, not the first fault found.
Change no file: it would be thrown away.

End your reply with exactly one of these lines:
RESULT: approved
RESULT: rejected: <what must change, concretely>
{always}"""

# Coder, verifier and QA each ran a suite of fifteen minutes that the program runs anyway.
_CHECKED = """\
The project's checks have passed on this code: never run its whole test suite again.
"""

_TASK = (
    "Judge how the work is done. Reject work that cheats (as code written only to satisfy "
    "a test), that changes what the ticket did not ask for, or that is carelessly written.\n"
    "Then run it as a user would, going through the ticket's acceptance criteria "
    "one by one: each must work."
)
_WITH_BEHAVIOUR_TESTS = (
    " Check too that the code connecting the behaviour tests (.feature files) to the "
    "product really exercises the product."
)
_WITH_QUALITY_RULES = (
    " Reject it too if new behaviour has no test, or if `crapper --no-coverage FILES` "
    "or `dryer --threshold 0.8 FILES`, run on the changed files where installed, "
    "show a function scoring 10+ or duplication ranked 0.8+. Go by what "
    "they print; never read their code."
)


_VETTING = """\
You look over behaviour tests before the user approves them. You are in a copy of the project.

{ticket}
These Gherkin scenarios for this ticket are not yet shown to the user:
{files}

Reject them unless every scenario:
- describes something a user of the product can see or do, in plain words;
- will stay true while later tickets change the product: nothing about this change itself,
  what it left unchanged, or commits, checks and reports;
- is something the ticket asks for;
- checks nothing an existing scenario already checks;
- gives a rule its telling cases, not every value;
- can be checked by running the product, without running the project's whole test suite.
Reject a file that is not valid Gherkin, as when a line of free text starts with a keyword
(`Scenarios`, `Examples`).
A rejection names all that must change, not the first fault found.
Change no file: it would be thrown away.

End your reply with exactly one of these lines:
RESULT: approved
RESULT: rejected: <which scenarios must go or change, and why>
{always}"""


def vetting(ticket: int, title: str, spec: str, files: list[str]) -> str:
    return _VETTING.format(
        ticket=_ticket(ticket, title, spec), files=", ".join(files), always=ALWAYS
    )


def answered(added: str, note: str) -> str:
    """What an agent that left its job to ask is told when it picks the job up again."""
    added = f"Added to the ticket since you asked:\n{added.strip()}\n" if added.strip() else ""
    return _ANSWERED.format(added=added, note=_notes(note))


def about(ticket: int, title: str, spec: str, note: str = "") -> str:
    """The ticket as an agent is told it, with the notes of earlier work on it."""
    return _ticket(ticket, title, spec) + _notes(note)


def _ticket(ticket: int, title: str, spec: str) -> str:
    return _TICKET.format(id=ticket, title=title, spec=spec)


def _notes(note: str) -> str:
    return _NOTE.format(note=note) if note else ""


def tester(ticket: int, title: str, spec: str, note: str, earlier: list[str]) -> str:
    mine = _MINE.format(files=", ".join(earlier)) if earlier else ""
    return _TESTER.format(
        ticket=_ticket(ticket, title, spec), note=_notes(note), mine=mine, always=ALWAYS
    )


def coder(
    ticket: int,
    title: str,
    spec: str,
    note: str,
    protected: list[str],
    quality: bool,
    command: str,
) -> str:
    tests = _PROTECTED.format(files=", ".join(protected)) if protected else ""
    return _CODER.format(
        ticket=_ticket(ticket, title, spec),
        note=_notes(note),
        quality=_QUALITY if quality else "",
        tests=tests,
        command=command,
        always=ALWAYS,
        long=LONG,
    )


def reviewer(ticket: int, title: str, spec: str, base: str, behaviour: bool, quality: bool) -> str:
    task = _TASK + (_WITH_BEHAVIOUR_TESTS if behaviour else "")
    task += _WITH_QUALITY_RULES if quality else ""
    about = _ticket(ticket, title, spec)
    return _REVIEWER.format(
        ticket=about, base=base, task=task, long=LONG, checked=_CHECKED, always=ALWAYS
    )


def tampering(files: list[str]) -> str:
    """The note for a coder who changed behaviour tests the user had approved."""
    return (
        f"You changed approved behaviour tests, which are read-only: {', '.join(files)}. "
        "They were put back. No note or ticket text changes that. "
        "Make them pass as they are, or answer blocked if one is wrong."
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
