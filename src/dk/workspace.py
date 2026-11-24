"""A separate copy of the code for each ticket, and bringing finished work into the project.

The user's own checkout is only touched by the final merge. Git never runs hooks or helper
programs that an agent could have planted.
"""

from __future__ import annotations

import math
import subprocess
import threading
import time
from pathlib import Path

_SAFE = ("-c", "core.hooksPath=/dev/null")
_AUTHOR = ("-c", "user.name=DevKit", "-c", "user.email=devkit@localhost")


class Workspace:
    def __init__(self, project: Path, home: Path) -> None:
        self._project, self._home = project, home
        self._creating = threading.Lock()

    def _git(self, cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *_SAFE, *_AUTHOR, *args], cwd=cwd, capture_output=True, text=True
        )

    def _must(self, cwd: Path, *args: str) -> str:
        done = self._git(cwd, *args)
        if done.returncode != 0:
            raise RuntimeError(f"git {args[0]} failed: {done.stderr.strip()}")
        return done.stdout.strip()

    def _copy(self, ticket: int) -> Path:
        return self._home / f"ticket-{ticket}"

    def prepare(self, ticket: int) -> Path:
        """The ticket's copy of the code, created on first use and kept between attempts."""
        copy = self._copy(ticket)
        with self._creating:
            if not copy.exists():
                self._home.mkdir(parents=True, exist_ok=True)
                branch = f"ticket/{ticket}"
                self._must(self._project, "worktree", "add", "-q", "-B", branch, str(copy))
        return copy

    def text(self, ticket: int, name: str) -> str:
        """What a file of the ticket says: in its copy, or in the project once that is gone."""
        copy = self._copy(ticket)
        file = (copy if copy.exists() else self._project) / name
        return file.read_text() if file.is_file() else ""

    def save(self, ticket: int, message: str) -> bool:
        """Record what the agent left. Returns whether the ticket has any work to show."""
        copy = self._copy(ticket)
        self._must(copy, "add", "-A")
        self._git(copy, "commit", "-qm", message)  # also concludes an update left to resolve
        ahead = self._must(self._project, "rev-list", "--count", f"HEAD..ticket/{ticket}")
        return ahead != "0"

    def base(self, ticket: int) -> str:
        """The commit the ticket's work started from; `git diff <base>` shows the work."""
        return self._must(self._project, "merge-base", "HEAD", f"ticket/{ticket}")

    def _last(self, what: str, files: tuple[str, ...]) -> str:
        """`what` (a Git format) of the latest commit that wrote any of `files` (patterns)."""
        patterns = (f":(glob){one}" for one in files)
        return self._must(self._project, "log", "-1", f"--format={what}", "--", *patterns)

    def changed_since(self, *files: str, apart: str = "") -> bool:
        """Whether the project changed, apart from what is under `apart` (the folder of
        `files` when not given), since the latest of `files` (patterns) was written; true
        when there is none."""
        last = self._last("%H", files)
        beside = f":(exclude){apart or files[0].rpartition('/')[0]}"
        unchanged = ("diff", "--quiet", last, "HEAD", "--", ".", beside)
        return not last or self._git(self._project, *unchanged).returncode != 0

    def days_since(self, *files: str) -> float:
        """How many days ago the latest of `files` (patterns) was written; never, for none."""
        written = self._last("%ct", files)
        return (time.time() - int(written)) / 86400 if written else math.inf

    def restore(self, ticket: int) -> None:
        """Throw away anything not saved, such as what a reviewer changed or left behind."""
        copy = self._copy(ticket)
        self._must(copy, "reset", "-q", "--hard")
        self._must(copy, "clean", "-qfd")

    def keep_only(self, ticket: int, *kept: str) -> None:
        """Throw away everything not saved in the copy, except what is at these paths: the
        files written, changed or removed there stay so."""
        copy = self._copy(ticket)
        if self._git(copy, "rev-parse", "-q", "--verify", "MERGE_HEAD").returncode == 0:
            # An update left to resolve ends with what the agent made of these paths. Left
            # open, the reset below forgot it, and the same collision came back every time.
            for path in kept:
                self._git(copy, "add", "-A", "--", path)
            self._git(copy, "commit", "-q", "--no-edit")
        self._must(copy, "reset", "-q")
        for path in kept:
            self._git(copy, "add", "-A", "--", path)  # nothing there is no trouble
        self._must(copy, "checkout", "-q", "--", ".")
        self._must(copy, "clean", "-qfd")

    def forget(self, ticket: int, pattern: str) -> None:
        """Have the files matching `pattern` be in the copy as the ticket found them: those
        it wrote go, those it changed or removed come back."""
        copy = self._copy(ticket)
        self._must(copy, "rm", "-rqf", "--ignore-unmatch", "--", pattern)
        self._git(copy, "checkout", "-q", self.base(ticket), "--", pattern)  # none is no trouble
        self.save(ticket, "Remove behaviour tests nobody approved")

    def fingerprints(self, ticket: int, pattern: str) -> dict[str, str]:
        """The files this ticket wrote that match `pattern`, each with its content's identity."""
        copy = self._copy(ticket)
        names = self._must(copy, "diff", "--name-only", self.base(ticket), "HEAD", "--", pattern)
        return {
            name: self._must(copy, "rev-parse", f"HEAD:{name}")
            for name in names.splitlines()
            if (copy / name).exists()
        }

    def tampered(self, ticket: int, fingerprints: dict[str, str]) -> list[str]:
        """Which of those files no longer have the content they were recorded with."""
        copy = self._copy(ticket)
        return [
            name
            for name, content in fingerprints.items()
            if self._git(copy, "rev-parse", f"HEAD:{name}").stdout.strip() != content
        ]

    def put_back(self, ticket: int, fingerprints: dict[str, str], names: list[str]) -> None:
        copy = self._copy(ticket)
        for name in names:
            (copy / name).parent.mkdir(parents=True, exist_ok=True)
            content = self._git(copy, "cat-file", "blob", fingerprints[name]).stdout
            (copy / name).write_text(content)
        self.save(ticket, "Put back approved behaviour tests")

    def update(self, ticket: int) -> tuple[list[str], list[str]]:
        """Bring into the copy what the project gained since. Returns the files that came,
        and those left with conflict markers for the coder to resolve."""
        copy = self._copy(ticket)
        project = self._must(self._project, "rev-parse", "HEAD")
        if self._git(copy, "merge-base", "--is-ancestor", project, "HEAD").returncode == 0:
            return [], []
        came = self._must(copy, "diff", "--name-only", f"HEAD...{project}").splitlines()
        if self._git(copy, "merge", "-q", "--no-edit", project).returncode == 0:
            return came, []
        return came, self._must(copy, "diff", "--name-only", "--diff-filter=U").splitlines()

    def unsaved(self) -> list[str]:
        """The project's files that Git does not hold as they are now; copies lack them."""
        changed = self._must(self._project, "status", "--porcelain").splitlines()
        return [line[2:].strip() for line in changed]

    def discard(self, ticket: int) -> None:
        """Throw away the ticket's copy and everything in it, if it has one."""
        copy = self._copy(ticket)
        if copy.exists():
            self._must(self._project, "worktree", "remove", "--force", str(copy))
            self._must(self._project, "branch", "-qD", f"ticket/{ticket}")

    def merge(self, ticket: int, title: str) -> str | None:
        """Bring the ticket into the project. Returns None, or why it could not be done."""
        message = f"Merge ticket #{ticket}: {title}"
        done = self._git(self._project, "merge", "--no-ff", "-qm", message, f"ticket/{ticket}")
        if done.returncode != 0:
            self._git(self._project, "merge", "--abort")
            return f"the merge could not be done:\n{(done.stderr or done.stdout).strip()}"
        self._must(self._project, "worktree", "remove", "--force", str(self._copy(ticket)))
        self._must(self._project, "branch", "-qd", f"ticket/{ticket}")
        return None
