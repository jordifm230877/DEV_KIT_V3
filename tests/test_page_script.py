"""What the page of `dk web` draws from the data it is given, and what it sends when the
reader presses something. Tried without a browser: Node runs the page's own script against
a stand-in for the browser that only keeps what it is asked to draw."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from test_markdown import _drawn

PAGES = Path(__file__).parent.parent / "src" / "dk" / "pages"
BROWSER = r"""
const fs = require("fs"), vm = require("vm");
const asked = JSON.parse(fs.readFileSync(0, "utf8"));
const out = { orders: [], keys: [], confirms: [], alerts: [] };
const text = (t) => ({ text: String(t), nodeType: 3 });
const node = (tag) => ({ tag, attrs: {}, children: [], heard: {}, nodeType: 1, value: "",
  setAttribute(name, value) { this.attrs[name] = value; },
  append(...more) { this.children.push(...more); },
  replaceChildren(...all) { this.children = all; },
  addEventListener(name, f) { (this.heard[name] ||= []).push(f); },
  set textContent(t) { this.children = [text(t)]; },
  set className(name) { this.attrs.class = name; } });
const ids = {}, kept = new Map(asked.key ? [["key", asked.key]] : []), windows = {};
const storage = (f) => (...all) => {
  if (asked.private) throw new Error("private");
  return f(...all);
};
const location = { hash: asked.hash || "", pathname: "/" };
const browser = { location, console, markdown: undefined,
  document: { getElementById: (id) => (ids[id] ||= node(id)), createElement: node,
    createTextNode: text },
  history: { replaceState() { location.hash = ""; } },
  localStorage: { getItem: storage((k) => kept.get(k) ?? null),
    setItem: storage((k, v) => kept.set(k, v)) },
  setInterval() {}, scrollTo() {},
  addEventListener(name, f) { (windows[name] ||= []).push(f); },
  confirm: (words) => (out.confirms.push(words), asked.sure !== false),
  alert: (words) => out.alerts.push(words),
  fetch: async (url, sent) => {
    if (asked.down) throw new Error("down");
    if (sent) {
      out.orders.push(JSON.parse(sent.body));
      out.keys.push(sent.headers["X-Key"]);
      const ok = !asked.refused;
      return { ok, status: ok ? 200 : asked.status || 400,
        json: async () => (ok ? { said: "as you say" } : { error: asked.refused }) };
    }
    const data = asked.answers[url];
    return { ok: Boolean(data), text: async () => JSON.stringify(data || { error: "no such" }) };
  } };
const settle = async () => { for (let n = 0; n < 20; n++) await new Promise(setImmediate); };
const all = (one, found = []) => {
  if (one.nodeType === 1) { found.push(one); one.children.forEach((c) => all(c, found)); }
  return found;
};
const words = (one) => (one.nodeType === 3 ? one.text : one.children.map(words).join(""));
const kept_as = (one) => (one.nodeType === 3 ? one.text
  : { tag: one.tag, attrs: { ...one.attrs, ...(one.value && { value: one.value }) },
    children: one.children.map(kept_as) });
