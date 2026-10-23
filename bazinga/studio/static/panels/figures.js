// Figures and drawings: pick one (with a live preview), start a new one from a starter or a description, edit its
// code (Save runs its test and shows the result), and insert ::figure name / ::drawing module.fn | caption.
import { api, store, h, clear, modal, icon, toast, escapeHtml, fill, fitFrame, previewURL } from "../lib.js";
import { codeEditor } from "../cm.js";
import { isDark } from "../studio.js";

const fit = (frame) => fitFrame(frame, 160, 1400);

export function open(ed, { kind = "figure" } = {}) {
  const isFig = kind === "figure";
  const listEl = h("nav.fp-list", { "aria-label": isFig ? "Figures" : "Drawings" });
  const mainEl = h("div.fp-main");
  let code = null;          // the code editor view, when open
  let selected = null;      // figure name, or {module, fn}

  const m = modal({
    title: isFig ? "Figures" : "Drawings",
    subtitle: isFig ? "Interactive figures computed from a small file of code. Readers move the controls." : "Diagrams drawn when the site is built.",
    body: h("div.fp", listEl, mainEl), wide: true, className: "fp-modal",
    onClose: () => { if (code) code.destroy(); },
  });

  const theme = () => (isDark() ? "dark" : "light");
  const frameURL = (ref, extra = "") => previewURL(`/frame/${kind}/${encodeURIComponent(ref)}?theme=${theme()}${extra}`);

  function paintList() {
    clear(listEl);
    listEl.append(h("button.btn.primary.block", { onclick: () => showNew() }, icon("plus", 16), h("span", isFig ? "New figure" : "New drawing")));
    const items = isFig ? store.state.figures : store.state.drawings;
    if (!items.length) {
      listEl.append(h("p.muted.small", isFig ? "No figures yet. Start one from a starter." : "No drawings yet. Start one from a starter."));
      return;
    }
    if (isFig) {
      for (const f of items) {
        listEl.append(h("button.fp-item", { "aria-current": String(selected === f.name), onclick: () => showFigure(f.name) },
          h("span.fp-title", f.title || f.name), h("span.fp-name", f.name)));
      }
    } else {
      for (const d of items) {
        listEl.append(h("div.fp-group", d.module));
        for (const fn of d.functions) {
          const ref = `${d.module}.${fn}`;
          listEl.append(h("button.fp-item", { "aria-current": String(selected === ref), onclick: () => showDrawing(d.module, fn) },
            h("span.fp-title", fn.replace(/_/g, " ")), h("span.fp-name", ref)));
        }
        if (!d.functions.length) listEl.append(h("button.fp-item", { onclick: () => editCode(d.module) }, h("span.fp-title.muted", "No drawings in this file yet"), h("span.fp-name", `${d.module}.py`)));
      }
    }
  }

  // --- pick an existing one ------------------------------------------------------------------------------------------
  function showFigure(name) {
    selected = name;
    paintList();
    const f = store.state.figures.find((x) => x.name === name) || { name, presets: [] };
    const presetSel = f.presets && f.presets.length
      ? h("select.select", { "aria-label": "Open at" }, h("option", { value: "" }, "Open at its defaults"), f.presets.map((p) => h("option", { value: p }, `Open at “${p}”`)))
      : null;
    const frame = fit(h("iframe.fp-frame", { title: `Preview of ${name}`, src: frameURL(name) }));
    if (presetSel) presetSel.addEventListener("change", () => { frame.src = frameURL(name, presetSel.value ? `&start=${encodeURIComponent(presetSel.value)}` : ""); });
    fill(mainEl, 
      h("div.fp-head", h("div", h("h3", f.title || name), f.caption ? h("p.muted", f.caption) : null)),
      h("div.fp-actions.top",
        h("button.btn.ghost", { onclick: () => editCode(name) }, icon("code", 16), h("span", "Edit its code")),
        h("span.grow"), presetSel,
        h("button.btn.primary", { onclick: () => {
            const start = presetSel && presetSel.value ? ` | start: ${presetSel.value}` : "";
            ed.insertBlock(`::figure ${name}${start}`);
            m.close();
          } }, "Insert figure")),
      h("div.fp-stage", frame));
  }

  function showDrawing(module, fn) {
    const ref = `${module}.${fn}`;
    selected = ref;
    paintList();
    const caption = h("input.input", { type: "text", placeholder: "What the diagram shows, in one sentence", "aria-label": "Caption" });
    const frame = fit(h("iframe.fp-frame", { title: `Preview of ${ref}`, src: frameURL(ref) }));
    let t = null;
    caption.addEventListener("input", () => { clearTimeout(t); t = setTimeout(() => { frame.src = frameURL(ref, `&caption=${encodeURIComponent(caption.value)}`); }, 500); });
    fill(mainEl, 
      h("div.fp-head", h("div", h("h3", fn.replace(/_/g, " ")), h("p.muted", `${module}.py`))),
      h("div.fp-actions.top",
        h("button.btn.ghost", { onclick: () => editCode(module) }, icon("code", 16), h("span", "Edit its code")),
        h("span.grow"),
        h("button.btn.primary", { onclick: () => {
            ed.insertBlock(`::drawing ${ref}${caption.value.trim() ? ` | ${caption.value.trim()}` : ""}`);
            m.close();
          } }, "Insert drawing")),
      h("label.field", h("span.label", "Caption"), caption),
      h("div.fp-stage", frame));
  }

  // --- edit code ---------------------------------------------------------------------------------------------------
  async function editCode(name, { source = null, unsaved = false, result = null } = {}) {
    if (code) { code.destroy(); code = null; }
    selected = name;
    paintList();
    let src = source;
    if (src === null) {
      try { src = (await api(`/api/code?kind=${kind}&name=${encodeURIComponent(name)}`)).source; }
      catch (e) { toast(e.message, "error"); return; }
    }
    const host = h("div.fp-code");
    const out = h("div.fp-result");
    const status = h("span.save-state");
    const saveBtn = h("button.btn.primary", { onclick: () => saveCode() }, unsaved ? "Save and test" : "Save and test");
    fill(mainEl, 
      h("div.fp-head", h("div", h("h3", isFig ? `figures/${name}.py` : `drawings/${name}.py`),
        h("p.muted", isFig ? "Save runs the figure at its defaults, its presets and 20 random settings, and checks it stays fast." : "Save draws every diagram in this file."))),
      h("div.fp-split", host, out),
      h("div.fp-actions", status, h("span.grow"),
        h("button.btn.ghost", { onclick: () => (isFig ? (store.state.figures.some((f) => f.name === name) ? showFigure(name) : paintEmpty()) : paintEmpty()) }, "Back"),
        saveBtn));
    code = await codeEditor(host, src, {
      onChange: () => { status.textContent = "Not saved"; status.className = "save-state pending"; },
      keys: [{ key: "Mod-s", run: () => { saveCode(); return true; }, preventDefault: true }],
    });
    if (result) showResult(result, name);
    else if (unsaved) out.append(h("div.result-ok", icon("check", 16), "The draft passes its test"),
      h("p.muted.small", "Read it, change what you like, then save it to see it working and insert it."));
    else if (!unsaved) out.append(fit(h("iframe.fp-frame", { title: "Preview", src: isFig ? frameURL(name) : "about:blank" })));
    if (!isFig && !unsaved) drawingPreview(name, out);

    async function saveCode() {
      saveBtn.disabled = true;
      status.textContent = "Testing…"; status.className = "save-state saving";
      try {
        const res = isFig
          ? await api("/api/figures/save", { name, source: code.state.doc.toString(), create: unsaved })
          : await api("/api/drawings/save", { module: name, source: code.state.doc.toString() });
        unsaved = false;
        await ed.refreshState();
        showResult(res, name);
        status.textContent = res.ok ? "Saved, test passed" : "Saved, test failed";
        status.className = "save-state " + (res.ok ? "saved" : "error");
      } catch (e) {
        status.textContent = e.message; status.className = "save-state error";
      } finally { saveBtn.disabled = false; }
    }

    function showResult(res, nm) {
      clear(out);
      if (isFig) {
        if (res.ok) out.append(h("div.result-ok", icon("check", 16), "Passes its test"), fit(h("iframe.fp-frame", { title: "Preview", src: frameURL(nm) })),
          h("button.btn.primary.block", { onclick: () => { ed.insertBlock(`::figure ${nm}`); m.close(); } }, "Insert this figure"));
        else out.append(h("div.result-err", h("strong", res.available === false ? "Figure tests are not available yet" : res.ran === false ? "Read this draft before running it" : "This figure needs fixing"),
          (res.problems || [res.error]).filter(Boolean).map((p) => h("pre", p))));
      } else {
        if (res.error) out.append(h("div.result-err", h("strong", "This file needs fixing"), h("pre", res.error)));
        for (const f of res.functions || []) {
          if (f.ok) out.append(h("div.result-fn", h("div.result-ok", icon("check", 16), `${nm}.${f.fn}`),
            fit(h("iframe.fp-frame.small", { title: `${nm}.${f.fn}`, src: frameURL(`${nm}.${f.fn}`) })),
            h("button.btn.small", { onclick: () => { ed.insertBlock(`::drawing ${nm}.${f.fn}`); m.close(); } }, "Insert")));
          else out.append(h("div.result-err", h("strong", `${nm}.${f.fn}`), h("pre", f.error)));
        }
      }
    }
  }

  async function drawingPreview(module, out) {
    try {
      const res = await api("/api/drawings/preview", { module });
      clear(out);
      if (res.available === false) { out.append(h("p.muted", "Drawings are not available yet.")); return; }
      if (res.error) out.append(h("div.result-err", h("pre", res.error)));
      for (const f of res.functions || []) {
        out.append(f.ok ? h("div.result-fn", h("div.result-ok", icon("check", 16), `${module}.${f.fn}`), fit(h("iframe.fp-frame.small", { title: `${module}.${f.fn}`, src: frameURL(`${module}.${f.fn}`) })))
          : h("div.result-err", h("strong", `${module}.${f.fn}`), h("pre", f.error)));
      }
    } catch (e) { out.append(h("p.muted", e.message)); }
  }

  // --- new ---------------------------------------------------------------------------------------------------------
  async function showNew() {
    selected = null;
    paintList();
    let starters = { figures: [], drawings: [] };
    try { starters = await api("/api/starters"); } catch (e) { /* shown as empty */ }
    const list = isFig ? starters.figures : starters.drawings;
    const name = h("input.input", { type: "text", placeholder: isFig ? "softmax_temperature" : "pipeline", spellcheck: "false", autofocus: true, "aria-label": "Name" });
    const title = h("input.input", { type: "text", placeholder: "Softmax temperature", "aria-label": "Title" });
    let starter = list.length ? list[0].name : null;
    const cards = h("div.starter-grid", list.map((s, i) => h("button.starter", { type: "button", "aria-pressed": String(i === 0), onclick: (e) => {
        starter = s.name;
        for (const c of cards.children) c.setAttribute("aria-pressed", String(c === e.currentTarget));
      } }, h("strong", s.title), s.caption ? h("span", s.caption) : h("span", s.name.replace(/_/g, " ")))));
    const err = h("p.form-error");
    const nameOk = () => {
      const v = name.value.trim();
      if (!/^[a-z][a-z0-9_]*$/.test(v)) { err.textContent = "A name is lowercase letters, digits and _ , starting with a letter."; name.focus(); return null; }
      return v;
    };
    const fromStarter = h("button.btn.primary", { onclick: async () => {
        const nm = nameOk(); if (!nm) return;
        if (!starter) { err.textContent = "No starters are available yet."; return; }
        try {
          const res = isFig ? await api("/api/figures/new", { name: nm, starter, title: title.value })
            : await api("/api/drawings/new", { module: nm, starter });
          await ed.refreshState();
          editCode(nm, { source: res.source });
        } catch (e) { err.textContent = e.message; }
      } }, "Create from this starter");

    let describeBox = null;
    if (isFig && store.state.llm) {
      const desc = h("textarea.input", { rows: 3, placeholder: "A slider for the temperature and bars showing the softmax of five scores", "aria-label": "Describe the figure" });
      const draftBtn = h("button.btn", { onclick: async () => {
          const nm = nameOk(); if (!nm) return;
          if (!desc.value.trim()) { desc.focus(); return; }
          draftBtn.disabled = true; draftBtn.textContent = "Drafting…";
          try {
            const res = await api("/api/figures/draft", { name: nm, description: desc.value });
            editCode(nm, { source: res.source, unsaved: true, result: res });   // shown as text; it runs when saved
          } catch (e) { err.textContent = e.message; }
          finally { draftBtn.disabled = false; draftBtn.textContent = "Draft it"; }
        } }, "Draft it");
      describeBox = h("div.describe-box", h("h4", "Or describe it"), desc, h("div.row", h("span.hint", "A draft to read and test before you save it."), h("span.grow"), draftBtn));
    }

    fill(mainEl, 
      h("div.fp-head", h("div", h("h3", isFig ? "New figure" : "New drawing"), h("p.muted", "Start from a working example and change it."))),
      h("div.form-row",
        h("label.field", h("span.label", "Name"), name, h("span.hint", isFig ? "Used in the text as ::figure name" : "The file drawings/name.py")),
        isFig ? h("label.field", h("span.label", "Title"), title) : null),
      list.length ? cards : h("p.muted", "Starters are not available yet."),
      err,
      h("div.fp-actions", h("span.grow"), fromStarter),
      describeBox);
  }

  function paintEmpty() {
    selected = null;
    paintList();
    fill(mainEl, h("div.fp-empty", icon(isFig ? "figure" : "drawing", 30),
      h("p", isFig ? "Pick a figure to see it working, or start a new one." : "Pick a drawing to see it, or start a new one.")));
  }

  paintList();
  const items = isFig ? store.state.figures : store.state.drawings;
  if (isFig && items.length) showFigure(items[0].name);
  else if (!isFig && items.length && items[0].functions.length) showDrawing(items[0].module, items[0].functions[0]);
  else paintEmpty();
}

export { escapeHtml };
