// The live preview: an iframe of the real rendered page (/preview/<id>). Updates patch the page in place so the
// scroll position, and the state of interactive figures that did not change, survive typing.
import { h } from "./lib.js";

export function createPreview(container, id, { onReady } = {}) {
  const frame = h("iframe.preview-frame", { title: "Preview of the page", src: `/preview/${encodeURIComponent(id)}` });
  const note = h("div.preview-note", { hidden: true });
  container.append(frame, note);
  let ready = false, pending = null, reloadScroll = null;
  let syncTarget = null;

  function matchTheme() {
    const d = doc();
    if (!d || !d.documentElement) return;
    const t = document.documentElement.dataset.theme;
    if (t) d.documentElement.setAttribute("data-theme", t); else d.documentElement.removeAttribute("data-theme");
  }
  window.addEventListener("studio-theme", matchTheme);

  frame.addEventListener("load", () => {
    ready = true;
    matchTheme();
    try { if (reloadScroll !== null) frame.contentWindow.scrollTo(0, reloadScroll); } catch (e) { /* error page */ }
    reloadScroll = null;
    // links inside the preview open other pages' previews; external links open a new tab
    try {
      frame.contentDocument.addEventListener("click", (e) => {
        const a = e.target.closest && e.target.closest("a[href]");
        if (!a) return;
        const url = new URL(a.getAttribute("href"), frame.contentWindow.location.href);
        if (url.origin !== location.origin) { e.preventDefault(); window.open(url.href, "_blank", "noopener,noreferrer"); }
      });
    } catch (e) { /* not same-origin: ignore */ }
    if (pending) { const p = pending; pending = null; update(p); }
    if (onReady) onReady();
  });

  function doc() { try { return frame.contentDocument; } catch (e) { return null; } }

  function reload() {
    try { reloadScroll = frame.contentWindow.scrollY; } catch (e) { reloadScroll = 0; }
    ready = false;
    frame.src = `/preview/${encodeURIComponent(id)}?t=${Date.now()}`;
  }

  function update(html) {
    if (!ready) { pending = html; return; }
    const d = doc();
    if (!d || !d.body) { reload(); return; }
    const next = new DOMParser().parseFromString(html, "text/html");
    // a change in the stylesheets or scripts needs a real reload
    const sig = (dd) => [...dd.querySelectorAll("head link[rel=stylesheet], script[src]")].map((n) => n.getAttribute("href") || n.getAttribute("src")).join("|");
    if (sig(d) !== sig(next)) { reload(); return; }
    if (d.title !== next.title) d.title = next.title;
    const added = [];
    morphChildren(d.body, next.body, d, added);
    copyAttrs(d.body, next.body);
    const figs = added.flatMap((n) => (n.matches && n.matches(".fig") ? [n] : n.querySelectorAll ? [...n.querySelectorAll(".fig")] : []));
    if (figs.length) {
      const T = frame.contentWindow && frame.contentWindow.Bazinga;
      if (T && T.figures && T.figures.init) T.figures.init(d);
      else reload();
    }
  }

  function setNote(text, kind = "info") {
    note.hidden = !text;
    note.className = `preview-note ${kind}`;
    note.textContent = text || "";
  }

  // --- scroll sync: editor position -> preview position, through matching headings, figures and equations --------
  function anchors() {
    const d = doc();
    if (!d) return null;
    const body = d.querySelector(".post-body") || d.body;
    const pick = (sel) => [...body.querySelectorAll(sel)].filter((el) => !el.closest("nav, aside, .toc"));
    const top = (el) => el.getBoundingClientRect().top + frame.contentWindow.scrollY;
    return {
      h: pick("h1, h2, h3, h4, h5, h6").map(top),
      fig: pick(".fig, figure.drawing, .drawing").map(top),
      math: pick(".math-display").map(top),
      start: top(body),
      height: d.documentElement.scrollHeight,
    };
  }

  // editorAnchors: [{y, kind}] in editor pixels; ratio: where the editor's top is; we map with piecewise lines.
  function syncTo(editorY, editorAnchors, editorHeight, bodyTop = 0) {
    const a = anchors();
    if (!a) return;
    const used = { h: 0, fig: 0, math: 0 };
    const pairs = [[0, 0], [Math.max(1, bodyTop), Math.max(0, a.start - 24)]];
    for (const e of editorAnchors) {
      const list = a[e.kind];
      const i = used[e.kind]++;
      if (list && i < list.length) {
        const p = list[i] - 80;
        if (p >= pairs[pairs.length - 1][1] && e.y >= pairs[pairs.length - 1][0]) pairs.push([e.y, p]);
      }
    }
    const view = frame.contentWindow.innerHeight;
    pairs.push([Math.max(editorHeight, pairs[pairs.length - 1][0] + 1), Math.max(a.height - view, pairs[pairs.length - 1][1])]);
    let y = 0;
    for (let i = 1; i < pairs.length; i++) {
      const [e0, p0] = pairs[i - 1], [e1, p1] = pairs[i];
      if (editorY <= e1 || i === pairs.length - 1) {
        const f = e1 > e0 ? Math.min(1, Math.max(0, (editorY - e0) / (e1 - e0))) : 0;
        y = p0 + f * (p1 - p0);
        break;
      }
    }
    syncTarget = y;
    frame.contentWindow.scrollTo({ top: y, behavior: "auto" });
  }

  function scrollToId(anchor) {
    const d = doc();
    const el = d && d.getElementById(anchor);
    if (el) el.scrollIntoView({ block: "start", behavior: "smooth" });
  }

  return { frame, update, reload, setNote, syncTo, scrollToId, get target() { return syncTarget; } };
}

