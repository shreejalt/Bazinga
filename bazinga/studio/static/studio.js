// Studio entry: theme, state, routing between the Library and the Editor.
import { api, store, h, clear, toast, icon, fill } from "./lib.js";
import { renderLibrary } from "./library.js";

const app = document.getElementById("app");
let current = null;   // the active screen ({destroy()})

// --- theme ---------------------------------------------------------------------------------------------------------
const THEME_KEY = "bazinga-studio-theme";
function readTheme() { try { return localStorage.getItem(THEME_KEY) || "auto"; } catch (e) { return "auto"; } }
export function applyTheme(mode) {
  const root = document.documentElement;
  if (mode === "light" || mode === "dark") root.dataset.theme = mode; else delete root.dataset.theme;
  try { localStorage.setItem(THEME_KEY, mode); } catch (e) { /* private mode */ }
  window.dispatchEvent(new CustomEvent("studio-theme"));
}
export function isDark() {
  const t = document.documentElement.dataset.theme;
  return t ? t === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
}
export function themeButton() {
  const b = h("button.icon-btn", { title: "Light or dark", "aria-label": "Switch between light and dark" });
  const paint = () => { fill(b, icon(isDark() ? "sun" : "moon")); };
  b.addEventListener("click", () => { applyTheme(isDark() ? "light" : "dark"); paint(); });
  paint();
  return b;
}
applyTheme(readTheme());

// --- state -----------------------------------------------------------------------------------------------------------
export async function refreshState() {
  store.state = await api("/api/state");
  document.documentElement.style.setProperty("--accent", store.state.accent || "#3b5bdb");
  document.title = `Studio · ${store.state.site.name}`;
  return store.state;
}

// --- routing ---------------------------------------------------------------------------------------------------------
export function go(hash) { if (location.hash !== hash) location.hash = hash; else route(); }

async function route() {
  const hash = location.hash || "#/";
  const m = hash.match(/^#\/edit\/(.+)$/);
  if (current && current.beforeLeave && !(await current.beforeLeave())) return;
  if (current && current.destroy) current.destroy();
  current = null;
  clear(app);
  try {
    if (m) {
      const { openEditor } = await import("./editor.js");
      current = await openEditor(app, decodeURIComponent(m[1]));
    } else {
      current = await renderLibrary(app);
    }
  } catch (e) {
    console.error(e);
    fill(app, h("div.fatal", h("h1", "Something went wrong"), h("p", e.message || String(e)),
      h("button.btn", { onclick: () => go("#/") }, "Back to your pages")));
  }
}

window.addEventListener("hashchange", route);
window.addEventListener("beforeunload", (e) => {
  if (current && current.dirty && current.dirty()) { e.preventDefault(); e.returnValue = ""; }
});

(async () => {
  try {
    await refreshState();
  } catch (e) {
    fill(app, h("div.fatal", h("h1", "The Studio could not start"), h("p", e.message)));
    return;
  }
  route();
})();

export { toast };
