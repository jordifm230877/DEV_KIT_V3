"""`dk init` writes the two files a project needs, so nobody starts from a wrong example."""

from __future__ import annotations

import tomllib

from conftest import Project


def test_a_new_project_gets_a_full_team_on_the_chosen_model(project: Project) -> None:
    said = project.dk("init", "--model", "some/model")

    written = tomllib.loads((project.root / "devkit.toml").read_text())
    roles = [agent["role"] for agent in written["agents"]]
    assert roles == ["principal", "examiner", "tester", "coder", "verifier", "qa"]
    assert {agent["model"] for agent in written["agents"]} == {"some/model"}
    assert {agent["program"] for agent in written["agents"]} == {"pi"}
    assert "devkit.toml" in said and "AGENTS.md" in said and "commit" in said
    assert project.dk("status") == "", "the written configuration can be read"


def test_a_project_of_an_unknown_kind_is_told_to_write_its_checks(project: Project) -> None:
    said = project.dk("init", "--model", "some/model")

    assert "checks" not in tomllib.loads((project.root / "devkit.toml").read_text())
    assert "[checks]" in said and "features/" in (project.root / "AGENTS.md").read_text()


def test_a_rust_project_gets_the_cargo_checks_and_its_own_folders(project: Project) -> None:
    (project.root / "Cargo.toml").write_text('[package]\nname = "demo"\n')

    project.dk("init", "--model", "some/model")

    checks = tomllib.loads((project.root / "devkit.toml").read_text())["checks"]
    assert checks["test"] == ["cargo", "test"] and checks["format"] == ["cargo", "fmt", "--check"]
    assert checks["lint"] == ["cargo", "clippy", "--all-targets", "--", "-D", "warnings"]
    rules = (project.root / "AGENTS.md").read_text()
    assert "tests/features/" in rules and "cargo clippy --all-targets -- -D warnings" in rules
    assert "DevKit runs all of these on each ticket" in rules, "no agent has to run them all"


def test_files_that_already_exist_are_left_alone(project: Project) -> None:
    (project.root / "AGENTS.md").write_text("our own rules\n")
    (project.root / "devkit.toml").write_text("max_attempts = 5\n")

    said = project.dk("init", "--model", "some/model")

    assert (project.root / "AGENTS.md").read_text() == "our own rules\n"
    assert (project.root / "devkit.toml").read_text() == "max_attempts = 5\n"
    assert said.count("already exists") == 2
