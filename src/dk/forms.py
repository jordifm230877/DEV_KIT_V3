"""The headings a ticket and an epic are written under, and the user's own editor for a
text too long for a command line. It knows no ticket list."""

from __future__ import annotations

import os
import re
import shlex
import subprocess
import tempfile
from pathlib import Path

TICKET = ("Wanted:", "Acceptance criteria:", "Out of scope:")
EPIC = ("Goal:", "Includes:", "Excludes:")


def formed(text: str, headings: tuple[str, ...], agent: str) -> str:
    """A text laid out under the headings every such text has. The user writes as they
    like; an agent (`agent` names it) is refused a text that lacks a part."""
    if not agent:
        return text
    first, *rest = re.split("(" + "|".join(map(re.escape, headings)) + ")", text)
    said = [body.strip() for body in rest[1::2]]
    if first.strip() or tuple(rest[::2]) != headings or not all(said):
        raise LookupError(f"write it as `{form(headings)}`: each once, in this order, none empty")
    return "\n\n".join(f"{heading}\n{body}" for heading, body in zip(headings, said, strict=True))


def form(headings: tuple[str, ...]) -> str:
    return " ".join(f"{heading} ..." for heading in headings)


def write(title: str, text: str) -> tuple[str, str]:
    """Have the user change a title and a text in their editor ($VISUAL, $EDITOR, else vi),
    as one file whose first line is the title."""
    editor = shlex.split(os.environ.get("VISUAL") or os.environ.get("EDITOR") or "vi")
    with tempfile.TemporaryDirectory() as folder:
        file = Path(folder) / "ticket.md"
        file.write_text(f"{title}\n\n{text}\n")
        if subprocess.run([*editor, str(file)]).returncode:
            raise LookupError("the editor ended with an error; nothing was changed")
        first, _, rest = file.read_text().strip().partition("\n")
    if not rest.strip():
        raise LookupError("a title on the first line, then the text; nothing was changed")
    return first.strip(), rest.strip()
