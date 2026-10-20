// CodeMirror 6 for the Studio: the Markdown writing surface (with maths, links, citations and figures marked up as
// you type) and a plain code editor for figure and drawing files.
import { EditorState, Compartment, Prec } from "@codemirror/state";
import {
  EditorView, keymap, drawSelection, dropCursor, ViewPlugin, Decoration, placeholder,
  highlightSpecialChars, rectangularSelection, crosshairCursor, lineNumbers, highlightActiveLine,
  highlightActiveLineGutter,
} from "@codemirror/view";
import { defaultKeymap, history, historyKeymap, indentWithTab } from "@codemirror/commands";
import { syntaxHighlighting, HighlightStyle, indentOnInput, bracketMatching, defaultHighlightStyle } from "@codemirror/language";
import { autocompletion, completionKeymap, closeBrackets, closeBracketsKeymap, startCompletion } from "@codemirror/autocomplete";
import { searchKeymap, highlightSelectionMatches } from "@codemirror/search";
import { markdown, markdownLanguage } from "@codemirror/lang-markdown";
import { tags as t } from "@lezer/highlight";

export { startCompletion, EditorView };

// --- look ------------------------------------------------------------------------------------------------------------
const prose = HighlightStyle.define([
  { tag: t.heading1, class: "md-h md-h1" },
  { tag: t.heading2, class: "md-h md-h2" },
  { tag: t.heading3, class: "md-h md-h3" },
  { tag: [t.heading4, t.heading5, t.heading6], class: "md-h md-h4" },
  { tag: t.emphasis, class: "md-em" },
  { tag: t.strong, class: "md-strong" },
  { tag: t.strikethrough, class: "md-del" },
  { tag: t.link, class: "md-link" },
  { tag: t.url, class: "md-url" },
  { tag: t.monospace, class: "md-code" },
  { tag: t.quote, class: "md-quote" },
  { tag: [t.processingInstruction, t.contentSeparator], class: "md-mark" },
  { tag: t.list, class: "md-list" },
  { tag: t.comment, class: "md-comment" },
  // code inside fences
  { tag: t.keyword, class: "tok-kw" },
  { tag: [t.string, t.special(t.string)], class: "tok-str" },
  { tag: [t.number, t.bool, t.null], class: "tok-num" },
  { tag: [t.lineComment, t.blockComment], class: "tok-comment" },
  { tag: [t.function(t.variableName), t.function(t.propertyName)], class: "tok-fn" },
  { tag: [t.definition(t.variableName), t.className], class: "tok-def" },
  { tag: t.operator, class: "tok-op" },
]);

const codeStyle = HighlightStyle.define([
  { tag: t.keyword, class: "tok-kw" },
  { tag: [t.string, t.special(t.string)], class: "tok-str" },
  { tag: [t.number, t.bool, t.null], class: "tok-num" },
  { tag: [t.lineComment, t.blockComment, t.comment], class: "tok-comment" },
  { tag: [t.function(t.variableName), t.function(t.propertyName)], class: "tok-fn" },
  { tag: [t.definition(t.variableName), t.className, t.definition(t.function(t.variableName))], class: "tok-def" },
  { tag: [t.operator, t.punctuation], class: "tok-op" },
  { tag: t.propertyName, class: "tok-prop" },
  { tag: t.self, class: "tok-kw" },
]);

// --- maths, links, citations, directives -----------------------------------------------------------------------------
const mMath = Decoration.mark({ class: "cm-math" });
const mCmd = Decoration.mark({ class: "cm-tex-cmd" });
const mBrace = Decoration.mark({ class: "cm-tex-brace" });
const mScript = Decoration.mark({ class: "cm-tex-op" });
const mDelim = Decoration.mark({ class: "cm-math-delim" });
const mWiki = Decoration.mark({ class: "cm-wikilink" });
const mCite = Decoration.mark({ class: "cm-cite" });
const mDirective = Decoration.mark({ class: "cm-directive" });
const mLabel = Decoration.mark({ class: "cm-eqlabel" });
const mCallout = Decoration.mark({ class: "cm-callout-tag" });
const lMath = Decoration.line({ class: "cm-math-line" });
const lMathFirst = Decoration.line({ class: "cm-math-line cm-math-first" });
const lMathLast = Decoration.line({ class: "cm-math-line cm-math-last" });
const lDirective = Decoration.line({ class: "cm-directive-line" });
const lFence = Decoration.line({ class: "cm-fence-line" });

