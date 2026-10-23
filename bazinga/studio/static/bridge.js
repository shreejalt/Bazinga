// Runs inside the Editor's preview frames. Previews are served from a second port (another origin), so the page's
// own scripts and its figures cannot read the Editor or write through it. The Editor and the frame talk by messages
// only, and only with each other:
//   Editor -> frame: {bz: "theme", theme} | {bz: "update", html} | {bz: "sync", ...} | {bz: "scrollTo", y}
//                    | {bz: "scrollToId", id}
//   frame -> Editor: {bz: "size", height} | {bz: "scroll", y} | {bz: "reload"}
(function () {
  "use strict";
  var me = document.currentScript;
  var EDITOR = me && me.getAttribute("data-editor");
  if (!EDITOR || window.parent === window) return;

  function send(msg) { try { window.parent.postMessage(msg, EDITOR); } catch (e) { /* the Editor went away */ } }

  // --- size and scroll, reported to the Editor ------------------------------------------------------------------
  var lastH = -1;
  function reportSize() {
    var h = document.documentElement ? document.documentElement.scrollHeight : 0;
    if (h !== lastH) { lastH = h; send({ bz: "size", height: h }); }
  }
  var scrollQueued = false;
  window.addEventListener("scroll", function () {
    if (scrollQueued) return;
    scrollQueued = true;
    requestAnimationFrame(function () { scrollQueued = false; send({ bz: "scroll", y: window.scrollY }); });
  }, { passive: true });
  try { new ResizeObserver(reportSize).observe(document.documentElement); } catch (e) { /* older browsers */ }
  window.addEventListener("load", reportSize);
  reportSize();

  // links to other sites open in a new tab; links to other pages open their previews in this frame
  document.addEventListener("click", function (e) {
    var a = e.target.closest && e.target.closest("a[href]");
    if (!a) return;
    var url;
    try { url = new URL(a.getAttribute("href"), location.href); } catch (err) { return; }
    if (url.protocol !== "http:" && url.protocol !== "https:") { e.preventDefault(); return; }
    if (url.origin !== location.origin) { e.preventDefault(); window.open(url.href, "_blank", "noopener,noreferrer"); }
  });

  // --- messages from the Editor ----------------------------------------------------------------------------------
  window.addEventListener("message", function (e) {
    if (e.source !== window.parent || e.origin !== EDITOR) return;
    var m = e.data || {};
    if (m.bz === "theme") {
      if (m.theme === "light" || m.theme === "dark") document.documentElement.setAttribute("data-theme", m.theme);
      else document.documentElement.removeAttribute("data-theme");
    } else if (m.bz === "update" && typeof m.html === "string") {
      update(m.html);
    } else if (m.bz === "sync") {
      syncTo(+m.editorY || 0, Array.isArray(m.anchors) ? m.anchors : [], +m.editorHeight || 0, +m.bodyTop || 0);
    } else if (m.bz === "scrollTo") {
      window.scrollTo(0, +m.y || 0);
    } else if (m.bz === "scrollToId" && typeof m.id === "string") {
      var el = document.getElementById(m.id);
      if (el) el.scrollIntoView({ block: "start", behavior: "smooth" });
    }
  });

  // --- live update: patch the page in place so the scroll position and untouched figures survive typing ----------
  function update(html) {
    var d = document;
    var next = new DOMParser().parseFromString(html, "text/html");
    var sig = function (dd) {
      return Array.prototype.map.call(dd.querySelectorAll("head link[rel=stylesheet], script[src]"), function (n) {
        return n.getAttribute("href") || n.getAttribute("src");
      }).filter(function (s) { return s !== "/_studio/bridge.js"; }).join("|");
    };
    if (sig(d) !== sig(next)) { send({ bz: "reload" }); return; }
    if (d.title !== next.title) d.title = next.title;
    var added = [];
    var bridge = me.parentNode === d.body ? me : null;
    if (bridge) bridge.remove();
    morphChildren(d.body, next.body, d, added);
    copyAttrs(d.body, next.body);
    if (bridge) d.body.append(bridge);
    var figs = [];
    added.forEach(function (n) {
      if (n.matches && n.matches(".fig")) figs.push(n);
      else if (n.querySelectorAll) figs.push.apply(figs, n.querySelectorAll(".fig"));
    });
    if (figs.length) {
      var T = window.Bazinga;
      if (T && T.figures && T.figures.init) T.figures.init(d);
      else send({ bz: "reload" });
    }
    reportSize();
  }

  function sameFigure(a, b) {
    return a.nodeType === 1 && b.nodeType === 1 && a.classList.contains("fig") && b.classList.contains("fig")
      && a.getAttribute("data-figure") === b.getAttribute("data-figure")
      && a.getAttribute("data-controls") === b.getAttribute("data-controls")
      && a.getAttribute("data-start") === b.getAttribute("data-start");
  }

  function copyAttrs(a, b) {
    Array.prototype.slice.call(a.attributes).forEach(function (at) { if (!b.hasAttribute(at.name)) a.removeAttribute(at.name); });
    Array.prototype.slice.call(b.attributes).forEach(function (at) {
      if (a.getAttribute(at.name) !== at.value) a.setAttribute(at.name, at.value);
    });
  }

  function morphNode(a, b, docA, added) {
    var n;
    if (a.nodeType !== b.nodeType || a.nodeName !== b.nodeName) {
      n = docA.importNode(b, true); a.replaceWith(n); added.push(n); return;
    }
    if (a.nodeType === 3 || a.nodeType === 8) { if (a.nodeValue !== b.nodeValue) a.nodeValue = b.nodeValue; return; }
    if (a.nodeType !== 1) return;
    if (a.classList.contains("fig")) {
      if (sameFigure(a, b)) return;          // keep the live figure as it is
      n = docA.importNode(b, true); a.replaceWith(n); added.push(n); return;
    }
    if (a.nodeName === "SCRIPT" || (a.namespaceURI === "http://www.w3.org/1998/Math/MathML" && a.nodeName.toLowerCase() === "math")) {
      if (!a.isEqualNode(b)) { n = docA.importNode(b, true); a.replaceWith(n); }
      return;
    }
    if (a.isEqualNode(b)) return;
    copyAttrs(a, b);
    morphChildren(a, b, docA, added);
  }

  function morphChildren(a, b, docA, added) {
    var ac = Array.prototype.slice.call(a.childNodes), bc = Array.prototype.slice.call(b.childNodes);
    var start = 0;
    while (start < ac.length && start < bc.length && ac[start].isEqualNode(bc[start])) start++;
    var endA = ac.length - 1, endB = bc.length - 1;
    while (endA >= start && endB >= start && (ac[endA].isEqualNode(bc[endB]) || sameFigure(ac[endA], bc[endB]))) { endA--; endB--; }
    var midA = ac.slice(start, endA + 1), midB = bc.slice(start, endB + 1);
    var n = Math.min(midA.length, midB.length), i;
    for (i = 0; i < n; i++) morphNode(midA[i], midB[i], docA, added);
    var ref = endA + 1 < ac.length ? ac[endA + 1] : null;
    for (i = n; i < midB.length; i++) {
      var node = docA.importNode(midB[i], true);
      a.insertBefore(node, ref);
      added.push(node);
    }
    for (i = n; i < midA.length; i++) midA[i].remove();
  }

  // --- scroll sync: the Editor's position -> this page's position, through matching headings, figures, equations --
  function anchors() {
    var body = document.querySelector(".post-body") || document.body;
    var pick = function (sel) {
      return Array.prototype.filter.call(body.querySelectorAll(sel), function (el) { return !el.closest("nav, aside, .toc"); });
    };
    var top = function (el) { return el.getBoundingClientRect().top + window.scrollY; };
    return {
      h: pick("h1, h2, h3, h4, h5, h6").map(top),
      fig: pick(".fig, figure.drawing, .drawing").map(top),
      math: pick(".math-display").map(top),
      start: top(body),
      height: document.documentElement.scrollHeight,
    };
  }

  function syncTo(editorY, editorAnchors, editorHeight, bodyTop) {
    var a = anchors();
    var used = { h: 0, fig: 0, math: 0 };
    var pairs = [[0, 0], [Math.max(1, bodyTop), Math.max(0, a.start - 24)]];
    editorAnchors.forEach(function (e) {
      var list = a[e.kind];
      if (!list) return;
      var i = used[e.kind]++;
      if (i < list.length) {
        var p = list[i] - 80, last = pairs[pairs.length - 1];
        if (p >= last[1] && e.y >= last[0]) pairs.push([e.y, p]);
      }
    });
    var view = window.innerHeight, lastP = pairs[pairs.length - 1];
    pairs.push([Math.max(editorHeight, lastP[0] + 1), Math.max(a.height - view, lastP[1])]);
    var y = 0;
    for (var i = 1; i < pairs.length; i++) {
      var e0 = pairs[i - 1][0], p0 = pairs[i - 1][1], e1 = pairs[i][0], p1 = pairs[i][1];
      if (editorY <= e1 || i === pairs.length - 1) {
        var f = e1 > e0 ? Math.min(1, Math.max(0, (editorY - e0) / (e1 - e0))) : 0;
        y = p0 + f * (p1 - p0);
        break;
      }
    }
    window.scrollTo({ top: y, behavior: "auto" });
  }
})();
