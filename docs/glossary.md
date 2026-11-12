# Glossary

- **Agent** — a program driven by a language model that is given one job at a time.
- **Role** — what an agent is for: coder, verifier, QA, test-writer, Principal.
- **Epic** — a large piece of work agreed between the user and the Principal.
- **Ticket** — one unit of work: what is wanted and its acceptance criteria.
- **Process** — the ordered list of steps every ticket goes through.
- **Step** — one stage of the process, carried out by an agent, by the program or by the user.
- **Outcome** — how a step ended: passed, failed (the work goes back to be redone), lost (the step gave nothing usable and is done again) or stopped (the user decides).
- **Attempt** — one try at a ticket; a failed or lost outcome uses one up.
- **Stopped** — a ticket that waits at its step for the user: out of attempts, blocked, a question, or a merge that could not be done. `dk retry` sends it on.
- **Skipped** — a step whose role no agent has; the history records it.
- **Verdict** — a reviewer's answer: approved or rejected with what must change.
- **Brief** — the instructions an agent receives for one job.
- **Answer** — the last line of an agent's reply: done, blocked or question.
- **Copy** — a ticket's own working copy of the project (a Git worktree on branch `ticket/<n>`).
- **Checks** — the project's own commands that must succeed; run by the program, never trusted from an agent.
- **Behaviour test** — a Gherkin scenario written before the code and approved by the user.
- **Director** — the piece that decides what happens next to each ticket.
- **Clash** — a ticket's work collides with work merged while it was in progress; the coder gets the files to resolve.
