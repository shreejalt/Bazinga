// Records one browser clip: node lib/run.mjs clips/<name>.mjs <raw-dir>
//
// The clip file exports `meta` (caption, speed, trim, gif, poster) and a default async function (page, h).
// This runner opens Chrome at a fixed 1280x800 viewport (at 2x), films the page with Chrome's screencast, and gives
// the clip a few helpers (h.*) that move a visible cursor dot with the real mouse, so viewers can follow along.
// It writes <raw-dir>/<name>-frames/ (the filmed frames and their times) and <raw-dir>/<name>.json (meta, where the
// action starts and which stretches to cut).
// BASE_URL (the example site, e.g. http://127.0.0.1:8020) comes from make.py.
import { chromium } from "playwright";
import { mkdirSync, rmSync, writeFileSync } from "node:fs";
import { basename, resolve } from "node:path";
import { pathToFileURL } from "node:url";

const [clipPath, rawDir] = process.argv.slice(2);
if (!clipPath || !rawDir) {
  console.error("usage: node lib/run.mjs clips/<name>.mjs <raw-dir>");
  process.exit(2);
}
const name = basename(clipPath).replace(/\.mjs$/, "");
const BASE = (process.env.BASE_URL || "http://127.0.0.1:8020").replace(/\/$/, "");
const SIZE = { width: 1280, height: 800 };   // the size of every clip, in CSS pixels
const mod = await import(pathToFileURL(resolve(clipPath)).href);
const meta = { speed: 1, trim: [0, 0], gif: false, ...(mod.meta || {}) };
const viewport = meta.viewport || SIZE;

// The overlay drawn above the page while recording (never takes clicks):
// - a standard mouse-pointer arrow (black, white outline) whose tip sits exactly at the pointer;
// - a ripple (an expanding ring) on every click, and a slight press-scale while the button is down;
// - a highlight box around the control about to be used;
// - a step caption: a small sapphire pill at the bottom ("1 · Drag the slider").
// It lives in the top page only. Fixed positioning puts it above iframes (the Editor's preview) too.
const OVERLAY = `
(() => {
  if (window.top !== window) return;
  const CSS = "#__clip_cursor{position:fixed;left:0;top:0;width:28px;height:28px;z-index:2147483647;pointer-events:none;" +
    "transform-origin:2px 2px;transition:transform .12s ease-out;filter:drop-shadow(0 1px 2px rgba(0,0,0,.35))}" +
    "#__clip_cursor.down{transform:scale(.86)}" +
    "#__clip_ring{position:fixed;width:34px;height:34px;margin:-17px 0 0 -17px;border-radius:50%;" +
    "border:3px solid #0F52BA;z-index:2147483646;pointer-events:none;opacity:0}" +
    "#__clip_ring.go{animation:__clip_ripple .55s ease-out}" +
    "@keyframes __clip_ripple{0%{opacity:.9;transform:scale(.3)}100%{opacity:0;transform:scale(1.9)}}" +
    "#__clip_box{position:fixed;border:2.5px solid #F2B632;border-radius:8px;z-index:2147483645;pointer-events:none;" +
    "opacity:0;transition:opacity .25s;box-shadow:0 0 0 4px rgba(242,182,50,.22)}" +
    "#__clip_box.on{opacity:1}" +
    "#__clip_step{position:fixed;left:50%;bottom:22px;transform:translate(-50%,8px);z-index:2147483646;" +
    "pointer-events:none;background:#0F52BA;color:#FBF7EC;font:700 17px/1.2 'Courier Prime','Courier New',monospace;" +
    "letter-spacing:.01em;padding:9px 18px 10px;border-radius:999px;box-shadow:0 4px 14px rgba(15,82,186,.35);" +
    "opacity:0;transition:opacity .25s,transform .25s;white-space:nowrap}" +
    "#__clip_step.on{opacity:1;transform:translate(-50%,0)}";
  const ARROW = '<svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 28 28">' +
    '<path d="M2 2 L2 23 L7.4 17.8 L11.2 26.2 L14.6 24.7 L10.9 16.5 L18.4 16.5 Z" fill="#111" stroke="#fff" ' +
    'stroke-width="2" stroke-linejoin="round"/></svg>';
  const make = () => {
    if (document.getElementById("__clip_cursor") || !document.body) return;
    const s = document.createElement("style"); s.textContent = CSS; document.head.appendChild(s);
    const c = document.createElement("div"); c.id = "__clip_cursor"; c.innerHTML = ARROW;
    const r = document.createElement("div"); r.id = "__clip_ring";
    const b = document.createElement("div"); b.id = "__clip_box";
    const t = document.createElement("div"); t.id = "__clip_step";
    document.body.append(b, r, c, t);
    const at = window.__clip_at || [-60, -60];
    c.style.left = (at[0] - 2) + "px"; c.style.top = (at[1] - 2) + "px";
  };
  window.__clip_set = (x, y, state) => {
    make();
    window.__clip_at = [x, y];
    const c = document.getElementById("__clip_cursor"), r = document.getElementById("__clip_ring");
    if (!c) return;
    c.style.left = (x - 2) + "px"; c.style.top = (y - 2) + "px";       // the arrow's tip is at (2, 2)
    r.style.left = x + "px"; r.style.top = y + "px";
    if (state === "down") c.classList.add("down");
    if (state === "up") c.classList.remove("down");
    if (state === "pulse") { r.classList.remove("go"); void r.offsetWidth; r.classList.add("go"); }
  };
  window.__clip_box = (rect) => {
    make();
    const b = document.getElementById("__clip_box");
    if (!b) return;
    if (!rect) { b.classList.remove("on"); return; }
    const pad = 6;
    Object.assign(b.style, { left: rect.x - pad + "px", top: rect.y - pad + "px",
      width: rect.width + 2 * pad + "px", height: rect.height + 2 * pad + "px" });
    b.classList.add("on");
  };
  window.__clip_step = (text) => {
    make();
    const t = document.getElementById("__clip_step");
    if (!t) return;
    if (!text) { t.classList.remove("on"); return; }
    t.textContent = text; t.classList.add("on");
  };
  window.__clip_restore = () => {
    if (window.__clip_text) window.__clip_step(window.__clip_text);
  };
  document.addEventListener("DOMContentLoaded", () => { make(); window.__clip_restore(); });
})();`;

