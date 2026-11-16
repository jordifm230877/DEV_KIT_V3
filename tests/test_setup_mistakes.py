"""Mistakes in how the project is set up are reported in plain words, not as crashes."""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import Project

from dk.cli import main


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

    assert "no agent has the role 'coder'" in project.refused("run")


def test_an_unknown_agent_program_is_named(project: Project) -> None:
    (project.root / "devkit.toml").write_text(
        '[[agents]]\nname = "coder-1"\nrole = "coder"\nprogram = "nope"\n'
    )
    project.dk("add", "Greet", "--spec", "x")

    assert "unknown agent program 'nope'" in project.refused("run")


def test_asking_for_a_ticket_that_does_not_exist_says_so(project: Project) -> None:
    assert "no ticket #7" in project.refused("show", "7")


@pytest.mark.parametrize(
    "command", [["status"], ["approve", "48"], ["add", "Greet", "--spec", "x"]]
)
def test_a_command_given_in_a_folder_that_is_no_project_says_so_and_leaves_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], command: list[str]
) -> None:
    """Given by mistake in a folder of a network drive, `dk approve` left a `.devkit` there
    and ended in a crash: database is locked."""
    assert main(["--project", str(tmp_path), *command]) == 1

    said = capsys.readouterr().out
    assert "no project in" in said and str(tmp_path) in said and "dk init" in said
    assert list(tmp_path.iterdir()) == []


def test_a_project_can_be_begun_in_a_folder_that_holds_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["--project", str(tmp_path), "init", "--model", "some/model"]) == 0

    assert (tmp_path / "devkit.toml").exists()
    assert main(["--project", str(tmp_path), "status"]) == 0
