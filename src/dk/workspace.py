"""A separate copy of the code for each ticket, and bringing finished work into the project.

The user's own checkout is only touched by the final merge. Git never runs hooks or helper
programs that an agent could have planted.
"""

from __future__ import annotations

import subprocess
import threading
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

    def restore(self, ticket: int) -> None:
        """Throw away anything not saved, such as what a reviewer changed or left behind."""
        copy = self._copy(ticket)
        self._must(copy, "reset", "-q", "--hard")
        self._must(copy, "clean", "-qfd")

    def update(self, ticket: int) -> tuple[bool, list[str]]:
        """Bring into the copy what the project gained since. Returns whether anything came,
        and the files left with conflict markers for the coder to resolve."""
        copy = self._copy(ticket)
        project = self._must(self._project, "rev-parse", "HEAD")
        if self._git(copy, "merge-base", "--is-ancestor", project, "HEAD").returncode == 0:
            return False, []
        if self._git(copy, "merge", "-q", "--no-edit", project).returncode == 0:
            return True, []
        return True, self._must(copy, "diff", "--name-only", "--diff-filter=U").splitlines()

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
