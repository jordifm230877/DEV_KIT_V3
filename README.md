# DevKit 3

A small conductor for a team of coding agents. You write tickets; the program gives each one
to an agent in a separate copy of your code, runs your project's checks itself, and merges
the work only when they pass.

DevKit 3 is a from-scratch successor to DevKit V1 and V2. Its goals, in order: simple to use,
small enough to read, and built from pieces that can be replaced one at a time.
Start with [Getting started](docs/getting-started.md). See also [the design](docs/design.md)
and [the glossary](docs/glossary.md).

## Status

Working so far (see the [build order](docs/design.md#build-order)): you talk with a
Principal agent that writes the tickets, or write them yourself; a ticket goes from
written to merged through a coder, the project's checks and a verifier that reads the work and tries it. With a test-writer
agent, behaviour tests (Gherkin) are written first, wait for your approval and are then
read-only. With several coders, tickets advance side by side; merges happen one at a time, each checked together
with what was merged before it. Tried with a real model through Pi on small throwaway projects.

## Use

`dk init --model MODEL [--program pi|claude|codex]` writes a first `devkit.toml` and `AGENTS.md`, and `dk check` tells
you whether the agents, the checks and the repository are ready. By hand, put a
`devkit.toml` in your Git project and commit it:

```toml
max_attempts = 3            # failed attempts before a ticket stops and waits for you
# agent_minutes = 90        # how long one job of an agent may take before it is cut off and done again;
                            # an agent may have its own: `minutes = 120` under its [[agents]]
                            # `tab = false` under an [[agents]] has it work without a Herdr tab
                            # `reasoning = "high"` under an [[agents]] sets how hard it thinks; its program's default if left out
# check_minutes = 30        # how long one of the project's checks may take before it counts as failed
# quality_rules = false     # coders are told how to work well (tests first, crapper, dryer, mutator); this leaves it out
# web = false               # agents may look things up on the web; this takes it away

[[agents]]
name = "coder-1"
role = "coder"
program = "pi"              # or "claude" or "codex"; each agent names its own
model = "provider/model-name"

[[agents]]                  # optional: the agent you talk to with `dk talk`
name = "principal"
role = "principal"
program = "pi"
model = "provider/model-name"

[[agents]]                  # optional: without a verifier the review is skipped
name = "verifier-1"
role = "verifier"
program = "pi"
model = "provider/model-name"

[[agents]]                  # optional: carries out `dk audit`
name = "auditor-1"
role = "auditor"
program = "pi"
model = "provider/model-name"

[[agents]]                  # optional: carries out `dk document`
name = "documenter-1"
role = "documenter"
program = "pi"
model = "provider/model-name"

[[agents]]                  # optional: writes Gherkin behaviour tests before any code
name = "tester-1"
role = "tester"
program = "pi"
model = "provider/model-name"

[audit]                     # optional: what an audit should have; `dk check` names the missing ones
tools = ["cargo-audit", "gitleaks"]

[checks]                    # run by the program on every ticket's work: the build and the unit tests; all must exit 0
unit = ["pytest", "-q", "tests/unit"]

[checks.behaviour]          # optional: run on a ticket's work with that ticket's own .feature files
run = ["behave", "{features}"]

[checks.epic]               # optional: the whole test suite, run only when an epic is closed
all = ["pytest", "-q"]
```

Then either talk:

```bash
dk talk           # a conversation with the Principal; work goes on behind it until you leave
```

or use the commands yourself:

```bash
dk add "Greeting" --spec "Create greeting.txt containing hello." --epic "Manners"   # optionally --after N, --no-behaviour-tests
dk run            # work on every unfinished ticket
dk status         # one line per ticket; --watch keeps showing agents and unfinished tickets
dk show 1         # the ticket and everything that happened to it
dk web            # the same in your browser: agents, epics, tickets and their behaviour tests, the documents under docs/ and the audit reports by day; with the key it prints, approve and answer there
dk retry 1 --note "an answer"   # send a stopped ticket on again; --no-behaviour-tests if it stopped for them and needs none
dk cancel 1       # give a ticket up; its unmerged work is thrown away
dk epic "EPIC" --spec "Goal: ... Includes: ... Excludes: ..."   # say what an epic is for; without --spec, show it
dk close "EPIC"   # close an epic once all its tickets are finished: the whole test suite (`[checks.epic]`) is run on the
                  # next run, the epic closes if it passes, and what fails becomes a ticket of the epic; a documenter then documents it
dk reopen "EPIC"  # open a closed epic again
dk audit security # or performance, or tests: an `auditor` agent reports on the whole project in
                  # docs/audits/ and proposes tickets for what matters most
dk document       # a `documenter` agent brings docs/technical/ and docs/howto/ up to date with the code
dk night          # every audit that has something new to look at; `--at 02:30` starts it every day
dk approve 1      # accept the behaviour tests shown by `dk show 1`; only you can, no agent
dk reject 1 --note "what to change"
dk propose "Title" --spec "..."   # an agent suggests a ticket; it waits until you `dk approve N` or `dk reject N`
dk move 1 --epic "EPIC"   # put a proposed ticket in an epic, where alone it is accepted; --no-epic takes it out
```

A ticket that stops is looked at by the Principal first: it sends the ticket on with an answer
the project already holds, or explains the stop for you in `dk show N`.

Any program can be an agent: give `command = ["my-agent", "--flag"]` instead of `program`.
It receives the instructions on standard input (or in place of an `"{instructions}"`
argument) and must end its output with one line: `RESULT: done` (a coder or test-writer), `RESULT: approved` or
`RESULT: rejected: <what must change>` (a reviewer), `RESULT: blocked: <why>` or
`RESULT: question: <what>`.

Behaviour tests are `.feature` files, kept where the project's `AGENTS.md` says (under
`features/` if it says nothing). DevKit does not know how to run them: give your project's
own command for them (Cucumber, behave, ...) under `[checks.behaviour]`, with `"{features}"`
where the files go. After the coder, the program runs it with the `.feature` files of that
ticket alone; every other scenario waits for `[checks.epic]`.

Started inside [Herdr](https://herdr.dev), `dk run` opens a `status` tab and one tab per agent showing what it
is doing, and closes them when the run ends (`--no-tabs` to skip). The same text stays in
`.devkit/logs/<agent>.log` as plain text; the tabs show it in colour.

DevKit keeps its own files in `.devkit/` inside the project (ticket list, working copies,
logs); it ignores itself in Git.

## Develop

Python 3.14 and [uv](https://docs.astral.sh/uv/). No runtime dependencies.

```bash
uv sync
uv run ruff format --check . && uv run ruff check . && uv run mypy && uv run pytest -q
```
