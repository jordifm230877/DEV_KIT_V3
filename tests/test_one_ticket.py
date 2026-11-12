"""Step 1: one ticket goes from written to merged with a single coder."""

from __future__ import annotations

from conftest import Project

WRITES_GREETING = (
    "pathlib.Path('greeting.txt').write_text('hello\\n')\nprint('wrote it\\nRESULT: done')"
)
NEEDS_GREETING = (
    "sys.exit(0 if pathlib.Path('greeting.txt').exists() else 'greeting.txt is missing')"
)


def test_finished_work_that_passes_the_checks_reaches_the_main_branch(project: Project) -> None:
    project.configure(coder=WRITES_GREETING, check=NEEDS_GREETING)
    project.dk("add", "Greet", "--spec", "Create greeting.txt saying hello.")

    project.dk("run")

    assert project.merged("greeting.txt") == "hello\n"
    assert "#1 done" in project.dk("status")
    assert project.git("status", "--porcelain") == ""


def test_the_coder_is_told_the_ticket_and_nothing_about_the_process(project: Project) -> None:
    project.configure(coder="pathlib.Path('seen.txt').write_text(prompt)\nprint('RESULT: done')")
    project.dk("add", "Greet", "--spec", "Create greeting.txt saying hello.")

    project.dk("run")

    seen = project.merged("seen.txt")
    assert seen is not None
    assert "Greet" in seen and "Create greeting.txt saying hello." in seen
    assert len(seen.split()) < 150


def test_failing_checks_send_the_ticket_back_with_the_reason(project: Project) -> None:
    coder = (
        "if 'greeting.txt is missing' in prompt:\n"
        "    pathlib.Path('greeting.txt').write_text('hello\\n')\n"
        "else:\n"
        "    pathlib.Path('other.txt').write_text('oops\\n')\n"
        "print('RESULT: done')"
    )
    project.configure(coder=coder, check=NEEDS_GREETING)
    project.dk("add", "Greet", "--spec", "Create greeting.txt.")

    project.dk("run")

    assert project.merged("greeting.txt") == "hello\n"
    assert "#1 done" in project.dk("status")
    assert "unit failed" in project.dk("show", "1")


def test_a_ticket_that_keeps_failing_stops_and_nothing_is_merged(project: Project) -> None:
    coder = "pathlib.Path('other.txt').open('a').write('again\\n')\nprint('RESULT: done')"
    project.configure(coder=coder, check=NEEDS_GREETING, max_attempts=2)
    project.dk("add", "Greet", "--spec", "Create greeting.txt.")

    project.dk("run")

    status = project.dk("status")
    assert "#1 stopped" in status and "2 attempts" in status
    assert project.merged("other.txt") is None
    assert project.dk("show", "1").count("coder-1 started") == 2


def test_a_coder_that_cannot_do_it_stops_the_ticket_with_its_reason(project: Project) -> None:
    project.configure(coder="print('RESULT: blocked: the spec names no file')")
    project.dk("add", "Vague", "--spec", "Do the thing.")

    project.dk("run")

    status = project.dk("status")
    assert "#1 stopped" in status and "the spec names no file" in status
    assert project.dk("show", "1").count("coder-1 started") == 1


def test_a_question_stops_the_ticket_for_the_user(project: Project) -> None:
    project.configure(coder="print('RESULT: question: which language?')")
    project.dk("add", "Vague", "--spec", "Do the thing.")

    project.dk("run")

    assert "which language?" in project.dk("status")


def test_a_coder_that_gives_no_clear_answer_is_asked_again(project: Project) -> None:
    coder = (
        "marker = pathlib.Path('tried.txt')\n"
        "if marker.exists():\n"
        "    print('RESULT: done')\n"
        "else:\n"
        "    marker.write_text('once\\n'); sys.exit(3)"
    )
    project.configure(coder=coder)
    project.dk("add", "Flaky", "--spec", "Anything.")

    project.dk("run")

    assert "#1 done" in project.dk("status")
    assert project.dk("show", "1").count("coder-1 started") == 2


