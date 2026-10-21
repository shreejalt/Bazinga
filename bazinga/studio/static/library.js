// The Library: every page with its status, size, figures, last edit and checks; search, filters, New post.
import { api, store, h, clear, icon, pill, ago, plural, modal, toast, niceDate } from "./lib.js";
import { go, themeButton, refreshState } from "./studio.js";

const FILTER_KEY = "bazinga-studio-filter";

export async function renderLibrary(app) {
  const state = store.state;
  let saved = {};
  try { saved = JSON.parse(localStorage.getItem(FILTER_KEY) || "{}"); } catch (e) { saved = {}; }
  const view = { status: saved.status || "all", kind: saved.kind || "all", q: "" };
  let rows = [];
  let checks = {};

  const search = h("input.search", { type: "search", placeholder: "Search titles, summaries, topics", "aria-label": "Search pages",
    oninput: () => { view.q = search.value.trim().toLowerCase(); paint(); } });
  const tabs = h("nav.tabs", { role: "tablist", "aria-label": "Filter by status" });
  const kindSel = state.kinds.length > 1
    ? h("select.select", { "aria-label": "Kind of page", onchange: () => { view.kind = kindSel.value; remember(); paint(); } },
        h("option", { value: "all" }, "All kinds"),
        state.kinds.map((k) => h("option", { value: k.name }, k.label)))
    : null;
  if (kindSel) kindSel.value = view.kind;
  const list = h("div.lib-list", { role: "list" });

  const root = h("div.library",
    h("header.lib-top",
      h("div.brand", h("span.brand-mark"), h("span.brand-name", state.site.name), h("span.brand-sub", "Studio")),
      h("div.top-actions",
        h("a.btn.ghost", { href: state.site.origin, target: "_blank", rel: "noopener noreferrer", title: "Open the live site" },
          icon("external", 16), h("span", "Live site")),
        themeButton(),
        h("button.btn.primary", { onclick: () => newPostDialog() }, icon("plus", 16), h("span", "New post")))),
    h("main.lib-main",
      h("div.lib-head",
        h("h1", "Your pages"),
        h("p.lib-lead", "Write here, preview as you go, and publish when it is ready. Everything stays on this computer until you publish.")),
      h("div.lib-controls", tabs, h("div.lib-filters", kindSel, h("label.search-wrap", icon("search", 16), search))),
      list));
  app.append(root);

  function remember() {
    try { localStorage.setItem(FILTER_KEY, JSON.stringify({ status: view.status, kind: view.kind })); } catch (e) { /* ignore */ }
  }

  function counts() {
    const c = { all: 0, draft: 0, scheduled: 0, published: 0 };
    for (const r of rows) if (view.kind === "all" || r.kind === view.kind) { c.all++; c[r.state] = (c[r.state] || 0) + 1; }
    return c;
  }

  function paintTabs() {
    const c = counts();
    clear(tabs);
    for (const [key, label] of [["all", "All"], ["draft", "Drafts"], ["scheduled", "Scheduled"], ["published", "Published"]]) {
      tabs.append(h("button.tab", { role: "tab", "aria-selected": String(view.status === key),
        onclick: () => { view.status = key; remember(); paint(); } }, label, h("span.count", String(c[key] || 0))));
    }
  }

  function matches(r) {
    if (view.status !== "all" && r.state !== view.status) return false;
    if (view.kind !== "all" && r.kind !== view.kind) return false;
    if (!view.q) return true;
    return [r.title, r.summary, r.slug, (r.topics || []).join(" ")].join(" ").toLowerCase().includes(view.q);
  }

  function paint() {
    paintTabs();
    clear(list);
    const shown = rows.filter(matches);
    if (!rows.length) {
      list.append(h("div.empty",
        h("div.empty-art", icon("pen", 28)),
        h("h2", "Nothing written yet"),
        h("p", "Start a post: give it a title and the Studio makes a draft you can write in straight away."),
        h("button.btn.primary", { onclick: () => newPostDialog() }, icon("plus", 16), h("span", "New post"))));
      return;
    }
    if (!shown.length) {
      list.append(h("div.empty.small", h("p", "No pages match."),
        h("button.btn.ghost", { onclick: () => { search.value = ""; view.q = ""; view.status = "all"; paint(); } }, "Show all pages")));
      return;
    }
    const kindLabel = Object.fromEntries(state.kinds.map((k) => [k.name, k.singular]));
    for (const r of shown) {
      const c = checks[r.id];
      let badge = null;
      if (r.error) badge = h("span.badge.err", { title: r.error }, icon("alert", 14), "Cannot be read");
      else if (c && c.errors) badge = h("span.badge.err", icon("alert", 14), plural(c.errors, "error"));
      else if (c && c.warnings) badge = h("span.badge.warn", icon("alert", 14), plural(c.warnings, "warning"));
      else if (c) badge = h("span.badge.ok", icon("check", 14), "Checks pass");
      const meta = [
        pill(r.state),
        state.kinds.length > 1 ? h("span.meta-item", kindLabel[r.kind] || r.kind) : null,
        r.state !== "draft" && r.date ? h("span.meta-item", (r.state === "scheduled" ? "Goes live " : "") + niceDate(r.date)) : null,
        h("span.meta-item", plural(r.words, "word")),
        r.figures ? h("span.meta-item", plural(r.figures, "figure")) : null,
        h("span.meta-item", { title: new Date(r.mtime * 1000).toLocaleString() }, "Edited " + ago(r.mtime)),
      ];
      list.append(h("a.lib-row", { role: "listitem", href: `#/edit/${encodeURIComponent(r.id)}` },
        h("div.row-main",
          h("h3.row-title", r.title || r.slug),
          r.summary ? h("p.row-summary", r.summary) : h("p.row-summary.none", "No summary yet"),
          h("div.row-meta", meta)),
        h("div.row-side", badge, r.topics && r.topics.length ? h("div.row-topics", r.topics.slice(0, 3).map((t) => h("span.topic", t))) : null)));
    }
  }

  async function load() {
    rows = (await api("/api/pages")).pages;
    paint();
    api("/api/checks/summary").then((res) => { if (res.available) { checks = res.pages; paint(); } }).catch(() => {});
  }

  function onKey(e) {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); search.focus(); }
  }
  document.addEventListener("keydown", onKey);
  await load();
  return { destroy() { document.removeEventListener("keydown", onKey); } };
}

