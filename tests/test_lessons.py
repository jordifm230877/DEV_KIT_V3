"""When an epic closes, the auditor draws the lessons of what was rejected, blocked or asked
in it, the verifier checks them, and they join one short file every coder and verifier reads."""

from __future__ import annotations

from conftest import Project
from test_close_suite import suite

HELLO = "pathlib.Path('greeting.txt').write_text('hello\\n')\nprint('RESULT: done')"
LESSON = "- Bow before greeting. (#1)\n"
# A verifier that sends the product back once, and keeps what it is told about lessons.
REJECTS_ONCE = """
tools = pathlib.Path(sys.argv[0]).parent
if 'lessons' in prompt.splitlines()[0]:
    (tools / 'checker.txt').write_text(prompt)
    print('RESULT: approved')
elif (tools / 'seen').exists():
    print('RESULT: approved')
else:
    (tools / 'seen').touch()
    print('RESULT: rejected: it does not bow')
"""
# An auditor that looks at the ticket it is pointed at, writes a lesson and meddles.
LEARNS = f"""
import re, shlex, subprocess
tools = pathlib.Path(sys.argv[0]).parent
with (tools / 'learner.txt').open('a') as told:
    told.write(prompt)
dk = shlex.split(re.search(r'`(.+) show N`', prompt)[1])
looked = subprocess.run([*dk, 'show', '1'], capture_output=True, text=True).stdout
(tools / 'looked.txt').write_text(looked)
file = pathlib.Path('docs/lessons.md')
file.parent.mkdir(exist_ok=True)
file.write_text({LESSON!r})
pathlib.Path('README.md').write_text('meddled\\n')
print('RESULT: done')
"""


def told(project: Project, name: str) -> str:
    return (project.root.parent / "tools" / f"{name}.txt").read_text()


def rejected_once(project: Project, **others: str) -> None:
    """An epic with one ticket, merged after the verifier sent it back once."""
    project.configure(coder=HELLO, **{"verifier": REJECTS_ONCE, **others})
    project.dk("add", "Greet", "--spec", "Say hello.", "--epic", "Manners")
    project.dk("run")


def test_closing_an_epic_has_the_lessons_of_what_went_wrong_in_it_kept(project: Project) -> None:
    rejected_once(project, auditor=LEARNS)

    said = project.dk("close", "Manners")
    project.dk("run")

    assert "Manners closed" in said and "#2 written" in said
    assert project.merged("docs/lessons.md") == LESSON
    assert project.merged("README.md") == "demo\n", "only the lessons are kept"
    assert "#2 done  Lessons of Manners" in project.dk("status")
    assert "rejected the work: it does not bow" in told(project, "looked")


def test_the_auditor_is_told_where_to_look_and_how_few_lessons_to_write(project: Project) -> None:
    rejected_once(project, auditor=LEARNS)
    project.dk("close", "Manners")

    project.dk("run")

    brief = told(project, "learner")
    assert "epic Manners" in brief and "#1" in brief
    for part in ("docs/lessons.md", "at most three", "or none", "AGENTS.md", "300 words"):
        assert part in brief
    assert "RESULT: done" in brief and len(brief.split()) < 300


def test_the_verifier_checks_each_lesson_against_what_happened(project: Project) -> None:
    rejected_once(project, auditor=LEARNS)
    project.dk("close", "Manners")

    project.dk("run")

    brief = told(project, "checker")
    assert "git diff" in brief and "docs/lessons.md" in brief
    for part in ("show N", "happened there", "concretely", "AGENTS.md", "more than three"):
        assert part in brief
    assert "RESULT: rejected" in brief and len(brief.split()) < 300


def test_lessons_the_verifier_rejects_go_back_to_the_auditor(project: Project) -> None:
    doubts = REJECTS_ONCE.replace(
        "    print('RESULT: approved')\nelif",
        "    again = (tools / 'doubted').exists()\n    (tools / 'doubted').touch()\n"
        "    print('RESULT: approved' if again else 'RESULT: rejected: too vague')\nelif",
    )
    rejected_once(project, auditor=LEARNS, verifier=doubts)
    project.dk("close", "Manners")

    project.dk("run")

    assert "rejected the lessons: too vague" in told(project, "learner")
    assert project.merged("docs/lessons.md") == LESSON


