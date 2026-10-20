// The map at /explore/: every public page as a node, placed by the build (data/graph.json).
// Hover, focus or tap a node: its neighbours light up nearest first, ring by ring, then everything
// the rings did not reach fades. Click (or a second tap on phones) opens the page.
//
// Markup: <div id="explore-root" data-graph="/data/graph.json" data-kinds='{"posts":"Writing"}'></div>
// Everything else is built here. Works with mouse, touch and keyboard.
(function () {
  "use strict";

  const SVGNS = "http://www.w3.org/2000/svg";
  const RING_MS = 170;
  const LABEL_FONT = 12.5;

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
  function sv(tag, attrs, parent) {
    const e = document.createElementNS(SVGNS, tag);
    for (const k in attrs || {}) {
      if (k === "text") e.textContent = attrs[k];
      else e.setAttribute(k, attrs[k]);
    }
    if (parent) parent.appendChild(e);
    return e;
  }
  function fold(s) {
    return String(s || "").normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase();
  }

  // ---------------------------------------------------------------------------------------- start
  function init(root) {
    if (root.dataset.ready) return;
    root.dataset.ready = "1";
    const url = root.dataset.graph || "/data/graph.json";
    let kindLabels = {};
    try { kindLabels = JSON.parse(root.dataset.kinds || "{}"); } catch (e) { kindLabels = {}; }
    root.classList.add("xmap");
    const status = el("p", { class: "xmap-status", role: "status", text: "Loading the map…" }, root);
    fetch(url)
      .then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then((g) => { status.remove(); build(root, g, kindLabels); })
      .catch(() => { status.textContent = "The map could not be loaded. Every page is still listed in the menu."; });
  }

  function build(root, g, kindLabels) {
    const nodes = g.nodes || [];
    if (!nodes.length) {
      el("p", { class: "xmap-status", text: "Nothing is published yet." }, root);
      return;
    }
    const byId = new Map(nodes.map((n) => [n.id, n]));
    const kinds = [...new Set(nodes.map((n) => n.kind))];
    const kindIndex = new Map(kinds.map((k, i) => [k, i % 6]));
    const topicLabels = g.topics || {};
    const rings = g.rings || {};
    const edges = (g.edges || []).filter((e) => byId.has(e.source) && byId.has(e.target));
    const adj = new Map(nodes.map((n) => [n.id, new Set()]));       // builds on, mentions, series
    const citeAdj = new Map(nodes.map((n) => [n.id, new Set()]));   // same sources
    edges.forEach((e) => {
      const m = e.type === "cites" ? citeAdj : e.type === "topic" ? null : adj;
      if (m) { m.get(e.source).add(e.target); m.get(e.target).add(e.source); }
    });

    // --- toolbar: search + topic chips
    const bar = el("div", { class: "xmap-bar" }, root);
    const searchWrap = el("div", { class: "xmap-search" }, bar);
    const sid = "xmap-q-" + Math.random().toString(36).slice(2, 7);
    el("label", { for: sid, class: "xmap-sr", text: "Find a page on the map" }, searchWrap);
    const search = el("input", { id: sid, type: "search", placeholder: "Find a page…", autocomplete: "off", spellcheck: "false" }, searchWrap);
    const counts = {};
    nodes.forEach((n) => (n.topics || []).forEach((t) => { counts[t] = (counts[t] || 0) + 1; }));
    const topicList = Object.keys(counts).sort((a, b) => counts[b] - counts[a] || a.localeCompare(b));
    const chips = el("div", { class: "xmap-chips", role: "group", "aria-label": "Show one topic" }, bar);
    let activeTopic = "";
    const chipEls = [];
    function chip(slug, label) {
      const b = el("button", { type: "button", class: "xmap-chip", "aria-pressed": slug === "" ? "true" : "false", text: label }, chips);
      b.addEventListener("click", () => {
        activeTopic = activeTopic === slug ? "" : slug;
        chipEls.forEach((c) => c.b.setAttribute("aria-pressed", c.slug === activeTopic ? "true" : "false"));
        applyFilter();
      });
      chipEls.push({ b, slug });
    }
    chip("", "All");
    topicList.forEach((t) => chip(t, topicLabels[t] || t));

    // --- stage + info
    const layout = el("div", { class: "xmap-layout" }, root);
    const stage = el("div", { class: "xmap-stage" }, layout);
    const svg = sv("svg", { class: "xmap-svg", role: "group", "aria-label": "Map of the site: " + nodes.length + " pages" }, stage);
    const gEdges = sv("g", { class: "xmap-edges" }, svg);
    const gPulse = sv("g", { class: "xmap-pulses" }, svg);
    const gNodes = sv("g", { class: "xmap-nodes" }, svg);
    const gLabels = sv("g", { class: "xmap-labels", "aria-hidden": "true" }, svg);
    const zoom = el("div", { class: "xmap-zoom" }, stage);
    const zin = el("button", { type: "button", "aria-label": "Zoom in", text: "+" }, zoom);
    const zout = el("button", { type: "button", "aria-label": "Zoom out", text: "−" }, zoom);
    const zreset = el("button", { type: "button", "aria-label": "Fit the whole map", text: "Fit" }, zoom);
    const hint = el("p", { class: "xmap-hint", text: "" }, stage);

    const info = el("aside", { class: "xmap-info", "aria-live": "polite" }, layout);
    const legend = el("div", { class: "xmap-legend" }, root);
    kinds.forEach((k) => {
      const item = el("span", { class: "xmap-legend-item" }, legend);
      el("span", { class: "xmap-dot k" + kindIndex.get(k) }, item);
      item.appendChild(document.createTextNode(kindLabels[k] || (k.charAt(0).toUpperCase() + k.slice(1))));
    });
    const legEdge = el("span", { class: "xmap-legend-item" }, legend);
    el("span", { class: "xmap-line" }, legEdge);
    legEdge.appendChild(document.createTextNode("builds on or links to"));
    const legCite = el("span", { class: "xmap-legend-item" }, legend);
    el("span", { class: "xmap-line is-cite" }, legCite);
    legCite.appendChild(document.createTextNode("same sources"));
    if (edges.some((e) => e.type === "series")) {
      const legSeries = el("span", { class: "xmap-legend-item" }, legend);
      el("span", { class: "xmap-line is-series" }, legSeries);
      legSeries.appendChild(document.createTextNode("next in a series"));
    }

    const touch = window.matchMedia && window.matchMedia("(hover: none)").matches;
    hint.textContent = touch ? "Tap a page for its links; tap again to open it." : "";
    hint.hidden = !touch;

    // --- elements
    const maxDeg = Math.max(1, ...nodes.map((n) => n.degree || 0));
    const R = (n) => 4.5 + 7 * Math.sqrt((n.degree || 0) / maxDeg);
    // shared-topic edges shape the layout but are not drawn: too many, too little meaning
    const edgeEls = edges.filter((e) => e.type !== "topic").map((e) => {
      const line = sv("line", { class: "xmap-edge t-" + e.type }, gEdges);
      return { e, line };
    });
    const nodeEls = new Map();
    nodes.forEach((n) => {
      const a = sv("a", { href: n.url, class: "xmap-node k" + kindIndex.get(n.kind), "aria-label": n.title + (n.summary ? ". " + n.summary : "") }, gNodes);
      a.setAttribute("tabindex", "0");
      sv("title", { text: n.title }, a);
      const hit = sv("circle", { class: "xmap-hit", r: Math.max(R(n) + 8, 16) }, a);
      const c = sv("circle", { class: "xmap-circle", r: R(n) }, a);
      const label = sv("text", { class: "xmap-label", text: n.title }, gLabels);
      nodeEls.set(n.id, { n, a, c, hit, label, r: R(n), sx: 0, sy: 0, w: 0 });
    });

    // --- view transform (world = unit square)
    let W = 0, H = 0, base = { ax: 1, ay: 1, ox: 0, oy: 0 }, view = { k: 1, x: 0, y: 0 };
    function fit() {
      const rect = stage.getBoundingClientRect();
      W = Math.max(280, rect.width);
      H = Math.max(300, rect.height);
      svg.setAttribute("viewBox", "0 0 " + W + " " + H);
      svg.setAttribute("width", W);
      svg.setAttribute("height", H);
      const xs = nodes.map((n) => n.x), ys = nodes.map((n) => n.y);
      const minx = Math.min(...xs), maxx = Math.max(...xs), miny = Math.min(...ys), maxy = Math.max(...ys);
      const pad = W < 520 ? 28 : 56;
      const sx = (W - 2 * pad) / Math.max(0.05, maxx - minx);
      const sy = (H - 2 * pad) / Math.max(0.05, maxy - miny);
      // fill the stage, but never stretch one axis more than 1.6 times the other
      const s = Math.min(sx, sy);
      const ax = Math.min(sx, s * 1.6), ay = Math.min(sy, s * 1.6);
      base = { ax, ay, ox: (W - ax * (maxx + minx)) / 2, oy: (H - ay * (maxy + miny)) / 2 };
    }
    function toScreen(n) {
      return [(base.ox + base.ax * n.x) * view.k + view.x, (base.oy + base.ay * n.y) * view.k + view.y];
    }

    function render() {
      nodeEls.forEach((o) => {
        const p = toScreen(o.n);
        o.sx = p[0]; o.sy = p[1];
        o.c.setAttribute("cx", p[0]); o.c.setAttribute("cy", p[1]);
        o.hit.setAttribute("cx", p[0]); o.hit.setAttribute("cy", p[1]);
      });
      edgeEls.forEach(({ e, line }) => {
        const a = nodeEls.get(e.source), b = nodeEls.get(e.target);
        line.setAttribute("x1", a.sx); line.setAttribute("y1", a.sy);
        line.setAttribute("x2", b.sx); line.setAttribute("y2", b.sy);
      });
      placeLabels();
    }

    // Labels: biggest nodes first; try right, left, above, below; skip any that would overlap.
    function placeLabels() {
      const boxes = [];
      nodeEls.forEach((o) => boxes.push([o.sx - o.r, o.sy - o.r, o.sx + o.r, o.sy + o.r, o.n.id]));
      const zr = zoom.getBoundingClientRect(), sr = svg.getBoundingClientRect();
      if (zr.width) boxes.push([zr.left - sr.left - 4, zr.top - sr.top - 4, zr.right - sr.left + 4, zr.bottom - sr.top + 4, ""]);
      if (!hint.hidden) {
        const hr = hint.getBoundingClientRect();
        if (hr.width) boxes.push([hr.left - sr.left, hr.top - sr.top, hr.right - sr.left, hr.bottom - sr.top, ""]);
      }
      const focusSet = currentLit;
      const rank = (o) => (o.n.id === currentId ? 2 : focusSet && focusSet.has(o.n.id) ? 1 : 0);
      const order = [...nodeEls.values()].sort((a, b) => rank(b) - rank(a) || (b.n.degree || 0) - (a.n.degree || 0) || a.n.title.localeCompare(b.n.title));
      const placed = [];
      order.forEach((o) => {
        const text = o.n.title.length > 34 ? o.n.title.slice(0, 32).trimEnd() + "…" : o.n.title;
        if (o.label.textContent !== text) { o.label.textContent = text; o.w = 0; }
        const important = !!(focusSet && focusSet.has(o.n.id));
        if (o.label.classList.contains("is-key") !== important) { o.label.classList.toggle("is-key", important); o.w = 0; }
        if (!o.w) {
          let m = 0;
          try { m = o.label.getComputedTextLength(); } catch (e) { m = 0; }
          o.w = m > 0 ? m + 2 : text.length * LABEL_FONT * 0.6;
        }
        const w = o.w, h = LABEL_FONT + 3, gap = o.r + 4;
        const tries = [
          [o.sx + gap, o.sy - h / 2, "start"],
          [o.sx - gap - w, o.sy - h / 2, "end"],
          [o.sx - w / 2, o.sy - gap - h, "middle"],
          [o.sx - w / 2, o.sy + gap, "middle"],
        ];
        let ok = null;
        for (const t of tries) {
          const box = [t[0], t[1], t[0] + w, t[1] + h];
          if (box[0] < 2 || box[2] > W - 2 || box[1] < 2 || box[3] > H - 2) continue;
          const hitsNode = boxes.some((b) => b[4] !== o.n.id && b[0] < box[2] && b[2] > box[0] && b[1] < box[3] && b[3] > box[1]);
          const hitsLabel = placed.some((b) => b[0] < box[2] + 3 && b[2] + 3 > box[0] && b[1] < box[3] && b[3] > box[1]);
          if (!hitsNode && !hitsLabel) { ok = [t, box]; break; }
        }
        if (ok) {
          placed.push(ok[1]);
          const [t] = ok;
          const x = t[2] === "start" ? t[0] : t[2] === "end" ? t[0] + w : t[0] + w / 2;
          o.label.setAttribute("x", x);
          o.label.setAttribute("y", t[1] + h - 4);
          o.label.setAttribute("text-anchor", t[2]);
          o.label.classList.remove("is-hidden");
        } else {
          o.label.classList.add("is-hidden");
        }
      });
    }

    // --- focus: rings nearest first, then fade what they did not reach
    let currentId = null, currentLit = null, timers = [];
    function clearTimers() { timers.forEach(clearTimeout); timers = []; }
    function focusNode(id, opts) {
      if (id === currentId) return;
      clearTimers();
      currentId = id;
      svg.classList.remove("is-faded");
      gPulse.textContent = "";
      nodeEls.forEach((o) => { o.a.classList.remove("is-lit", "is-focus"); o.a.style.removeProperty("--d"); });
      edgeEls.forEach(({ line }) => { line.classList.remove("is-lit"); line.style.removeProperty("--d"); });
      if (!id) {
        currentLit = null;
        svg.classList.remove("has-focus");
        showInfo(null);
        placeLabels();
        return;
      }
      const o = nodeEls.get(id);
      const levels = [[id]].concat(rings[id] || []);
      const depth = new Map();
      levels.forEach((ids, d) => ids.forEach((x) => depth.set(x, d)));
      currentLit = new Set(depth.keys());
      svg.classList.add("has-focus");
      o.a.classList.add("is-focus");
      const reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      const step = reduce ? 0 : RING_MS;
      depth.forEach((d, x) => {
        const ne = nodeEls.get(x);
        if (!ne) return;
        ne.a.style.setProperty("--d", d * step + "ms");
        ne.a.classList.add("is-lit");
      });
      edgeEls.forEach(({ e, line }) => {
        if (e.type === "topic" || e.type === "cites") return;
        const da = depth.get(e.source), db = depth.get(e.target);
        if (da === undefined || db === undefined || Math.abs(da - db) !== 1) return;
        line.style.setProperty("--d", Math.max(da, db) * step - step / 2 + "ms");
        line.classList.add("is-lit");
      });
      if (!reduce) {
        for (let d = 1; d < levels.length; d++) {
          const maxR = Math.max(...levels[d].map((x) => {
            const ne = nodeEls.get(x);
            return ne ? Math.hypot(ne.sx - o.sx, ne.sy - o.sy) : 0;
          }));
          const ring = sv("circle", { class: "xmap-pulse", cx: o.sx, cy: o.sy, r: 4 }, gPulse);
          ring.style.setProperty("--d", (d - 1) * step + "ms");
          ring.style.setProperty("--to", String(Math.max(1, maxR / 4)));
        }
      }
      timers.push(setTimeout(() => svg.classList.add("is-faded"), levels.length * step + 60));
      showInfo(o.n, depth);
      placeLabels();
      if (opts && opts.center) centreOn(o);
    }

    function showInfo(n, depth) {
      info.textContent = "";
      if (!n) {
        el("p", { class: "xmap-info-lead", text: nodes.length + " pages, " + edges.filter((e) => e.type !== "topic" && e.type !== "cites").length + " links between them." }, info);
        el("p", { class: "xmap-info-muted", text: touch ? "Tap a page to start." : "Point at a page, or use Tab to walk through them." }, info);
        return;
      }
      el("p", { class: "xmap-info-kind", text: kindLabels[n.kind] || n.kind }, info);
      const h = el("h2", { class: "xmap-info-title" }, info);
      el("a", { href: n.url, text: n.title }, h);
      if (n.summary) el("p", { class: "xmap-info-summary", text: n.summary }, info);
      if ((n.topics || []).length) {
        const t = el("p", { class: "xmap-info-topics" }, info);
        n.topics.forEach((s) => el("span", { class: "xmap-tag", text: topicLabels[s] || s }, t));
      }
      const listOf = (set) => [...(set || [])].map((x) => byId.get(x)).filter(Boolean).sort((a, b) => a.title.localeCompare(b.title));
      const near = listOf(adj.get(n.id));
      const same = listOf(citeAdj.get(n.id)).filter((m) => !adj.get(n.id).has(m.id));
      function group(title, items, max) {
        if (!items.length) return;
        el("p", { class: "xmap-info-sub", text: title }, info);
        const ul = el("ul", { class: "xmap-info-list" }, info);
        items.slice(0, max).forEach((m) => {
          const li = el("li", {}, ul);
          const a = el("a", { href: m.url, text: m.title }, li);
          a.addEventListener("mouseenter", () => nodeEls.get(m.id).a.classList.add("is-peek"));
          a.addEventListener("mouseleave", () => nodeEls.get(m.id).a.classList.remove("is-peek"));
        });
        if (items.length > max) el("p", { class: "xmap-info-muted", text: "and " + (items.length - max) + " more" }, info);
      }
      group("Linked with", near, 8);
      group("Same sources", same, 4);
      if (!near.length && !same.length) el("p", { class: "xmap-info-muted", text: "Not linked to other pages yet." }, info);
      const reached = depth ? depth.size - 1 : 0;
      if (reached > near.length) el("p", { class: "xmap-info-muted", text: reached + " pages within " + (Math.max(...depth.values())) + " steps." }, info);
      el("a", { class: "xmap-open", href: n.url, text: "Open the page →" }, info);
    }

    // --- filtering
    function applyFilter() {
      const q = fold(search.value.trim());
      let first = null;
      nodeEls.forEach((o) => {
        const inTopic = !activeTopic || (o.n.topics || []).includes(activeTopic);
        const hay = fold(o.n.title + " " + (o.n.summary || "") + " " + (o.n.topics || []).join(" "));
        const match = !q || q.split(/\s+/).every((w) => hay.includes(w));
        const on = inTopic && match;
        o.a.classList.toggle("is-out", !on);
        o.label.classList.toggle("is-out", !on);
        if (on && q && !first) first = o;
      });
      edgeEls.forEach(({ e, line }) => {
        const out = nodeEls.get(e.source).a.classList.contains("is-out") || nodeEls.get(e.target).a.classList.contains("is-out");
        line.classList.toggle("is-out", out);
      });
      return first;
    }
    search.addEventListener("input", applyFilter);
    search.addEventListener("keydown", (ev) => {
      if (ev.key === "Enter") {
        ev.preventDefault();
        const first = applyFilter();
        if (first) { focusNode(first.n.id, { center: true }); first.a.focus({ preventScroll: true }); }
      } else if (ev.key === "Escape") {
        search.value = "";
        applyFilter();
      }
    });

    // --- pointer: hover on desktop, tap-tap on touch, drag to pan, wheel/pinch to zoom
    const pointers = new Map();
    let drag = null, moved = false, pinch = null;
    nodeEls.forEach((o) => {
      o.a.addEventListener("pointerenter", (ev) => { if (ev.pointerType === "mouse" && !drag) focusNode(o.n.id); });
      o.a.addEventListener("focus", () => focusNode(o.n.id));
      o.a.addEventListener("click", (ev) => {
        if (moved) { ev.preventDefault(); return; }
        if (lastPointerType !== "mouse" && tapped !== o.n.id) {
          // first tap shows the connections; a second tap on the same page opens it
          ev.preventDefault();
          tapped = o.n.id;
          focusNode(o.n.id);
        }
      });
      o.a.addEventListener("keydown", (ev) => {
        if (ev.key === "Escape") { focusNode(null); o.a.blur(); }
        if (ev.key.startsWith("Arrow")) { ev.preventDefault(); stepFocus(o, ev.key); }
      });
    });
    let lastPointerType = "mouse";
    let tapped = null;
    svg.addEventListener("pointerleave", (ev) => { if (ev.pointerType === "mouse" && !drag) focusNode(null); });

    function stepFocus(o, key) {
      const dir = { ArrowRight: [1, 0], ArrowLeft: [-1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] }[key];
      let best = null, bestScore = Infinity;
      nodeEls.forEach((p) => {
        if (p === o || p.a.classList.contains("is-out")) return;
        const dx = p.sx - o.sx, dy = p.sy - o.sy;
        const along = dx * dir[0] + dy * dir[1];
        if (along <= 1) return;
        const across = Math.abs(dx * dir[1] - dy * dir[0]);
        const score = along + across * 2.5;
        if (score < bestScore) { bestScore = score; best = p; }
      });
      if (best) best.a.focus();
    }

    stage.addEventListener("pointerdown", (ev) => {
      lastPointerType = ev.pointerType;
      pointers.set(ev.pointerId, [ev.clientX, ev.clientY]);
      moved = false;
      if (pointers.size === 1) drag = { x: ev.clientX, y: ev.clientY, vx: view.x, vy: view.y };
      if (pointers.size === 2) {
        const [a, b] = [...pointers.values()];
        pinch = { d: Math.hypot(a[0] - b[0], a[1] - b[1]), k: view.k, cx: (a[0] + b[0]) / 2, cy: (a[1] + b[1]) / 2, vx: view.x, vy: view.y };
        drag = null;
      }
    });
    stage.addEventListener("pointermove", (ev) => {
      if (!pointers.has(ev.pointerId)) return;
      pointers.set(ev.pointerId, [ev.clientX, ev.clientY]);
      if (pinch && pointers.size === 2) {
        const [a, b] = [...pointers.values()];
        const d = Math.hypot(a[0] - b[0], a[1] - b[1]);
        const rect = svg.getBoundingClientRect();
        zoomAt(pinch.cx - rect.left, pinch.cy - rect.top, (pinch.k * d) / pinch.d, pinch);
        moved = true;
      } else if (drag) {
        const dx = ev.clientX - drag.x, dy = ev.clientY - drag.y;
        if (!moved && Math.hypot(dx, dy) < 6) return;
        if (!moved) { stage.setPointerCapture(ev.pointerId); stage.classList.add("is-dragging"); }
        moved = true;
        view.x = drag.vx + dx;
        view.y = drag.vy + dy;
        render();
      }
    });
    function endPointer(ev) {
      pointers.delete(ev.pointerId);
      if (pointers.size < 2) pinch = null;
      if (pointers.size === 0) {
        drag = null;
        stage.classList.remove("is-dragging");
        setTimeout(() => { moved = false; }, 0);
      }
    }
    stage.addEventListener("pointerup", endPointer);
    stage.addEventListener("pointercancel", endPointer);
    stage.addEventListener("click", (ev) => {
      if (!moved && ev.target === svg) { tapped = null; focusNode(null); }
    });
    stage.addEventListener("wheel", (ev) => {
      ev.preventDefault();
      const rect = svg.getBoundingClientRect();
      const factor = Math.exp(-ev.deltaY * (ev.ctrlKey ? 0.01 : 0.0018));
      zoomAt(ev.clientX - rect.left, ev.clientY - rect.top, view.k * factor);
    }, { passive: false });

    function zoomAt(px, py, k, from) {
      const f = from ? { k: from.k, x: from.vx, y: from.vy } : { k: view.k, x: view.x, y: view.y };
      k = Math.max(0.6, Math.min(6, k));
      const wx = (px - f.x) / f.k;
      const wy = (py - f.y) / f.k;
      view.k = k;
      view.x = px - wx * k;
      view.y = py - wy * k;
      render();
    }
    function zoomBy(f) { zoomAt(W / 2, H / 2, view.k * f); }
    function centreOn(o) {
      const p = toScreen(o.n);
      if (p[0] > 40 && p[0] < W - 40 && p[1] > 40 && p[1] < H - 40) return;
      view.x += W / 2 - p[0];
      view.y += H / 2 - p[1];
      render();
    }
    zin.addEventListener("click", () => zoomBy(1.35));
    zout.addEventListener("click", () => zoomBy(1 / 1.35));
    zreset.addEventListener("click", () => { view = { k: 1, x: 0, y: 0 }; render(); });

    // --- size
    let raf = 0;
    function resize() {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => { fit(); render(); });
    }
    if (window.ResizeObserver) new ResizeObserver(resize).observe(stage);
    else window.addEventListener("resize", resize);
    fit();
    render();
    showInfo(null);

    // deep link: /explore/#post:attention focuses that page
    const hash = decodeURIComponent(location.hash.slice(1));
    if (hash && nodeEls.has(hash)) focusNode(hash, { center: true });
  }

  function start() {
    document.querySelectorAll("#explore-root, [data-explore]").forEach(init);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();
