"""The project's `devkit.toml`: who the agents are, which checks to run and the limits."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

FILE = "devkit.toml"


class ConfigError(Exception):
    """The configuration file is missing or does not make sense."""


@dataclass(frozen=True)
class Agent:
    name: str
    role: str
    program: str = ""
    model: str = ""
    reasoning: str = ""  # how hard it thinks, in its program's own words; empty for its default
    command: tuple[str, ...] = ()
    minutes: float = 0  # how long one job of its may take; 0 for the project's `agent_minutes`
    tab: bool = True  # whether its work is shown in a Herdr tab; it works the same without


@dataclass(frozen=True)
class Config:
    agents: tuple[Agent, ...]
    checks: dict[str, tuple[str, ...]]  # run on every ticket's work
    behaviour: dict[str, tuple[str, ...]]  # run on a ticket's own behaviour tests
    suite: dict[str, tuple[str, ...]]  # the whole test suite, run before an epic is closed
    owns: dict[str, tuple[str, ...]] = field(default_factory=dict)  # a check's paths, if any
    max_attempts: int = 3
    agent_minutes: float = 90  # 30 cut off a coder twice on a ticket that builds slowly
    check_minutes: float = 30  # 10 was short for a Rust project's whole test suite
    quality_rules: bool = True  # tell coders how to work well; a project may turn it off
    web: bool = True  # agents may look things up on the web; a project may turn it off
    audit_tools: tuple[str, ...] = ()  # the scanners and profilers an audit should have
    components: dict[str, tuple[str, ...]] = field(default_factory=dict)  # the paths of each
    audit_whole_at_night: bool = False  # with components, the night shift audits them alone

    def with_role(self, role: str) -> tuple[Agent, ...]:
        return tuple(agent for agent in self.agents if agent.role == role)


def _table(listed: dict[str, object], name: str) -> bool:
    """Whether `[checks.NAME]` is a group of commands; a list under that name is one check."""
    return isinstance(listed.get(name), dict)


def _commands(
    listed: dict[str, Any],
    owns: dict[str, tuple[str, ...]],
    components: dict[str, tuple[str, ...]],
    kind: str = "",
) -> dict[str, tuple[str, ...]]:
    """The command of each check. One written as a table says what it is for, in `paths`
    or by the name of a `component`, which is noted in `owns` under the name it is shown by."""
    found = {}
    for name, entry in listed.items():
        if isinstance(entry, dict):
            if extra := sorted(set(entry) - {"run", "paths", "component"}):
                takes = "takes `run` and `paths` or `component`"
                raise TypeError(f"check '{name}' {takes}, not {', '.join(extra)}")
            if "run" not in entry:
                raise TypeError(f"check '{name}' has no `run`")
            part = entry.get("component", "")
            if part and part not in components:
                named = ", ".join(components) or "none"
                raise TypeError(f"check '{name}' is for the component '{part}'; named: {named}")
            if paths := (*entry.get("paths", ()), *components.get(part, ())):
                owns[kind + name] = paths
            entry = entry["run"]
        found[name] = tuple(entry)
    return found


def _join(into: dict[str, Any], more: dict[str, Any], source: str, under: str = "") -> None:
    """Add the settings of an included file. What is set twice is refused, not chosen."""
    for key, value in more.items():
        if key not in into:
            into[key] = value
        elif isinstance(value, dict) and isinstance(into[key], dict):
            _join(into[key], value, source, f"{under}{key}.")
        elif under + key == "agents":
            into[key] = [*into[key], *value]
        else:
            raise ConfigError(f"{source} sets `{under}{key}`, which is already set")


def _read(path: Path) -> dict[str, Any]:
    try:
        return tomllib.loads(path.read_text())
    except (tomllib.TOMLDecodeError, OSError) as error:
        raise ConfigError(f"{path}: {error}") from error


def _settings(project: Path) -> dict[str, Any]:
    """What `devkit.toml` says, with what the files it names in `include` say."""
    raw = _read(project / FILE)
    names = raw.pop("include", ())
    for name in [names] if isinstance(names, str) else names:
        more = _read(project / name)
        if "include" in more:
            raise ConfigError(f"{name} may not include other files")
        _join(raw, more, name)
    return raw


def _components(named: dict[str, Any]) -> dict[str, tuple[str, ...]]:
    for name, paths in named.items():
        if not isinstance(paths, list):  # a path alone would be read as its letters
            raise TypeError(f"component '{name}' takes a list of paths")
    return {name: tuple(paths) for name, paths in named.items()}


def load(project: Path) -> Config:
    path = project / FILE
    if not path.exists():
        raise ConfigError(f"{path} does not exist")
    raw = _settings(project)
    try:
        agents = tuple(
            Agent(**{**entry, "command": tuple(entry.get("command", ()))})
            for entry in raw.pop("agents", [])
        )
        listed = raw.pop("checks", {})
        owns: dict[str, tuple[str, ...]] = {}
        runners = listed.pop("behaviour", {}) if _table(listed, "behaviour") else {}
        parts = _components(raw.pop("components", {}))
        behaviour = _commands(runners, owns, parts, "behaviour ")
        suite = _commands(listed.pop("epic", {}) if _table(listed, "epic") else {}, {}, parts)
        audit = raw.pop("audit", {})
        raw |= {"audit_tools": tuple(audit.get("tools", ())), "components": parts}
        raw["audit_whole_at_night"] = audit.get("whole_project_at_night", False)
        every = _commands(listed, owns, parts)
        return Config(agents, every, behaviour, suite, owns, **raw)
    except TypeError as error:
        raise ConfigError(f"{path}: {error}") from error
