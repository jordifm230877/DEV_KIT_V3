"""The two files a project needs before its first ticket: `devkit.toml` and `AGENTS.md`.

Written once and never overwritten. `AGENTS.md` describes the project only; how the work is
organised is the program's business, and a rule there that disagrees with it stops the agents.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

TEAM = ("principal", "examiner", "tester", "coder", "verifier", "qa")


@dataclass(frozen=True)
class Kind:
    """What is known about a kind of project, recognised by a file in its top folder."""

    checks: dict[str, tuple[str, ...]]
    scenarios: str
    steps: str


_KINDS = {
    "Cargo.toml": Kind(
        {
            "format": ("cargo", "fmt", "--check"),
            "lint": ("cargo", "clippy", "--all-targets", "--", "-D", "warnings"),
            "test": ("cargo", "test"),
        },
        "tests/features/",
        "`tests/cucumber.rs`",
    ),
}
_UNKNOWN = Kind({}, "features/", "<!-- say where -->")

_NO_CHECKS = """\
# No checks yet. Add the commands that prove this project works; each must exit 0:
# [checks]
# test = ["your", "test", "command"]
"""

_RULES = """\
# Working on this project

<!-- Say in two or three lines what this project is and who uses it. -->

## Commands

{commands}

## Layout

- Behaviour tests (Gherkin scenarios): `{scenarios}*.feature`
- The code that connects each scenario sentence to the product: {steps}

<!-- Say where the product's code and its unit tests live. -->

## Project rules

<!-- Conventions of this project: language, style, what must not be touched.
Leave out anything about commits, about who may change scenarios and about the order of
work: DevKit takes care of those, and a rule here that disagrees with it stops the agents. -->
"""


def _configuration(kind: Kind, model: str, program: str) -> str:
    text = "max_attempts = 3        # failed attempts before a ticket stops and waits for you\n"
    for role in TEAM:
        name = role if role == "principal" else f"{role}-1"
        text += (
            f'\n[[agents]]\nname = "{name}"\nrole = "{role}"\nprogram = "{program}"\n'
            f"model = {json.dumps(model)}\n"
        )
    if not kind.checks:
        return f"{text}\n{_NO_CHECKS}"
    lines = [f"{name} = {json.dumps(list(argv))}" for name, argv in kind.checks.items()]
    return f"{text}\n[checks]                # each must exit 0\n" + "\n".join(lines) + "\n"


def _rules(kind: Kind) -> str:
    listed = "\n".join(f"    {' '.join(argv)}" for argv in kind.checks.values())
    commands = (
        "DevKit runs all of these on each ticket once its code is written, and they must "
        "succeed.\nWhile you work, run only the tests of what you change, not the whole suite:"
        f"\n\n{listed}"
        if listed
        else "<!-- List the commands that build and test the project. -->"
    )
    return _RULES.format(commands=commands, scenarios=kind.scenarios, steps=kind.steps)


def write(project: Path, model: str, program: str = "pi") -> list[str]:
    """Write whichever of the two files is missing. Returns what to tell the user."""
    kind = next((kind for marker, kind in _KINDS.items() if (project / marker).exists()), _UNKNOWN)
    told = []
    for name, text in (
        ("devkit.toml", _configuration(kind, model, program)),
        ("AGENTS.md", _rules(kind)),
    ):
        if (project / name).exists():
            told.append(f"{name} already exists; left as it is")
        else:
            (project / name).write_text(text)
            told.append(f"wrote {name}")
    if not kind.checks:
        told.append("this kind of project is not known: add its commands under [checks]")
    told.append("read both files, fill in what is marked, then commit them")
    return told
