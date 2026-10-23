// Interactive figures. Included on every page; it does nothing until a figure needs it.
//
// Each <figure class="fig" data-bazinga="{...}"> already shows its build-time SVG. When the reader
// touches a control (or the figure has been on screen for a moment while the page is idle), one
// shared module worker (pyworker.js) starts, and every change re-runs the figure's compute() and
// renderer there; the new SVG replaces the old one. Requests are coalesced: only the latest values
// are computed. If the worker cannot start, the static figure stays and a plain message says so.
//
// 3-D figures (bazinga/scene3d.py) draw a <g class="s3"> panel. Dragging its background turns the view (an
// "orbit" control, changed here); dragging a handle (<g class="s3-handle">) sends compute() a _drag
// {handle, name, inset, start, from, to} in picture units, and compute() may answer with a "state" of new
// control values, which the controls then show. Overlapping handles: a press takes the nearest one.
//
// Also exposes window.Bazinga.py.call(moduleUrl, fnName, args) -> Promise<JSON> for other scripts
// (Ask uses it). Inside args, {"$json": url} is fetched once and handed to the function as data.
(function () {
  "use strict";
  if (window.Bazinga && window.Bazinga.py && window.Bazinga.py.__figure) return;

  var DEFAULT_INDEX_URL = "https://cdn.jsdelivr.net/pyodide/v314.0.7/full/";
  var script = document.currentScript;
  var scriptSrc = (script && script.src) ||
    new URL("assets/js/figure.js", new URL(meta("bazinga-root") || "/", location.href)).href;

  function meta(name) {
    var m = document.querySelector('meta[name="' + name + '"]');
    return m ? m.getAttribute("content") : null;
  }
  var cfg = (window.BazingaConfig || {});
  var indexURL = cfg.pyodide || meta("bazinga-pyodide") || DEFAULT_INDEX_URL;
  var siteRoot = new URL(cfg.root || meta("bazinga-root") || new URL("../../", scriptSrc).href, location.href).href;
  var workerURL = new URL("pyworker.js", scriptSrc).href;

  // ------------------------------------------------------------------ worker

  var worker = null;
  var ready = null;       // Promise that resolves when the runtime is up
  var failed = null;      // error text once the worker has failed for good
  var seq = 0;
  var waiting = new Map();
  var stats = { bootMs: null, lastMs: null, requests: 0 };

  function startWorker() {
    if (ready) return ready;
    var t0 = performance.now();
    ready = new Promise(function (resolve, reject) {
      try {
        worker = new Worker(workerURL, { type: "module" });
      } catch (e) {
        reject(e);
        return;
      }
      worker.onmessage = function (ev) {
        var m = ev.data || {};
        var w = waiting.get(m.id);
        if (!w) return;
        waiting.delete(m.id);
        if (m.ok) w.resolve(m.result); else w.reject(new Error(m.error || "failed"));
      };
      worker.onerror = function (ev) {
        var err = new Error((ev && ev.message) || "worker failed");
        waiting.forEach(function (w) { w.reject(err); });
        waiting.clear();
        reject(err);
      };
      post({ type: "init", indexURL: indexURL }).then(function () {
        stats.bootMs = Math.round(performance.now() - t0);
        resolve();
      }, reject);
    });
    ready.catch(function (e) {
      failed = String((e && e.message) || e);
      // only figures the reader has touched say so; the others fail quietly when touched
      document.querySelectorAll(".fig[data-bazinga]").forEach(function (el) {
        if (el.__fig && el.__fig.touched) el.__fig.fail();
      });
    });
    return ready;
  }

  function post(msg) {
    return new Promise(function (resolve, reject) {
      var id = ++seq;
      waiting.set(id, { resolve: resolve, reject: reject });
      msg.id = id;
      msg.indexURL = indexURL;
      worker.postMessage(msg);
    });
  }

  function call(moduleUrl, fn, args, opts) {
    opts = opts || {};
    return startWorker().then(function () {
      return post({
        type: "call",
        module: new URL(moduleUrl, location.href).href,
        fn: fn,
        args: args == null ? {} : args,
        requires: opts.requires || []
      });
    });
  }

  // ------------------------------------------------------------------ figures

  var narrowMQ = window.matchMedia("(max-width: 600px)");
  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  var instances = 0;

  function clone(v) { return Array.isArray(v) ? v.slice() : v; }
  function same(a, b) {
    if (Array.isArray(a) || Array.isArray(b)) {
      return Array.isArray(a) && Array.isArray(b) && a.length === b.length &&
        a.every(function (x, i) { return Math.abs(x - b[i]) < 1e-9; });
    }
    return Math.abs(a - b) < 1e-9;
  }
  function vecText(v) {
    var f = function (x) { return String(Math.round(x * 100) / 100).replace("-", "\u2212"); };
    return Array.isArray(v) ? "(" + v.map(f).join(", ") + ")" : f(v);
  }

  function decimals(step) {
    var s = String(step);
    if (s.indexOf("e-") >= 0) return parseInt(s.split("e-")[1], 10);
    var i = s.indexOf(".");
    return i < 0 ? 0 : s.length - i - 1;
  }

  function Figure(el) {
    this.el = el;
    this.data = JSON.parse(el.getAttribute("data-bazinga"));
    this.values = Object.assign({}, this.data.values);
    this.shown = Object.assign({}, this.data.values);
    this.inflight = false;
    this.dirty = false;
    this.playing = null;
    this.status = el.querySelector(".fig-status");
    this.stage = el.querySelector(".fig-stage");
    this.out = el.querySelector(".fig-out");
    this.byName = {};
    var self = this;
    var n = ++instances;
    this.data.controls.forEach(function (c) { self.byName[c.name] = c; });

    // radio groups must be unique when a figure appears twice on a page
    el.querySelectorAll('input[type="radio"]').forEach(function (r) {
      r.name = r.name + "-" + n;
    });
    var fs = el.querySelector(".fig-fs");
    if (fs) fs.disabled = false;

    el.querySelectorAll(".fig-ctl").forEach(function (box) {
      var name = box.getAttribute("data-name");
      var c = self.byName[name];
      if (!c) return;
      if (c.kind === "slider") {
        var input = box.querySelector('input[type="range"]');
        self.paintSlider(input);
        input.addEventListener("input", function () {
          if (self.playing && self.playing.name === name) self.stopPlay();
          self.set(name, parseFloat(input.value));
        });
      } else {
        box.querySelectorAll('input[type="radio"]').forEach(function (r) {
          r.addEventListener("change", function () {
            if (r.checked) self.set(name, parseInt(r.value, 10));
          });
        });
      }
    });
    el.querySelectorAll(".fig-preset").forEach(function (b) {
      b.addEventListener("click", function () {
        var p = self.data.presets[parseInt(b.getAttribute("data-preset"), 10)];
        self.stopPlay();
        self.apply(Object.assign({}, self.data.defaults, p.values));
      });
    });
    var reset = el.querySelector(".fig-reset");
    if (reset) reset.addEventListener("click", function () {
      self.stopPlay();
      self.apply(Object.assign({}, self.data.defaults));
    });
    el.querySelectorAll(".fig-play").forEach(function (b) {
      b.addEventListener("click", function () {
        var name = b.getAttribute("data-for");
        if (self.playing && self.playing.name === name) self.stopPlay();
        else self.startPlay(name, b);
      });
    });
    // start the worker as soon as the reader shows intent
    var warm = function () { startWorker(); };
    el.addEventListener("pointerenter", warm, { once: true });
    el.addEventListener("focusin", warm, { once: true });
    el.addEventListener("touchstart", warm, { once: true, passive: true });
    this.markPresets();
    this.wirePicture();
  }

  Figure.prototype.paintSlider = function (input) {
    var lo = parseFloat(input.min), hi = parseFloat(input.max), v = parseFloat(input.value);
    input.style.setProperty("--p", (hi > lo ? (100 * (v - lo) / (hi - lo)) : 0).toFixed(2) + "%");
  };

  Figure.prototype.formatValue = function (c, v) {
    if (c.kind === "pad" || c.kind === "orbit" || c.kind === "hidden") return vecText(v);
    if (c.kind !== "slider") return String(c.options[v]);
    var step = c.step || (c.max - c.min) / 100;
    var allInt = [c.min, c.max, step].every(function (x) { return Number.isInteger(x); });
    return allInt ? String(Math.round(v)) : Number(v).toFixed(decimals(step));
  };

  Figure.prototype.syncControl = function (name) {
    var c = this.byName[name], v = this.values[name];
    var box = this.el.querySelector('.fig-ctl[data-name="' + name + '"]');
    if (!box) return;
    if (c.kind === "pad") {
      var o = box.querySelector("output");
      if (o) o.textContent = this.formatValue(c, v);
      return;
    }
    if (c.kind === "slider") {
      var input = box.querySelector('input[type="range"]');
      if (parseFloat(input.value) !== v) input.value = v;
      this.paintSlider(input);
      var out = box.querySelector("output");
      if (out) out.textContent = this.formatValue(c, v);
    } else {
      box.querySelectorAll('input[type="radio"]').forEach(function (r) {
        r.checked = parseInt(r.value, 10) === v;
      });
    }
  };

  Figure.prototype.markPresets = function () {
    var self = this;
    this.el.querySelectorAll(".fig-preset").forEach(function (b) {
      var p = self.data.presets[parseInt(b.getAttribute("data-preset"), 10)];
      var target = Object.assign({}, self.data.defaults, p.values);
      var eq = Object.keys(target).every(function (k) { return same(target[k], self.values[k]); });
      b.setAttribute("aria-pressed", eq ? "true" : "false");
    });
  };

  Figure.prototype.set = function (name, v) {
    this.touched = true;
    this.values[name] = v;
    this.syncControl(name);
    this.markPresets();
    this.request();
  };

  Figure.prototype.apply = function (vals) {
    var self = this;
    this.touched = true;
    Object.keys(vals).forEach(function (k) {
      if (self.byName[k]) { self.values[k] = clone(vals[k]); self.syncControl(k); }
    });
    this.markPresets();
    this.request();
  };

  Figure.prototype.say = function (text, isError) {
    if (!this.status) return;
    this.status.textContent = text || "";
    this.status.classList.toggle("is-error", !!isError);
  };

  Figure.prototype.request = function () {
    if (failed) { this.fail(); return; }
    this.dirty = true;
    if (this.inflight) return;
    this.send();
  };

  Figure.prototype.send = function () {
    var self = this;
    this.dirty = false;
    this.inflight = true;
    var values = JSON.parse(JSON.stringify(this.values));
    var drag = this.pendingDrag || null;
    this.pendingDrag = null;
    var narrow = narrowMQ.matches ? 1 : 0;
    var booted = false;
    var loadingTimer = setTimeout(function () {
      if (!booted) { self.say("Loading…"); self.el.classList.add("is-busy"); }
    }, 150);
    startWorker().then(function () {
      booted = true;
      return post({
        type: "figure",
        name: self.data.name,
        module: new URL(self.data.module, siteRoot).href,
        plot: new URL(self.data.plot, siteRoot).href,
        kits: self.kitURLs(),
        requires: self.data.requires || [],
        values: values,
        narrow: narrow,
        drag: drag
      });
    }).then(function (res) {
      clearTimeout(loadingTimer);
      stats.lastMs = Math.round(res.ms * 10) / 10;
      stats.requests++;
      self.show(res, values, narrow);
      self.inflight = false;
      self.say("");
      self.el.classList.remove("is-busy");
      if (self.dirty) self.send();
      else if (self.playing) self.playing.tick();
    }, function (err) {
      clearTimeout(loadingTimer);
      self.inflight = false;
      self.el.classList.remove("is-busy");
      if (failed) { self.fail(); return; }
      // a single bad state: keep what is shown, say so plainly
      self.stopPlay();
      self.say("This setting could not be drawn.", true);
      if (window.console) console.warn("[figure " + self.data.name + "]", err && err.message);
      if (self.dirty) self.send();
    });
  };

  Figure.prototype.show = function (res, values, narrow) {
    var live = this.stage.querySelector(".fig-svg-live");
    if (!live) {
      live = document.createElement("div");
      live.className = "fig-svg fig-svg-live";
      this.stage.appendChild(live);
    }
    var focused = document.activeElement && document.activeElement.closest && document.activeElement.closest("g.s3-handle");
    var focusName = focused && this.stage.contains(focused) ? focused.getAttribute("data-name") : null;
    live.innerHTML = res.svg;
    this.el.classList.add("is-live");
    if (focusName) {
      var again = live.querySelector('g.s3-handle[data-name="' + CSS.escape(focusName) + '"]');
      if (again) again.focus({ preventScroll: true });
    }
    if (this.out) this.out.innerHTML = res.readouts_html || "";
    if (res.state && typeof res.state === "object") {
      // the values a drag changed: the controls follow them
      var self = this;
      Object.keys(res.state).forEach(function (k) {
        if (!self.byName[k]) return;
        self.values[k] = clone(res.state[k]);
        values[k] = clone(res.state[k]);
        self.syncControl(k);
      });
      this.markPresets();
    }
    this.el.classList.add("is-live");
    this.shown = values;
    this.shownNarrow = narrow;
    this.el.dispatchEvent(new CustomEvent("bazinga:figure", { detail: { values: values, ms: res.ms } }));
  };

  Figure.prototype.fail = function () {
    if (this.failedShown) return;
    this.failedShown = true;
    this.stopPlay();
    this.inflight = false;
    this.el.classList.remove("is-busy");
    // put the controls back to what the picture shows, and stop offering them
    var self = this;
    this.values = Object.assign({}, this.el.classList.contains("is-live") ? this.shown : this.data.values);
    Object.keys(this.values).forEach(function (k) { self.syncControl(k); });
    var fs = this.el.querySelector(".fig-fs");
    if (fs) fs.disabled = true;
    this.say("The interactive version could not start here; this is the figure at its default settings.", true);
  };

  Figure.prototype.kitURLs = function () {
    var out = {}, kits = this.data.kits || {};
    Object.keys(kits).forEach(function (k) { out[k] = new URL(kits[k], siteRoot).href; });
    return out;
  };

  // ------------------------------------------------------------------ 3-D pictures: orbit and handles

  // the SVG the reader sees now: the live one, else the phone or wide picture from the build
  Figure.prototype.visibleSvg = function () {
    if (this.el.classList.contains("is-live")) return this.stage.querySelector(".fig-svg-live svg");
    return this.stage.querySelector(narrowMQ.matches ? ".fig-svg-narrow svg" : ".fig-svg-wide svg");
  };

  // client coordinates -> the coordinates of an SVG element (the scene panel or one of its insets)
  function toLocal(node, x, y) {
    var m = node && node.getScreenCTM && node.getScreenCTM();
    if (!m) return null;
    var p = new DOMPoint(x, y).matrixTransform(m.inverse());
    return [Math.round(p.x * 10) / 10, Math.round(p.y * 10) / 10];
  }

  Figure.prototype.panelNode = function (index, inset) {
    var svg = this.visibleSvg();
    var g = svg && svg.querySelectorAll("g.s3")[index];
    if (!g) return null;
    if (inset) return g.querySelector('g.s3-inset[data-inset="' + CSS.escape(inset) + '"]') || g;
    return g;
  };

  Figure.prototype.wirePicture = function () {
    var self = this;
    this.orbit = (this.data.controls || []).filter(function (c) { return c.kind === "orbit"; })[0] || null;
    var drag = null;
    var stage = this.stage;
    if (this.el.querySelector("g.s3")) this.el.classList.add("fig-3d");
    if (this.orbit) this.el.classList.add("fig-orbits");

    function nearestHandle(svg, x, y) {
      var best = null, bd = 26 * 26;     // within 26 screen pixels: a finger's width
      svg.querySelectorAll("g.s3-handle .s3-grab").forEach(function (c) {
        var r = c.getBoundingClientRect();
        if (!r.width) return;
        var dx = r.left + r.width / 2 - x, dy = r.top + r.height / 2 - y, d = dx * dx + dy * dy;
        if (d < bd) { bd = d; best = c.closest("g.s3-handle"); }
      });
      return best;
    }

    stage.addEventListener("pointerdown", function (e) {
      if (e.button > 0) return;
      var g = e.target.closest && e.target.closest("g.s3");
      if (!g) return;
      var svg = g.ownerSVGElement;
      var index = Array.prototype.indexOf.call(svg.querySelectorAll("g.s3"), g);
      var h = nearestHandle(svg, e.clientX, e.clientY);
      if (h && self.byName[h.getAttribute("data-control")]) {
        var name = h.getAttribute("data-control"), inset = h.getAttribute("data-inset") || null;
        var from = toLocal(self.panelNode(index, inset), e.clientX, e.clientY);
        if (!from) return;
        self.stopPlay();
        drag = { kind: "handle", index: index, handle: h.getAttribute("data-name"), name: name, inset: inset,
                 start: clone(self.values[name]), from: from };
      } else if (self.orbit) {
        self.stopPlay();
        drag = { kind: "orbit", start: clone(self.values[self.orbit.name]), x: e.clientX, y: e.clientY,
                 w: Math.max(240, g.getBoundingClientRect().width) };
      } else {
        return;
      }
      startWorker();
      try { stage.setPointerCapture(e.pointerId); } catch (_) { /* fine */ }
      self.el.classList.add("is-dragging");
      if (e.pointerType !== "touch" || drag.kind === "handle") e.preventDefault();
    });

    stage.addEventListener("pointermove", function (e) {
      if (!drag) return;
      e.preventDefault();
      if (drag.kind === "orbit") {
        var k = 300 / drag.w;              // degrees per screen pixel: a full-width drag turns it most of the way round
        var c = self.orbit, lo = (c.el_range || [-89, 89])[0], hi = (c.el_range || [-89, 89])[1];
        var az = drag.start[0] - (e.clientX - drag.x) * k;
        az = ((az + 180) % 360 + 360) % 360 - 180;
        var el = Math.min(hi, Math.max(lo, drag.start[1] + (e.clientY - drag.y) * k * 0.6));
        self.set(c.name, [Math.round(az * 10) / 10, Math.round(el * 10) / 10]);
        return;
      }
      var to = toLocal(self.panelNode(drag.index, drag.inset), e.clientX, e.clientY);
      if (!to) return;
      self.sendDrag({ handle: drag.handle, name: drag.name, inset: drag.inset, start: drag.start, from: drag.from, to: to });
    });

    function end() {
      drag = null;
      self.el.classList.remove("is-dragging");
    }
    stage.addEventListener("pointerup", end);
    stage.addEventListener("pointercancel", end);
    stage.addEventListener("lostpointercapture", end);

    // keyboard: the picture itself takes focus and turns with the arrow keys (left/right turn it, up/down tilt it)
    if (this.orbit && this.el.querySelector("g.s3")) {
      stage.tabIndex = 0;
      stage.setAttribute("role", "group");
      stage.setAttribute("aria-label", "3-D picture. Left and right arrow keys turn it; up and down tilt it.");
      var said = document.createElement("span");     // its own live region: the figure's status line is rewritten
      said.className = "fig-said";
      said.setAttribute("role", "status");
      said.setAttribute("aria-live", "polite");
      said.style.cssText = "position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap";
      this.el.appendChild(said);
      stage.addEventListener("keydown", function (e) {
        if (e.target !== stage || e.altKey || e.ctrlKey || e.metaKey) return;
        var step = e.shiftKey ? 2 : 10;
        var d = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step / 2], ArrowDown: [0, step / 2] }[e.key];
        if (!d) return;
        e.preventDefault();
        self.stopPlay();
        startWorker();
        var c = self.orbit, lo = (c.el_range || [-89, 89])[0], hi = (c.el_range || [-89, 89])[1];
        var v = self.values[c.name] || [0, 0];
        var az = ((v[0] + d[0] + 180) % 360 + 360) % 360 - 180;
        var el = Math.min(hi, Math.max(lo, v[1] + d[1]));
        self.set(c.name, [Math.round(az * 10) / 10, Math.round(el * 10) / 10]);
        said.textContent = "Turned to " + Math.round(az) + "°, tilted " + Math.round(el) + "°.";
      });
    }

    // a focused handle moves with the arrow keys
    stage.addEventListener("keydown", function (e) {
      var h = e.target.closest && e.target.closest("g.s3-handle");
      if (!h) return;
      var d = { ArrowLeft: [-8, 0], ArrowRight: [8, 0], ArrowUp: [0, -8], ArrowDown: [0, 8] }[e.key];
      var name = h.getAttribute("data-control");
      if (!d || !self.byName[name]) return;
      e.preventDefault();
      var from = [parseFloat(h.getAttribute("data-lx")), parseFloat(h.getAttribute("data-ly"))];
      self.sendDrag({ handle: h.getAttribute("data-name"), name: name, inset: h.getAttribute("data-inset") || null,
                      start: clone(self.values[name]), from: from, to: [from[0] + d[0], from[1] + d[1]] });
    });
  };

  Figure.prototype.sendDrag = function (drag) {
    this.touched = true;
    this.pendingDrag = drag;
    this.request();
  };

  // ------------------------------------------------------------------ play

  Figure.prototype.startPlay = function (name, button) {
    var self = this;
    var c = this.byName[name];
    var step = c.step || (c.max - c.min) / 100;
    if (this.values[name] >= c.max - step / 2) this.values[name] = c.min;
    // about 4 seconds end to end at 60 frames per second, never finer than one step
    var inc = Math.max(step, Math.round(((c.max - c.min) / 240) / step) * step);
    var last = 0;
    // a full sweep takes about 4 seconds however coarse the steps are (slower if the reader prefers less motion)
    var nSteps = Math.max(1, Math.round((c.max - c.min) / inc));
    var minGap = Math.max(reduceMotion.matches ? 250 : 16, 4000 / nSteps);
    button.setAttribute("aria-pressed", "true");
    var t = button.querySelector(".fig-play-text");
    if (t) t.textContent = "Pause";
    this.playing = {
      name: name,
      button: button,
      raf: null,
      tick: function () {
        if (!self.playing || self.playing.raf) return;
        self.playing.raf = requestAnimationFrame(function (now) {
          if (!self.playing) return;
          self.playing.raf = null;
          if (now - last < minGap) { self.playing.tick(); return; }
          last = now;
          var v = Math.min(c.max, self.values[name] + inc);
          v = Number((Math.round((v - c.min) / step) * step + c.min).toFixed(decimals(step) + 1));
          self.set(name, v);
          if (v >= c.max - step / 2) self.stopPlay();
        });
      }
    };
    if (!this.inflight) this.playing.tick();
  };

  Figure.prototype.stopPlay = function () {
    if (!this.playing) return;
    if (this.playing.raf) cancelAnimationFrame(this.playing.raf);
    var b = this.playing.button;
    b.setAttribute("aria-pressed", "false");
    var t = b.querySelector(".fig-play-text");
    if (t) t.textContent = "Play";
    this.playing = null;
  };

  // ------------------------------------------------------------------ setup

  function init(root) {
    (root || document).querySelectorAll(".fig[data-bazinga]").forEach(function (el) {
      if (el.__fig) return;
      try {
        el.__fig = new Figure(el);
        if (io) io.observe(el);
      } catch (e) {
        if (window.console) console.warn("[figure]", e);
      }
    });
  }

  // When a figure has been near the screen and the page is idle, start the worker quietly,
  // so the first slider move is fast. Skipped when the reader asked to save data.
  var saveData = navigator.connection && navigator.connection.saveData;
  var io = (!saveData && "IntersectionObserver" in window) ? new IntersectionObserver(function (entries) {
    if (!entries.some(function (e) { return e.isIntersecting; })) return;
    io.disconnect();
    var go = function () { startWorker(); };
    if ("requestIdleCallback" in window) requestIdleCallback(go, { timeout: 4000 });
    else setTimeout(go, 1500);
  }, { rootMargin: "300px 0px" }) : null;

  narrowMQ.addEventListener && narrowMQ.addEventListener("change", function () {
    document.querySelectorAll(".fig.is-live").forEach(function (el) {
      if (el.__fig) el.__fig.request();
    });
  });

  window.Bazinga = window.Bazinga || {};
  window.Bazinga.py = { call: call, start: startWorker, stats: stats, __figure: true };
  window.Bazinga.figures = { init: init };

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", function () { init(); });
  else init();
})();
