# Getting started

From nothing to a first ticket merged. About ten minutes.

## 1. What you need

- Linux or macOS, Git, Python 3.14 and [uv](https://docs.astral.sh/uv/).
- An agent program on your `PATH`, already logged in: [Pi](https://pi.dev) (check with
  `pi --list-models`), Claude Code (`claude`) or Codex (`codex`).
- Optional: [Herdr](https://herdr.dev). Inside it you get one tab per agent.

## 2. Install the `dk` command

```bash
uv tool install --editable /mnt/2TB/projects/DEV_KIT_V3
dk --help
```

`--editable` means the command always runs the code in that folder, so pulling or changing
the code needs no reinstall. To remove it: `uv tool uninstall devkit3`.

On another computer, with no copy of the code, install it from the repository. It is
private, so that computer needs an SSH key GitHub knows:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh      # uv, if it is not there; brings Python 3.14
uv tool install git+ssh://git@github.com/jordifm230877/DEV_KIT_V3.git
dk --help
```

To take a newer version later: `uv tool upgrade devkit3`. DevKit has not yet been run on
macOS; to see what holds there, clone the repository and run `uv run pytest -q` in it.

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
name = "verifier-1"     # reads the code and tries the result as a user would
role = "verifier"
program = "pi"
model = "openai-codex/gpt-6.1-sol"

[checks]                # REPLACE with your project's own commands; each must exit 0
unit = ["python3", "-m", "unittest", "-q"]   # on every ticket: the build and the unit tests

[checks.behaviour]      # on a ticket's work, with the .feature files of that ticket alone
run = ["behave", "{features}"]

[checks.epic]           # the whole test suite, only when an epic is closed
all = ["behave"]
```

The checks above only fit a Python project. A Rust project would have, for example,
`unit = ["cargo", "test", "--lib"]` and `lint = ["cargo", "clippy", "--", "-D", "warnings"]`. A check
whose command is not installed fails every ticket, so never leave the example as it is.

Then commit it:

```bash
git add devkit.toml && git commit -m "Configure DevKit"
```

Things to know:

- **Only the coder is required.** Leave out the verifier and the review is skipped.
  Leave out the principal and you write tickets yourself with `dk add`. Leave out the
  tester, together with `[checks.behaviour]`, and tickets go straight to the coder.
- **`[checks.behaviour]`** is `behave` for Python, your Cucumber command for Java. DevKit
  puts the ticket's own `.feature` files where the command says `"{features}"`, and runs
  it after the coder. Inside a longer word, as in `"FEATURES={features}"`, they go there
  with spaces between them. A ticket without behaviour tests skips it.
- **`[checks.epic]`** is everything the project can test. No ticket waits for it: it is
  run when you close an epic, so keep what is slow there and `[checks]` quick. Until then
  a ticket can break a scenario of an earlier one without anybody noticing.
- **In a repository of several components**, a check can say what it is for, and is then
  run only on a ticket that changed something there:

  ```toml
  [checks.auth]
  run = ["make", "-C", "auth", "test"]
  paths = ["auth/**", "shared/**"]

  [checks.behaviour.auth]              # given only the ticket's .feature files under auth/
  run = ["make", "-C", "auth", "behave", "FEATURES={features}"]
  paths = ["auth/**"]
  ```

  A check without `paths` is run on every ticket, as before. A ticket that changed a file
  within no check's paths has every check run, so list shared files under each component
  that uses them; `docs/` and `devkit.toml` belong to none and count for nothing. The
  ticket's history says each time which checks ran and which were left out. A ticket in
  one component can still break another: that shows when the epic is closed, since
  `[checks.epic]` is always run whole.

  The components can be named once, and a check then says which it is for instead of
  repeating the paths. Audits use the same names (section 7):

  ```toml
  [components]
  auth = ["auth/**", "shared/**"]
  login = ["login/**"]

  [checks.auth]
  run = ["make", "-C", "auth", "test"]
  component = "auth"
  ```
- **`devkit.toml` can be split.** A line at its top names other files, written like it,
  anywhere in the project; their paths are given from the project's folder:

  ```toml
  include = ["devkit/agents.toml", "auth/devkit.toml"]
  ```

  Any section can go in them. What two files both set is refused when DevKit starts, with
  the name of the file, rather than one of them chosen; agents are the exception, and those
  of every file make the team. An included file names no further files.
- **Commit everything agents must see.** Each ticket is worked on in a copy of what Git
  holds; uncommitted files, `AGENTS.md` included, do not exist for the agents.
- **More agents is more lines.** Add `coder-2` with `role = "coder"` and two tickets advance
  at once. The same works for verifiers. Behaviour tests for later tickets are
  written while the coders are busy.
- **Each agent can use a different model.** A smaller model for reviews, for example.
- **Each agent can think more or less.** `reasoning = "high"` under an agent is passed to
  its program in that program's own way (Pi `--thinking`, Claude `--effort`, Codex
  `model_reasoning_effort`), so use a level that program knows: `low`, `medium`, `high`
  and `xhigh` in all three. Left out, the program uses its default. Codex refuses a level
  it does not know, which `dk check` shows; Pi and Claude warn and use their default.
- **Checks** are whatever proves your project works: tests, lint, a build. DevKit runs them
  itself in the ticket's copy of the code; it never takes an agent's word for it.
- **DevKit makes the commits**, one per step, with the ticket's title as the message. Agents
  are told not to commit, so do not ask in `AGENTS.md` for anything in commit messages.
- **Coders are told how to work well**: failing test first, smallest change, fix causes,
  and to run `crapper`, `dryer` and `mutator` on what they changed where those are
  installed. The verifier rejects work with no test for new behaviour or that `crapper` or
  `dryer` flag. Put `quality_rules = false` at the top of `devkit.toml` to leave both out.
- **A job that takes over 90 minutes is cut off** and done again; what the agent had done
  is kept. Put `agent_minutes = 120` at the top of `devkit.toml` for another limit, or
  `minutes = 120` under one agent for a limit of its own.
  An agent's tab closes each job with a line that says how it ended: `=== ended ===`,
  `=== cut off after 90 minutes ===` or `=== stopped ===`, so an old command is not
  taken for work still going on.
- **A program that is cut off is warned first.** An agent or a check that takes too long,
  or that is running when you stop the work, is told to end (`SIGTERM`) and has ten seconds
  to tidy up what it started, such as a container; what is still there after that is ended
  outright. The limit for one check (`check_minutes`, 30 by default) counts from when the
  check starts, whatever it waits for meanwhile.
- **Agents may look things up on the web.** Claude and Codex search by themselves; Pi needs
  an extension for it (`pi install npm:pi-codex-search`). Put `web = false` at the top of
  `devkit.toml` to take the web away from all of them.
- **The verifier judges how the work is done and whether it works.** It reads the changes,
  then runs the product and goes through the ticket's acceptance criteria one by one.
- If your project has an `AGENTS.md`, the agents read it, so project conventions belong
  there. (Pi and Codex do by themselves; a Claude agent is told to. In the conversation a
  Claude Principal reads `CLAUDE.md` only: put `@AGENTS.md` in it.)
- `program` is `"pi"`, `"claude"` or `"codex"`, per agent, so a team can mix them. `model`
  is whatever that program calls its models (`sonnet`, `gpt-5-codex`, `provider/name`...).

## 4. First ticket

Open a terminal in the project, inside Herdr if you use it, and run:

```bash
dk talk
```

Tell the Principal what you want. While it is not yet clear what to build, it explores
with you: it reads code, tries things out, asks, and writes each study in a file of its own under
`docs/discovery/`, and what is decided now in `docs/decisions.md`, which stays short. No
ticket is written in that phase. When you say it is clear enough, it
proposes epics and tickets, writes them once you agree, and the work starts behind the
conversation. What it writes always has the same form: an epic says its goal, what it
includes and what it excludes; a ticket what is wanted, its acceptance criteria and what is
out of scope. `dk web` shows both. In Herdr the tab you are talking in is named `Principal` for as long as the conversation
lasts, and you will see a `status` tab that says which agent is on which
ticket and lists the unfinished tickets,
and one tab per agent showing what it is doing. An agent with `tab = false` under its
`[[agents]]` in `devkit.toml` works without one. Outside Herdr, `dk status --watch` in
another terminal shows the same board, and `dk web` shows it in your browser, with every
ticket and its behaviour tests a click away. Next to a working agent the board says how
many tokens its job has sent to the model and how many the model wrote so far; `dk show
NUMBER` lists the same for each job that ended. Ask the Principal how things are going
whenever you like. Leaving the conversation (Ctrl-D) stops the work; whatever was half done
is redone next time.

When a ticket is finished, its changes are merged into your branch as one merge commit.

## 5. When a ticket needs you

A ticket that stops goes to the Principal first. When it can answer safely (the answer
follows from the ticket, `AGENTS.md` or `docs/decisions.md`, and would be cheap to put right)
it sends the ticket on with that answer, once, saying what it is based on. It never decides
what is built, changes approved behaviour tests or makes a choice you left open. Otherwise it writes for you what happened, why, and what it
recommends: `dk show N` has it on a line starting with the Principal's name, and in Herdr
the `team_forum` tab shows it being worked out.

Herdr shows a notification, and `dk status` shows the ticket as stopped with the reason:

| It says | What to do |
|---|---|
| `question: ...` or `blocked: ...` | Tell the Principal your answer, or `dk retry N --note "answer"`; the agent goes on from where it stopped |
| a check or review failed too many times | Read `dk show N`, then `dk retry N --note "hint"` for a fresh set of attempts |
| it stopped before its behaviour tests were approved, for a change no user of the product sees | `dk retry N --no-behaviour-tests`: the ticket goes on to the coder without them, and what the test-writer had written for it is thrown away |
| `the merge could not be done` | Usually your own uncommitted changes are in the way. Commit or move them, then `dk retry N` |
| `the behaviour tests are ready for you` | See the next section |
| a coder says an approved scenario is wrong | `dk reject N --note "what to change"`: the test-writer rewrites it and you approve again |

Whatever you write in `--note` is added to the ticket, so every agent that works on it
afterwards reads it.

A ticket you no longer want: `dk cancel N`, or tell the Principal. Its unmerged work is
thrown away.

A ticket you want left for later, as when the coders are needed elsewhere: `dk pause N`. It
shows as stopped, `paused by the user`, and nobody starts on it; its work is kept. A job an
agent is doing on it is left to end and its result counts, but nothing follows it.
`dk retry N` sends it on from where it was. The page of `dk web` has a button for each.

An epic whose tickets are all finished: `dk close "EPIC NAME"`, or tell the Principal.
Where the project has a whole test suite (`[checks.epic]`), closing writes a run of it,
listed in the epic as `Close EPIC NAME` and carried out by `dk run`, `dk talk` or
`dk night`. If the suite passes, the epic is closed. If it fails, the program writes a
ticket in the epic with what failed, which goes straight to a coder, and runs the suite
again once that ticket is merged. Until then the copy of the project the suite failed
in is kept, with whatever logs the suite wrote there. `dk cancel` on the run gives the closing up.
A closed epic takes one line in `dk status` and accepts no more tickets.
`dk reopen "EPIC NAME"` undoes it.

## 6. Behaviour tests

With a tester in the configuration, every ticket starts with Gherkin scenarios
(`.feature` files) that you approve before any code is written. If there is a verifier, it
looks them over first and sends back any that are not about what a user of the product sees,
so what reaches you is already filtered. They are easiest to read in the page of `dk web`,
where you can also approve them or send them back with a note, answer a stopped ticket,
pause one and accept a proposal. For that, open the page once with the second address `dk web` prints when
it starts, the one that ends in a key: without the key the page only shows. The key changes
each time `dk web` starts.
Say in `AGENTS.md` where
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

## 7. Audits

To have the whole project looked over, ask the Principal or run `dk audit security`,
`dk audit performance` or `dk audit tests` (add `--note "..."` to say what to look at in
particular). An audit of the tests breaks the code on purpose, in its throwaway copy, to see
whether the tests notice; on a large project it is slow, so give the auditor a longer limit
(`minutes = 240` under its `[[agents]]`). It needs an agent with the role `auditor` in `devkit.toml`:

```toml
[[agents]]
name = "auditor-1"
role = "auditor"
program = "pi"
model = "provider/model-name"
```

The audit is carried out like a ticket: you see it in `dk status` and in the auditor's tab.
The auditor works in a throwaway copy, where it may build, run and measure, and uses the
scanners and profilers it finds installed (`cargo audit`, `trivy`, ...). It fixes nothing.
Its report arrives in `docs/audits/`, with the severity and the evidence of each finding.
The page of `dk web` lists the reports under *Audits*, by the day of each, the latest first.
For the findings that matter most, two at most, it proposes a ticket (see below); which of
them become tickets is your decision.

The report ends with the tools the auditor recommends for this project, after looking on
the web for current ones, and how to install each: first the ones it missed in this audit,
with what each would have shown, then the others that exist. Install those you want and list their
commands in `devkit.toml`:

```toml
[audit]
tools = ["cargo-audit", "gitleaks"]
```

The auditor is then told to use them, and `dk check` names those that are not installed.

Where `devkit.toml` names `[components]` (section 3), `dk audit security auth` audits that
component alone: the auditor is told its paths, and the report is its own,
`docs/audits/DAY-security-audit-of-auth.md`. Without a component the audit is of the whole
project, which is where what the components share and how they talk to each other is seen.
DevKit installs nothing itself. When you ask the Principal
to close an epic, it suggests an audit if what the epic changed gives a reason.

### Documentation

`dk document` (add `--note "..."` to say what to write or correct in particular) has the
project's documentation brought up to date with its code. It needs an agent with the role
`documenter` in `devkit.toml`, written like the auditor above. The documenter works in a
throwaway copy, where it may build and run the product, and only what it leaves in two
folders is kept:

- `docs/technical/` — for whoever will change the code: the parts of the product, how they
  fit together, how to build, run and test it.
- `docs/howto/` — for whoever uses the product: one guide for each thing they do with it,
  taken from the approved behaviour tests and tried by the documenter before it is written.

It is carried out like a ticket and only one runs at a time. Nobody reviews what it writes:
read it yourself. When it finds nothing to change, the run ends as done.

Everything under `docs/` is easiest to read in the page of `dk web`, under *Documentation*:
the decisions, the studies, the technical pages and the guides. The audit reports are under
*Audits*.

Where a project has a documenter, two things ask for a run without you: closing an epic
(`dk close`), and the night shift once the documentation is five days old and the project,
apart from `docs/`, changed since it was written.

### Lessons

Where a project has an auditor, closing an epic also has its lessons drawn. Nothing is
asked of you, and the epic does not wait for it.

- A ticket `Lessons of EPIC` is written when the epic's tickets include some where work
  was rejected, or an agent was blocked or had to ask. With none, no ticket is written.
- The auditor reads those tickets and adds three lessons at most to `docs/lessons.md`, or
  none. Each is one line saying what to do or not to do, with the tickets it comes from.
- A verifier checks that each lesson happened on the tickets it names, is concrete, and
  neither repeats nor contradicts `AGENTS.md`. What it rejects goes back to the auditor.
- Coders and verifiers are told to read the file before every ticket.

The file may hold 300 words: a new lesson in a full file takes the place of an old one.
It is yours to edit: delete a line you find wrong.

Claude agents started by DevKit keep no notes of their own between jobs; the lessons are
what the project remembers. Your own Claude sessions are not affected.

### Proposed tickets and a coder's notes

An auditor, and a coder that comes across work its ticket does not cover, propose a ticket
instead of doing the work. A proposed ticket is listed as `proposed` and nothing happens to
it until you decide:

```bash
dk show 14                             # what is proposed, by whom, and on which ticket
dk move 14 --epic "Accounts"           # put it in an epic; --no-epic takes it out of one
dk approve 14                          # it becomes a ticket like any other; add
                                       # --no-behaviour-tests if a user of the product sees nothing of it
dk reject 14 --note "why not"          # it is given up
```

A proposal is accepted only inside an epic. One an auditor makes belongs to none, so you
or the Principal move it first; no other agent can, and only a proposal is moved.
Only you can decide: ask the Principal to explain a proposal or to look into it first, but
`dk` refuses the decision to any agent. A coder may also end its work with one line for you, such
as where it departed from the ticket or what it is unsure of; `dk show N` has it as
`coder-1 noted: ...`. The reviewers are not shown it.

### The night shift

`dk night` writes all three audits and then works like `dk run`. It leaves out an audit
that is still unfinished, and one whose last report the project has not changed since, so
the same findings do not come back every morning.

In a project that names `[components]`, the night shift audits each component instead,
and only those with a change within their paths since their last report. The whole project
is then not audited at night, and a change outside every component brings no audit, unless
the project asks for it:

```toml
[audit]
whole_project_at_night = true
```

To have the night shift start by itself:

```bash
dk night --at 02:30                    # every day at that time; starts nothing now
dk night --off                         # no longer
```

This uses your system's own timers (systemd, for your account); the computer must be on,
and where you are not kept logged in, `loginctl enable-linger` lets it run without you. On
macOS it uses launchd instead: you must be logged in, and a Mac asleep at that time starts
the night shift when it wakes. On a system with neither, have your own scheduler run
`dk night`. In the morning,
`dk status` lists what was proposed. Only one of `dk run`, `dk talk` and `dk night` works on
a project at a time: a night shift that finds work going on writes its audits and leaves
them to it.

Known vulnerabilities in dependencies and container images are better caught on every
ticket by a scanner under `[checks]` than by an audit now and then.

## 8. Without the conversation

```bash
dk add "Title" --spec "What is wanted and how to tell it is done" --epic "Accounts"   # every ticket names its epic
dk add "Next" --spec "..." --epic "Accounts" --after 1    # not started until ticket 1 is merged
dk epic "Accounts" --spec "Goal: ... Includes: ... Excludes: ..."   # what the epic is for
dk add "Test server" --spec "..." --epic "Accounts" --no-behaviour-tests   # changes nothing a user can see
dk run            # work on every unfinished ticket, then exit
dk status
dk show 1
dk cancel 1       # give a ticket up
dk pause 1        # leave it for later, with its work; dk retry 1 sends it on
```

## 9. Where things are

Everything DevKit keeps is in `.devkit/` inside the project; Git ignores it.

- `.devkit/logs/<agent>.log` — everything each agent did, newest at the bottom.
  `dk follow FILE` shows one in colour as it grows, as the agent tabs do.
- `.devkit/logs/tickets.log` — progress during `dk talk`.
- `.devkit/logs/ticket-N/attempt-M/check-<name>.log` — full output of each check.
- `.devkit/work/ticket-N/` — the ticket's copy of the code while it is in progress.

Deleting `.devkit/` forgets all tickets; your code and merged work are not affected.

## 10. Limits to keep in mind

- Agents run as you, with your own settings for their program and full access to your
  machine: Claude and Codex are started with their permission checks and sandbox off, as
  Pi has none. DevKit guards against mistakes, not against an agent that deliberately
  works around it.
- Tried so far only on small throwaway projects with one model.
- Pi, Claude Code and Codex are known as agent programs. Any other command-line agent can
  be plugged in with `command = [...]` instead of `program`; see the README.
