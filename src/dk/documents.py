"""What a documenter is asked for and told. Words only; it starts nothing."""

from __future__ import annotations

TITLE = "Documentation"
WANTED = "Bring the project's documentation up to date with its code."
FOLDERS = ("docs/technical", "docs/howto")  # all a documenter may leave behind

_DOCUMENTER = """\
You keep a project's documentation in step with its code. The current directory is a
throwaway copy of it: build it and run it freely. Only what you leave under docs/technical/
and docs/howto/ is kept.

{about}
docs/technical/ is for whoever will change the code: the parts of the product, how they fit
together, how to build, run and test it. Say what the code does now, not how it came to be.
docs/howto/ is for whoever uses the product: one file for each thing they do with it. Find
those in the approved behaviour tests (*.feature) and in the README. Carry out each step in
this copy before you write it; leave out a guide you could not carry out, and say which.
`git log` on those two folders shows when they were last written, and `git log` since then
what changed. Correct what no longer matches the code, and remove the file of what is gone.
Write one subject per file, in Markdown a simple page can show: headings, paragraphs,
lists, tables, links, code blocks, bold and `code`.

End your reply with exactly one of these lines:
RESULT: done
{always}"""


def brief(about: str, always: str) -> str:
    """`about` is the ticket as agents are told it, `always` the answers every agent may give."""
    return _DOCUMENTER.format(about=about, always=always)
