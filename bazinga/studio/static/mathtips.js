// Equations in the writing surface: a rendered equation when you hover over one, a wavy underline (with the message
// and the fix) under the exact place of a mistake, and an "Edit equation" button while the caret is inside one.
import { hoverTooltip, showTooltip, EditorView } from "@codemirror/view";
import { StateField } from "@codemirror/state";
import { linter } from "@codemirror/lint";
import { api, h } from "./lib.js";
import { scanRegions } from "./cm.js";

// --- rendering, shared with the equation helper ---------------------------------------------------------------------
const cache = new Map();   // "d|tex" or "i|tex" -> result {mathml, tag, label} or {error, hint, line, column, index, length}
const key = (tex, display) => (display ? "d|" : "i|") + tex;

// Render many formulas at once; answers come from the cache when they can.
export async function renderMany(items) {
  const missing = [];
  for (const it of items) if (!cache.has(key(it.tex, it.display))) missing.push(it);
  for (let i = 0; i < missing.length; i += 200) {
    const chunk = missing.slice(i, i + 200);
    const res = await api("/api/math", { items: chunk.map(({ tex, display }) => ({ tex, display })) });
    if (res.available === false) return items.map(() => null);
    chunk.forEach((it, k) => cache.set(key(it.tex, it.display), res.results[k]));
  }
  if (cache.size > 2000) for (const k of [...cache.keys()].slice(0, 500)) cache.delete(k);
  return items.map((it) => cache.get(key(it.tex, it.display)));
}

export async function renderOne(tex, display) {
  const [r] = await renderMany([{ tex, display }]);
  return r;
}

// The formula inside a region of the page, where it starts in the document, and whether it is displayed.
export function formulaOf(text, region) {
  if (region.kind === "display" || region.inner) {
    const [a, b] = region.inner;
    return { tex: text.slice(a, b), start: a, display: true };
  }
  return { tex: text.slice(region.from + 1, region.to - 1), start: region.from + 1, display: false };
}

export function allFormulas(text) {
  const r = scanRegions(text);
  const out = [];
  for (const d of r.display) if (!d.open) out.push({ ...formulaOf(text, { ...d, kind: "display" }), region: { ...d, kind: "display" } });
  for (const d of r.inline) out.push({ ...formulaOf(text, { ...d, kind: "inline" }), region: { ...d, kind: "inline" } });
  return out.filter((f) => f.tex.trim());
}

function regionAt(text, pos, inclusive = true) {
  const r = scanRegions(text);
  for (const d of r.display) if (!d.open && pos >= d.from && (inclusive ? pos <= d.to : pos < d.to)) return { ...d, kind: "display" };
  for (const d of r.inline) if (pos > d.from && pos < d.to) return { ...d, kind: "inline" };
  return null;
}

// A rendered result as DOM: the equation, or the message with what to write instead.
export function resultNode(res, display) {
  if (!res) return h("div.math-tip-note", "Equations are not available yet.");
  if (res.mathml) {
    const box = h("div.math-tip-eq", { class: display ? "display" : "" });
    box.innerHTML = res.mathml;
    return box;
  }
  return h("div.math-tip-err",
    h("strong", sentence(res.error)),
    res.hint ? h("p", h("span.math-tip-label", "Instead: "), ...hintNodes(res.hint)) : null);
}

// A hint as text with its LaTeX parts set as code.
export function hintNodes(hint) {
  const parts = [];
  const re = /(\\[A-Za-z]+\*?(?:\[[^\]]*\])?(?:\{[^{}]*\})*|[\^_]\{[^{}]*\}|\$\$|\[eq:[^\]]*\]|\{#eq:[^}]*\}|x\^\{[^}]*\}|\{[^{}]*\}[\^_]\w|\\\\)/g;
  let last = 0, m;
  while ((m = re.exec(hint))) {
    if (m.index > last) parts.push(hint.slice(last, m.index));
    parts.push(h("code.eq-hint", m[0]));
    last = m.index + m[0].length;
  }
  if (last < hint.length) parts.push(hint.slice(last));
  return parts;
}

export function sentence(s) { return s ? s.charAt(0).toUpperCase() + s.slice(1) : s; }

