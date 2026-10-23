// The Editor: title and summary, the Markdown surface, the live preview, autosave, checks, drawers and dialogs.
import { api, store, h, clear, icon, pill, toast, debounce, modKey, ApiError, uploadImage, pickFile, IMAGE_ACCEPT, anyLayerOpen, fill, previewURL } from "./lib.js";
import { markdownEditor, makeCompletions, insertBlock, wrapSelection, insertText, goToLine, startCompletion, EditorView } from "./cm.js";
import { createPreview } from "./preview.js";
import { mathExtensions } from "./mathtips.js";
import { diagramButtons } from "./panels/diagram.js";
import { go, themeButton, refreshState } from "./studio.js";

const SPLIT_KEY = "bazinga-studio-split";
const PREVIEW_KEY = "bazinga-studio-preview";

export async function openEditor(app, id) {
  const state = store.state;
  const page = await api(`/api/page?id=${encodeURIComponent(id)}`);
  const ed = {
    id, page, meta: page.meta || {}, base: page.hash, state: page.state, view: null, dirty: false, saving: false,
    issues: [], bodyLine: 1, checksAvailable: true, destroyed: false, forcedSlash: false,
  };

  // --- layout ----------------------------------------------------------------------------------------------------------
  const saveState = h("span.save-state", { "aria-live": "polite" }, "Saved");
  const pillBox = h("span.pill-box", pill(page.state));
  const checksBtn = h("button.btn.ghost.checks-btn", { title: "Checks", onclick: () => toggleDrawer("checks") }, icon("check", 16), h("span.lbl", "Checks"));
  const previewBtn = h("button.icon-btn", { title: `Preview (${modKey()}+P)`, "aria-label": "Show or hide the preview", onclick: () => togglePreview() }, icon("eye"));
  const publishBtn = h("button.btn.primary", { onclick: () => openPanel("publish") }, h("span", page.state === "published" ? "Publish changes" : "Publish"));
  const topbar = h("header.ed-top",
    h("div.ed-top-left",
      h("button.btn.ghost.back", { onclick: () => go("#/"), title: "All pages" }, icon("back", 16), h("span", "Pages")),
      h("span.sep"), pillBox, saveState),
    h("div.ed-top-right",
      h("button.icon-btn", { title: "Versions", "aria-label": "Earlier versions", onclick: () => openPanel("history") }, icon("history")),
      h("button.btn.ghost", { title: "Title, summary, topics, series, date", onclick: () => toggleDrawer("details") }, icon("sliders", 16), h("span.lbl", "Details")),
      checksBtn, previewBtn, themeButton(), publishBtn));

  const titleInput = h("textarea.title-input", { rows: 1, placeholder: "Title", "aria-label": "Title", spellcheck: "true" });
  const summaryInput = h("textarea.summary-input", { rows: 1, placeholder: "A two- or three-sentence summary, shown in lists and on the map", "aria-label": "Summary", spellcheck: "true" });
  titleInput.value = ed.meta.title || "";
  summaryInput.value = ed.meta.summary || "";
  const cmHost = h("div.cm-host");
  const toolbar = h("div.toolbar", { role: "toolbar", "aria-label": "Insert" });
  const writeScroll = h("div.write-scroll", h("div.write-col", titleInput, summaryInput, h("div.write-rule"), cmHost));
  const writePane = h("section.pane.write", toolbar, writeScroll);
  const previewHost = h("div.preview-host");
  const deviceBtns = h("div.seg", { role: "group", "aria-label": "Preview width" },
    h("button.seg-btn", { "aria-pressed": "true", title: "Wide", onclick: (e) => device("wide", e.currentTarget) }, icon("desktop", 15)),
    h("button.seg-btn", { "aria-pressed": "false", title: "Phone width", onclick: (e) => device("phone", e.currentTarget) }, icon("phone", 15)));
  const previewPane = h("section.pane.preview",
    h("div.preview-bar", h("span.preview-label", "Preview"), h("span.preview-ms"), h("span.grow"), deviceBtns,
      h("a.icon-btn", { href: previewURL(`/preview/${encodeURIComponent(id)}`), target: "_blank", rel: "noopener", title: "Open the preview in a new tab" }, icon("external", 16))),
    previewHost);
  const splitter = h("div.splitter", { role: "separator", "aria-orientation": "vertical", "aria-label": "Resize", tabindex: "0" });
  const drawer = h("aside.drawer", { "aria-label": "Side panel", hidden: true });
  const conflict = h("div.banner", { hidden: true });
  const main = h("div.ed-main", writePane, splitter, previewPane, drawer);
  const root = h("div.editor", topbar, conflict, main);
  app.append(root);

  let split = 52;
  try { split = Number(localStorage.getItem(SPLIT_KEY)) || 52; } catch (e) { /* ignore */ }
  let showPreview = true;
  try { showPreview = localStorage.getItem(PREVIEW_KEY) !== "0"; } catch (e) { /* ignore */ }
  const narrow = () => innerWidth < 980;
  if (narrow()) showPreview = false;
  function layout() {
    main.style.setProperty("--split", `${split}%`);
    main.classList.toggle("no-preview", !showPreview);
    main.classList.toggle("only-preview", showPreview && narrow());
    previewBtn.setAttribute("aria-pressed", String(showPreview));
  }
  layout();

  // --- the editor --------------------------------------------------------------------------------------------------
  const completionContext = () => ({
    pages: state.pages || [], references: store.state.references, figures: store.state.figures,
    drawings: store.state.drawings, slash: commandList(), forcedSlash: ed.forcedSlash,
  });
  ed.view = markdownEditor(cmHost, page.body || "", {
    onChange: () => { ed.forcedSlash = false; changed(); },
    completions: makeCompletions(completionContext),
    keys: [
      { key: "Mod-s", run: () => { save(true); return true; }, preventDefault: true },
      { key: "Mod-p", run: () => { togglePreview(); return true; }, preventDefault: true },
      { key: "Mod-/", run: (v) => { slashAtCursor(v); return true; }, preventDefault: true },
      { key: "Mod-b", run: (v) => { wrapSelection(v, "**", "**", "bold"); return true; } },
      { key: "Mod-i", run: (v) => { wrapSelection(v, "*", "*", "italic"); return true; } },
      { key: "Mod-k", run: () => { openPanel("link"); return true; } },
      { key: "Mod-m", run: () => { openPanel("equation"); return true; } },
    ],
    onPaste: (e) => handleFiles(e.clipboardData && e.clipboardData.files, e),
    onDrop: (e, v) => {
      const pos = v.posAtCoords({ x: e.clientX, y: e.clientY });
      if (pos !== null && e.dataTransfer && e.dataTransfer.files.length) v.dispatch({ selection: { anchor: pos } });
      return handleFiles(e.dataTransfer && e.dataTransfer.files, e);
    },
    extensions: [...mathExtensions({ onEdit: () => openPanel("equation"), modLabel: modKey() }),
      ...diagramButtons((_v, pos) => openPanel("diagram", { at: pos }))],
  });
  ed.insertBlock = (text, off) => insertBlock(ed.view, text, off);
  ed.insertText = (text) => insertText(ed.view, text);
  ed.goToLine = (n) => goToLine(ed.view, n);

  function slashAtCursor(v) {
    const sel = v.state.selection.main;
    const line = v.state.doc.lineAt(sel.head);
    const before = line.text.slice(0, sel.head - line.from);
    const insert = before === "" || /\s$/.test(before) ? "/" : " /";
    ed.forcedSlash = true;
    v.dispatch({ changes: { from: sel.head, insert }, selection: { anchor: sel.head + insert.length } });
    ed.forcedSlash = true;
    startCompletion(v);
  }

  function handleFiles(files, e) {
    const imgs = files ? [...files].filter((f) => f.type.startsWith("image/")) : [];
    if (!imgs.length) return false;
    e.preventDefault();
    for (const f of imgs) uploadAndInsert(f);
    return true;
  }

  async function uploadAndInsert(file) {
    try {
      toast("Uploading the image…");
      const res = await uploadImage(file, page.slug);
      const alt = file.name.replace(/\.[^.]+$/, "").replace(/[-_]+/g, " ");
      ed.insertBlock(`![${alt}](${res.path} "")`, 2);
      toast("Image added. Describe it in the brackets (that is the text for screen readers).", "ok", 4500);
    } catch (err) { toast(err.message, "error", 5000); }
  }
  ed.uploadAndInsert = uploadAndInsert;

  // --- title, summary, meta -------------------------------------------------------------------------------------------
  const autosize = (ta) => { ta.style.height = "auto"; ta.style.height = ta.scrollHeight + "px"; };
  for (const ta of [titleInput, summaryInput]) {
    ta.addEventListener("input", () => autosize(ta));
    ta.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        if (ta === titleInput) summaryInput.focus(); else ed.view.focus();
      }
    });
    requestAnimationFrame(() => autosize(ta));
  }
  titleInput.addEventListener("input", () => { setMeta({ title: titleInput.value.replace(/\s+/g, " ") }); });
  summaryInput.addEventListener("input", () => { setMeta({ summary: summaryInput.value.replace(/\s+/g, " ") }); });

  function setMeta(patch, { silent = false } = {}) {
    for (const [k, v] of Object.entries(patch)) {
      if (v === undefined || v === null || v === "" || (Array.isArray(v) && !v.length)) delete ed.meta[k];
      else ed.meta[k] = v;
    }
    if ("title" in patch && document.activeElement !== titleInput) { titleInput.value = ed.meta.title || ""; autosize(titleInput); }
    if ("summary" in patch && document.activeElement !== summaryInput) { summaryInput.value = ed.meta.summary || ""; autosize(summaryInput); }
    if (!silent) changed();
  }
  ed.setMeta = setMeta;

  // --- saving, preview, checks ---------------------------------------------------------------------------------------
  const payload = () => ({ id: ed.id, meta: ed.meta, body: ed.view.state.doc.toString() });
  const autosave = debounce(() => save(false), 2000);
  const previewSoon = debounce(() => renderPreview(), 300);
  const checkSoon = debounce(() => runChecks(), 900);

  function changed() {
    ed.dirty = true;
    saveState.textContent = "Edited";
    saveState.className = "save-state pending";
    autosave();
    previewSoon();
    checkSoon();
  }

  let saveQueued = false;
  async function save(explicit, force = false, quiet = false) {
    if (ed.destroyed) return true;
    if (ed.saving) { saveQueued = true; return false; }
    if (!ed.dirty && !explicit) return true;
    autosave.cancel();
    ed.saving = true;
    saveState.textContent = "Saving…";
    saveState.className = "save-state saving";
    const wasDirty = ed.dirty;
    ed.dirty = false;
    try {
      const res = await api("/api/page/save", { ...payload(), base: ed.base, explicit, force });
      ed.base = res.hash;
      saveState.textContent = "Saved";
      saveState.className = "save-state saved";
      if (res.state !== ed.state) { ed.state = res.state; fill(pillBox, pill(res.state)); }
      conflict.hidden = true;
      if (explicit && !quiet) toast("Saved, with a version you can go back to.", "ok", 2200);
      return true;
    } catch (e) {
      ed.dirty = ed.dirty || wasDirty;
      if (e.status === 409) showConflict();
      saveState.textContent = e.status === 409 ? "Not saved" : "Not saved: " + e.message;
      saveState.className = "save-state error";
      return false;
    } finally {
      ed.saving = false;
      if (saveQueued) { saveQueued = false; if (ed.dirty) save(false); }
    }
  }
  ed.save = save;

  function showConflict() {
    fill(conflict, icon("alert", 16),
      h("span", "This page was changed outside the Editor since you opened it."),
      h("button.btn.small", { onclick: () => location.reload() }, "Load the file"),
      h("button.btn.small.ghost", { onclick: () => save(true, true) }, "Keep my version"));
    conflict.hidden = false;
  }

  const preview = createPreview(previewHost, id, { onReady: () => syncScroll() });
  async function renderPreview() {
    if (!showPreview || ed.destroyed) return;
    try {
      const res = await api("/api/preview", payload());
      if (res.html) {
        preview.update(res.html);
        preview.setNote("");
        previewPane.querySelector(".preview-ms").textContent = "";
      } else if (res.unavailable) {
        preview.setNote("The preview is not available yet.", "info");
      } else {
        const line = res.line && res.body_line ? Math.max(1, res.line - res.body_line + 1) : null;
        preview.setNote(`The preview stopped${line ? ` at line ${line}` : ""}: ${res.error}${res.hint ? ` (${res.hint})` : ""}`, "error");
      }
    } catch (e) { preview.setNote(e.message, "error"); }
  }

  async function runChecks() {
    if (ed.destroyed) return;
    try {
      const res = await api("/api/check", payload());
      ed.checksAvailable = res.available !== false;
      ed.issues = res.issues || [];
      ed.bodyLine = res.body_line || 1;
      paintChecksButton();
      if (drawerKind === "checks" && drawerApi && drawerApi.refresh) drawerApi.refresh();
    } catch (e) { /* the next edit retries */ }
  }
  ed.runChecks = runChecks;

  function paintChecksButton() {
    const errs = ed.issues.filter((i) => i.level === "error").length;
    const warns = ed.issues.length - errs;
    checksBtn.classList.toggle("has-err", errs > 0);
    checksBtn.classList.toggle("has-warn", !errs && warns > 0);
    clear(checksBtn);
    if (!ed.checksAvailable) {
      checksBtn.append(icon("check", 16), h("span.lbl", "Checks"));
      checksBtn.title = "Checks are not available yet";
      return;
    }
    const label = errs ? (errs === 1 ? "1 error" : `${errs} errors`) : warns ? (warns === 1 ? "1 warning" : `${warns} warnings`) : "Checks pass";
    checksBtn.append(icon(errs || warns ? "alert" : "check", 16), h("span.lbl", label));
    checksBtn.title = "Open the checks";
  }

  // editor line of an issue (the editor shows the body only)
  ed.editorLine = (fileLine) => (fileLine && fileLine >= ed.bodyLine ? fileLine - ed.bodyLine + 1 : null);

  // --- scroll sync ---------------------------------------------------------------------------------------------------
  const hostTop = () => cmHost.getBoundingClientRect().top - writeScroll.getBoundingClientRect().top + writeScroll.scrollTop;
  function editorAnchors() {
    const out = [];
    const doc = ed.view.state.doc;
    const top = hostTop();
    let inFence = false;
    for (let i = 1; i <= doc.lines; i++) {
      const text = doc.line(i).text;
      if (/^\s*(```|~~~)/.test(text)) { inFence = !inFence; continue; }
      if (inFence) continue;
      let kind = null;
      if (/^#{1,6}\s/.test(text)) kind = "h";
      else if (/^\s*::(figure|drawing)\b/.test(text)) kind = "fig";
      else if (/^\s*\$\$/.test(text)) {
        kind = "math";
        if (!/\$\$.*\$\$/.test(text)) { while (i < doc.lines && !doc.line(i + 1).text.includes("$$")) i++; i++; }
      }
      if (kind) {
        const lineNo = kind === "math" ? Math.min(i, doc.lines) : i;
        const block = ed.view.lineBlockAt(doc.line(kind === "math" ? lineNo : i).from);
        out.push({ kind, y: top + block.top });
      }
    }
    return out;
  }
  let syncing = false;
  function syncScroll() {
    if (!showPreview || syncing) return;
    syncing = true;
    requestAnimationFrame(() => {
      syncing = false;
      try { preview.syncTo(writeScroll.scrollTop, editorAnchors(), writeScroll.scrollHeight - writeScroll.clientHeight, hostTop() - 40); } catch (e) { /* preview not ready */ }
    });
  }
  writeScroll.addEventListener("scroll", syncScroll, { passive: true });

  // --- splitter, preview toggle, device --------------------------------------------------------------------------------
  splitter.addEventListener("pointerdown", (e) => {
    e.preventDefault();
    splitter.setPointerCapture(e.pointerId);
    main.classList.add("resizing");
    const rect = main.getBoundingClientRect();
    const move = (ev) => { split = Math.min(75, Math.max(30, ((ev.clientX - rect.left) / rect.width) * 100)); layout(); };
    const up = () => {
      main.classList.remove("resizing");
      splitter.removeEventListener("pointermove", move);
      try { localStorage.setItem(SPLIT_KEY, String(Math.round(split))); } catch (err) { /* ignore */ }
    };
    splitter.addEventListener("pointermove", move);
    splitter.addEventListener("pointerup", up, { once: true });
  });
  splitter.addEventListener("keydown", (e) => {
    if (e.key === "ArrowLeft") { split = Math.max(30, split - 2); layout(); }
    if (e.key === "ArrowRight") { split = Math.min(75, split + 2); layout(); }
  });
  function togglePreview() {
    showPreview = !showPreview;
    try { localStorage.setItem(PREVIEW_KEY, showPreview ? "1" : "0"); } catch (e) { /* ignore */ }
    layout();
    if (showPreview) { renderPreview(); setTimeout(syncScroll, 120); } else ed.view.focus();
  }
  function device(kind, btn) {
    for (const b of deviceBtns.children) b.setAttribute("aria-pressed", String(b === btn));
    previewHost.classList.toggle("phone", kind === "phone");
  }
  const onResize = () => layout();
  addEventListener("resize", onResize);

  // --- commands: toolbar and "/" menu ------------------------------------------------------------------------------
  function commandList() {
    const v = ed.view;
    return [
      { id: "heading", label: "Heading", detail: "## A section title", icon: "heading", run: () => toggleHeading(v) },
      { id: "equation", label: "Equation…", detail: "an equation, with a live preview and templates", icon: "sigma", key: "Mod-M", run: () => openPanel("equation") },
      { id: "inline", label: "Inline math", detail: "$x^2$ inside a sentence", icon: "dollar", run: () => wrapSelection(v, "$", "$", "x") },
      { id: "figure", label: "Figure…", detail: "an interactive figure", icon: "figure", run: () => openPanel("figure") },
      { id: "diagram", label: "Diagram…", detail: "boxes and arrows, a flowchart, a timeline or a tree, written as text", icon: "drawing", run: () => openPanel("diagram") },
      { id: "drawing", label: "Drawing from code…", detail: "a diagram drawn by a small code file", icon: "code", run: () => openPanel("drawing") },
      { id: "cite", label: "Citation…", detail: "a paper by arXiv id or DOI", icon: "quote", run: () => openPanel("cite") },
      { id: "link", label: "Link to page…", detail: "[[another page]]", icon: "link", key: "Mod-K", run: () => openPanel("link") },
      { id: "callout", label: "Callout", detail: "> [!NOTE] a highlighted box", icon: "callout", run: () => insertBlock(v, "> [!NOTE]\n> ", 12) },
      { id: "table", label: "Table", detail: "a small table to fill in", icon: "table", run: () => insertBlock(v, "| Column | Column |\n| --- | --- |\n| | |", 2) },
      { id: "image", label: "Image upload", detail: "PNG, JPEG, GIF, WebP", icon: "image", run: async () => { const f = await pickFile(IMAGE_ACCEPT); if (f) uploadAndInsert(f); } },
      { id: "code", label: "Code block", detail: "``` fenced code", icon: "code", run: () => insertBlock(v, "```python\n\n```", 10) },
      { id: "footnote", label: "Footnote", detail: "[^1] with its text at the end", icon: "footnote", run: () => footnote(v) },
      { id: "divider", label: "Divider", detail: "---", icon: "divider", run: () => insertBlock(v, "---") },
    ];
  }
  for (const c of commandList()) {
    if (c.id === "callout") toolbar.append(h("span.tb-sep"));
    if (c.id === "image") toolbar.append(h("span.tb-sep"));
    toolbar.append(h("button.tb-btn", { title: c.label.replace("…", "") + (c.key ? ` (${c.key.replace("Mod", modKey())})` : ""),
      "aria-label": c.label.replace("…", ""), onmousedown: (e) => e.preventDefault(), onclick: () => c.run() }, icon(c.icon, 17)));
  }
  toolbar.append(h("span.grow"), h("span.tb-hint", `Type / on an empty line, or ${modKey()}+/`));

  function toggleHeading(v) {
    const line = v.state.doc.lineAt(v.state.selection.main.head);
    const m = line.text.match(/^(#{1,6})\s/);
    const next = !m ? "## " : m[1].length >= 4 ? "" : "#".repeat(m[1].length + 1) + " ";
    v.dispatch({ changes: { from: line.from, to: line.from + (m ? m[0].length : 0), insert: next } });
    v.focus();
  }
  function footnote(v) {
    const text = v.state.doc.toString();
    let n = 1;
    while (text.includes(`[^${n}]`)) n++;
    const sel = v.state.selection.main;
    const end = v.state.doc.length;
    const tail = (text.endsWith("\n") ? "" : "\n") + (/\[\^\d+\]:/.test(text) ? "" : "\n") + `[^${n}]: `;
    v.dispatch({ changes: [{ from: sel.to, insert: `[^${n}]` }, { from: end, insert: tail }],
      selection: { anchor: end + `[^${n}]`.length + tail.length }, scrollIntoView: true });
    v.focus();
  }

  // --- drawers and dialogs -------------------------------------------------------------------------------------------
  let drawerKind = null, drawerApi = null;
  async function toggleDrawer(kind) {
    if (drawerKind === kind) { closeDrawer(); return; }
    clear(drawer);
    drawer.hidden = false;
    main.classList.add("with-drawer");
    drawerKind = kind;
    const mod = kind === "details" ? await import("./panels/details.js") : await import("./panels/checks.js");
    drawerApi = mod.render(drawer, ed, { close: closeDrawer });
  }
  function closeDrawer() {
    if (drawerApi && drawerApi.destroy) drawerApi.destroy();
    drawerKind = null; drawerApi = null;
    drawer.hidden = true;
    main.classList.remove("with-drawer");
  }
  ed.openDrawer = (kind) => { if (drawerKind !== kind) toggleDrawer(kind); };
  ed.focusField = (field) => {
    ed.openDrawer("details");
    setTimeout(() => { const el = drawer.querySelector(`[data-field="${field}"]`); if (el) { el.scrollIntoView({ block: "center" }); el.focus(); } }, 120);
  };

  async function openPanel(kind, opts = {}) {
    const mods = {
      equation: "./panels/equation.js", figure: "./panels/figure.js", drawing: "./panels/figures.js", diagram: "./panels/diagram.js",
      cite: "./panels/cite.js", link: "./panels/links.js", publish: "./panels/publish.js", history: "./panels/history.js",
    };
    const mod = await import(mods[kind]);
    mod.open(ed, { kind, ...opts });
  }
  ed.openPanel = openPanel;
  ed.refreshState = async () => { await refreshState(); };
  ed.reloadPage = async () => {
    const p = await api(`/api/page?id=${encodeURIComponent(ed.id)}`);
    ed.base = p.hash;
    ed.state = p.state;
    fill(pillBox, pill(p.state));
    ed.meta = p.meta || {};
    setMeta({ title: ed.meta.title, summary: ed.meta.summary }, { silent: true });
    const body = p.body || "";
    if (body !== ed.view.state.doc.toString()) {
      ed.view.dispatch({ changes: { from: 0, to: ed.view.state.doc.length, insert: body } });
    }
    ed.dirty = false;
    saveState.textContent = "Saved";
    saveState.className = "save-state saved";
    publishBtn.firstChild.textContent = p.state === "published" ? "Publish changes" : "Publish";
    renderPreview();
    runChecks();
  };
  ed.setBody = (text) => { ed.view.dispatch({ changes: { from: 0, to: ed.view.state.doc.length, insert: text } }); };

  // the page list for [[ completion and the builds_on picker
  try { state.pages = (await api("/api/pages")).pages; } catch (e) { state.pages = []; }

  // global keys while the editor is open (when focus is outside CodeMirror)
  function onKey(e) {
    if (!(e.metaKey || e.ctrlKey) || anyLayerOpen()) return;
    const k = e.key.toLowerCase();
    if (k === "s") { e.preventDefault(); save(true); }
    else if (k === "p") { e.preventDefault(); togglePreview(); }
    else if (k === "/" && !ed.view.hasFocus) { e.preventDefault(); ed.view.focus(); slashAtCursor(ed.view); }
  }
  document.addEventListener("keydown", onKey);

  // first render
  renderPreview();
  runChecks();
  if (!(ed.meta.title || "").trim() || ed.meta.title === "Untitled") titleInput.focus(); else ed.view.focus();
  if (page.meta_error) toast(page.meta_error, "error", 8000);

  return {
    dirty: () => ed.dirty,
    async beforeLeave() { if (ed.dirty) await save(false); return true; },
    destroy() {
      ed.destroyed = true;
      autosave.cancel(); previewSoon.cancel(); checkSoon.cancel();
      document.removeEventListener("keydown", onKey);
      removeEventListener("resize", onResize);
      ed.view.destroy();
    },
  };
}

export { EditorView, ApiError };