// Filming: Chrome's own screencast (through Playwright's CDP session) sends a sharp JPEG of the page each time it
// changes, at the device's resolution. At deviceScaleFactor 2 that is 2560x1600; make.py turns the frames and their
// times into a 25 fps video and scales it down to 1280 px with lanczos, which keeps text crisp. (Playwright's
// recordVideo films at CSS-pixel size only, which looks soft at 2x screens.)
const SCALE = Number(process.env.CLIP_SCALE || meta.scale || 2);
const browser = await chromium.launch({ channel: process.env.CLIP_CHANNEL || "chrome" });
const context = await browser.newContext({ viewport, deviceScaleFactor: SCALE, colorScheme: meta.colorScheme || "light" });
await context.addInitScript(OVERLAY);
const frameDir = resolve(rawDir, name + "-frames");
rmSync(frameDir, { recursive: true, force: true });
mkdirSync(frameDir, { recursive: true });
const frames = [];
const t0 = Date.now();
const now = () => (Date.now() - t0) / 1000;
let startAt = null;
const skips = [];               // [from, to] seconds cut from the clip (page loads, waiting)
let stepNo = 0;
const page = await context.newPage();
const cdp = await context.newCDPSession(page);
cdp.on("Page.screencastFrame", ({ data, metadata, sessionId }) => {
  const file = String(frames.length).padStart(5, "0") + ".jpg";
  writeFileSync(resolve(frameDir, file), Buffer.from(data, "base64"));
  frames.push([file, metadata.timestamp ? metadata.timestamp - t0 / 1000 : now()]);
  cdp.send("Page.screencastFrameAck", { sessionId }).catch(() => {});
});
await cdp.send("Page.startScreencast", {
  format: "jpeg", quality: 92, maxWidth: viewport.width * SCALE, maxHeight: viewport.height * SCALE, everyNthFrame: 1,
});
let pos = [viewport.width * 0.62, viewport.height * 0.55];
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const call = (fn, ...args) => page.evaluate(([f, a]) => window[f] && window[f](...a), [fn, args]).catch(() => {});
const setCursor = (state) => call("__clip_set", pos[0], pos[1], state);
const ease = (t) => (t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2);