(async () => {
  vm.createContext(browser);
  const index = fs.readFileSync(`${process.argv[1]}/index.html`, "utf8");
  for (const [, file] of index.matchAll(/<script src="([^"]+)"/g)) {
    vm.runInContext(fs.readFileSync(`${process.argv[1]}/${file}`, "utf8"), browser);
  }
  await settle();
  for (const [what, value] of asked.does || []) {
    const within = all(ids.app);
    if (what === "write" || what === "title") {
      const box = within.find((one) => one.tag === (what === "write" ? "textarea" : "input"));
      box.value = value;
      box.heard.input.forEach((f) => f());
    } else if (what === "go") {
      location.hash = value;
      windows.hashchange.forEach((f) => f());
    } else {
      const pressed = within.find((one) => one.tag === "button" && words(one) === value);
      if (!pressed) throw new Error(`no button says: ${value}`);
      for (const f of pressed.heard.click) await f({ preventDefault() {} });
    }
    await settle();
  }
  console.log(JSON.stringify({ ...out, app: ids.app.children.map(kept_as),
    where: words(ids.where), fresh: `${ids.fresh.attrs.class}: ${words(ids.fresh)}` }));
})();
"""
pytestmark = pytest.mark.skipif(
    not shutil.which("node"), reason="needs Node to run the page's code"
)
TICKET = {
    "id": 7,
    "title": "Greet",
    "kind": "ticket",
    "step": "code",
    "attempts": 0,
    "behaviour": True,
    "worker": "",
    "since": "",
    "follows": [],
    "waits": [],
    "note": "",
    "epic": "Manners",
    "spec": "Wanted:\nSay hello.",
    "editable": False,
    "approval": False,
    "tests": [],
    "history": ["2026-11-27 10:00:00  written"],
}
EPIC = {
    "name": "Manners",
    "closed": False,
    "trusted": False,
    "follows": [],
    "done": 1,
    "description": "",
    "tickets": [
        {**TICKET, "id": 1, "kind": "done", "step": "done"},
        {**TICKET, "id": 2, "kind": "cancelled", "step": "cancelled"},
        TICKET,
    ],
}


def page(hash_: str, answers: dict[str, object], **more: object) -> dict[str, Any]:
    """What the page ends up showing at this address, as HTML under `app`, with what it
    sent meanwhile."""
    asked = json.dumps({"hash": hash_, "answers": answers, **more})
    done = subprocess.run(
        ["node", "-e", BROWSER, str(PAGES)], input=asked, capture_output=True, text=True, check=True
    )
    seen: dict[str, Any] = json.loads(done.stdout)
    return {**seen, "app": "".join(map(_drawn, seen["app"]))}


def ticket(**facts: object) -> dict[str, Any]:
    return page("#/ticket/7", {"api/ticket/7": {**TICKET, **facts}}, key="k")


def buttons(shown: str) -> list[str]:
    return [part.split("<")[0] for part in shown.split('type="button">')[1:]]


def test_a_ticket_shows_what_it_is_and_what_happened() -> None:
    shown = ticket(attempts=2, worker="coder-1", since="2026-11-27 10:05:00", waits=[3, 4])

    assert shown["where"] == "Manners"
    assert '<h1>#7 Greet</h1><span class="state ticket">in progress</span>' in shown["app"]
    assert (
        '<div class="meta"><span>at code</span><span>2 attempts</span>'
        "<span>coder-1 since 10:05:00</span>"
        '<span>waits for <a href="#/ticket/3">#3</a>, <a href="#/ticket/4">#4</a></span></div>'
    ) in shown["app"]
    assert '<div class="label">Wanted:</div><div>Say hello.</div>' in shown["app"]
    assert "This ticket has no behaviour tests." in shown["app"]
    assert "<li><time>2026-11-27 10:00:00</time><span>written</span></li>" in shown["app"]
    assert "Why it stopped" not in shown["app"]


def test_a_ticket_says_little_when_there_is_little_to_say() -> None:
    shown = ticket(kind="done", step="done", attempts=1, behaviour=False, follows=[2])["app"]
    waiting = ticket(kind="held", waits=[3])["app"]

    assert (
        '<div class="meta"><span>1 attempt</span><span>no behaviour tests</span>'
        '<span>after <a href="#/ticket/2">#2</a></span></div>'
    ) in shown
    assert '<span class="state done">done</span>' in shown
    assert (
        '<div class="meta"><span>at code</span>'
        '<span>waits for <a href="#/ticket/3">#3</a></span></div>'
    ) in waiting


def test_a_stopped_ticket_shows_why_and_its_behaviour_tests() -> None:
    feature = "Feature: Greeting\n  Scenario: Hello\n    Given a guest\n"
    shown = ticket(
        kind="stopped", note="question: which language?", approval=True,
        tests=[{"name": "features/greet.feature", "text": feature}],
    )["app"]  # fmt: skip

    assert '<h2>Why it stopped</h2><div class="say card">question: which language?</div>' in shown
    assert "<h2>Behaviour tests waiting for your approval</h2>" in shown
    assert '<div class="path">features/greet.feature</div><pre class="gherkin">' in shown
    assert '<div class="head scenario">  Scenario: Hello</div>' in shown
    assert '<div class="head">Feature: Greeting</div>' in shown
    assert '<div>    <span class="step">Given</span> a guest</div>' in shown


@pytest.mark.parametrize(
    ("facts", "offered"),
    [
        ({"kind": "ticket"}, ["Pause this ticket", "Give up this ticket"]),
        ({"kind": "held"}, ["Pause this ticket", "Give up this ticket"]),
        ({"kind": "stopped"}, ["Send it on with this answer", "Give up this ticket"]),
        (
            {"kind": "stopped", "approval": True},
            ["Approve the behaviour tests", "Send them back", "Give up this ticket"],
        ),
        (
            {"kind": "proposed"},
            ["Accept", "Accept, no behaviour tests", "Turn down", "Give up this ticket"],
        ),
        ({"kind": "done"}, []),
        ({"kind": "cancelled"}, []),
    ],
)
def test_the_reader_is_offered_what_can_be_decided_now(
    facts: dict[str, object], offered: list[str]
) -> None:
    shown = ticket(**facts)["app"]

    assert buttons(shown) == offered
    assert ("<h2>Your word</h2>" in shown) == bool(offered)
    assert ("<textarea" in shown) == (len(offered) > 2 or facts["kind"] == "stopped")


def test_without_the_key_the_reader_is_told_how_to_decide() -> None:
    shown = page("#/ticket/7", {"api/ticket/7": TICKET})["app"]

    assert buttons(shown) == [] and "the one that ends in your key" in shown


def test_what_the_reader_decides_is_sent_with_their_note() -> None:
    does = [["write", "In Catalan."], ["press", "Send it on with this answer"]]
    shown = page("#/ticket/7", {"api/ticket/7": {**TICKET, "kind": "stopped"}}, key="k", does=does)

    assert shown["orders"] == [{"do": "retry", "ticket": 7, "note": "In Catalan."}]
    assert '<div class="told">as you say</div>' in shown["app"]
    assert shown["confirms"] == []


def test_a_note_that_was_not_taken_is_still_there() -> None:
    does = [["write", "In Catalan."], ["press", "Send it on with this answer"]]
    answers = {"api/ticket/7": {**TICKET, "kind": "stopped"}}

    shown = page("#/ticket/7", answers, key="k", does=does, refused="not now")["app"]

    assert 'value="In Catalan."></textarea>' in shown and '<div class="told bad">not now' in shown


def test_a_proposal_can_be_accepted_without_behaviour_tests() -> None:
    answers = {"api/ticket/7": {**TICKET, "kind": "proposed"}}

    shown = page("#/ticket/7", answers, key="k", does=[["press", "Accept, no behaviour tests"]])

    assert shown["orders"] == [{"do": "approve", "ticket": 7, "tests": False, "note": ""}]


def test_giving_a_ticket_up_is_asked_twice() -> None:
    does = [["press", "Give up this ticket"]]
    answers = {"api/ticket/7": TICKET}

    kept = page("#/ticket/7", answers, key="k", does=does, sure=False)
    gone = page("#/ticket/7", answers, key="k", does=does)

    assert kept["orders"] == [] and kept["confirms"] == gone["confirms"]
    assert gone["confirms"] == ["Give up #7? Its unmerged work is thrown away."]
    assert gone["orders"] == [{"do": "cancel", "ticket": 7, "note": ""}]


def test_what_was_refused_is_said_even_on_a_finished_ticket() -> None:
    does = [["press", "Pause this ticket"]]
    shown = page("#/ticket/7", {"api/ticket/7": TICKET}, key="k", does=does, refused="not now")

    assert '<div class="told bad">not now</div>' in shown["app"]
    assert shown["orders"] == [{"do": "pause", "ticket": 7, "note": ""}]


def test_the_key_comes_with_the_address_and_is_kept() -> None:
    shown = page("#secret", {"api/board": {"epics": [EPIC], "agents": []}})

    assert '<button class="small" type="button">Trust</button>' in shown["app"]


def test_the_board_lists_what_needs_the_reader_the_agents_and_the_epics() -> None:
    stopped = {**TICKET, "id": 3, "kind": "stopped", "note": "question: which?", "attempts": 1}
    proposed = {**TICKET, "id": 4, "kind": "proposed", "title": "Wave"}
    held = {**TICKET, "id": 5, "kind": "held", "waits": [3]}
    busy = {**TICKET, "id": 6, "worker": "coder-1", "since": "2026-11-27 10:05:00"}
    epic = {**EPIC, "tickets": [*EPIC["tickets"], stopped, proposed, held, busy]}  # type: ignore[misc]
    agents = [
        {"name": "coder-1", "ticket": 6, "since": "2026-11-27 10:05:00", "spent": "12k tokens"},
        {"name": "verifier-1", "ticket": 0, "since": "", "spent": ""},
    ]
    shown = page("", {"api/board": {"epics": [epic], "agents": agents}})

    assert shown["where"] == "7 tickets, 2 waiting for you"
    app = shown["app"]
    assert '<div class="why">question: which?</div>' in app
    assert '<div class="why">A proposed ticket: accept it or turn it down.</div>' in app
    assert (
        '<div class="agent card busy"><div class="name">coder-1</div><div class="doing">'
        '<a href="#/ticket/6">#6</a> Greet, since 10:05:00</div>'
        '<div class="spent">12k tokens</div></div>'
    ) in app
    assert '<div class="agent card "><div class="name">verifier-1</div>' in app
    assert '<div class="doing">free</div></div>' in app
    assert '<span class="state ticket">queued</span>' in app
    assert '<span class="extra"> at code</span></span><span class="extra">1 attempt</span>' in app
    assert '<span class="extra">waits for #3</span>' in app
    assert '<span class="extra">coder-1 since 10:05:00</span>' in app
    assert '<span class="state done">done</span><span>Greet<span class="extra"></span>' in app


def test_an_epic_shows_how_far_it_is_and_what_is_said_of_it() -> None:
    epic = {**EPIC, "trusted": True, "follows": ["Basics"], "description": "Goal:\nBe polite."}
    shown = page("", {"api/board": {"epics": [epic], "agents": []}}, key="k")["app"]

    assert '<details class="epic card" open=""><summary><span class="name">Manners</span>' in shown
    assert '<span class="chip">trusted</span>' in shown
    assert '<button class="small" type="button">Withdraw trust</button>' in shown
    assert '<span class="chip">after Basics</span><span class="count">1 of 2 done</span>' in shown
    assert '<span class="bar"><i style="width:50%"></i></span>' in shown
    assert '<div class="about"><div class="label">Goal:</div><div>Be polite.</div></div>' in shown


def test_a_closed_epic_and_tickets_of_none_are_shown_folded_or_named() -> None:
    closed = {**EPIC, "closed": True}
    whole = {**EPIC, "name": "Basics", "done": 3, "tickets": [*EPIC["tickets"], TICKET, TICKET]}  # type: ignore[misc]
    complete = {**EPIC, "name": "Ended", "tickets": EPIC["tickets"][:2]}  # type: ignore[index]
    loose = {**EPIC, "name": "", "done": 0, "tickets": []}
    shown = page(
        "", {"api/board": {"epics": [closed, loose, whole, complete], "agents": []}}, key="k"
    )["app"]

    assert '<details class="epic card"><summary><span class="name">Manners</span>' in shown
    assert '<span class="chip">closed</span><span class="count">1 of 2 done</span>' in shown
    assert '<details class="epic card"><summary><span class="name">Ended</span>' in shown
    assert '<span class="count">3 of 4 done</span><span class="bar"><i style="width:75%">' in shown
    assert (
        '<span class="name">Without an epic</span><span class="count">0 of 0 done</span>' in shown
    )
    assert '<i style="width:0%"></i>' in shown


def test_trusting_an_epic_is_asked_first_and_sent() -> None:
    board = {"api/board": {"epics": [EPIC], "agents": []}}

    shown = page("", board, key="k", does=[["press", "Trust"]])

    assert shown["orders"] == [{"do": "trust", "epic": "Manners", "given": True}]
    assert shown["confirms"][0].startswith("Trust Manners?") and shown["alerts"] == []
    assert page("", board, key="k", does=[["press", "Trust"]], sure=False)["orders"] == []


def test_behaviour_tests_are_drawn_by_what_each_line_is() -> None:
    feature = "@slow\n# why\nFeature: A\n  Scenario Outline: B\n    When <x>\n    | x |\n  free\n"
    shown = ticket(tests=[{"name": "a.feature", "text": feature}])["app"]

    assert '<div class="note">@slow</div><div class="note"># why</div>' in shown
    assert '<div class="head scenario">  Scenario Outline: B</div>' in shown
    assert (
        '<span class="step">When</span> &lt;x&gt;</div><div class="cells">    | x |</div>' in shown
    )
    assert "<div>  free</div></pre>" in shown


def test_only_a_ticket_nobody_worked_on_offers_to_be_rewritten() -> None:
    fresh = {"api/ticket/7": {**TICKET, "editable": True}}

    assert "Edit" in buttons(ticket(editable=True)["app"])
    assert "<div>Say hello.</div></div><h2>Behaviour tests</h2>" in ticket()["app"]
    assert "Edit" not in buttons(page("#/ticket/7", fresh)["app"])


def test_a_ticket_is_rewritten_in_place_and_sent() -> None:
    fresh = {"api/ticket/7": {**TICKET, "editable": True}}
    does = [["press", "Edit"]]
    writes = [["title", " Greet all "], ["write", "Say hello to all.\n"], ["press", "Save"]]

    form = page("#/ticket/7", fresh, key="k", does=does)["app"]
    saved = page("#/ticket/7", fresh, key="k", does=does + writes)

    assert '<input type="text" value="Greet"></input>' in form
    assert 'value="Wanted:\nSay hello."></textarea>' in form
    assert buttons(form)[:2] == ["Save", "Cancel"] and "Edit" not in buttons(form)
    assert saved["orders"] == [
        {"do": "edit", "ticket": 7, "title": "Greet all", "spec": "Say hello to all."}
    ]
    assert "Edit" in buttons(saved["app"]) and '<div class="told">as you say</div>' in saved["app"]


def test_a_rewriting_that_was_refused_or_left_is_not_lost_or_sent() -> None:
    fresh = {"api/ticket/7": {**TICKET, "editable": True}}
    writes = [["press", "Edit"], ["write", "Other."]]

    refused = page(
        "#/ticket/7", fresh, key="k", does=[*writes, ["press", "Save"]], refused="taken"
    )["app"]
    left = page("#/ticket/7", fresh, key="k", does=[*writes, ["press", "Cancel"]])

    assert 'value="Other."></textarea>' in refused and '<div class="told bad">taken' in refused
    assert left["orders"] == [] and "Other." not in left["app"]
    assert '<div class="label">Wanted:</div>' in left["app"]


def test_the_documents_are_listed_by_their_folder() -> None:
    files = ["docs/design.md", "docs/howto/greet.md", "docs/howto/deep/wave.md"]
    shown = page("#/docs", {"api/docs": {"files": files}})
    none = page("#/docs", {"api/docs": {"files": []}})

    assert shown["where"] == "3 documents" and none["where"] == "0 documents"
    assert (
        '<h2>docs</h2><div class="card">'
        '<a class="row plain" href="#/doc/docs/design.md">design</a></div>'
        '<h2>howto</h2><div class="card">'
        '<a class="row plain" href="#/doc/docs/howto/greet.md">greet</a></div>'
        "<h2>howto/deep</h2>"
    ) in shown["app"]
    assert none["app"] == '<div class="empty card">This project has no documents under docs/.</div>'


def test_the_audit_reports_are_listed_by_their_day() -> None:
    one = {"path": "docs/audits/2026-11-27-tests-audit.md", "name": "tests audit"}
    days = [{"day": "2026-11-27", "reports": [one, one]}, {"day": "2025-01-02", "reports": [one]}]
    shown = page("#/audits", {"api/audits": {"days": days}})
    none = page("#/audits", {"api/audits": {"days": []}})

    assert shown["where"] == "3 audit reports"
    first, second = shown["app"].split("<h2>")[1:]
    assert "2026" in first.split("</h2>")[0] and "27" in first.split("</h2>")[0]
    assert "2025" in second.split("</h2>")[0]
    assert first.count('href="#/doc/docs/audits/2026-11-27-tests-audit.md">tests audit</a>') == 2
    assert none["app"] == '<div class="empty card">No audit has left a report yet.</div>'


def test_a_document_is_drawn_from_its_markdown() -> None:
    answers = {"api/doc/docs/howto/a.md": {"path": "docs/howto/a.md", "text": "# A\n\n[B](b.md)"}}
    shown = page("#/doc/docs/howto/a.md", answers)

    assert shown["where"] == "docs/howto/a.md" and shown["fresh"].startswith(": up to date at ")
    assert shown["app"] == (
        '<article class="doc card"><h1>A</h1><p><a href="#/doc/docs/howto/b.md">B</a></p></article>'
    )


def test_what_dk_web_cannot_give_is_said() -> None:
    assert page("#/ticket/9", {})["app"] == '<div class="empty card">no such</div>'
    assert page("#/ticket/7", {}, down=True)["fresh"] == "lost: dk web is not answering"


def test_a_key_that_is_refused_is_forgotten() -> None:
    does = [["press", "Pause this ticket"]]
    shown = page(
        "#/ticket/7", {"api/ticket/7": TICKET}, key="k", does=does, refused="no", status=403
    )["app"]

    assert buttons(shown) == [] and "the one that ends in your key" in shown


def test_the_key_can_be_given_to_a_page_already_open_or_one_that_keeps_nothing() -> None:
    board = {"api/board": {"epics": [EPIC], "agents": []}}

    does = [["go", "#secret"], ["press", "Trust"]]
    later = page("#/docs", {**board, "api/docs": {"files": []}}, does=does)
    private = page("#secret", board, private=True)

    assert later["keys"] == ["secret"] and "Trust" in buttons(private["app"])
