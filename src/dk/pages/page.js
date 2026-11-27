// The page of `dk web`: it asks for data every two seconds and draws it. With the key that
// `dk web` showed the user, it also passes on what they decide about a ticket.
const app = document.getElementById("app");
const where = document.getElementById("where");
const fresh = document.getElementById("fresh");
const folded = new Map(); // epics the reader opened or closed by hand
const NAMES = { stopped: "needs you", proposed: "proposed", held: "waiting", ticket: "in progress",
  done: "done", cancelled: "cancelled" };
const notes = new Map(); // what the reader is writing about each ticket, kept while it redraws
const drafts = new Map(); // the tickets the reader is rewriting: each one's title and text so far
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

const drawable = (child) => child !== null && child !== undefined && child !== false;

function h(tag, attrs, ...children) {
  const node = document.createElement(tag);
  for (const [name, value] of Object.entries(attrs || {})) {
    if (value !== false && value !== null) node.setAttribute(name, value === true ? "" : value);
  }
  for (const child of children.flat().filter(drawable)) {
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

// Have an epic's behaviour tests go on to the coder unapproved, or wait for the reader again.
function trusting(one) {
  const words = one.trusted ? "Withdraw trust" : "Trust";
  const sure = `Trust ${one.name}? The behaviour tests of its tickets will go on to the coder `
    + "once a verifier approves them, without your approval.";
  const press = h("button", { class: "small", type: "button" }, words);
  press.addEventListener("click", async (event) => {
    event.preventDefault(); // it sits in the line that opens and closes the epic
    if (!one.trusted && !confirm(sure)) return;
    await order({ do: "trust", epic: one.name, given: !one.trusted });
    if (told.bad) alert(told.text);
  });
  return press;
}

// The line that opens and closes an epic: its name, what is so of it, and how far it is.
function heading(one, total) {
  return h("summary", {},
    h("span", { class: "name" }, one.name || "Without an epic"),
    one.closed && h("span", { class: "chip" }, "closed"),
    one.trusted && h("span", { class: "chip" }, "trusted"),
    key && one.name && !one.closed && trusting(one),
    one.follows.map((name) => h("span", { class: "chip" }, `after ${name}`)),
    h("span", { class: "count" }, `${one.done} of ${total} done`),
    h("span", { class: "bar" }, h("i", { style: `width:${total ? (100 * one.done) / total : 0}%` })));
}

function epic(one) {
  const total = one.tickets.filter((ticket) => ticket.kind !== "cancelled").length;
  const open = folded.has(one.name) ? folded.get(one.name) : !one.closed && one.done < total;
  const card = h("details", { class: "epic card", open }, heading(one, total),
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

// The documents of the project, by the folder of `docs` each is in.
function documents(data) {
  where.textContent = `${data.files.length} documents`;
  const folders = new Map();
  for (const path of data.files) {
    const [, folder, name] = /^docs\/(?:(.*)\/)?([^/]+)\.md$/.exec(path);
    folders.set(folder || "", [...(folders.get(folder || "") || []), { path, name }]);
  }
  if (!data.files.length) return [h("div", { class: "empty card" }, "This project has no documents under docs/.")];
  return [...folders].map(([folder, files]) => [
    h("h2", {}, folder || "docs"),
    h("div", { class: "card" }, files.map((file) =>
      h("a", { class: "row plain", href: `#/doc/${file.path}` }, file.name))),
  ]);
}

// The reports the audits left, by the day each was made, the latest first.
function audits(data) {
  const reports = data.days.flatMap((day) => day.reports);
  where.textContent = `${reports.length} audit reports`;
  if (!reports.length) return [h("div", { class: "empty card" }, "No audit has left a report yet.")];
  const long = { weekday: "long", day: "numeric", month: "long", year: "numeric" };
  return data.days.map((day) => [
    h("h2", {}, new Date(`${day.day}T12:00`).toLocaleDateString(undefined, long)),
    h("div", { class: "card" }, day.reports.map((one) =>
      h("a", { class: "row plain", href: `#/doc/${one.path}` }, one.name))),
  ]);
}

const built = (node) => (typeof node === "string" ? node
  : h(node.tag, node.attrs, node.children.map(built)));

function documentPage(data) {
  where.textContent = data.path;
  return [h("article", { class: "doc card" }, markdown(data.text, data.path).map(built))];
}

// What the address asks for, and how to draw the answer.
function asked() {
  const number = /^#\/ticket\/(\d+)$/.exec(location.hash);
  const file = /^#\/doc\/(.+)$/.exec(location.hash);
  if (number) return [`ticket/${number[1]}`, ticket];
  if (file) return [`doc/${file[1]}`, documentPage];
  if (location.hash === "#/audits") return ["audits", audits];
  return location.hash === "#/docs" ? ["docs", documents] : ["board", board];
}

async function look() {
  const [what, draw] = asked();
  try {
    const answer = await fetch(`api/${what}`);
    const text = await answer.text();
    fresh.className = "";
    fresh.textContent = `up to date at ${new Date().toLocaleTimeString()}`;
    if (what + text === drawn) return;
    drawn = what + text;
    const data = JSON.parse(text);
    app.replaceChildren(...(answer.ok ? draw(data)
      : [h("div", { class: "empty card" }, data.error)]).flat(3).filter(Boolean));
  } catch {
    fresh.className = "lost";
    fresh.textContent = "dk web is not answering";
  }
}

addEventListener("hashchange", () => { keyed(); scrollTo(0, 0); look(); });
setInterval(look, 2000);
look();
