# Getting started

From nothing to a first ticket merged. About ten minutes.

## 1. What you need

- Linux or macOS, Git, Python 3.14 and [uv](https://docs.astral.sh/uv/).
- [Pi](https://pi.dev) on your `PATH`, already logged in to a model provider.
  Check with `pi --list-models`.
- Optional: [Herdr](https://herdr.dev). Inside it you get one tab per agent.

## 2. Install the `dk` command

```bash
uv tool install --editable /mnt/2TB/projects/DEV_KIT_V3
dk --help
```

`--editable` means the command always runs the code in that folder, so pulling or changing
the code needs no reinstall. To remove it: `uv tool uninstall devkit3`.

## 3. Set up a project

The project must be a Git repository with at least one commit, and you should be on the
branch you want finished work merged into.

Create `devkit.toml` in its top folder:

```toml
max_attempts = 3        # failed attempts before a ticket stops and waits for you

[[agents]]
name = "principal"      # the agent you talk to
role = "principal"
program = "pi"
model = "openai-codex/gpt-6.1-sol"

[[agents]]
name = "tester-1"       # writes the behaviour tests you approve before any code
role = "tester"
program = "pi"
model = "openai-codex/gpt-6.1-sol"

[[agents]]
name = "coder-1"
role = "coder"
program = "pi"
model = "openai-codex/gpt-6.1-sol"

[[agents]]
name = "verifier-1"     # reads the code
role = "verifier"
program = "pi"
model = "openai-codex/gpt-6.1-sol"

[[agents]]
name = "qa-1"           # tries the result as a user would
role = "qa"
program = "pi"
model = "openai-codex/gpt-6.1-sol"

[checks]                # your project's own commands; each must exit 0
unit = ["python3", "-m", "unittest", "-q"]
behaviour = ["behave"]  # runs the behaviour tests: use your project's own command here
```

Then commit it:

```bash
git add devkit.toml && git commit -m "Configure DevKit"
```

Things to know:

- **Only the coder is required.** Leave out the verifier or QA and that review is skipped.
  Leave out the principal and you write tickets yourself with `dk add`. Leave out the
  tester, together with the `behaviour` check, and tickets go straight to the coder.
- **The `behaviour` check must be a command that exists in your project**: `behave` for
  Python, your Cucumber command for Java. A command that is not installed fails every ticket.
- **More agents is more lines.** Add `coder-2` with `role = "coder"` and two tickets advance
  at once. The same works for verifiers and QA.
- **Each agent can use a different model.** A smaller model for reviews, for example.
- **Checks** are whatever proves your project works: tests, lint, a build. DevKit runs them
  itself in the ticket's copy of the code; it never takes an agent's word for it.
- If your project has an `AGENTS.md`, Pi reads it, so project conventions belong there.

## 4. First ticket

Open a terminal in the project, inside Herdr if you use it, and run:

```bash
dk talk
```

Tell the Principal what you want. It asks until it is clear, writes the ticket, and the work
starts behind the conversation. In Herdr you will see a `tickets` tab with overall progress
and one tab per agent showing what it is doing. Ask the Principal how things are going
whenever you like. Leaving the conversation (Ctrl-D) stops the work; whatever was half done
is redone next time.

When a ticket is finished, its changes are merged into your branch as one merge commit.

## 5. When a ticket needs you

Herdr shows a notification, and `dk status` shows the ticket as stopped with the reason:

| It says | What to do |
|---|---|
| `question: ...` or `blocked: ...` | Tell the Principal your answer, or `dk retry N --note "answer"` |
| a check or review failed too many times | Read `dk show N`, then `dk retry N --note "hint"` for a fresh set of attempts |
| `the merge could not be done` | Usually your own uncommitted changes are in the way. Commit or move them, then `dk retry N` |
| `the behaviour tests are ready for you` | See the next section |

## 6. Behaviour tests

With a tester in the configuration, every ticket starts with Gherkin scenarios
(`features/*.feature`) that you approve before any code is written. Say in `AGENTS.md` where
the code that connects the scenarios to your product goes (for `behave`, `features/steps/`).

When the scenarios are ready the ticket waits. **In a second terminal** in the project:

```bash
dk show 3                              # read the scenarios
dk approve 3                           # or:
dk reject 3 --note "what to change"
```

Only you can approve: `dk` refuses this to any agent, the Principal included. After
approval the scenarios are read-only. A coder that changes one has it put back and the work
returned; a coder that thinks one is wrong stops and tells you why.

## 7. Without the conversation

```bash
dk add "Title" --spec "What is wanted and how to tell it is done" --epic "Optional group"
dk run            # work on every unfinished ticket, then exit
dk status
dk show 1
```

## 8. Where things are

Everything DevKit keeps is in `.devkit/` inside the project; Git ignores it.

- `.devkit/logs/<agent>.log` — everything each agent did, newest at the bottom.
- `.devkit/logs/tickets.log` — progress during `dk talk`.
- `.devkit/logs/ticket-N/attempt-M/check-<name>.log` — full output of each check.
- `.devkit/work/ticket-N/` — the ticket's copy of the code while it is in progress.

Deleting `.devkit/` forgets all tickets; your code and merged work are not affected.

## 9. Limits to keep in mind

- Agents run as you, with your Pi settings and full access to your machine. DevKit guards
  against mistakes, not against an agent that deliberately works around it.
- Tried so far only on small throwaway projects with one model.
- Only Pi is known as an agent program. Any other command-line agent can be plugged in with
  `command = [...]` instead of `program`; see the README.
