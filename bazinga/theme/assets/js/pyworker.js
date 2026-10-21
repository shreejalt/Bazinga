// Module worker that runs figure code in the reader's browser.
// Started by figure.js as `new Worker(url, {type: "module"})`.
//
// Messages in:  {id, type: "init", indexURL}
//               {id, type: "figure", module, plot, name, requires, values, narrow}
//               {id, type: "call", module, fn, args, requires}
// Messages out: {id, ok: true, result} | {id, ok: false, error}
//
// "figure" returns {svg, readouts_html}; "call" returns whatever the function returns, as JSON.
// Module files are fetched once per URL and written into the in-memory file system under /bazinga.

// Pinned runtime. figure.js normally passes the URL it was given by the page (from bazinga/vendor.py);
// this constant is only the fallback and must match the pinned version there.
const DEFAULT_INDEX_URL = "https://cdn.jsdelivr.net/pyodide/v314.0.7/full/";

let py = null;
let fns = null;     // the helper functions, looked up once
let booting = null;
const fetched = new Map();   // url -> module name
const sourceOf = new Map();  // module name -> url it was last loaded from
const packages = new Set();

const BOOT_CODE = `
import sys, json, importlib
sys.dont_write_bytecode = True
if "/bazinga" not in sys.path:
    sys.path.insert(0, "/bazinga")
_bazinga_json = {}

def _bazinga_import(name):
    if name in sys.modules:
        return sys.modules[name]
    importlib.invalidate_caches()
    return importlib.import_module(name)

def _bazinga_figure(modname, values_json, narrow):
    plot = _bazinga_import("_plot")
    mod = _bazinga_import(modname)
    controls = getattr(mod, "CONTROLS", [])
    values = plot.coerce(controls, json.loads(values_json))
    spec = mod.compute(_narrow=1 if narrow else 0, **values)
    svg, ro = plot.render(spec, narrow=narrow, title=getattr(mod, "TITLE", ""))
    return json.dumps({"svg": svg, "readouts_html": ro})

def _bazinga_resolve(v):
    if isinstance(v, dict):
        if len(v) == 1 and "$json" in v:
            return _bazinga_json[v["$json"]]
        return {k: _bazinga_resolve(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_bazinga_resolve(x) for x in v]
    return v

def _bazinga_call(modname, fn, args_json):
    mod = _bazinga_import(modname)
    f = getattr(mod, fn)
    args = _bazinga_resolve(json.loads(args_json))
    out = f(**args) if isinstance(args, dict) else f(*args)
    return json.dumps(out)

def _bazinga_put_json(url, text):
    _bazinga_json[url] = json.loads(text)
`;

async function boot(indexURL) {
  if (py) return py;
  if (!booting) {
    booting = (async () => {
      const base = indexURL || DEFAULT_INDEX_URL;
      const mod = await import(base + "pyodide.mjs");
      const p = await mod.loadPyodide({ indexURL: base });
      p.FS.mkdirTree("/bazinga");
      p.runPython(BOOT_CODE);
      fns = {
        figure: p.globals.get("_bazinga_figure"),
        call: p.globals.get("_bazinga_call"),
        putJson: p.globals.get("_bazinga_put_json"),
      };
      py = p;
      return p;
    })();
    booting.catch(() => { booting = null; });
  }
  return booting;
}

function moduleName(url) {
  const file = new URL(url, self.location.href).pathname.split("/").pop() || "module.py";
  const stem = file.replace(/\.py$/, "").replace(/[^A-Za-z0-9_]/g, "_");
  return /^[A-Za-z_]/.test(stem) ? stem : "_" + stem;
}

async function ensureModule(url, asName) {
  const abs = new URL(url, self.location.href).href;
  if (fetched.has(abs)) return fetched.get(abs);
  const res = await fetch(abs, { cache: "default" });
  if (!res.ok) throw new Error("could not load " + abs + " (" + res.status + ")");
  const text = await res.text();
  const name = asName || moduleName(abs);
  py.FS.writeFile("/bazinga/" + name + ".py", text);
  if (sourceOf.has(name) && sourceOf.get(name) !== abs) {
    // a new version of a module already imported (e.g. a changed ?v= in a preview): import it afresh
    py.runPython("import sys; sys.modules.pop(" + JSON.stringify(name) + ", None)");
  }
  sourceOf.set(name, abs);
  fetched.set(abs, name);
  return name;
}

async function ensurePackages(list) {
  const need = (list || []).filter((p) => !packages.has(p));
  if (!need.length) return;
  await py.loadPackage(need);
  need.forEach((p) => packages.add(p));
}

const jsonLoaded = new Set();
async function ensureJsonArgs(value) {
  // any {"$json": url} inside args is fetched once and kept on the worker side
  const urls = [];
  (function walk(v) {
    if (v && typeof v === "object") {
      if (!Array.isArray(v) && Object.keys(v).length === 1 && typeof v.$json === "string") urls.push(v.$json);
      else Object.values(v).forEach(walk);
    }
  })(value);
  for (const u of urls) {
    if (jsonLoaded.has(u)) continue;
    const res = await fetch(new URL(u, self.location.href).href);
    if (!res.ok) throw new Error("could not load " + u + " (" + res.status + ")");
    const text = await res.text();
    fns.putJson(u, text);
    jsonLoaded.add(u);
  }
}

function lastLine(err) {
  const s = String((err && err.message) || err || "error");
  const lines = s.trim().split("\n").filter(Boolean);
  return lines.length ? lines[lines.length - 1] : s;
}

// One task at a time keeps file writes and imports simple.
let queue = Promise.resolve();

self.onmessage = (ev) => {
  const msg = ev.data || {};
  queue = queue.then(() => handle(msg)).catch(() => {});
};

async function handle(msg) {
  const id = msg.id;
  try {
    let result = null;
    if (msg.type === "init") {
      const t0 = performance.now();
      await boot(msg.indexURL);
      result = { ms: performance.now() - t0 };
    } else if (msg.type === "figure") {
      await boot(msg.indexURL);
      await ensurePackages(msg.requires);
      await ensureModule(msg.plot, "_plot");
      const name = await ensureModule(msg.module, "tfig_" + String(msg.name).replace(/[^A-Za-z0-9_]/g, "_"));
      const t0 = performance.now();
      const out = fns.figure(name, JSON.stringify(msg.values || {}), msg.narrow ? 1 : 0);
      result = JSON.parse(out);
      result.ms = performance.now() - t0;
    } else if (msg.type === "call") {
      await boot(msg.indexURL);
      await ensurePackages(msg.requires);
      const name = await ensureModule(msg.module);
      await ensureJsonArgs(msg.args);
      const out = fns.call(name, msg.fn, JSON.stringify(msg.args ?? {}));
      result = JSON.parse(out);
    } else {
      throw new Error("unknown message type " + msg.type);
    }
    self.postMessage({ id, ok: true, result });
  } catch (err) {
    self.postMessage({ id, ok: false, error: lastLine(err), detail: String((err && err.message) || err) });
  }
}
