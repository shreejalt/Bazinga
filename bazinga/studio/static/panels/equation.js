// The equation helper: write LaTeX (or pick from the palette and the templates) and see it rendered as you type, with
// the place of any mistake underlined and what to write instead; on its own line or inside a sentence; numbered with
// a name you can refer to; edits an existing equation in place.
import { EditorView, keymap, Decoration, ViewPlugin, placeholder as cmPlaceholder } from "@codemirror/view";
import { EditorState, StateField, StateEffect, Prec } from "@codemirror/state";
import { defaultKeymap, history, historyKeymap } from "@codemirror/commands";
import { closeBrackets, closeBracketsKeymap } from "@codemirror/autocomplete";
import { bracketMatching } from "@codemirror/language";
import { api, store, h, clear, modal, debounce, toast, fill, modKey } from "../lib.js";
import { mathAt } from "../cm.js";
import { renderOne, renderMany, namedEquations, sentence, hintNodes } from "../mathtips.js";

const BOX = "□";   // a box to fill in; Tab moves to the next one

// --- the palette -----------------------------------------------------------------------------------------------------
// [label shown on the button, LaTeX inserted, name for the tooltip]
const GREEK = [["α", "\\alpha"], ["β", "\\beta"], ["γ", "\\gamma"], ["δ", "\\delta"], ["ε", "\\epsilon"],
  ["ϵ", "\\varepsilon"], ["ζ", "\\zeta"], ["η", "\\eta"], ["θ", "\\theta"], ["ι", "\\iota"], ["κ", "\\kappa"],
  ["λ", "\\lambda"], ["μ", "\\mu"], ["ν", "\\nu"], ["ξ", "\\xi"], ["π", "\\pi"], ["ρ", "\\rho"], ["σ", "\\sigma"],
  ["τ", "\\tau"], ["υ", "\\upsilon"], ["ϕ", "\\phi"], ["φ", "\\varphi"], ["χ", "\\chi"], ["ψ", "\\psi"], ["ω", "\\omega"],
  ["Γ", "\\Gamma"], ["Δ", "\\Delta"], ["Θ", "\\Theta"], ["Λ", "\\Lambda"], ["Ξ", "\\Xi"], ["Π", "\\Pi"], ["Σ", "\\Sigma"],
  ["Φ", "\\Phi"], ["Ψ", "\\Psi"], ["Ω", "\\Omega"], ["ℓ", "\\ell"], ["ℏ", "\\hbar"]].map(([l, t]) => [l, t, t.slice(1)]);

const OPERATORS = [["+", "+", "plus"], ["−", "-", "minus"], ["×", "\\times", "times"], ["·", "\\cdot", "dot product"],
  ["÷", "\\div", "divided by"], ["±", "\\pm", "plus or minus"], ["∘", "\\circ", "composition"], ["⊙", "\\odot", "element-wise product"],
  ["⊗", "\\otimes", "tensor product"], ["⊕", "\\oplus", "direct sum"], ["=", "=", "equals"], ["≠", "\\neq", "not equal"],
  ["≈", "\\approx", "approximately"], ["≡", "\\equiv", "identical"], ["∝", "\\propto", "proportional to"],
  ["∼", "\\sim", "distributed as"], ["≔", "\\coloneqq", "defined as"], ["≤", "\\le", "at most"], ["≥", "\\ge", "at least"],
  ["≪", "\\ll", "much less"], ["≫", "\\gg", "much greater"], ["∈", "\\in", "in"], ["∉", "\\notin", "not in"],
  ["⊂", "\\subset", "subset"], ["⊆", "\\subseteq", "subset or equal"], ["∪", "\\cup", "union"], ["∩", "\\cap", "intersection"],
  ["∖", "\\setminus", "set minus"], ["∅", "\\emptyset", "empty set"], ["∀", "\\forall", "for all"], ["∃", "\\exists", "there is"],
  ["¬", "\\neg", "not"], ["∧", "\\land", "and"], ["∨", "\\lor", "or"], ["∣", "\\mid", "given / such that"],
  ["∥", "\\parallel", "parallel"], ["⊥", "\\perp", "perpendicular"], ["∞", "\\infty", "infinity"], ["∂", "\\partial", "partial"],
  ["∇", "\\nabla", "gradient"], ["′", "'", "prime"], ["xᵀ", "^\\top", "transpose"], ["…", "\\ldots", "dots"],
  ["⋯", "\\cdots", "centred dots"], ["⋮", "\\vdots", "vertical dots"], ["⋱", "\\ddots", "diagonal dots"],
  ["ℝ", "\\mathbb{R}", "real numbers"], ["ℕ", "\\mathbb{N}", "natural numbers"], ["ℤ", "\\mathbb{Z}", "integers"],
  ["𝔼", "\\mathbb{E}", "expectation"], ["ℙ", "\\mathbb{P}", "probability"]];

