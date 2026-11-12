"""A stopped ticket waits for the user, who can send it on its way again."""

from __future__ import annotations

from conftest import Project

HELLO = "pathlib.Path('greeting.txt').write_text('hello\\n')\nprint('RESULT: done')"


def test_an_answer_to_a_question_reaches_the_agent_that_asked(project: Project) -> None:
    asks = (
        "if 'Catalan' in prompt:\n"
        "    pathlib.Path('greeting.txt').write_text('hola\\n'); print('RESULT: done')\n"
        "else:\n"
        "    print('RESULT: question: which language?')"
    )
    project.configure(coder=asks)
    project.dk("add", "Greet", "--spec", "Say hello.")
    project.dk("run")

    project.dk("retry", "1", "--note", "Catalan")
    project.dk("run")

    assert project.merged("greeting.txt") == "hola\n"


def test_a_ticket_out_of_attempts_gets_a_fresh_set(project: Project) -> None:
    second_time = (
        "marker = pathlib.Path(sys.argv[0]).with_name('tried.txt')\n"
        "if marker.exists():\n"
        "    pathlib.Path('greeting.txt').write_text('hello\\n')\n"
        "marker.write_text('once'); print('RESULT: done')"
    )
    project.configure(coder=second_time, max_attempts=1)
    project.dk("add", "Greet", "--spec", "Say hello.")
    project.dk("run")
    assert "#1 stopped" in project.dk("status")

    project.dk("retry", "1")
    project.dk("run")

    assert "#1 done" in project.dk("status")


def test_a_merge_that_was_in_the_way_is_retried_without_redoing_the_work(project: Project) -> None:
    project.configure(coder=HELLO)
    project.dk("add", "Greet", "--spec", "Say hello.")
    in_the_way = project.root / "greeting.txt"
    in_the_way.write_text("the user's own unsaved file\n")
    project.dk("run")
    assert "#1 stopped at merge" in project.dk("status")

    in_the_way.unlink()
    project.dk("retry", "1")
    project.dk("run")

    assert project.merged("greeting.txt") == "hello\n"
    assert project.dk("show", "1").count("coder-1 started") == 1


def test_only_a_stopped_ticket_can_be_retried(project: Project) -> None:
    project.configure(coder=HELLO)
    project.dk("add", "Greet", "--spec", "Say hello.")

    assert "#1 is not stopped" in project.refused("retry", "1")
