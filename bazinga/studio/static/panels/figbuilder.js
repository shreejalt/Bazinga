// The figure builder's form. It edits one plain object (the "spec") and calls onChange() after every edit; the
// server checks the spec, writes the figure file from it and answers with problems keyed by path
// ("curves.0.expr"), which showProblems() puts next to the right field with the bad part marked.
import { h, fill, icon } from "../lib.js";

const COLOURS = [["main", "Blue"], ["second", "Orange"], ["third", "Green"], ["fourth", "Purple"], ["muted", "Grey"],
  ["highlight", "Red"], ["good", "Bright green"], ["ink", "Black"]];
const LINES = [["", "Solid"], ["dashed", "Dashed"], ["dotted", "Dotted"], ["thick", "Thick"], ["thin", "Thin"], ["points", "Dots only"]];
const SHAPES = [["point", "Point"], ["line", "Line"], ["arrow", "Arrow"], ["circle", "Circle"], ["rect", "Rectangle"],
  ["polygon", "Polygon"], ["curve", "Curve in t"], ["text", "Text"]];
const SHAPE_FIELDS = {
  point: [["x", "x"], ["y", "y"]], text: [["x", "x"], ["y", "y"]],
  line: [["x1", "from x"], ["y1", "from y"], ["x2", "to x"], ["y2", "to y"]],
  arrow: [["x1", "from x"], ["y1", "from y"], ["x2", "to x"], ["y2", "to y"]],
  circle: [["x", "centre x"], ["y", "centre y"], ["r", "radius"]],
  rect: [["x", "corner x"], ["y", "corner y"], ["w", "width"], ["h", "height"]],
  curve: [["x", "x(t)"], ["y", "y(t)"], ["t_min", "t starts at"], ["t_max", "t ends at"]],
  polygon: [],
};
const COMMON_FUNCS = ["sin", "cos", "exp", "log", "sqrt", "abs", "min", "max", "where", "pi"];

function slugify(text) {
  return String(text || "").toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "").replace(/^(\d)/, "f_$1").slice(0, 40);
}

export function nameFromTitle(title) { return slugify(title) || "my_figure"; }

// Number fields keep what was typed when it is not a number, so the server can say so.
function toNumber(v) {
  const t = String(v).trim().replace("−", "-");
  if (t === "") return undefined;
  const n = Number(t);
  return Number.isFinite(n) ? n : t;
}

function styleParts(style, fallback = "main") {
  const words = String(style || fallback).split(/\s+/).filter(Boolean);
  const colour = words.find((w) => COLOURS.some((c) => c[0] === w)) || fallback;
  const line = words.find((w) => LINES.some((l) => l[0] === w)) || "";
  return { colour, line };
}

