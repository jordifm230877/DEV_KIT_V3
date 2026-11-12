"""Finished code is read by a verifier and tried by QA before it is merged."""

from __future__ import annotations

import pytest
from conftest import Project

HELLO = "pathlib.Path('greeting.txt').write_text('hello\\n')\nprint('RESULT: done')"
APPROVES = "print('RESULT: approved')"
WANTS_HELLO = (
    "said = pathlib.Path('greeting.txt').read_text()\n"
    "print('RESULT: approved' if said == 'hello\\n' else 'RESULT: rejected: it must say hello')"
)
LEARNS = (
    "said = 'hello' if 'it must say hello' in prompt else 'hi'\n"
    "pathlib.Path('greeting.txt').write_text(said + '\\n')\nprint('RESULT: done')"
)


def test_work_is_verified_and_then_tried_by_qa_before_merging(project: Project) -> None:
    project.configure(coder=HELLO, verifier=WANTS_HELLO, qa=WANTS_HELLO)
    project.dk("add", "Greet", "--spec", "Say hello.")

    project.dk("run")

    assert project.merged("greeting.txt") == "hello\n"
    history = project.dk("show", "1")
    assert history.index("verifier-1 started") < history.index("qa-1 started")


@pytest.mark.parametrize("reviewer", ["verifier", "qa"])
def test_rejected_work_returns_to_the_coder_with_the_reason(
    project: Project, reviewer: str
) -> None:
    project.configure(coder=LEARNS, **{reviewer: WANTS_HELLO})
    project.dk("add", "Greet", "--spec", "Say hello.")

    project.dk("run")

    assert project.merged("greeting.txt") == "hello\n"
    assert "it must say hello" in project.dk("show", "1")
    assert "[1 attempt]" in project.dk("status")


def test_a_reviewer_is_told_the_ticket_and_how_to_see_the_changes(project: Project) -> None:
    keeps = "pathlib.Path(sys.argv[0]).with_name('seen.txt').write_text(prompt)\n" + APPROVES
    project.configure(coder=HELLO, verifier=keeps)
    project.dk("add", "Greet", "--spec", "Say hello.")

    project.dk("run")

    seen = (project.root.parent / "tools" / "seen.txt").read_text()
    assert "Greet" in seen and "Say hello." in seen
    assert f"git diff {project.git('rev-parse', 'HEAD~1')}" in seen
    assert len(seen.split()) < 200


def test_nothing_a_reviewer_changes_or_leaves_behind_is_merged(project: Project) -> None:
    meddles = (
        "pathlib.Path('greeting.txt').write_text('goodbye\\n')\n"
        "pathlib.Path('junk.txt').write_text('left behind\\n')\n" + APPROVES
    )
    project.configure(coder=HELLO, verifier=meddles, qa=WANTS_HELLO)
    project.dk("add", "Greet", "--spec", "Say hello.")

    project.dk("run")

    assert project.merged("greeting.txt") == "hello\n"
    assert project.merged("junk.txt") is None


def test_a_reviewer_without_a_verdict_is_asked_again_not_the_coder(project: Project) -> None:
    undecided = (
        "marker = pathlib.Path(sys.argv[0]).with_name('asked.txt')\n"
        "if marker.exists():\n"
        "    print('RESULT: approved')\n"
        "else:\n"
        "    marker.write_text('once'); print('RESULT: done')"
    )
    project.configure(coder=HELLO, verifier=undecided)
    project.dk("add", "Greet", "--spec", "Say hello.")

    project.dk("run")

    history = project.dk("show", "1")
    assert "#1 done" in history
    assert history.count("verifier-1 started") == 2 and history.count("coder-1 started") == 1


def test_a_review_nobody_is_there_to_do_is_skipped_openly(project: Project) -> None:
    project.configure(coder=HELLO, qa=APPROVES)
    project.dk("add", "Greet", "--spec", "Say hello.")

    project.dk("run")

    history = project.dk("show", "1")
    assert "verify skipped: no verifier" in history and "qa-1 started" in history


def test_a_reviewer_with_a_question_stops_the_ticket_at_its_review(project: Project) -> None:
    project.configure(coder=HELLO, qa="print('RESULT: question: hello to whom?')")
    project.dk("add", "Greet", "--spec", "Say hello.")

    project.dk("run")

    status = project.dk("status")
    assert "#1 stopped at qa" in status and "hello to whom?" in status
    assert project.merged("greeting.txt") is None
