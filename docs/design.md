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
   says so and the user decides. In an epic the user trusts (`dk trust "EPIC"`), the
   verifier's approval stands for the user's.
5. A coder writes the code, its own tests and the code that connects the Gherkin sentences
   to the product.
6. The program runs the project's checks on the ticket's work: the build, the unit tests
   and the behaviour tests of that ticket alone.
7. A verifier reads the code and judges how the work is done: cheating, work outside the
   ticket, poor quality, and whether the connecting code really exercises the product. It
   then runs the product as a user would and goes through the acceptance criteria one by one.
8. The program merges. Rejected work goes back to the coder with the reason. After the
   configured number of failed attempts the ticket stops and the user is told.
9. When the tickets of an epic are finished the user closes it: the program runs the
   project's whole test suite, and what fails becomes a ticket of the epic.

Several coders and verifiers may exist; tickets run in parallel, merges happen one at a
time.

## The pieces

| Piece | Does | Does not |
|---|---|---|
| `config` | Reads `devkit.toml`: agents, checks, limits | — |
| `tickets` | Stores tickets, where each one is and what happened | Decide anything |
| `process` | The cycle as a list of steps and the rule for moving along it | Touch files or programs |
| `director` | Carries out the step each ticket waits for; the only piece that decides | Talk to models or Git directly |
| `jobs` | The jobs agents are given on a ticket: what each is told and what its answer means; a composer | Decide where a ticket goes next |
| `orders` | What the user, or the Principal for them, asks of the ticket list with a command: write, send on, give up, close, decide; a composer | Start anything |
| `upkeep` | Work on the whole project, not one ticket: writes audits and documentation runs for the user, the close of an epic and the night shift, and the lessons of a closed epic; a composer | Start anything |
| `nightly` | Has the system start a command every day at a set time (systemd timers) | Know what the command does |
| `principal` | What the Principal is told, in the conversation and about a stopped ticket | Start anything |
| `agents` | Starts an agent program, hands it one job, reads its answer | Know the process |
| `shown` | Turns what Pi, Claude and Codex print into lines a person can read | Start anything |
| `spent` | Counts the tokens a job sends its model and the ones the model writes, from what Pi, Claude and Codex print | Start anything |
| `briefs` | The short instructions each role receives | — |
| `audits` | The kinds of audit and what an auditor is told | — |
| `documents` | What a documenter is asked for and told, and the folders it may write | — |
| `lessons` | The file of lessons a project keeps and its limit; what the auditor who writes them, the verifier who checks them and those who read them are told | — |
| `workspace` | A separate copy of the code per ticket; merging | Decide when to merge |
| `checks` | Runs the project's check commands | Interpret results |
| `screen` | One Herdr tab per agent, showing what it is doing, and one for the board; watch-only | Affect the run |
| `starter` | Writes a first `devkit.toml` and `AGENTS.md` (`dk init`) | Overwrite anything |
| `preflight` | Finds what would stop the first ticket (`dk check`); a composer | Change anything |
| `views` | What the user is shown: the ticket list, the board, one ticket, an agent's work as it happens, and the same as data for the web page; a composer | Change anything |
| `web` | A web server for this computer and its network: hands out the page in `pages/` and answers with data it is given | Know what a ticket is |
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
  asks in the conversation itself and writes the result under `docs/`; tickets are
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
- Accepting a proposal with `--no-behaviour-tests` writes that it takes none before it
  becomes a ticket. Written after, a conversation that was going took the ticket up in
  between, as one that takes them: on a real project the test-writer wrote scenarios nobody
  wanted, the verifier rejected them, and the ticket spent three attempts before any code.
