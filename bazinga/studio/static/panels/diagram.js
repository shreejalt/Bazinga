// Diagrams written as text: an editor on the left (with the syntax at hand and a gallery of examples), the drawing on
// the right as it will appear in the post (wide or phone width), the line of any mistake marked with a plain hint.
// "Insert" puts a ```diagram block at the cursor; an existing block opens here from its "Edit diagram" button and is
// updated in place.
import { EditorState, StateField, StateEffect, RangeSetBuilder } from "@codemirror/state";
import {
  EditorView, keymap, lineNumbers, drawSelection, highlightActiveLine, highlightActiveLineGutter, Decoration,
  ViewPlugin, WidgetType,
} from "@codemirror/view";
import { defaultKeymap, history, historyKeymap, indentWithTab } from "@codemirror/commands";
import { api, store, h, clear, fill, icon, modal, toast, debounce } from "../lib.js";
import { scanRegions } from "../cm.js";

// --- the blocks in the page ------------------------------------------------------------------------------------------
const OPEN = /^(\s*(?:>\s?)*)(`{3,}|~{3,})\s*diagram\b\s*([A-Za-z-]*)/;

// The ```diagram block around a position of the page: {from, to, source, kind, fence, prefix} or null.
export function diagramBlockAt(doc, pos) {
  const text = doc.toString();
  for (const f of scanRegions(text).fences) {
    if (pos < f.from || pos > f.to) continue;
    const first = doc.line(f.line0 + 1);
    const m = first.text.match(OPEN);
    if (!m) return null;
    const lastNo = Math.min(f.line1 + 1, doc.lines);
    const last = doc.line(lastNo);
    const closed = lastNo > f.line0 + 1 && last.text.trim().startsWith(m[2][0].repeat(3));
    const inner = [];
    for (let n = f.line0 + 2; n <= (closed ? lastNo - 1 : lastNo); n++) inner.push(doc.line(n).text.slice(m[1].length));
    return { from: first.from, to: last.to, source: inner.join("\n"), kind: m[3] || "", fence: m[2], prefix: m[1] };
  }
  return null;
}

class EditButton extends WidgetType {
  constructor(pos, onEdit) { super(); this.pos = pos; this.onEdit = onEdit; }
  eq(other) { return other.pos === this.pos; }
  toDOM(view) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "dgp-edit-btn";
    b.textContent = "Edit diagram";
    b.title = "Open this diagram in the diagram editor";
    b.addEventListener("mousedown", (e) => e.preventDefault());
    b.addEventListener("click", (e) => { e.preventDefault(); this.onEdit(view, this.pos); });
    return b;
  }
  ignoreEvent() { return true; }
}

// An "Edit diagram" button at the end of every ```diagram line of the page.
export function diagramButtons(onEdit) {
  loadCss();
  const build = (view) => {
    const b = new RangeSetBuilder();
    const doc = view.state.doc;
    for (const f of scanRegions(doc.toString()).fences) {
      const line = doc.line(f.line0 + 1);
      if (OPEN.test(line.text)) b.add(line.to, line.to, Decoration.widget({ widget: new EditButton(line.from, onEdit), side: 1 }));
    }
    return b.finish();
  };
  return [ViewPlugin.fromClass(class {
    constructor(view) { this.decorations = build(view); }
    update(u) { if (u.docChanged) this.decorations = build(u.view); }
  }, { decorations: (v) => v.decorations })];
}

// --- the syntax, marked up in the panel's editor ---------------------------------------------------------------------
const marks = {
  com: Decoration.mark({ class: "dgp-com" }), kw: Decoration.mark({ class: "dgp-kw" }),
  arrow: Decoration.mark({ class: "dgp-arrow" }), str: Decoration.mark({ class: "dgp-str" }),
  attr: Decoration.mark({ class: "dgp-attr" }), shape: Decoration.mark({ class: "dgp-shape" }),
};
const errLine = Decoration.line({ class: "dgp-err-line" });
const setError = StateEffect.define();
const errorField = StateField.define({
  create: () => Decoration.none,
  update(deco, tr) {
    deco = deco.map(tr.changes);
    for (const e of tr.effects) {
      if (e.is(setError)) {
        const n = e.value;
        deco = n && n <= tr.state.doc.lines ? Decoration.set([errLine.range(tr.state.doc.line(n).from)]) : Decoration.none;
      }
    }
    return deco;
  },
  provide: (f) => EditorView.decorations.from(f),
});

