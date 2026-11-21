"""A ticket that builds on another waits until that one is merged."""

from __future__ import annotations

import sqlite3

from conftest import Project

# Each ticket writes a file named after itself that lists what it found in its copy.
BUILDS = (
    "number = prompt.split('Ticket #')[1][0]\n"
    "if number == '1':\n"
    "    import time; time.sleep(0.5)\n"
    "found = sorted(path.name for path in pathlib.Path('.').glob('*.txt'))\n"
    "pathlib.Path(number + '.txt').write_text(' '.join(found))\n"
    "print('RESULT: done')"
)
ASKS = "print('RESULT: question: which language?')"


def test_a_ticket_starts_from_the_merged_work_of_the_one_it_follows(project: Project) -> None:
    project.configure(coder=BUILDS, coders=2)
    project.dk("add", "Base", "--spec", "a")
    project.dk("add", "On top", "--spec", "b", "--after", "1")

    project.dk("run")

    assert project.merged("2.txt") == "1.txt"


def test_the_status_says_what_a_ticket_waits_for(project: Project) -> None:
    project.configure(coder=BUILDS)
    project.dk("add", "Base", "--spec", "a")
    project.dk("add", "Other base", "--spec", "b")
    project.dk("add", "On top", "--spec", "c", "--after", "1", "--after", "2")
    assert "#3 specify  On top  waits for #1, #2" in project.dk("status")

    project.dk("run")

    assert "#3 done  On top\n" in project.dk("status")
    assert project.merged("3.txt") == "1.txt 2.txt"


def test_a_ticket_is_not_started_while_the_one_it_follows_is_stopped(project: Project) -> None:
    project.configure(coder=ASKS, coders=2)
    project.dk("add", "Base", "--spec", "a")
    project.dk("add", "On top", "--spec", "b", "--after", "1")

    project.dk("run")

    assert "started" not in project.dk("show", "2")
    assert "waits for #1" in project.dk("show", "2")


def test_a_cancelled_ticket_holds_nobody_back(project: Project) -> None:
    project.configure(coder=BUILDS)
    project.dk("add", "Base", "--spec", "a")
    project.dk("add", "On top", "--spec", "b", "--after", "1")

    project.dk("cancel", "1")
    project.dk("run")

    status = project.dk("status")
    assert "#2 done" in status and "waits" not in status


def test_a_ticket_cannot_follow_one_that_does_not_exist(project: Project) -> None:
    assert "there is no ticket #7" in project.refused(
        "add", "On top", "--spec", "b", "--after", "7", "--epic", "Work"
    )
    assert project.dk("status") == ""


def test_a_ticket_list_from_before_tickets_had_an_order_still_works(project: Project) -> None:
    home = project.root / ".devkit"
    home.mkdir()
    old = sqlite3.connect(home / "tickets.db")
    old.executescript(
        "CREATE TABLE ticket (id INTEGER PRIMARY KEY, title TEXT NOT NULL, spec TEXT NOT NULL,"
        " step TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, note TEXT NOT NULL DEFAULT '',"
        " stopped INTEGER NOT NULL DEFAULT 0, protected TEXT NOT NULL DEFAULT '{}',"
        " epic TEXT NOT NULL DEFAULT '');"
        "INSERT INTO ticket (title, spec, step) VALUES ('Old', 'a', 'specify');"
    )
    old.close()

    project.dk("add", "New", "--spec", "b", "--after", "1")

    status = project.dk("status")
    assert "#1 specify  Old\n" in status and "#2 specify  New  waits for #1" in status
