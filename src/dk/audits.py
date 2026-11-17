"""The kinds of audit and what an auditor is told. Words only; it starts nothing."""

from __future__ import annotations

_AUDITOR = """\
You audit a project. The current directory is a throwaway copy of it: build it, run it and
measure freely. Only your report is kept.

{about}
{tools}Use the scanners and profilers this kind of project has, if installed; say which
were missing, and install nothing. Do not fix anything.
Write your report to {report}. For each finding give its severity (high, medium or low),
where it is and the evidence (the command run and what it showed).
Report what you observed, not what might be. Say what you checked and found fine,
and what you could not check.
Propose a ticket for the findings that matter most, five at most; the user decides:
`{command} propose "TITLE" --spec "WHAT AND WHY"`
{known}End the report with the tools you recommend, after looking on the web: what each is
for and how to install it. Name first, apart, those this audit lacked and what each would
have shown; only they go in the `[audit]` line of devkit.toml, `tools = [...]`, by command.

End your reply with exactly one of these lines:
RESULT: done
{always}"""

AUDITS = {
    "security": "Audit the security of this project: how secrets and credentials are handled, "
    "what is done with input from outside, how cryptography is used, permissions, "
    "dependencies with known vulnerabilities, and container images if it has any.",
    "performance": "Audit the performance of this project: find where the product is slow or "
    "wasteful. Measure: time its start and its main operations and profile where you can. "
    "Point at code only with a measurement or a plain reason behind it.",
    "tests": "Audit how well this project's tests protect it. Break the code on purpose, "
    "one small change at a time (mutation testing, with a tool for its language), and find "
    "the changes no test notices. Look too for behaviour that has no test and for tests "
    "that would pass whatever the code did. Then try the unusual and the wrong: empty, "
    "huge or malformed input, limits, work that fails halfway, is cancelled or times out. "
    "Name each such case that has no test.",
}


def brief(
    about: str, report: str, tools: tuple[str, ...], command: str, known: list[str], always: str
) -> str:
    """`about` is the ticket as agents are told it, `known` the titles of tickets already
    asked for or turned down, `always` the answers every agent may give."""
    expected = f"The project expects these tools: {', '.join(tools)}.\n" if tools else ""
    known_text = f"Propose none of these again: {'; '.join(known)}.\n" if known else ""
    return _AUDITOR.format(
        about=about,
        tools=expected,
        report=report,
        command=command,
        known=known_text,
        always=always,
    )
