"""The user can ask for an audit of the whole project: an agent looks and measures, changes
nothing, and leaves a report for the user to decide on."""

from __future__ import annotations

from datetime import date

from conftest import Project

HELLO = "pathlib.Path('greeting.txt').write_text('hello\\n')\nprint('RESULT: done')"
# A stand-in auditor: it writes its report where the brief says, and meddles with the product.
AUDITS = """
import re
report = pathlib.Path(re.search(r"docs/audits/\\S+\\.md", prompt).group(0))
pathlib.Path('brief.txt').write_text(prompt)
report.parent.mkdir(parents=True, exist_ok=True)
report.write_text('# Findings\\n- high: the password is logged\\n')
pathlib.Path('README.md').write_text('meddled\\n')
pathlib.Path('scratch.bin').write_text('left behind\\n')
print('RESULT: done')
"""


def report(kind: str) -> str:
    return f"docs/audits/{date.today()}-{kind}-audit.md"


def test_an_audit_leaves_a_report_in_the_project_and_nothing_else(project: Project) -> None:
    project.configure(coder=HELLO, auditor=AUDITS)

    said = project.dk("audit", "security")
    project.dk("run")

    assert "#1" in said and report("security") in said
    assert project.merged(report("security")) == "# Findings\n- high: the password is logged\n"
    assert project.merged("README.md") == "demo\n", "an auditor fixes nothing"
    assert project.merged("scratch.bin") is None and project.merged("brief.txt") is None
    assert "#1 done  Security audit" in project.dk("status")
    assert project.git("status", "--porcelain") == "", "the report is saved in Git"


def brief(project: Project, *audit: str) -> str:
    seen = "pathlib.Path(sys.argv[0]).with_name('brief.txt').write_text(prompt)\n"
    project.configure(coder=HELLO, auditor=seen + AUDITS)
    project.dk("audit", *audit)
    project.dk("run")
    return (project.root.parent / "tools" / "brief.txt").read_text()


def test_a_security_auditor_is_told_what_to_look_for_and_to_fix_nothing(project: Project) -> None:
    told = brief(project, "security", "--note", "Look hard at the session code.")

    for part in ("secrets", "dependencies", "container images", "Look hard at the session code."):
        assert part in told
    for rule in ("Do not fix", "what you observed", "could not check", "severity"):
        assert rule in told
    assert "in the background" in told, "its own tool cuts off a command that runs long"
    assert "RESULT: done" in told and len(told.split()) < 300


def test_a_performance_auditor_is_told_to_measure(project: Project) -> None:
    told = brief(project, "performance")

    assert "Measure" in told and "slow" in told
    assert "secrets" not in told
    assert report("performance") in told


def test_an_audit_needs_an_auditor(project: Project) -> None:
    project.configure(coder=HELLO)

    assert "no agent has the role 'auditor'" in project.refused("audit", "security")
    assert project.dk("status") == ""


def test_an_auditor_that_writes_no_report_has_not_done_the_audit(project: Project) -> None:
    project.configure(coder=HELLO, auditor="print('RESULT: done')", max_attempts=1)
    project.dk("audit", "security")

    project.dk("run")

    status = project.dk("status")
    assert "#1 stopped at audit" in status and "wrote no report" in status


def test_an_auditor_can_ask_the_user_as_any_agent_can(project: Project) -> None:
    project.configure(coder=HELLO, auditor="print('RESULT: question: which server may I load?')")
    project.dk("audit", "performance")

    project.dk("run")

    status = project.dk("status")
    assert "#1 stopped at audit" in status and "which server may I load?" in status


def test_tickets_go_on_as_before_beside_an_audit(project: Project) -> None:
    project.configure(coder=HELLO, auditor=AUDITS)
    project.dk("add", "Greet", "--spec", "Say hello.")
    project.dk("audit", "security")

    project.dk("run")

    assert project.merged("greeting.txt") == "hello\n"
    assert project.merged(report("security")) is not None


TOOLS = '[audit]\ntools = ["cargo-audit", "gitleaks"]\n'


def test_an_auditor_is_told_which_tools_the_project_expects(project: Project) -> None:
    seen = "pathlib.Path(sys.argv[0]).with_name('brief.txt').write_text(prompt)\n"
    project.configure(coder=HELLO, auditor=seen + AUDITS, settings=TOOLS)
    project.dk("audit", "security")

    project.dk("run")

    told = (project.root.parent / "tools" / "brief.txt").read_text()
    assert "cargo-audit, gitleaks" in told and len(told.split()) < 300


def test_an_auditor_recommends_the_tools_this_project_should_have(project: Project) -> None:
    told = brief(project, "security")

    assert "recommend" in told and "on the web" in told and "how to install" in told
    assert "[audit]" in told, "where the user would list them"
    assert "expects" not in told, "no tools were listed for this project"


def test_an_audit_of_the_tests_breaks_the_code_to_see_whether_they_notice(project: Project) -> None:
    told = brief(project, "tests")

    assert "Break the code on purpose" in told and "no test notices" in told
    for case in ("malformed input", "limits", "fails halfway", "cancelled", "times out"):
        assert case in told, "what no ticket asks anyone to try"
    assert "Name each such case that has no test" in told
    assert "secrets" not in told and report("tests") in told
    assert len(told.split()) < 300


def test_an_auditor_proposes_tickets_for_what_matters_most(project: Project) -> None:
    told = brief(project, "security")

    assert f"--project {project.root} propose" in told
    assert "five at most" in told and "the user decides" in told


def test_an_auditor_is_told_what_is_already_asked_for_or_was_turned_down(project: Project) -> None:
    seen = "pathlib.Path(sys.argv[0]).with_name('brief.txt').write_text(prompt)\n"
    project.configure(coder=HELLO, auditor=seen + AUDITS)
    project.dk("add", "Greet", "--spec", "Say hello.")
    project.dk("run")
    project.dk("propose", "Rotate the key", "--spec", "a")
    project.dk("propose", "Hide the log", "--spec", "b")
    project.dk("reject", "3", "--note", "no")
    project.dk("audit", "security")

    project.dk("run")

    told = (project.root.parent / "tools" / "brief.txt").read_text()
    assert "Rotate the key; Hide the log" in told
    assert "Greet" not in told, "what is merged can be found wanting again"
    assert "Security audit;" not in told and "; Security audit" not in told
