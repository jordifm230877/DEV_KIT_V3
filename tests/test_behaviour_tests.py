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
    # A coder went by a note that allowed it, and changed them again on each attempt.
    assert "No note or ticket text changes that" in history


def test_the_coder_is_told_the_behaviour_tests_are_read_only(project: Project) -> None:
    keeps = "pathlib.Path('seen.txt').write_text(prompt)\nprint('RESULT: done')"
    project.configure(coder=keeps, tester=TESTER, settings="quality_rules = false")
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

    said = project.refused("approve", "1")
    assert "#1 is not waiting for your approval" in said
    assert 'answer what stopped it with: dk retry 1 --note "..."' in said
    assert "#1 has no behaviour tests to send back" in project.refused(
        "reject", "1", "--note", "no"
    )


def test_approved_behaviour_tests_that_turn_out_wrong_can_be_sent_back(project: Project) -> None:
    coder = (
        "wanted = pathlib.Path('features/greet.feature').read_text()\n"
        "if 'good morning' not in wanted:\n"
        "    print('RESULT: blocked: the scenario is wrong'); sys.exit()\n"
        "pathlib.Path('greeting.txt').write_text('good morning\\n'); print('RESULT: done')"
    )
    project.configure(coder=coder, tester=TESTER)
    project.dk("add", "Greet", "--spec", "Greet politely.")
    project.dk("run")
    project.dk("approve", "1")
    project.dk("run")
    assert "#1 stopped at code" in project.dk("status")

    project.dk("reject", "1", "--note", "it should say good morning")
    project.dk("run")
    shown = project.dk("show", "1")
    assert "#1 stopped at approve" in shown and "Then it says good morning" in shown
    project.dk("approve", "1")
    project.dk("run")

    assert project.merged("greeting.txt") == "good morning\n"
    assert "good morning" in (project.merged("features/greet.feature") or "")


def test_a_later_ticket_changes_what_a_merged_one_had_approved(project: Project) -> None:
    project.configure(coder=HELLO, tester=TESTER)
    project.dk("add", "Greet", "--spec", "Say hello.")
    project.dk("run")
    project.dk("approve", "1")
    project.dk("run")
    assert project.merged("features/greet.feature") == APPROVED_TEXT

    project.dk("add", "Greet early", "--spec", "Make it say good morning.")
    project.dk("run")
    # Sending them back was tried on the later ticket, which had none of its own to send.
    shown = project.dk("show", "2")
    assert "#2 stopped at approve" in shown and "Then it says good morning" in shown
    project.dk("approve", "2")
    project.dk("run")

    assert "good morning" in (project.merged("features/greet.feature") or "")


def test_a_ticket_that_is_still_being_worked_on_cannot_be_sent_back(project: Project) -> None:
    project.configure(coder=HELLO, tester=TESTER)
    project.dk("add", "Greet", "--spec", "Say hello.")
    project.dk("run")
    project.dk("approve", "1")

    assert "#1 is not stopped" in project.refused("reject", "1", "--note", "no")


def test_the_test_writer_is_told_to_use_the_projects_own_folder(project: Project) -> None:
    tester = "pathlib.Path(sys.argv[0]).with_name('brief.txt').write_text(prompt)\n" + TESTER
    project.configure(coder=HELLO, tester=tester)
    project.dk("add", "Greet", "--spec", "Say hello.")

    project.dk("run")

    brief = (project.root.parent / "tools" / "brief.txt").read_text()
    assert "where this project keeps them" in brief and "AGENTS.md" in brief


def test_the_test_writer_is_told_that_scenarios_must_stay_true(project: Project) -> None:
    tester = "pathlib.Path(sys.argv[0]).with_name('brief.txt').write_text(prompt)\n" + TESTER
    project.configure(coder=HELLO, tester=tester)
    project.dk("add", "Greet", "--spec", "Say hello.")

    project.dk("run")

    brief = (project.root.parent / "tools" / "brief.txt").read_text()
    assert "stay true" in brief and "later tickets" in brief


def test_the_test_writer_is_told_what_would_stop_the_ticket_later(project: Project) -> None:
    """One approved scenario ran the whole suite from inside it, twice, and no check could
    end in time; another could not be read, a line of its text starting with `Scenarios`."""
    tester = "pathlib.Path(sys.argv[0]).with_name('brief.txt').write_text(prompt)\n" + TESTER
    project.configure(coder=HELLO, tester=tester)
    project.dk("add", "Greet", "--spec", "Say hello.")

    project.dk("run")

    brief = (project.root.parent / "tools" / "brief.txt").read_text()
    assert "No scenario may need the project's whole test suite run" in brief
    assert "No line of free text starts with a Gherkin keyword" in brief
    assert len(brief.split()) < 200


