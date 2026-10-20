// Ask: questions answered from this site's own pages.
//
// - The /ask/ page:     <div id="ask-page"></div>
// - Every other page:   <div id="ask-root" data-page="post:attention"></div>  -> a floating "Ask" button + panel
//   (data-page is the current page id, or empty). Optional data-passages / data-graph / data-api URLs.
//
// The quick answer runs the site's search code in the browser through window.Tessera.py.call (the same worker
// the figures use), from /data/passages.json and /data/graph.json. When that is not available a small keyword
// search answers instead. A "Written answer" button appears when /api/ask/ says it is on.
(function () {
  "use strict";

  const DEFAULTS = { passages: "/data/passages.json", graph: "/data/graph.json", api: "/api/ask/", module: "/figures/_retrieve.py" };
  let urls = Object.assign({}, DEFAULTS);
  let dataPromise = null;
  let apiPromise = null;
  let pyOk = null;           // null = untried, true/false after the first attempt

  function el(tag, attrs, parent) {
    const e = document.createElement(tag);
    for (const k in attrs || {}) {
      if (k === "text") e.textContent = attrs[k];
      else if (k === "class") e.className = attrs[k];
      else e.setAttribute(k, attrs[k]);
    }
    if (parent) parent.appendChild(e);
    return e;
  }

  function loadData() {
    if (!dataPromise) {
      const get = (u) => fetch(u).then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); });
      dataPromise = Promise.all([get(urls.passages), get(urls.graph).catch(() => null)])
        .then(([passages, graph]) => ({ passages, graph }));
      dataPromise.catch(() => { dataPromise = null; });
    }
    return dataPromise;
  }

  function apiStatus() {
    if (!apiPromise) {
      apiPromise = fetch(urls.api, { headers: { Accept: "application/json" } })
        .then((r) => (r.ok ? r.json() : { on: false }))
        .then((j) => (j && j.on ? j : { on: false }))
        .catch(() => ({ on: false }));
    }
    return apiPromise;
  }

  // --------------------------------------------------------------------------------- quick answer
  function withTimeout(p, ms) {
    return Promise.race([p, new Promise((_, rej) => setTimeout(() => rej(new Error("timeout")), ms))]);
  }

  async function quickAnswer(question, page) {
    const data = await loadData();
    const py = window.Tessera && window.Tessera.py && typeof window.Tessera.py.call === "function" ? window.Tessera.py : null;
    if (py && pyOk !== false) {
      try {
        const res = await withTimeout(py.call(urls.module, "answer", {
          question,
          passages: { $json: urls.passages },
          graph: { $json: urls.graph },
          page: page || null,
          k: 6,
        }), pyOk ? 8000 : 25000);
        pyOk = true;
        if (res && typeof res === "object") res.engine = "page";
        return res;
      } catch (e) {
        pyOk = false;
      }
    }
    const res = jsAnswer(question, data.passages, data.graph, page);
    res.engine = "fallback";
    return res;
  }

  // A small keyword search, used only when the in-browser search code cannot run.
  const STOP = new Set("a an and are as at be by can do does for from has have how i in is it its of on or that the this to was what when where which who why will with you your about explain tell me".split(" "));
  function toks(s) {
    return (String(s || "").normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase().match(/[\p{L}\p{N}]+/gu) || [])
      .filter((w) => !STOP.has(w) && (w.length > 1 || /\d/.test(w)))
      .map((w) => (w.length > 4 && w.endsWith("s") && !w.endsWith("ss") ? w.slice(0, -1) : w));
  }
  function jsAnswer(question, passages, graph, page) {
    const q = [...new Set(toks(question))];
    if (!q.length) return { answer: "", passages: [], pages: [], count: passages.length };
    const df = new Map();
    const docs = passages.map((p) => {
      const t = toks(p.text + " " + p.section);
      const tf = new Map();
      t.forEach((w) => tf.set(w, (tf.get(w) || 0) + 1));
      tf.forEach((_, w) => df.set(w, (df.get(w) || 0) + 1));
      return { p, tf, len: t.length };
    });
    const N = passages.length;
    const avg = docs.reduce((s, d) => s + d.len, 0) / Math.max(1, N);
    const near = new Set();
    if (graph && page && graph.rings && graph.rings[page]) (graph.rings[page][0] || []).forEach((x) => near.add(x));
    const scored = [];
    docs.forEach((d) => {
      let s = 0;
      q.forEach((w) => {
        const f = d.tf.get(w);
        if (!f) return;
        const idf = Math.log(1 + (N - df.get(w) + 0.5) / (df.get(w) + 0.5));
        s += (idf * f * 2.2) / (f + 1.2 * (0.25 + 0.75 * d.len / avg));
      });
      if (s > 0) {
        if (d.p.id === page) s *= 1.6;
        else if (near.has(d.p.id)) s *= 1.25;
        scored.push(Object.assign({}, d.p, { score: s }));
      }
    });
    scored.sort((a, b) => b.score - a.score);
    const top = scored.slice(0, 6);
    const sents = [];
    top.slice(0, 3).forEach((p, rank) => {
      (p.text.match(/[^.!?]+[.!?]+(\s|$)/g) || [p.text]).forEach((s, j) => {
        const st = new Set(toks(s));
        const hit = q.filter((w) => st.has(w)).length;
        if (hit && s.trim().length > 24) sents.push({ s: s.trim(), score: hit / q.length - 0.15 * rank - 0.03 * j, rank, j });
      });
    });
    sents.sort((a, b) => b.score - a.score);
    const chosen = sents.slice(0, 2).sort((a, b) => a.rank - b.rank || a.j - b.j);
    const seen = new Set();
    const pages = [];
    top.forEach((p) => { if (!seen.has(p.id)) { seen.add(p.id); pages.push({ id: p.id, title: p.title, url: p.url }); } });
    return { answer: chosen.map((c) => c.s).join(" "), passages: top, pages, count: N };
  }

  // -------------------------------------------------------------------------------------- UI piece
  function sourceHref(p) {
    return p.url + (p.anchor ? "#" + encodeURIComponent(p.anchor) : "");
  }

  // Numbered sources (written answer): one row per source. Quick answer: one row per page, its sections after it.
  function sourceList(parent, items, numbered) {
    const ol = el(numbered ? "ol" : "ul", { class: "ask-sources" }, parent);
    if (numbered) {
      items.forEach((p) => {
        const li = el("li", {}, ol);
        const a = el("a", { href: sourceHref(p) }, li);
        if (p.n) a.dataset.n = p.n;
        el("span", { class: "ask-src-title", text: p.title }, a);
        if (p.section) el("span", { class: "ask-src-section", text: p.section }, a);
      });
      return ol;
    }
    const pages = new Map();
    items.forEach((p) => {
      if (!pages.has(p.url)) pages.set(p.url, { title: p.title, url: p.url, parts: [] });
      const pg = pages.get(p.url);
      if (!pg.parts.some((x) => x.anchor === (p.anchor || ""))) pg.parts.push({ anchor: p.anchor || "", section: p.section || "" });
    });
    pages.forEach((pg) => {
      const li = el("li", { class: "ask-src-page" }, ol);
      const first = pg.parts.find((x) => x.anchor) || pg.parts[0];
      el("a", { class: "ask-src-title", href: pg.url + (first && first.anchor ? "#" + encodeURIComponent(first.anchor) : ""), text: pg.title }, li);
      pg.parts.filter((x) => x.section).forEach((x) => {
        el("a", { class: "ask-src-section", href: pg.url + "#" + encodeURIComponent(x.anchor), text: x.section }, li);
      });
    });
    return ol;
  }

  // Answer text with [n] markers turned into links to the numbered sources.
  function citedText(parent, text, sources) {
    const byN = new Map(sources.map((s) => [String(s.n), s]));
    text.split(/\n{2,}/).forEach((para) => {
      const p = el("p", {}, parent);
      let last = 0;
      const re = /\[(\d+)\]/g;
      let m;
      while ((m = re.exec(para))) {
        p.appendChild(document.createTextNode(para.slice(last, m.index)));
        const s = byN.get(m[1]);
        if (s) {
          const a = el("a", { class: "ask-cite", href: sourceHref(s), title: s.title + (s.section ? " — " + s.section : ""), text: m[1] }, p);
          a.setAttribute("aria-label", "source " + m[1] + ": " + s.title);
        } else {
          p.appendChild(document.createTextNode(m[0]));
        }
        last = re.lastIndex;
      }
      p.appendChild(document.createTextNode(para.slice(last)));
    });
  }

  // Builds the ask form + answer area inside `host`. Returns {input, ask(q)}.
  function askBox(host, opts) {
    const page = opts.page || "";
    const form = el("form", { class: "ask-form", role: "search" }, host);
    const id = "ask-q-" + Math.random().toString(36).slice(2, 7);
    el("label", { for: id, class: opts.showLabel ? "ask-label" : "ask-sr", text: opts.label || "Your question" }, form);
    const row = el("div", { class: "ask-row" }, form);
    const input = el("input", { id, type: "text", name: "q", maxlength: "400", autocomplete: "off", placeholder: opts.placeholder || "Ask a question…", enterkeyhint: "search" }, row);
    const btn = el("button", { type: "submit", class: "ask-submit", text: "Ask" }, row);
    const status = el("p", { class: "ask-status", role: "status", "aria-live": "polite" }, host);
    const out = el("div", { class: "ask-out" }, host);
    let last = "";
    let busy = false;

    async function ask(q) {
      q = (q || "").trim();
      if (!q || busy) return;
      busy = true;
      last = q;
      input.value = q;
      btn.disabled = true;
      out.textContent = "";
      status.textContent = "Searching…";
      host.classList.add("is-busy");
      try {
        const res = await quickAnswer(q, page);
        render(q, res);
      } catch (e) {
        status.textContent = "The pages could not be loaded. Please try again.";
      } finally {
        busy = false;
        btn.disabled = false;
        host.classList.remove("is-busy");
      }
    }

    function render(q, res) {
      out.textContent = "";
      host.dataset.engine = res.engine || "";
      const n = res.count || 0;
      if (!res.passages || !res.passages.length) {
        status.textContent = "Nothing on this site matches that yet. Try other words.";
        return;
      }
      status.textContent = "Answered from " + n.toLocaleString() + " passages of this site.";
      const card = el("div", { class: "ask-answer" }, out);
      if (res.answer) {
        el("p", { class: "ask-kicker", text: "From the pages" }, card);
        el("blockquote", { class: "ask-quote", text: res.answer }, card);
      }
      el("p", { class: "ask-kicker", text: res.answer ? "Read more" : "These sections look closest" }, card);
      const best = res.passages[0].score || 0;
      sourceList(card, res.passages.filter((p, i) => i < 2 || !best || (p.score || 0) >= best * 0.3).slice(0, 6), false);
      writtenSlot(out, q);
    }

    async function writtenSlot(parent, q) {
      const st = await apiStatus();
      if (!st.on || last !== q) return;
      const box = el("div", { class: "ask-written" }, parent);
      const b = el("button", { type: "button", class: "ask-written-btn", text: "Written answer" }, box);
      const note = el("span", { class: "ask-written-note", text: typeof st.left === "number" ? st.left + " left today" : "" }, box);
      if (st.left === 0) { b.disabled = true; note.textContent = "None left today"; }
      b.addEventListener("click", async () => {
        b.disabled = true;
        note.textContent = "Writing…";
        try {
          const r = await fetch(urls.api, {
            method: "POST",
            headers: { "Content-Type": "application/json", Accept: "application/json" },
            body: JSON.stringify({ q, page: page || null }),
          });
          const j = await r.json().catch(() => ({}));
          if (!r.ok || !j.answer) {
            note.textContent = j.error || "No written answer right now.";
            if (typeof j.left === "number") st.left = j.left;
            b.disabled = st.left === 0;
            return;
          }
          st.left = j.left;
          box.textContent = "";
          const card = el("div", { class: "ask-answer ask-answer-written" }, box);
          el("p", { class: "ask-kicker", text: "Written answer, from the pages below" }, card);
          const body = el("div", { class: "ask-written-body" }, card);
          citedText(body, j.answer, j.sources || []);
          if ((j.sources || []).length) sourceList(card, j.sources, true);
          el("p", { class: "ask-fine", text: (typeof j.left === "number" ? j.left + " written answers left today. " : "") + "Check the sources; the wording is not the author's." }, card);
        } catch (e) {
          note.textContent = "No written answer right now.";
          b.disabled = false;
        }
      });
    }

    form.addEventListener("submit", (ev) => { ev.preventDefault(); ask(input.value); });
    return { input, ask, out, status };
  }

  // ------------------------------------------------------------------------------------ /ask/ page
  function initPage(root) {
    if (root.dataset.ready) return;
    root.dataset.ready = "1";
    readUrls(root);
    root.classList.add("ask-page");
    const params = new URLSearchParams(location.search);
    const box = askBox(root, { page: params.get("page") || "", showLabel: true, label: "Ask a question about anything on this site", placeholder: "For example: why divide by the square root of d?" });
    const tries = el("div", { class: "ask-tries" }, root);
    tries.hidden = true;
    loadData().then(({ passages, graph }) => {
      const nodes = (graph && graph.nodes) || [];
      const pick = nodes.slice().sort((a, b) => (b.degree || 0) - (a.degree || 0)).slice(0, 4);
      if (!pick.length) return;
      el("p", { class: "ask-kicker", text: "Or ask about" }, tries);
      const ul = el("div", { class: "ask-try-list" }, tries);
      pick.forEach((n) => {
        const b = el("button", { type: "button", class: "ask-try", text: n.title }, ul);
        b.addEventListener("click", () => box.ask(n.title));
      });
      tries.hidden = false;
      if (!box.status.textContent) box.status.textContent = passages.length.toLocaleString() + " passages from " + nodes.length + " pages.";
    }).catch(() => {});
    const q = params.get("q");
    if (q) box.ask(q);
    else if (!matchMedia("(hover: none)").matches) box.input.focus({ preventScroll: true });
  }

  // ------------------------------------------------------------------------- floating button + panel
  function initWidget(root) {
    if (root.dataset.ready) return;
    root.dataset.ready = "1";
    readUrls(root);
    const page = root.dataset.page || "";
    root.classList.add("ask-widget");
    const fab = el("button", { type: "button", class: "ask-fab", "aria-expanded": "false", "aria-controls": "ask-panel" }, root);
    el("span", { class: "ask-fab-mark", "aria-hidden": "true", text: "?" }, fab);
    el("span", { text: "Ask" }, fab);
    const panel = el("section", { id: "ask-panel", class: "ask-panel", role: "dialog", "aria-label": "Ask this site", hidden: "" }, root);
    const head = el("div", { class: "ask-panel-head" }, panel);
    el("h2", { class: "ask-panel-title", text: page ? "Ask about this page" : "Ask this site" }, head);
    const close = el("button", { type: "button", class: "ask-close", "aria-label": "Close", text: "×" }, head);
    const ctx = el("div", { class: "ask-context" }, panel);
    const box = askBox(panel, { page, placeholder: page ? "Ask about this page or the site…" : "Ask a question…" });
    const foot = el("p", { class: "ask-foot" }, panel);
    el("a", { href: "/ask/", text: "Open the Ask page" }, foot);
    let filled = false;

    function fillContext() {
      if (filled || !page) return;
      filled = true;
      loadData().then(({ graph }) => {
        const nodes = new Map(((graph && graph.nodes) || []).map((n) => [n.id, n]));
        const me = nodes.get(page);
        if (!me) return;
        el("p", { class: "ask-kicker", text: "This page" }, ctx);
        if (me.summary) el("p", { class: "ask-context-summary", text: me.summary }, ctx);
        const near = ((graph.rings && graph.rings[page]) || [])[0] || [];
        if (near.length) {
          const p = el("p", { class: "ask-context-near" }, ctx);
          p.appendChild(document.createTextNode("Connected: "));
          near.slice(0, 4).forEach((id, i) => {
            const n = nodes.get(id);
            if (!n) return;
            if (i) p.appendChild(document.createTextNode(" · "));
            el("a", { href: n.url, text: n.title }, p);
          });
        }
      }).catch(() => {});
    }

    function open() {
      panel.hidden = false;
      root.classList.add("is-open");
      fab.setAttribute("aria-expanded", "true");
      fillContext();
      apiStatus();
      setTimeout(() => box.input.focus({ preventScroll: true }), 30);
      // warm the search code while the reader types
      loadData().catch(() => {});
    }
    function shut(returnFocus) {
      panel.hidden = true;
      root.classList.remove("is-open");
      fab.setAttribute("aria-expanded", "false");
      if (returnFocus) fab.focus();
    }
    fab.addEventListener("click", () => (panel.hidden ? open() : shut(false)));
    close.addEventListener("click", () => shut(true));
    document.addEventListener("keydown", (ev) => {
      if (ev.key === "Escape" && !panel.hidden) shut(true);
    });
    document.addEventListener("pointerdown", (ev) => {
      if (!panel.hidden && !root.contains(ev.target)) shut(false);
    });
  }

  function readUrls(root) {
    if (root.dataset.passages) urls.passages = root.dataset.passages;
    if (root.dataset.graph) urls.graph = root.dataset.graph;
    if (root.dataset.api) urls.api = root.dataset.api;
    if (root.dataset.module) urls.module = root.dataset.module;
  }

  function start() {
    const pageRoot = document.getElementById("ask-page");
    if (pageRoot) initPage(pageRoot);
    const w = document.getElementById("ask-root");
    if (w && !pageRoot) initWidget(w);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();

  window.TesseraAsk = { jsAnswer };
})();