const ARROWS = [["→", "\\to", "to"], ["←", "\\leftarrow", "left arrow"], ["↔", "\\leftrightarrow", "both ways"],
  ["⇒", "\\Rightarrow", "implies"], ["⇐", "\\Leftarrow", "is implied by"], ["⇔", "\\Leftrightarrow", "if and only if"],
  ["⟶", "\\longrightarrow", "long arrow"], ["⟹", "\\implies", "implies (long)"], ["⟺", "\\iff", "iff (long)"],
  ["↦", "\\mapsto", "maps to"], ["↪", "\\hookrightarrow", "embeds in"], ["↑", "\\uparrow", "up"], ["↓", "\\downarrow", "down"],
  ["⇌", "\\rightleftharpoons", "equilibrium"], ["→ᶠ", `\\xrightarrow{${BOX}}`, "arrow with a label"]];

const ACCENTS = [["x̂", `\\hat{${BOX}}`, "hat (an estimate)"], ["x̄", `\\bar{${BOX}}`, "bar (a mean)"], ["x̃", `\\tilde{${BOX}}`, "tilde"],
  ["x⃗", `\\vec{${BOX}}`, "vector arrow"], ["ẋ", `\\dot{${BOX}}`, "dot (time derivative)"], ["ẍ", `\\ddot{${BOX}}`, "double dot"],
  ["x̂y", `\\widehat{${BOX}}`, "wide hat"], ["x̅y", `\\overline{${BOX}}`, "line over"], ["x̲", `\\underline{${BOX}}`, "line under"],
  ["𝐱", `\\mathbf{${BOX}}`, "bold (vectors, matrices)"], ["𝜽", `\\boldsymbol{${BOX}}`, "bold Greek"], ["ℝ", `\\mathbb{${BOX}}`, "blackboard (sets)"],
  ["ℒ", `\\mathcal{${BOX}}`, "script (losses, sets)"], ["𝔤", `\\mathfrak{${BOX}}`, "fraktur"], ["d", `\\mathrm{${BOX}}`, "upright"],
  ["f", `\\operatorname{${BOX}}`, "named function"], ["abc", `\\text{${BOX}}`, "words"], ["𝗑", `\\mathsf{${BOX}}`, "sans"],
  ["☐", `\\boxed{${BOX}}`, "box around"], ["x̸", `\\cancel{${BOX}}`, "struck through"], ["x", `\\color{gray}{${BOX}}`, "colour"]];

const BIG = [["Σ", `\\sum_{${BOX}}^{${BOX}}`, "sum"], ["Π", `\\prod_{${BOX}}^{${BOX}}`, "product"],
  ["∫", `\\int_{${BOX}}^{${BOX}}`, "integral"], ["∬", "\\iint", "double integral"], ["∮", "\\oint", "contour integral"],
  ["⋃", `\\bigcup_{${BOX}}`, "union of many"], ["⋂", `\\bigcap_{${BOX}}`, "intersection of many"],
  ["lim", `\\lim_{${BOX} \\to ${BOX}}`, "limit"], ["max", `\\max_{${BOX}}`, "maximum"], ["min", `\\min_{${BOX}}`, "minimum"],
  ["sup", `\\sup_{${BOX}}`, "supremum"], ["arg max", `\\argmax_{${BOX}}`, "arg max"], ["arg min", `\\argmin_{${BOX}}`, "arg min"],
  ["𝔼[·]", `\\mathbb{E}_{${BOX}}\\left[ ${BOX} \\right]`, "expectation"], ["log", "\\log", "log"], ["ln", "\\ln", "natural log"],
  ["exp", "\\exp", "exp"], ["sin", "\\sin", "sine"], ["cos", "\\cos", "cosine"], ["det", "\\det", "determinant"],
  ["tr", "\\operatorname{tr}", "trace"], ["softmax", "\\operatorname{softmax}", "softmax"]];

const BRACKETS = [["( )", `\\left( ${BOX} \\right)`, "brackets that grow"], ["[ ]", `\\left[ ${BOX} \\right]`, "square brackets that grow"],
  ["{ }", `\\left\\{ ${BOX} \\right\\}`, "braces that grow"], ["|x|", `\\lvert ${BOX} \\rvert`, "absolute value"],
  ["‖x‖", `\\lVert ${BOX} \\rVert`, "norm"], ["⟨x⟩", `\\langle ${BOX} \\rangle`, "angle brackets"],
  ["⌊x⌋", `\\lfloor ${BOX} \\rfloor`, "floor"], ["⌈x⌉", `\\lceil ${BOX} \\rceil`, "ceiling"],
  ["{x|…}", `\\{ ${BOX} \\mid ${BOX} \\}`, "set builder"], ["f|ₓ", `\\left. ${BOX} \\right|_{${BOX}}`, "evaluated at"]];