export function builderForm(container, initial, info, onChange) {
  let spec = initial;
  let focusedExpr = null;     // the expression input the helper strip belongs to
  let lastProblems = [];      // shown again after the form is redrawn
  const helper = h("div.fb-helper", { hidden: true, role: "toolbar", "aria-label": "Insert a name or a function" });

  const changed = () => onChange(spec);
  const rerender = () => { render(); changed(); };

  // --- field builders --------------------------------------------------------------------------------------------
  function field(label, input, { hint, wide, path } = {}) {
    return h("label.fb-field", { class: wide ? "wide" : "", "data-field": path || "" }, h("span.label", label), input, hint ? h("span.hint", hint) : null);
  }

  function textIn(obj, key, { path, placeholder = "", mono = false, number = false, rows = 0, onInput } = {}) {
    const v = obj[key] === undefined || obj[key] === null ? "" : String(obj[key]);
    const el = rows ? h("textarea.input", { rows, spellcheck: "false" }) : h("input.input", { type: "text", spellcheck: mono ? "false" : "true" });
    el.value = v;
    if (mono) el.classList.add("mono");
    if (number) { el.classList.add("num"); el.inputMode = "decimal"; }
    el.placeholder = placeholder;
    if (path) el.dataset.path = path;
    el.addEventListener("input", () => {
      if (number) { const n = toNumber(el.value); if (n === undefined) delete obj[key]; else obj[key] = n; }
      else obj[key] = el.value;
      if (onInput) onInput(el.value);
      changed();
    });
    return el;
  }

  function exprIn(obj, key, path, placeholder = "") {
    const el = textIn(obj, key, { path, placeholder, mono: true });
    el.classList.add("fb-expr");
    el.setAttribute("autocapitalize", "off");
    el.setAttribute("autocomplete", "off");
    el.addEventListener("focus", () => { focusedExpr = el; showHelper(el); });
    return el;
  }

  function select(obj, key, options, { path, onPick, value } = {}) {
    const el = h("select.select", { "data-path": path || "" }, options.map(([v, label]) => h("option", { value: v }, label)));
    el.value = value !== undefined ? value : (obj[key] === undefined ? options[0][0] : String(obj[key]));
    el.addEventListener("change", () => { if (onPick) onPick(el.value); else obj[key] = el.value; changed(); });
    return el;
  }

  function check(obj, key, label, { path, rerenderOnChange = false } = {}) {
    const box = h("input", { type: "checkbox", "data-path": path || "" });
    box.checked = !!obj[key];
    box.addEventListener("change", () => { if (box.checked) obj[key] = true; else delete obj[key]; if (rerenderOnChange) rerender(); else changed(); });
    return h("label.fb-check", box, h("span", label));
  }

  function styleSelects(obj, key, path, { lines = LINES, fallback = "main" } = {}) {
    const cur = styleParts(obj[key], fallback);
    const set = (colour, line) => { obj[key] = (colour + (line ? " " + line : "")).trim(); changed(); };
    const c = select({}, "", COLOURS, { path, value: cur.colour, onPick: (v) => { cur.colour = v; set(cur.colour, cur.line); } });
    const l = lines ? select({}, "", lines, { value: cur.line, onPick: (v) => { cur.line = v; set(cur.colour, cur.line); } }) : null;
    c.setAttribute("aria-label", "Colour");
    if (l) l.setAttribute("aria-label", "Line");
    return [field("Colour", c), l ? field("Line", l) : null];
  }

  function removeBtn(list, i, what) {
    return h("button.icon-btn.fb-remove", { type: "button", title: `Remove this ${what}`, "aria-label": `Remove this ${what}`,
      onclick: () => { list.splice(i, 1); rerender(); } }, icon("trash", 16));
  }

  function section(title, blurb, body, { open = true, path, count } = {}) {
    const d = h("details.fb-section", { open, "data-path": path || "" },
      h("summary", h("span.fb-sec-title", title), count ? h("span.fb-count", count) : null, blurb ? h("span.fb-sec-blurb", blurb) : null),
      h("div.fb-sec-body", body));
    return d;
  }

  // --- names you can use (the chip strip under an expression field) ---------------------------------------------
  function names(where) {
    const out = [];
    const t = spec.type;
    if (where === "curve") out.push("x");
    if (where === "cell") out.push("i", "j");
    if (where === "param") out.push("t");
    if (where === "surface") out.push("x", "y");
    if (where === "repeat") out.push("k");
    if (t === "distribution") {
      const fam = (info.families || {})[spec.family || "normal"];
      if (fam) out.push(...Object.keys(fam.params));
      out.push("mean", "variance", "std");
      const mode = (spec.interval || {}).mode;
      if (mode === "sigma") out.push("width");
      if (where === "readout" && (mode === "sigma" || mode === "range")) out.push("prob");
    }
    for (const c of spec.controls || []) if (c.name) out.push(c.name);
    for (const v of spec.values || []) if (v.name) out.push(v.name);
    if (where === "readout") {
      if (t === "function" || t === "data") for (const c of spec.curves || []) if (c.name) out.push(c.name);
      if (t === "bars") out.push("bars");
      if (t === "heatmap") out.push("cells");
      if (t === "data") {
        out.push(...csvColumns(spec.csv).map((c) => c.id));
        if (spec.fit === "line") out.push("slope", "intercept", "r2");
      }
    }
    return [...new Set(out)];
  }

  function showHelper(el) {
    const where = el.dataset.where || "";
    const list = names(where);
    const funcs = where === "readout" ? ["max", "min", "mean", "area", "at", "argmax", ...COMMON_FUNCS.filter((f) => !["max", "min"].includes(f))] : COMMON_FUNCS;
    fill(helper,
      h("span.fb-helper-label", "Names"),
      list.length ? list.map((n) => chip(n, n)) : h("span.muted.small", "none yet"),
      h("span.fb-helper-label", "Functions"),
      funcs.map((f) => chip(f, f === "pi" ? "pi" : f + "()")),
      chip("^", "^"),
      h("button.fb-chip.more", { type: "button", onclick: () => { const d = container.querySelector(".fb-help"); if (d) { d.open = true; d.scrollIntoView({ block: "nearest" }); } } }, "All functions…"));
    helper.hidden = false;
    (el.closest(".fb-field") || el).after(helper);
  }

  function chip(label, insert) {
    return h("button.fb-chip", { type: "button", onmousedown: (e) => e.preventDefault(), onclick: () => {
      const el = focusedExpr;
      if (!el) return;
      const s = el.selectionStart ?? el.value.length, e2 = el.selectionEnd ?? el.value.length;
      el.value = el.value.slice(0, s) + insert + el.value.slice(e2);
      const caret = s + (insert.endsWith("()") ? insert.length - 1 : insert.length);
      el.setSelectionRange(caret, caret);
      el.dispatchEvent(new Event("input"));
      el.focus();
    } }, label);
  }

  // --- the parts every type has ----------------------------------------------------------------------------------
  function basics() {
    return h("div.fb-grid",
      field("Title", textIn(spec, "title", { path: "title", placeholder: "A damped wave" }), { wide: true, hint: "Shown above the figure." }),
      field("Caption", textIn(spec, "caption", { path: "caption", rows: 2, placeholder: "What the controls do, in a sentence or two." }), { wide: true }));
  }

  function controlsSection() {
    spec.controls = spec.controls || [];
    const own = spec.controls;
    const rows = own.map((c, i) => {
      const p = `controls.${i}`;
      const kind = c.kind || "slider";
      const head = [
        field("Kind", select(c, "kind", [["slider", "Slider"], ["toggle", "Toggle"], ["steps", "Steps"]], { path: `${p}.kind`, onPick: (v) => {
          c.kind = v;
          if (v !== "slider") { c.options = c.options || (v === "toggle" ? "Off, On" : "1, 2, 3"); c.value = 0; delete c.min; delete c.max; delete c.step; delete c.play; }
          else { Object.assign(c, { min: 0, max: 1, step: 0.01, value: 0.5 }); delete c.options; }
          rerender();
        } })),
        field("Name", textIn(c, "name", { path: `${p}.name`, mono: true, placeholder: "freq" }), { hint: "Used in expressions" }),
        field("Label", textIn(c, "label", { path: `${p}.label`, placeholder: "Frequency" }), { hint: "Shown to readers" }),
      ];
      let rest;
      if (kind === "slider") {
        rest = [
          field("From", textIn(c, "min", { path: `${p}.min`, number: true })),
          field("To", textIn(c, "max", { path: `${p}.max`, number: true })),
          field("Step", textIn(c, "step", { path: `${p}.step`, number: true })),
          field("Starts at", textIn(c, "value", { path: `${p}.value`, number: true })),
          check(c, "play", "Play button", { path: `${p}.play` }),
        ];
      } else {
        const opts = Array.isArray(c.options) ? c.options.join(", ") : (c.options || "");
        const optObj = { options: opts };
        const startSel = h("select.select", { "data-path": `${p}.value` });
        const paintStart = () => {
          const list = String(optObj.options).split(",").map((s) => s.trim()).filter(Boolean);
          fill(startSel, list.map((o, k) => h("option", { value: k }, o)));
          startSel.value = String(Math.min(Number(c.value) || 0, Math.max(0, list.length - 1)));
        };
        startSel.addEventListener("change", () => { c.value = Number(startSel.value); changed(); });
        const optIn = textIn(optObj, "options", { path: `${p}.options`, placeholder: kind === "toggle" ? "Hide, Show" : "1, 3, 9",
          onInput: (v) => { c.options = v; paintStart(); } });
        paintStart();
        rest = [field(kind === "toggle" ? "Two choices" : "Choices", optIn, { wide: true, hint: kind === "steps" ? "Separated by commas. When every choice is a number, expressions get that number; otherwise its position (0, 1, …)." : "Separated by a comma. Expressions get 0 for the first, 1 for the second." }),
          field("Starts at", startSel)];
      }
      return h("div.fb-row.fb-control", { "data-path": p }, h("div.fb-row-fields", head, rest), removeBtn(own, i, "control"));
    });
    const add = (kind) => () => {
      const n = own.length + 1;
      const taken = new Set(names(""));
      let name = kind === "slider" ? "a" : kind === "toggle" ? "show" : "n";
      for (let k = 2; taken.has(name); k++) name = (kind === "slider" ? "a" : kind === "toggle" ? "show" : "n") + k;
      own.push(kind === "slider" ? { name, kind, label: `Slider ${n}`, min: 0, max: 1, step: 0.01, value: 0.5 }
        : kind === "toggle" ? { name, kind, label: "Show", options: "Off, On", value: 0 }
          : { name, kind, label: "Choose", options: "1, 2, 3", value: 0 });
      rerender();
    };
    const builtIn = spec.type === "distribution" ? h("p.hint", "The distribution's own sliders are set under What to draw; add more here if you need them.") : null;
    return section("Controls", "Sliders, toggles and steps under the figure. Each has a name you use in expressions.", [
      builtIn, rows.length ? rows : (spec.type === "distribution" ? null : h("p.fb-empty", "No controls yet. A slider is the usual start.")),
      h("div.fb-adds", h("button.btn.small", { type: "button", onclick: add("slider") }, icon("plus", 14), "Slider"),
        h("button.btn.small", { type: "button", onclick: add("toggle") }, icon("plus", 14), "Toggle"),
        h("button.btn.small", { type: "button", onclick: add("steps") }, icon("plus", 14), "Steps")),
    ], { path: "controls", count: own.length ? String(own.length) : "" });
  }

  function valuesSection() {
    spec.values = spec.values || [];
    const list = spec.values;
    const rows = list.map((v, i) => h("div.fb-row", { "data-path": `values.${i}` }, h("div.fb-row-fields",
      field("Name", textIn(v, "name", { path: `values.${i}.name`, mono: true, placeholder: "half_life" })),
      field("Is", Object.assign(exprIn(v, "expr", `values.${i}.expr`, "log(2)/d"), {}), { wide: true })),
    removeBtn(list, i, "value")));
    return section("Values", "Name a number worked out from the controls, then use the name anywhere.", [
      rows, h("div.fb-adds", h("button.btn.small", { type: "button", onclick: () => { list.push({ name: "", expr: "" }); rerender(); } }, icon("plus", 14), "Value"))],
    { open: list.length > 0, path: "values", count: list.length ? String(list.length) : "" });
  }

  function readoutsSection() {
    spec.readouts = spec.readouts || [];
    const list = spec.readouts;
    const rows = list.map((r, i) => {
      const p = `readouts.${i}`;
      const e = exprIn(r, "expr", `${p}.expr`, spec.type === "function" ? "max(wave)" : "a*2");
      e.dataset.where = "readout";
      return h("div.fb-row", { "data-path": p }, h("div.fb-row-fields",
        field("Label", textIn(r, "label", { path: `${p}.label`, placeholder: "Peak" })),
        field("Shows", e, { wide: true }),
        field("Decimals", textIn(r, "decimals", { path: `${p}.decimals`, number: true, placeholder: "auto" })),
        field("Unit", textIn(r, "unit", { path: `${p}.unit`, placeholder: "s" })),
        field("Small note", textIn(r, "note", { path: `${p}.note`, placeholder: "of at most {n}" }), { wide: true })),
      removeBtn(list, i, "readout"));
    });
    return section("Readouts", "Numbers in tiles under the figure. Use max(wave), mean(bars), area(y) … for a whole curve.", [
      rows, h("div.fb-adds", h("button.btn.small", { type: "button", onclick: () => { list.push({ label: "", expr: "" }); rerender(); } }, icon("plus", 14), "Readout"))],
    { path: "readouts", count: list.length ? String(list.length) : "" });
  }

  function allControls() {
    const out = [];
    if (spec.type === "distribution") {
      const fam = (info.families || {})[spec.family || "normal"];
      if (fam) for (const [n, d] of Object.entries(fam.params)) out.push({ name: n, kind: "slider", label: ((spec.params || {})[n] || {}).label || d.label });
      if ((spec.interval || {}).mode === "sigma") out.push({ name: "width", kind: "slider", label: "Shaded band (± σ)" });
      if (spec.cdf_toggle) out.push({ name: "show", kind: "toggle", label: "Show", options: ["Probability", "Cumulative"] });
    }
    if (spec.type === "data" && spec.fit === "line" && spec.fit_toggle) out.push({ name: "fit", kind: "toggle", label: "Fitted line", options: ["Hide", "Show"] });
    return [...out, ...(spec.controls || [])].filter((c) => c.name);
  }

  function presetsSection() {
    spec.presets = spec.presets || [];
    const list = spec.presets;
    const ctls = allControls();
    const rows = list.map((ps, i) => {
      ps.values = ps.values || {};
      const p = `presets.${i}`;
      const cells = ctls.map((c) => {
        const opts = c.kind !== "slider" ? (Array.isArray(c.options) ? c.options : String(c.options || "").split(",").map((s) => s.trim()).filter(Boolean)) : null;
        let input;
        if (opts) {
          input = h("select.select", { "data-path": `${p}.values.${c.name}` }, h("option", { value: "" }, "unchanged"), opts.map((o, k) => h("option", { value: k }, o)));
          input.value = ps.values[c.name] === undefined ? "" : String(ps.values[c.name]);
          input.addEventListener("change", () => { if (input.value === "") delete ps.values[c.name]; else ps.values[c.name] = Number(input.value); changed(); });
        } else {
          input = textIn(ps.values, c.name, { path: `${p}.values.${c.name}`, number: true, placeholder: "unchanged" });
        }
        return field(c.label || c.name, input);
      });
      return h("div.fb-row", { "data-path": p }, h("div.fb-row-fields",
        field("Button text", textIn(ps, "label", { path: `${p}.label`, placeholder: "No damping" })), cells,
        h("div.fb-pathmsg", { "data-path": `${p}.values` })), removeBtn(list, i, "preset"));
    });
    return section("Presets", "Buttons that set several controls at once, to show a case worth seeing. Reset is added for you.", [
      ctls.length ? rows : h("p.fb-empty", "Add a control first."),
      ctls.length ? h("div.fb-adds", h("button.btn.small", { type: "button", onclick: () => { list.push({ label: "", values: {} }); rerender(); } }, icon("plus", 14), "Preset")) : null],
    { open: list.length > 0, path: "presets", count: list.length ? String(list.length) : "" });
  }

  function axesFields({ x = true, y = true, logs = false, labels = true } = {}) {
    return h("div.fb-grid",
      x ? field("Smallest x", textIn(spec, "x_min", { path: "x_min", number: true })) : null,
      x ? field("Largest x", textIn(spec, "x_max", { path: "x_max", number: true })) : null,
      y ? field("Lowest y", textIn(spec, "y_min", { path: "y_min", number: true, placeholder: "auto" })) : null,
      y ? field("Highest y", textIn(spec, "y_max", { path: "y_max", number: true, placeholder: "auto" })) : null,
      labels ? field("Label across", textIn(spec, "x_label", { path: "x_label", placeholder: "time" })) : null,
      labels ? field("Label up", textIn(spec, "y_label", { path: "y_label", placeholder: "height" })) : null,
      logs ? h("div.fb-checks", check(spec, "x_log", "Log scale across", { path: "x_log" }), check(spec, "y_log", "Log scale up", { path: "y_log" }),
        check(spec, "grid", "Grid lines", { path: "grid" })) : null);
  }

  function curvesEditor(where = "curves") {
    spec.curves = spec.curves || [];
    const list = spec.curves;
    const others = list.map((c) => c.name).filter(Boolean);
    const rows = list.map((c, i) => {
      const p = `curves.${i}`;
      const e = exprIn(c, "expr", `${p}.expr`, "a*sin(f*x)");
      e.dataset.where = "curve";
      const show = exprIn(c, "show", `${p}.show`, "always");
      return h("div.fb-row.fb-curve", { "data-path": p }, h("div.fb-row-fields",
        field("Name", textIn(c, "name", { path: `${p}.name`, mono: true, placeholder: "wave" })),
        field("y =", e, { wide: true, hint: "In terms of x and your names." }),
        field("Label at its end", textIn(c, "label", { path: `${p}.label`, placeholder: "none" })),
        ...styleSelects(c, "style", `${p}.style`, { fallback: ["main", "second", "third", "fourth", "muted"][Math.min(i, 4)] }),
        field("Shade", select(c, "fill", [["", "Nothing"], ["zero", "Down to 0"], ...others.filter((n) => n !== c.name).map((n) => [n, `Between it and ${n}`])], { path: `${p}.fill`, value: c.fill || "" })),
        field("Shown when", show, { hint: "Optional, e.g. env (a toggle)" })),
      removeBtn(list, i, "curve"));
    });
    return [rows, h("div.fb-adds", h("button.btn.small", { type: "button", onclick: () => {
      const taken = new Set(list.map((c) => c.name));
      let name = "y"; for (let k = 2; taken.has(name); k++) name = "y" + k;
      list.push({ name, label: name, expr: "" }); rerender();
    } }, icon("plus", 14), where === "overlay" ? "Curve on top" : "Curve"))];
  }

  function marksEditor(axisChoice = true) {
    spec.marks = spec.marks || [];
    const list = spec.marks;
    return [list.map((m, i) => {
      const p = `marks.${i}`;
      const e = exprIn(m, "expr", `${p}.expr`, "half");
      e.dataset.where = "readout";
      return h("div.fb-row", { "data-path": p }, h("div.fb-row-fields",
        axisChoice ? field("Line", select(m, "axis", [["x", "Up and down, at x ="], ["y", "Across, at y ="]], { path: `${p}.axis` })) : null,
        field(axisChoice ? "Position" : "At height", e, { wide: true }),
        field("Label", textIn(m, "label", { path: `${p}.label`, placeholder: "T = {t:.2f}" })),
        ...styleSelects(m, "style", `${p}.style`, { lines: null, fallback: "muted" })),
      removeBtn(list, i, "line"));
    }), h("div.fb-adds", h("button.btn.small", { type: "button", onclick: () => { list.push({ axis: axisChoice ? "x" : "y", expr: "", label: "" }); rerender(); } }, icon("plus", 14), "Reference line"))];
  }

  function pointsEditor() {
    spec.points = spec.points || [];
    const list = spec.points;
    return [list.map((q, i) => {
      const p = `points.${i}`;
      const ex = exprIn(q, "x", `${p}.x`, "argmax(wave)");
      const ey = exprIn(q, "y", `${p}.y`, "max(wave)");
      ex.dataset.where = ey.dataset.where = "readout";
      return h("div.fb-row", { "data-path": p }, h("div.fb-row-fields",
        field("x", ex), field("y", ey), field("Label", textIn(q, "label", { path: `${p}.label`, placeholder: "peak" })),
        ...styleSelects(q, "style", `${p}.style`, { lines: null, fallback: "highlight" })),
      removeBtn(list, i, "point"));
    }), h("div.fb-adds", h("button.btn.small", { type: "button", onclick: () => { list.push({ x: "", y: "", label: "" }); rerender(); } }, icon("plus", 14), "Marked point"))];
  }

  // --- what to draw, per type ------------------------------------------------------------------------------------
  const TYPE_PARTS = {
    function() {
      return [
        section("Curves", "One or more curves y = expression in x.", curvesEditor(), { path: "curves" }),
        section("Axes", "Where x runs, and the y range (fix it so the picture does not jump as the sliders move).", [
          axesFields({ logs: true }),
          h("div.fb-grid", field("Points per curve", textIn(spec, "samples", { path: "samples", number: true, placeholder: "200" }), { hint: "200 is plenty; at most 1000." }),
            field("Title above the plot", textIn(spec, "panel_title", { path: "panel_title", placeholder: "optional, e.g. T = {t:.1f}" }), { wide: true }))]),
        section("Reference lines and points", "Lines at an x or a y, and labelled points (both may move with the controls).", [marksEditor(), pointsEditor()],
          { open: (spec.marks || []).length + (spec.points || []).length > 0 }),
      ];
    },
    shapes() {
      spec.items = spec.items || [];
      const list = spec.items;
      const rows = list.map((it, i) => {
        const p = `items.${i}`;
        const kind = it.type || "point";
        const fields = SHAPE_FIELDS[kind].map(([k, label]) => {
          const e = exprIn(it, k, `${p}.${k}`, k.startsWith("t_") ? (k === "t_min" ? "0" : "2*pi") : "0");
          if (kind === "curve" && (k === "x" || k === "y")) e.dataset.where = "param";
          if (it.repeat) e.dataset.where = e.dataset.where || "repeat";
          return field(label, e);
        });
        if (kind === "polygon") {
          const ta = textIn(it, "points", { path: `${p}.points`, rows: 3, mono: true, placeholder: "0, 0\n1, 0\n1, a" });
          fields.push(field("Corners, one per line: x, y", ta, { wide: true }));
        }
        return h("div.fb-row", { "data-path": p }, h("div.fb-row-fields",
          field("Shape", select(it, "type", SHAPES, { path: `${p}.type`, onPick: (v) => { it.type = v; rerender(); } })),
          ...fields,
          field(kind === "text" ? "Text" : "Label", textIn(it, "label", { path: `${p}.label`, placeholder: kind === "text" ? "P = ({cos(a):.2f}, {sin(a):.2f})" : "optional" }), { wide: kind === "text" }),
          ...styleSelects(it, "style", `${p}.style`, { lines: [["", "Solid"], ["dashed", "Dashed"], ["thick", "Thick"], ["thin", "Thin"], ["outline", "Outline only"]] }),
          field("Repeat", textIn(it, "repeat", { path: `${p}.repeat`, mono: true, placeholder: "once" }), { hint: "Draw it n times; k = 0, 1, 2 … inside." })),
        removeBtn(list, i, "shape"));
      });
      return [
        section("Shapes", "Each number is an expression, so shapes move with the controls. Labels can show numbers: {a:.2f}.", [rows,
          h("div.fb-adds", SHAPES.map(([k, label]) => h("button.btn.small", { type: "button", onclick: () => {
            const d = { point: { x: "0", y: "0" }, line: { x1: "0", y1: "0", x2: "1", y2: "1" }, arrow: { x1: "0", y1: "0", x2: "1", y2: "1" },
              circle: { x: "0", y: "0", r: "1" }, rect: { x: "0", y: "0", w: "1", h: "1" }, polygon: { points: "0, 0\n1, 0\n0, 1" },
              curve: { x: "cos(t)", y: "sin(t)", t_min: "0", t_max: "2*pi" }, text: { x: "0", y: "0", label: "text" } }[k];
            list.push({ type: k, ...d }); rerender();
          } }, icon("plus", 14), label)))], { path: "items" }),
        section("View", "The part of the plane shown.", [axesFields({ logs: false, labels: true }),
          h("div.fb-checks", check(spec, "axes", "Axes with numbers", { path: "axes" }), check(spec, "grid", "Grid", { path: "grid" }),
            check(spec, "origin", "Lines through 0", { path: "origin" }),
            (() => { const box = h("input", { type: "checkbox" }); box.checked = spec.equal !== false;
              box.addEventListener("change", () => { if (box.checked) delete spec.equal; else spec.equal = false; changed(); });
              return h("label.fb-check", box, h("span", "Same scale across and up")); })())]),
      ];
    },
    bars() {
      spec.bars = spec.bars || [];
      const list = spec.bars;
      const rows = list.map((b, i) => {
        const p = `bars.${i}`;
        const e = exprIn(b, "expr", `${p}.expr`, "0.5");
        if (b.repeat) e.dataset.where = "repeat";
        return h("div.fb-row", { "data-path": p }, h("div.fb-row-fields",
          field("Label", textIn(b, "label", { path: `${p}.label`, placeholder: "Rent" })),
          field("Height", e, { wide: true }),
          ...styleSelects(b, "style", `${p}.style`, { lines: null }),
          field("Repeat", textIn(b, "repeat", { path: `${p}.repeat`, mono: true, placeholder: "once" }), { hint: "n bars, k = 0, 1, … in label and height" })),
        removeBtn(list, i, "bar"));
      });
      return [
        section("Bars", "One row per bar. Heights are expressions; a repeated row makes many bars from one formula.", [rows,
          h("div.fb-adds", h("button.btn.small", { type: "button", onclick: () => { list.push({ label: "", expr: "" }); rerender(); } }, icon("plus", 14), "Bar"))], { path: "bars" }),
        section("Look", "", [h("div.fb-grid",
          field("Highlight", select(spec, "highlight", [["", "No bar"], ["max", "The tallest"], ["min", "The shortest"]], { path: "highlight" })),
          field("Decimals on the bars", textIn(spec, "decimals", { path: "decimals", number: true, placeholder: "auto" })),
          field("Bars start at", textIn(spec, "y_min", { path: "y_min", number: true, placeholder: "auto" })),
          field("Axis goes up to", textIn(spec, "y_max", { path: "y_max", number: true, placeholder: "auto" })),
          field("Label up", textIn(spec, "y_label", { path: "y_label" })),
          field("Label across", textIn(spec, "x_label", { path: "x_label" }))),
        h("div.fb-checks", check(spec, "horizontal", "Lying down (horizontal bars)", { path: "horizontal" }),
          (() => { const box = h("input", { type: "checkbox" }); box.checked = spec.show_values !== false;
            box.addEventListener("change", () => { if (box.checked) delete spec.show_values; else spec.show_values = false; changed(); });
            return h("label.fb-check", box, h("span", "Numbers on the bars")); })())]),
        section("Reference lines", "Lines across at a height, e.g. mean(bars).", marksEditor(false), { open: (spec.marks || []).length > 0 }),
      ];
    },
    heatmap() {
      const cell = exprIn(spec, "expr", "expr", "sin(i*a)*cos(j*a)");
      cell.dataset.where = "cell";
      return [
        section("Cells", "Each cell's value is an expression in its row i and column j (both counted from 0).", [h("div.fb-grid",
          field("Rows", textIn(spec, "rows", { path: "rows", mono: true, placeholder: "8" })),
          field("Columns", textIn(spec, "cols", { path: "cols", mono: true, placeholder: "8" })),
          field("Each cell is", cell, { wide: true }),
          field("Row labels", textIn(spec, "row_labels", { path: "row_labels", placeholder: "a, b, c  or  row {i+1}" }), { wide: true }),
          field("Column labels", textIn(spec, "col_labels", { path: "col_labels", placeholder: "Mon, Tue  or  {j}" }), { wide: true }))]),
        section("Colours", "Fix the range so colours mean the same thing as the controls move.", [h("div.fb-grid",
          field("Colour range, lowest", textIn(spec, "range_min", { path: "range_min", number: true, placeholder: "auto" })),
          field("Colour range, highest", textIn(spec, "range_max", { path: "range_max", number: true, placeholder: "auto" })),
          field("Decimals", textIn(spec, "decimals", { path: "decimals", number: true, placeholder: "auto" })),
          field("Legend title", textIn(spec, "legend", { path: "legend" })),
          field("Label across", textIn(spec, "x_label", { path: "x_label" }))),
        h("div.fb-checks", check(spec, "show_values", "Numbers in the cells", { path: "show_values" }))]),
      ];
    },
    distribution() {
      const fams = info.families || {};
      const famName = spec.family || "normal";
      const fam = fams[famName];
      spec.params = spec.params || {};
      const params = fam ? Object.entries(fam.params).map(([n, d]) => {
        const o = spec.params[n] = spec.params[n] || {};
        const p = `params.${n}`;
        const ph = (k) => String(d[k]);
        return h("div.fb-row", { "data-path": p }, h("div.fb-row-fields",
          h("div.fb-param-name", h("strong", d.label), h("span.fp-name", n)),
          field("From", textIn(o, "min", { path: `${p}.min`, number: true, placeholder: ph("min") })),
          field("To", textIn(o, "max", { path: `${p}.max`, number: true, placeholder: ph("max") })),
          field("Step", textIn(o, "step", { path: `${p}.step`, number: true, placeholder: ph("step") })),
          field("Starts at", textIn(o, "value", { path: `${p}.value`, number: true, placeholder: ph("value") }))));
      }) : [];
      spec.interval = spec.interval || { mode: "none" };
      const iv = spec.interval;
      const lo = exprIn(iv, "lo", "interval.lo", "mean - 1");
      const hi = exprIn(iv, "hi", "interval.hi", "mean + 1");
      return [
        section("Distribution", "Its parameters become sliders; the mean, variance and standard deviation are shown under it.", [
          h("div.fb-family", Object.entries(fams).map(([k, f]) => h("button.fb-fam", { type: "button", "aria-pressed": String(k === famName),
            onclick: () => { spec.family = k; spec.params = {}; rerender(); } }, h("strong", f.label), h("span", f.discrete ? "counts 0, 1, 2 …" : "any number")))),
          params]),
        section("Shading", "Shade part of it and show the chance of landing there.", [h("div.fb-grid",
          field("Shade", select(iv, "mode", [["none", "Nothing"], ["sigma", "Within ± a number of standard deviations (a slider)"], ["range", "From one value to another"]], { path: "interval.mode", onPick: (v) => { iv.mode = v; rerender(); } }), { wide: true }),
          iv.mode === "range" ? field("From", lo) : null, iv.mode === "range" ? field("To", hi) : null),
        h("div.fb-checks", check(spec, "cdf_toggle", "Let readers switch to the cumulative chance", { path: "cdf_toggle", rerenderOnChange: true }),
          (() => { const box = h("input", { type: "checkbox" }); box.checked = spec.show_moments !== false;
            box.addEventListener("change", () => { if (box.checked) delete spec.show_moments; else spec.show_moments = false; changed(); });
            return h("label.fb-check", box, h("span", "Show mean, variance and standard deviation")); })())]),
        section("Axes", "The range across is worked out to fit every slider position; set it yourself if you prefer.", [h("div.fb-grid",
          field("Smallest x", textIn(spec, "x_min", { path: "x_min", number: true, placeholder: "auto" })),
          field("Largest x", textIn(spec, "x_max", { path: "x_max", number: true, placeholder: "auto" })),
          field("Axis goes up to", textIn(spec, "y_max", { path: "y_max", number: true, placeholder: "auto" })),
          field("Label across", textIn(spec, "x_label", { path: "x_label", placeholder: "x" })))], { open: false }),
      ];
    },
    data() {
      const cols = csvColumns(spec.csv);
      const colOpts = cols.map((c) => [c.header, c.header]);
      const ycur = new Set((Array.isArray(spec.y) ? spec.y : spec.y ? [spec.y] : []).map(String));
      const resolve = (v) => { const c = cols.find((c2) => c2.header === v || c2.id === v); return c ? c.header : v; };
      const ys = cols.map((c) => {
        const box = h("input", { type: "checkbox" });
        box.checked = ycur.has(c.header) || ycur.has(c.id);
        box.addEventListener("change", () => {
          const now = new Set((Array.isArray(spec.y) ? spec.y : []).map(resolve));
          if (box.checked) now.add(c.header); else now.delete(c.header);
          spec.y = cols.map((c2) => c2.header).filter((x) => now.has(x));
          changed();
        });
        return h("label.fb-check", box, h("span", c.header));
      });
      return [
        section("The table", "Paste it from a spreadsheet: a first line of column names, then one row per line (commas, semicolons or tabs).", [
          field("Table", textIn(spec, "csv", { path: "csv", rows: 7, mono: true, placeholder: "year, sales\n2021, 4.2\n2022, 5.1", onInput: () => { clearTimeout(textTimer); textTimer = setTimeout(rerenderKeepFocus, 600); } }), { wide: true }),
          cols.length ? h("p.hint", `${cols.length} columns, ${csvRows(spec.csv)} rows.`) : null]),
        section("Chart", "", [h("div.fb-grid",
          field("Draw as", select(spec, "chart", [["line", "Lines"], ["scatter", "Dots"], ["bar", "Bars"]], { path: "chart", onPick: (v) => { spec.chart = v; rerender(); } })),
          cols.length ? field("Across (x)", select(spec, "x", colOpts, { path: "x", value: resolve(spec.x || (cols[0] || {}).header) || "" })) : null,
          spec.chart !== "bar" ? field("Fitted line", select(spec, "fit", [["none", "None"], ["line", "Straight line (least squares)"]], { path: "fit", onPick: (v) => { spec.fit = v; rerender(); } })) : null),
        cols.length ? h("div.fb-field.wide", { "data-path": "y" }, h("span.label", "Columns to draw"), h("div.fb-checks", ys)) : null,
        spec.fit === "line" && spec.chart !== "bar" ? h("div.fb-checks", check(spec, "fit_toggle", "A toggle to hide or show the fitted line", { path: "fit_toggle", rerenderOnChange: true })) : null,
        axesFields({ x: false, logs: spec.chart !== "bar" })]),
        spec.chart !== "bar" ? section("Curves on top", "Optional: a curve y = expression in x drawn over the data, e.g. a model to fit by hand with sliders.", curvesEditor("overlay"), { open: (spec.curves || []).length > 0, path: "curves" }) : null,
      ];
    },
  };

  // 3-D scene: rows of points, segments and boxes whose coordinates are expressions, and a surface z = f(x, y)
  TYPE_PARTS.scene3d = function () {
    const coordRows = (key, fields, what, extra) => {
      spec[key] = spec[key] || [];
      const list = spec[key];
      return list.map((it, i) => {
        const p = `${key}.${i}`;
        const coords = fields.map(([k, label]) => {
          const e = exprIn(it, k, `${p}.${k}`, "0");
          if (it.repeat) e.dataset.where = "repeat";
          return field(label, e);
        });
        return h("div.fb-row", { "data-path": p }, h("div.fb-row-fields", ...coords, ...extra(it, p),
          ...styleSelects(it, "style", `${p}.style`, { lines: key === "segments" ? [["", "Solid"], ["dashed", "Dashed"], ["thick", "Thick"], ["thin", "Thin"]] : null,
            fallback: key === "segments" ? "ink" : "main" })),
        removeBtn(list, i, what));
      });
    };
    const labelAndRepeat = (it, p) => [
      field("Label", textIn(it, "label", { path: `${p}.label`, placeholder: "optional, e.g. P" })),
      field("Repeat", textIn(it, "repeat", { path: `${p}.repeat`, mono: true, placeholder: "once" }), { hint: "n times; k = 0, 1, 2 … inside" })];
    const P3 = [["x", "x"], ["y", "y"], ["z", "z (up)"]];
    const S6 = [["x1", "from x"], ["y1", "from y"], ["z1", "from z"], ["x2", "to x"], ["y2", "to y"], ["z2", "to z"]];
    const B6 = [["x1", "corner x"], ["y1", "corner y"], ["z1", "corner z"], ["x2", "opposite x"], ["y2", "opposite y"], ["z2", "opposite z"]];
    const surf = exprIn(spec, "surface", "surface", "a*sin(x)*cos(y)");
    surf.dataset.where = "surface";
    spec.view = Array.isArray(spec.view) ? spec.view : [35, 25];
    const viewIn = (i, label, hint) => {
      const el = h("input.input.num", { type: "text", inputmode: "decimal", "data-path": "view" });
      el.value = String(spec.view[i]);
      el.addEventListener("input", () => { const n = toNumber(el.value); spec.view[i] = n === undefined ? 0 : n; changed(); });
      return field(label, el, { hint });
    };
    const add = (key, label, d) => h("button.btn.small", { type: "button", onclick: () => { (spec[key] = spec[key] || []).push(d); rerender(); } }, icon("plus", 14), label);
    return [
      section("Surface", "Optional: a surface z = expression in x and y, coloured by height. Leave it empty for none.", [h("div.fb-grid",
        field("z =", surf, { wide: true }),
        field("Pieces along each side", textIn(spec, "samples", { path: "samples", number: true, placeholder: "16" }), { hint: "4 to 24; more is smoother and slower" }))]),
      section("Points", "Each coordinate is an expression, so points move with the controls.", [
        coordRows("points", P3, "point", labelAndRepeat),
        h("div.fb-adds", add("points", "Point", { x: "0", y: "0", z: "0", label: "" }))], { path: "points", open: (spec.points || []).length > 0 || !spec.surface }),
      section("Segments and arrows", "Straight lines from one point to another.", [
        coordRows("segments", S6, "segment", (it, p) => [check(it, "arrow", "Arrow at the end", { path: `${p}.arrow` }), ...labelAndRepeat(it, p)]),
        h("div.fb-adds", add("segments", "Segment", { x1: "0", y1: "0", z1: "0", x2: "1", y2: "1", z2: "1" }))], { path: "segments", open: (spec.segments || []).length > 0 }),
      section("Boxes", "A box between two opposite corners, with see-through sides.", [
        coordRows("boxes", B6, "box", (it, p) => [(() => { const box = h("input", { type: "checkbox" }); box.checked = it.faces !== false;
          box.addEventListener("change", () => { if (box.checked) delete it.faces; else it.faces = false; changed(); });
          return h("label.fb-check", box, h("span", "Shaded sides")); })()]),
        h("div.fb-adds", add("boxes", "Box", { x1: "-0.5", y1: "-0.5", z1: "-0.5", x2: "0.5", y2: "0.5", z2: "0.5" }))], { path: "boxes", open: (spec.boxes || []).length > 0 }),
      section("View", "The box the scene fills (z is up), and where the reader looks from at first. Readers turn the picture by dragging it.", [h("div.fb-grid",
        ...["x", "y", "z"].flatMap((a) => [
          field(`Smallest ${a}`, textIn(spec, `${a}_min`, { path: `${a}_min`, number: true, placeholder: a === "z" ? "-1" : "-2" })),
          field(`Largest ${a}`, textIn(spec, `${a}_max`, { path: `${a}_max`, number: true, placeholder: a === "z" ? "1" : "2" }))]),
        viewIn(0, "Turned by (degrees)", "around the up axis"),
        viewIn(1, "Looking down by (degrees)", "0 is level, 89 from straight above")),
      h("div.fb-checks",
        (() => { const box = h("input", { type: "checkbox" }); box.checked = spec.axes !== false;
          box.addEventListener("change", () => { if (box.checked) delete spec.axes; else spec.axes = false; changed(); });
          return h("label.fb-check", box, h("span", "Axes")); })(),
        (() => { const box = h("input", { type: "checkbox" }); box.checked = spec.ticks !== false;
          box.addEventListener("change", () => { if (box.checked) delete spec.ticks; else spec.ticks = false; changed(); });
          return h("label.fb-check", box, h("span", "Numbers on the axes")); })())]),
    ];
  };

  let textTimer = null;
  function rerenderKeepFocus() {
    const active = document.activeElement;
    const path = active && active.dataset ? active.dataset.path : null;
    const pos = active && "selectionStart" in active ? [active.selectionStart, active.selectionEnd] : null;
    render();
    if (path) {
      const el = container.querySelector(`[data-path="${CSS.escape(path)}"]`);
      if (el) { el.focus(); if (pos && el.setSelectionRange) el.setSelectionRange(pos[0], pos[1]); }
    }
  }

  function helpSection() {
    const fns = (info.functions || []).map((f) => h("li", h("code", `${f.name}()`), " ", f.help));
    const aggs = (info.aggregates || []).map((f) => h("li", h("code", `${f.name}(list)`), " ", f.help));
    return h("details.fb-help", h("summary", icon("info", 15), "How to write expressions"),
      h("div.fb-help-body",
        h("p", "Write maths the way you would on paper: ", h("code", "a*sin(f*x)*exp(-d*x)"), ", ", h("code", "x^2 + 1"), ", ",
          h("code", "2pi r"), ". Use ", h("code", "^"), " for powers, ", h("code", "pi"), " and ", h("code", "e"), " for the constants, and the names you gave your controls and values."),
        h("p", "Comparisons give 1 or 0, so ", h("code", "(x > 0) * x"), " is x on the right and 0 on the left; ",
          h("code", "where(x > 0, log(x), 0)"), " picks between two expressions. Where an expression has no value (the log of a negative number, a division by 0) the curve simply leaves a gap."),
        h("p", "In labels, notes and titles, put an expression in braces to show its value: ", h("code", "T = {t:.2f}"), " shows t with two decimals."),
        h("div.fb-help-cols", h("div", h("h5", "Functions"), h("ul", fns)), h("div", h("h5", "Of a whole list (readouts)"), h("ul", aggs)))));
  }

  // --- render ----------------------------------------------------------------------------------------------------
  function render() {
    const parts = TYPE_PARTS[spec.type] ? TYPE_PARTS[spec.type]() : [];
    fill(container,
      basics(),
      h("div.fb-type-row", h("span.label", "What to draw"), h("strong", ((info.types || []).find((t) => t.type === spec.type) || {}).label || spec.type)),
      parts,
      controlsSection(),
      valuesSection(),
      readoutsSection(),
      presetsSection(),
      section("Note", "One line of text under the readouts (optional).", [field("Note", textIn(spec, "note", { path: "note", placeholder: "Half-life {log(2)/d:.2f}" }), { wide: true })], { open: !!spec.note }),
      helpSection());
    helper.hidden = true;
    if (lastProblems.length) placeProblems(lastProblems);
  }

  // --- problems from the server ----------------------------------------------------------------------------------
  function showProblems(problems) {
    lastProblems = problems || [];
    return placeProblems(lastProblems);
  }

  function placeProblems(problems) {
    for (const el of container.querySelectorAll(".fb-bad")) el.classList.remove("fb-bad");
    for (const el of container.querySelectorAll(".fb-msg")) el.remove();
    const placed = [];
    for (const p of problems || []) {
      let path = p.path || "";
      let el = null;
      while (path && !el) {
        el = container.querySelector(`[data-path="${CSS.escape(path)}"]`);
        if (!el) path = path.includes(".") ? path.slice(0, path.lastIndexOf(".")) : "";
      }
      const msg = h("div.fb-msg", { role: "alert" }, icon("alert", 14), h("span", p.message));
      if (p.text && p.col !== null && p.col !== undefined) {
        const a = Math.max(0, Math.min(p.col, p.text.length)), b = Math.max(a + 1, Math.min(p.end ?? a + 1, p.text.length));
        msg.append(h("code.fb-where", p.text.slice(0, a), h("mark", p.text.slice(a, b) || " "), p.text.slice(b)));
      }
      if (el) {
        if (el.matches("input, textarea, select")) el.classList.add("fb-bad");
        if (el.tagName === "DETAILS") el.open = true;
        const anchor = el.closest(".fb-field") || el;
        const parent = el.closest("details");
        if (parent) parent.open = true;
        anchor.after(msg);
      } else {
        container.prepend(msg);
      }
      placed.push({ problem: p, el, msg });
    }
    return placed;
  }

  render();
  return {
    get spec() { return spec; },
    setSpec(next) { spec = next; render(); },
    showProblems,
    focusPath(path) {
      const el = container.querySelector(`[data-path="${CSS.escape(path)}"]`);
      if (el) { const d = el.closest("details"); if (d) d.open = true; el.scrollIntoView({ block: "center", behavior: "smooth" }); if (el.focus) el.focus(); }
    },
  };
}

// --- tables (only to offer the column names; the server parses the table itself) ------------------------------
export function csvColumns(text) {
  const first = String(text || "").trim().split(/\r?\n/)[0] || "";
  if (!first) return [];
  const delim = first.includes("\t") ? "\t" : (first.split(";").length > first.split(",").length ? ";" : ",");
  const taken = new Set();
  return first.split(delim).map((raw, i) => {
    const header = raw.trim().replace(/^"|"$/g, "") || `column ${i + 1}`;
    let id = slugify(header) || "column";
    let n = 2; const base = id;
    while (taken.has(id)) id = `${base}_${n++}`;
    taken.add(id);
    return { header, id };
  });
}

function csvRows(text) {
  return Math.max(0, String(text || "").trim().split(/\r?\n/).filter((l) => l.trim()).length - 1);
}
