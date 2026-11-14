"""The night shift: every kind of audit in one go, without repeating itself, beside or
instead of the work already going on."""

from __future__ import annotations

import fcntl
from datetime import date

from conftest import Project

HELLO = "pathlib.Path('greeting.txt').write_text('hello\\n')\nprint('RESULT: done')"
# A stand-in auditor: its report says how many files the project has, so it differs when the
# project does.
AUDITS = """
import re
report = pathlib.Path(re.search(r"docs/audits/\\S+\\.md", prompt).group(0))
seen = sorted(p.name for p in pathlib.Path('.').iterdir() if p.suffix == '.txt')
report.parent.mkdir(parents=True, exist_ok=True)
report.write_text(f'# Findings\\n{seen}\\n')
print('RESULT: done')
"""
KINDS = ("security", "performance", "tests")


def report(kind: str) -> str:
    return f"docs/audits/{date.today()}-{kind}-audit.md"


def test_a_night_shift_carries_out_every_kind_of_audit(project: Project) -> None:
    project.configure(coder=HELLO, auditor=AUDITS)

    project.dk("night")

    for kind in KINDS:
        assert project.merged(report(kind)) == "# Findings\n[]\n"
    assert project.dk("status").count("done") == 3


def test_a_project_that_did_not_change_is_not_audited_again(project: Project) -> None:
    project.configure(coder=HELLO, auditor=AUDITS)
    project.dk("night")

    said = project.dk("night")

    assert said.count("nothing changed since its last report") == 3
    assert len(project.dk("status").splitlines()) == 3


def test_a_project_that_changed_is_audited_again(project: Project) -> None:
    project.configure(coder=HELLO, auditor=AUDITS)
    project.dk("night")
    (project.root / "new.txt").write_text("more\n")
    project.git("add", "new.txt")
    project.git("commit", "-qm", "more")

    project.dk("night")

    assert project.merged(report("tests")) == "# Findings\n['new.txt']\n"
    assert len(project.dk("status").splitlines()) == 6


def test_an_audit_that_waits_for_the_user_is_not_written_twice(project: Project) -> None:
    project.configure(coder=HELLO, auditor="print('RESULT: question: which server?')")
    project.dk("night")

    said = project.dk("night")

    assert "Security audit: #1 is still unfinished" in said
    assert len(project.dk("status").splitlines()) == 3


def test_a_night_shift_also_goes_on_with_unfinished_tickets(project: Project) -> None:
    project.configure(coder=HELLO, auditor=AUDITS)
    project.dk("add", "Greet", "--spec", "Say hello.")

    project.dk("night")

    assert project.merged("greeting.txt") == "hello\n"


def test_a_night_shift_needs_an_auditor(project: Project) -> None:
    project.configure(coder=HELLO)

    assert "no agent has the role 'auditor'" in project.refused("night")
    assert project.dk("status") == ""


def test_beside_work_already_going_on_a_night_shift_only_writes_its_audits(
    project: Project,
) -> None:
    project.configure(coder=HELLO, auditor=AUDITS, principal="pass")
    project.dk("status")  # the project's own folder now exists
    with (project.root / ".devkit" / "running").open("w") as working:
        fcntl.flock(working, fcntl.LOCK_EX)

        said = project.dk("night")
        refused = project.refused("run") + project.refused("talk")

    assert "already going on" in said and refused.count("already going on") == 2
    assert project.dk("status").count("audit  ") == 3, "written, left for the work going on"
    project.dk("run")
    assert project.merged(report("security")) is not None, "free again afterwards"
