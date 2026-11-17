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
    command: tuple[str, ...] = ()
    minutes: float = 0  # how long one job of its may take; 0 for the project's `agent_minutes`
    tab: bool = True  # whether its work is shown in a Herdr tab; it works the same without


@dataclass(frozen=True)
class Config:
    agents: tuple[Agent, ...]
    checks: dict[str, tuple[str, ...]]
    max_attempts: int = 3
    agent_minutes: float = 90  # 30 cut off a coder twice on a ticket that builds slowly
    check_minutes: float = 30  # 10 was short for a Rust project's whole test suite
    quality_rules: bool = True  # tell coders how to work well; a project may turn it off
    web: bool = True  # agents may look things up on the web; a project may turn it off
    audit_tools: tuple[str, ...] = ()  # the scanners and profilers an audit should have

    def with_role(self, role: str) -> tuple[Agent, ...]:
        return tuple(agent for agent in self.agents if agent.role == role)


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
        checks = {name: tuple(argv) for name, argv in raw.pop("checks", {}).items()}
        tools = tuple(raw.pop("audit", {}).get("tools", ()))
        return Config(agents, checks, audit_tools=tools, **raw)
    except (tomllib.TOMLDecodeError, TypeError) as error:
        raise ConfigError(f"{path}: {error}") from error
