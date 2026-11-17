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

function inline(text, from) {
  const out = [];
  let at = 0;
  for (const found of text.matchAll(INLINE)) {
    const [whole, code, bold, starred, underlined, words, href] = found;
    if (found.index > at) out.push(text.slice(at, found.index));
    at = found.index + whole.length;
    const leads = href !== undefined && target(href, from);
    if (code !== undefined) out.push(el("code", [code]));
    else if (bold !== undefined) out.push(el("strong", inline(bold, from)));
    else if (href === undefined) out.push(el("em", inline(starred ?? underlined, from)));
    else if (leads) out.push(el("a", inline(words, from), leads));
    else out.push(...inline(words, from));
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

// A list is its items at one depth; what is written deeper under an item belongs to it,
// across empty lines too, and is read as a document of its own.
function list(lines, at, from) {
  const [, indent, first] = ITEM.exec(lines[at]);
  const items = [];
  const mine = (line) => {
    const item = line === undefined ? null : ITEM.exec(line);
    return item && item[1].length === indent.length ? item : null;
  };
  while (mine(lines[at])) {
    const [, , mark, words] = mine(lines[at]);
    const inside = [words];
    const depth = indent.length + mark.length + 1;
    at += 1;
    while (at < lines.length) {
      const next = lines.slice(at).findIndex((line) => !blank(line));
      if (next === -1 || lead(lines[at + next]) <= indent.length) {
        if (next > 0 && mine(lines[at + next])) at += next;
        break;
      }
      inside.push(...lines.slice(at, at + next + 1).map((line) => line.slice(Math.min(lead(line), depth))));
      at += next + 1;
    }
    const [head, ...rest] = blocks(inside, from);
    const alone = head && head.tag === "p" && !rest.some((one) => one.tag === "p");
    items.push(el("li", alone ? [...head.children, ...rest] : [head, ...rest].filter(Boolean)));
  }
  return [el(/\d/.test(first) ? "ol" : "ul", items), at];
}

const begins = (lines, at) => [FENCE, HEADING, RULE, QUOTE, ITEM].some((shape) => shape.test(lines[at]))
  || (lines[at].includes("|") && DIVIDER.test(lines[at + 1] ?? ""));

function blocks(lines, from) {
  const out = [];
  let at = 0;
  while (at < lines.length) {
    const line = lines[at];
    const heading = HEADING.exec(line);
    if (blank(line)) {
      at += 1;
    } else if (FENCE.test(line)) {
      const close = lines.findIndex((other, where) => where > at && FENCE.test(other));
      const end = close === -1 ? lines.length : close;
      out.push(el("pre", [el("code", [lines.slice(at + 1, end).join("\n")])]));
      at = end + 1;
    } else if (heading) {
      out.push(el(`h${heading[1].length}`, inline(heading[2], from)));
      at += 1;
    } else if (RULE.test(line)) {
      out.push(el("hr"));
      at += 1;
    } else if (QUOTE.test(line)) {
      const end = lines.findIndex((other, where) => where > at && !QUOTE.test(other));
      const quoted = lines.slice(at, end === -1 ? lines.length : end);
      out.push(el("blockquote", blocks(quoted.map((one) => one.replace(QUOTE, "")), from)));
      at += quoted.length;
    } else if (ITEM.test(line)) {
      const [made, end] = list(lines, at, from);
      out.push(made);
      at = end;
    } else if (line.includes("|") && DIVIDER.test(lines[at + 1] ?? "")) {
      const [made, end] = table(lines, at, from);
      out.push(made);
      at = end;
    } else {
      let end = at + 1;
      while (end < lines.length && !blank(lines[end]) && !begins(lines, end)) end += 1;
      const words = lines.slice(at, end).map((one) => one.trim()).join(" ");
      out.push(el("p", inline(words, from)));
      at = end;
    }
  }
  return out;
}

// `path` is the document's own, so that its links to other documents can be followed.
function markdown(text, path) {
  return blocks(text.replace(/\r/g, "").replace(/\t/g, "    ").split("\n"), path);
}

if (typeof module !== "undefined") module.exports = { markdown };