- At `merge` the ticket's copy takes in what the project gained meanwhile and the checks
  are run again on the two together, unless all that came is under `docs/` or is
  devkit.toml. On a real project every audit report and documentation run merged meanwhile
  had a ticket's whole suite, minutes long, run a second time. The checks of a run are
  those it started with, so devkit.toml cannot change them; that no check reads `docs/` is
  assumed, as reports and documentation already join the project unchecked.
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
- Approved behaviour tests of a merged ticket are changed by a later ticket: its test-writer
  rewrites them and the user approves them again, as that ticket's own. Both Principal
  briefs say so. They said "only by reject", and the Principal advised `dk reject` on a
  ticket at `examine` for a scenario an earlier ticket had merged; there was none to send.
  The conversation's brief then said only a later ticket's test-writer changes them, and
  the Principal refused the user a ticket without behaviour tests to delete old scenarios,
  which the program allows: only a ticket's own approved tests are read-only to its coder.
  It now says any later ticket may change or remove them.
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
  follows from what the ticket, `AGENTS.md` or `docs/decisions.md` decide, and would be cheap
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
  refused, and the user was asked to approve an empty file. It is still checked, and verified
  against its acceptance criteria.
- An agent that writes a ticket says which it is, `--behaviour-tests` or
  `--no-behaviour-tests`, and is refused one that says neither; the user, typing by hand,
  may still leave it unsaid and gets a ticket that takes them. A ticket that takes none
  says so on its line in the list and on its page. The user asked for the mark. Left to
  say nothing, the Principal of the real trial sent work no user sees to the test-writer:
  of 76 tickets it marked nine, the verifier refused the scenarios of others 27 times, and
  seven times the test-writer wrote none.
- A ticket whose test-writer ends with no scenarios goes on to the coder as one that takes
  none, without stopping: the test-writer is told to write none when no user of the product
  would see the change. It used to be sent back for having written nothing. On a real
  project four tickets of upkeep died there in a day: the verifier refused every scenario as
  not being about the product, the test-writer then rightly wrote none, and the program
  refused that until the attempts ran out. Two rules that could not both be met left the
  ticket to the user each time. Whoever writes the ticket may still say so beforehand.
- An agent works without a tab when its `[[agents]]` says `tab = false`. The user wanted
  the tabs of the agents they watch, not one for an auditor or a documenter that works
  now and then. What it does is still kept in its file under `.devkit/logs/`.
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
  its report with the tools it recommends after looking on the web, those whose lack limited
  that audit first and apart (twelve came as one list, and none was installed); the user installs and
  lists those wanted; `dk check` names the listed ones that are not installed.
- Every agent may look things up on the web, reviewers too, unless the project says
  `web = false`: models do not know what was released after they were trained. Claude and
  Codex search by themselves; Pi does through an extension (`pi-codex-search`, or any tool
  with `web` in its name), which DevKit does not install. Agents could already reach the
  network with shell commands, so this opens nothing new.
- How hard an agent thinks is set per agent (`reasoning`), and is the program's default when
  left out. DevKit passes the word on as written, each program in its own way, and keeps
  no list of levels: the programs' lists differ and change, as the tools table would.
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
  doing it, and auditors to propose their most important findings, two at most or none, knowing
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
  It reads the same ticket list as the commands. The page is plain HTML, CSS
  and JavaScript with no build step and asks again every two seconds, as the board does. An
  epic follows another when one of its tickets follows a ticket of the other; that is worked
  out, not stored, so it cannot disagree with the tickets. Looked at with the real trial
  project in a browser, wide and narrow. It answers every computer of the network, because
  the user looks at it from another one; anyone on that network can read the tickets.
- The page has a part for documentation: every Markdown file under `docs/`, by folder,
  each drawn as a page; the user asked for it because documents are hard to read in a
  terminal. So decisions, studies, audit reports, technical pages and guides are read in
  one place. The page reads Markdown with a small reader of its own (`pages/markdown.js`:
  headings, paragraphs, lists, tables, quotes, rules, code, bold, italic, links), chosen
  over a library fetched from the web, which would not work without a connection and would
  be the project's first dependency. Anything else in a document stays the text it is;
  nothing a document says is run, and a link is followed only to the web or to another
  document. The reader builds a tree and touches no page, so its tests run it with Node,
  and are skipped where there is none. Looked at in a browser with the documents a real
  documenter wrote for the trial project.