const STRUCTURES = [["a⁄b", `\\frac{${BOX}}{${BOX}}`, "fraction"], ["√x", `\\sqrt{${BOX}}`, "square root"],
  ["ⁿ√x", `\\sqrt[${BOX}]{${BOX}}`, "n-th root"], ["xⁿ", `^{${BOX}}`, "superscript"], ["xᵢ", `_{${BOX}}`, "subscript"],
  ["xᵢⁿ", `_{${BOX}}^{${BOX}}`, "both"], ["(ⁿₖ)", `\\binom{${BOX}}{${BOX}}`, "binomial"],
  ["a̲ᵇ", `\\underset{${BOX}}{${BOX}}`, "something under"], ["=ᵈᵉᶠ", `\\overset{${BOX}}{${BOX}}`, "something over"],
  ["⏞ over", `\\overbrace{${BOX}}^{${BOX}}`, "brace over"], ["⏟ under", `\\underbrace{${BOX}}_{${BOX}}`, "brace under"],
  ["space", "\\quad", "a wide space"], ["thin", "\\,", "a thin space"]];

// ~20 equations people write in ML posts. Each one renders as is; edit the parts you need.
export const TEMPLATES = [
  ["Softmax", "\\operatorname{softmax}(\\mathbf{z})_i = \\frac{e^{z_i}}{\\sum_{j=1}^{K} e^{z_j}}"],
  ["Cross-entropy", "\\mathcal{L}_{\\mathrm{CE}} = -\\sum_{k=1}^{K} y_k \\log \\hat{y}_k"],
  ["Attention", "\\operatorname{Attention}(Q, K, V) = \\operatorname{softmax}\\left( \\frac{Q K^\\top}{\\sqrt{d_k}} \\right) V"],
  ["Gradient descent", "\\theta_{t+1} = \\theta_t - \\eta \\, \\nabla_\\theta \\mathcal{L}(\\theta_t)"],
  ["Adam", "\\begin{aligned}\nm_t &= \\beta_1 m_{t-1} + (1 - \\beta_1)\\, g_t \\\\\nv_t &= \\beta_2 v_{t-1} + (1 - \\beta_2)\\, g_t^2 \\\\\n\\theta_t &= \\theta_{t-1} - \\alpha \\frac{\\hat{m}_t}{\\sqrt{\\hat{v}_t} + \\epsilon}\n\\end{aligned}"],
  ["KL divergence", "D_{\\mathrm{KL}}(P \\parallel Q) = \\sum_{x} P(x) \\log \\frac{P(x)}{Q(x)}"],
  ["Bayes' rule", "P(A \\mid B) = \\frac{P(B \\mid A)\\, P(A)}{P(B)}"],
  ["Normal density", "p(x) = \\frac{1}{\\sqrt{2\\pi\\sigma^2}} \\exp\\left( -\\frac{(x - \\mu)^2}{2\\sigma^2} \\right)"],
  ["Expectation", "\\mathbb{E}_{x \\sim p}[f(x)] = \\int f(x)\\, p(x)\\, \\mathrm{d}x"],
  ["Variance", "\\operatorname{Var}[X] = \\mathbb{E}\\left[ (X - \\mathbb{E}[X])^2 \\right]"],
  ["Mean squared error", "\\mathrm{MSE} = \\frac{1}{n} \\sum_{i=1}^{n} (y_i - \\hat{y}_i)^2"],
  ["Sigmoid", "\\sigma(x) = \\frac{1}{1 + e^{-x}}"],
  ["ReLU", "\\operatorname{ReLU}(x) = \\begin{cases} x & \\text{if } x > 0 \\\\ 0 & \\text{otherwise} \\end{cases}"],
  ["Convolution", "(f * g)(t) = \\int_{-\\infty}^{\\infty} f(\\tau)\\, g(t - \\tau)\\, \\mathrm{d}\\tau"],
  ["Layer norm", "\\operatorname{LN}(\\mathbf{x}) = \\boldsymbol{\\gamma} \\odot \\frac{\\mathbf{x} - \\mu}{\\sqrt{\\sigma^2 + \\epsilon}} + \\boldsymbol{\\beta}"],
  ["Chain rule", "\\frac{\\partial L}{\\partial x} = \\frac{\\partial L}{\\partial y} \\, \\frac{\\partial y}{\\partial x}"],
  ["Matrix product", "C_{ij} = \\sum_{k=1}^{n} A_{ik} B_{kj}"],
  ["L2 norm", "\\lVert \\mathbf{x} \\rVert_2 = \\sqrt{\\sum_{i=1}^{d} x_i^2}"],
  ["Logistic regression", "P(y = 1 \\mid \\mathbf{x}) = \\sigma(\\mathbf{w}^\\top \\mathbf{x} + b)"],
  ["Entropy", "H(X) = -\\sum_{x \\in \\mathcal{X}} p(x) \\log p(x)"],
  ["Linear layer", "\\mathbf{y} = W \\mathbf{x} + \\mathbf{b}, \\quad W \\in \\mathbb{R}^{m \\times n}"],
];