function locate(target) {
  return typeof target === "string" ? page.locator(target).first() : target;
}
async function box(target) {
  const loc = locate(target);
  await loc.waitFor({ state: "visible", timeout: 20000 });
  await loc.scrollIntoViewIfNeeded().catch(() => {});
  const b = await loc.boundingBox();
  if (!b) throw new Error(`clip ${name}: nothing visible for ${target}`);
  return b;
}

/** Wait until the page is ready to be filmed: loaded, fonts in, figures drawn, nothing still "Loading". */
async function settle(extra = 300) {
  await page.waitForLoadState("load").catch(() => {});
  await page.evaluate(() => document.fonts && document.fonts.ready).catch(() => {});
  for (let i = 0; i < 60; i++) {
    const ok = await page.evaluate(() => [...document.querySelectorAll("figure[data-figure]")]
      .every((f) => f.querySelector("svg"))).catch(() => true);
    if (ok) break;
    await sleep(250);
  }
  await sleep(extra);
  await setCursor();
  await call("__clip_restore");
}

const h = {
  page, base: BASE, viewport,
  url: (path = "/") => BASE + path,
  /** Open a page of the example site and wait until it is fully drawn (the wait is cut from the clip). */
  async goto(path = "/", wait = 500) {
    await h.offCamera(async () => {
      await page.goto(BASE + path, { waitUntil: "load" });
      await settle(wait);
    });
  },
  /** Run something whose frames should not be in the clip (a navigation, a slow load). */
  async offCamera(fn) {
    const a = now();
    await fn();
    if (startAt !== null) skips.push([a, now()]);
  },
  /** Everything before this call is cut from the clip (loading, setup). */
  start() { startAt = now(); },
  /** Wait for a page load that a click started, off camera. */
  async loaded(selector, wait = 400) {
    await h.offCamera(async () => {
      if (selector) await page.waitForSelector(selector, { timeout: 30000 });
      await settle(wait);
    });
  },
  pause: sleep,
  /** Wait until fn() (run in the page) is true. Unlike waitForFunction this works under the Editor's strict CSP. */
  async until(fn, arg, timeout = 30000) {
    const end = Date.now() + timeout;
    while (Date.now() < end) {
      if (await page.evaluate(fn, arg).catch(() => false)) return true;
      await sleep(150);
    }
    throw new Error(`clip ${name}: timed out waiting for ${fn}`);
  },
  /** Show a step caption at the bottom ("2 · Pick a preset"); null hides it. */
  async step(text) {
    if (!text) { await page.evaluate(() => { window.__clip_text = null; }).catch(() => {}); await call("__clip_step", null); return; }
    stepNo += 1;
    const label = `${stepNo} · ${text}`;
    await page.evaluate((t) => { window.__clip_text = t; }, label).catch(() => {});
    await call("__clip_step", label);
    await sleep(350);
  },
  /** Draw a highlight box around a control for a moment, before it is used. */
  async highlight(target, ms = 650) {
    const b = await box(target);
    await call("__clip_box", { x: b.x, y: b.y, width: b.width, height: b.height });
    await sleep(ms);
  },
  async unhighlight() { await call("__clip_box", null); },
  /** Glide the mouse (and the arrow) to a point along an eased, slightly curved path. */
  async move(x, y, ms) {
    const [x0, y0] = pos;
    const dist = Math.hypot(x - x0, y - y0);
    ms = ms ?? Math.min(1100, 380 + dist * 0.9);
    const n = Math.max(8, Math.round(ms / 22));
    const bend = Math.min(60, dist * 0.12);     // a gentle arc, as a hand moves
    for (let i = 1; i <= n; i++) {
      const k = ease(i / n), arc = Math.sin(Math.PI * k) * bend;
      const nx = dist ? -(y - y0) / dist : 0, ny = dist ? (x - x0) / dist : 0;
      pos = [x0 + (x - x0) * k + nx * arc, y0 + (y - y0) * k + ny * arc];
      await page.mouse.move(pos[0], pos[1]);
      await setCursor();
      await sleep(ms / n);
    }
  },
  /** Glide to an element (a selector or a locator); fx, fy pick the point inside it (0..1). */
  async moveTo(target, { fx = 0.5, fy = 0.5, ms } = {}) {
    const b = await box(target);
    await h.move(b.x + b.width * fx, b.y + b.height * fy, ms);
    return b;
  },
  /** Glide to an element, show it for a moment, and click it with a ripple. */
  async click(target, opts = {}) {
    if (opts.highlight) await h.highlight(target);
    await h.moveTo(target, opts);
    await sleep(opts.before ?? 400);
    await h.unhighlight();
    await setCursor("down");
    await page.mouse.down();
    await sleep(90);
    await page.mouse.up();
    await setCursor("pulse");
    await setCursor("up");
    await sleep(opts.after ?? 350);
  },
  /** Type at a human speed into whatever has focus. */
  async type(text, delay = 55) {
    for (const ch of text) {
      if (ch === "\n") await page.keyboard.press("Enter");
      else await page.keyboard.type(ch);
      await sleep(delay + (Math.random() * delay) / 2);
    }
  },
  async press(key) { await page.keyboard.press(key); await sleep(120); },
  /** Press at a point inside an element, drag by (dx, dy) pixels in ms, and let go. */
  async drag(target, dx, dy = 0, ms = 1400, { fx = 0.5, fy = 0.5 } = {}) {
    const b = await h.moveTo(target, { fx, fy });
    await sleep(300);
    const [x0, y0] = [b.x + b.width * fx, b.y + b.height * fy];
    await h.dragFrom(x0, y0, dx, dy, ms);
  },
  /** Press at (x0, y0), drag by (dx, dy), let go. */
  async dragFrom(x0, y0, dx, dy, ms = 1400) {
    if (Math.hypot(pos[0] - x0, pos[1] - y0) > 2) { await h.move(x0, y0); await sleep(300); }
    await setCursor("down");
    await page.mouse.down();
    const n = Math.max(10, Math.round(ms / 25));
    for (let i = 1; i <= n; i++) {
      const k = ease(i / n);
      pos = [x0 + dx * k, y0 + dy * k];
      await page.mouse.move(pos[0], pos[1]);
      await setCursor();
      await sleep(ms / n);
    }
    await page.mouse.up();
    await setCursor("up");
  },
  /** Drag a range input's thumb from its current value to `to`. */
  async slide(target, to, ms = 1500) {
    const loc = locate(target);
    const b = await box(loc);
    const [min, max, val] = await loc.evaluate((el) => [+el.min, +el.max, +el.value]);
    const thumb = 16, track = b.width - thumb;
    const xAt = (v) => b.x + thumb / 2 + (track * (v - min)) / (max - min);
    const y = b.y + b.height / 2;
    await h.move(xAt(val), y);
    await sleep(350);
    await h.dragFrom(xAt(val), y, xAt(to) - xAt(val), 0, ms);
  },
  /** Scroll the page smoothly by dy pixels (with the mouse wheel, where the arrow is). */
  async scroll(dy, ms = 900) {
    const n = Math.max(8, Math.round(ms / 30));
    for (let i = 0; i < n; i++) { await page.mouse.wheel(0, dy / n); await sleep(ms / n); }
    await sleep(150);
  },
};

let failed = null;
try {
  await mod.default(page, h);
  await h.step(null);
  await sleep(300);
} catch (err) {
  failed = err;
}
const end = now();
await cdp.send("Page.stopScreencast").catch(() => {});
await sleep(200);
await context.close();
await browser.close();
if (failed) {
  console.error(`clip ${name} failed: ${failed.stack || failed}`);
  process.exit(1);
}
mkdirSync(rawDir, { recursive: true });
writeFileSync(resolve(frameDir, "frames.json"), JSON.stringify(frames));
writeFileSync(resolve(rawDir, name + ".json"),
  JSON.stringify({ ...meta, name, startAt: startAt ?? 0, endAt: end, skips, scale: SCALE, frames: frames.length }, null, 2));
console.log(`recorded ${name}: ${(end - (startAt ?? 0)).toFixed(1)} s of action, ${skips.length} cut(s)`);
