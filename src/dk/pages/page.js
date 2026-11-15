// The page of `dk web`: it asks for data every two seconds and draws it. With the key that
// `dk web` showed the user, it also passes on what they decide about a ticket.
const app = document.getElementById("app");
const where = document.getElementById("where");
const fresh = document.getElementById("fresh");
const folded = new Map(); // epics the reader opened or closed by hand
const NAMES = { stopped: "needs you", proposed: "proposed", held: "waiting", ticket: "in progress",
  done: "done", cancelled: "cancelled" };
const notes = new Map(); // what the reader is writing about each ticket, kept while it redraws
let drawn = "";
let told = null; // the answer to the last thing the reader asked for
let key = "";

// The address `dk web` gives ends in the key; it is kept in this browser and taken out of
// sight. The page may already be open when that address is: then nothing loads again.
function keyed() {
  const given = location.hash.startsWith("#/") ? "" : location.hash.slice(1);
  if (given) history.replaceState(null, "", location.pathname);
  try {
    if (given) localStorage.setItem("key", given);
    key = localStorage.getItem("key") || "";
  } catch { key = given || key; }
  drawn = "";
}
keyed();

function h(tag, attrs, ...children) {
  const node = document.createElement(tag);
  for (const [name, value] of Object.entries(attrs || {})) {
    if (value !== false && value !== null) node.setAttribute(name, value === true ? "" : value);
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child.nodeType ? child : document.createTextNode(String(child)));
  }
  return node;
}

const link = (number) => h("a", { href: `#/ticket/${number}` }, `#${number}`);
const state = (ticket) => h("span", { class: `state ${ticket.kind}` },
  ticket.kind === "ticket" && !ticket.worker ? "queued" : NAMES[ticket.kind]);
const listed = (numbers) => numbers.flatMap((number, at) => [at ? ", " : "", link(number)]);

// Text as it was written, with a line that is only a heading ("Wanted:") set apart.
const prose = (text) => text.trim().split("\n").map((line) =>
  h("div", { class: /^[A-Z][A-Za-z ]{1,30}:$/.test(line.trim()) ? "label" : false }, line || "\u00a0"));

function extra(ticket) {
  if (ticket.worker) return `${ticket.worker} since ${ticket.since.slice(11)}`;
  if (ticket.waits.length) return `waits for ${ticket.waits.map((n) => `#${n}`).join(", ")}`;
  return ticket.attempts ? `${ticket.attempts} attempt${ticket.attempts > 1 ? "s" : ""}` : "";
}

function row(ticket) {
  const step = ["done", "cancelled", "proposed"].includes(ticket.kind) ? "" : ` at ${ticket.step}`;
  return h("a", { class: "row", href: `#/ticket/${ticket.id}` },
    h("span", { class: "id" }, `#${ticket.id}`), state(ticket),
    h("span", {}, ticket.title, h("span", { class: "extra" }, step)),
    h("span", { class: "extra" }, extra(ticket)));
}

function epic(one) {
  const total = one.tickets.filter((ticket) => ticket.kind !== "cancelled").length;
  const open = folded.has(one.name) ? folded.get(one.name) : !one.closed && one.done < total;
  const card = h("details", { class: "epic card", open },
    h("summary", {},
      h("span", { class: "name" }, one.name || "Without an epic"),
      one.closed && h("span", { class: "chip" }, "closed"),
      one.follows.map((name) => h("span", { class: "chip" }, `after ${name}`)),
      h("span", { class: "count" }, `${one.done} of ${total} done`),
      h("span", { class: "bar" }, h("i", { style: `width:${total ? (100 * one.done) / total : 0}%` }))),
    one.description && h("div", { class: "about" }, prose(one.description)),
    one.tickets.map(row));
  card.addEventListener("toggle", () => folded.set(one.name, card.open));
  return card;
}

function board(data) {
  const tickets = data.epics.flatMap((one) => one.tickets);
  const titles = new Map(tickets.map((ticket) => [ticket.id, ticket.title]));
  const yours = ["stopped", "proposed"].flatMap((kind) => tickets.filter((ticket) => ticket.kind === kind));
  where.textContent = `${tickets.length} tickets, ${yours.length} waiting for you`;
  return [
    h("h2", {}, "Needs you"),
    yours.length ? yours.map((ticket) => h("div", { class: `needs card of-${ticket.kind}` },
      h("div", {}, link(ticket.id), " ", ticket.title, " ", state(ticket)),
      h("div", { class: "why" }, ticket.note || "A proposed ticket: accept it or turn it down.")))
      : h("div", { class: "empty card" }, "Nothing is waiting for you."),
    h("h2", {}, "Agents"),
    h("div", { class: "agents" }, data.agents.map((agent) =>
      h("div", { class: `agent card ${agent.ticket ? "busy" : ""}` },
        h("div", { class: "name" }, agent.name),
        h("div", { class: "doing" }, agent.ticket
          ? [link(agent.ticket), ` ${titles.get(agent.ticket) || ""}, since ${agent.since.slice(11)}`]
          : "free"),
        agent.spent && h("div", { class: "spent" }, agent.spent)))),
    h("h2", {}, "Epics and tickets"),
    data.epics.length ? data.epics.map(epic) : h("div", { class: "empty card" }, "No tickets yet."),
  ];
}

