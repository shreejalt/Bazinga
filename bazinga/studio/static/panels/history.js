// Versions: snapshots taken on save; look at one and restore it (the current text is kept as a version first).
import { api, h, clear, modal, icon, ago, toast, fill } from "../lib.js";

export async function open(ed) {
  const list = h("div.ver-list");
  const pane = h("div.ver-pane", h("p.muted", "Pick a version to read it."));
  const m = modal({ title: "Versions", subtitle: "Saved copies of this page, newest first. Kept on this computer only.", body: h("div.ver", list, pane), wide: true, className: "ver-modal" });
  let versions = [];
  try { versions = (await api(`/api/history?id=${encodeURIComponent(ed.id)}`)).versions; }
  catch (e) { fill(list, h("p.muted", e.message)); return; }
  if (!versions.length) {
    list.append(h("p.muted.small", "No versions yet. One is kept every time you press " + (navigator.platform.includes("Mac") ? "⌘" : "Ctrl") + "+S, and while you write."));
    return;
  }
  for (const v of versions) {
    const b = h("button.ver-item", { onclick: () => show(v, b) }, h("span", ago(v.time)), h("span.muted.small", `${v.words.toLocaleString()} words · ${new Date(v.time * 1000).toLocaleString()}`));
    list.append(b);
  }
  async function show(v, btn) {
    for (const c of list.children) c.setAttribute("aria-current", String(c === btn));
    fill(pane, h("p.muted", "Loading…"));
    try {
      const res = await api(`/api/history/version?id=${encodeURIComponent(ed.id)}&name=${encodeURIComponent(v.name)}`);
      fill(pane, 
        h("div.ver-actions", h("strong", res.meta.title || "Untitled"), h("span.grow"),
          h("button.btn.primary", { onclick: async () => {
              await ed.save(true);
              ed.setMeta({ ...Object.fromEntries(Object.keys(ed.meta).map((k) => [k, null])), ...res.meta }, { silent: true });
              ed.setBody(res.body);
              await ed.save(true);
              await ed.reloadPage();
              toast("Restored. Your text before restoring is kept as a version too.", "ok", 4000);
              m.close();
            } }, icon("undo", 15), "Restore this version")),
        h("pre.ver-text", res.body));
    } catch (e) { fill(pane, h("p.msg-err", e.message)); }
  }
}
