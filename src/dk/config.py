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


@dataclass(frozen=True)
class Config:
    agents: tuple[Agent, ...]
    checks: dict[str, tuple[str, ...]]
    max_attempts: int = 3
    agent_minutes: float = 30
    check_minutes: float = 10

    def with_role(self, role: str) -> Agent:
        for agent in self.agents:
            if agent.role == role:
                return agent
        raise ConfigError(f"{FILE} has no agent with the role '{role}'")


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
        return Config(agents, checks, **raw)
    except (tomllib.TOMLDecodeError, TypeError) as error:
        raise ConfigError(f"{path}: {error}") from error