const TABS = [
  { id: "templates", label: "Templates" }, { id: "structures", label: "Structures", items: STRUCTURES },
  { id: "greek", label: "Greek", items: GREEK }, { id: "operators", label: "Operators & relations", items: OPERATORS },
  { id: "arrows", label: "Arrows", items: ARROWS }, { id: "accents", label: "Accents & fonts", items: ACCENTS },
  { id: "big", label: "Big operators", items: BIG }, { id: "brackets", label: "Brackets", items: BRACKETS },
];
const TAB_KEY = "bazinga-studio-eq-tab";

// Builders for blocks of rows.
export function matrixSnippet(rows, cols, kind = "pmatrix") {
  const row = Array(cols).fill(BOX).join(" & ");
  return `\\begin{${kind}}\n` + Array(rows).fill(row).join(" \\\\\n") + `\n\\end{${kind}}`;
}
export function casesSnippet(n) {
  const rows = Array(n).fill(0).map((_, i) => `${BOX} & ${i === n - 1 ? "\\text{otherwise}" : `\\text{if } ${BOX}`}`);
  return "\\begin{cases}\n" + rows.join(" \\\\\n") + "\n\\end{cases}";
}
export function alignedSnippet(n) {
  const rows = Array(n).fill(0).map((_, i) => (i === 0 ? `${BOX} &= ${BOX}` : `&= ${BOX}`));
  return "\\begin{aligned}\n" + rows.join(" \\\\\n") + "\n\\end{aligned}";
}

// --- the LaTeX field: a small editor with highlighting, boxes to fill, and the mistake underlined ----------------------
const setError = StateEffect.define();
const errorField = StateField.define({
  create: () => Decoration.none,
  update(deco, tr) {
    deco = deco.map(tr.changes);
    for (const e of tr.effects) if (e.is(setError)) {
      const { from, to } = e.value || {};
      deco = e.value && to > from ? Decoration.set([Decoration.mark({ class: "eq-err-mark" }).range(from, to)]) : Decoration.none;
    }
    return deco;
  },
  provide: (f) => EditorView.decorations.from(f),
});
const markCmd = Decoration.mark({ class: "eq-cmd" });
const markBrace = Decoration.mark({ class: "eq-brace" });
const markScript = Decoration.mark({ class: "eq-script" });
const markBox = Decoration.mark({ class: "eq-box" });
const texHighlight = ViewPlugin.fromClass(class {
  constructor(v) { this.decorations = this.build(v); }
  update(u) { if (u.docChanged) this.decorations = this.build(u.view); }
  build(v) {
    const s = v.state.doc.toString();
    const out = [];
    const re = /\\[A-Za-z]+\*?|\\.|[{}]|[_^&]|□/g;
    let m;
    while ((m = re.exec(s))) {
      const c = m[0][0];
      out.push((m[0] === BOX ? markBox : c === "\\" ? markCmd : c === "{" || c === "}" ? markBrace : markScript).range(m.index, m.index + m[0].length));
    }
    return Decoration.set(out, true);
  }
}, { decorations: (v) => v.decorations });

function nextBox(view, dir = 1) {
  const s = view.state.doc.toString();
  const sel = view.state.selection.main;
  let at = dir > 0 ? s.indexOf(BOX, sel.to) : s.lastIndexOf(BOX, Math.max(0, sel.from - 1));
  if (at < 0) at = dir > 0 ? s.indexOf(BOX) : s.lastIndexOf(BOX);
  if (at < 0) return false;
  view.dispatch({ selection: { anchor: at, head: at + 1 }, scrollIntoView: true });
  return true;
}

