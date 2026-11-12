"""A disposable Git project whose coder is a small script instead of a real model."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from dk.cli import main

GIT = ["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid"]


class Project:
    def __init__(self, root: Path, capsys: pytest.CaptureFixture[str]) -> None:
        self.root, self._capsys = root, capsys

    def git(self, *args: str) -> str:
        done = subprocess.run([*GIT, *args], cwd=self.root, capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        return done.stdout.strip()

    def configure(
        self,
        coder: str,
        check: str = "",
        max_attempts: int = 3,
        settings: str = "",
        coders: int = 1,
        **others: str,
    ) -> None:
        """Each role is a Python body that reads its instructions as `prompt`.

        `others` adds one agent per extra role, for example `verifier="..."`.
        """
        tools = self.root.parent / "tools"
        tools.mkdir(exist_ok=True)
        (tools / "check.py").write_text(f"import sys, pathlib\n{check}\n")
        agents = ""
        for role, body in {"coder": coder, **others}.items():
            script = tools / f"{role}.py"
            script.write_text(f"import sys, pathlib\nprompt = sys.stdin.read()\n{body}\n")
            for number in range(1, (coders if role == "coder" else 1) + 1):
                command = json.dumps([sys.executable, str(script)])
                agents += (
                    f'[[agents]]\nname = "{role}-{number}"\nrole = "{role}"\n'
                    f"command = {command}\n\n"
                )
        check_command = json.dumps([sys.executable, str(tools / "check.py")])
        (self.root / "devkit.toml").write_text(  # committed, as a real project would
            f"max_attempts = {max_attempts}\n{settings}\n\n{agents}"
            f"[checks]\nunit = {check_command}\n"
        )
        self.git("add", "devkit.toml")
        self.git("commit", "-qm", "configure devkit")

    def dk(self, *args: str) -> str:
        code = main(["--project", str(self.root), *args])
        output = self._capsys.readouterr().out
        assert code == 0, output
        return output

    def refused(self, *args: str) -> str:
        """The message of a command that `dk` could not carry out."""
        code = main(["--project", str(self.root), *args])
        assert code == 1
        return self._capsys.readouterr().out

    def merged(self, name: str) -> str | None:
        """The content of a file on the main branch, as the user would find it."""
        path = self.root / name
        return path.read_text() if path.exists() else None


@pytest.fixture(autouse=True)
def outside_herdr(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests never touch the Herdr session they may happen to be started from."""
    for name in ("HERDR_WORKSPACE_ID", "HERDR_BIN_PATH", "HERDR_TAB_ID", "HERDR_PANE_ID"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def project(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> Project:
    root = tmp_path / "project"
    root.mkdir()
    made = Project(root, capsys)
    made.git("init", "-q", "-b", "main")
    (root / "README.md").write_text("demo\n")
    made.git("add", "README.md")
    made.git("commit", "-qm", "initial")
    return made