- From the page the user approves or sends back behaviour tests, answers a stopped ticket,
  accepts or turns down a proposal and gives a ticket up: the same orders as the commands,
  carried out by the same code. They need a key that `dk web` makes anew each time it
  starts and prints in the user's terminal, at the end of an address to open once; the
  browser keeps it. Without it an agent on the same computer, or anyone on the network,
  could approve in the user's name. The key is written to no file, because agents read
  files. It travels unencrypted, which is enough for a home network and not for an open
  one. Tried in a browser: the page already open when the address with the key was opened
  did not load again, so the key is also read then.
- What a job spends of its model is counted from what the agent's program prints: the tokens
  sent to the model and the tokens it wrote. The board and the page show it for the job
  going on, and the ticket's history keeps it for each job that ended. Each call to the
  model sends again all that came before, so the tokens sent add up to the cost of the job,
  not to how full the model's memory is. How full it is, and its limit, are left out: Claude
  reports both, Pi only the first, and Codex neither while it works, and a figure shown for
  some agents and not for others would mislead. Codex reports only as a turn ends, so its
  count appears late. Read from the real programs, each asked one question.
- The ticket list is kept in SQLite's write-ahead mode, where a reader never waits for a
  writer. Before, the board waited for each write, and counting what jobs spend made writes
  frequent: with the disk busy compiling, the board gave up after five seconds and ended
  with `database is locked`. Programs started before the change go on working with the list.
- The coder, the reviewers and the auditor are told to run a command that takes minutes in
  the background, with its output in a file. An agent program limits how long one command of
  its agent may run, and DevKit cannot change that: Claude cut a QA's `cargo test` off at
  ten minutes, and the ten minutes were lost.
- Only the program runs the whole of the project's checks. A coder is told to run just the
  tests of what it changes; a verifier and QA, that the checks have passed on the code they
  look at; the Principal, never to write the checks as an acceptance criterion; and the
  `AGENTS.md` that `dk init` writes says DevKit runs them. In a trial whose suite took
  fifteen minutes, every ticket listed `cargo test` as a criterion, so the coder, the
  verifier and QA each ran all of it again: over an hour for a change of minutes.
- A project begun from nothing has no checks when `dk init` runs: there is no file yet to
  tell what kind it is, and the starter files are never written again. So the Principal is
  told that the first ticket of a project, or of a component, adds its checks to
  `devkit.toml` and `AGENTS.md`; the starter `AGENTS.md` says who runs the checks even when
  it can list none; and every run of a project with no checks says so. `dk init` does not
  have to know each language, or how a repository of several components is laid out.
- The audit of the tests also tries the unusual and the wrong (empty, huge or malformed
  input, limits, work that fails halfway, is cancelled or times out) and names each case
  with no test. No ticket asks anyone for that, and asking it of the coder or the verifier
  would lengthen every ticket; the audit runs at night and proposes tickets for what it finds.
- The test-writer and the verifier who looks its scenarios over are told two things that
  each stopped a ticket only once it reached the coder: no scenario may need the project's
  whole test suite run (one ran it twice from inside itself, and no check ended within its
  thirty minutes), and no line of free text may start with a Gherkin keyword (a description
  line starting with `Scenarios` left an approved file unreadable). DevKit parses no Gherkin
  itself: the project's own runner is what decides, and the verifier may use it.
- The test-writer reads the scenarios the project already has and writes none for what one
  already checks, and gives a rule its telling cases rather than every value; the verifier
  rejects scenarios that do otherwise. In a real trial fifty or more of some 180 scenarios
  repeated another, most of them rows of limit values that belong in unit tests: each
  started a test server, and the suite took twenty-five minutes on every ticket.
- The Principal is told, in the conversation and when a ticket stops, that approved behaviour
  tests change only by `reject` and that no note lets a coder change them; the coder whose
  changes are put back is told that no note or ticket text changes that. In a real trial the
  Principal advised an exception, the user passed it on as a note, and the coder changed the
  tests on each of its three attempts while the program put them back each time.
- A command given where no project is (no `devkit.toml`, no Git repository, no `.devkit`) is
  refused and leaves nothing behind; `init`, `check` and `follow` need none. Given by mistake
  in a folder of a network drive, `dk approve` made a `.devkit` there and crashed, since the
  ticket list cannot be kept on such a drive: database is locked.
