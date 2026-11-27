"""The page of `dk web` shows the project's documents: Markdown turned into what a browser
draws, by the page's own small reader. Tried here without a browser, with Node."""

from __future__ import annotations

import html
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

READER = Path(__file__).parent.parent / "src" / "dk" / "pages" / "markdown.js"
ASK = (
    "const { markdown } = require(process.argv[1]);"
    "const [text, path] = JSON.parse(require('fs').readFileSync(0, 'utf8'));"
    "console.log(JSON.stringify(markdown(text, path)));"
)
pytestmark = pytest.mark.skipif(
    not shutil.which("node"), reason="needs Node to run the page's code"
)


def _drawn(node: Any) -> str:
    if isinstance(node, str):
        return html.escape(node, quote=False)
    attrs = "".join(f' {name}="{value}"' for name, value in sorted(node["attrs"].items()))
    return f"<{node['tag']}{attrs}>{''.join(map(_drawn, node['children']))}</{node['tag']}>"


def shown(text: str, path: str = "docs/howto/greet.md") -> str:
    """What the reader would have the browser draw for a document, written as HTML."""
    asked = json.dumps([text, path])
    done = subprocess.run(
        ["node", "-e", ASK, str(READER)], input=asked, capture_output=True, text=True, check=True
    )
    return "".join(map(_drawn, json.loads(done.stdout)))


def test_headings_and_paragraphs_with_their_emphasis() -> None:
    text = "# Sign in\n\nPress **Sign in** or *wait*,\nthen run `dk web`.\n\n### Later\n"

    assert shown(text) == (
        "<h1>Sign in</h1>"
        "<p>Press <strong>Sign in</strong> or <em>wait</em>, then run <code>dk web</code>.</p>"
        "<h3>Later</h3>"
    )


def test_code_is_shown_as_it_was_written() -> None:
    text = "Run:\n\n```sh\ncargo run -- --help\n# not a heading\n  **not bold**\n```\nDone."

    assert shown(text) == (
        "<p>Run:</p>"
        "<pre><code>cargo run -- --help\n# not a heading\n  **not bold**</code></pre>"
        "<p>Done.</p>"
    )


def test_lists_with_lines_that_go_on_and_lists_inside_them() -> None:
    text = "- one\n  goes on\n- two\n  - inner\n  - other\n- three\n"

    assert shown(text) == (
        "<ul><li>one goes on</li><li>two<ul><li>inner</li><li>other</li></ul></li>"
        "<li>three</li></ul>"
    )


def test_numbered_steps_stay_one_list_across_empty_lines() -> None:
    text = "1. Open the window.\n\n   It shows the form.\n\n2. Press **Enter**.\n\nAfter.\n"

    assert shown(text) == (
        "<ol><li><p>Open the window.</p><p>It shows the form.</p></li>"
        "<li>Press <strong>Enter</strong>.</li></ol><p>After.</p>"
    )


def test_tables() -> None:
    text = "| Module | Does |\n| --- | :-- |\n| `session` | owns the **session** |\n| a | |\n"

    assert shown(text) == (
        "<table><thead><tr><th>Module</th><th>Does</th></tr></thead><tbody>"
        "<tr><td><code>session</code></td><td>owns the <strong>session</strong></td></tr>"
        "<tr><td>a</td><td></td></tr></tbody></table>"
    )


def test_quotes_and_rules() -> None:
    assert shown("> Careful:\n> it is **slow**.\n\n---\n\nAfter.") == (
        "<blockquote><p>Careful: it is <strong>slow</strong>.</p></blockquote>"
        "<hr></hr><p>After.</p>"
    )


def test_a_link_to_another_document_opens_it_in_the_page() -> None:
    text = "See [Parts](../technical/parts.md#modules) and [Log out](log-out.md)."

    assert shown(text, "docs/howto/greet.md") == (
        '<p>See <a href="#/doc/docs/technical/parts.md">Parts</a> and '
        '<a href="#/doc/docs/howto/log-out.md">Log out</a>.</p>'
    )


def test_a_link_to_the_web_opens_apart() -> None:
    assert shown("[Vaultwarden](https://example.org/a_b)") == (
        '<p><a href="https://example.org/a_b" rel="noopener" target="_blank">Vaultwarden</a></p>'
    )


@pytest.mark.parametrize(
    "href",
    [
        "javascript:alert(1)",
        "JavaScript:alert(1)",
        "data:text/html,x",
        "../src/main.rs",
        "/etc",
        "javascript:a.md",
        "/etc/a.md",
    ],
)
def test_a_link_the_page_cannot_follow_is_left_as_words(href: str) -> None:
    assert shown(f"[here]({href})") == "<p>here</p>"


def test_what_looks_like_html_stays_text() -> None:
    drawn = shown("<script>alert(1)</script> and <b>bold</b>")

    assert drawn == "<p>&lt;script&gt;alert(1)&lt;/script&gt; and &lt;b&gt;bold&lt;/b&gt;</p>"


def test_names_and_sums_are_not_emphasis() -> None:
    text = "Set `my_var`, then use session_boundary_test and 2 * 3 * 4."

    assert shown(text) == (
        "<p>Set <code>my_var</code>, then use session_boundary_test and 2 * 3 * 4.</p>"
    )


def test_an_empty_document_draws_nothing() -> None:
    assert shown("") == "" and shown("\n\n  \n") == ""


def test_what_the_document_ends_in_is_drawn_whole() -> None:
    assert shown("Run:\n```\na\nb") == "<p>Run:</p><pre><code>a\nb</code></pre>"
    assert shown("> a\n> b") == "<blockquote><p>a b</p></blockquote>"
    assert shown("| A |\n| - |\n| b |") == (
        "<table><thead><tr><th>A</th></tr></thead><tbody><tr><td>b</td></tr></tbody></table>"
    )


def test_code_under_a_list_item_keeps_its_own_indent() -> None:
    assert shown("- Run:\n\n  ```\n    deep\n  ```\n") == (
        "<ul><li>Run:<pre><code>  deep</code></pre></li></ul>"
    )


def test_a_bar_or_a_line_of_dashes_alone_makes_no_table() -> None:
    assert shown("a | b\n\nTitle\n---\n") == "<p>a | b</p><p>Title</p><hr></hr>"