// --- a small DOM morph -------------------------------------------------------------------------------------------------
function sameFigure(a, b) {
  return a.nodeType === 1 && b.nodeType === 1 && a.classList.contains("fig") && b.classList.contains("fig")
    && a.getAttribute("data-figure") === b.getAttribute("data-figure")
    && a.getAttribute("data-controls") === b.getAttribute("data-controls")
    && a.getAttribute("data-start") === b.getAttribute("data-start");
}

function copyAttrs(a, b) {
  for (const { name } of [...a.attributes]) if (!b.hasAttribute(name)) a.removeAttribute(name);
  for (const { name, value } of [...b.attributes]) if (a.getAttribute(name) !== value) a.setAttribute(name, value);
}

function morphNode(a, b, docA, added) {
  if (a.nodeType !== b.nodeType || a.nodeName !== b.nodeName) {
    const n = docA.importNode(b, true);
    a.replaceWith(n);
    added.push(n);
    return;
  }
  if (a.nodeType === 3 || a.nodeType === 8) { if (a.nodeValue !== b.nodeValue) a.nodeValue = b.nodeValue; return; }
  if (a.nodeType !== 1) return;
  if (a.classList.contains("fig")) {
    if (sameFigure(a, b)) return;          // keep the live figure as it is
    const n = docA.importNode(b, true);
    a.replaceWith(n);
    added.push(n);
    return;
  }
  if (a.nodeName === "SCRIPT" || a.namespaceURI === "http://www.w3.org/1998/Math/MathML" && a.nodeName.toLowerCase() === "math") {
    if (!a.isEqualNode(b)) { const n = docA.importNode(b, true); a.replaceWith(n); }
    return;
  }
  if (a.isEqualNode(b)) return;
  copyAttrs(a, b);
  if (a.nodeName === "DETAILS" && b.hasAttribute("open") === false && a.open) { /* keep the reader's choice */ }
  morphChildren(a, b, docA, added);
}

function morphChildren(a, b, docA, added) {
  const ac = [...a.childNodes], bc = [...b.childNodes];
  let start = 0;
  while (start < ac.length && start < bc.length && ac[start].isEqualNode(bc[start])) start++;
  let endA = ac.length - 1, endB = bc.length - 1;
  while (endA >= start && endB >= start && (ac[endA].isEqualNode(bc[endB]) || sameFigure(ac[endA], bc[endB]))) { endA--; endB--; }
  const midA = ac.slice(start, endA + 1), midB = bc.slice(start, endB + 1);
  const n = Math.min(midA.length, midB.length);
  // pair up the middle by position, then add or remove the rest
  for (let i = 0; i < n; i++) morphNode(midA[i], midB[i], docA, added);
  const ref = endA + 1 < ac.length ? ac[endA + 1] : null;
  for (let i = n; i < midB.length; i++) {
    const node = docA.importNode(midB[i], true);
    a.insertBefore(node, ref);
    added.push(node);
  }
  for (let i = n; i < midA.length; i++) midA[i].remove();
}
