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
7. A verifier reads the code and judges how the work is done: cheating, work outside the
   ticket, poor quality, and whether the connecting code really exercises the product.
8. QA runs the product as a user would and goes through the acceptance criteria, and the
   approved behaviour tests, one by one.
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
| `jobs` | The jobs agents are given on a ticket: what each is told and what its answer means; a composer | Decide where a ticket goes next |
| `orders` | What the user, or the Principal for them, asks of the ticket list with a command: write, send on, give up, close, decide; a composer | Start anything |
| `nightly` | Has the system start a command every day at a set time (systemd timers) | Know what the command does |
| `principal` | What the Principal is told, in the conversation and about a stopped ticket | Start anything |
| `agents` | Starts an agent program, hands it one job, reads its answer | Know the process |
| `shown` | Turns what Pi, Claude and Codex print into lines a person can read | Start anything |
| `briefs` | The short instructions each role receives | — |
| `workspace` | A separate copy of the code per ticket; merging | Decide when to merge |
| `checks` | Runs the project's check commands | Interpret results |
| `screen` | One Herdr tab per agent, showing what it is doing, and one for the board; watch-only | Affect the run |
| `starter` | Writes a first `devkit.toml` and `AGENTS.md` (`dk init`) | Overwrite anything |
| `preflight` | Finds what would stop the first ticket (`dk check`); a composer | Change anything |
| `views` | What the user is shown: the ticket list, the board, one ticket, an agent's work as it happens, and the same as data for the web page; a composer | Change anything |
| `web` | A web server for this computer only: hands out the page in `pages/` and answers with data it is given | Know what a ticket is |
| `paint` | Colour for one line of an agent's work or of the board | Know agents or tickets |
| `child` | Shared groundwork: run a program with a time limit and a stop signal | Know any piece |
| conversation (`dk talk`) | The Principal talks with the user; its only tool is the `dk` command | Approve, finish tickets or skip steps |
| stop review | A ticket that stops goes to the Principal as a job: it answers from what the project already says, or explains the stop to the user | Decide for the user, change files |

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
5. Claude and Codex as agent programs. *(done)*
6. Later: a second-opinion agent, web access.

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
- As many tickets are built at once (from `code` to `merge`) as there are coders, so with
  one coder each ticket is built on the one before it. Preparing behaviour tests does not
  count: in a real trial the test-writer sat idle on an answered ticket while the one coder
  worked on another. The director hands the first agent to a ticket itself, in ticket order.
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
- A ticket that stops is handed to the Principal before the user (not the wait for approval,
  which is no problem to explain). It is a separate read-only job, not the open conversation:
  a program cannot speak into that. It may send the ticket on once with an answer of its own when that is safe: the answer
  follows from what the ticket, `AGENTS.md` or `docs/discovery.md` decide, and would be cheap
  to put right if wrong. What is built, approved behaviour tests and choices left open stay
  the user's, and it says what the answer is based on. A second stop is the user's. In the real
  trial every stop reached the user as one raw line, and somebody outside DevKit had to
  read the history to say what it meant. Only a Principal set up with `program` is asked;
  a custom `command` is a conversation and cannot take a job.
- The coder's brief carries a short set of quality rules by default (failing test first,
  smallest change, causes not symptoms, and the `crapper`, `dryer` and `mutator` tools where
  installed); `quality_rules = false` leaves them out. The user asked for it: it is the way
  of working they already use by hand. The verifier is told to reject work that has no test for new behaviour or that
  `crapper` or `dryer` flag; the program itself does not enforce them, and a project that
  wants that adds the tools to `[checks]`.
- `dk status --watch` is a board that redraws itself: which agent is on which ticket, the
  tickets not finished, a count of the rest. Inside Herdr it has a `status` tab. The ticket
  list records who is working on a ticket right now, because the board runs as a separate
  program and cannot see inside the director. The user missed the status tab of V1 and V2.
- `dk close EPIC` marks an epic as complete once all its tickets are merged or given up; the
  list then shows it as one line, and it takes no more tickets. It is the user's statement
  that the epic is finished: tickets all being done does not say that by itself. Asked for
  in the real trial when the first epic was finished and nothing could say so. `dk reopen`
  undoes it, so that a mistaken closing can be put right.
- `dk talk` opens no tab for the progress lines: the `status` tab already lists the tickets,
  and two tabs said nearly the same. The lines are still kept in `.devkit/logs/tickets.log`.
- During `dk talk` inside Herdr, the tab of the conversation is named `Principal` and gets
  its earlier name back at the end; the user could not tell it from the other tabs by "1".
- Claude Code and Codex are agent programs beside Pi, for a job and for the conversation;
  an agent names its own, so a team can mix them. Each is started for one job, printing one
  event per line, which `agents` turns into the lines a person follows. They run with
  their permission checks and sandbox switched off: the user chose the freedom Pi already
  has over each program's own automatic gatekeeper, which could refuse a command a project
  needs. A reviewing Claude gets no editing tools, as with Pi; Codex has no such list, and
  the director throws away what a reviewer changes in any case.
