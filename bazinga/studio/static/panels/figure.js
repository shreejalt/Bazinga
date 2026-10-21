// The figure panel: a gallery of the site's figures (drawn live), a page per figure (working preview, insert it
// at the cursor, optionally opened at a preset), and three ways to make one: fill in a form (no code), start from
// an example (code), or describe it (when suggestions are on). Code opens in an editor beside a live preview with
// the figure's test in plain words; a failing line is marked.
import { api, store, h, clear, fill, modal, icon, toast, debounce, modKey } from "../lib.js";
import { codeEditor, goToLine } from "../cm.js";
import { isDark } from "../studio.js";
import { builderForm, nameFromTitle } from "./figbuilder.js";
import { StateField, StateEffect } from "@codemirror/state";
import { EditorView, Decoration } from "@codemirror/view";

const NAME_RE = /^[a-z][a-z0-9_]{0,40}$/;
let builderInfo = null;

function ensureCss(href) {
  if (document.querySelector(`link[data-fg="${href}"]`)) return;
  document.head.append(h("link", { rel: "stylesheet", href, "data-fg": href }));
}

const TYPE_PICTURES = {
  function: "M3 15c3 0 3-9 6-9s3 12 6 12 3-6 6-6",
  shapes: "M12 4a8 8 0 1 0 0 16 8 8 0 0 0 0-16zM12 12l5-4M12 12h.01",
  bars: "M5 20V12M10 20V6M15 20V9M20 20V14",
  heatmap: "M4 4h5v5H4zM10 4h5v5h-5zM16 4h4v5h-4zM4 10h5v5H4zM10 10h5v5h-5zM16 10h4v5h-4zM4 16h5v4H4zM10 16h5v4h-5zM16 16h4v4h-4z",
  distribution: "M3 19c4 0 5-13 9-13s5 13 9 13M3 19h18",
  data: "M5 17l3-4 3 2 4-6 4 3M5 6h.01M9 9h.01M13 5h.01",
};

function picture(type) {
  const svg = icon("dot", 34);
  svg.querySelector("path").setAttribute("d", TYPE_PICTURES[type] || TYPE_PICTURES.function);
  return svg;
}

// Frames grow to fit the figure they show.
function fitFrame(frame) {
  const size = () => {
    try {
      const d = frame.contentDocument;
      if (!d || !d.documentElement) return;
      frame.style.height = Math.min(1600, Math.max(140, d.documentElement.scrollHeight)) + "px";
    } catch (e) { /* not ready */ }
  };
  frame.addEventListener("load", () => {
    size();
    try { new ResizeObserver(size).observe(frame.contentDocument.body); } catch (e) { /* older browsers */ }
  });
  return frame;
}

// A stage that swaps in a new frame only once it has loaded, so the preview never flashes empty.
function stage() {
  const el = h("div.fg-stage");
  let current = null;
  let latest = null;
  return {
    el,
    show(url) {
      const next = fitFrame(h("iframe.fg-frame", { title: "Preview of the figure", src: url }));
      latest = next;
      next.classList.add("loading");
      next.addEventListener("load", () => {
        if (next !== latest) { next.remove(); return; }      // a newer preview is on its way
        next.classList.remove("loading");
        for (const f of el.querySelectorAll("iframe")) if (f !== next && f !== latest) f.remove();
        for (const e of el.querySelectorAll(".fg-stage-empty")) e.remove();
        current = next;
      }, { once: true });
      el.append(next);
      el.classList.remove("stale");
    },
    stale(on) { el.classList.toggle("stale", !!on); },
    empty(text) { fill(el, h("div.fg-stage-empty", text)); current = null; },
  };
}

function theme() { return isDark() ? "dark" : "light"; }
function withTheme(url) { return url + (url.includes("?") ? "&" : "?") + "theme=" + theme(); }

function checksList(report) {
  if (!report) return null;
  const items = (report.checks || []).map((c) => h("li", { class: c.ok ? "ok" : "bad" },
    icon(c.ok ? "check" : "x", 15), h("div", h("span", c.label), c.detail ? h("pre", c.detail) : null)));
  return h("ul.fg-checks", items);
}

