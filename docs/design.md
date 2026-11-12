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
   ("given, when, then"), as `.feature` files.
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
| screen *(later)* | One Herdr tab per agent, showing its live output; watch-only | Affect the run |
| conversation *(later)* | The tab where the user talks to the Principal | Finish tickets or skip steps |

An agent answers every job in one of three ways: done, blocked (with the reason), or a
question for the user. It never needs to know what happens next.

## Rules that keep it small

- Pieces do not import each other; only `director` and `cli` know them all.
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
   step with its approval and read-only rule *(done)*; epics.
3. Herdr tabs.
4. Conversation with the Principal.
5. Later: Claude and Codex as agent programs, a second-opinion agent, web access.

## Decisions taken while building

- The program does not check that behaviour tests fail before the code exists. The coder
  writes the code that connects the sentences to the product, so until then they cannot pass
  anyway; the check would prove nothing.
- Read-only means the `.feature` files a ticket's test-writer wrote. A coder may add
  scenarios of its own. Changed or deleted ones are put back and the work is returned.
- Each agent job is a fresh run of the agent program with no memory of earlier jobs; what it
  needs to know is in its brief.

## Deliberately left out

Beads, a web dashboard, backups and retention, several projects in one database, a separate
watcher process for Git, per-role credentials, resuming a job exactly where it was.
