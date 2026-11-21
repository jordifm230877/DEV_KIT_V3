"""Run the project's own checks. The program runs them, so no agent can claim they passed."""

from __future__ import annotations

import threading
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from dk import child

_TAIL_LINES = 30


def concern(files: Sequence[str]) -> bool:
    """Whether files the project gained could change what its checks say. Its documents
    could not, nor devkit.toml: the checks of a run are those it started with."""
    return any(not file.startswith("docs/") and file != "devkit.toml" for file in files)


FEATURES = "{features}"  # where a behaviour check takes the files it is to run


def behaviour(
    commands: Mapping[str, Sequence[str]], features: Sequence[str]
) -> dict[str, tuple[str, ...]]:
    """The checks that run these behaviour-test files, and none when there is no file. The
    files take the place of a `{features}` word, or go inside a longer one, with spaces."""

    def given(word: str) -> Sequence[str]:
        return features if word == FEATURES else [word.replace(FEATURES, " ".join(features))]

    return {
        f"behaviour {name}": tuple(part for word in argv for part in given(word))
        for name, argv in commands.items()
        if features
    }


def run(
    checks: Mapping[str, Sequence[str]],
    cwd: Path,
    logs: Path,
    seconds: float,
    stop: threading.Event | None = None,
    starting: Callable[[str], object] = str,
) -> str | None:
    """Run each check in order, telling `starting` its name first. Returns None if all
    pass, else what failed and its last output."""
    logs.mkdir(parents=True, exist_ok=True)
    for name, argv in checks.items():
        starting(name)
        log = logs / f"check-{name}.log"
        with log.open("w") as output:
            code = child.run(argv, cwd, output.write, seconds, stop)
        if code is None and not (stop and stop.is_set()):
            limit = "the limit for one check (`check_minutes` in devkit.toml)"
            return f"{name} failed: cut off after {seconds / 60:g} minutes, {limit}"
        if code != 0:
            tail = "\n".join(log.read_text().splitlines()[-_TAIL_LINES:])
            return f"{name} failed:\n{tail}"
    return None
