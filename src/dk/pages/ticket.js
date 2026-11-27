// The page of one ticket: what it is, what it asks for, its behaviour tests, and what the
// reader can decide about it. Drawn with what `page.js` holds, which is read after this.

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

const button = (words, kind, asked, sure) => {
  const one = h("button", { class: kind, type: "button" }, words);
  one.addEventListener("click", () => {
    if (!sure || confirm(sure)) order({ ...asked, note: notes.get(asked.ticket) || "" });
  });
  return one;
};

const hint = () => h("div", { class: "hint" },
  "To decide from here, open this page once with the second address `dk web` printed ",
  "when it started: the one that ends in your key.");

// The answers a ticket that waits for the reader can be given, each with the reader's note.
function answers(data) {
  const ticket = data.id;
  if (data.kind === "proposed") {
    return [button("Accept", "main", { do: "approve", ticket }),
      button("Accept, no behaviour tests", "", { do: "approve", ticket, tests: false }),
      button("Turn down", "", { do: "reject", ticket })];
  }
  if (data.approval) {
    return [button("Approve the behaviour tests", "main", { do: "approve", ticket }),
      button("Send them back", "", { do: "reject", ticket })];
  }
  return data.kind === "stopped"
    ? [button("Send it on with this answer", "main", { do: "retry", ticket })] : [];
}

// The answer to what the reader last asked of this ticket, if it was of this one.
const heard = (ticket) => told && told.ticket === ticket
  && h("div", { class: told.bad ? "told bad" : "told" }, told.text);

// What the reader can decide about this ticket now, as the commands of the same names would.
function word(data) {
  const ticket = data.id;
  const over = ["done", "cancelled"].includes(data.kind);
  const said = heard(ticket);
  if (over) return said ? [h("h2", {}, "Your word"), h("div", { class: "word card" }, said)] : [];
  if (!key) return [h("h2", {}, "Your word"), h("div", { class: "word card" }, said, hint())];
  const note = h("textarea", { rows: 3, placeholder: "A note for the agents (needed to send back)" });
  note.value = notes.get(ticket) || "";
  note.addEventListener("input", () => notes.set(ticket, note.value));
  const give = button("Give up this ticket", "quiet", { do: "cancel", ticket },
    `Give up #${ticket}? Its unmerged work is thrown away.`);
  const can = answers(data);
  // Only a ticket that would go on: it is left with its work until it is sent on from here.
  const pause = ["ticket", "held"].includes(data.kind)
    && button("Pause this ticket", "quiet", { do: "pause", ticket });
  return [h("h2", {}, "Your word"),
    h("div", { class: "word card" }, said, can.length > 0 && note,
      h("div", { class: "buttons" }, can, pause, give))];
}

// What the ticket asks for. Whoever has the key can rewrite one nobody has worked on yet.
function wanted(data) {
  const draft = drafts.get(data.id);
  const again = () => { drawn = ""; look(); };
  if (!draft) {
    const edit = key && data.editable && h("button", { class: "small", type: "button" }, "Edit");
    if (edit) edit.addEventListener("click", () => {
      drafts.set(data.id, { title: data.title, spec: data.spec });
      again();
    });
    return h("div", { class: "block card" }, prose(data.spec), edit && h("div", { class: "buttons" }, edit));
  }
  const title = h("input", { type: "text", value: draft.title });
  const spec = h("textarea", { rows: 14 });
  spec.value = draft.spec;
  title.addEventListener("input", () => { draft.title = title.value; });
  spec.addEventListener("input", () => { draft.spec = spec.value; });
  const save = h("button", { class: "main", type: "button" }, "Save");
  save.addEventListener("click", async () => {
    await order({ do: "edit", ticket: data.id, title: draft.title.trim(), spec: draft.spec.trim() });
    if (!told.bad) drafts.delete(data.id);
    again();
  });
  const cancel = h("button", { type: "button" }, "Cancel");
  cancel.addEventListener("click", () => { drafts.delete(data.id); again(); });
  return h("div", { class: "word card" }, title, spec, h("div", { class: "buttons" }, save, cancel));
}

// The line under a ticket's title: where it is and what holds it.
function facts(data) {
  return h("div", { class: "meta" },
    !["done", "cancelled", "proposed"].includes(data.kind) && h("span", {}, `at ${data.step}`),
    data.attempts > 0 && h("span", {}, `${data.attempts} attempt${data.attempts > 1 ? "s" : ""}`),
    !data.behaviour && h("span", {}, "no behaviour tests"),
    data.worker && h("span", {}, `${data.worker} since ${data.since.slice(11)}`),
    data.follows.length > 0 && h("span", {}, "after ", listed(data.follows)),
    data.waits.length > 0 && h("span", {}, "waits for ", listed(data.waits)));
}

function ticket(data) {
  where.textContent = data.epic || "Without an epic";
  return [
    h("div", { class: "title-line" }, h("h1", {}, `#${data.id} ${data.title}`), state(data)),
    facts(data),
    data.note && [h("h2", {}, "Why it stopped"), h("div", { class: "say card" }, data.note)],
    h("h2", {}, "What is wanted"),
    wanted(data),
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
