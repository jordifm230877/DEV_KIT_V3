"""Behaviour tests are looked over by a reviewer before the user is asked to approve them."""

from __future__ import annotations

from conftest import Project

HELLO = "pathlib.Path('greeting.txt').write_text('hello\\n')\nprint('RESULT: done')"
# The test-writer drops its second scenario once it is told that it is about the process.
TESTER = (
    "second = '' if 'about the process' in prompt else '  Scenario: The checks pass\\n'\n"
    "pathlib.Path('features').mkdir(exist_ok=True)\n"
    "pathlib.Path('features/greet.feature').write_text("
    "'Feature: Greeting\\n  Scenario: Polite\\n' + second)\n"
    "print('RESULT: done')"
)
# The verifier keeps what it was asked beside itself, and refuses a scenario about checks.
VERIFIER = (
    "asked = pathlib.Path(sys.argv[0]).with_name('asked.txt')\n"
    "asked.write_text((asked.read_text() if asked.exists() else '') + prompt + '\\n=====\\n')\n"
    "vetting = 'not yet shown to the user' in prompt\n"
    "bad = vetting and 'The checks pass' in pathlib.Path('features/greet.feature').read_text()\n"
    "print('RESULT: rejected: the second scenario is about the process' if bad"
    " else 'RESULT: approved')"
)


def asked(project: Project) -> list[str]:
    return (project.root.parent / "tools" / "asked.txt").read_text().split("\n=====\n")[:-1]


def test_scenarios_a_reviewer_refuses_are_rewritten_before_the_user_sees_them(
    project: Project,
) -> None:
    project.configure(coder=HELLO, tester=TESTER, verifier=VERIFIER)
    project.dk("add", "Greet", "--spec", "Say hello.")

    said = project.dk("run")

    shown = project.dk("show", "1")
    assert "#1 stopped at approve" in shown and "The checks pass" not in shown.split("---")[-1]
    assert "verifier-1 rejected the behaviour tests: the second scenario is about" in shown
    assert said.index("#1 vet failed") < said.index("#1 vet passed") < said.index("#1 approve")


def test_the_reviewer_is_told_what_makes_a_scenario_good(project: Project) -> None:
    project.configure(coder=HELLO, tester=TESTER, verifier=VERIFIER)
    project.dk("add", "Greet", "--spec", "Say hello.")

    project.dk("run")

    brief = asked(project)[0]
    assert "features/greet.feature" in brief and "Say hello." in brief
    for rule in ("a user of the product", "stay true", "the ticket asks for"):
        assert rule in brief


def test_the_reviewer_refuses_scenarios_that_would_stop_the_ticket_later(
    project: Project,
) -> None:
    project.configure(coder=HELLO, tester=TESTER, verifier=VERIFIER)
    project.dk("add", "Greet", "--spec", "Say hello.")

    project.dk("run")

    brief = asked(project)[0]
    assert "without running the project's whole test suite" in brief
    assert "valid Gherkin" in brief and "starts with a keyword" in brief
    assert len(brief.split()) < 200


def test_the_reviewer_refuses_scenarios_that_repeat_what_is_already_checked(
    project: Project,
) -> None:
    project.configure(coder=HELLO, tester=TESTER, verifier=VERIFIER)
    project.dk("add", "Greet", "--spec", "Say hello.")

    project.dk("run")

    brief = asked(project)[0]
    assert "checks nothing an existing scenario already checks" in brief
    assert "telling cases, not every value" in brief
    assert len(brief.split()) < 200


def test_without_behaviour_tests_there_is_nothing_to_look_over(project: Project) -> None:
    project.configure(coder=HELLO, verifier=VERIFIER)
    project.dk("add", "Greet", "--spec", "Say hello.")

    project.dk("run")

    assert len(asked(project)) == 1 and "not yet shown" not in asked(project)[0]
    assert "#1 done" in project.dk("status")
