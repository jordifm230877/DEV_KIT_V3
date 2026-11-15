"""A coder is told how to work well, unless the project turns that off."""

from __future__ import annotations

from conftest import Project

KEEPS = (
    "pathlib.Path(sys.argv[0]).with_name('brief.txt').write_text(prompt)\n"
    "pathlib.Path('greeting.txt').write_text('hello\\n')\nprint('RESULT: done')"
)
RULES = ("failing test first", "crapper", "dryer", "mutator")


def brief(project: Project) -> str:
    return (project.root.parent / "tools" / "brief.txt").read_text()


def test_a_coder_is_told_the_quality_rules(project: Project) -> None:
    project.configure(coder=KEEPS)
    project.dk("add", "Greet", "--spec", "Say hello.")

    project.dk("run")

    told = brief(project)
    for rule in RULES:
        assert rule in told
    assert "only the tests of what you change" in told
    assert len(told.split()) < 200


def test_a_project_can_turn_the_quality_rules_off(project: Project) -> None:
    project.configure(coder=KEEPS, settings="quality_rules = false")
    project.dk("add", "Greet", "--spec", "Say hello.")

    project.dk("run")

    told = brief(project)
    for rule in RULES:
        assert rule not in told


def test_the_quality_rules_are_for_whoever_writes_code(project: Project) -> None:
    tester = (
        "pathlib.Path(sys.argv[0]).with_name('brief.txt').write_text(prompt)\n"
        "print('RESULT: question: what?')"
    )
    project.configure(coder="print('RESULT: done')", tester=tester)
    project.dk("add", "Greet", "--spec", "Say hello.")

    project.dk("run")

    told = brief(project)
    for rule in RULES:
        assert rule not in told
