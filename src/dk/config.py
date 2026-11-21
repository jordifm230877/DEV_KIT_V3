"""The project's `devkit.toml`: who the agents are, which checks to run and the limits."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

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
    max_attempts: int = 3
    agent_minutes: float = 90  # 30 cut off a coder twice on a ticket that builds slowly
    check_minutes: float = 30  # 10 was short for a Rust project's whole test suite
    quality_rules: bool = True  # tell coders how to work well; a project may turn it off
    web: bool = True  # agents may look things up on the web; a project may turn it off
    audit_tools: tuple[str, ...] = ()  # the scanners and profilers an audit should have

    def with_role(self, role: str) -> tuple[Agent, ...]:
        return tuple(agent for agent in self.agents if agent.role == role)


def _table(listed: dict[str, object], name: str) -> bool:
    """Whether `[checks.NAME]` is a group of commands; a list under that name is one check."""
    return isinstance(listed.get(name), dict)


def _commands(listed: dict[str, list[str]]) -> dict[str, tuple[str, ...]]:
    return {name: tuple(argv) for name, argv in listed.items()}


def load(project: Path) -> Config:
    path = project / FILE
    if not path.exists():
        raise ConfigError(f"{path} does not exist")
    try:
        raw = tomllib.loads(path.read_text())
        agents = tuple(
            Agent(**{**entry, "command": tuple(entry.get("command", ()))})
            for entry in raw.pop("agents", [])
        )
        listed = raw.pop("checks", {})
        behaviour = _commands(listed.pop("behaviour", {}) if _table(listed, "behaviour") else {})
        suite = _commands(listed.pop("epic", {}) if _table(listed, "epic") else {})
        tools = tuple(raw.pop("audit", {}).get("tools", ()))
        return Config(agents, _commands(listed), behaviour, suite, audit_tools=tools, **raw)
    except (tomllib.TOMLDecodeError, TypeError) as error:
        raise ConfigError(f"{path}: {error}") from error