export function newPostDialog() {
  const state = store.state;
  const title = h("input.input.big", { type: "text", placeholder: "Attention, step by step", autofocus: true, maxlength: 140 });
  const kind = h("select.select", state.kinds.map((k) => h("option", { value: k.name }, k.singular)));
  const err = h("p.form-error");
  const slugHint = h("p.hint", " ");
  const updateHint = () => {
    const s = slugify(title.value);
    const k = kind.value;
    slugHint.textContent = s ? `Its address will be ${state.site.origin.replace(/^https?:\/\//, "")}/${k}/${s}/` : " ";
  };
  title.addEventListener("input", updateHint);
  kind.addEventListener("change", updateHint);
  const create = h("button.btn.primary", { type: "submit" }, "Create draft");
  const form = h("form.form", { onsubmit: async (e) => {
      e.preventDefault();
      if (!title.value.trim()) { err.textContent = "Give the post a title first."; title.focus(); return; }
      create.disabled = true;
      try {
        const res = await api("/api/page/new", { title: title.value, kind: kind.value });
        m.close();
        await refreshState();
        go(`#/edit/${encodeURIComponent(res.id)}`);
      } catch (ex) { err.textContent = ex.message; create.disabled = false; }
    } },
    h("label.field", h("span.label", "Title"), title, slugHint),
    state.kinds.length > 1 ? h("label.field", h("span.label", "Kind"), kind) : null,
    err,
    h("div.form-actions", h("button.btn.ghost", { type: "button", onclick: () => m.close() }, "Cancel"), create));
  const m = modal({ title: "New post", subtitle: "A draft is private until you publish it.", body: form });
}

export function slugify(s) {
  return s.normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 60);
}

export { toast };
