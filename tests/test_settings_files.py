"""The settings of a project may be spread over several files: `devkit.toml` names the
others, which are written like it."""

from __future__ import annotations

from conftest import Project
from test_audit import AUDITS, report
from test_component_checks import CODER, _check, ran


def included(project: Project, name: str, text: str) -> None:
    file = project.root / name
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(text)
    project.git("add", "-A")
    project.git("commit", "-qm", f"settings in {name}")


def test_checks_written_in_other_files_are_run_too(project: Project) -> None:
    project.configure(coder=CODER, settings='include = ["checks.toml", "auth/devkit.toml"]')
    included(project, "checks.toml", _check(project, "checks", "login"))
    included(project, "auth/devkit.toml", _check(project, "checks", "auth"))
    project.dk("add", "auth/a.txt login/b.txt", "--spec", "a")

    project.dk("run")

    assert sorted(ran(project)) == ["auth", "login"] and "#1 done" in project.dk("status")


def test_agents_written_in_another_file_join_the_team(project: Project) -> None:
    project.configure(coder=CODER, auditor=AUDITS)
    whole = (project.root / "devkit.toml").read_text()
    team, rest = whole[whole.index("[[agents]]") : whole.index("[checks]")], whole
    (project.root / "devkit.toml").write_text('include = ["team.toml"]\n' + rest.replace(team, ""))
    included(project, "team.toml", team)

    project.dk("audit", "security")
    project.dk("run")

    assert project.merged(report("security")) is not None


def test_what_two_files_both_set_is_refused(project: Project) -> None:
    project.configure(coder=CODER, settings='include = ["conf/more.toml"]')
    included(project, "conf/more.toml", '[checks]\nunit = ["true"]\n')

    refused = project.refused("run")

    assert "conf/more.toml sets `checks.unit`, which is already set" in refused


def test_a_check_written_once_as_a_list_and_once_as_a_table_is_refused(project: Project) -> None:
    project.configure(coder=CODER, settings='include = ["conf/more.toml"]')
    included(project, "conf/more.toml", '[checks.unit]\nrun = ["true"]\n')

    assert "conf/more.toml sets `checks.unit`" in project.refused("run")


def test_a_file_that_is_not_there_is_named(project: Project) -> None:
    project.configure(coder=CODER, settings='include = ["conf/gone.toml"]')

    assert "conf/gone.toml" in project.refused("run")


def test_a_mistake_is_said_of_the_file_it_is_in(project: Project) -> None:
    project.configure(coder=CODER, settings='include = ["conf/bad.toml"]')
    included(project, "conf/bad.toml", "[checks\n")

    refused = project.refused("run")

    assert "conf/bad.toml: " in refused and "devkit.toml: " not in refused.replace("conf/", "")


def test_one_other_file_may_be_named_without_a_list(project: Project) -> None:
    project.configure(coder=CODER, settings='include = "checks.toml"')
    included(project, "checks.toml", _check(project, "checks", "login"))
    project.dk("add", "login/b.txt", "--spec", "a")

    project.dk("run")

    assert ran(project) == ["login"]


def test_only_devkit_toml_names_other_files(project: Project) -> None:
    project.configure(coder=CODER, settings='include = ["conf/more.toml"]')
    included(project, "conf/more.toml", 'include = ["conf/yet.toml"]\n')

    assert "conf/more.toml may not include other files" in project.refused("run")
