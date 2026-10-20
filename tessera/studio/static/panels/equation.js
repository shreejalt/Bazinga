// Equation helper: LaTeX with a live rendering, a palette, the converter's messages with hints, "describe in words",
// display or inline, and a name to refer to it by.
import { api, store, h, clear, modal, debounce, toast, fill } from "../lib.js";
import { mathAt } from "../cm.js";

const C = "◊"; // where the caret goes after inserting a snippet

const PALETTE = [
  ["Greek", [["α", "\\alpha"], ["β", "\\beta"], ["γ", "\\gamma"], ["δ", "\\delta"], ["ε", "\\epsilon"], ["θ", "\\theta"],
    ["λ", "\\lambda"], ["μ", "\\mu"], ["π", "\\pi"], ["ρ", "\\rho"], ["σ", "\\sigma"], ["τ", "\\tau"], ["φ", "\\phi"],
    ["ψ", "\\psi"], ["ω", "\\omega"], ["Γ", "\\Gamma"], ["Δ", "\\Delta"], ["Θ", "\\Theta"], ["Λ", "\\Lambda"],
    ["Σ", "\\Sigma"], ["Φ", "\\Phi"], ["Ω", "\\Omega"]]],
  ["Operators", [["×", "\\times"], ["·", "\\cdot"], ["÷", "\\div"], ["±", "\\pm"], ["≤", "\\le"], ["≥", "\\ge"],
    ["≠", "\\ne"], ["≈", "\\approx"], ["∝", "\\propto"], ["≡", "\\equiv"], ["∈", "\\in"], ["⊂", "\\subset"],
    ["∪", "\\cup"], ["∩", "\\cap"], ["∂", "\\partial"], ["∇", "\\nabla"], ["∞", "\\infty"], ["‖x‖", `\\lVert ${C} \\rVert`],
    ["xᵀ", "^\\top"], ["∘", "\\circ"], ["⊗", "\\otimes"], ["∀", "\\forall"], ["∃", "\\exists"]]],
  ["Fractions", [["a⁄b", `\\frac{${C}}{}`], ["√x", `\\sqrt{${C}}`], ["ⁿ√x", `\\sqrt[n]{${C}}`], ["xⁿ", `^{${C}}`],
    ["xᵢ", `_{${C}}`], ["( )", `\\left( ${C} \\right)`], ["[ ]", `\\left[ ${C} \\right]`], ["{ }", `\\left\\{ ${C} \\right\\}`],
    ["(ⁿₖ)", `\\binom{${C}}{k}`], ["|x|", `\\lvert ${C} \\rvert`]]],
  ["Sums & integrals", [["Σ", `\\sum_{i=1}^{${C}n}`], ["Π", `\\prod_{i=1}^{${C}n}`], ["∫", `\\int_{${C}a}^{b}`],
    ["∬", "\\iint"], ["∮", "\\oint"], ["lim", `\\lim_{${C}x \\to 0}`], ["max", `\\max_{${C}}`], ["min", `\\min_{${C}}`],
    ["argmax", `\\operatorname{argmax}_{${C}}`], ["𝔼", `\\mathbb{E}\\left[ ${C} \\right]`], ["log", "\\log"], ["exp", "\\exp"]]],
  ["Matrices", [["( 2×2 )", `\\begin{pmatrix} ${C}a & b \\\\ c & d \\end{pmatrix}`],
    ["[ 2×2 ]", `\\begin{bmatrix} ${C}a & b \\\\ c & d \\end{bmatrix}`],
    ["column", `\\begin{pmatrix} ${C}x_1 \\\\ x_2 \\\\ x_3 \\end{pmatrix}`],
    ["| det |", `\\begin{vmatrix} ${C}a & b \\\\ c & d \\end{vmatrix}`],
    ["3×3", `\\begin{pmatrix} ${C}a & b & c \\\\ d & e & f \\\\ g & h & i \\end{pmatrix}`],
    ["⋯ ⋮ ⋱", "\\cdots"]]],
  ["Cases", [["cases", `\\begin{cases} ${C}a & \\text{if } x > 0 \\\\ b & \\text{otherwise} \\end{cases}`],
    ["rows", `\\begin{array}{l} ${C}a = b \\\\ c = d \\end{array}`],
    ["aligned rows", `\\begin{array}{rl} ${C}a &= b \\\\ c &= d \\end{array}`]]],
  ["Arrows", [["→", "\\to"], ["←", "\\leftarrow"], ["⇒", "\\Rightarrow"], ["⇐", "\\Leftarrow"], ["⇔", "\\Leftrightarrow"],
    ["↦", "\\mapsto"], ["⟶", "\\longrightarrow"], ["↑", "\\uparrow"], ["↓", "\\downarrow"]]],
  ["Accents", [["x̂", `\\hat{${C}x}`], ["x̄", `\\bar{${C}x}`], ["x̃", `\\tilde{${C}x}`], ["x⃗", `\\vec{${C}x}`],
    ["ẋ", `\\dot{${C}x}`], ["ẍ", `\\ddot{${C}x}`], ["𝐱", `\\mathbf{${C}x}`], ["ℝ", "\\mathbb{R}"], ["𝒳", `\\mathcal{${C}X}`],
    ["text", `\\text{${C}}`]]],
];

