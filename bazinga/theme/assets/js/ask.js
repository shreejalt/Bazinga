/* Ask: the /ask/ page and the floating "Ask ?" on every other page (which takes the page being read as context).

   A question is answered from the site itself, in the browser:
   - questions about how pages connect ("what connects A and B", "what should I read before …", "what comes after …",
     "what is … about", "what is this site about") are answered from the map (/data/mapdata.json and each page's
     /data/view/<id>.json, written by the build);
   - everything else, and the "where the pages talk about it" lists, come from the pages' passages
     (/data/passages.json), searched by the site's own search code through window.Bazinga.py.call (the same worker
     the figures use), with a small keyword search as a fallback.
   "Written answer" posts the question to /api/ask/, which picks passages the same way and writes a few sentences
   from them only, each cited. It appears only when the site has it switched on. Answers are never stored. */
(function () {
  "use strict";
  const PASSAGES = "/data/passages.json", GRAPH = "/data/graph.json", MAPDATA = "/data/mapdata.json";
  const MODULE = "/figures/_retrieve.py", API = "/api/ask/";
  const PAGE = document.body.dataset.page || null, TITLE = document.body.dataset.title || "";
  const S = window.SITE || { nodes: {}, kinds: {} };
  const e = (s) => String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/"/g, "&quot;");
  const kl = (id) => (S.nodes[id] || {}).kl || "";
  const href = (id) => (S.nodes[id] || {}).url || "#";
  const CONTENT = new Set(["read", "paper", "proj", "ext"]);
  let api = null, data = null, mapdata = null, pyOk = null;
  const views = {};

  // ------------------------------------------------------------------------------------------- data
  const getJSON = (u) => fetch(u).then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); });
  function loadData() {
    return data || (data = Promise.all([getJSON(PASSAGES).catch(() => []), getJSON(GRAPH).catch(() => null)])
      .then(([passages, graph]) => ({ passages, graph })));
  }
  function loadMap() { return mapdata || (mapdata = getJSON(MAPDATA).catch(() => ({ items: [] }))); }
  function viewOf(id) { return views[id] || (views[id] = getJSON("/data/view/" + id.replace(":", "-") + ".json")); }
  function apiStatus() {
    return api || (api = fetch(API, { headers: { Accept: "application/json" } })
      .then((r) => (r.ok ? r.json() : { on: false })).catch(() => ({ on: false })));
  }

  // ------------------------------------------------------------------------------- passages search
  const withTimeout = (p, ms) => Promise.race([p, new Promise((_, rej) => setTimeout(() => rej(new Error("timeout")), ms))]);
  async function search(question, page) {
    const d = await loadData();
    const py = window.Bazinga && window.Bazinga.py && typeof window.Bazinga.py.call === "function" ? window.Bazinga.py : null;
    if (py && pyOk !== false) {
      try {
        const res = await withTimeout(py.call(MODULE, "answer", {
          question, passages: { $json: PASSAGES }, graph: { $json: GRAPH }, page: page || null, k: 6,
        }), pyOk ? 8000 : 25000);
        pyOk = true;
        res.count = res.count || d.passages.length;
        return res;
      } catch (err) { pyOk = false; }
    }
    return keywordAnswer(question, d.passages, d.graph, page);
  }
  // A small keyword search, used only when the in-browser search code cannot run.
  const STOP = new Set("a an and are as at be by can do does for from has have how i in is it its of on or that the this to was what when where which who why will with you your about explain tell me".split(" "));
  function toks(s) {
    return (String(s || "").normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase().match(/[\p{L}\p{N}]+/gu) || [])
      .filter((w) => !STOP.has(w) && (w.length > 1 || /\d/.test(w)))
      .map((w) => (w.length > 4 && w.endsWith("s") && !w.endsWith("ss") ? w.slice(0, -1) : w));
  }
  function keywordAnswer(question, passages, graph, page) {
    const q = [...new Set(toks(question))];
    if (!q.length) return { answer: "", passages: [], pages: [], count: passages.length };
    const df = new Map();
    const docs = passages.map((p) => {
      const t = toks(p.text + " " + p.section), tf = new Map();
      t.forEach((w) => tf.set(w, (tf.get(w) || 0) + 1));
      tf.forEach((_, w) => df.set(w, (df.get(w) || 0) + 1));
      return { p, tf, len: t.length };
    });
    const N = passages.length, avg = docs.reduce((s, d) => s + d.len, 0) / Math.max(1, N), scored = [];
    docs.forEach((d) => {
      let s = 0;
      q.forEach((w) => {
        const f = d.tf.get(w);
        if (!f) return;
        const idf = Math.log(1 + (N - df.get(w) + 0.5) / (df.get(w) + 0.5));
        s += (idf * f * 2.2) / (f + 1.2 * (0.25 + 0.75 * d.len / avg));
      });
      if (s > 0) scored.push(Object.assign({}, d.p, { score: d.p.id === page ? s * 1.6 : s }));
    });
    scored.sort((a, b) => b.score - a.score);
    const top = scored.slice(0, 6), sents = [];
    top.slice(0, 3).forEach((p, rank) => {
      (p.text.match(/[^.!?]+[.!?]+(\s|$)/g) || [p.text]).forEach((s, j) => {
        const st = new Set(toks(s)), hit = q.filter((w) => st.has(w)).length;
        if (hit && s.trim().length > 24) sents.push({ s: s.trim(), score: hit / q.length - 0.15 * rank - 0.03 * j, rank, j });
      });
    });
    sents.sort((a, b) => b.score - a.score);
    const chosen = sents.slice(0, 2).sort((a, b) => a.rank - b.rank || a.j - b.j);
    return { answer: chosen.map((c) => c.s).join(" "), passages: top, pages: [], count: N };
  }

  // ------------------------------------------------------------------------------------ the map's answers
  function findPage(name) {
    const n = String(name || "").trim().replace(/^the\s+/i, "").replace(/[?.!]+$/, "").toLowerCase();
    if (!n) return null;
    if (/^(this|this page|here|it)$/.test(n)) return PAGE;
    const want = toks(n);
    let best = null, score = 0;
    Object.entries(S.nodes).forEach(([id, nd]) => {
      if (!CONTENT.has(nd.type)) return;
      const t = nd.title.toLowerCase(), sh = (nd.short || "").toLowerCase();
      let s = t === n || sh === n ? 100 : t.includes(n) ? 50 + n.length / t.length : 0;
      if (!s && want.length) {
        const have = new Set(toks(t));
        const hit = want.filter((w) => have.has(w)).length;
        s = hit ? (hit / want.length) * 40 - (have.size - hit) * 0.5 : 0;
      }
      if (s > score) { best = id; score = s; }
    });
    return score >= 20 ? best : null;
  }
  function intent(q) {
    const s = q.trim().replace(/\s+/g, " ");
    let m;
    if (/^(what|who) is this site( about)?\??$|^what is on this site\??$|^what('s| is) here\??$/i.test(s)) return { kind: "site" };
    if ((m = s.match(/(?:what )?connects (.+?) (?:and|with|to) (.+?)\??$/i)) || (m = s.match(/^(?:how (?:is|are|do) )?(.+?) (?:and|to) (.+?) (?:connected|related|linked)\??$/i)))
      return { kind: "connect", a: m[1], b: m[2] };
    if ((m = s.match(/(?:read|know|start with) (?:first )?before (.+?)\??$/i)) || (m = s.match(/what comes before (.+?)\??$/i)))
      return { kind: "before", a: m[1] };
    if ((m = s.match(/(?:comes|read|next) after (.+?)\??$/i)) || (m = s.match(/what builds on (.+?)\??$/i)))
      return { kind: "after", a: m[1] };
    if ((m = s.match(/^what is (.+?) about\??$/i)) || (m = s.match(/^(?:what is )?related to (.+?)\??$/i)) || (m = s.match(/^what is related to (.+?)\??$/i)))
      return { kind: "about", a: m[1] };
    return { kind: "search" };
  }
  function item(id) { return `<a data-x="${e(id)}" href="${e(href(id))}">${e((S.nodes[id] || {}).title || id)}</a><span class="dim"> · ${e(kl(id))}</span>`; }
  function list(ids, empty) { return ids.length ? `<ol class="path">${ids.map((i) => `<li><div>${item(i)}</div></li>`).join("")}</ol>` : `<p class="why">${empty}</p>`; }
  function passagesHTML(res, head, shown) {
    const ps = ((res && res.passages) || []).filter((p) => !shown || !shown.has(p.id));
    if (!ps.length) return "";
    const seen = new Map();
    ps.forEach((p) => { const k = p.id; if (!seen.has(k)) seen.set(k, Object.assign({}, p, { more: [] })); else if (p.section && seen.get(k).section !== p.section) seen.get(k).more.push(p); });
    return `<div class="sub" style="margin-top:16px">${head}</div><ul class="rel">${[...seen.values()].map((p) =>
      `<li><div><a data-x="${e(p.id)}" href="${e(p.url)}${p.anchor ? "#" + e(p.anchor) : ""}">${e(p.title)}</a>${p.section ? `<span class="dim"> › ${e(p.section)}</span>` : ""}${p.more.map((m) => `<span class="dim"> · also </span><a class="dim" href="${e(p.url)}#${e(m.anchor)}">${e(m.section)}</a>`).join("")}</div><div class="why">${e(snippet(p.text))}</div></li>`).join("")}</ul>`;
  }
  const snippet = (t) => { t = String(t || "").replace(/\s+/g, " ").trim(); return t.length > 180 ? t.slice(0, 177).replace(/\s+\S*$/, "") + " …" : t; };

  function chain(items, a, b) {
    // breadth-first over pages, the references they cite and their topics; returns the hops between pages
    const adj = new Map(), add = (x, y, how) => { if (!adj.has(x)) adj.set(x, []); adj.get(x).push([y, how]); };
    items.forEach((it) => {
      (it.links || []).forEach((l) => { add(it.id, l, "builds on"); add(l, it.id, "is built on by"); });
      (it.mentions || []).forEach((l) => { add(it.id, l, "links to"); add(l, it.id, "is linked from"); });
      (it.cites || []).forEach((c) => { add(it.id, c, "cite"); add(c, it.id, "cite"); });
      (it.topics || []).forEach((t) => { add(it.id, "topic:" + t, "tag"); add("topic:" + t, it.id, "tag"); });
    });
    const prev = new Map([[a, null]]), queue = [a];
    while (queue.length) {
      const u = queue.shift();
      if (u === b) break;
      (adj.get(u) || []).forEach(([v, how]) => { if (!prev.has(v)) { prev.set(v, [u, how]); queue.push(v); } });
    }
    if (!prev.has(b)) return null;
    const path = [];
    for (let v = b; v !== a; v = prev.get(v)[0]) path.unshift([prev.get(v)[0], v, prev.get(v)[1]]);
    const hops = [];
    for (let i = 0; i < path.length; i++) {
      const [x, y, how] = path[i];
      if (CONTENT.has((S.nodes[y] || {}).type) || y === b) { hops.push({ a: x, b: y, how }); continue; }
      const [, z] = path[i + 1] || [];            // through a reference or a topic: the next step reaches a page
      const via = (S.nodes[y] || {}).title || y;
      hops.push({ a: x, b: z, how: y.startsWith("topic:") ? `both tagged ${via}` : `both cite “${via}”` });
      i++;
    }
    return hops;
  }

  async function mapAnswer(it, question) {
    const md = await loadMap(), items = md.items || [];
    const shown = new Set();
    if (it.kind === "site") {
      const by = {};
      items.forEach((x) => { by[x.type] = (by[x.type] || 0) + 1; });
      const parts = Object.entries(by).map(([t, n]) => `${n} ${e(((S.kinds || {})[t] || t).toLowerCase())}${n === 1 ? "" : "s"}`);
      const below = {};
      items.forEach((x) => (x.links || []).forEach((l) => { below[l] = (below[l] || 0) + 1; }));
      const roots = items.filter((x) => !(x.links || []).length && below[x.id]).sort((p, q) => below[q.id] - below[p.id]).slice(0, 4);
      const tags = {};
      items.forEach((x) => (x.topics || []).forEach((t) => { tags[t] = (tags[t] || 0) + 1; }));
      const groups = {};
      Object.keys(tags).forEach((t) => { const nd = S.nodes["topic:" + t] || { title: t, group: "" }; (groups[nd.group || "Topics"] = groups[nd.group || "Topics"] || []).push([t, nd.title, tags[t]]); });
      return { html: `<div class="sub">This site</div><p>${parts.join(", ")}, all on one <a href="/explore/">map</a>: a page hangs from what it builds on.</p>` +
        (roots.length ? `<div class="sub" style="margin-top:12px">Where it starts</div><ol class="path">${roots.map((x) => `<li><div>${item(x.id)}</div><div class="why">${below[x.id]} page${below[x.id] === 1 ? "" : "s"} build on it</div></li>`).join("")}</ol>` : "") +
        `<div class="sub" style="margin-top:12px">By topic</div>${Object.entries(groups).map(([g, ts]) => `<p class="why"><b>${e(g)}</b> · ${ts.map(([t, title, n]) => `<a href="/topics/${e(t)}/">${e(title)}</a> (${n})`).join(", ")}</p>`).join("")}` +
        `<p class="why">Ask about any page by name, or open one and use the Ask button there: it then knows which page you mean.</p>`, shown, search: false };
    }
    if (it.kind === "connect") {
      const a = findPage(it.a), b = findPage(it.b);
      if (!a || !b) return null;
      shown.add(a); shown.add(b);
      let h = `<div class="sub">The chain between them</div>`;
      if (a === b) h += `<p>Those are the same page: ${item(a)}.</p>`;
      else {
        const hops = chain(items, a, b);
        if (!hops || !hops.length) h += `<p>${item(a)} and ${item(b)} are not linked on the map: no chain of “builds on”, citations or links joins them.</p>`;
        else {
          hops.forEach((x) => { shown.add(x.a); shown.add(x.b); });
          h += `<ol class="chain">${hops.map((x, i) => `<li>${i ? "" : `<div>${item(x.a)}</div>`}<div class="how">${e(x.how)}</div><div>${item(x.b)}</div></li>`).join("")}</ol><p class="why">${hops.length} link${hops.length === 1 ? "" : "s"} apart on the map.</p>`;
        }
      }
      return { html: h, shown, search: true };
    }
    const id = findPage(it.a);
    if (!id) return null;
    const v = await viewOf(id);
    shown.add(id);
    const title = (S.nodes[id] || {}).title || id;
    if (it.kind === "before") {
      const ids = v.path.filter((p) => p.role === "before").map((p) => p.id);
      ids.forEach((i) => shown.add(i));
      const me = items.find((x) => x.id === id) || { links: [] };
      return { html: `<div class="sub">Read before ${e(title)}</div>${list(ids, "Nothing comes before it: it is a root of the map.")}${(me.links || []).length ? `<p class="why">It builds directly on ${me.links.map((i) => e((S.nodes[i] || {}).title || i)).join("; ")}.</p>` : ""}`, shown, search: true };
    }
    if (it.kind === "after") {
      const ids = v.path.filter((p) => p.role === "after").map((p) => p.id);
      ids.forEach((i) => shown.add(i));
      return { html: `<div class="sub">After ${e(title)}, in reading order</div>${list(ids, "Nothing builds on it yet.")}`, shown, search: true };
    }
    const me = items.find((x) => x.id === id) || { links: [] };
    const up = (me.links || []), down = items.filter((x) => (x.links || []).includes(id)).map((x) => x.id);
    up.concat(down).forEach((i) => shown.add(i));
    const rel = v.related.filter((r) => !shown.has(r.id));
    rel.forEach((r) => shown.add(r.id));
    const nd = S.nodes[id] || {};
    return { html: `<div class="sub">${item(id)}</div>${nd.desc ? `<p>${e(nd.desc)}</p>` : ""}` +
      (up.length ? `<p><b>Builds on</b> ${up.map(item).join("; ")}</p>` : "") +
      (down.length ? `<p><b>Built on by</b> ${down.map(item).join("; ")}</p>` : "") +
      (rel.length ? `<div class="sub" style="margin-top:12px">Related</div><ul class="rel">${rel.map((x) => `<li><div>${item(x.id)}</div><div class="why">${e(x.why)}</div></li>`).join("")}</ul>` : "") +
      `<p class="why" style="margin-top:10px">Ask “what should I read before …” or “what comes after …” for the reading order.</p>`, shown, search: true, others: id };
  }

  // ----------------------------------------------------------------------------------------- one box
  function mount(root) {
    const $ = (s) => root.querySelector(s);
    const form = $("#ask-form"), input = $("#ask-q"), go = $("#ask-go"), model = $("#ask-model"),
      out = $("#ask-out"), stat = $("#ask-stat");
    const A = { on: false, limit: 0, left: 0, busy: false };
    function status(html, cls) { stat.hidden = false; stat.classList.remove("busy", "live"); if (cls) stat.classList.add(cls); stat.innerHTML = html; }

    async function ask(question) {
      question = (question || "").trim();
      if (!question) return;
      out.hidden = false;
      out.innerHTML = '<p class="why">Reading the question …</p>';
      status("Updating …", "busy");
      try {
        const it = intent(question);
        let it2 = it;
        if (it.kind === "search" && PAGE && /\b(this page|this one|here)\b/i.test(question)) it2 = { kind: "about", a: "this" };
        const fromMap = it2.kind !== "search" ? await mapAnswer(it2, question).catch(() => null) : null;
        let html = fromMap ? fromMap.html : "";
        let res = null;
        if (!fromMap || fromMap.search) {
          const page = (fromMap && fromMap.others) || PAGE;
          res = await search(question, page);
          if (fromMap) {
            const others = new Set([...fromMap.shown].filter((id) => id !== fromMap.others));
            html += passagesHTML(res, "Where the pages talk about it", others);
          } else {
            const ps = res.passages || [];
            if (res.answer) html += `<div class="sub">From the pages</div><div class="said"><p>${e(res.answer)}</p></div>`;
            html += ps.length ? passagesHTML(res, "Pages that match best") : `<p class="why">No page matches those words. Try the name of a page or a method${A.on ? ", or ask for a written answer" : ""}.</p>`;
          }
        }
        out.innerHTML = html || '<p class="why">Type a question.</p>';
        const d = await loadData();
        status(`Answered from the map and ${d.passages.length} passages of this site.`, "live");
        const weak = !fromMap && res && (!(res.passages || []).length || ((res.passages[0] || {}).score || 0) < 2);
        model.classList.toggle("lead", A.on && weak);
        if (A.on && weak) stat.innerHTML += " The pages do not match the words well: a <b>written answer</b> can say what the closest passages do and do not cover.";
      } catch (err) {
        out.innerHTML = '<p class="why">Could not answer right now; press Ask again in a moment.</p>';
        status("", "");
      }
    }

    async function written(question) {
      question = (question || "").trim();
      if (!question || A.busy) return;
      A.busy = true;
      out.hidden = false;
      out.innerHTML = '<p class="why">Writing an answer from the matching passages …</p>';
      status("Updating …", "busy");
      try {
        const res = await fetch(API, { method: "POST", headers: { "Content-Type": "application/json", Accept: "application/json" },
          body: JSON.stringify({ q: question, page: PAGE }) });
        const r = await res.json();
        if (r.error) out.innerHTML = `<p class="why">${e(r.error)}</p>`;
        else {
          const src = r.sources || [], byN = new Map(src.map((s, i) => [s.n || i + 1, s]));
          const cite = (t) => t.replace(/\[(\d+)\]/g, (m, n) => { const s = byN.get(+n); return s ? `<a class="cite" href="${e(s.url)}${s.anchor ? "#" + e(s.anchor) : ""}" title="${e(s.title)}">[${n}]</a>` : m; });
          const groups = [];
          src.forEach((s, i) => { let g = groups.find((x) => x.url === s.url); if (!g) { g = { url: s.url, title: s.title, parts: [] }; groups.push(g); } g.parts.push({ n: s.n || i + 1, section: s.section, anchor: s.anchor }); });
          out.innerHTML = `<div class="sub">A written answer, from ${src.length} passage${src.length === 1 ? "" : "s"}</div><div class="said">${String(r.answer || "").split(/\n{2,}/).map((p) => `<p>${cite(e(p))}</p>`).join("")}</div>
            <ol class="srcs">${groups.map((g) => `<li><span class="n">${g.parts.map((p) => "[" + p.n + "]").join("")}</span> <a href="${e(g.url)}">${e(g.title)}</a>${g.parts.filter((p) => p.section).length ? `<span class="dim"> › ${g.parts.filter((p) => p.section).map((p) => `<a class="dim" href="${e(g.url)}#${e(p.anchor)}">${e(p.section)}</a>`).join(" · ")}</span>` : ""}</li>`).join("")}</ol>
            <p class="why">Put together from these passages only; it is not the author's writing. Read the pages for the full story.</p>`;
        }
        if (typeof r.left === "number") { A.left = r.left; leftLabel(); }
        status(typeof r.left === "number" ? `${r.left} written answer${r.left === 1 ? "" : "s"} left today from this connection.` : "", "live");
      } catch (err) {
        out.innerHTML = '<p class="why">No written answer right now; the pointers above still stand.</p>';
        status("", "");
      }
      A.busy = false;
    }
    function leftLabel() { const l = $("#ask-left"); if (l) l.textContent = A.limit ? `· ${A.left} left today` : ""; model.disabled = A.left <= 0; }

    form.addEventListener("submit", (ev) => { ev.preventDefault(); ask(input.value); });
    model.addEventListener("click", () => written(input.value));
    root.querySelectorAll("#ask-eg .eg").forEach((b) => b.addEventListener("click", () => { input.value = b.dataset.q; ask(b.dataset.q); }));
    apiStatus().then((r) => { if (r && r.on) { A.on = true; A.limit = r.limit; A.left = r.left; model.hidden = false; leftLabel(); } });
    return { ask, input, go, stat };
  }

  // ------------------------------------------------------------------------------------- page and widget
  function start() {
    const page = document.getElementById("ask-form");
    if (page && location.pathname.replace(/index\.html$/, "") === "/ask/") {
      const box = mount(document);
      const pre = new URLSearchParams(location.search).get("q");
      if (pre) { box.input.value = pre; box.input.focus(); if (!pre.endsWith(" ")) box.ask(pre); }
      return;
    }
    const btn = document.createElement("button");
    btn.className = "askfab"; btn.type = "button"; btn.setAttribute("aria-expanded", "false");
    btn.innerHTML = 'Ask<span class="askfab-k">?</span>';
    const panel = document.createElement("aside");
    panel.className = "askpanel"; panel.hidden = true; panel.setAttribute("aria-label", "Ask about this site");
    const eg = PAGE ? [["What is this page about?", "What is this page about?"], ["Read before this", "What should I read before this page?"], ["What builds on this", "What comes after this page?"], ["Related", "What is related to this page?"]]
      : [["What is this site about?", "What is this site about?"]];
    panel.innerHTML = `<div class="askpanel-h"><span class="sub">Ask${PAGE ? " about this page" : ""}</span><button type="button" class="askpanel-x" aria-label="Close">×</button></div>
      ${PAGE ? `<p class="askpanel-ctx">Reading: <b>${e(TITLE)}</b>. Answered from this site's pages.</p>` : "<p class=\"askpanel-ctx\">Answered from this site's pages, nothing made up.</p>"}
      <form class="askbox" id="ask-form" autocomplete="off"><div class="askrow"><input class="find" id="ask-q" type="search" placeholder="a paper, a concept, or what connects two pages …" aria-label="Your question" maxlength="300"><button class="chip" type="submit" id="ask-go">Ask</button><button class="chip" type="button" id="ask-model" hidden>Written answer <span class="left" id="ask-left"></span></button></div>
      <div class="chips examples" id="ask-eg">${eg.map(([l, q]) => `<button type="button" class="chip eg" data-q="${e(q)}">${e(l)}</button>`).join("")}</div></form>
      <div class="answer" id="ask-out" hidden></div><p class="pystat" id="ask-stat" hidden></p>
      <p class="askpanel-more"><a href="/ask/">Open the Ask page →</a></p>`;
    document.body.append(btn, panel);
    let box = null, opened = false;
    function open() {
      panel.hidden = false; btn.setAttribute("aria-expanded", "true");
      if (!box) box = mount(panel);
      box.input.focus();
      if (PAGE && !opened) { opened = true; box.ask("What is this page about?"); }   // the page's own overview comes up at once
    }
    function close() { panel.hidden = true; btn.setAttribute("aria-expanded", "false"); }
    btn.addEventListener("click", () => (panel.hidden ? open() : close()));
    panel.querySelector(".askpanel-x").addEventListener("click", close);
    document.addEventListener("keydown", (ev) => { if (ev.key === "Escape" && !panel.hidden) { close(); btn.focus(); } });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start); else start();
})();
