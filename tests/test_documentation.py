"""The user can have the project's documentation brought up to date with its code: an agent
reads and tries the product, and only what it writes in the documentation folders is kept."""

from __future__ import annotations

import time

import pytest
from conftest import Project

HELLO = "pathlib.Path('greeting.txt').write_text('hello\\n')\nprint('RESULT: done')"
# A stand-in documenter: it writes in both folders, and meddles with the product.
DOCUMENTS = """
pathlib.Path(sys.argv[0]).with_name('brief.txt').write_text(prompt)
written = (('docs/technical/parts.md', '# Parts\\n'), ('docs/howto/greet.md', '# Greet\\n'))
for name, text in written:
    pathlib.Path(name).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(name).write_text(text)
pathlib.Path('README.md').write_text('meddled\\n')
pathlib.Path('docs/decisions.md').write_text('meddled\\n')
pathlib.Path('scratch.bin').write_text('left behind\\n')
print('RESULT: done')
"""


def test_documentation_is_written_in_its_folders_and_nothing_else_is_kept(
    project: Project,
) -> None:
    project.configure(coder=HELLO, documenter=DOCUMENTS)

    said = project.dk("document")
    project.dk("run")

    assert "#1 written" in said
    assert project.merged("docs/technical/parts.md") == "# Parts\n"
    assert project.merged("docs/howto/greet.md") == "# Greet\n"
    assert project.merged("README.md") == "demo\n", "a documenter changes no product file"
    assert project.merged("docs/decisions.md") is None, "decisions are the Principal's"
    assert project.merged("scratch.bin") is None
    assert "#1 done  Documentation" in project.dk("status")
    assert "found the documentation up to date" not in project.dk("show", "1")
    assert project.git("status", "--porcelain") == "", "the documentation is saved in Git"


def test_a_documenter_is_told_what_to_write_and_to_try_what_it_describes(
    project: Project,
) -> None:
    project.configure(coder=HELLO, documenter=DOCUMENTS)
    project.dk("document", "--note", "Start with the sign-in guide.")

    project.dk("run")

    told = (project.root.parent / "tools" / "brief.txt").read_text()
    for part in ("docs/technical/", "docs/howto/", "Start with the sign-in guide."):
        assert part in told
    for rule in ("what the code does now", "*.feature", "Carry out each step", "git log"):
        assert rule in told
    assert "headings" in told and "tables" in told, "what the page of `dk web` can show"
    assert "in the background" in told
    assert "RESULT: done" in told and len(told.split()) < 300


def test_documentation_that_needs_no_change_is_not_a_failure(project: Project) -> None:
    project.configure(coder=HELLO, documenter="print('RESULT: done')", max_attempts=1)
    project.dk("document")

    project.dk("run")

    shown = project.dk("show", "1")
    assert "#1 done" in shown and "documenter-1 found the documentation up to date" in shown


def test_a_documenter_removes_the_guide_of_what_is_gone(project: Project) -> None:
    (project.root / "docs" / "howto").mkdir(parents=True)
    (project.root / "docs" / "howto" / "old.md").write_text("# Old\n")
    project.git("add", "docs")
    project.git("commit", "-qm", "an old guide")
    project.configure(
        coder=HELLO, documenter="pathlib.Path('docs/howto/old.md').unlink()\nprint('RESULT: done')"
    )
    project.dk("document")

    project.dk("run")

    assert project.merged("docs/howto/old.md") is None and "#1 done" in project.dk("status")


def test_documentation_needs_a_documenter(project: Project) -> None:
    project.configure(coder=HELLO)

    assert "no agent has the role 'documenter'" in project.refused("document")
    assert project.dk("status") == ""


def test_one_documentation_run_at_a_time(project: Project) -> None:
    """Two writers of the same files would collide when the second is merged."""
    project.configure(coder=HELLO, documenter=DOCUMENTS)
    project.dk("document")

    assert "#1 is still unfinished" in project.refused("document")


def test_a_ticket_of_the_same_name_is_not_a_documentation_run(project: Project) -> None:
    project.configure(coder=HELLO, documenter=DOCUMENTS)
    project.dk("add", "Documentation", "--spec", "Fix a typo in the README.")

    assert "#2 written" in project.dk("document")


