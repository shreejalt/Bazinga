// Link to page: pick another page and insert [[id]] (or [[id|the selected words]]).
import { store, h, clear, modal, pill } from "../lib.js";

export function open(ed) {
  const view = ed.view;
  const sel = view.state.selection.main;
  const selected = view.state.sliceDoc(sel.from, sel.to).replace(/\n/g, " ");
  const q = h("input.input.big", { type: "search", placeholder: "Search pages by title", autofocus: true, "aria-label": "Search pages" });
  const list = h("div.pick-list", { role: "listbox" });
  let active = 0, shown = [];

  function paint() {
    const s = q.value.trim().toLowerCase();
    shown = (store.state.pages || []).filter((p) => p.id !== ed.id && (!s || `${p.title} ${p.id} ${(p.topics || []).join(" ")}`.toLowerCase().includes(s))).slice(0, 40);
    active = Math.min(active, Math.max(0, shown.length - 1));
    clear(list);
    if (!shown.length) list.append(h("p.muted.small", "No other pages match."));
    shown.forEach((p, i) => list.append(h("button.pick-item", { role: "option", "aria-selected": String(i === active), onclick: () => choose(p),
      onmouseenter: () => { active = i; mark(); } },
      h("span.pick-title", p.title), h("span.pick-meta", pill(p.state), h("span.mono", p.id)))));
  }
  function mark() { [...list.children].forEach((c, i) => c.setAttribute && c.setAttribute("aria-selected", String(i === active))); }
  function choose(p) {
    const text = selected ? `[[${p.id}|${selected}]]` : `[[${p.id}]]`;
    view.dispatch({ changes: { from: sel.from, to: sel.to, insert: text }, selection: { anchor: sel.from + text.length } });
    view.focus();
    m.close();
  }
  q.addEventListener("input", () => { active = 0; paint(); });
  q.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown") { e.preventDefault(); active = Math.min(shown.length - 1, active + 1); mark(); }
    if (e.key === "ArrowUp") { e.preventDefault(); active = Math.max(0, active - 1); mark(); }
    if (e.key === "Enter" && shown[active]) { e.preventDefault(); choose(shown[active]); }
  });
  const m = modal({ title: "Link to a page", subtitle: selected ? `The words “${selected.slice(0, 60)}” become the link.` : "Readers see the page's title as the link.",
    body: h("div.pick", q, list), className: "pick-modal" });
  paint();
}