- An audit does not take up a coder: tickets are built while it goes on. Counted as a ticket
  being built, an audit of the tests of fifty minutes kept three approved tickets waiting
  with the one coder idle. The auditor already works in its own copy; its report describes
  the project as it was when the audit began, and what it measures shares the machine.
- Nobody examines a ticket before the work, and one verifier reads the work and tries it:
  the steps `examine` and `qa` and their roles are gone, and a ticket has six steps where
  it had nine. An examiner had been added to find unclear tickets early, and QA tried what
  the verifier had read. On a real project of three days and sixty tickets, with every step
  able to stop a ticket, tickets were sent back or stopped 116 times for 32 merged: the
  examiner alone stopped thirteen, one of them twice in two minutes. A coder that would have to guess asks, as any agent may. A project that still
  lists an `examiner` or a `qa` agent gives it nothing to do.
- Whether behaviour tests are written for a ticket is something the ticket says
  (`--no-behaviour-tests`), not the step it starts at: every ticket starts at the first
  step, and the steps about behaviour tests are skipped for one that takes none.
- A ticket stopped before its behaviour tests are approved can be sent on without them
  (`dk retry N --no-behaviour-tests`), by the user or the Principal, as either may when
  writing it. What its test-writer wrote leaves the ticket's copy, and the scenarios it
  changed or removed come back as they were: on a real project a file the verifier had
  refused stayed there, for the coder to remove or to be merged unapproved. Once tests are
  approved the command is refused, since only `dk reject` changes those. In a real trial a
  proposal accepted with behaviour tests was reliability work on an existing scenario: its
  one scenario was refused, the test-writer then rightly wrote none, the Principal saw why
  and could only send it back to the test-writer, and it was cancelled to be written again.
- What the Principal finds out is kept in two places by how long it lasts. A study is one
  file under `docs/discovery/`, written once. `docs/decisions.md` holds only what is decided
  now and what is open, is rewritten instead of added to, and is the one the
  Principal reads for every ticket. Nothing about a single ticket goes in either: that
  is the ticket's own history. In the real trial the one `docs/discovery.md` reached 898
  lines of decisions, studies and notes on tickets long finished, read whole by the
  examiner for every ticket. The Principal is told to split an older file itself. It is
  also told where a finding about one ticket does go, to the user and into the ticket
  with its `retry` note: told only where not to write it, it wrote its look at a failing
  ticket into the old file all the same. Trying things out with throwaway scripts and data
  is named as its work too: told only to read and to ask, it proposed two tickets to find
  out how a server behaved, one of them to "record decisions with the user", whom no
  coder talks with.
- A documenter (`dk document`, an optional role) keeps `docs/technical/` and `docs/howto/`
  in step with the code. Its job is carried like an audit, with a process of its own,
  `document` then `publish`: it works in a throwaway copy where it may build and run the
  product, and only those two folders are kept of what it leaves. It looks at the whole
  project and at what was merged since it last wrote, rather than being a step of every
  ticket: one writer cannot collide with itself, most tickets change nothing to document,
  and a step would cost every ticket a job. Only one run exists at a time. Finding nothing
  to change is a job done. Guides for users start from the approved behaviour tests, and
  the documenter carries out each step before writing it. Nobody reviews what it writes;
  the user reads it. The user asked for it, after the agents of the real trial left
  documents of their own making across `docs/`.
- The documenter is told how to write, not only what goes where: one file is one kind of
  document (a guide, a reference or an explanation), a guide is named by its task and holds
  only steps, one thought per sentence, one name per thing, and a last reading that takes
  out what a machine writes by habit. A file it changes is left whole by these rules, so
  the old documents come to them as they are touched. The user asked for it, with two
  published sets of rules to draw on (Cursor's `technical-writing` and `unslop` skills,
  MIT); the rules are written anew and much shorter, and none is fetched when it works.
  What it had written for the real trial showed the lack: a 1,310-word `testing.md` that
  mixed how to run the tests, what they need and how to read their results. Its brief may
  now reach 550 words where it kept under 300; it is the only word it gets, since nobody
  reviews it, and it works a few times a week. Tried with a real documenter on a copy of
  the trial project: `testing.md` came out a plain reference, 300 words shorter, but the
  paragraph on what a passing check does not prove was dropped instead of moved, so the
  brief now says that what does not fit a file's kind moves to a file of its own. It also
  wrote a curly apostrophe in a title, so curly quotes are among what it takes out.
