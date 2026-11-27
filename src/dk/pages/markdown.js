// Markdown as a project's documents use it, turned into a tree the page can draw: headings,
// paragraphs, lists, tables, quotes, rules, code, bold, italic and links. Whatever else a
// document holds stays the text it is. Nothing here touches the page, so it can be tried
// without a browser.
const el = (tag, children = [], attrs = {}) => ({ tag, attrs, children });

const FENCE = /^\s*```/;
const HEADING = /^(#{1,6})\s+(.*?)\s*#*\s*$/;
const RULE = /^\s*([-*_])(\s*\1){2,}\s*$/;
const QUOTE = /^\s*>\s?/;
const ITEM = /^(\s*)([-*+]|\d+[.)])\s+(.*)$/;
const DIVIDER = /^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$/;
const INLINE = new RegExp([
  "`([^`]+)`",
  "\\*\\*(.+?)\\*\\*",
  "(?<![\\w*])\\*(?!\\s)([^*]+?)(?<!\\s)\\*(?![\\w*])",
  "(?<!\\w)_(?!\\s)([^_]+?)(?<!\\s)_(?!\\w)",
  "\\[([^\\]]+)\\]\\(((?:[^()\\s]|\\([^()\\s]*\\))+)\\)",
].join("|"), "g");

const lead = (line) => line.length - line.trimStart().length;
const blank = (line) => line.trim() === "";

// Where a link leads: to the web, to another document of the project (`from` is the one
// being read), or nowhere the page can follow, which is null.
function target(href, from) {
  if (/^https?:\/\//i.test(href)) return { href, target: "_blank", rel: "noopener" };
  const [file] = href.split("#");
  if (/^[a-z][a-z0-9+.-]*:/i.test(href) || file.startsWith("/") || !file.endsWith(".md")) return null;
  const parts = from.split("/").slice(0, -1);
  for (const part of file.split("/")) {
    if (part === "..") parts.pop();
    else if (part !== ".") parts.push(part);
  }
  return { href: `#/doc/${parts.join("/")}` };
}

// What one find of INLINE is drawn as.
function marked([, code, bold, starred, underlined, words, href], from) {
  if (code !== undefined) return [el("code", [code])];
  if (bold !== undefined) return [el("strong", inline(bold, from))];
  if (href === undefined) return [el("em", inline(starred ?? underlined, from))];
  const leads = target(href, from);
  return leads ? [el("a", inline(words, from), leads)] : inline(words, from);
}

function inline(text, from) {
  const out = [];
  let at = 0;
  for (const found of text.matchAll(INLINE)) {
    if (found.index > at) out.push(text.slice(at, found.index));
    at = found.index + found[0].length;
    out.push(...marked(found, from));
  }
  if (at < text.length) out.push(text.slice(at));
  return out;
}

const cells = (line) => line.trim().replace(/^\|/, "").replace(/\|$/, "").split("|")
  .map((cell) => cell.trim());

function table(lines, at, from) {
  const row = (line, tag) => el("tr", cells(line).map((cell) => el(tag, inline(cell, from))));
  let end = at + 2;
  while (end < lines.length && lines[end].includes("|")) end += 1;
  const body = lines.slice(at + 2, end).map((line) => row(line, "td"));
  return [el("table", [el("thead", [row(lines[at], "th")]), el("tbody", body)]), end];
}

// How far the first line with words is from `at`; -1 when there is none.
const ahead = (lines, at) => lines.slice(at).findIndex((line) => !blank(line));

// The lines from `at` on that are written deeper than `indent`, each without its lead up to
// `depth`, and where they end.
function deeper(lines, at, indent, depth) {
  const under = [];
  let next = ahead(lines, at);
  while (next !== -1 && lead(lines[at + next]) > indent) {
    under.push(...lines.slice(at, at + next + 1).map((line) => line.slice(Math.min(lead(line), depth))));
    at += next + 1;
    next = ahead(lines, at);
  }
  return [under, at];
}

function item(inside, from) {
  const [head, ...rest] = blocks(inside, from);
  const alone = head && head.tag === "p" && !rest.some((one) => one.tag === "p");
  return el("li", alone ? [...head.children, ...rest] : [head, ...rest].filter(Boolean));
}

// A list is its items at one depth; what is written deeper under an item belongs to it,
// across empty lines too, and is read as a document of its own.
function list(lines, at, from) {
  const [, indent, first] = ITEM.exec(lines[at]);
  const items = [];
  const mine = (line) => {
    const found = line === undefined ? null : ITEM.exec(line);
    return found && found[1].length === indent.length ? found : null;
  };
  while (mine(lines[at])) {
    const [, , mark, words] = mine(lines[at]);
    const [under, end] = deeper(lines, at + 1, indent.length, indent.length + mark.length + 1);
    items.push(item([words, ...under], from));
    const next = ahead(lines, end);
    at = next > 0 && mine(lines[end + next]) ? end + next : end; // its next item, past empty lines
  }
  return [el(/\d/.test(first) ? "ol" : "ul", items), at];
}

function fenced(lines, at) {
  const close = lines.findIndex((other, where) => where > at && FENCE.test(other));
  const end = close === -1 ? lines.length : close;
  return [el("pre", [el("code", [lines.slice(at + 1, end).join("\n")])]), end + 1];
}

function headed(lines, at, from) {
  const [, marks, words] = HEADING.exec(lines[at]);
  return [el(`h${marks.length}`, inline(words, from)), at + 1];
}

function quoted(lines, at, from) {
  const end = lines.findIndex((other, where) => where > at && !QUOTE.test(other));
  const said = lines.slice(at, end === -1 ? lines.length : end);
  return [el("blockquote", blocks(said.map((one) => one.replace(QUOTE, "")), from)), at + said.length];
}

function paragraph(lines, at, from) {
  let end = at + 1;
  while (end < lines.length && !blank(lines[end]) && reader(lines, end) === paragraph) end += 1;
  const words = lines.slice(at, end).map((one) => one.trim()).join(" ");
  return [el("p", inline(words, from)), end];
}

const SHAPES = [[FENCE, fenced], [HEADING, headed], [RULE, (lines, at) => [el("hr"), at + 1]],
  [QUOTE, quoted], [ITEM, list]];

// What reads the block that starts at this line, giving what it makes and where it ends.
function reader(lines, at) {
  const shape = SHAPES.find(([looks]) => looks.test(lines[at]));
  if (shape) return shape[1];
  return lines[at].includes("|") && DIVIDER.test(lines[at + 1] ?? "") ? table : paragraph;
}

function blocks(lines, from) {
  const out = [];
  let at = 0;
  while (at < lines.length) {
    const [made, end] = blank(lines[at]) ? [null, at + 1] : reader(lines, at)(lines, at, from);
    if (made) out.push(made);
    at = end;
  }
  return out;
}

// `path` is the document's own, so that its links to other documents can be followed.
function markdown(text, path) {
  return blocks(text.replace(/\r/g, "").replace(/\t/g, "    ").split("\n"), path);
}

if (typeof module !== "undefined") module.exports = { markdown };