def test_a_coder_that_changes_nothing_has_not_done_the_ticket(project: Project) -> None:
    project.configure(coder="print('RESULT: done')", max_attempts=1)
    project.dk("add", "Idle", "--spec", "Anything.")

    project.dk("run")

    status = project.dk("status")
    assert "#1 stopped" in status and "changed nothing" in status


def test_running_again_does_not_redo_finished_tickets(project: Project) -> None:
    project.configure(coder=WRITES_GREETING, check=NEEDS_GREETING)
    project.dk("add", "Greet", "--spec", "Create greeting.txt.")
    project.dk("run")
    head = project.git("rev-parse", "HEAD")

    project.dk("run")

    assert project.git("rev-parse", "HEAD") == head
    assert project.dk("show", "1").count("coder-1 started") == 1


def test_tickets_are_done_in_the_order_they_were_written(project: Project) -> None:
    coder = (
        "pathlib.Path('log.txt').open('a').write(prompt.split('Ticket #')[1][0])\n"
        "print('RESULT: done')"
    )
    project.configure(coder=coder)
    project.dk("add", "First", "--spec", "a")
    project.dk("add", "Second", "--spec", "b")

    project.dk("run")

    assert project.merged("log.txt") == "12"


def test_a_coder_that_never_finishes_is_cut_off_and_asked_again(project: Project) -> None:
    coder = (
        "marker = pathlib.Path('tried.txt')\n"
        "if not marker.exists():\n"
        "    marker.write_text('once\\n')\n"
        "    import time; time.sleep(60)\n"
        "print('RESULT: done')"
    )
    project.configure(coder=coder, settings="agent_minutes = 0.01")
    project.dk("add", "Slow", "--spec", "Anything.")

    project.dk("run")

    assert "#1 done" in project.dk("status")
    assert "without a clear answer" in project.dk("show", "1")


def test_a_check_that_never_finishes_counts_as_failed(project: Project) -> None:
    project.configure(
        coder=WRITES_GREETING,
        check="import time; time.sleep(60)",
        max_attempts=1,
        settings="check_minutes = 0.01",
    )
    project.dk("add", "Greet", "--spec", "Create greeting.txt.")

    project.dk("run")

    assert "unit failed" in project.dk("status")
    assert project.merged("greeting.txt") is None


def test_work_that_cannot_be_merged_stops_and_is_not_lost(project: Project) -> None:
    project.configure(coder=WRITES_GREETING, check=NEEDS_GREETING)
    project.dk("add", "Greet", "--spec", "Create greeting.txt.")
    (project.root / "greeting.txt").write_text("the user's own unsaved file\n")

    project.dk("run")

    status = project.dk("status")
    assert "#1 stopped" in status and "merge could not be done" in status
    assert project.merged("greeting.txt") == "the user's own unsaved file\n"
    assert project.git("show", "ticket/1:greeting.txt") == "hello"


def test_planted_git_hooks_are_not_run(project: Project) -> None:
    coder = (
        "hooks = pathlib.Path(__import__('subprocess').run(['git', 'rev-parse', "
        "'--git-common-dir'], capture_output=True, text=True).stdout.strip()) / 'hooks'\n"
        "hooks.mkdir(exist_ok=True)\n"
        "for name in ('pre-commit', 'post-commit', 'pre-merge-commit', 'post-merge'):\n"
        "    hook = hooks / name\n"
        f"    hook.write_text('#!/bin/sh\\ntouch {project.root.parent}/ran\\n')\n"
        "    hook.chmod(0o755)\n"
        "pathlib.Path('greeting.txt').write_text('hello\\n')\nprint('RESULT: done')"
    )
    project.configure(coder=coder)
    project.dk("add", "Greet", "--spec", "Create greeting.txt.")

    project.dk("run")

    assert "#1 done" in project.dk("status")
    assert not (project.root.parent / "ran").exists()