function syntaxMarks(view) {
  const out = [];
  const doc = view.state.doc;
  for (let n = 1; n <= doc.lines; n++) {
    const line = doc.line(n);
    const t = line.text;
    const at = (a, b, m) => { if (b > a) out.push(m.range(line.from + a, line.from + b)); };
    let code = t;
    const c = t.search(/(^|\s)#/);
    if (c >= 0 && !/"[^"]*#/.test(t.slice(0, c + 2))) { at(c + (t[c] === "#" ? 0 : 1), t.length, marks.com); code = t.slice(0, c); }
    const kw = code.match(/^\s*(direction|layout|kind|type|title|caption|group|note)\b/i);
    if (kw) at(kw.index + kw[0].length - kw[1].length, kw.index + kw[0].length, marks.kw);
    const re = /"[^"]*"?|<-\.->|<==>|<-->|-\.->|<-\.-|==>|<==|-->|<--|<->|-\.-|===|---|->|<-|--|\|[^|]*\||\[\/[^\]]*\/\]|\(\([^)]*\)\)|\[[^\]]*\]|\{[^}]*\}|\([^)]*\)/g;
    let m;
    while ((m = re.exec(code))) {
      const s = m[0];
      const kind = s[0] === '"' ? marks.str : s[0] === "|" ? marks.str : s[0] === "[" && /=|^\[(accent|muted|data|emphasis|box|round|diamond|circle|cylinder)/i.test(s) && !s.startsWith("[/") ? marks.attr
        : /^[[({]/.test(s) ? marks.shape : marks.arrow;
      at(m.index, m.index + s.length, kind);
    }
  }
  return Decoration.set(out.sort((a, b) => a.from - b.from || a.value.startSide - b.value.startSide), true);
}
const syntax = ViewPlugin.fromClass(class {
  constructor(view) { this.decorations = syntaxMarks(view); }
  update(u) { if (u.docChanged) this.decorations = syntaxMarks(u.view); }
}, { decorations: (v) => v.decorations });

// --- the cheat sheet -------------------------------------------------------------------------------------------------
const SYNTAX = [
  ["Boxes and arrows", [
    ["A -> B -> C", "a chain of arrows (boxes are made for you)"],
    ["A <- B   A <-> B   A -- B", "backwards, both ways, a plain line"],
    ["A -.-> B   A ==> B", "dashed, thick"],
    ['A -> B: "label"', "a label on the arrow"],
    ["A ->|yes| B", "a label on one arrow of a chain"],
    ["A -> B & C", "one arrow to each"],
    ['"Step 1: load"', "quote names with : ; # & [ or arrows"],
  ]],
  ["Shapes and styles", [
    ["[box]  (round)  {decision}", "write the shape around the name"],
    ["((circle))  [/data/]", "a circle; a cylinder for data"],
    ["Name [accent]", "accent, muted, data, emphasis"],
    ['Name: "second line"', "a quieter line inside the box"],
    ['Name [label="Shown", sub="more"]', "settings, separated by commas"],
  ]],
  ["Groups, notes, layout", [
    ["group Encoder { A; B -> C }", "a frame; arrows to its title go to the frame"],
    ['note Name: "6 layers"', "a note beside a box"],
    ['note: "under the drawing"', "a note under the whole diagram"],
    ["direction: down", "right (the default) or down"],
    ['caption: "Shown below"', "a caption for the figure"],
  ]],
  ["Timelines and trees", [
    ["kind: timeline", "then one item per line:"],
    ['2017: Transformer: "detail"', "date, title, optional detail"],
    ["kind: tree", "then one box per line, children indented"],
  ]],
];

let cssLoaded = false;
function loadCss() {
  if (cssLoaded) return;
  cssLoaded = true;
  for (const href of ["/_studio/panels/diagram.css", "/assets/css/diagram.css",
    "https://fonts.googleapis.com/css2?family=Courier+Prime:ital,wght@0,400;0,700;1,400&display=swap"]) {
    document.head.append(h("link", { rel: "stylesheet", href }));
  }
}

const STARTER = "Input -> Model -> Output\nModel [accent]\n";

// --- the panel ---------------------------------------------------------------------------------------------------------
export function open(ed, { block = null, at = null } = {}) {
  loadCss();
  if (!block) block = diagramBlockAt(ed.view.state.doc, at !== null ? at : ed.view.state.selection.main.head);
  const editing = !!block;
  let examples = [];
  let width = "wide";
  let last = null;           // the last answer from the server
  let seq = 0;
  let edited = false;

  const host = h("div.dgp-code");
  const status = h("div.dgp-status", { role: "status", "aria-live": "polite" });
  const stage = h("div.dgp-stage.dgp-paper", { "aria-label": "Preview of the diagram" });
  const gallery = h("div.dgp-gallery", { role: "group", "aria-label": "Examples" });
  const segWide = h("button.seg-btn", { "aria-pressed": "true", title: "As on a wide screen", onclick: () => setWidth("wide") }, icon("desktop", 15), h("span", "Wide"));
  const segPhone = h("button.seg-btn", { "aria-pressed": "false", title: "As on a phone", onclick: () => setWidth("phone") }, icon("phone", 15), h("span", "Phone"));
  const help = h("details.dgp-help", h("summary", "How to write a diagram"),
    SYNTAX.map(([title, rows]) => h("div.dgp-help-sec", h("h4", title),
      h("dl", rows.map(([code, what]) => [h("dt", h("code", code)), h("dd", what)])))));
  const insertBtn = h("button.btn.primary", { onclick: () => insert() }, editing ? "Update diagram" : "Insert diagram");
  const codeLink = h("button.btn.ghost", { title: "Diagrams drawn by a small code file, for layouts text cannot describe", onclick: () => { m.close(); ed.openPanel("drawing"); } },
    icon("code", 16), h("span", "From a code file…"));

  const m = modal({
    title: editing ? "Edit diagram" : "Diagram",
    subtitle: "Boxes and arrows written as text, drawn when the site is built.",
    body: h("div.dgp",
      h("section.dgp-left", gallery, host, status, help),
      h("section.dgp-right", h("div.dgp-bar", h("span.dgp-label", "Preview"), h("span.grow"), h("div.seg", { role: "group", "aria-label": "Preview width" }, segWide, segPhone)), stage)),
    footer: [codeLink, h("span.grow"), h("button.btn.ghost", { onclick: () => m.close() }, "Cancel"), insertBtn],
    wide: true, className: "dgp-modal",
    onClose: () => view.destroy(),
  });

  const view = new EditorView({
    parent: host,
    state: EditorState.create({
      doc: block ? block.source : STARTER,
      extensions: [
        lineNumbers(), highlightActiveLineGutter(), history(), drawSelection(), highlightActiveLine(),
        keymap.of([{ key: "Mod-Enter", run: () => { insert(); return true; } }, ...defaultKeymap, ...historyKeymap, indentWithTab]),
        EditorView.lineWrapping, syntax, errorField,
        EditorView.updateListener.of((u) => { if (u.docChanged) { edited = true; renderSoon(); } }),
        EditorView.contentAttributes.of({ "aria-label": "Diagram text", spellcheck: "false" }),
      ],
    }),
  });
  setTimeout(() => view.focus(), 40);

  const text = () => view.state.doc.toString();
  const renderSoon = debounce(() => render(), 220);

  async function render() {
    const my = ++seq;
    let res;
    try { res = await api("/api/diagram/render", { source: text(), kind: block && block.kind ? block.kind : null }); }
    catch (e) { if (my === seq) showError({ error: e.message }); return; }
    if (my !== seq) return;
    if (res.available === false) { showError({ error: res.error || "Diagrams are not available yet." }); return; }
    if (!res.ok) { showError(res); return; }
    last = res;
    stage.classList.remove("stale");
    view.dispatch({ effects: setError.of(null) });
    paint();
    const parts = [res.kind === "timeline" ? `${res.boxes} ${res.boxes === 1 ? "event" : "events"}` : `${res.boxes} ${res.boxes === 1 ? "box" : "boxes"}`];
    if (res.kind === "flow") parts.push(`${res.arrows} ${res.arrows === 1 ? "arrow" : "arrows"}`);
    fill(status, icon("check", 15), h("span", parts.join(", ")));
    status.className = "dgp-status ok";
    insertBtn.disabled = false;
  }

  function paint() {
    if (!last) return;
    stage.classList.toggle("phone", width === "phone");
    stage.innerHTML = width === "phone" ? last.narrow : last.svg;
  }

  function showError(res) {
    const line = res.line || null;
    view.dispatch({ effects: setError.of(line) });
    fill(status, icon("alert", 15),
      line ? h("button.dgp-jump", { onclick: () => jump(line) }, `Line ${line}`) : null,
      h("span", ` ${res.error}`), res.hint ? h("span.dgp-hint", ` — ${res.hint}`) : null);
    status.className = "dgp-status err";
    stage.classList.add("stale");    // the last good drawing stays, faded, until the text draws again
  }

  function jump(n) {
    const line = view.state.doc.line(Math.min(n, view.state.doc.lines));
    view.dispatch({ selection: { anchor: line.from, head: line.to }, scrollIntoView: true });
    view.focus();
  }

  function setWidth(w) {
    width = w;
    segWide.setAttribute("aria-pressed", String(w === "wide"));
    segPhone.setAttribute("aria-pressed", String(w === "phone"));
    paint();
  }

  function loadExample(ex) {
    const had = edited && text().trim() && text() !== ex.source;
    view.dispatch({ changes: { from: 0, to: view.state.doc.length, insert: ex.source.replace(/\n$/, "") } });
    if (had) toast(`Example loaded. Undo (${navigator.platform.includes("Mac") ? "⌘" : "Ctrl"}+Z) brings your text back.`, "info", 3500);
    edited = false;
    for (const b of gallery.querySelectorAll("button")) b.setAttribute("aria-pressed", String(b.dataset.name === ex.name));
    view.focus();
  }

  function insert() {
    const src = text().replace(/\s+$/, "");
    if (!src.trim()) { toast("Write a diagram first.", "error"); return; }
    const kind = block && block.kind ? ` ${block.kind}` : "";
    if (editing) {
      const fence = block.fence || "```";
      const p = block.prefix || "";
      const body = src.split("\n").map((l) => p + l).join("\n");
      const insertText = `${p}${fence}diagram${kind}\n${body}\n${p}${fence}`;
      ed.view.dispatch({ changes: { from: block.from, to: block.to, insert: insertText }, selection: { anchor: block.from }, scrollIntoView: true });
      ed.view.focus();
      toast("Diagram updated.", "ok", 1800);
    } else {
      ed.insertBlock("```diagram\n" + src + "\n```");
    }
    m.close();
  }

  (async () => {
    try { examples = (await api("/api/diagram/examples")).examples || []; } catch (e) { examples = []; }
    clear(gallery);
    gallery.append(h("span.dgp-gallery-label", "Examples"));
    for (const ex of examples) {
      gallery.append(h("button.dgp-chip", { type: "button", "data-name": ex.name, "aria-pressed": "false", title: ex.caption || ex.title, onclick: () => loadExample(ex) }, ex.title));
    }
  })();
  render();
  return { close: () => m.close(), view };
}

export { store };
