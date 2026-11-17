"""Work on the whole project rather than on one ticket: audits and documentation runs, asked
for by the user, by the close of an epic or by the night shift.

A composer: it reads the settings, the process and the project's history, and writes the
ticket list. It starts nothing.
"""

from __future__ import annotations

from pathlib import Path

from dk import audits, config, documents, jobs, process
from dk.tickets import Tickets
from dk.workspace import Workspace


def _staffed(project: Path, steps: tuple[process.Step, ...]) -> bool:
    """Whether the project has somebody for the work these steps begin with."""
    return bool(config.load(project).with_role(steps[0].role))


def _needs(project: Path, steps: tuple[process.Step, ...]) -> None:
    if not _staffed(project, steps):
        raise config.ConfigError(f"no agent has the role '{steps[0].role}'")


def auditor(project: Path) -> None:
    """Refuse when the project has nobody to carry out an audit."""
    _needs(project, process.AUDIT)


def _unfinished(tickets: Tickets, title: str) -> list[int]:
    """The audits or documentation runs of this title that are still to end: those at a
    step of their own process. A ticket the user gave the same title is neither."""
    return [
        ticket.id
        for ticket in tickets.all()
        if ticket.title == title and process.of(ticket.step) is not process.PROCESS
    ]


def audit(kind: str, note: str, project: Path, tickets: Tickets) -> None:
    auditor(project)
    title = _audit_title(kind)
    spec = f"{audits.AUDITS[kind]}\n{note}".strip()
    number = tickets.add(title, spec, process.AUDIT[0].name, "", [])
    print(f"#{number} written; its report will be {jobs.report(title)}")


def _audit_title(kind: str) -> str:
    return f"{kind.capitalize()} audit"


def document(note: str, project: Path, tickets: Tickets) -> None:
    """Ask for the documentation to be brought up to date; one such run at a time, for two
    would write the same files."""
    _needs(project, process.DOCUMENT)
    unfinished = _unfinished(tickets, documents.TITLE)
    if unfinished:
        raise LookupError(f"#{unfinished[0]} is still unfinished")
    _document(note, tickets)


def _document(note: str, tickets: Tickets) -> None:
    spec = f"{documents.WANTED}\n{note}".strip()
    number = tickets.add(documents.TITLE, spec, process.DOCUMENT[0].name, "", [])
    print(f"#{number} written; it will write under {' and '.join(documents.FOLDERS)}")


def _may_document(project: Path, tickets: Tickets) -> bool:
    """Whether a documentation run nobody asked for may be written: somebody documents, and
    no run is unfinished, which is said."""
    if not _staffed(project, process.DOCUMENT):
        return False
    unfinished = _unfinished(tickets, documents.TITLE)
    if unfinished:
        print(f"{documents.TITLE}: #{unfinished[0]} is still unfinished")
    return not unfinished


def epic_closed(project: Path, tickets: Tickets) -> None:
    """Have what a closed epic built documented, where somebody documents."""
    if _may_document(project, tickets):
        _document("", tickets)


def night(project: Path, tickets: Tickets, workspace: Workspace) -> None:
    """Write an audit of every kind, except one still unfinished or one whose last report
    the project has not changed since; then a documentation run where that is due."""
    for kind in audits.AUDITS:
        title = _audit_title(kind)
        unfinished = _unfinished(tickets, title)
        if unfinished:
            print(f"{title}: #{unfinished[0]} is still unfinished")
        elif not workspace.changed_since(jobs.report(title, "*")):
            print(f"{title}: nothing changed since its last report")
        else:
            audit(kind, "", project, tickets)
    _nightly_documentation(project, tickets, workspace)


def _nightly_documentation(project: Path, tickets: Tickets, workspace: Workspace) -> None:
    """A documentation run when the last was written days ago and the project, apart from
    its `docs`, changed since."""
    written = [f"{folder}/**" for folder in documents.FOLDERS]
    if not _may_document(project, tickets):
        return
    if workspace.days_since(*written) < documents.EVERY:
        print(f"{documents.TITLE}: written less than {documents.EVERY} days ago")
    elif not workspace.changed_since(*written, apart="docs"):
        print(f"{documents.TITLE}: nothing changed since it was written")
    else:
        _document("", tickets)
