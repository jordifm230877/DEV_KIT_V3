"""The verifier judges how the work is done and whether it works for a user."""

from __future__ import annotations

from conftest import Project

HELLO = "pathlib.Path('greeting.txt').write_text('hello\\n')\nprint('RESULT: done')"
KEEPS = (
    "pathlib.Path(sys.argv[0]).with_suffix('.seen').write_text(prompt)\nprint('RESULT: approved')"
)
QUALITY = ("has no test", "crapper --no-coverage", "dryer --threshold 0.8", "never read their code")


def told(project: Project, role: str) -> str:
    return (project.root.parent / "tools" / f"{role}.seen").read_text()


def test_the_verifier_judges_how_the_work_is_done_and_whether_it_works(
    project: Project,
) -> None:
    project.configure(coder=HELLO, verifier=KEEPS)
    project.dk("add", "Greet", "--spec", "Say hello.")

    project.dk("run")

    brief = told(project, "verifier")
    for part in ("how the work is done", "cheats", "did not ask for", "carelessly"):
        assert part in brief
    assert "acceptance criteria" in brief and "one by one: each must work" in brief
    for rule in QUALITY:
        assert rule in brief
    # coder, verifier and QA each ran a suite of 15 minutes the program had just run
    assert "checks have passed on this code" in brief and "never run its whole test suite" in brief
    assert ".feature" not in brief, "there are no behaviour tests in this project"
    # A real one named a fault or two each time: four rejections, an hour of coding after each.
    assert "names all that must change" in brief and "not the first fault found" in brief
    assert len(brief.split()) < 300


def test_without_the_quality_rules_the_verifier_does_not_ask_for_them(project: Project) -> None:
    project.configure(coder=HELLO, verifier=KEEPS, settings="quality_rules = false")
    project.dk("add", "Greet", "--spec", "Say hello.")

    project.dk("run")

    brief = told(project, "verifier")
    assert "cheats" in brief and all(rule not in brief for rule in QUALITY)
