"""A coder can leave a note for the user with its answer, and proposes work it comes across
instead of doing it. The note is for the user and the Principal, not for the reviewers."""

from __future__ import annotations

from conftest import Project

SEEN = "pathlib.Path(sys.argv[0] + '.brief').write_text(prompt)\n"
NOTES = (
    "pathlib.Path('greeting.txt').write_text('hello\\n')\n"
    "print('RESULT: done: I wrote it in English; the ticket does not say which language.')"
)
# A stand-in coder that proposes what it found with the command its brief gives it.
PROPOSES = """
import re, shlex, subprocess
dk = shlex.split(re.search(r"`([^`]*-m dk[^`]*) propose", prompt).group(1))
subprocess.run([*dk, "propose", "Greet in Catalan", "--spec", "Say hola too."], check=True)
pathlib.Path('greeting.txt').write_text('hello\\n')
print('RESULT: done')
"""


def brief(project: Project, role: str) -> str:
    return (project.root.parent / "tools" / f"{role}.py.brief").read_text()


def test_what_a_coder_notes_with_its_answer_is_kept_with_the_ticket(project: Project) -> None:
    project.configure(coder=NOTES)
    project.dk("add", "Greet", "--spec", "Say hello.")

    project.dk("run")

    assert "#1 done" in project.dk("status")
    shown = project.dk("show", "1")
    assert "coder-1 noted: I wrote it in English; the ticket does not say which language." in shown


def test_a_reviewer_is_not_shown_the_coders_note(project: Project) -> None:
    project.configure(coder=NOTES, verifier=SEEN + "print('RESULT: approved')")
    project.dk("add", "Greet", "--spec", "Say hello.")

    project.dk("run")

    assert "English" not in brief(project, "verifier")


def test_a_coder_is_told_how_to_leave_a_note_and_to_propose_other_work(project: Project) -> None:
    project.configure(coder=SEEN + NOTES)
    project.dk("add", "Greet", "--spec", "Say hello.")

    project.dk("run")

    told = brief(project, "coder")
    assert "RESULT: done: <" in told and "departed from the ticket" in told
    assert "never do it" in told and f"--project {project.root} propose" in told


def test_work_a_coder_comes_across_becomes_a_proposal_in_the_same_epic(project: Project) -> None:
    project.configure(coder=PROPOSES)
    project.dk("add", "Greet", "--spec", "Say hello.", "--epic", "Manners")

    project.dk("run")

    assert project.dk("status").splitlines() == [
        "Manners",
        "  #1 done  Greet",
        "  #2 proposed  Greet in Catalan",
    ]
    assert "proposed by coder-1 while on #1 Greet" in project.dk("show", "2")
