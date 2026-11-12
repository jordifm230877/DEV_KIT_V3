"""Behaviour tests are written before the code, approved by the user, and then read-only."""

from __future__ import annotations

import pytest
from conftest import Project

FEATURE = "Feature: Greeting\\n  Scenario: Polite\\n    Then it says hello\\n"
TESTER = (
    "polite = 'good morning' if 'say good morning' in prompt else 'hello'\n"
    "pathlib.Path('features').mkdir(exist_ok=True)\n"
    f"pathlib.Path('features/greet.feature').write_text('{FEATURE}'.replace('hello', polite))\n"
    "print('RESULT: done')"
)
HELLO = "pathlib.Path('greeting.txt').write_text('hello\\n')\nprint('RESULT: done')"
APPROVED_TEXT = FEATURE.replace("\\n", "\n")


def test_the_ticket_waits_for_the_user_to_read_the_behaviour_tests(project: Project) -> None:
    project.configure(coder=HELLO, tester=TESTER)
    project.dk("add", "Greet", "--spec", "Say hello.")

    project.dk("run")

    shown = project.dk("show", "1")
    assert "#1 stopped at approve" in shown and "dk approve 1" in shown
    assert "features/greet.feature" in shown and "Then it says hello" in shown
    assert "coder-1 started" not in shown


def test_approved_behaviour_tests_let_the_coder_start(project: Project) -> None:
    project.configure(coder=HELLO, tester=TESTER)
    project.dk("add", "Greet", "--spec", "Say hello.")
    project.dk("run")

    project.dk("approve", "1")
    project.dk("run")

    assert project.merged("greeting.txt") == "hello\n"
    assert project.merged("features/greet.feature") == APPROVED_TEXT


def test_rejected_behaviour_tests_are_rewritten_with_the_users_reason(project: Project) -> None:
    project.configure(coder=HELLO, tester=TESTER)
    project.dk("add", "Greet", "--spec", "Say hello.")
    project.dk("run")

    project.dk("reject", "1", "--note", "it should say good morning")
    project.dk("run")

    shown = project.dk("show", "1")
    assert "#1 stopped at approve" in shown and "Then it says good morning" in shown
    assert "attempt" not in project.dk("status"), "the user's own decision is not a failed attempt"


@pytest.mark.parametrize(
    "tamper",
    [
        "pathlib.Path('features/greet.feature').write_text('Feature: anything goes\\n')",
        "pathlib.Path('features/greet.feature').unlink()",
    ],
)
def test_a_coder_cannot_change_approved_behaviour_tests(project: Project, tamper: str) -> None:
    coder = f"if 'put back' not in prompt:\n    {tamper}\n{HELLO}"
    project.configure(coder=coder, tester=TESTER)
    project.dk("add", "Greet", "--spec", "Say hello.")
    project.dk("run")
    project.dk("approve", "1")

    project.dk("run")

    assert project.merged("features/greet.feature") == APPROVED_TEXT
    history = project.dk("show", "1")
    assert "features/greet.feature" in history and history.count("coder-1 started") == 2


def test_the_coder_is_told_the_behaviour_tests_are_read_only(project: Project) -> None:
    keeps = "pathlib.Path('seen.txt').write_text(prompt)\nprint('RESULT: done')"
    project.configure(coder=keeps, tester=TESTER)
    project.dk("add", "Greet", "--spec", "Say hello.")
    project.dk("run")
    project.dk("approve", "1")

    project.dk("run")

    seen = project.merged("seen.txt") or ""
    assert "features/greet.feature" in seen and "read-only" in seen
    assert len(seen.split()) < 200


def test_a_coder_may_add_scenarios_of_its_own(project: Project) -> None:
    coder = "pathlib.Path('features/extra.feature').write_text('Feature: Extra\\n')\n" + HELLO
    project.configure(coder=coder, tester=TESTER)
    project.dk("add", "Greet", "--spec", "Say hello.")
    project.dk("run")
    project.dk("approve", "1")

    project.dk("run")

    assert project.merged("features/extra.feature") == "Feature: Extra\n"
    assert project.dk("show", "1").count("coder-1 started") == 1


def test_a_tester_that_writes_no_behaviour_tests_has_not_done_its_job(project: Project) -> None:
    project.configure(
        coder=HELLO,
        tester="pathlib.Path('notes.txt').write_text('x')\nprint('RESULT: done')",
        max_attempts=1,
    )
    project.dk("add", "Greet", "--spec", "Say hello.")

    project.dk("run")

    status = project.dk("status")
    assert "#1 stopped at specify" in status and "wrote no behaviour tests" in status


def test_the_verifier_checks_that_behaviour_tests_really_exercise_the_product(
    project: Project,
) -> None:
    keeps = (
        "pathlib.Path(sys.argv[0]).with_name('seen.txt').write_text(prompt)\n"
        "print('RESULT: approved')"
    )
    project.configure(coder=HELLO, tester=TESTER, verifier=keeps)
    project.dk("add", "Greet", "--spec", "Say hello.")
    project.dk("run")
    project.dk("approve", "1")

    project.dk("run")

    seen = (project.root.parent / "tools" / "seen.txt").read_text()
    assert "really exercises the product" in seen


def test_only_a_ticket_waiting_for_the_user_can_be_approved_or_rejected(project: Project) -> None:
    project.configure(coder="print('RESULT: question: which?')")
    project.dk("add", "Greet", "--spec", "Say hello.")
    project.dk("run")

    assert "#1 is not waiting for your approval" in project.refused("approve", "1")
    assert "#1 is not waiting for your approval" in project.refused("reject", "1", "--note", "no")