const MADE = { builder: "Made with the form", edited: "Form, then code", code: "Code" };

export async function open(ed) {
  ensureCss("/_studio/panels/figure.css");
  ensureCss("/assets/css/figure.css");
  const main = h("div.fg-main");
  let cleanup = null;          // the current view's teardown (editor, timers)
  let leaveCheck = null;       // () => true when it is fine to leave the current view
  const m = modal({
    title: "Figures", subtitle: "Interactive figures: readers move the controls and the picture follows.",
    body: main, wide: true, className: "fg-modal",
    onClose: () => { if (cleanup) cleanup(); },
  });

  async function go(view, ...args) {
    if (leaveCheck && !leaveCheck()) {
      if (!confirm("Leave without saving? Your changes to this figure will be lost.")) return;
    }
    if (cleanup) cleanup();
    cleanup = null;
    leaveCheck = null;
    main.scrollTop = 0;
    await view(...args);
  }

  function crumbs(...parts) {
    const out = [h("button.fg-crumb", { type: "button", onclick: () => go(gallery) }, "All figures")];
    for (const p of parts) out.push(h("span.fg-crumb-sep", "›"), typeof p === "string" ? h("span.fg-crumb.now", p) : p);
    return h("nav.fg-crumbs", { "aria-label": "Where you are" }, out);
  }

  function insert(name, preset) {
    ed.insertBlock(`::figure ${name}${preset ? ` | start: ${preset}` : ""}`);
    m.close();
    toast(`Placed ${name} in the text.`, "ok");
  }

  function presetPicker(presets) {
    if (!presets || !presets.length) return null;
    return h("select.select.fg-start", { "aria-label": "Open it at" },
      h("option", { value: "" }, "At its starting values"), presets.map((p) => h("option", { value: p }, `At “${p}”`)));
  }

  // --- the gallery -------------------------------------------------------------------------------------------------
  async function gallery() {
    const grid = h("div.fg-grid", { "aria-busy": "true" });
    const search = h("input.input.fg-search", { type: "search", placeholder: "Find a figure", "aria-label": "Find a figure" });
    fill(main, h("div.fg-gallery-head", h("div", h("h3", "Your figures"), h("p.muted", "Pick one to see it working and place it in the text, or make a new one.")),
      search), grid);
    const newCard = h("button.fg-card.fg-new", { type: "button", onclick: () => go(choose) },
      h("div.fg-thumb", icon("plus", 30)), h("div.fg-card-body", h("strong", "New figure"), h("span.muted", "With a form, from an example, or described")));
    grid.append(newCard);
    for (let k = 0; k < Math.min(3, store.state.figures.length); k++) grid.append(h("div.fg-card.skeleton", h("div.fg-thumb"), h("div.fg-card-body", h("span"), h("span"))));
    let res;
    try { res = await api("/api/figures/gallery"); }
    catch (e) { grid.append(h("p.form-error", e.message)); return; }
    grid.removeAttribute("aria-busy");
    for (const s of grid.querySelectorAll(".skeleton")) s.remove();
    if (res.available === false) { grid.append(h("p.muted", "Figures are not available yet.")); return; }
    const cards = res.figures.map((f) => {
      const thumb = h("div.fg-thumb");
      if (f.ok) thumb.innerHTML = f.svg; else thumb.append(h("div.fg-thumb-err", icon("alert", 20), h("span", "Does not draw")));
      const card = h("button.fg-card", { type: "button", "data-name": f.name, onclick: () => go(detail, f.name) }, thumb,
        h("div.fg-card-body", h("strong", f.title || f.name), h("span.fp-name", f.name),
          h("span.fg-badges", h("span.fg-badge", { class: `made-${f.made}` }, MADE[f.made] || f.made),
            f.controls ? h("span.fg-badge.plain", `${f.controls} control${f.controls === 1 ? "" : "s"}`) : null),
          h("span.fg-used", f.used_in && f.used_in.length ? `In: ${f.used_in.join(", ")}` : "Not used in a page yet")));
      card.dataset.search = `${f.name} ${f.title || ""} ${f.caption || ""}`.toLowerCase();
      return card;
    });
    grid.append(...cards);
    if (cards.length < 7) search.hidden = true;
    search.addEventListener("input", () => {
      const q = search.value.trim().toLowerCase();
      for (const c of cards) c.hidden = q && !c.dataset.search.includes(q);
    });
  }

  // --- one figure --------------------------------------------------------------------------------------------------
  async function detail(name) {
    const f = store.state.figures.find((x) => x.name === name) || { name, presets: [] };
    const st = stage();
    st.el.classList.add("fg-stage-detail");
    const pick = presetPicker(f.presets);
    const url = () => withTheme(`/frame/figure/${encodeURIComponent(name)}${pick && pick.value ? `?start=${encodeURIComponent(pick.value)}` : ""}`);
    if (pick) pick.addEventListener("change", () => st.show(url()));
    const madeBox = h("span.fg-badge", "…");
    const editBtn = h("button.btn", { type: "button", disabled: true }, icon("pen", 16), h("span", "Change it"));
    fill(main, crumbs(f.title || name),
      h("div.fg-detail-head",
        h("div", h("h3", f.title || name), f.caption ? h("p.muted", f.caption) : null,
          h("p.fg-meta", h("span.fp-name", `figures/${name}.py`), madeBox)),
        h("div.fg-detail-actions", editBtn, pick,
          h("button.btn.primary", { type: "button", onclick: () => insert(name, pick && pick.value) }, icon("plus", 16), h("span", "Place in the text")))),
      st.el,
      h("p.hint", `It goes in the text as ::figure ${name}` + (f.presets && f.presets.length ? ", optionally opened at one of its presets." : ".")));
    st.show(url());
    try {
      const o = await api(`/api/figures/open?name=${encodeURIComponent(name)}`);
      fill(madeBox, MADE[o.made] || o.made);
      madeBox.className = `fg-badge made-${o.made}`;
      editBtn.disabled = false;
      if (o.made === "builder") {
        fill(editBtn, icon("sliders", 16), h("span", "Change it with the form"));
        editBtn.onclick = () => go(builder, { name, spec: o.spec, isNew: false });
        editBtn.after(h("button.btn.ghost", { type: "button", onclick: () => go(codeView, { name, source: o.source, made: o.made }) }, icon("code", 16), h("span", "Its code")));
      } else {
        fill(editBtn, icon("code", 16), h("span", "Change its code"));
        editBtn.onclick = () => go(codeView, { name, source: o.source, made: o.made });
      }
    } catch (e) { fill(madeBox, ""); toast(e.message, "error"); }
  }

  // --- making a new one ----------------------------------------------------------------------------------------
  function choose() {
    const ways = [
      { id: "form", title: "Fill in a form", text: "No code. Pick a kind of figure, write expressions like a*sin(f*x), add sliders, and watch it work as you type.", icon: "sliders", go: () => go(pickType) },
      { id: "example", title: "Start from an example", text: "A working figure file with a comment on every part. Change it to make it yours.", icon: "code", go: () => go(pickStarter) },
    ];
    if (store.state.llm) ways.push({ id: "describe", title: "Describe it", text: "Say in a sentence what it should show. A draft is written for you to read, test and change.", icon: "wand", go: () => go(describe) });
    fill(main, crumbs("New figure"),
      h("div.fg-head", h("h3", "How do you want to make it?"), h("p.muted", "Every way ends in the same kind of file, so you can switch later: a form-made figure can be opened as code.")),
      h("div.fg-ways", ways.map((w) => h("button.fg-way", { type: "button", "data-way": w.id, onclick: w.go }, icon(w.icon, 26), h("strong", w.title), h("span", w.text)))));
  }

  async function info() {
    if (!builderInfo) builderInfo = await api("/api/builder/info");
    return builderInfo;
  }

  async function pickType() {
    let bi;
    try { bi = await info(); } catch (e) { toast(e.message, "error"); return; }
    if (bi.available === false) { fill(main, crumbs("New figure", "With a form"), h("p.muted", "The figure builder is not available yet.")); return; }
    fill(main, crumbs(h("button.fg-crumb", { type: "button", onclick: () => go(choose) }, "New figure"), "With a form"),
      h("div.fg-head", h("h3", "What should it draw?"), h("p.muted", "Each kind starts as a small working example; change it into yours.")),
      h("div.fg-types", bi.types.map((t) => h("button.fg-type", { type: "button", "data-type": t.type, onclick: () => {
        const spec = JSON.parse(JSON.stringify(bi.examples[t.type]));
        go(builder, { name: uniqueName(nameFromTitle(spec.title)), spec, isNew: true });
      } }, picture(t.type), h("strong", t.label), h("span", t.blurb)))));
  }

  function uniqueName(base) {
    const taken = new Set(store.state.figures.map((f) => f.name));
    let n = base, k = 2;
    while (taken.has(n)) n = `${base}_${k++}`;
    return n;
  }

  async function pickStarter() {
    let starters = { figures: [] };
    try { starters = await api("/api/starters"); } catch (e) { /* shown as empty */ }
    const list = starters.figures || [];
    let chosen = list.length ? list[0].name : null;
    const name = h("input.input.mono", { type: "text", spellcheck: "false", value: uniqueName(chosen || "my_figure"), "aria-label": "Name" });
    let nameTouched = false;
    name.addEventListener("input", () => { nameTouched = true; });
    const err = h("p.form-error");
    const cards = h("div.fg-starters", list.map((s, i) => h("button.starter", { type: "button", "aria-pressed": String(i === 0), onclick: (e) => {
      chosen = s.name;
      if (!nameTouched) name.value = uniqueName(s.name);
      for (const c of cards.children) c.setAttribute("aria-pressed", String(c === e.currentTarget));
    } }, h("strong", s.title), h("span", s.caption || s.name.replace(/_/g, " ")))));
    const create = h("button.btn.primary", { type: "button", onclick: async () => {
      const nm = name.value.trim();
      if (!NAME_RE.test(nm)) { err.textContent = "A name is lowercase letters, digits and _ , starting with a letter."; name.focus(); return; }
      create.disabled = true;
      try {
        const res = await api("/api/figures/new", { name: nm, starter: chosen });
        await ed.refreshState();
        go(codeView, { name: nm, source: res.source, made: "code", fresh: true });
      } catch (e) { err.textContent = e.message; create.disabled = false; }
    } }, "Create it");
    fill(main, crumbs(h("button.fg-crumb", { type: "button", onclick: () => go(choose) }, "New figure"), "From an example"),
      h("div.fg-head", h("h3", "Pick an example to start with"), h("p.muted", "Each one works as it is and explains itself in comments.")),
      list.length ? cards : h("p.muted", "Examples are not available yet."),
      h("div.fg-row", h("label.field", h("span.label", "Name"), name, h("span.hint", "Used in the text as ::figure name")), h("span.grow"), create), err);
  }

  function describe() {
    const name = h("input.input.mono", { type: "text", spellcheck: "false", placeholder: "softmax_bars", "aria-label": "Name" });
    const text = h("textarea.input", { rows: 4, placeholder: "A slider for the temperature and bars showing the softmax of five scores", "aria-label": "Describe the figure" });
    const err = h("p.form-error");
    const btn = h("button.btn.primary", { type: "button", onclick: async () => {
      const nm = name.value.trim();
      if (!NAME_RE.test(nm)) { err.textContent = "A name is lowercase letters, digits and _ , starting with a letter."; name.focus(); return; }
      if (!text.value.trim()) { text.focus(); return; }
      btn.disabled = true; btn.textContent = "Writing a draft…";
      try {
        const res = await api("/api/figures/draft", { name: nm, description: text.value });
        go(codeView, { name: nm, source: res.source, made: "code", unsaved: true, draft: res });
      } catch (e) { err.textContent = e.message; btn.disabled = false; btn.textContent = "Write a draft"; }
    } }, "Write a draft");
    fill(main, crumbs(h("button.fg-crumb", { type: "button", onclick: () => go(choose) }, "New figure"), "Described"),
      h("div.fg-head", h("h3", "Describe the figure"), h("p.muted", "You get a draft to read and test. Nothing is saved until you save it.")),
      h("label.field", h("span.label", "What should it show?"), text),
      h("div.fg-row", h("label.field", h("span.label", "Name"), name), h("span.grow"), btn), err);
  }

  // --- the builder -------------------------------------------------------------------------------------------------
  async function builder({ name, spec, isNew }) {
    let bi;
    try { bi = await info(); } catch (e) { toast(e.message, "error"); return; }
    let saved = !isNew;
    let dirty = false;
    let lastGood = null;
    const formHost = h("div.fb-form");
    const nameIn = h("input.input.mono", { type: "text", spellcheck: "false", value: name, "aria-label": "Name", "data-path": "name", disabled: !isNew });
    let nameTouched = !isNew;
    const status = h("div.fg-status", { role: "status", "aria-live": "polite" });
    const st = stage();
    const checks = h("div.fg-checks-box");
    const fixes = h("div.fg-fixes");
    const codePre = h("pre.fg-code-pre");
    const codeBox = h("details.fg-code-peek", h("summary", icon("code", 15), "The code it writes"), codePre);
    const pick = h("select.select.fg-start", { "aria-label": "Open it at", hidden: true });
    const saveBtn = h("button.btn", { type: "button", onclick: () => save(false) }, "Save");
    const insertBtn = h("button.btn.primary", { type: "button", onclick: () => save(true) }, icon("plus", 16), h("span.long", "Save and place in the text"), h("span.short", "Save, place"));
    const toCode = h("button.btn.ghost", { type: "button", onclick: () => {
      if (!lastGood) { toast("Fix the form first, so there is code to open.", "error"); return; }
      if (!confirm("Open this figure as code? Once you change the code by hand, the form will not open it again (your code is kept).")) return;
      const unsavedNow = !saved || dirty;
      dirty = false;
      go(codeView, { name: currentName(), source: lastGood.source, made: "builder", unsaved: unsavedNow, fromBuilder: true });
    } }, icon("code", 16), h("span", "Open as code"));

    const currentName = () => nameIn.value.trim();
    const form = builderForm(formHost, spec, bi, () => {
      dirty = true;
      if (isNew && !nameTouched) nameIn.value = uniqueName(nameFromTitle(form.spec.title));
      refresh();
    });
    nameIn.addEventListener("input", () => { nameTouched = true; dirty = true; refresh(); });
    leaveCheck = () => !dirty;

    let seq = 0;
    const refresh = debounce(async () => {
      const nm = currentName();
      if (!NAME_RE.test(nm)) { setStatus("bad", "The name must be lowercase letters, digits and _ , starting with a letter."); return; }
      const my = ++seq;
      setStatus("busy", "Updating…");
      let res;
      try { res = await api("/api/builder/preview", { name: nm, spec: form.spec }); }
      catch (e) { if (my === seq) setStatus("bad", e.message); return; }
      if (my !== seq) return;
      const placed = form.showProblems(res.problems || []);
      if (res.problems && res.problems.length) {
        setStatus("bad", `${res.problems.length === 1 ? "One thing" : `${res.problems.length} things`} to fix in the form`);
        fill(fixes, h("ul", placed.map(({ problem }) => h("li", h("button.fg-fix", { type: "button", onclick: () => form.focusPath(problem.path) },
          icon("alert", 14), h("span", problem.message))))));
        st.stale(!!lastGood);
        return;
      }
      clear(fixes);
      lastGood = res;
      codePre.textContent = res.source;
      fill(checks, checksList(res.report));
      if (res.frame) st.show(withTheme(res.frame));
      const presets = (form.spec.presets || []).map((p) => p.label).filter(Boolean);
      fill(pick, h("option", { value: "" }, "At its starting values"), presets.map((p) => h("option", { value: p }, `At “${p}”`)));
      pick.hidden = !presets.length;
      setStatus(res.ok ? "ok" : "bad", res.ok ? "Works, and passes its test" : "Draws, but its test found a problem");
    }, 450);

    function setStatus(kind, text) {
      status.className = `fg-status ${kind}`;
      fill(status, kind === "busy" ? h("span.spinner") : icon(kind === "ok" ? "check" : kind === "bad" ? "alert" : "info", 16), h("span", text));
    }

    async function save(andInsert, replace = false) {
      const nm = currentName();
      if (!NAME_RE.test(nm)) { toast("The name must be lowercase letters, digits and _ , starting with a letter.", "error"); nameIn.focus(); return; }
      saveBtn.disabled = insertBtn.disabled = true;
      try {
        const res = await api("/api/builder/save", { name: nm, spec: form.spec, create: isNew && !saved, replace });
        if (res.problems && res.problems.length) {
          form.showProblems(res.problems);
          toast("The form has something to fix first.", "error");
          return;
        }
        saved = true;
        dirty = false;
        isNew = false;
        nameIn.disabled = true;
        await ed.refreshState();
        if (!res.ok) toast("Saved, but its test found a problem: see the checks.", "error", 5000);
        else toast(`Saved figures/${nm}.py`, "ok");
        fill(checks, checksList(res.report));
        if (andInsert) insert(nm, pick.hidden ? "" : pick.value);
      } catch (e) {
        if (e.status === 409 && /changed by hand|written or changed/.test(e.message)) {
          if (confirm(e.message + " Replace it with what the form makes?")) return save(andInsert, true);
        } else toast(e.message, "error", 5000);
      } finally { saveBtn.disabled = insertBtn.disabled = false; }
    }

    const typeLabel = (bi.types.find((t) => t.type === spec.type) || {}).label || spec.type;
    fill(main,
      crumbs(isNew ? h("button.fg-crumb", { type: "button", onclick: () => go(pickType) }, "New figure") : h("button.fg-crumb", { type: "button", onclick: () => go(detail, name) }, spec.title || name),
        isNew ? `${typeLabel}, with a form` : "The form"),
      h("div.fg-build",
        h("div.fg-form-col",
          h("div.fb-name", h("label.fb-field", h("span.label", "Name"), nameIn,
            h("span.hint", isNew ? "The file figures/name.py, and ::figure name in the text." : "Saved as figures/" + name + ".py."))),
          formHost),
        h("aside.fg-preview-col", { "aria-label": "Preview" }, status, fixes, st.el, checks, codeBox)),
      h("div.fg-bar", h("button.btn.ghost", { type: "button", onclick: () => go(isNew ? pickType : detail, isNew ? undefined : name) }, icon("back", 16), h("span", "Back")),
        toCode, h("span.grow"), pick, saveBtn, insertBtn));
    st.empty("Drawing the figure…");
    refresh.flush();
    cleanup = () => refresh.cancel();
  }

  // --- code ------------------------------------------------------------------------------------------------------
  async function codeView({ name, source, made = "code", unsaved = false, draft = null, fresh = false, fromBuilder = false }) {
    const host = h("div.fg-editor");
    const status = h("div.fg-status", { role: "status", "aria-live": "polite" });
    const st = stage();
    const checks = h("div.fg-checks-box");
    const note = h("div.fg-note");
    let dirty = unsaved;
    let autoRun = !(draft && draft.ran === false);   // a model's draft that is not plain computation runs only on request
    let created = !unsaved;
    const saveBtn = h("button.btn", { type: "button", onclick: () => save(false) }, h("span", "Save"), h("kbd", `${modKey()} S`));
    const insertBtn = h("button.btn.primary", { type: "button", onclick: () => save(true) }, icon("plus", 16), h("span.long", "Save and place in the text"), h("span.short", "Save, place"));
    const runBtn = h("button.btn", { type: "button", hidden: autoRun, onclick: () => { autoRun = true; runBtn.hidden = true; check.flush(); } }, icon("play", 16), h("span", "Run it to check"));

    // the failing line, marked in the editor
    const setBad = StateEffect.define();
    const badLine = StateField.define({
      create: () => Decoration.none,
      update(deco, tr) {
        deco = deco.map(tr.changes);
        for (const e of tr.effects) if (e.is(setBad)) {
          deco = e.value && e.value <= tr.state.doc.lines
            ? Decoration.set([Decoration.line({ class: "fg-bad-line" }).range(tr.state.doc.line(e.value).from)]) : Decoration.none;
        }
        return deco;
      },
      provide: (f) => EditorView.decorations.from(f),
    });

    if (made === "edited") note.append(h("p", icon("info", 15), " This figure was made with the form and then changed by hand, so it opens as code. Your changes are kept."));
    if (fromBuilder) note.append(h("p", icon("info", 15), " This is the code the form wrote. Once you change it here, the form will not open this figure again."));
    if (draft && draft.ran === false) note.append(h("p.warn", icon("alert", 15), " ", (draft.problems || [])[0] || "Read this draft before running it."));
    if (fresh) note.append(h("p", icon("info", 15), " The comments explain each part. Change something and the preview follows."));

    fill(main, crumbs(created ? h("button.fg-crumb", { type: "button", onclick: () => go(detail, name) }, name) : name, "Code"),
      note,
      h("div.fg-build.code",
        h("div.fg-editor-col", h("div.fg-file", icon("doc", 15), h("span.fp-name", `figures/${name}.py`), h("span.grow"), h("span.hint", "The preview follows as you type")), host),
        h("aside.fg-preview-col", { "aria-label": "Preview" }, status, runBtn, st.el, checks)),
      h("div.fg-bar", h("button.btn.ghost", { type: "button", onclick: () => go(created ? detail : gallery, name) }, icon("back", 16), h("span", "Back")),
        h("span.grow"), saveBtn, insertBtn));

    function setStatus(kind, text) {
      status.className = `fg-status ${kind}`;
      fill(status, kind === "busy" ? h("span.spinner") : icon(kind === "ok" ? "check" : kind === "bad" ? "alert" : "info", 16), h("span", text));
    }

    function showReport(report) {
      const lineNo = report && report.line;
      fill(checks, checksList(report));
      // a failing test is read first, above the picture; a passing one sits under it
      if (report && !report.ok) st.el.before(checks); else st.el.after(checks);
      if (lineNo) {
        checks.prepend(h("button.btn.small.fg-goto", { type: "button", onclick: () => goToLine(view, lineNo) }, icon("alert", 14), h("span", `Go to line ${lineNo}`)));
      }
      view.dispatch({ effects: setBad.of(lineNo || 0) });
    }

    let seq = 0;
    const check = debounce(async () => {
      if (!autoRun) return;
      const my = ++seq;
      setStatus("busy", "Checking…");
      let res;
      try { res = await api("/api/figures/check", { name, source: view.state.doc.toString() }); }
      catch (e) { if (my === seq) setStatus("bad", e.message); return; }
      if (my !== seq) return;
      showReport(res.report);
      if (res.frame) st.show(withTheme(res.frame)); else st.stale(true);
      setStatus(res.ok ? "ok" : "bad", res.ok ? (dirty ? "Works (not saved yet)" : "Works, and passes its test") : "Needs fixing: see below");
    }, 900);

    async function save(andInsert) {
      saveBtn.disabled = insertBtn.disabled = true;
      setStatus("busy", "Saving and testing…");
      try {
        const exists = store.state.figures.some((f) => f.name === name);
        const res = await api("/api/figures/save-code", { name, source: view.state.doc.toString(), create: !exists });
        created = true;
        dirty = false;
        await ed.refreshState();
        showReport(res.report);
        st.show(withTheme(`/frame/figure/${encodeURIComponent(name)}`));
        setStatus(res.ok ? "ok" : "bad", res.ok ? "Saved, and passes its test" : "Saved, but its test found a problem");
        if (andInsert) {
          if (!res.ok && !confirm("Its test found a problem. Place it in the text anyway?")) return;
          insert(name, "");
        }
      } catch (e) { setStatus("bad", e.message); }
      finally { saveBtn.disabled = insertBtn.disabled = false; }
    }

    const view = await codeEditor(host, source, {
      onChange: () => { dirty = true; check(); },
      keys: [{ key: "Mod-s", run: () => { save(false); return true; }, preventDefault: true }],
      extensions: [badLine],
    });
    leaveCheck = () => !dirty;
    cleanup = () => { check.cancel(); view.destroy(); };
    if (autoRun) { check.flush(); }
    else { setStatus("info", "Not run yet"); st.empty("Read the draft, then run it to see it."); }
  }

  // --- start ---------------------------------------------------------------------------------------------------
  await gallery();
}
