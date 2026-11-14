"""Several agents share the work: tickets advance side by side, merges happen one by one."""

from __future__ import annotations

from conftest import Project

# Each stand-in finds its ticket number in the instructions and a shared folder beside itself.
SETUP = (
    "import time\n"
    "number = prompt.split('Ticket #')[1].split(':')[0]\n"
    "shared = pathlib.Path(sys.argv[0]).parent\n"
)
OWN_FILE = SETUP + "pathlib.Path(f'file-{number}.txt').write_text('x\\n')\nprint('RESULT: done')"
ONE_AT_A_TIME = SETUP + (
    "busy = shared / 'busy'\n"
    "try:\n"
    "    busy.touch(exist_ok=False)\n"
    "except FileExistsError:\n"
    "    (shared / 'overlap').touch()\n"
    "time.sleep(0.2)\n"
    "busy.unlink(missing_ok=True)\n"
)


def test_two_coders_work_on_two_tickets_at_the_same_time(project: Project) -> None:
    together = SETUP + (
        "(shared / f'here-{number}').touch()\n"
        "deadline = time.monotonic() + 10\n"
        "while len(list(shared.glob('here-*'))) < 2 and time.monotonic() < deadline:\n"
        "    time.sleep(0.02)\n"
        "met = len(list(shared.glob('here-*'))) == 2\n"
        "pathlib.Path(f'file-{number}.txt').write_text('together\\n' if met else 'alone\\n')\n"
        "print('RESULT: done')"
    )
    project.configure(coder=together, coders=2)
    project.dk("add", "One", "--spec", "a")
    project.dk("add", "Two", "--spec", "b")

    project.dk("run")

    assert project.merged("file-1.txt") == "together\n"
    assert project.merged("file-2.txt") == "together\n"


def test_one_agent_does_one_job_at_a_time(project: Project) -> None:
    review = ONE_AT_A_TIME + "print('RESULT: approved')"
    project.configure(coder=OWN_FILE, coders=2, verifier=review)
    project.dk("add", "One", "--spec", "a")
    project.dk("add", "Two", "--spec", "b")

    project.dk("run")

    assert project.merged("file-1.txt") and project.merged("file-2.txt")
    assert not (project.root.parent / "tools" / "overlap").exists()


def test_work_is_checked_together_with_what_was_merged_meanwhile(project: Project) -> None:
    check = (
        "both = pathlib.Path('file-1.txt').exists() and pathlib.Path('file-2.txt').exists()\n"
        "sys.exit('the two changes do not work together' if both else 0)"
    )
    project.configure(coder=OWN_FILE, coders=2, check=check, max_attempts=1)
    project.dk("add", "One", "--spec", "a")
    project.dk("add", "Two", "--spec", "b")

    project.dk("run")

    merged = [name for name in ("file-1.txt", "file-2.txt") if project.merged(name)]
    assert len(merged) == 1
    histories = project.dk("show", "1") + project.dk("show", "2")
    assert "done" in project.dk("status") and "do not work together" in histories


def test_a_coder_resolves_a_clash_with_work_merged_meanwhile(project: Project) -> None:
    clash = SETUP + (
        "said = pathlib.Path('shared.txt')\n"
        "if 'shared.txt' in prompt and '<<<<<<<' in said.read_text():\n"
        "    said.write_text('both\\n')\n"
        "else:\n"
        "    said.write_text(f'only {number}\\n')\n"
        "print('RESULT: done')"
    )
    project.configure(coder=clash, coders=2)
    project.dk("add", "One", "--spec", "a")
    project.dk("add", "Two", "--spec", "b")

    project.dk("run")

    assert project.merged("shared.txt") == "both\n"
    status = project.dk("status")
    assert "#1 done" in status and "#2 done" in status
    assert project.git("status", "--porcelain") == ""


def test_a_ticket_advances_whenever_the_agent_it_needs_is_free(project: Project) -> None:
    coder = SETUP + (
        "deadline = time.monotonic() + 3\n"
        "while not (shared / 'tester-here').exists() and time.monotonic() < deadline:\n"
        "    time.sleep(0.02)\n"
        "met = (shared / 'tester-here').exists()\n"
        "pathlib.Path('file.txt').write_text('together\\n' if met else 'alone\\n')\n"
        "print('RESULT: done')"
    )
    tester = SETUP + (
        "(shared / 'tester-here').touch()\n"
        "pathlib.Path('features').mkdir(exist_ok=True)\n"
        "pathlib.Path('features/two.feature').write_text('Feature: Two\\n')\n"
        "print('RESULT: done')"
    )
    project.configure(coder=coder, tester=tester)
    project.dk("add", "One", "--spec", "a", "--no-behaviour-tests")
    project.dk("add", "Two", "--spec", "b")

    project.dk("run")

    assert project.merged("file.txt") == "together\n", "the one coder was busy, the tester free"
