"""Mistakes in how the project is set up are reported in plain words, not as crashes."""

from __future__ import annotations

from conftest import Project


def test_running_without_a_configuration_file_says_so(project: Project) -> None:
    project.dk("add", "Greet", "--spec", "x")

    assert "devkit.toml does not exist" in project.refused("run")


def test_a_configuration_that_cannot_be_read_says_where(project: Project) -> None:
    (project.root / "devkit.toml").write_text("max_attempts = \n")

    assert "devkit.toml:" in project.refused("run")


def test_an_unknown_setting_is_refused(project: Project) -> None:
    (project.root / "devkit.toml").write_text("max_atempts = 2\n")

    assert "max_atempts" in project.refused("run")


def test_a_project_without_a_coder_says_which_role_is_missing(project: Project) -> None:
    (project.root / "devkit.toml").write_text("max_attempts = 2\n")
    project.dk("add", "Greet", "--spec", "x")

    assert "no agent with the role 'coder'" in project.refused("run")


def test_an_unknown_agent_program_is_named(project: Project) -> None:
    (project.root / "devkit.toml").write_text(
        '[[agents]]\nname = "coder-1"\nrole = "coder"\nprogram = "nope"\n'
    )
    project.dk("add", "Greet", "--spec", "x")

    assert "unknown agent program 'nope'" in project.refused("run")


def test_asking_for_a_ticket_that_does_not_exist_says_so(project: Project) -> None:
    assert "no ticket #7" in project.refused("show", "7")
