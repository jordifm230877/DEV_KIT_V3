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


def test_a_ticket_sent_on_again_sees_what_the_user_committed_meanwhile(project: Project) -> None:
    needs_hint = (
        "if pathlib.Path('hint.txt').exists():\n"
        "    pathlib.Path('greeting.txt').write_text('hola\\n'); print('RESULT: done')\n"
        "else:\n"
        "    print('RESULT: blocked: there is no hint')"
    )
    project.configure(coder=needs_hint)
    project.dk("add", "Greet", "--spec", "Say hello.")
    project.dk("run")
    assert "there is no hint" in project.dk("status")

    (project.root / "hint.txt").write_text("in Catalan\n")
    project.git("add", "hint.txt")
    project.git("commit", "-qm", "add the hint")
    project.dk("retry", "1")
    project.dk("run")

    assert project.merged("greeting.txt") == "hola\n"


def test_a_coder_is_told_when_the_users_changes_collide_with_its_earlier_work(
    project: Project,
) -> None:
    coder = (
        "text = 'resolved' if '<<<<<<<' in prompt else 'mine'\n"
        "pathlib.Path('greeting.txt').write_text(text + '\\n'); print('RESULT: done')"
    )
    check = "sys.exit(pathlib.Path('greeting.txt').read_text() != 'resolved\\n')"
    project.configure(coder=coder, check=check, max_attempts=1)
    project.dk("add", "Greet", "--spec", "Say hello.")
    project.dk("run")
    assert "#1 stopped" in project.dk("status")

    (project.root / "greeting.txt").write_text("theirs\n")
    project.git("add", "greeting.txt")
    project.git("commit", "-qm", "the user's own greeting")
    project.dk("retry", "1")
    project.dk("run")

    assert project.merged("greeting.txt") == "resolved\n"


def test_what_the_user_answers_becomes_part_of_the_ticket_for_everyone(project: Project) -> None:
    asks = (
        "if 'Catalan' in prompt:\n"
        "    pathlib.Path('greeting.txt').write_text('hola\\n'); print('RESULT: done')\n"
        "else:\n"
        "    print('RESULT: question: which language?')"
    )
    verifier = (
        "pathlib.Path(sys.argv[0]).with_name('verifier.txt').write_text(prompt)\n"
        "print('RESULT: approved')"
    )
    project.configure(coder=asks, verifier=verifier)
    project.dk("add", "Greet", "--spec", "Say hello.")
    project.dk("run")

    project.dk("retry", "1", "--note", "in Catalan")
    project.dk("run")

    told = (project.root.parent / "tools" / "verifier.txt").read_text()
    assert "Say hello." in told and "The user added later: in Catalan" in told
    assert "The user added later: in Catalan" in project.dk("show", "1")
