"""A disposable Git project whose coder is a small script instead of a real model."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any
from urllib.request import urlopen

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
        """Each role is a Python body that finds its instructions in `prompt`.

        `others` adds one agent per extra role, for example `verifier="..."`.
        """
        tools = self.root.parent / "tools"
        tools.mkdir(exist_ok=True)
        (tools / "check.py").write_text(f"import sys, pathlib\n{check}\n")
        agents = ""
        for role, body in {"coder": coder, **others}.items():
            script = tools / f"{role}.py"
            given = "sys.argv[-1]" if role == "principal" else "sys.stdin.read()"
            script.write_text(f"import sys, pathlib\nprompt = {given}\n{body}\n")
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


FAKE_HERDR = """\
import json, pathlib, sys
calls = pathlib.Path(__file__).with_name("herdr-calls.jsonl")
before = calls.read_text().count("\\n") if calls.exists() else 0
with calls.open("a") as log:
    log.write(json.dumps(sys.argv[1:]) + "\\n")
if pathlib.Path(__file__).with_name("herdr-broken").exists():
    sys.exit(1)
if sys.argv[1:3] == ["tab", "get"]:
    print(json.dumps({"result": {"tab": {"label": "1", "tab_id": sys.argv[3]}}}))
if sys.argv[1:3] == ["tab", "create"]:
    n = before + 1
    made = {"tab": {"tab_id": f"w1:t{n}"}, "root_pane": {"pane_id": f"w1:p{n}"}}
    print(json.dumps({"result": made}))
"""


class Herdr:
    def __init__(self, folder: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self._folder = folder
        script = folder / "herdr.py"
        script.write_text(FAKE_HERDR)
        launcher = folder / "herdr"
        launcher.write_text(f'#!/bin/sh\nexec {sys.executable} {script} "$@"\n')
        launcher.chmod(0o755)
        monkeypatch.setenv("HERDR_BIN_PATH", str(launcher))
        monkeypatch.setenv("HERDR_WORKSPACE_ID", "w1")

    def calls(self) -> list[list[str]]:
        log = self._folder / "herdr-calls.jsonl"
        return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []

    def breaks(self) -> None:
        (self._folder / "herdr-broken").touch()


@pytest.fixture
def herdr(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Herdr:
    return Herdr(tmp_path, monkeypatch)


PREAMBLE = """\
import json, pathlib, sys
here = pathlib.Path(__file__).parent
me = pathlib.Path(__file__).stem
with (here / f"{me}-calls.jsonl").open("a") as log:
    log.write(json.dumps(sys.argv[1:]) + "\\n")
prompt = sys.argv[-1]

def emit(**event):
    print(json.dumps(event))

def claude_says(*parts):
    emit(type="assistant", message={"role": "assistant", "content": list(parts)})
"""


class Programs:
    """Stand-ins for the real programs on PATH; what each does is written by the test."""

    def __init__(self, folder: Path) -> None:
        self._folder = folder

    def does(self, name: str, body: str) -> None:
        script = self._folder / f"{name}.py"
        script.write_text(PREAMBLE + body + "\n")
        launcher = self._folder / name
        launcher.write_text(f'#!/bin/sh\nexec {sys.executable} {script} "$@"\n')
        launcher.chmod(0o755)

    def calls(self, name: str) -> list[list[str]]:
        log = self._folder / f"{name}-calls.jsonl"
        return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []


@pytest.fixture
def programs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Programs:
    folder = tmp_path / "bin"
    folder.mkdir()
    monkeypatch.setenv("PATH", f"{folder}{os.pathsep}{os.environ['PATH']}")
    return Programs(folder)


def team(project: Project, program: str, *roles: str, settings: str = "", each: str = "") -> None:
    agents = settings + "".join(
        f'[[agents]]\nname = "{role}-1"\nrole = "{role}"\nprogram = "{program}"\n'
        f'model = "some-model"\n{each}\n'
        for role in roles
    )
    (project.root / "devkit.toml").write_text(f'{agents}[checks]\nunit = ["true"]\n')
    project.git("add", "devkit.toml")
    project.git("commit", "-qm", "configure devkit")


Site = Callable[[str], Any]


@pytest.fixture
def site(project: Project) -> Iterator[Site]:
    """Start `dk web` as the user does; ask it for a path as a browser would."""
    command = [sys.executable, "-m", "dk", "--project", str(project.root), "web", "--port", "0"]
    server = subprocess.Popen(command, stdout=subprocess.PIPE, text=True)
    assert server.stdout is not None
    address = server.stdout.readline().split()[-1]
    tools = project.root.parent / "tools"
    tools.mkdir(exist_ok=True)
    (tools / "site.txt").write_text(address)
    (tools / "key.txt").write_text(server.stdout.readline().split()[-1].partition("#")[2])

    def get(path: str) -> Any:
        with urlopen(address.rstrip("/") + path) as answer:
            text = answer.read().decode()
            return json.loads(text) if "json" in answer.headers["Content-Type"] else text

    yield get
    server.terminate()
    server.wait()
