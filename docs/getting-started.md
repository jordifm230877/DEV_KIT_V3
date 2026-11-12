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

The quick way writes a first `devkit.toml` and `AGENTS.md` for you, with a full team on one
model and, for a kind of project it recognises (Rust so far), the right checks:

```bash
dk init --model openai-codex/gpt-6.1-sol
```

Read both files, fill in what is marked, and commit them. Then make sure everything works
before the first ticket:

```bash
dk check
```

It asks every agent one small question, runs every check once, and lists files that are not
committed. Fix whatever it reports as `PROBLEM`; each of those would otherwise stop a ticket
after it had used up its attempts.

Written by hand, `devkit.toml` looks like this:

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

[checks]                # REPLACE with your project's own commands; each must exit 0
unit = ["python3", "-m", "unittest", "-q"]
behaviour = ["behave"]  # the command that runs the behaviour tests
```

The two checks above only fit a Python project. A Rust project would have, for example,
`unit = ["cargo", "test"]` and `lint = ["cargo", "clippy", "--", "-D", "warnings"]`. A check
whose command is not installed fails every ticket, so never leave the example as it is.

Then commit it:

```bash
git add devkit.toml && git commit -m "Configure DevKit"
```

Things to know:

- **Only the coder is required.** Leave out the verifier or QA and that review is skipped.
  Leave out the principal and you write tickets yourself with `dk add`. Leave out the
  tester, together with the `behaviour` check, and tickets go straight to the coder.
- **The `behaviour` check** is `behave` for Python, your Cucumber command for Java.
- **Commit everything agents must see.** Each ticket is worked on in a copy of what Git
  holds; uncommitted files, `AGENTS.md` included, do not exist for the agents.
- **More agents is more lines.** Add `coder-2` with `role = "coder"` and two tickets advance
  at once. The same works for verifiers and QA.
- **Each agent can use a different model.** A smaller model for reviews, for example.
- **Checks** are whatever proves your project works: tests, lint, a build. DevKit runs them
  itself in the ticket's copy of the code; it never takes an agent's word for it.
- **DevKit makes the commits**, one per step, with the ticket's title as the message. Agents
  are told not to commit, so do not ask in `AGENTS.md` for anything in commit messages.
- If your project has an `AGENTS.md`, Pi reads it, so project conventions belong there.

## 4. First ticket

Open a terminal in the project, inside Herdr if you use it, and run:

```bash
dk talk
```

Tell the Principal what you want. While it is not yet clear what to build, it explores
with you: it reads code, asks, and writes what was found and decided in
`docs/discovery.md`. No ticket is written in that phase. When you say it is clear enough, it
proposes epics and tickets, writes them once you agree, and the work starts behind the
conversation. In Herdr you will see a `tickets` tab with overall progress
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
| a coder says an approved scenario is wrong | `dk reject N --note "what to change"`: the test-writer rewrites it and you approve again |

Whatever you write in `--note` is added to the ticket, so every agent that works on it
afterwards reads it.

A ticket you no longer want: `dk cancel N`, or tell the Principal. Its unmerged work is
thrown away.

## 6. Behaviour tests

With a tester in the configuration, every ticket starts with Gherkin scenarios
(`.feature` files) that you approve before any code is written. If there is a verifier, it
looks them over first and sends back any that are not about what a user of the product sees,
so what reaches you is already filtered. Say in `AGENTS.md` where
the scenarios go and where the code that connects them to your product goes (for `behave`,
`features/` and `features/steps/`). Without that, scenarios go under `features/`.

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
dk add "Next" --spec "..." --after 1    # not started until ticket 1 is merged
dk run            # work on every unfinished ticket, then exit
dk status
dk show 1
dk cancel 1       # give a ticket up
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
