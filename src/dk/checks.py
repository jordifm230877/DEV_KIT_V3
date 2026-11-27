"""Run the project's own checks. The program runs them, so no agent can claim they passed."""

from __future__ import annotations

import threading
from collections.abc import Callable, Collection, Mapping, Sequence
from pathlib import Path, PurePosixPath

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


def _within(file: str, paths: Sequence[str]) -> bool:
    return any(PurePosixPath(file).full_match(pattern) for pattern in paths)


def _plain(
    commands: Mapping[str, Sequence[str]], owns: Mapping[str, Sequence[str]], changed: Sequence[str]
) -> dict[str, tuple[str, ...]]:
    """The checks without paths, and those whose paths hold one of the changed files."""
    return {
        name: tuple(argv)
        for name, argv in commands.items()
        if name not in owns or any(_within(file, owns[name]) for file in changed)
    }


def _runners(
    runners: Mapping[str, Sequence[str]], owns: Mapping[str, Sequence[str]], features: Sequence[str]
) -> dict[str, tuple[str, ...]]:
    """Each runner with the behaviour tests within its paths, and those within nobody's."""
    mine = [p for name, ps in owns.items() if name.startswith("behaviour ") for p in ps]
    loose = [file for file in features if not _within(file, mine)]
    found: dict[str, tuple[str, ...]] = {}
    for name, argv in runners.items():
        paths = owns.get(f"behaviour {name}")
        given = [file for file in features if not paths or file in loose or _within(file, paths)]
        found |= behaviour({name: argv}, given)
    return found


def _told(found: Collection[str], every: Sequence[str], stray: Sequence[str]) -> str:
    """The line for the ticket's history: which checks ran, and which were left out."""
    if stray:
        return f"checks: all of them, as no check's paths hold {', '.join(stray)}"
    out = [name for name in every if name not in found]
    left = f"; left out, nothing of theirs changed: {', '.join(out)}" if out else ""
    return f"checks: {', '.join(found) or 'none'}{left}"


def chosen(
    commands: Mapping[str, Sequence[str]],
    runners: Mapping[str, Sequence[str]],
    owns: Mapping[str, Sequence[str]],
    changed: Sequence[str],
    features: Sequence[str],
) -> tuple[dict[str, tuple[str, ...]], str]:
    """The checks for a ticket that changed these files and has these behaviour tests, and
    a line for its history, empty where no check names paths (`owns`).

    A check with paths is run when a changed file is within them; a runner of behaviour
    tests is given those within its own. A file within nobody's paths goes to all: a check
    run for nothing costs time, one left out lets a fault through."""
    changed = [file for file in changed if concern([file])]
    stray = [file for file in changed if not _within(file, [p for ps in owns.values() for p in ps])]
    found = _plain(commands, {} if stray else owns, changed) | _runners(runners, owns, features)
    every = [*commands, *(f"behaviour {name}" for name in runners if features)]
    return found, _told(found, every, stray) if owns else ""


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
