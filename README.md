# DevKit 3

A small conductor for a team of coding agents. You write tickets; the program gives each one
to an agent in a separate copy of your code, runs your project's checks itself, and merges
the work only when they pass.

DevKit 3 is a from-scratch successor to DevKit V1 and V2. Its goals, in order: simple to use,
small enough to read, and built from pieces that can be replaced one at a time.
See [the design](docs/design.md) and [the glossary](docs/glossary.md).

## Status

Working so far (see the [build order](docs/design.md#build-order)): a ticket goes from
written to merged through a coder, the project's checks, a verifier and QA. With several
coders, tickets advance side by side; merges happen one at a time, each checked together
with what was merged before it. Tried with a real model through Pi on small throwaway projects.

## Use

Put a `devkit.toml` in your Git project and commit it:

```toml
max_attempts = 3            # failed attempts before a ticket stops and waits for you

[[agents]]
name = "coder-1"
role = "coder"
program = "pi"
model = "provider/model-name"

[[agents]]                  # optional: without a verifier or QA that review is skipped
name = "verifier-1"
role = "verifier"
program = "pi"
model = "provider/model-name"

[checks]                    # run by the program in the ticket's copy; all must exit 0
unit = ["pytest", "-q"]
```

Then:

```bash
dk add "Greeting" --spec "Create greeting.txt containing hello."
dk run            # work on every unfinished ticket
dk status         # one line per ticket
dk show 1         # the ticket and everything that happened to it
dk retry 1 --note "an answer"   # send a stopped ticket on again
```

Any program can be an agent: give `command = ["my-agent", "--flag"]` instead of `program`.
It receives the instructions on standard input (or in place of an `"{instructions}"`
argument) and must end its output with one line: `RESULT: done` (a coder), `RESULT: approved` or
`RESULT: rejected: <what must change>` (a reviewer), `RESULT: blocked: <why>` or
`RESULT: question: <what>`.

DevKit keeps its own files in `.devkit/` inside the project (ticket list, working copies,
logs); it ignores itself in Git.

## Develop

Python 3.14 and [uv](https://docs.astral.sh/uv/). No runtime dependencies.

```bash
uv sync
uv run ruff format --check . && uv run ruff check . && uv run mypy && uv run pytest -q
```