// Where the maths and code are in the whole document (used by decorations, completion and the equation helper).
export function scanRegions(text) {
  const regions = { display: [], inline: [], fences: [] };
  const lines = text.split("\n");
  let pos = 0, i = 0;
  while (i < lines.length) {
    const line = lines[i];
    const start = pos;
    const fence = line.match(/^\s*(?:>\s?)*(`{3,}|~{3,})/);
    if (fence) {
      const mark = fence[1];
      let j = i + 1, p = pos + line.length + 1;
      while (j < lines.length && !lines[j].trim().startsWith(mark)) { p += lines[j].length + 1; j++; }
      const end = j < lines.length ? p + lines[j].length : p - 1;
      regions.fences.push({ from: start, to: Math.max(start, end), line0: i, line1: Math.min(j, lines.length - 1) });
      for (let k = i; k <= Math.min(j, lines.length - 1); k++) pos += lines[k].length + 1;
      i = j + 1;
      continue;
    }
    const dm = line.match(/^(\s*(?:>\s?)*)\$\$/);
    if (dm) {
      const open = start + dm[1].length;
      const rest = line.slice(dm[1].length + 2);
      if (rest.includes("$$")) {
        const close = open + 2 + rest.indexOf("$$");
        regions.display.push({ from: open, to: close + 2, line0: i, line1: i, inner: [open + 2, close], after: [close + 2, start + line.length] });
        pos += line.length + 1; i++;
        continue;
      }
      let j = i + 1, p = pos + line.length + 1, closeAt = -1;
      while (j < lines.length) {
        const k = lines[j].indexOf("$$");
        if (k >= 0) { closeAt = p + k; break; }
        p += lines[j].length + 1; j++;
      }
      if (closeAt < 0) {   // unclosed: mark to the end so the author sees it
        regions.display.push({ from: open, to: text.length, line0: i, line1: lines.length - 1, inner: [open + 2, text.length], open: true });
        break;
      }
      const lineEnd = p + lines[j].length;
      regions.display.push({ from: open, to: closeAt + 2, line0: i, line1: j, inner: [open + 2, closeAt], after: [closeAt + 2, lineEnd] });
      for (let k = i; k <= j; k++) pos += lines[k].length + 1;
      i = j + 1;
      continue;
    }
    // inline $…$ (not $$, not \$), and not inside `code`
    const codeSpans = [];
    line.replace(/(`+)[^`]*?\1/g, (m0, _b, off) => { codeSpans.push([off, off + m0.length]); return m0; });
    const inCode = (k) => codeSpans.some(([a, b]) => k >= a && k < b);
    let k = 0;
    while (k < line.length) {
      if (line[k] === "$" && line[k - 1] !== "\\" && line[k + 1] !== "$" && !inCode(k)) {
        let e = k + 1;
        while (e < line.length && !(line[e] === "$" && line[e - 1] !== "\\")) e++;
        if (e < line.length && e > k + 1 && line[k + 1] !== " ") {
          regions.inline.push({ from: start + k, to: start + e + 1 });
          k = e + 1;
          continue;
        }
      }
      k++;
    }
    pos += line.length + 1;
    i++;
  }
  return regions;
}

export function mathAt(text, pos) {
  const r = scanRegions(text);
  for (const d of r.display) if (pos >= d.from && pos <= d.to) return { kind: "display", ...d };
  for (const d of r.inline) if (pos > d.from && pos < d.to) return { kind: "inline", ...d };
  return null;
}

function texMarks(text, from, to, out) {
  const s = text.slice(from, to);
  const re = /\\[A-Za-z]+|\\.|[{}]|[_^&]/g;
  let m;
  while ((m = re.exec(s))) {
    const a = from + m.index, b = a + m[0].length;
    const c = m[0][0];
    out.push((c === "\\" ? mCmd : c === "{" || c === "}" ? mBrace : mScript).range(a, b));
  }
}

function buildDecorations(view) {
  const text = view.state.doc.toString();
  const r = scanRegions(text);
  const out = [];
  const doc = view.state.doc;
  for (const f of r.fences) {
    for (let l = f.line0; l <= f.line1; l++) out.push(lFence.range(doc.line(l + 1).from));
  }
  for (const d of r.display) {
    for (let l = d.line0; l <= d.line1; l++) {
      const deco = d.line0 === d.line1 ? lMathFirst : l === d.line0 ? lMathFirst : l === d.line1 ? lMathLast : lMath;
      out.push(deco.range(doc.line(l + 1).from));
    }
    out.push(mDelim.range(d.from, d.from + 2));
    if (!d.open) out.push(mDelim.range(d.inner[1], d.inner[1] + 2));
    if (d.inner[1] > d.inner[0]) {
      out.push(mMath.range(d.inner[0], d.inner[1]));
      texMarks(text, d.inner[0], d.inner[1], out);
    }
    if (d.after && d.after[1] > d.after[0]) {
      const after = text.slice(d.after[0], d.after[1]);
      const lm = after.match(/\{#eq:[^}]*\}/);
      if (lm) out.push(mLabel.range(d.after[0] + lm.index, d.after[0] + lm.index + lm[0].length));
    }
  }
  for (const d of r.inline) {
    out.push(mDelim.range(d.from, d.from + 1), mDelim.range(d.to - 1, d.to));
    if (d.to - 1 > d.from + 1) { out.push(mMath.range(d.from + 1, d.to - 1)); texMarks(text, d.from + 1, d.to - 1, out); }
  }
  const inBlock = (p) => r.fences.some((f) => p >= f.from && p <= f.to) || r.display.some((d) => p >= d.from && p <= d.to);
  const inInline = (p) => r.inline.some((d) => p >= d.from && p < d.to);
  let m;
  const wiki = /\[\[[^\[\]\n]+?\]\]/g;
  while ((m = wiki.exec(text))) if (!inBlock(m.index) && !inInline(m.index)) out.push(mWiki.range(m.index, m.index + m[0].length));
  const cite = /\[@[^\[\]\n]+\]|\[eq:[^\]\n]+\]/g;
  while ((m = cite.exec(text))) if (!inBlock(m.index) && !inInline(m.index)) out.push(mCite.range(m.index, m.index + m[0].length));
  const dir = /^[ \t]*(?:>[ \t]?)*::(?:figure|drawing)\b.*$/gm;
  while ((m = dir.exec(text))) {
    if (inBlock(m.index)) continue;
    out.push(lDirective.range(doc.lineAt(m.index).from));
    out.push(mDirective.range(m.index, m.index + m[0].length));
  }
  const callout = /^>\s*\[!(NOTE|TIP|WARNING|KEY|[A-Z]+)\]/gm;
  while ((m = callout.exec(text))) if (!inBlock(m.index)) out.push(mCallout.range(m.index + m[0].indexOf("[!"), m.index + m[0].length));
  return Decoration.set(out, true);
}

const richText = ViewPlugin.fromClass(class {
  constructor(view) { this.decorations = buildDecorations(view); }
  update(u) { if (u.docChanged) this.decorations = buildDecorations(u.view); }
}, { decorations: (v) => v.decorations });

// --- completion --------------------------------------------------------------------------------------------------------
const TEX = [
  ["\\frac{}{}", "fraction"], ["\\sqrt{}", "square root"], ["\\sum_{i=1}^{n}", "sum"], ["\\prod_{i=1}^{n}", "product"],
  ["\\int_{a}^{b}", "integral"], ["\\lim_{x \\to 0}", "limit"], ["\\partial", "∂"], ["\\nabla", "∇"], ["\\infty", "∞"],
  ["\\cdot", "·"], ["\\times", "×"], ["\\le", "≤"], ["\\ge", "≥"], ["\\ne", "≠"], ["\\approx", "≈"], ["\\propto", "∝"],
  ["\\in", "∈"], ["\\subset", "⊂"], ["\\mathbb{R}", "ℝ"], ["\\mathbf{}", "bold"], ["\\mathcal{}", "script"],
  ["\\operatorname{softmax}", "softmax"], ["\\operatorname{argmax}", "argmax"], ["\\top", "⊤ transpose"],
  ["\\left(", "("], ["\\right)", ")"], ["\\text{}", "text"], ["\\quad", "space"], ["\\hat{}", "hat"], ["\\bar{}", "bar"],
  ["\\tilde{}", "tilde"], ["\\vec{}", "vector"], ["\\dot{}", "dot"], ["\\to", "→"], ["\\rightarrow", "→"],
  ["\\Rightarrow", "⇒"], ["\\mapsto", "↦"], ["\\log", "log"], ["\\exp", "exp"], ["\\max", "max"], ["\\min", "min"],
  ["\\mathrm{}", "upright"], ["\\begin{pmatrix}  \\end{pmatrix}", "matrix"], ["\\begin{cases}  \\end{cases}", "cases"],
  ["\\begin{array}{l}  \\end{array}", "rows"],
  ...["alpha", "beta", "gamma", "delta", "epsilon", "varepsilon", "zeta", "eta", "theta", "lambda", "mu", "nu", "xi",
    "pi", "rho", "sigma", "tau", "phi", "varphi", "chi", "psi", "omega", "Gamma", "Delta", "Theta", "Lambda", "Pi",
    "Sigma", "Phi", "Psi", "Omega"].map((g) => [`\\${g}`, g]),
];

export function makeCompletions(getContext) {
  // getContext() -> {pages, references, figures, drawings, slash: [{label, detail, run}], forcedSlash}
  return (context) => {
    const ctx = getContext();
    const line = context.state.doc.lineAt(context.pos);
    const before = line.text.slice(0, context.pos - line.from);

    let m = before.match(/\[\[([^\]|\n]*)$/);
    if (m) {
      const after = line.text.slice(context.pos - line.from);
      const close = after.startsWith("]]") ? "" : "]]";
      return {
        from: context.pos - m[1].length,
        options: ctx.pages.map((p) => ({ label: p.id, detail: p.title, type: "page", apply: p.id + close, boost: p.state === "published" ? 1 : 0 })),
        validFor: /^[\w:-]*$/,
      };
    }
    m = before.match(/\[@([\w:.-]*)$/);
    if (m) {
      const after = line.text.slice(context.pos - line.from);
      const close = after.startsWith("]") ? "" : "]";
      return {
        from: context.pos - m[1].length,
        options: ctx.references.map((r) => ({ label: r.key, detail: `${r.title}${r.year ? " (" + r.year + ")" : ""}`, type: "cite", apply: r.key + close })),
        validFor: /^[\w:.-]*$/,
      };
    }
    m = before.match(/^\s*::figure\s+(\w*)$/);
    if (m) return { from: context.pos - m[1].length, options: ctx.figures.map((f) => ({ label: f.name, detail: f.title, type: "figure" })), validFor: /^\w*$/ };
    m = before.match(/^\s*::drawing\s+([\w.]*)$/);
    if (m) {
      const opts = [];
      for (const d of ctx.drawings) for (const fn of d.functions) opts.push({ label: `${d.module}.${fn}`, type: "drawing" });
      return { from: context.pos - m[1].length, options: opts, validFor: /^[\w.]*$/ };
    }
    m = before.match(/^\s*::(\w*)$/);
    if (m) return { from: context.pos - m[1].length, options: [{ label: "figure ", detail: "an interactive figure" }, { label: "drawing ", detail: "a diagram" }] };
    m = before.match(/^>\s*\[!(\w*)$/);
    if (m) return { from: context.pos - m[1].length, options: ["NOTE", "TIP", "WARNING", "KEY"].map((k) => ({ label: k, apply: k + "] " })) };

    // the "/" menu: at the start of an empty line, or anywhere right after Mod-/
    m = before.match(/(^|\s)\/([\w-]*)$/);
    if (m && (/^\s*\/[\w-]*$/.test(before) || ctx.forcedSlash)) {
      const slashFrom = context.pos - m[2].length - 1;
      return {
        from: context.pos - m[2].length,
        filter: true,
        options: ctx.slash.map((s, i) => ({
          label: s.label, detail: s.detail || "", type: "slash", boost: -i, section: s.section,
          apply: (view, _c, _from, to) => {
            view.dispatch({ changes: { from: slashFrom, to, insert: "" } });
            s.run(view);
          },
        })),
        validFor: /^[\w-]*$/,
      };
    }

    // LaTeX commands inside maths
    m = before.match(/\\([A-Za-z]*)$/);
    if (m && mathAt(context.state.doc.toString(), context.pos)) {
      return {
        from: context.pos - m[1].length - 1,
        options: TEX.map(([cmd, detail]) => ({ label: cmd, detail, type: "tex", apply: cmd })),
        validFor: /^\\?[A-Za-z]*$/,
      };
    }
    return null;
  };
}

// --- editors -----------------------------------------------------------------------------------------------------------
const baseTheme = EditorView.theme({
  "&": { backgroundColor: "transparent" },
  ".cm-content": { caretColor: "var(--accent)" },
  "&.cm-focused .cm-cursor": { borderLeftColor: "var(--accent)", borderLeftWidth: "2px" },
  "&.cm-focused": { outline: "none" },
});

export function markdownEditor(parent, doc, { onChange, completions, keys = [], onPaste, onDrop }) {
  const wrap = new Compartment();
  const view = new EditorView({
    parent,
    state: EditorState.create({
      doc,
      extensions: [
        highlightSpecialChars(), history(), drawSelection(), dropCursor(), indentOnInput(), bracketMatching(),
        closeBrackets(), rectangularSelection(), crosshairCursor(), highlightSelectionMatches(),
        EditorView.lineWrapping, wrap.of([]),
        markdown({ base: markdownLanguage, addKeymap: true }),
        syntaxHighlighting(prose),
        richText,
        autocompletion({ override: [completions], icons: false, activateOnTyping: true, closeOnBlur: true,
          optionClass: (c) => c.type === "slash" ? "cm-slash-option" : "" }),
        placeholder("Start writing. Type / at the start of a line for equations, figures, citations and more."),
        Prec.highest(keymap.of(keys)),
        keymap.of([...closeBracketsKeymap, ...defaultKeymap, ...searchKeymap, ...historyKeymap, ...completionKeymap, indentWithTab]),
        EditorView.updateListener.of((u) => { if (u.docChanged && onChange) onChange(u); }),
        EditorView.domEventHandlers({
          paste: (e, v) => (onPaste ? onPaste(e, v) : false),
          drop: (e, v) => (onDrop ? onDrop(e, v) : false),
        }),
        baseTheme,
        EditorView.contentAttributes.of({ "aria-label": "Page text", spellcheck: "true", autocorrect: "on", autocapitalize: "sentences" }),
      ],
    }),
  });
  return view;
}

export async function codeEditor(parent, doc, { onChange, keys = [], language = "python" } = {}) {
  let lang = [];
  if (language === "python") {
    try { const mod = await import("@codemirror/lang-python"); lang = [mod.python()]; }
    catch (e) { lang = []; }   // highlighting is a nicety; editing works without it
  }
  return new EditorView({
    parent,
    state: EditorState.create({
      doc,
      extensions: [
        lineNumbers(), highlightActiveLineGutter(), highlightSpecialChars(), history(), drawSelection(),
        indentOnInput(), bracketMatching(), closeBrackets(), highlightActiveLine(), highlightSelectionMatches(),
        ...lang, syntaxHighlighting(codeStyle), syntaxHighlighting(defaultHighlightStyle, { fallback: true }),
        Prec.highest(keymap.of(keys)),
        keymap.of([...closeBracketsKeymap, ...defaultKeymap, ...searchKeymap, ...historyKeymap, indentWithTab]),
        EditorState.tabSize.of(4),
        EditorView.updateListener.of((u) => { if (u.docChanged && onChange) onChange(u); }),
        baseTheme,
        EditorView.contentAttributes.of({ "aria-label": "Code", spellcheck: "false" }),
      ],
    }),
  });
}

// --- edit helpers ----------------------------------------------------------------------------------------------------
export function insertBlock(view, text, cursorOffset = null) {
  // Put a block on its own lines at the cursor (replacing an empty line), with blank lines around it.
  const { state } = view;
  const line = state.doc.lineAt(state.selection.main.head);
  const empty = line.text.trim() === "";
  const from = empty ? line.from : line.to;
  const to = empty ? line.to : line.to;
  const before = state.doc.sliceString(Math.max(0, from - 2), from);
  const after = state.doc.sliceString(to, Math.min(state.doc.length, to + 2));
  let prefix = "";
  if (from > 0) prefix = !before.endsWith("\n") ? "\n\n" : before.endsWith("\n\n") || from === 1 ? "" : "\n";
  let suffix = "";
  if (!after.startsWith("\n\n")) suffix = after.startsWith("\n") ? "\n" : after.length ? "\n\n" : "\n";
  const insert = prefix + text + suffix;
  const anchor = from + prefix.length + (cursorOffset === null ? text.length : cursorOffset);
  view.dispatch({ changes: { from, to, insert }, selection: { anchor }, scrollIntoView: true });
  view.focus();
}

export function wrapSelection(view, left, right, placeholderText = "") {
  const sel = view.state.selection.main;
  const text = view.state.sliceDoc(sel.from, sel.to) || placeholderText;
  view.dispatch({
    changes: { from: sel.from, to: sel.to, insert: left + text + right },
    selection: { anchor: sel.from + left.length, head: sel.from + left.length + text.length },
    scrollIntoView: true,
  });
  view.focus();
}

export function insertText(view, text) {
  const sel = view.state.selection.main;
  view.dispatch({ changes: { from: sel.from, to: sel.to, insert: text }, selection: { anchor: sel.from + text.length }, scrollIntoView: true });
  view.focus();
}

export function goToLine(view, n) {
  const line = view.state.doc.line(Math.max(1, Math.min(view.state.doc.lines, n)));
  view.dispatch({ selection: { anchor: line.from, head: line.to }, effects: EditorView.scrollIntoView(line.from, { y: "center" }) });
  view.focus();
}
