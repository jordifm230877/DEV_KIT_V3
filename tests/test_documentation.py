"""The user can have the project's documentation brought up to date with its code: an agent
reads and tries the product, and only what it writes in the documentation folders is kept."""

from __future__ import annotations

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