def test_a_documenter_can_ask_the_user_as_any_agent_can(project: Project) -> None:
    project.configure(coder=HELLO, documenter="print('RESULT: question: who reads the guides?')")
    project.dk("document")

    project.dk("run")

    status = project.dk("status")
    assert "#1 stopped at document" in status and "who reads the guides?" in status


def test_tickets_go_on_as_before_beside_documentation(project: Project) -> None:
    project.configure(coder=HELLO, documenter=DOCUMENTS)
    project.dk("add", "Greet", "--spec", "Say hello.")
    project.dk("document")

    project.dk("run")

    assert project.merged("greeting.txt") == "hello\n"
    assert project.merged("docs/howto/greet.md") == "# Greet\n"


def _finished_epic(project: Project, **agents: str) -> None:
    project.configure(coder=HELLO, **agents)
    project.dk("add", "Greet", "--spec", "Say hello.", "--epic", "Greetings")
    project.dk("run")


def test_closing_an_epic_asks_for_its_documentation(project: Project) -> None:
    _finished_epic(project, documenter=DOCUMENTS)

    said = project.dk("close", "Greetings")

    assert "Greetings closed" in said and "#2 written" in said
    assert "#2 document  Documentation" in project.dk("status")


def test_closing_an_epic_asks_for_nothing_where_nobody_documents(project: Project) -> None:
    _finished_epic(project)

    assert "written" not in project.dk("close", "Greetings")
    assert "Documentation" not in project.dk("status")


def test_closing_an_epic_leaves_an_unfinished_documentation_run_alone(project: Project) -> None:
    _finished_epic(project, documenter=DOCUMENTS)
    project.dk("document")

    said = project.dk("close", "Greetings")

    assert "Greetings closed" in said and "Documentation: #2 is still unfinished" in said
    assert project.dk("status").count("Documentation") == 1


AUDITS = """
import re
report = pathlib.Path(re.search(r"docs/audits/\\S+\\.md", prompt).group(0))
report.parent.mkdir(parents=True, exist_ok=True)
report.write_text('# Findings\\n')
print('RESULT: done')
"""
SIX_DAYS = 6 * 24 * 3600


def _change(project: Project) -> None:
    (project.root / "new.txt").write_text("more\n")
    project.git("add", "new.txt")
    project.git("commit", "-qm", "more")


def _night_long_ago(project: Project, monkeypatch: pytest.MonkeyPatch) -> None:
    """A first night shift, six days ago by Git's clock."""
    project.configure(coder=HELLO, auditor=AUDITS, documenter=DOCUMENTS)
    for name in ("GIT_COMMITTER_DATE", "GIT_AUTHOR_DATE"):
        monkeypatch.setenv(name, f"@{int(time.time()) - SIX_DAYS} +0000")
    project.dk("night")
    monkeypatch.delenv("GIT_COMMITTER_DATE")
    monkeypatch.delenv("GIT_AUTHOR_DATE")


def test_a_night_shift_writes_documentation_that_was_never_written(project: Project) -> None:
    project.configure(coder=HELLO, auditor=AUDITS, documenter=DOCUMENTS)

    project.dk("night")

    assert project.merged("docs/howto/greet.md") == "# Greet\n"


def test_a_night_shift_leaves_documentation_written_lately(project: Project) -> None:
    project.configure(coder=HELLO, auditor=AUDITS, documenter=DOCUMENTS)
    project.dk("night")
    _change(project)

    said = project.dk("night")

    assert "Documentation: written less than 5 days ago" in said
    assert project.dk("status").count("Documentation") == 1


def test_a_night_shift_documents_again_what_changed_days_ago(
    project: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    _night_long_ago(project, monkeypatch)
    _change(project)

    project.dk("night")

    assert project.dk("status").count("done  Documentation") == 2


def test_a_night_shift_leaves_documentation_of_a_project_that_did_not_change(
    project: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The reports its audits leave are no change to document."""
    _night_long_ago(project, monkeypatch)

    said = project.dk("night")

    assert "Documentation: nothing changed since it was written" in said
    assert project.dk("status").count("Documentation") == 1


def test_a_night_shift_says_nothing_of_documentation_where_nobody_documents(
    project: Project,
) -> None:
    project.configure(coder=HELLO, auditor=AUDITS)

    assert "Documentation" not in project.dk("night")