export function open(ed, { kind } = {}) {
  const state = store.state;
  const view = ed.view;
  const text = view.state.doc.toString();
  const here = mathAt(text, view.state.selection.main.head);
  let editing = null, display = true, name = "", tex = "";
  if (here) {
    editing = here;
    display = here.kind === "display";
    tex = display ? text.slice(here.inner[0], here.inner[1]).replace(/^\n|\n$/g, "") : text.slice(here.from + 1, here.to - 1);
    if (here.after) {
      const lm = text.slice(here.after[0], here.after[1]).match(/\{#eq:([^}]*)\}/);
      if (lm) name = lm[1];
    }
  } else {
    const sel = view.state.selection.main;
    const picked = view.state.sliceDoc(sel.from, sel.to);
    if (picked && !picked.includes("\n")) { tex = picked; display = false; }
  }

  const input = h("textarea.tex-input", { rows: 4, spellcheck: "false", autocomplete: "off", "aria-label": "LaTeX", placeholder: "e.g. \\operatorname{softmax}(z)_i = \\frac{e^{z_i}}{\\sum_j e^{z_j}}", autofocus: true });
  input.value = tex;
  const out = h("div.math-out", { "aria-live": "polite" });
  const msg = h("div.math-msg");
  const nameInput = h("input.input", { type: "text", placeholder: "attention", value: name, spellcheck: "false", "aria-label": "Name" });
  const nameField = h("label.field.inline-field", h("span.label", "Name"), h("span.prefix-wrap", h("span.prefix", "eq:"), nameInput),
    h("span.hint", "Optional. Numbers the equation; refer to it in the text as [eq:name]."));
  const modeDisplay = h("button.seg-btn", { type: "button", onclick: () => setMode(true) }, "On its own line");
  const modeInline = h("button.seg-btn", { type: "button", onclick: () => setMode(false) }, "Inside a sentence");
  function setMode(d) {
    display = d;
    modeDisplay.setAttribute("aria-pressed", String(d));
    modeInline.setAttribute("aria-pressed", String(!d));
    nameField.hidden = !d;
    render();
  }

  // palette
  const tabs = h("div.pal-tabs", { role: "tablist" });
  const grid = h("div.pal-grid");
  function showGroup(i) {
    [...tabs.children].forEach((b, j) => b.setAttribute("aria-selected", String(i === j)));
    clear(grid);
    for (const [label, snippet] of PALETTE[i][1]) {
      grid.append(h("button.pal-btn", { type: "button", title: snippet.replace(C, ""), onclick: () => insertSnippet(snippet) }, label));
    }
  }
  PALETTE.forEach(([label], i) => tabs.append(h("button.pal-tab", { type: "button", role: "tab", onclick: () => showGroup(i) }, label)));
  showGroup(0);

  function insertSnippet(snippet) {
    const a = input.selectionStart, b = input.selectionEnd;
    const v = input.value;
    const selected = v.slice(a, b);
    let s = snippet;
    let caret = s.indexOf(C);
    if (caret >= 0 && selected) {
      // wrap the selection: replace the placeholder word after the caret marker, if any
      s = s.replace(new RegExp(C + "[A-Za-z0-9_]*"), selected);
      caret = -1;
    }
    const clean = s.replace(C, "");
    const pad = a > 0 && /[A-Za-z]$/.test(v.slice(0, a)) && /^\\[A-Za-z]/.test(clean) ? " " : "";
    input.value = v.slice(0, a) + pad + clean + v.slice(b);
    const pos = a + pad.length + (caret >= 0 ? caret : clean.length);
    input.focus();
    // select the placeholder word right after the caret (e.g. the "n" in \sum_{i=1}^{n})
    const word = caret >= 0 ? (s.slice(caret + 1).match(/^[A-Za-z0-9_]+/) || [""])[0] : "";
    input.setSelectionRange(pos, pos + (word && !/^\\/.test(word) ? word.length : 0));
    render();
  }

  // describe in words
  const words = h("input.input", { type: "text", placeholder: "e.g. the softmax of z, component i", "aria-label": "Describe the equation in words" });
  const wordsBtn = h("button.btn.small", { type: "button", onclick: async () => {
      if (!words.value.trim()) { words.focus(); return; }
      wordsBtn.disabled = true; wordsBtn.textContent = "Writing…";
      try {
        const res = await api("/api/llm/equation", { words: words.value });
        input.value = res.tex;
        render();
      } catch (e) { toast(e.message, "error", 5000); }
      finally { wordsBtn.disabled = false; wordsBtn.textContent = "Write it"; }
    } }, "Write it");
  const describe = state.llm ? h("div.describe", h("span.label", "Describe in words"), h("div.row", words, wordsBtn),
    h("span.hint", "A suggestion to check, not a final answer.")) : null;

  let last = { ok: false };
  const render = debounce(async () => {
    const value = input.value.trim();
    clear(msg);
    if (!value) { fill(out, h("span.math-empty", "The equation appears here as you type.")); last = { ok: false }; insertBtn.disabled = true; return; }
    try {
      const res = await api("/api/math", { tex: display ? value : value.replace(/\s*\n\s*/g, " "), display });
      if (res.available === false) { fill(out, h("span.math-empty", "Equations are not available yet.")); last = { ok: true }; insertBtn.disabled = false; return; }
      if (res.mathml) {
        out.innerHTML = res.mathml;
        out.classList.toggle("inline", !display);
        out.classList.remove("stale");
        last = { ok: true };
      } else {
        out.classList.add("stale");
        msg.append(h("div.msg-err", h("strong", res.error), res.hint ? h("p", res.hint) : null,
          res.offset ? h("p.muted", `Line ${res.offset + 1} of the formula.`) : null));
        last = { ok: false };
      }
      insertBtn.disabled = false;
    } catch (e) { msg.append(h("div.msg-err", e.message)); }
  }, 180);
  input.addEventListener("input", render);
  input.addEventListener("keydown", (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") { e.preventDefault(); insert(); }
  });

  function insert() {
    const value = input.value.trim();
    if (!value) return;
    const nm = nameInput.value.trim().replace(/^eq:/, "");
    if (nm && !/^[A-Za-z0-9_.:-]+$/.test(nm)) { toast("A name is letters, digits and - _ . only.", "error"); nameInput.focus(); return; }
    const block = display ? `$$\n${value}\n$$${nm ? ` {#eq:${nm}}` : ""}` : `$${value.replace(/\s*\n\s*/g, " ")}$`;
    if (editing) {
      const to = editing.kind === "display" && editing.after ? editing.after[1] : editing.to;
      if (editing.kind === "display" && display) {
        view.dispatch({ changes: { from: editing.from, to, insert: block }, selection: { anchor: editing.from + block.length } });
      } else {
        view.dispatch({ changes: { from: editing.from, to, insert: display ? "\n" + block + "\n" : block } });
      }
      view.focus();
    } else if (display) {
      ed.insertBlock(block);
    } else {
      ed.insertText(block);
    }
    m.close();
    if (!last.ok) toast("Inserted. The checks will show what to fix.", "info");
  }

  const insertBtn = h("button.btn.primary", { type: "button", onclick: insert }, editing ? "Update equation" : "Insert");
  const body = h("div.eq-layout",
    h("div.eq-left",
      h("div.seg.mode", { role: "group", "aria-label": "Where the equation goes" }, modeDisplay, modeInline),
      input,
      h("div.palette", tabs, grid),
      describe),
    h("div.eq-right",
      h("span.label", "Preview"),
      out, msg, nameField));
  const m = modal({ title: editing ? "Edit equation" : "Equation", subtitle: "Write LaTeX; it is checked as you type.", body, wide: true, className: "eq-modal",
    footer: [h("span.hint", "⌘/Ctrl+Enter inserts"), h("span.grow"), h("button.btn.ghost", { type: "button", onclick: () => m.close() }, "Cancel"), insertBtn] });
  setMode(display);
  setTimeout(() => { input.focus(); input.setSelectionRange(input.value.length, input.value.length); }, 40);
}
