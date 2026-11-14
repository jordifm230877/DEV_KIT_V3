"""Before the first ticket: can every agent be reached, do the checks pass, is everything
committed? Each of these, found late, stops a ticket after it has used up its attempts.

A composer: it uses the agents, checks, configuration and workspace pieces.
"""

from __future__ import annotations

import shutil
import tempfile
from collections.abc import Iterator
from pathlib import Path

from dk import agents, checks
from dk.config import Agent, Config
from dk.workspace import Workspace

_PROBE = (
    "This only tests that you can be reached. Do nothing else.\n"
    "Reply with exactly this line:\nRESULT: done"
)
_PROBE_SECONDS = 120
Finding = tuple[bool, str]  # whether it is fine, and what to tell the user


def _reach(agent: Agent, argv: tuple[str, ...], log: Path) -> str:
    """Ask the agent's program one small thing. Returns what is wrong, or nothing."""
    if shutil.which(argv[0]) is None:
        return f"{argv[0]} is not installed"
    with tempfile.TemporaryDirectory() as nowhere:
        reply = agents.ask(
            *(argv, _PROBE, Path(nowhere), log, _PROBE_SECONDS),
            title=f"check {agent.name}",
            plain=agents.reader(agent.program),
            name=agent.name,
        )
    if reply.kind != "unclear":
        return ""
    return "gave no answer" + (f"; it said: {reply.text}" if reply.text else "")


def _team(settings: Config, conversing: str, log: Path) -> Iterator[Finding]:
    if not settings.with_role("coder"):
        yield False, "no agent has the role 'coder'"
    asked: dict[tuple[str, ...], str] = {}
    for agent in settings.agents:
        if agent.role == conversing and agent.command:
            continue  # a conversation of the user's own; it cannot be asked a question here
        argv = agent.command or agents.command(agent.program, agent.model, False, settings.web)
        if argv not in asked:
            asked[argv] = _reach(agent, argv, log)
        yield not asked[argv], f"{agent.name}: {asked[argv]}" if asked[argv] else agent.name


def _checks(settings: Config, project: Path, logs: Path) -> Iterator[Finding]:
    if not settings.checks:
        yield False, "no checks: nothing would prove that a ticket's work is right"
    for name, argv in settings.checks.items():
        if shutil.which(argv[0]) is None:
            yield False, f"check '{name}': {argv[0]} is not installed"
            continue
        failure = checks.run({name: argv}, project, logs, settings.check_minutes * 60)
        last = failure.strip().splitlines()[-1] if failure else ""
        yield (
            not failure,
            f"check '{name}'" + (f" fails before any work: {last}" if failure else ""),
        )


def _audit_tools(settings: Config) -> Iterator[Finding]:
    for tool in settings.audit_tools:
        installed = shutil.which(tool) is not None
        yield installed, f"audit tool '{tool}'" + ("" if installed else " is not installed")


def run(
    settings: Config, project: Path, workspace: Workspace, logs: Path, conversing: str
) -> list[Finding]:
    """Everything that would stop the first ticket, found in one go."""
    unsaved = workspace.unsaved()
    committed: Finding = (
        (False, f"not committed, so agents will not see them: {', '.join(unsaved)}")
        if unsaved
        else (True, "everything is committed")
    )
    return [
        committed,
        *_team(settings, conversing, logs / "check.log"),
        *_checks(settings, project, logs / "check"),
        *_audit_tools(settings),
    ]
