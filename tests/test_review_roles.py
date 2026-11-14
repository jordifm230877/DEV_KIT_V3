"""The verifier judges how the work is done; QA judges whether it works for a user."""

from __future__ import annotations

from conftest import Project

HELLO = "pathlib.Path('greeting.txt').write_text('hello\\n')\nprint('RESULT: done')"
KEEPS = (
    "pathlib.Path(sys.argv[0]).with_suffix('.seen').write_text(prompt)\nprint('RESULT: approved')"
)
TESTER = (
    "pathlib.Path('features').mkdir(exist_ok=True)\n"
    "pathlib.Path('features/greet.feature').write_text('Feature: Greeting\\n')\n"
    "print('RESULT: done')"
)
QUALITY = ("has no test", "crapper", "dryer")


def told(project: Project, role: str) -> str:
    return (project.root.parent / "tools" / f"{role}.seen").read_text()


def test_qa_goes_through_the_acceptance_criteria_one_by_one(project: Project) -> None:
    project.configure(coder=HELLO, qa=KEEPS)
    project.dk("add", "Greet", "--spec", "Say hello.")

    project.dk("run")

    brief = told(project, "qa")
    assert "acceptance criteria" in brief and "one by one" in brief
    assert "say which" in brief
    assert ".feature" not in brief, "there are no behaviour tests in this project"
    assert len(brief.split()) < 200


def test_qa_also_checks_the_approved_behaviour_tests_against_the_product(
    project: Project,
) -> None:
    project.configure(coder=HELLO, tester=TESTER, qa=KEEPS)
    project.dk("add", "Greet", "--spec", "Say hello.")
    project.dk("run")
    project.dk("approve", "1")

    project.dk("run")

    brief = told(project, "qa")
    assert "approved behaviour tests" in brief and ".feature" in brief


def test_the_verifier_judges_how_the_work_is_done(project: Project) -> None:
    project.configure(coder=HELLO, verifier=KEEPS, qa=KEEPS)
    project.dk("add", "Greet", "--spec", "Say hello.")

    project.dk("run")

    brief = told(project, "verifier")
    for part in ("how the work is done", "cheats", "did not ask for", "carelessly"):
        assert part in brief
    for rule in QUALITY:
        assert rule in brief
    assert all(rule not in told(project, "qa") for rule in QUALITY)
    assert len(brief.split()) < 200


def test_without_the_quality_rules_the_verifier_does_not_ask_for_them(project: Project) -> None:
    project.configure(coder=HELLO, verifier=KEEPS, settings="quality_rules = false")
    project.dk("add", "Greet", "--spec", "Say hello.")

    project.dk("run")

    brief = told(project, "verifier")
    assert "cheats" in brief and all(rule not in brief for rule in QUALITY)