// --- the dialog ----------------------------------------------------------------------------------------------------
export function open(ed) {
  const state = store.state;
  const view = ed.view;
  const text = view.state.doc.toString();
  const here = mathAt(text, view.state.selection.main.head);
  const returnPos = view.state.selection.main.head;
  let editing = null, display = true, name = "", tex = "";
  if (here) {
    editing = here;
    display = here.kind === "display";
    tex = display ? text.slice(here.inner[0], here.inner[1]).replace(/^[ \t]*\n|\n[ \t]*$/g, "") : text.slice(here.from + 1, here.to - 1);
    if (here.after) {
      const lm = text.slice(here.after[0], here.after[1]).match(/\{#eq:([^}]*)\}/);
      if (lm) name = lm[1];
    }
  } else {
    const sel = view.state.selection.main;
    const picked = view.state.sliceDoc(sel.from, sel.to);
    if (picked && !picked.includes("\n")) { tex = picked; display = false; }
  }
  const mod = modKey();

  // field
  const fieldHost = h("div.eq-field", { "aria-label": "The equation in LaTeX" });
  const errBox = h("div.eq-error", { role: "status", "aria-live": "polite", hidden: true });
  const out = h("div.math-out", { "aria-live": "polite", "aria-label": "Preview" });
  const insertBtn = h("button.btn.primary", { type: "button", onclick: () => insert() }, editing ? "Update equation" : "Insert");
  let last = { ok: false, res: null };

  const field = new EditorView({
    parent: fieldHost,
    state: EditorState.create({
      doc: tex,
      extensions: [
        history(), closeBrackets(), bracketMatching(), EditorView.lineWrapping, errorField, texHighlight,
        cmPlaceholder("Type LaTeX, e.g. \\frac{a}{b}, or pick from the palette below"),
        Prec.highest(keymap.of([
          { key: "Tab", run: (v) => nextBox(v, 1) },
          { key: "Shift-Tab", run: (v) => nextBox(v, -1) },
          { key: "Mod-Enter", run: () => { insert(); return true; } },
        ])),
        keymap.of([...closeBracketsKeymap, ...defaultKeymap, ...historyKeymap]),
        EditorView.updateListener.of((u) => { if (u.docChanged) { render(); refreshNumbering(); } }),
        EditorView.contentAttributes.of({ "aria-label": "Equation in LaTeX", spellcheck: "false", autocorrect: "off", autocapitalize: "off" }),
      ],
    }),
  });
  const value = () => field.state.doc.toString();

  function insertSnippet(snippet, { replaceAll = false } = {}) {
    const sel = field.state.selection.main;
    const selected = field.state.sliceDoc(sel.from, sel.to);
    let s = snippet;
    if (selected && selected !== BOX && s.includes(BOX)) s = s.replace(BOX, selected);   // wrap the selection
    let from = sel.from, to = sel.to;
    if (replaceAll || !value().trim()) { from = 0; to = field.state.doc.length; }
    const before = field.state.sliceDoc(Math.max(0, from - 1), from);
    const after = field.state.sliceDoc(to, to + 1);
    if (/[A-Za-z]$/.test(before) && /^\\[A-Za-z]/.test(s)) s = " " + s;                 // \alpha after a letter
    if (/\\[A-Za-z]+$/.test(s) && /^[A-Za-z]/.test(after)) s = s + " ";                 // a letter after \alpha
    field.dispatch({ changes: { from, to, insert: s }, selection: { anchor: from + s.length } });
    const at = s.indexOf(BOX);
    if (at >= 0) field.dispatch({ selection: { anchor: from + at, head: from + at + 1 } });
    field.focus();
  }

  // mode
  const modeDisplay = h("button.seg-btn", { type: "button", onclick: () => setMode(true) }, "On its own line");
  const modeInline = h("button.seg-btn", { type: "button", onclick: () => setMode(false) }, "Inside a sentence");
  function setMode(d) {
    display = d;
    modeDisplay.setAttribute("aria-pressed", String(d));
    modeInline.setAttribute("aria-pressed", String(!d));
    numbering.hidden = !d;
    render();
  }

  // numbering and references
  const hasLabel = () => /\\(?:label|tag)\s*\{/.test(value());
  const numberToggle = h("input", { type: "checkbox", id: "eq-number-toggle" });
  numberToggle.checked = !!name;
  const nameInput = h("input.input", { type: "text", placeholder: "e.g. softmax", value: name, spellcheck: "false", "aria-label": "Name of the equation" });
  const refLine = h("p.eq-ref-line");
  const nameRow = h("div.eq-name-row", h("span.prefix-wrap", h("span.prefix", "eq:"), nameInput), refLine);
  const refList = h("div.eq-ref-list");
  const numbering = h("section.eq-numbering",
    h("label.eq-check", numberToggle, h("span", "Number this equation")),
    nameRow,
    h("div.eq-refs", h("span.label", "Refer to an equation on this page"), refList));
  function cleanName() { return nameInput.value.trim().replace(/^eq:/, "").replace(/\s+/g, "-"); }
  function refreshNumbering() {
    nameRow.hidden = !numberToggle.checked;
    const nm = cleanName();
    clear(refLine);
    if (numberToggle.checked) {
      if (nm && !/^[A-Za-z0-9_.:-]+$/.test(nm)) refLine.append(h("span.eq-bad", "Use letters, digits, - _ . or : only."));
      else if (nm) refLine.append("Refer to it in the text as ", h("code", `[eq:${nm}]`), ".");
      else refLine.append("Give it a short name, then write ", h("code", "[eq:name]"), " in the text to refer to it.");
    }
    const named = namedEquations(view.state.doc.toString()).filter((e) => !(editing && e.name === name));
    clear(refList);
    if (!named.length) { refList.append(h("p.muted.small", "Numbered equations on this page appear here, to refer to.")); return; }
    for (const e of named) {
      refList.append(h("div.eq-ref",
        h("span.eq-ref-num", `(${e.number})`), h("code", `[eq:${e.name}]`),
        h("span.eq-ref-tex", { title: e.tex }, e.tex.replace(/\s+/g, " ").slice(0, 60)),
        h("button.btn.small.ghost", { type: "button", title: "Put the reference in the page where the cursor was", onclick: () => insertReference(e.name) }, "Insert reference")));
    }
  }
  numberToggle.addEventListener("change", () => { refreshNumbering(); render(); if (numberToggle.checked) nameInput.focus(); });
  // the number this equation will get: one more than the numbered equations above it
  function nextNumber() {
    const at = editing ? editing.from : returnPos;
    return namedEquations(view.state.doc.toString()).filter((e) => e.from < at && !e.tagged && !(editing && e.name === name)).length + 1;
  }
  nameInput.addEventListener("input", refreshNumbering);
  nameInput.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); insert(); } });

  function insertReference(nm) {
    let pos = returnPos;
    if (editing) pos = editing.after ? editing.after[1] : editing.to;
    const before = view.state.sliceDoc(Math.max(0, pos - 1), pos);
    const ins = (before && !/\s|\(/.test(before) ? " " : "") + `[eq:${nm}]`;
    view.dispatch({ changes: { from: pos, insert: ins }, selection: { anchor: pos + ins.length }, scrollIntoView: true });
    m.close();
    view.focus();
    toast(`Added a reference to ${nm}. It shows its number on the page.`, "ok", 2600);
  }

  // palette
  const tabs = h("div.pal-tabs", { role: "tablist", "aria-label": "Symbols and templates" });
  const panel = h("div.pal-panel", { role: "tabpanel" });
  let tabIndex = 0;
  try { tabIndex = Math.max(0, TABS.findIndex((t) => t.id === localStorage.getItem(TAB_KEY))); } catch (e) { /* ignore */ }
  TABS.forEach((t, i) => tabs.append(h("button.pal-tab", { type: "button", role: "tab", id: `eq-tab-${t.id}`, tabindex: "-1",
    onclick: () => showTab(i), onkeydown: (e) => {
      if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
        e.preventDefault();
        const j = (i + (e.key === "ArrowRight" ? 1 : -1) + TABS.length) % TABS.length;
        showTab(j); tabs.children[j].focus();
      }
    } }, t.label)));
  function showTab(i) {
    tabIndex = i;
    try { localStorage.setItem(TAB_KEY, TABS[i].id); } catch (e) { /* ignore */ }
    [...tabs.children].forEach((b, j) => { b.setAttribute("aria-selected", String(i === j)); b.tabIndex = i === j ? 0 : -1; });
    clear(panel);
    const t = TABS[i];
    if (t.id === "templates") return showTemplates();
    const grid = h("div.pal-grid");
    for (const [label, snippet, title] of t.items) {
      grid.append(h("button.pal-btn", { type: "button", title: `${title}: ${snippet.replaceAll(BOX, "…")}`,
        class: /[a-z]{3,}/.test(label) && !/^(lim|max|min|sup|log|exp|sin|cos|det|arg|ln|tr)/.test(label) ? "word" : "",
        "aria-label": title, onclick: () => insertSnippet(snippet) }, label));
    }
    panel.append(grid);
    if (t.id === "structures") panel.append(builders());
  }

  function numberInput(val, min, max, label) {
    return h("input.input.num", { type: "number", min, max, value: val, "aria-label": label });
  }
  function builders() {
    const rows = numberInput(2, 1, 8, "Rows"), cols = numberInput(2, 1, 8, "Columns");
    const kind = h("select.select", { "aria-label": "Brackets" },
      ...[["pmatrix", "( )"], ["bmatrix", "[ ]"], ["vmatrix", "| | determinant"], ["Bmatrix", "{ }"], ["matrix", "no brackets"]]
        .map(([v, l]) => h("option", { value: v }, l)));
    const ncases = numberInput(2, 2, 8, "Number of cases"), nrows = numberInput(3, 2, 12, "Number of steps");
    const clamp = (el, lo, hi) => Math.max(lo, Math.min(hi, parseInt(el.value, 10) || lo));
    return h("div.pal-builders",
      h("div.builder", h("span.builder-title", "Matrix"), rows, h("span.times", "×"), cols, kind,
        h("button.btn.small", { type: "button", onclick: () => insertSnippet(matrixSnippet(clamp(rows, 1, 8), clamp(cols, 1, 8), kind.value)) }, "Insert")),
      h("div.builder", h("span.builder-title", "Cases"), ncases, h("span.muted", "choices"),
        h("button.btn.small", { type: "button", onclick: () => insertSnippet(casesSnippet(clamp(ncases, 2, 8))) }, "Insert")),
      h("div.builder", h("span.builder-title", "Derivation"), nrows, h("span.muted", "lines lined up at ="),
        h("button.btn.small", { type: "button", onclick: () => { insertSnippet(alignedSnippet(clamp(nrows, 2, 12))); if (!display) setMode(true); } }, "Insert")));
  }

  async function showTemplates() {
    const list = h("div.tpl-list");
    panel.append(list);
    const cells = TEMPLATES.map(([label, t]) => {
      const eq = h("div.tpl-eq");
      list.append(h("button.tpl", { type: "button", title: `Insert: ${label}`, onclick: () => {
        insertSnippet(t, { replaceAll: !value().trim() });
        if (t.includes("\n") && !display) setMode(true);
      } }, h("span.tpl-name", label), eq));
      return eq;
    });
    try {
      const res = await renderMany(TEMPLATES.map(([, t]) => ({ tex: t, display: false })));
      res.forEach((r, i) => { if (r && r.mathml) cells[i].innerHTML = r.mathml; else cells[i].textContent = TEMPLATES[i][1]; });
    } catch (e) { cells.forEach((c, i) => { c.textContent = TEMPLATES[i][1]; }); }
  }

  // describe in words (only when a writing model is set up for this site)
  const words = h("input.input", { type: "text", placeholder: "e.g. the softmax of z, component i", "aria-label": "Describe the equation in words" });
  const wordsBtn = h("button.btn.small", { type: "button", onclick: async () => {
      if (!words.value.trim()) { words.focus(); return; }
      wordsBtn.disabled = true; wordsBtn.textContent = "Writing…";
      try {
        const res = await api("/api/llm/equation", { words: words.value });
        field.dispatch({ changes: { from: 0, to: field.state.doc.length, insert: res.tex } });
      } catch (e) { toast(e.message, "error", 5000); }
      finally { wordsBtn.disabled = false; wordsBtn.textContent = "Write it"; }
    } }, "Write it");
  words.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); wordsBtn.click(); } });
  const describe = state.llm ? h("details.describe", h("summary", "Describe in words"),
    h("div.row", words, wordsBtn), h("span.hint", "A suggestion to check, not a final answer.")) : null;

  // live rendering
  let seq = 0;
  const render = debounce(async () => {
    const my = ++seq;
    const v = value();
    if (!v.trim()) {
      fill(out, h("span.math-empty", "The equation appears here as you type."));
      out.classList.remove("stale");
      errBox.hidden = true;
      field.dispatch({ effects: setError.of(null) });
      last = { ok: false, res: null };
      return;
    }
    const tx = display ? v : v.replace(/\n/g, " ");
    let res;
    try { res = await renderOne(tx, display); } catch (e) { fill(errBox, h("strong", e.message)); errBox.hidden = false; return; }
    if (my !== seq) return;
    if (!res) { fill(out, h("span.math-empty", "Equations are not available yet.")); last = { ok: true, res }; return; }
    out.classList.toggle("inline", !display);
    if (res.mathml) {
      const num = display && (numberToggle.checked || res.tag) ? h("span.eq-num", res.tag ? `(${res.tag})` : `(${nextNumber()})`) : null;
      if (!display) fill(out, h("p.eq-inline-ctx", "In a sentence, ", h("span.eq-math", { html: res.mathml }), " sits on the line."));
      else fill(out, num ? h("div.eq-row", h("div.eq-math", { html: res.mathml }), num) : h("div.eq-math", { html: res.mathml }));
      out.classList.remove("stale");
      errBox.hidden = true;
      field.dispatch({ effects: setError.of(null) });
      if (v.includes(BOX)) {
        fill(errBox, h("span.eq-boxes", `Fill in the empty boxes: Tab jumps to the next one.`));
        errBox.className = "eq-error info";
        errBox.hidden = false;
      }
      last = { ok: !v.includes(BOX), res };
      return;
    }
    out.classList.add("stale");
    if (!out.querySelector("math")) fill(out, h("span.math-empty", "The preview comes back when the mistake below is fixed."));
    const from = Math.min(res.index ?? 0, v.length);   // inline mode sends newlines as spaces: same positions
    const to = Math.min(v.length, from + (res.length || 1));
    field.dispatch({ effects: setError.of({ from: Math.min(from, v.length), to: Math.max(to, Math.min(from + 1, v.length)) }) });
    const where = res.line != null && res.column != null ? `Line ${res.line + 1}, column ${res.column + 1}` : "";
    errBox.className = "eq-error";
    fill(errBox,
      h("div.eq-error-head", h("strong", sentence(res.error)), where ? h("button.link-btn", { type: "button", title: "Put the cursor there",
        onclick: () => { field.dispatch({ selection: { anchor: from, head: to } }); field.focus(); } }, where) : null),
      res.hint ? h("p", h("span.eq-error-label", "Instead: "), ...hintNodes(res.hint)) : null);
    errBox.hidden = false;
    last = { ok: false, res };
  }, 140);

  function insert() {
    let v = value().trim();
    if (!v) { field.focus(); return; }
    if (v.includes(BOX)) {
      toast("Fill in the empty boxes first (Tab jumps to them), or delete them.", "error", 3500);
      nextBox(field, 1); field.focus();
      return;
    }
    let nm = "";
    if (display && numberToggle.checked) {
      nm = cleanName();
      if (!nm && !hasLabel()) { toast("Give the equation a name, or untick “Number this equation”.", "error"); nameInput.focus(); return; }
      if (nm && !/^[A-Za-z0-9_.:-]+$/.test(nm)) { toast("A name uses letters, digits and - _ . : only.", "error"); nameInput.focus(); return; }
      const clash = namedEquations(view.state.doc.toString()).find((e) => e.name === nm && !(editing && e.name === name));
      if (clash) { toast(`This page already has an equation named ${nm}.`, "error"); nameInput.focus(); return; }
    }
    if (!display) v = v.replace(/\s*\n\s*/g, " ");
    const block = display ? `$$\n${v}\n$$${nm ? ` {#eq:${nm}}` : ""}` : `$${v}$`;
    if (editing) {
      const to = editing.kind === "display" && editing.after ? editing.after[1] : editing.to;
      const ins = editing.kind === "display" || !display ? block : "\n\n" + block + "\n\n";
      view.dispatch({ changes: { from: editing.from, to, insert: ins }, selection: { anchor: editing.from + ins.length }, scrollIntoView: true });
      view.focus();
    } else if (display) {
      ed.insertBlock(block);
    } else {
      ed.insertText(block);
    }
    m.close();
    if (nm && (!editing || nm !== name)) {
      const ref = `[eq:${nm}]`;
      try { navigator.clipboard.writeText(ref); } catch (e) { /* no clipboard: the message still says it */ }
      toast(`Numbered. Refer to it in the text as ${ref} (copied).`, "ok", 4200);
    } else if (!last.ok) {
      toast("Inserted. The checks will show what to fix.", "info");
    }
  }

  const body = h("div.eq-layout",
    h("div.eq-left",
      h("div.eq-toprow", h("div.seg.mode", { role: "group", "aria-label": "Where the equation goes" }, modeDisplay, modeInline),
        h("span.hint", `Tab: next box · ${mod}+Enter: ${editing ? "update" : "insert"}`)),
      fieldHost, errBox,
      h("div.palette", tabs, panel),
      describe),
    h("div.eq-right",
      h("span.label", "Preview"),
      out, numbering));
  const m = modal({ title: editing ? "Edit equation" : "Equation", subtitle: "Write LaTeX, or build it from the palette. It is checked as you type.",
    body, wide: true, className: "eq-modal", onClose: () => field.destroy(),
    footer: [h("span.hint", editing ? "Changes replace the equation in the page." : "The equation goes where the cursor was."), h("span.grow"),
      h("button.btn.ghost", { type: "button", onclick: () => m.close() }, "Cancel"), insertBtn] });
  setMode(display);
  showTab(tabIndex);
  refreshNumbering();
  render.flush();
  setTimeout(() => { field.focus(); field.dispatch({ selection: { anchor: field.state.doc.length } }); }, 40);
}
