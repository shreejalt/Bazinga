// Small helpers shared by every Studio screen: the API, DOM building, icons, dialogs, toasts, dates.

export const store = { state: null };

// --- API ---------------------------------------------------------------------------------------------------------
export class ApiError extends Error {
  constructor(status, message) { super(message); this.status = status; }
}

export async function api(path, body) {
  const opts = body === undefined
    ? { method: "GET", credentials: "same-origin" }
    : { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body) };
  let res;
  try { res = await fetch(path, opts); }
  catch (e) { throw new ApiError(0, "The Studio is not running. Start it again from the terminal."); }
  let data = null;
  try { data = await res.json(); } catch (e) { data = null; }
  if (!res.ok) throw new ApiError(res.status, (data && data.error) || `Request failed (${res.status})`);
  return data;
}

// POST that answers with server-sent events; calls onEvent(name, data) for each.
export async function stream(path, body, onEvent) {
  const res = await fetch(path, {
    method: "POST", credentials: "same-origin",
    headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  if (!res.ok || !res.body) {
    let msg = `Request failed (${res.status})`;
    try { msg = (await res.json()).error || msg; } catch (e) { /* not JSON */ }
    throw new ApiError(res.status, msg);
  }
  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let i;
    while ((i = buf.indexOf("\n\n")) >= 0) {
      const chunk = buf.slice(0, i);
      buf = buf.slice(i + 2);
      let name = "message", data = "";
      for (const line of chunk.split("\n")) {
        if (line.startsWith("event: ")) name = line.slice(7);
        else if (line.startsWith("data: ")) data += line.slice(6);
      }
      try { onEvent(name, JSON.parse(data)); } catch (e) { onEvent(name, data); }
    }
  }
}

// --- DOM ---------------------------------------------------------------------------------------------------------
// h("div.card#x", {onclick, title}, child, ...) -- children may be strings, nodes, arrays, null.
export function h(spec, attrs, ...children) {
  if (attrs === null || typeof attrs !== "object" || attrs instanceof Node || Array.isArray(attrs)) {
    children.unshift(attrs);
    attrs = {};
  }
  const m = spec.match(/^([a-z0-9-]*)((?:[.#][\w-]+)*)$/i);
  const el = document.createElement((m && m[1]) || "div");
  if (m && m[2]) {
    for (const part of m[2].match(/[.#][\w-]+/g)) {
      if (part[0] === ".") el.classList.add(part.slice(1)); else el.id = part.slice(1);
    }
  }
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === undefined || v === null || v === false) continue;
    if (k.startsWith("on") && typeof v === "function") el.addEventListener(k.slice(2), v);
    else if (k === "class") el.className += (el.className ? " " : "") + v;
    else if (k === "style" && typeof v === "object") Object.assign(el.style, v);
    else if (k === "html") el.innerHTML = v;
    else if (k in el && typeof v !== "string") el[k] = v;
    else el.setAttribute(k, v === true ? "" : v);
  }
  append(el, children);
  return el;
}

function append(el, children) {
  for (const c of children) {
    if (c === null || c === undefined || c === false) continue;
    if (Array.isArray(c)) append(el, c);
    else el.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
}

export function clear(el) { while (el.firstChild) el.firstChild.remove(); return el; }

// Empty el, then add the given children (null/false/undefined are skipped, arrays flattened).
export function fill(el, ...children) { clear(el); append(el, children); return el; }

// Add children to el, skipping null/false/undefined (Element.append would print "null").
export function put(el, ...children) { append(el, children); return el; }

// --- icons (inline SVG, stroke 1.6, follow currentColor) ----------------------------------------------------------
const P = {
  back: "M15 18l-6-6 6-6",
  plus: "M12 5v14M5 12h14",
  search: "M11 19a8 8 0 1 1 0-16 8 8 0 0 1 0 16zM21 21l-4.3-4.3",
  heading: "M6 4v16M18 4v16M6 12h12",
  sigma: "M18 5H6l6 7-6 7h12",
  dollar: "M8 7c0-1.7 1.8-3 4-3s4 1.3 4 3-1.8 2.5-4 3-4 1.3-4 3 1.8 3 4 3 4-1.3 4-3M12 2v20",
  figure: "M4 19h16M6 16l4-5 3 3 5-7",
  drawing: "M4 5h6v5H4zM14 14h6v5h-6zM10 7.5h4.5v6.5",
  quote: "M7 7h4v4c0 3-2 5-4 6M15 7h4v4c0 3-2 5-4 6",
  link: "M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1",
  callout: "M4 5h16v11H8l-4 4zM12 8v3M12 13.5v.01",
  table: "M4 5h16v14H4zM4 10h16M4 15h16M10 5v14",
  image: "M4 5h16v14H4zM4 16l5-5 4 4 2-2 5 5M15 9.5a1 1 0 1 0 0-.01",
  code: "M9 8l-4 4 4 4M15 8l4 4-4 4",
  footnote: "M5 7h9M5 12h9M5 17h5M18 5v6M16 7l2-2",
  divider: "M4 12h16M8 7h8M8 17h8",
  check: "M5 12.5l4.5 4.5L19 7",
  x: "M6 6l12 12M18 6L6 18",
  dot: "M12 12h.01",
  eye: "M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12zM12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z",
  sliders: "M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12M20 18h0M14 4v4M8 10v4M16 16v4",
  history: "M3 12a9 9 0 1 0 3-6.7M3 4v4h4M12 7v5l3 2",
  alert: "M12 4l9 16H3zM12 10v4M12 17v.01",
  info: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 11v5M12 8v.01",
  sun: "M12 17a5 5 0 1 0 0-10 5 5 0 0 0 0 10zM12 1v2M12 21v2M4.2 4.2l1.4 1.4M18.4 18.4l1.4 1.4M1 12h2M21 12h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4",
  moon: "M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z",
  external: "M14 4h6v6M20 4l-9 9M18 14v5H5V6h5",
  phone: "M8 3h8a1 1 0 0 1 1 1v16a1 1 0 0 1-1 1H8a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1zM11 18h2",
  desktop: "M3 5h18v11H3zM8 20h8M12 16v4",
  send: "M4 12l16-8-6 16-3-7z",
  clock: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 7v5l3 2",
  undo: "M9 14L4 9l5-5M4 9h11a5 5 0 0 1 0 10h-3",
  wand: "M15 4V2M15 10V8M11 6h2M17 6h2M4 20l10-10M13 11l-2-2",
  more: "M5 12h.01M12 12h.01M19 12h.01",
  upload: "M12 16V4M7 9l5-5 5 5M4 20h16",
  trash: "M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3",
  pen: "M4 20h4L19 9l-4-4L4 16zM14 6l4 4",
  doc: "M7 3h7l5 5v13H7zM14 3v5h5",
  play: "M8 5v14l11-7z",
};

export function icon(name, size = 18) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("width", size);
  svg.setAttribute("height", size);
  svg.setAttribute("fill", "none");
  svg.setAttribute("stroke", "currentColor");
  svg.setAttribute("stroke-width", "1.7");
  svg.setAttribute("stroke-linecap", "round");
  svg.setAttribute("stroke-linejoin", "round");
  svg.setAttribute("aria-hidden", "true");
  svg.classList.add("icon");
  const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
  path.setAttribute("d", P[name] || P.dot);
  svg.append(path);
  return svg;
}

// --- toasts ------------------------------------------------------------------------------------------------------
export function toast(message, kind = "info", ms = 3200) {
  const box = document.getElementById("toasts");
  const t = h("div.toast", { class: `toast-${kind}` }, icon(kind === "error" ? "alert" : kind === "ok" ? "check" : "info", 16),
    h("span", message));
  box.append(t);
  requestAnimationFrame(() => t.classList.add("in"));
  setTimeout(() => { t.classList.remove("in"); setTimeout(() => t.remove(), 300); }, ms);
}

// --- dialogs and drawers -----------------------------------------------------------------------------------------
let openLayers = [];

export function modal({ title, subtitle, body, footer, wide = false, onClose, className = "" }) {
  const close = () => {
    if (!layer.isConnected) return;
    layer.classList.remove("in");
    openLayers = openLayers.filter((l) => l !== api_);
    setTimeout(() => layer.remove(), 180);
    document.removeEventListener("keydown", onKey, true);
    if (onClose) onClose();
    if (prevFocus && prevFocus.focus) prevFocus.focus();
  };
  const onKey = (e) => {
    if (e.key === "Escape" && openLayers[openLayers.length - 1] === api_) { e.preventDefault(); e.stopPropagation(); close(); }
  };
  const prevFocus = document.activeElement;
  const card = h("div.modal", { role: "dialog", "aria-modal": "true", "aria-label": title, class: (wide ? "wide " : "") + className },
    h("header.modal-head",
      h("div", h("h2", title), subtitle ? h("p.sub", subtitle) : null),
      h("button.icon-btn", { title: "Close (Esc)", "aria-label": "Close", onclick: () => close() }, icon("x"))),
    h("div.modal-body", body),
    footer ? h("footer.modal-foot", footer) : null);
  const layer = h("div.layer", { onmousedown: (e) => { if (e.target === layer) close(); } }, card);
  document.body.append(layer);
  document.addEventListener("keydown", onKey, true);
  requestAnimationFrame(() => layer.classList.add("in"));
  const api_ = { close, card, layer, body: card.querySelector(".modal-body"), foot: card.querySelector(".modal-foot") };
  openLayers.push(api_);
  const focusFirst = () => {
    if (card.contains(document.activeElement)) return;
    const f = card.querySelector("[autofocus]") || card.querySelector("input, textarea, select, button.primary");
    if (f) f.focus();
  };
  focusFirst();              // at once, so keys typed right after opening land in the dialog
  setTimeout(focusFirst, 30); // and again once content added after opening is there
  return api_;
}

export function anyLayerOpen() { return openLayers.length > 0; }

// --- formatting ----------------------------------------------------------------------------------------------------
export function ago(seconds) {
  const s = Math.max(0, Date.now() / 1000 - seconds);
  if (s < 45) return "just now";
  if (s < 90) return "a minute ago";
  if (s < 3600) return `${Math.round(s / 60)} minutes ago`;
  if (s < 5400) return "an hour ago";
  if (s < 86400) return `${Math.round(s / 3600)} hours ago`;
  if (s < 172800) return "yesterday";
  if (s < 86400 * 30) return `${Math.round(s / 86400)} days ago`;
  return new Date(seconds * 1000).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

export function niceDate(iso) {
  if (!iso) return "";
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

export function plural(n, one, many) { return `${n.toLocaleString()} ${n === 1 ? one : (many || one + "s")}`; }

export function today() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export function pill(state) {
  const label = { draft: "Draft", scheduled: "Scheduled", published: "Published" }[state] || state;
  return h("span.pill", { class: `pill-${state}` }, h("i"), label);
}

export function debounce(fn, ms) {
  let t = null;
  const d = (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
  d.flush = (...args) => { clearTimeout(t); return fn(...args); };
  d.cancel = () => clearTimeout(t);
  return d;
}

export function isMac() { return /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent); }
export function modKey() { return isMac() ? "⌘" : "Ctrl"; }

export function readFileAsDataURL(file) {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(r.result);
    r.onerror = () => reject(r.error);
    r.readAsDataURL(file);
  });
}

export const UPLOAD_MB = 8;
export const IMAGE_ACCEPT = "image/png,image/jpeg,image/gif,image/webp,image/avif";

export async function uploadImage(file, slug) {
  if (file.size > UPLOAD_MB * 1024 * 1024) throw new ApiError(413, `Images can be at most ${UPLOAD_MB} MB.`);
  const data = await readFileAsDataURL(file);
  return api("/api/upload", { name: file.name, data, slug });
}

export function pickFile(accept) {
  return new Promise((resolve) => {
    const input = h("input", { type: "file", accept, style: { display: "none" } });
    input.addEventListener("change", () => { resolve(input.files[0] || null); input.remove(); });
    document.body.append(input);
    input.click();
  });
}

export function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
