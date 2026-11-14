"""`dk check` finds, before any ticket, what would otherwise stop the first one."""

from __future__ import annotations

from conftest import Project

ANSWERS = "print('RESULT: done')"
COUNTS = (
    "asked = pathlib.Path(sys.argv[0]).with_name('asked.txt')\n"
    "asked.write_text(asked.read_text() + 'x' if asked.exists() else 'x')\n" + ANSWERS
)


def test_a_project_that_is_ready_says_so(project: Project) -> None:
    project.configure(coder=ANSWERS, verifier="print('RESULT: approved')")

    said = project.dk("check")

    for line in ("ok       coder-1", "ok       verifier-1", "ok       check 'unit'", "committed"):
        assert line in said
    assert "PROBLEM" not in said


def test_an_agent_that_cannot_be_reached_is_named_with_what_it_said(project: Project) -> None:
    project.configure(coder="print('error: 400: model not available in your region')")

    said = project.refused("check")

    assert "PROBLEM  coder-1" in said and "model not available in your region" in said
    assert "1 thing to fix" in said


def test_a_check_that_fails_before_any_work_is_reported(project: Project) -> None:
    project.configure(coder=ANSWERS, check="print('3 tests broken'); sys.exit(1)")

    said = project.refused("check")

    assert "PROBLEM  check 'unit'" in said and "3 tests broken" in said


def test_programs_that_are_not_installed_are_named(project: Project) -> None:
    (project.root / "devkit.toml").write_text(
        '[[agents]]\nname = "coder-1"\nrole = "coder"\ncommand = ["no-such-agent"]\n'
        '[checks]\nunit = ["no-such-tester", "-q"]\n'
    )
    project.git("add", "devkit.toml")
    project.git("commit", "-qm", "configure")

    said = project.refused("check")

    assert "PROBLEM  coder-1: no-such-agent is not installed" in said
    assert "PROBLEM  check 'unit': no-such-tester is not installed" in said
    assert "2 things to fix" in said


def test_files_the_agents_would_not_see_are_listed(project: Project) -> None:
    project.configure(coder=ANSWERS)
    (project.root / "AGENTS.md").write_text("rules\n")

    said = project.refused("check")

    assert "PROBLEM  not committed, so agents will not see them: AGENTS.md" in said


def test_a_project_with_no_checks_or_no_coder_is_not_ready(project: Project) -> None:
    (project.root / "devkit.toml").write_text("max_attempts = 3\n")
    project.git("add", "devkit.toml")
    project.git("commit", "-qm", "configure")

    said = project.refused("check")

    assert "PROBLEM  no agent has the role 'coder'" in said
    assert "PROBLEM  no checks" in said


def test_agents_that_share_a_model_are_asked_once(project: Project) -> None:
    project.configure(coder=COUNTS, coders=3)

    said = project.dk("check")

    assert (project.root.parent / "tools" / "asked.txt").read_text() == "x"
    assert said.count("ok       coder-") == 3


def test_checking_leaves_the_project_as_it_was(project: Project) -> None:
    project.configure(coder="pathlib.Path('stray.txt').write_text('x')\n" + ANSWERS)

    project.dk("check")

    assert project.git("status", "--porcelain") == ""


def test_audit_tools_the_project_lists_but_are_not_installed_are_named(project: Project) -> None:
    project.configure(coder=ANSWERS, settings='[audit]\ntools = ["git", "no-such-scanner"]\n')

    said = project.refused("check")

    assert "ok       audit tool 'git'" in said
    assert "PROBLEM  audit tool 'no-such-scanner' is not installed" in said
    assert "1 thing to fix" in said