def test_a_lessons_file_grown_over_its_limit_is_not_kept(project: Project) -> None:
    """It is read before every ticket: one file of notes had reached 13,500 words."""
    long = LEARNS.replace(repr(LESSON), repr("- " + "word " * 300 + "\n"))
    rejected_once(project, auditor=long)
    project.dk("close", "Manners")

    project.dk("run")

    assert project.merged("docs/lessons.md") is None
    shown = project.dk("show", "2")
    assert "docs/lessons.md has 301 words" in shown and "300" in shown
    assert "checker.txt" not in [file.name for file in (project.root.parent / "tools").iterdir()]


def test_a_lessons_file_just_within_its_limit_is_kept(project: Project) -> None:
    full = "- " + "word " * 299 + "\n"
    rejected_once(project, auditor=LEARNS.replace(repr(LESSON), repr(full)))
    project.dk("close", "Manners")

    project.dk("run")

    assert project.merged("docs/lessons.md") == full


def test_an_auditor_that_finds_no_lesson_ends_it_there(project: Project) -> None:
    rejected_once(project, auditor="print('RESULT: done')")
    project.dk("close", "Manners")

    project.dk("run")

    assert "#2 done  Lessons of Manners" in project.dk("status")
    assert "found no lesson to keep" in project.dk("show", "2")
    assert not (project.root.parent / "tools" / "checker.txt").exists(), "nothing to check"


def test_an_epic_where_nothing_went_wrong_has_no_lessons_drawn(project: Project) -> None:
    writes = "pathlib.Path('said.txt').write_text(prompt)\nprint('RESULT: done')"
    project.configure(coder=writes, verifier=REJECTS_ONCE, auditor=LEARNS)
    project.dk("add", "Greet", "--spec", "Say hello.", "--epic", "Another, where it went wrong")
    project.dk("add", "Bow", "--spec", "Bow.", "--epic", "Manners")
    project.dk("run")

    said = project.dk("close", "Manners")

    assert "nothing was rejected, blocked or asked" in said
    assert "#3" not in project.dk("status")


def test_a_ticket_where_an_agent_had_to_ask_is_one_to_learn_from(project: Project) -> None:
    asks = "if 'in English' not in prompt:\n    print('RESULT: question: which language?')\n"
    asks += "    sys.exit()\n" + HELLO
    project.configure(coder=asks, auditor=LEARNS)
    project.dk("add", "Greet", "--spec", "Say hello.", "--epic", "Manners")
    project.dk("run")
    project.dk("retry", "1", "--note", "in English")
    project.dk("run")

    assert "#2 written" in project.dk("close", "Manners")


def test_without_an_auditor_no_lessons_are_drawn(project: Project) -> None:
    rejected_once(project)

    said = project.dk("close", "Manners")

    assert "Manners closed" in said and "#2" not in said


def test_lessons_are_drawn_once_the_whole_test_suite_has_passed(project: Project) -> None:
    project.configure(
        coder=HELLO,
        verifier=REJECTS_ONCE,
        auditor=LEARNS.replace("(#1)", "(#1) "),
        settings=suite(project, needs_cake=False),
    )
    project.dk("add", "Greet", "--spec", "Say hello.", "--epic", "Manners")
    project.dk("run")
    project.dk("close", "Manners")

    project.dk("run")

    status = project.dk("status")
    assert "Manners  closed" in status and "#3 done  Lessons of Manners" in status
    assert project.merged("docs/lessons.md")


def test_coders_and_verifiers_are_told_to_read_the_lessons_there_are(project: Project) -> None:
    keeps = "pathlib.Path(sys.argv[0]).with_suffix('.txt').write_text(prompt)\n"
    writes = keeps + "pathlib.Path('said.txt').write_text(prompt)\nprint('RESULT: done')"
    project.configure(coder=writes, verifier=keeps + "print('RESULT: approved')")
    project.dk("add", "Greet", "--spec", "Say hello.")
    project.dk("run")
    before = told(project, "coder") + told(project, "verifier")
    (project.root / "docs").mkdir()
    (project.root / "docs" / "lessons.md").write_text(LESSON)
    project.git("add", "docs")
    project.git("commit", "-qm", "lessons")
    project.dk("add", "Bow", "--spec", "Bow.")

    project.dk("run")

    assert "lessons.md" not in before, "no words are spent on a file that is not there"
    for role in ("coder", "verifier"):
        assert "Read docs/lessons.md first" in told(project, role)