- The documenter carries out what it describes, but never the project's whole test suite.
  In the real trial, with a guide on running the tests to keep, it ran the suite once with
  `cargo test` and queued it again with the launcher the project's checks had moved to: some
  thirty minutes on the one desktop the tickets' own checks need.
- Besides `dk document`, closing an epic writes a documentation run, and so does the night
  shift when the documentation is five days old and the project changed since outside
  `docs/`; both do nothing where nobody documents, and leave an unfinished run alone. How
  old it is comes from Git, so DevKit still keeps no clock. A run that finds nothing to
  change leaves no trace in Git, so the night shift asks again the next night: accepted
  until it is seen to happen. `upkeep` is a fifth composer: with audits and documentation
  runs `orders` had reached its 300 lines.
- The page of `dk web` lists the reports of the audits apart, under *Audits*, by the day
  each was made and the latest first, and no longer among the documents. The user asked
  for it: after three nights a real project had nine reports in one alphabetical list among
  its other documents. The day is read from the name `jobs` gives a report, so the name is
  still decided in one place; a file in `docs/audits/` without a day stays a document.
- What an agent is told is kept short by its tests: under 150 to 300 words for those who
  take a job, under 450 for the Principal, whose two briefs carry the whole list of commands
  and what it may decide. Theirs was 300 until naming one more option left no room to say
  when to use it, and 400 until `move` made it 413: the user chose more room over
  sentences cut so short that their meaning could be lost. The verifier's went from 200
  to 300 for the same reason: with behaviour tests it was already 232, unchecked.
  The limit is there so that a rule learned in a trial replaces a weaker one
  or becomes the program's work, not one more sentence; raising it is the user's decision.
- What agents write has a fixed form, kept by the program and not by a model: a ticket
  says `Wanted:`, `Acceptance criteria:` and `Out of scope:`, an epic `Goal:`, `Includes:`
  and `Excludes:` (`dk epic NAME --spec ...`, which also replaces what was said). `dk`
  refuses an agent a text that lacks a part, has one empty or out of order, and lays out
  what it accepts with each heading on a line of its own; an agent must describe an epic
  before writing tickets for it. An agent that rewrote the Principal's drafts was
  considered and left out: it would know less than the Principal and could change what the
  user had agreed. The user, typing by hand, writes as they like, and so does whoever
  proposes a ticket.
- A verifier is told that a rejection names all that must change, not the first fault
  found, both for the work and for the behaviour tests. On a real project one ticket had
  its scenarios refused six times and its work four, each time for one or two new faults,
  some already there the time before: every rejection of the work cost an hour of coding,
  ten minutes of checks and ten of review, and the ticket took a working day.
- An auditor proposes two tickets at most, where it was five, and asks in none for what
  holds only on the computer it measured on. On a real project seventeen audits proposed
  41 tickets, of which the user gave up 16; and one asked for stalls "under about 100 ms"
  as measured there, so a ticket lost a round, and its rows their pressed look, to 110 ms
  that a graphics driver spends once whatever the product does.
- A proposal is accepted only inside an epic, and `dk move N --epic NAME` or `--no-epic`
  puts it in one or takes it out; the user and the Principal may, no other agent, and only
  a proposal is moved. The user asked for it: an auditor proposes outside every epic, and
  the whole test suite is to run when an epic is closed, which a ticket outside every epic
  would never meet. For the same reason `dk add` refuses a ticket that names no epic:
  it starts at once, and `move` could not put it in one later.
- A verifier is told to run no behaviour test: the program has run them. The user saw the
  verifiers of real projects run the scenarios again, although told the checks had passed.
- No ticket has the project's whole test suite run on its work. After the coder the
  program runs `[checks]`, meant for the build and the unit tests, and `[checks.behaviour]`
  with the `.feature` files of that ticket alone, put where the command says `{features}`;
  a ticket that takes no behaviour tests skips the second. The whole suite, `[checks.epic]`,
  is run when an epic is closed. The user asked for it: on real projects the suite took
  from fifteen minutes to hours and was run on every ticket. The price is known and
  accepted: a ticket can break a scenario of an earlier one, and it shows only when the
  epic is closed. A list named `behaviour` under `[checks]` is still one check of every
  ticket, as projects written before have it.
