// Details: the front matter as a form (title, address, summary, description, topics, series, builds on, cover, dates).
import { api, store, h, clear, icon, toast, pill, uploadImage, pickFile, IMAGE_ACCEPT, niceDate } from "../lib.js";
import { go } from "../studio.js";
import { slugify } from "../library.js";

const KNOWN = new Set(["title", "date", "updated", "status", "summary", "description", "topics", "series", "builds_on", "cites", "cover"]);
const DESCRIPTION_MAX = 155;

export function render(container, ed, { close }) {
  const meta = ed.meta;
  const state = store.state;
  const page = ed.page;

  const field = (label, control, hint, extra) => h("div.field", h("span.label", label), control, hint ? h("span.hint", hint) : null, extra || null);

  // title
  const title = h("input.input", { type: "text", value: meta.title || "", "data-field": "title", "aria-label": "Title",
    oninput: () => ed.setMeta({ title: title.value }) });

  // address (slug)
  const slug = h("input.input.mono", { type: "text", value: page.slug, "data-field": "slug", spellcheck: "false", "aria-label": "Address" });
  const renameBtn = h("button.btn.small", { disabled: true, onclick: async () => {
      const next = slugify(slug.value);
      if (!next || next === page.slug) return;
      renameBtn.disabled = true;
      try {
        await ed.save(true);
        const res = await api("/api/page/rename", { id: ed.id, slug: next });
        toast(res.changed.length ? `Renamed; links updated in ${res.changed.length} other page${res.changed.length === 1 ? "" : "s"}.` : "Renamed.", "ok", 4000);
        if (res.note) toast(res.note, "info", 8000);
        await ed.refreshState();
        go(`#/edit/${encodeURIComponent(res.id)}`);
      } catch (e) { toast(e.message, "error", 5000); renameBtn.disabled = false; }
    } }, "Rename");
  const addr = h("span.hint");
  const paintAddr = () => {
    const s = slugify(slug.value);
    addr.textContent = `${state.site.origin.replace(/^https?:\/\//, "")}/${page.kind}/${s || "…"}/`;
    renameBtn.disabled = !s || s === page.slug;
  };
  slug.addEventListener("input", paintAddr);
  paintAddr();

  // summary
  const summary = h("textarea.input", { rows: 3, "data-field": "summary", "aria-label": "Summary" });
  summary.value = meta.summary || "";
  summary.addEventListener("input", () => ed.setMeta({ summary: summary.value.replace(/\s+/g, " ") }));

  // description
  const desc = h("textarea.input", { rows: 3, "data-field": "description", "aria-label": "Description", placeholder: "Leave empty to use the start of the summary" });
  desc.value = meta.description || "";
  const counter = h("span.counter");
  const paintCounter = () => {
    const n = desc.value.trim().length;
    counter.textContent = `${n} / ${DESCRIPTION_MAX}`;
    counter.classList.toggle("over", n > DESCRIPTION_MAX);
  };
  desc.addEventListener("input", () => { paintCounter(); ed.setMeta({ description: desc.value.replace(/\s+/g, " ").trim() }); });
  paintCounter();
  const suggest = state.llm ? h("button.btn.small.ghost", { onclick: async () => {
      suggest.disabled = true; suggest.textContent = "Suggesting…";
      try {
        const res = await api("/api/llm/describe", { id: ed.id, meta: ed.meta, body: ed.view.state.doc.toString() });
        desc.value = res.description; paintCounter();
        ed.setMeta({ description: res.description });
        toast("Suggested from the page's own words. Edit it as you like.", "ok", 3500);
      } catch (e) { toast(e.message, "error", 5000); }
      finally { suggest.disabled = false; suggest.textContent = "Suggest"; }
    } }, icon("wand", 14), "Suggest") : null;

  // topics
  const topicOpts = () => store.state.topics.map((t) => ({ value: t.slug, label: t.label, sub: t.group }));
  const topics = chipInput({
    values: [...(meta.topics || [])], options: topicOpts, max: 4, field: "topics", placeholder: "Add a topic",
    onChange: (v) => ed.setMeta({ topics: v }),
    create: async (label) => {
      const res = await api("/api/topics/add", { label });
      await ed.refreshState();
      toast(res.existed ? `${res.label} already exists.` : `New topic “${res.label}” added to topics.yml.`, "ok");
      return res.slug;
    },
  });

  // series
  const seriesName = h("input.input", { type: "text", value: (meta.series && meta.series.name) || "", list: "series-names", placeholder: "None", "data-field": "series", "aria-label": "Series name" });
  const seriesPart = h("input.input", { type: "number", min: 1, value: (meta.series && meta.series.part) || 1, "aria-label": "Part", style: { maxWidth: "5.5em" } });
  const seriesList = h("datalist#series-names", (state.series || []).map((s) => h("option", { value: s })));
  const setSeries = () => ed.setMeta({ series: seriesName.value.trim() ? { name: seriesName.value.trim(), part: Number(seriesPart.value) || 1 } : null });
  seriesName.addEventListener("input", setSeries);
  seriesPart.addEventListener("input", setSeries);

  // builds on
  const pageOpts = () => (store.state.pages || []).filter((p) => p.id !== ed.id).map((p) => ({ value: p.id, label: p.title, sub: p.id }));
  const builds = chipInput({
    values: [...(meta.builds_on || [])], options: pageOpts, field: "builds_on", placeholder: "Add a page to read first",
    onChange: (v) => ed.setMeta({ builds_on: v }), labelFor: (v) => ((store.state.pages || []).find((p) => p.id === v) || {}).title || v,
  });

  // cover
  const cover = h("div.cover");
  const paintCover = () => {
    clear(cover);
    if (meta.cover) {
      cover.append(h("img", { src: "/" + meta.cover.replace(/^\//, ""), alt: "" }),
        h("div.row", h("span.mono.small", meta.cover), h("span.grow"),
          h("button.btn.small.ghost", { onclick: () => { ed.setMeta({ cover: null }); paintCover(); } }, "Remove")));
    } else {
      cover.append(h("button.btn.small", { onclick: async () => {
          const f = await pickFile(IMAGE_ACCEPT);
          if (!f) return;
          try { const res = await uploadImage(f, page.slug + "-cover"); ed.setMeta({ cover: res.path }); paintCover(); }
          catch (e) { toast(e.message, "error", 5000); }
        } }, icon("upload", 14), "Upload a share image"));
    }
  };
  paintCover();

  // dates
  const date = h("input.input", { type: "date", value: meta.date || "", "data-field": "date", "aria-label": "Date",
    oninput: () => ed.setMeta({ date: date.value || null }) });
  const updated = h("input.input", { type: "date", value: meta.updated || "", "data-field": "updated", "aria-label": "Updated",
    oninput: () => ed.setMeta({ updated: updated.value || null }) });
  const stateLine = h("p.small.muted", pill(ed.state), " ",
    ed.state === "draft" ? "Publishing sets today's date, or schedule it from Publish."
      : ed.state === "scheduled" ? `Goes live on ${niceDate(meta.date)}.` : "Change the date only to correct it; set Updated when you really revise the page.");

  const others = Object.keys(meta).filter((k) => !KNOWN.has(k));

  container.append(
    h("div.drawer-head", h("h2", "Details"), h("button.icon-btn", { title: "Close", "aria-label": "Close", onclick: close }, icon("x"))),
    h("div.drawer-body",
      field("Title", title),
      field("Address", h("div.row", slug, renameBtn), null, addr),
      field("Summary", summary, "Shown under the title, in lists and on the map. Two or three sentences."),
      h("div.field", h("div.label-row", h("span.label", "Description"), h("span.grow"), counter, suggest),
        desc, h("span.hint", "What search engines show. Up to 155 characters, in the page's own words.")),
      field("Topics", topics.el, "One to four, from your topics list."),
      field("Series", h("div.row", seriesName, h("span.muted.small", "part"), seriesPart), "Pages in the same series are read in part order."),
      seriesList,
      field("Builds on", builds.el, "Pages a reader should read first."),
      field("Share image", cover, "Optional. Shown when the page is shared."),
      h("div.form-row", field("Date", date), field("Updated", updated)),
      stateLine,
      others.length ? h("p.small.muted", "Also in the front matter (kept as written): ", others.join(", ")) : null));
  setTimeout(() => title.focus(), 30);
  return { destroy() {}, refresh() {} };
}

// Chips with a filtered dropdown. options() -> [{value, label, sub}]
export function chipInput({ values, options, onChange, placeholder, max = 99, create, field, labelFor }) {
  const chips = h("div.chips");
  const input = h("input.chip-input", { type: "text", placeholder, "data-field": field, "aria-label": placeholder, autocomplete: "off" });
  const menu = h("div.chip-menu", { hidden: true, role: "listbox" });
  const el = h("div.chip-field", chips, h("div.chip-entry", input, menu));
  let active = 0, shown = [];
  const label = (v) => (labelFor ? labelFor(v) : ((options().find((o) => o.value === v) || {}).label || v));

  function paint() {
    clear(chips);
    for (const v of values) {
      chips.append(h("span.chip", label(v), h("button", { type: "button", "aria-label": `Remove ${label(v)}`, onclick: () => { values = values.filter((x) => x !== v); onChange(values); paint(); } }, icon("x", 12))));
    }
    input.disabled = values.length >= max;
    input.placeholder = values.length >= max ? `Up to ${max}` : placeholder;
  }
  function paintMenu() {
    const s = input.value.trim().toLowerCase();
    shown = options().filter((o) => !values.includes(o.value) && (!s || `${o.label} ${o.value}`.toLowerCase().includes(s))).slice(0, 8);
    const canCreate = create && s && !options().some((o) => o.label.toLowerCase() === s || o.value === s);
    clear(menu);
    shown.forEach((o, i) => menu.append(h("button.chip-opt", { type: "button", role: "option", "aria-selected": String(i === active), onmousedown: (e) => { e.preventDefault(); add(o.value); } },
      h("span", o.label), o.sub ? h("span.muted.small", o.sub) : null)));
    if (canCreate) menu.append(h("button.chip-opt.create", { type: "button", onmousedown: async (e) => { e.preventDefault(); add(await create(input.value.trim())); } },
      icon("plus", 14), h("span", `Add “${input.value.trim()}” as a new topic`)));
    menu.hidden = !menu.children.length || document.activeElement !== input;
  }
  function add(v) {
    if (!v || values.includes(v) || values.length >= max) return;
    values = [...values, v];
    input.value = "";
    onChange(values);
    paint(); paintMenu();
  }
  input.addEventListener("focus", paintMenu);
  input.addEventListener("blur", () => setTimeout(() => { menu.hidden = true; }, 120));
  input.addEventListener("input", () => { active = 0; paintMenu(); });
  input.addEventListener("keydown", async (e) => {
    if (e.key === "ArrowDown") { e.preventDefault(); active = Math.min(shown.length - 1, active + 1); paintMenu(); }
    else if (e.key === "ArrowUp") { e.preventDefault(); active = Math.max(0, active - 1); paintMenu(); }
    else if (e.key === "Enter") {
      e.preventDefault();
      if (shown[active]) add(shown[active].value);
      else if (create && input.value.trim()) add(await create(input.value.trim()));
    } else if (e.key === "Backspace" && !input.value && values.length) {
      values = values.slice(0, -1); onChange(values); paint();
    }
  });
  paint();
  return { el, set(v) { values = v; paint(); } };
}
