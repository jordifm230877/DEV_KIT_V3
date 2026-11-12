# Design

Agreed with the user on 2026-11-12. This page is the whole design; if it stops fitting on
one page, the design has grown too much.

## Why a third version

- **V1** is simple to use, but the agents carry the process: long instructions plus an issue
  tracker (Beads) used as task list, message channel and archive at once. Smaller models
  misread the instructions and the process breaks. Only coders can be more than one.
- **V2** moved the process into the program and became reliable, but was built to survive
  every imaginable failure before being used, and grew to about 88,000 lines.
- **V3** keeps the middle: **the program carries the process; an agent only ever receives
  one concrete job.**

## The development cycle

1. The user and the Principal discuss what to build and write one or more **epics**.
2. Epics are split into **tickets**: what is wanted, and the acceptance criteria.
3. A test-writer agent turns each ticket into **behaviour tests** in Gherkin
   ("given, when, then"), as `.feature` files. If there is a verifier, it looks them over
   first and sends back scenarios that are not about what a user of the product sees.
4. **The user approves the behaviour tests.** From then on their text is read-only: the
   program rejects any delivery that changed it. If a test turns out to be wrong, the agent
   says so and the user decides.
5. A coder writes the code, its own tests and the code that connects the Gherkin sentences
   to the product.
6. The program runs the project's checks: behaviour tests, unit tests and whatever quality
   tools the project lists (complexity, duplication, mutation).
7. A verifier reads the code: cheating, work outside the ticket, poor quality, and whether
   the connecting code really exercises the product.
8. QA tries the product as a user would, against the acceptance criteria.
9. The program merges. Rejected work goes back to the coder with the reason. After the
   configured number of failed attempts the ticket stops and the user is told.

Several coders, verifiers and QA agents may exist; tickets run in parallel, merges happen
one at a time. Who gives the final approval is set per project: QA by default, the user on
request.

## The pieces

| Piece | Does | Does not |
|---|---|---|
| `config` | Reads `devkit.toml`: agents, checks, limits | — |
| `tickets` | Stores tickets, where each one is and what happened | Decide anything |
| `process` | The cycle as a list of steps and the rule for moving along it | Touch files or programs |
| `director` | Carries out the step each ticket waits for; the only piece that decides | Talk to models or Git directly |
| `agents` | Starts an agent program, hands it one job, reads its answer | Know the process |
| `briefs` | The short instructions each role receives | — |
| `workspace` | A separate copy of the code per ticket; merging | Decide when to merge |
| `checks` | Runs the project's check commands | Interpret results |
| `screen` | One Herdr tab per agent, showing what it is doing; watch-only | Affect the run |
| `starter` | Writes a first `devkit.toml` and `AGENTS.md` (`dk init`) | Overwrite anything |
| `preflight` | Finds what would stop the first ticket (`dk check`); a composer | Change anything |
| `child` | Shared groundwork: run a program with a time limit and a stop signal | Know any piece |
| conversation (`dk talk`) | The Principal talks with the user; its only tool is the `dk` command | Approve, finish tickets or skip steps |

An agent answers every job in one of three ways: done, blocked (with the reason), or a
question for the user. It never needs to know what happens next.

## Rules that keep it small

- Pieces do not import each other; only `director` and `cli` know them all. `child` is
  groundwork any piece may use.
- No piece is longer than 300 lines.
- No runtime dependencies beyond Python, Git, Herdr and the agent programs.
- Protection is added only for problems that have actually happened.
- A lost or failed job is thrown away and redone, never resumed mid-way.

`tests/test_shape.py` enforces the first three.

## What it defends against

Mistakes and accidents: an agent that misunderstands, dies, hangs or leaves a Git hook
behind; checks that fail; work that cannot be merged. It does not defend against a hostile
program running as the same user, or an agent that deliberately goes looking for ways around
the process.

## Build order

Each step ends with something usable.

1. **One ticket end to end** with one Pi coder, from the command line. *(done)*
2. Verifier and QA steps; several agents per role; tickets in parallel; the behaviour-test
   step with its approval and read-only rule; epics as a label on tickets. *(done)*
3. Herdr tabs. *(done)*
4. Conversation with the Principal. *(done)*
5. Later: Claude and Codex as agent programs, a second-opinion agent, web access.

## Decisions taken while building

- The program does not check that behaviour tests fail before the code exists. The coder
  writes the code that connects the sentences to the product, so until then they cannot pass
  anyway; the check would prove nothing.
- Read-only means the `.feature` files a ticket's test-writer wrote. A coder may add
  scenarios of its own. Changed or deleted ones are put back and the work is returned.
- Sending behaviour tests back is the user's choice and does not use up an attempt.
- An epic is only a name that groups tickets, until the Principal exists to manage them.
- Approving and rejecting behaviour tests is the user's own act: `dk` refuses them to any
  program started by an agent. The Principal shows the tests and asks the user to run it.
- The Principal is an ordinary interactive agent with a short brief; it learns what happened
  by asking `dk`, and Herdr notifies the user when a ticket needs them.
- Closing the conversation stops work in progress; that step is redone next time.
- Exploring is not a ticket. Before it is clear what to build, the Principal studies and
  asks in the conversation itself and writes the result in `docs/discovery.md`; tickets are
  only for changes to the project that can be checked. A first trial turned "survey this
  repository" into tickets, and the test-writer wrote behaviour tests for a survey.
- `dk cancel` gives a ticket up wherever it is; any agent may run it. A job in progress is
  left to end and its result is ignored. The director removes the copy at the end of a run,
  never the command, so a copy is not removed under an agent working in it.
- A ticket can say which tickets it follows (`dk add --after N`); it is not started until
  they are merged, so its copy begins with their work. A cancelled ticket holds nobody back.
  Tickets without it advance side by side. In the first real trial the Principal planned
  four tickets in order and three stopped at once, each waiting for work it could not see.
- The test-writer puts scenarios where the project's `AGENTS.md` says, and under `features/`
  only when it says nothing: a fixed folder clashed with a Rust project's `tests/features/`.
- Before a test-writer or coder starts, the ticket's copy takes in what the project gained
  since; a collision goes to the coder as files to resolve. Twice a ticket was sent on after
  the user had committed the fix, and its copy, made earlier, could not see it.
- The test-writer is told that scenarios must stay true while later tickets change the
  product. Scenarios such as "no dependency was added", approved for one ticket, blocked
  the next one, which had to add a dependency.
- What the user says with `dk retry --note` or `dk reject --note` is added to the ticket
  itself, so the test-writer, the coder and both reviewers all read it. Before, only the
  next agent saw it, and a reviewer could reject work for following the user's answer.
- `dk reject` also works on a ticket stopped after approval: approved behaviour tests that
  turn out wrong go back to the test-writer and are approved again. A coder had stopped on
  an approved scenario that could not be met, and there was no way to change it.
- Behaviour tests are vetted before the user sees them (step `vet`, done by the verifier,
  skipped without one). Three of the first six stops in the real trial came from approved
  scenarios about the change or the process ("no dependency was added", "the checks pass",
  "the commit message explains"); asking the test-writer not to write them was not enough.
- `dk init` and `dk check` exist because every setup mistake in that trial was found late,
  after a ticket had used its attempts. `preflight` is a fourth composer rather than more
  lines in `cli`.
- Each agent job is a fresh run of the agent program with no memory of earlier jobs; what it
  needs to know is in its brief.

## Deliberately left out

Beads, a web dashboard, backups and retention, several projects in one database, a separate
watcher process for Git, per-role credentials, resuming a job exactly where it was.
