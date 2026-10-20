// Citation: paste an arXiv id/link or a DOI, check the record, choose its key, save it to the references, insert [@KEY].
import { api, store, h, clear, modal, icon, toast, fill } from "../lib.js";

export function open(ed) {
  const q = h("input.input.big", { type: "text", placeholder: "1706.03762, an arXiv link, or a DOI such as 10.1145/3065386", autofocus: true, spellcheck: "false", "aria-label": "arXiv id, link or DOI" });
  const findBtn = h("button.btn.primary", { type: "submit" }, "Look it up");
  const result = h("div.cite-result");
  const search = h("input.input", { type: "search", placeholder: "Search your references", "aria-label": "Search your references" });
  const mine = h("div.ref-list");

  function paintMine() {
    clear(mine);
    const s = search.value.trim().toLowerCase();
    const refs = store.state.references.filter((r) => !s || `${r.key} ${r.title} ${(r.authors || []).join(" ")} ${r.year || ""}`.toLowerCase().includes(s));
    if (!store.state.references.length) { mine.append(h("p.muted.small", "Your references list is empty.")); return; }
    for (const r of refs.slice(0, 50)) {
      mine.append(h("button.ref-item", { onclick: () => insert(r.key) },
        h("span.ref-key", r.key), h("span.ref-title", r.title), h("span.ref-meta", [(r.authors || [])[0], r.year].filter(Boolean).join(", "))));
    }
  }
  search.addEventListener("input", paintMine);

  function insert(key) {
    const v = ed.view;
    const sel = v.state.selection.main;
    const before = v.state.sliceDoc(Math.max(0, sel.from - 1), sel.from);
    ed.insertText(`${before && !/\s/.test(before) ? " " : ""}[@${key}]`);
    m.close();
  }

  const form = h("form.cite-form", { onsubmit: async (e) => {
      e.preventDefault();
      if (!q.value.trim()) return;
      findBtn.disabled = true; findBtn.textContent = "Looking…";
      fill(result, h("p.muted", "Asking arXiv or Crossref…"));
      try {
        const res = await api("/api/cite/lookup", { q: q.value });
        showRecord(res);
      } catch (ex) { fill(result, h("div.msg-err", ex.message)); }
      finally { findBtn.disabled = false; findBtn.textContent = "Look it up"; }
    } }, h("div.row", q, findBtn));

  function showRecord({ record, key, existing }) {
    const keyIn = h("input.input.mono", { type: "text", value: key, spellcheck: "false", "aria-label": "Key" });
    const title = h("input.input", { type: "text", value: record.title || "", "aria-label": "Title" });
    const authors = h("input.input", { type: "text", value: (record.authors || []).join(", "), "aria-label": "Authors" });
    const year = h("input.input", { type: "number", value: record.year || "", "aria-label": "Year", style: { maxWidth: "7em" } });
    const venue = h("input.input", { type: "text", value: record.venue || "", "aria-label": "Venue" });
    const err = h("p.form-error");
    const saveBtn = h("button.btn.primary", { onclick: async () => {
        if (existing) { insert(existing); return; }
        saveBtn.disabled = true;
        try {
          const rec = { ...record, title: title.value, authors: authors.value.split(",").map((s) => s.trim()).filter(Boolean), year: year.value, venue: venue.value };
          await api("/api/cite/save", { key: keyIn.value.trim(), record: rec });
          await ed.refreshState();
          toast(`${keyIn.value.trim()} added to your references.`, "ok");
          insert(keyIn.value.trim());
        } catch (e) { err.textContent = e.message; saveBtn.disabled = false; }
      } }, existing ? `Insert [@${existing}]` : "Save and insert");
    const link = record.arxiv ? `https://arxiv.org/abs/${record.arxiv}` : record.url || (record.doi ? `https://doi.org/${record.doi}` : "");
    fill(result, h("div.record",
      existing ? h("p.note", icon("info", 16), `Already in your references as ${existing}.`) : null,
      h("div.form-grid",
        h("label.field", h("span.label", "Key"), keyIn, h("span.hint", "You cite it as [@KEY].")),
        h("label.field.span2", h("span.label", "Title"), title),
        h("label.field.span2", h("span.label", "Authors"), authors),
        h("label.field", h("span.label", "Year"), year),
        h("label.field", h("span.label", "Venue"), venue)),
      link ? h("p.small", h("a", { href: link, target: "_blank", rel: "noopener noreferrer" }, icon("external", 14), " ", link)) : null,
      err,
      h("div.form-actions", h("span.grow"), saveBtn)));
  }

  const body = h("div.cite",
    form, result,
    h("div.cite-mine", h("h4", "Or cite one you already have"), search, mine));
  const m = modal({ title: "Citation", subtitle: "Look up a paper and add it to your references.", body, wide: false, className: "cite-modal" });
  paintMine();
}