- Closing an epic is carried like a ticket where the project has a whole test suite:
  `dk close` writes `Close EPIC` in the epic, with a process of one step, `suite`. The suite
  is run in a fresh copy of the project as it is then; if it passes the epic is closed
  and documented. If it fails the program writes a ticket in the epic with what failed,
  which takes no behaviour tests and goes to a coder without the user accepting it, since
  the epic cannot close without it; the run waits for that ticket and is done again once
  it is merged. The copy of a run that failed is kept until the next run, and the
  ticket says where it is: a real suite named only the log of the group that failed, a
  file in a copy already thrown away, and the coder ran the group again to learn which
  test it was. It is a job and not the command's own work because the suite can take an
  hour, the Principal's tool cuts a command off at ten minutes, and the board should show
  it. A project without `[checks.epic]` closes an epic at once, as before.
- A closed epic has its lessons drawn, where the project has an auditor: `Lessons of EPIC`,
  written once the epic is closed, so closing takes no longer. It names the epic's tickets
  where work was rejected or an agent was blocked or had to ask, and is not written when
  there are none. The auditor reads them (`dk show N`) and writes three lessons at most, or
  none, each one line of `docs/lessons.md` ending with the tickets it comes from; nothing
  else it leaves is kept. A verifier then checks facts, not taste: that each lesson
  happened on the tickets it names, says what to do concretely, holds for later tickets and
  neither repeats nor contradicts `AGENTS.md`. The user is not asked: whoever follows a
  lesson judges it better than they would, and a wrong one is a line they can delete. The
  file may hold 300 words, which the program counts, so a new lesson in a full file takes
  the place of an old one; coders and verifiers are told to read it first, once it is
  there. The auditor writes them because it neither made the mistakes nor rejected them.
- Claude agents are started with their own notes off (`CLAUDE_CODE_DISABLE_AUTO_MEMORY`).
  On a real project a verifier's notes had grown to 13,500 words nobody had read, and from a
  habit written there it broke the code by hand 47 times on one ticket. The lessons are the
  one memory a project keeps: checked, short and in Git. Asked with the switch on, a real
  Claude said it had no folder for notes; without it, it named one.
- A verifier is told, where the project has a documenter, that `docs/technical/` and
  `docs/howto/` are the documenter's to bring up to date, and to reject nothing over what
  they say. On a real project one sent a ticket back to its coder for five guides that
  still described the sign-in form as it was before that ticket, which the documenter
  rewrites when the epic closes. The documents lag behind the code until then: accepted.
- A job of which only some paths are kept (lessons, documentation, an audit's report) ends
  an update left to resolve with what its agent made of those paths. On a real project four
  epics had their lessons drawn at once; each added to the one file, so the later ones
  collided at `keep`. The auditor resolved it, but throwing away the rest of what it left
  also forgot that the project's changes had been taken in: the verifier was shown other
  epics' lessons as added by this one, and the same collision came back at every `keep`.
- `dk trust "EPIC"` has the behaviour tests of that epic's tickets go on to the coder once
  a verifier has approved them; `--withdraw` ends it, and `dk trust` alone lists the trusted
  epics. The page has a button for both beside each open epic, for whoever has the key. The user wanted an epic whose tickets they had read to be built overnight, and the
  wait for approval was the one stop every ticket made. It is per epic, so that a delicate
  one still passes by the user; only the user gives it, since an agent that could would be
  approving in the user's name; and without a verifier the ticket still waits, since nobody
  would have read the tests. The Principal was not made the one who approves: it wrote the
  ticket, and its yes would be a model's call that checks nothing new.

## Deliberately left out

Beads, backups and retention, several projects in one database, a separate watcher process
for Git, per-role credentials, resuming a job that was cut off or failed (only one that
stopped to ask is picked up again), writing or editing tickets, epics and behaviour tests
from the web page.