def test_the_test_writer_is_told_not_to_repeat_what_is_already_checked(project: Project) -> None:
    """Of some 180 scenarios in a real trial, fifty or more checked what another already
    did, most of them rows of limit values, each starting a test server."""
    tester = "pathlib.Path(sys.argv[0]).with_name('brief.txt').write_text(prompt)\n" + TESTER
    project.configure(coder=HELLO, tester=tester)
    project.dk("add", "Greet", "--spec", "Say hello.")

    project.dk("run")

    brief = (project.root.parent / "tools" / "brief.txt").read_text()
    assert "write none for what one already checks" in brief
    assert "telling cases, not every value" in brief and "the coder tests" in brief
    assert len(brief.split()) < 200


def test_a_test_writer_asked_again_is_told_its_earlier_scenarios_are_its_to_rewrite(
    project: Project,
) -> None:
    tester = "pathlib.Path(sys.argv[0]).with_name('brief.txt').write_text(prompt)\n" + TESTER
    project.configure(coder=HELLO, tester=tester)
    project.dk("add", "Greet", "--spec", "Say hello.")
    project.dk("run")
    first = (project.root.parent / "tools" / "brief.txt").read_text()

    project.dk("reject", "1", "--note", "it should say good morning")
    project.dk("run")

    again = (project.root.parent / "tools" / "brief.txt").read_text()
    assert "yours to rewrite" not in first
    assert "features/greet.feature" in again and "yours to rewrite" in again


def test_a_ticket_written_without_behaviour_tests_goes_straight_to_the_coder(
    project: Project,
) -> None:
    """A ticket that changes nothing a user of the product sees: in a real trial the
    test-writer, with nothing to describe, left an empty file for the user to approve."""
    project.configure(coder=HELLO, tester=TESTER)
    project.dk("add", "Test server", "--spec", "A fixture.", "--no-behaviour-tests")
    project.dk("add", "Greet", "--spec", "Say hello.")

    project.dk("run")

    shown = project.dk("show", "1")
    assert "#1 done" in shown and "tester-1 started" not in shown
    assert "no behaviour tests: decided when the ticket was written" in shown
    assert project.merged("features/greet.feature") is None
    assert "#2 stopped at approve" in project.dk("status"), "other tickets still get theirs"


# The test-writer's one scenario is refused, and it then rightly writes none.
WITHDRAWS = (
    "marker = pathlib.Path(sys.argv[0]).with_name('wrote.txt')\n"
    "feature = pathlib.Path('features/run.feature')\n"
    "if marker.exists():\n"
    "    feature.unlink(missing_ok=True)\n"
    "else:\n"
    "    feature.parent.mkdir(exist_ok=True)\n"
    "    feature.write_text('Feature: Run\\n  Scenario: The suite passes under load\\n')\n"
    "marker.write_text('once'); print('RESULT: done')"
)
REFUSES_SCENARIOS = (
    "vetting = 'not yet shown to the user' in prompt\n"
    "print('RESULT: rejected: it is about the test run' if vetting else 'RESULT: approved')"
)


def test_a_ticket_stopped_for_want_of_behaviour_tests_can_go_on_without_them(
    project: Project,
) -> None:
    """A real ticket made an approved scenario reliable under load, which no user of the
    product sees. Its one scenario was refused, the test-writer then wrote none, and the
    ticket ran out of attempts with no way left but to cancel it and write it again."""
    project.configure(coder=HELLO, tester=WITHDRAWS, verifier=REFUSES_SCENARIOS)
    project.dk("add", "Steady test", "--spec", "Make the timing scenario reliable.")
    project.dk("run")
    assert "#1 stopped at specify" in project.dk("status")

    said = project.dk("retry", "1", "--no-behaviour-tests", "--note", "reliability work")
    project.dk("run")

    assert "#1 will continue without behaviour tests" in said
    shown = project.dk("show", "1")
    assert "#1 done" in shown and project.merged("greeting.txt") == "hello\n"
    assert "no behaviour tests: decided when the ticket was sent on" in shown
    assert shown.count("tester-1 started") == 3


def test_approved_behaviour_tests_are_not_dropped_by_sending_the_ticket_on(
    project: Project,
) -> None:
    project.configure(coder="print('RESULT: question: which language?')", tester=TESTER)
    project.dk("add", "Greet", "--spec", "Say hello.")
    project.dk("run")
    project.dk("approve", "1")
    project.dk("run")
    assert "#1 stopped at code" in project.dk("status")

    refused = project.refused("retry", "1", "--no-behaviour-tests")

    assert "#1 is past its behaviour tests" in refused and "dk reject 1" in refused