- A ticket that changes nothing a user of the product can see (a test fixture, a build
  script) is written with `--no-behaviour-tests` and starts at the coder; whoever writes the
  ticket decides, which was the user's choice over letting the test-writer decide. In the
  real trial such a ticket went to the test-writer, whose scenarios the verifier rightly
  refused, and the user was asked to approve an empty file. It is still checked, verified
  and tried by QA against its acceptance criteria.
- An agent's tab shows its work in colour (`dk follow FILE`): the title of each job, the
  tools it uses, errors, its answer, and the bold and code marks it writes. The colour is
  added when the file is shown; the file stays plain text, because agents and the user's
  own tools read it too. The user asked for the look the agent programs have by themselves.
  A block of code the agent writes between two ``` lines is coloured to its end, and every
  line of a script an agent runs is written to the file marked as part of the command
  (`>   `), because the lines of a script looked like the agent's own words.
  The board is coloured the same way, so that a stopped ticket and a working agent stand
  out; the plain `dk status` list has no colour, because the Principal reads it.
- The title of each job in an agent's log begins with the date and time it started, and the
  board says since when each working agent has been on its ticket, both in the user's own
  time: the user could not tell a job that had just begun from one stuck for an hour.
- An audit (`dk audit security|performance`) looks at the whole project, on the user's
  request only. It is carried like a ticket with a process of its own, `audit` then
  `report`, so it shows on the board, has its tab, and stops and is explained like any
  ticket. An agent with the role `auditor` works in a throwaway copy where it may build, run
  and measure; of what it leaves only its report is kept, merged into `docs/audits/`. It
  fixes nothing, and which findings become tickets is the user's choice. The user chose
  this over a security or performance reviewer on every ticket: speed is measured on the
  whole product, not read from one change, and known vulnerabilities are better found by
  scanners in `[checks]`. Before closing an epic the Principal suggests an audit when what
  the epic changed gives a reason; a `dk close` typed by the user reminds of nothing.
- Which tools an audit should have is listed by the project (`[audit] tools`), not known to
  DevKit: a table of tools per language inside the program would go stale. The auditor ends
  its report with the tools it recommends after looking on the web; the user installs and
  lists those wanted; `dk check` names the listed ones that are not installed.
- Every agent may look things up on the web, reviewers too, unless the project says
  `web = false`: models do not know what was released after they were trained. Claude and
  Codex search by themselves; Pi does through an extension (`pi-codex-search`, or any tool
  with `web` in its name), which DevKit does not install. Agents could already reach the
  network with shell commands, so this opens nothing new.
- Each agent job is a fresh run of the agent program with no memory of earlier jobs; what it
  needs to know is in its brief. The one exception: an agent that stops its job to ask picks
  that job up again when the ticket is sent on, and is told only what was added to the ticket
  since. Starting again lost everything the agent had understood, which made asking so costly
  that agents decided by themselves instead. Pi, Claude and Codex keep a session of every job
  for this, in their own folders; an agent of another program, or a session that is gone,
  starts the job afresh. Tried with the three real programs, each recalling a word across the
  two runs.
- An agent can propose a ticket (`dk propose`), which waits at the step `proposed` until the
  user accepts it or turns it down; `dk` refuses that decision to any agent, as with
  behaviour tests. Coders are told to propose work their ticket does not cover instead of
  doing it, and auditors to propose their most important findings, five at most, knowing
  the titles already asked for or turned down. Agents are given the command rather than a
  format to write proposals in: a command either works or fails, and nothing has to be
  read out of a model's prose.
- A coder may add one line for the user to its answer (`RESULT: done: ...`); it is kept in
  the ticket's history, where the user and the Principal read it. No reviewer is shown it:
  a reviewer judges better without the account of whoever wrote the code, whose reasons
  can talk it into accepting what it would have refused.
- The night shift (`dk night`) is every kind of audit plus `dk run`, started by the user or
  every day by a systemd timer (`--at`). DevKit keeps no clock and no process of its own
  running; the system already has both. An audit is left out while one of its kind is
  unfinished or while the project has not changed since its last report. A third kind of
  audit, `tests`, breaks the code on purpose to see whether the tests notice; it runs in the
  auditor's throwaway copy like the others.
- Only one program works on a project at a time (`dk run`, `dk talk`, `dk night`), held by a
  lock file in `.devkit/`. A night shift that starts by itself could otherwise take the same
  tickets as a conversation left open.
- `dk web` shows the board, the epics and each ticket with its behaviour tests in a browser,
  because long Gherkin files and a list of twenty tickets were hard to review in a terminal.
  It reads the same ticket list as the commands and changes nothing, so it needs no
  protection yet: approving from the page would let an agent on the same computer approve
  its own tests, and must come with a key only the user sees. The page is plain HTML, CSS
  and JavaScript with no build step and asks again every two seconds, as the board does. An
  epic follows another when one of its tickets follows a ticket of the other; that is worked
  out, not stored, so it cannot disagree with the tickets. Looked at with the real trial
  project in a browser, wide and narrow.

## Deliberately left out

Beads, backups and retention, several projects in one database, a separate watcher process
for Git, per-role credentials, resuming a job that was cut off or failed (only one that
stopped to ask is picked up again), changing anything from the web page.