// --- editor extensions ----------------------------------------------------------------------------------------------
const hover = hoverTooltip(async (view, pos) => {
  const text = view.state.doc.toString();
  const region = regionAt(text, pos, false);
  if (!region) return null;
  const f = formulaOf(text, region);
  if (!f.tex.trim()) return null;
  let res;
  try { res = await renderOne(f.tex, f.display); } catch (e) { return null; }
  return {
    pos: region.from, end: region.to, above: false,
    create() { return { dom: h("div.math-tip", resultNode(res, f.display)) }; },
  };
}, { hoverTime: 350 });

const lint = linter(async (view) => {
  const text = view.state.doc.toString();
  const formulas = allFormulas(text);
  if (!formulas.length) return [];
  let results;
  try { results = await renderMany(formulas); } catch (e) { return []; }
  if (view.state.doc.toString() !== text) return [];          // typed meanwhile: the next pass will do it
  const out = [];
  formulas.forEach((f, k) => {
    const r = results[k];
    if (!r || !r.error) return;
    const from = Math.min(f.start + (r.index ?? 0), f.region.to);
    const to = Math.max(from + 1, Math.min(from + (r.length || 1), f.region.to));
    out.push({
      from, to, severity: "error", source: "Equation",
      message: sentence(r.error) + (r.hint ? ` Instead: ${r.hint}` : ""),
      renderMessage() {
        return h("div.lint-math", h("strong", sentence(r.error)),
          r.hint ? h("p", h("span.math-tip-label", "Instead: "), ...hintNodes(r.hint)) : null);
      },
    });
  });
  return out;
}, { delay: 650 });

// "Edit equation" above an equation while the caret is in it.
function caretButton(onEdit, modLabel) {
  const field = StateField.define({
    create: (state) => compute(state),
    update(value, tr) { return tr.docChanged || tr.selection ? compute(tr.state) : value; },
    provide: (f) => showTooltip.from(f),
  });
  function compute(state) {
    const sel = state.selection.main;
    if (!sel.empty) return null;
    const region = regionAt(state.doc.toString(), sel.head);
    if (!region) return null;
    return {
      pos: region.from, above: true, strictSide: false, arrow: false,
      create() {
        const b = h("button.math-edit-btn", { type: "button", title: `Edit this equation (${modLabel}+M)`,
          onmousedown: (e) => e.preventDefault(), onclick: () => onEdit() }, "Edit equation");
        return { dom: h("div.math-edit-tip", b) };
      },
    };
  }
  return field;
}

export function mathExtensions({ onEdit, modLabel = "Ctrl" } = {}) {
  return [hover, lint, caretButton(onEdit || (() => {}), modLabel),
    EditorView.domEventHandlers({
      dblclick(e, view) {                      // double-click an equation's $ sign to edit it
        const pos = view.posAtCoords({ x: e.clientX, y: e.clientY });
        if (pos == null) return false;
        const ch = view.state.doc.sliceString(pos, pos + 1) + view.state.doc.sliceString(Math.max(0, pos - 1), pos);
        if (!ch.includes("$")) return false;
        const region = regionAt(view.state.doc.toString(), pos);
        if (!region || !onEdit) return false;
        e.preventDefault();
        view.dispatch({ selection: { anchor: Math.min(region.to - 1, region.from + (region.kind === "display" ? 2 : 1)) } });
        onEdit();
        return true;
      },
    })];
}

// Named equations on the page, in order: [{name, number, tex}].
export function namedEquations(text) {
  const out = [];
  let n = 0;
  for (const f of allFormulas(text)) {
    if (!f.display) continue;
    const after = f.region.after ? text.slice(f.region.after[0], f.region.after[1]) : "";
    const lm = after.match(/\{#eq:([A-Za-z0-9_.:-]+)\}/);
    const inner = f.tex.match(/\\label\s*\{(?:eq:)?([^{}]+)\}/);
    const tag = f.tex.match(/\\tag\*?\s*\{([^{}]*)\}/);
    const name = lm ? lm[1] : inner ? inner[1].trim() : null;
    if (!name) continue;
    let number;
    if (tag) number = tag[1];
    else { n += 1; number = String(n); }
    out.push({ name, number, tex: f.tex.trim(), from: f.region.from, tagged: !!tag });
  }
  return out;
}