function gherkin(text) {
  const kinds = [
    [/^\s*(Feature|Rule|Background|Examples|Scenarios)\b/, "head"],
    [/^\s*(Scenario Outline|Scenario Template|Scenario|Example)\b/, "head scenario"],
    [/^\s*[#@]/, "note"],
    [/^\s*\|/, "cells"],
  ];
  return h("pre", { class: "gherkin" }, text.replace(/\n$/, "").split("\n").map((line) => {
    const kind = kinds.find(([shape]) => shape.test(line));
    const step = /^(\s*)(Given|When|Then|And|But|\*)(\s.*)$/.exec(line);
    if (step) return h("div", {}, step[1], h("span", { class: "step" }, step[2]), step[3]);
    return h("div", { class: kind ? kind[1] : false }, line);
  }));
}

async function order(asked) {
  const answer = await fetch("api/order", { method: "POST", body: JSON.stringify(asked),
    headers: { "Content-Type": "application/json", "X-Key": key } });
  const said = await answer.json();
  told = { ticket: asked.ticket, text: said.said || said.error, bad: !answer.ok };
  if (answer.ok) notes.delete(asked.ticket);
  if (answer.status === 403) key = "";
  drawn = "";
  look();
}

const button = (words, kind, asked, sure) => {
  const one = h("button", { class: kind, type: "button" }, words);
  one.addEventListener("click", () => {
    if (!sure || confirm(sure)) order({ ...asked, note: notes.get(asked.ticket) || "" });
  });
  return one;
};

// What the reader can decide about this ticket now, as the commands of the same names would.
function word(data) {
  const ticket = data.id;
  const over = ["done", "cancelled"].includes(data.kind);
  const said = told && told.ticket === ticket
    && h("div", { class: told.bad ? "told bad" : "told" }, told.text);
  if (over) return said ? [h("h2", {}, "Your word"), h("div", { class: "word card" }, said)] : [];
  if (!key) {
    return [h("h2", {}, "Your word"), h("div", { class: "word card" }, said, h("div", { class: "hint" },
      "To decide from here, open this page once with the second address `dk web` printed ",
      "when it started: the one that ends in your key."))];
  }
  const note = h("textarea", { rows: 3, placeholder: "A note for the agents (needed to send back)" });
  note.value = notes.get(ticket) || "";
  note.addEventListener("input", () => notes.set(ticket, note.value));
  const give = button("Give up this ticket", "quiet", { do: "cancel", ticket },
    `Give up #${ticket}? Its unmerged work is thrown away.`);
  const can = data.kind === "proposed" ? [
    button("Accept", "main", { do: "approve", ticket }),
    button("Accept, no behaviour tests", "", { do: "approve", ticket, tests: false }),
    button("Turn down", "", { do: "reject", ticket }),
  ] : data.approval ? [
    button("Approve the behaviour tests", "main", { do: "approve", ticket }),
    button("Send them back", "", { do: "reject", ticket }),
  ] : data.kind === "stopped" ? [button("Send it on with this answer", "main", { do: "retry", ticket })]
    : [];
  return [h("h2", {}, "Your word"),
    h("div", { class: "word card" }, said, can.length > 0 && note, h("div", { class: "buttons" }, can, give))];
}

function ticket(data) {
  where.textContent = data.epic || "Without an epic";
  return [
    h("div", { class: "title-line" }, h("h1", {}, `#${data.id} ${data.title}`), state(data)),
    h("div", { class: "meta" },
      !["done", "cancelled", "proposed"].includes(data.kind) && h("span", {}, `at ${data.step}`),
      data.attempts > 0 && h("span", {}, `${data.attempts} attempt${data.attempts > 1 ? "s" : ""}`),
      data.worker && h("span", {}, `${data.worker} since ${data.since.slice(11)}`),
      data.follows.length > 0 && h("span", {}, "after ", listed(data.follows)),
      data.waits.length > 0 && h("span", {}, "waits for ", listed(data.waits))),
    data.note && [h("h2", {}, "Why it stopped"), h("div", { class: "say card" }, data.note)],
    h("h2", {}, "What is wanted"),
    h("div", { class: "block card" }, prose(data.spec)),
    h("h2", {}, data.approval ? "Behaviour tests waiting for your approval" : "Behaviour tests"),
    data.tests.length ? data.tests.map((file) => h("div", { class: "file card" },
      h("div", { class: "path" }, file.name), gherkin(file.text)))
      : h("div", { class: "empty card" }, "This ticket has no behaviour tests."),
    word(data),
    h("h2", {}, "What happened"),
    h("ul", { class: "history card" }, data.history.map((line) =>
      h("li", {}, h("time", {}, line.slice(0, 19)), h("span", {}, line.slice(21))))),
  ];
}

async function look() {
  const number = /^#\/ticket\/(\d+)$/.exec(location.hash);
  const what = number ? `ticket/${number[1]}` : "board";
  try {
    const answer = await fetch(`api/${what}`);
    const text = await answer.text();
    fresh.className = "";
    fresh.textContent = `up to date at ${new Date().toLocaleTimeString()}`;
    if (what + text === drawn) return;
    drawn = what + text;
    const data = JSON.parse(text);
    app.replaceChildren(...(answer.ok ? (number ? ticket(data) : board(data))
      : [h("div", { class: "empty card" }, data.error)]).flat(3).filter(Boolean));
  } catch {
    fresh.className = "lost";
    fresh.textContent = "dk web is not answering";
  }
}

addEventListener("hashchange", () => { keyed(); scrollTo(0, 0); look(); });
setInterval(look, 2000);
look();
