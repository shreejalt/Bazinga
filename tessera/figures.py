"""Interactive figures: figures/<name>.py modules.

A figure module declares TITLE, CAPTION, CONTROLS, optional PRESETS and REQUIRES, and a pure
``compute(**values, _narrow=0) -> spec``. This module:

- finds and imports them, checking the contract (FigureError says exactly what is wrong);
- runs compute() and renders the spec with tessera.plot (the same renderer the browser uses);
- writes the <figure> HTML for ``::figure name`` (static SVG at the defaults, wide and narrow, plus
  real form controls that figure.js wires to the in-browser worker);
- copies the used modules into _site/figures/;
- tests figures (defaults, presets, 20 random states, timing, NaN, well-formed SVG).
"""

import html
import importlib
import importlib.util
import inspect
import json
import math
import random
import re
import shutil
import sys
import time
import traceback
import xml.etree.ElementTree as ET
import zlib
from pathlib import Path

from tessera import plot

__all__ = ["FigureError", "discover", "load", "run", "figure_html", "write_assets", "test_figure",
           "defaults", "cli_new", "cli_test", "STARTERS"]

KINDS = ("slider", "steps", "toggle")
NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
BUDGET_MS = 30.0
STARTER_DIR = Path(__file__).parent / "starters"
STARTERS = ("slider_plot", "compare_bars", "heatmap", "geometry2d", "animation")
DRAWING_STARTERS = ("pipeline", "blocks")


class FigureError(Exception):
    """A figure that cannot be used. str(e) is a plain explanation with a hint."""


# ----------------------------------------------------------------------------------------------
# where things are

def _root(cfg=None):
    if cfg is not None and getattr(cfg, "root", None):
        return Path(cfg.root)
    try:
        from tessera import config
        return Path(config.ROOT)
    except Exception:
        return Path.cwd()


def _figures_dir(cfg=None):
    if cfg is not None:
        d = getattr(cfg, "figures_dir", None)
        if d:
            return Path(d)
    return _root(cfg) / "figures"


def discover(cfg=None):
    """{name: path} for figures/*.py not starting with '_'."""
    d = _figures_dir(cfg)
    if not d.is_dir():
        return {}
    return {p.stem: p for p in sorted(d.glob("*.py")) if not p.name.startswith("_")}


# ----------------------------------------------------------------------------------------------
# loading + the contract

_cache = {}  # path -> (mtime_ns, size, module)


def load(name, cfg=None, path=None):
    """Import figures/<name>.py and check its contract. Cached until the file changes."""
    if not isinstance(name, str) or not NAME_RE.match(name):
        raise FigureError("%r is not a valid figure name: use lowercase letters, digits and _ "
                          "(for example softmax_temperature)" % (name,))
    p = Path(path) if path else _figures_dir(cfg) / (name + ".py")
    if not p.is_file():
        known = sorted(discover(cfg))
        hint = _did_you_mean(name, known)
        raise FigureError("there is no figure %r (looked for %s).%s" % (
            name, p, hint or (" Known figures: " + ", ".join(known) if known else
                              " Create one with: python -m tessera figure new %s --from slider_plot" % name)))
    st = p.stat()
    key = str(p.resolve())
    hit = _cache.get(key)
    if hit and hit[0] == st.st_mtime_ns and hit[1] == st.st_size:
        return hit[2]
    modname = "tessera_figure_" + name
    spec = importlib.util.spec_from_file_location(modname, p)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except ModuleNotFoundError as e:
        raise FigureError("figure %r imports %r, which is not installed here. Install it in the build "
                          "environment and list it in REQUIRES (for example REQUIRES = [\"numpy\"])."
                          % (name, e.name))
    except SyntaxError as e:
        raise FigureError("figure %r has a syntax error at line %s: %s" % (name, e.lineno, e.msg))
    except Exception as e:
        raise FigureError("figure %r failed while importing: %s%s" % (name, _short_exc(e), _where(e, p)))
    validate(mod, name)
    _cache[key] = (st.st_mtime_ns, st.st_size, mod)
    return mod


def _did_you_mean(name, options):
    import difflib
    m = difflib.get_close_matches(name, options, n=1)
    return (" Did you mean %r?" % m[0]) if m else ""


def _short_exc(e):
    return "%s: %s" % (type(e).__name__, e)


def _where(e, path):
    """' (line 12)' for the deepest frame in the figure's own file."""
    line = None
    for fr in traceback.extract_tb(e.__traceback__):
        if Path(fr.filename).resolve() == Path(path).resolve():
            line = fr.lineno
    return (" (line %d)" % line) if line else ""


def _isnum(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def validate(mod, name):
    """Check the module-level contract. Raises FigureError with one clear message."""
    pre = "figure %r: " % name
    compute = getattr(mod, "compute", None)
    if compute is None or not callable(compute):
        raise FigureError(pre + "it has no compute() function. Add `def compute(_narrow=0, **values): "
                          "return {\"panels\": [...]}`.")
    title = getattr(mod, "TITLE", None)
    if not isinstance(title, str) or not title.strip():
        raise FigureError(pre + "TITLE must be a non-empty string, e.g. TITLE = \"Softmax temperature\".")
    if not isinstance(getattr(mod, "CAPTION", ""), str):
        raise FigureError(pre + "CAPTION must be a string.")
    req = getattr(mod, "REQUIRES", [])
    if not isinstance(req, (list, tuple)) or not all(isinstance(r, str) and r for r in req):
        raise FigureError(pre + "REQUIRES must be a list of package names, e.g. [\"numpy\"].")
    controls = getattr(mod, "CONTROLS", [])
    if not isinstance(controls, (list, tuple)):
        raise FigureError(pre + "CONTROLS must be a list of dicts.")
    names = set()
    for i, c in enumerate(controls):
        where = pre + "CONTROLS[%d]" % i
        if not isinstance(c, dict):
            raise FigureError(where + " must be a dict like {\"name\": \"t\", \"kind\": \"slider\", ...}.")
        n = c.get("name")
        if not isinstance(n, str) or not n.isidentifier() or n.startswith("_"):
            raise FigureError(where + ": 'name' must be a Python identifier not starting with _ (got %r)." % (n,))
        if n in names:
            raise FigureError(where + ": the name %r is used twice." % n)
        names.add(n)
        where = pre + "control %r" % n
        k = c.get("kind")
        if k not in KINDS:
            raise FigureError(where + ": unknown kind %r. Use one of: %s." % (k, ", ".join(KINDS)))
        if not isinstance(c.get("label", n), str):
            raise FigureError(where + ": 'label' must be a string.")
        if k == "slider":
            for f in ("min", "max", "value"):
                if not _isnum(c.get(f)):
                    raise FigureError(where + ": a slider needs a numeric %r." % f)
            if not c["min"] < c["max"]:
                raise FigureError(where + ": min (%s) must be smaller than max (%s)." % (c["min"], c["max"]))
            st = c.get("step", (c["max"] - c["min"]) / 100.0)
            if not _isnum(st) or st <= 0:
                raise FigureError(where + ": step must be a positive number.")
            if not c["min"] <= c["value"] <= c["max"]:
                raise FigureError(where + ": value %s is outside %s..%s." % (c["value"], c["min"], c["max"]))
            if "play" in c and not isinstance(c["play"], bool):
                raise FigureError(where + ": play must be True or False.")
        else:
            opts = c.get("options")
            if not isinstance(opts, (list, tuple)) or not opts or not all(isinstance(o, (str, int, float)) for o in opts):
                raise FigureError(where + ": a %s control needs 'options', a non-empty list of labels." % k)
            if k == "toggle" and len(opts) != 2:
                raise FigureError(where + ": a toggle has exactly two options (got %d); use kind \"steps\" for more." % len(opts))
            v = c.get("value", 0)
            if not isinstance(v, int) or isinstance(v, bool) or not 0 <= v < len(opts):
                raise FigureError(where + ": value is the index of the selected option, 0..%d (got %r)." % (len(opts) - 1, v))
            if c.get("play"):
                raise FigureError(where + ": only sliders can play.")
    # compute's signature takes every control and _narrow
    try:
        sig = inspect.signature(compute)
    except (TypeError, ValueError):
        sig = None
    if sig is not None:
        params = sig.parameters
        varkw = any(p.kind == p.VAR_KEYWORD for p in params.values())
        if not varkw:
            missing = [n for n in [c["name"] for c in controls] + ["_narrow"] if n not in params]
            if missing:
                raise FigureError(pre + "compute() does not accept %s. Its parameters must match CONTROLS "
                                  "plus _narrow, e.g. def compute(%s_narrow=0)." % (
                                      ", ".join(missing), "".join("%s=%r, " % (c["name"], c.get("value", 0)) for c in controls)))
    presets = getattr(mod, "PRESETS", [])
    if not isinstance(presets, (list, tuple)):
        raise FigureError(pre + "PRESETS must be a list of {\"label\": ..., \"values\": {...}}.")
    labels = set()
    by = {c["name"]: c for c in controls}
    for i, ps in enumerate(presets):
        where = pre + "PRESETS[%d]" % i
        if not isinstance(ps, dict) or not isinstance(ps.get("label"), str) or not ps["label"].strip():
            raise FigureError(where + " needs a 'label' (the button text).")
        if ps["label"].strip().lower() == "reset":
            raise FigureError(where + ": 'Reset' is added automatically; pick another label.")
        if ps["label"] in labels:
            raise FigureError(where + ": the label %r is used twice." % ps["label"])
        labels.add(ps["label"])
        vals = ps.get("values")
        if not isinstance(vals, dict) or not vals:
            raise FigureError(where + " (%r) needs 'values', a dict of control values." % ps["label"])
        for k, v in vals.items():
            if k not in by:
                raise FigureError(where + " (%r): %r is not a control.%s" % (ps["label"], k, _did_you_mean(k, list(by))))
            _check_value(by[k], v, where + " (%r)" % ps["label"])


def _check_value(c, v, where):
    if c["kind"] == "slider":
        if not _isnum(v):
            raise FigureError("%s: %s must be a number (got %r)." % (where, c["name"], v))
        if not c["min"] <= v <= c["max"]:
            raise FigureError("%s: %s = %s is out of range %s..%s." % (where, c["name"], v, c["min"], c["max"]))
    else:
        n = len(c["options"])
        if not isinstance(v, int) or isinstance(v, bool) or not 0 <= v < n:
            raise FigureError("%s: %s is an option index 0..%d (got %r)." % (where, c["name"], n - 1, v))


def controls(mod):
    return list(getattr(mod, "CONTROLS", []))


def presets(mod):
    return list(getattr(mod, "PRESETS", []))


def defaults(mod):
    return plot.coerce(controls(mod), {})


def _values_for(mod, name, values):
    ctl = controls(mod)
    by = {c["name"]: c for c in ctl}
    for k, v in (values or {}).items():
        if k not in by:
            raise FigureError("figure %r has no control %r.%s" % (name, k, _did_you_mean(k, list(by))))
        _check_value(by[k], v, "figure %r" % name)
    return plot.coerce(ctl, values or {})


# ----------------------------------------------------------------------------------------------
# running

def compute_spec(name, values=None, narrow=0, cfg=None):
    mod = load(name, cfg)
    vals = _values_for(mod, name, values)
    try:
        spec = mod.compute(_narrow=1 if narrow else 0, **vals)
    except Exception as e:
        raise FigureError("figure %r: compute(%s) raised %s%s" % (
            name, ", ".join("%s=%r" % kv for kv in vals.items()), _short_exc(e), _where(e, mod.__file__)))
    return mod, vals, spec


def run(name, values=None, narrow=0, cfg=None):
    """{"svg", "readouts_html", "ms"} for the figure at these values (defaults when None)."""
    t0 = time.perf_counter()
    mod, vals, spec = compute_spec(name, values, narrow, cfg)
    try:
        svg, ro = plot.render(spec, narrow=narrow, title=mod.TITLE)
    except plot.PlotError as e:
        raise FigureError("figure %r: the spec from compute() cannot be drawn: %s" % (name, e))
    return {"svg": svg, "readouts_html": ro, "ms": (time.perf_counter() - t0) * 1000.0}


# ----------------------------------------------------------------------------------------------
# HTML

def _attr(v):
    return html.escape(json.dumps(v, separators=(",", ":"), ensure_ascii=False), quote=True)


def _fmt_val(c, v):
    if c["kind"] != "slider":
        return str(c["options"][v])
    st = float(c.get("step") or 0)
    if isinstance(v, int):
        return str(v)
    dec = max(0, -int(math.floor(math.log10(st) + 1e-9))) if st > 0 else 2
    return ("%." + str(dec) + "f") % v


def _control_html(name, c, v):
    lab = html.escape(c.get("label", c["name"]))
    cname = html.escape(c["name"])
    if c["kind"] == "slider":
        step = c.get("step", (c["max"] - c["min"]) / 100.0)
        play = ""
        if c.get("play"):
            play = ('<button type="button" class="fig-play" data-for="%s" aria-label="Play %s">'
                    '<span class="fig-play-icon" aria-hidden="true"></span><span class="fig-play-text">Play</span></button>') % (cname, lab)
        return ('<div class="fig-ctl fig-slider" data-name="%s">'
                '<label><span class="fig-ctl-label">%s</span>'
                '<input type="range" name="%s" min="%s" max="%s" step="%s" value="%s"></label>'
                '<output class="fig-ctl-value" aria-hidden="true">%s</output>%s</div>') % (
            cname, lab, cname, _num(c["min"]), _num(c["max"]), _num(step), _num(v), html.escape(_fmt_val(c, v)), play)
    group = "fig-%s-%s" % (name, c["name"])
    opts = []
    for i, o in enumerate(c["options"]):
        opts.append('<label><input type="radio" name="%s" value="%d"%s><span>%s</span></label>' % (
            html.escape(group), i, " checked" if i == v else "", html.escape(str(o))))
    return ('<fieldset class="fig-ctl fig-%s" data-name="%s"><legend class="fig-ctl-label">%s</legend>'
            '<div class="fig-seg">%s</div></fieldset>') % (c["kind"], cname, lab, "".join(opts))


def _version(path):
    import hashlib
    return hashlib.sha1(Path(path).read_bytes()).hexdigest()[:10]


def _num(v):
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return repr(v) if isinstance(v, float) else str(v)


def figure_html(name, start=None, cfg=None):
    """The full <figure class="fig"> block for ``::figure name [| start: Preset]``."""
    mod = load(name, cfg)
    values = None
    if start:
        ps = {p["label"]: p for p in presets(mod)}
        if start not in ps:
            known = ", ".join(repr(k) for k in ps) or "none"
            raise FigureError("figure %r has no preset %r (presets: %s).%s" % (name, start, known, _did_you_mean(start, list(ps))))
        values = dict(ps[start]["values"])
    vals = _values_for(mod, name, values)
    wide = run(name, vals, 0, cfg)
    narrow = run(name, vals, 1, cfg)
    ctl = controls(mod)
    data = {
        "name": name,
        # ?v= changes when the file changes, so browsers and the worker never use a stale copy
        "module": "figures/%s.py?v=%s" % (name, _version(Path(mod.__file__))),
        "plot": "figures/_plot.py?v=%s" % _version(Path(plot.__file__)),
        "requires": list(getattr(mod, "REQUIRES", [])),
        "controls": ctl,
        "values": vals,
        "defaults": defaults(mod),
        "presets": presets(mod),
        "title": mod.TITLE,
    }
    caption = getattr(mod, "CAPTION", "")
    parts = ['<figure class="fig" data-figure="%s" data-tessera="%s">' % (
        html.escape(name), _attr(data))]
    parts.append('<figcaption class="fig-head"><span class="fig-title">%s</span>%s</figcaption>' % (
        html.escape(mod.TITLE), ('<span class="fig-caption">%s</span>' % html.escape(caption)) if caption else ""))
    parts.append('<div class="fig-stage"><div class="fig-svg fig-svg-wide">%s</div>'
                 '<div class="fig-svg fig-svg-narrow">%s</div></div>' % (wide["svg"], narrow["svg"]))
    parts.append('<div class="fig-out">%s</div>' % wide["readouts_html"])
    if ctl or presets(mod):
        parts.append('<form class="fig-controls" action="#" onsubmit="return false"><fieldset class="fig-fs" disabled>')
        parts.append("".join(_control_html(name, c, vals[c["name"]]) for c in ctl))
        btns = "".join('<button type="button" class="fig-preset" data-preset="%d">%s</button>' % (i, html.escape(p["label"]))
                       for i, p in enumerate(presets(mod)))
        parts.append('<div class="fig-presets">%s<button type="button" class="fig-reset">Reset</button>'
                     '<span class="fig-status" role="status" aria-live="polite"></span></div>' % btns)
        parts.append("</fieldset></form>")
    parts.append("</figure>")
    return "".join(parts)


# ----------------------------------------------------------------------------------------------
# assets

def write_assets(cfg, used, out):
    """Copy the used figure modules and the renderer into <out>/figures/."""
    out = Path(out)
    dest = out / "figures"
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(Path(plot.__file__), dest / "_plot.py")
    found = discover(cfg)
    for name in sorted(set(used or ())):
        if name not in found:
            raise FigureError("figure %r is used on a page but figures/%s.py does not exist." % (name, name))
        load(name, cfg)  # contract check
        shutil.copyfile(found[name], dest / (name + ".py"))
    return dest


# ----------------------------------------------------------------------------------------------
# testing

def _walk_bad_numbers(obj, path="spec"):
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return [path]
        return []
    if hasattr(obj, "tolist") and not isinstance(obj, (str, bytes)):
        try:
            obj = obj.tolist()
        except Exception:
            return []
    if isinstance(obj, dict):
        out = []
        for k, v in obj.items():
            out += _walk_bad_numbers(v, "%s.%s" % (path, k))
            if len(out) > 3:
                break
        return out
    if isinstance(obj, (list, tuple)):
        out = []
        for i, v in enumerate(obj):
            out += _walk_bad_numbers(v, "%s[%d]" % (path, i))
            if len(out) > 3:
                break
        return out
    return []


def _random_states(mod, n, seed):
    rng = random.Random(seed)
    states = []
    for _ in range(n):
        v = {}
        for c in controls(mod):
            if c["kind"] == "slider":
                if rng.random() < 0.15:
                    v[c["name"]] = rng.choice([c["min"], c["max"]])
                else:
                    v[c["name"]] = rng.uniform(c["min"], c["max"])
            else:
                v[c["name"]] = rng.randrange(len(c["options"]))
        states.append(plot.coerce(controls(mod), v))
    return states


def check_state(name, values, narrow=0, cfg=None, budget_ms=BUDGET_MS):
    """Problems for one state (empty list = fine)."""
    label = "%s %s%s" % (name, json.dumps(values, sort_keys=True), " (narrow)" if narrow else "")
    try:
        best = None
        for attempt in range(3):
            t0 = time.perf_counter()
            mod, vals, spec = compute_spec(name, values, narrow, cfg)
            svg, ro = plot.render(spec, narrow=narrow, title=mod.TITLE)
            ms = (time.perf_counter() - t0) * 1000
            best = ms if best is None else min(best, ms)
            if best <= budget_ms:
                break
    except FigureError as e:
        return ["%s: %s" % (label, e)]
    except plot.PlotError as e:
        return ["%s: the spec cannot be drawn: %s" % (label, e)]
    except Exception as e:
        return ["%s: %s" % (label, _short_exc(e))]
    problems = []
    bad = _walk_bad_numbers(spec)
    if bad:
        problems.append("%s: NaN or infinity at %s (use None for a gap in a line)" % (label, ", ".join(bad[:3])))
    if best > budget_ms:
        problems.append("%s: took %.1f ms (budget %.0f ms)" % (label, best, budget_ms))
    try:
        ET.fromstring(svg)
    except ET.ParseError as e:
        problems.append("%s: the SVG is not well-formed: %s" % (label, e))
    if re.search(r"\b(nan|inf)\b", svg, re.I) and re.search(r'="[^"]*\b(nan|inf)\b', svg, re.I):
        problems.append("%s: the SVG contains nan/inf coordinates" % label)
    try:
        ET.fromstring("<div>%s</div>" % ro)
    except ET.ParseError as e:
        problems.append("%s: the readouts HTML is not well-formed: %s" % (label, e))
    if re.search(r">\s*(nan|inf|-inf)\s*<", ro, re.I):
        problems.append("%s: a readout shows nan/inf" % label)
    return problems


def test_figure(name, cfg=None, n_random=20, budget_ms=BUDGET_MS):
    """All problems found for a figure: defaults (wide + narrow), every preset, 20 seeded random states."""
    try:
        mod = load(name, cfg)
    except FigureError as e:
        return [str(e)]
    problems = []
    for req in getattr(mod, "REQUIRES", []):
        try:
            importlib.import_module(req)
        except ImportError:
            problems.append("figure %r: REQUIRES %r but it is not installed in the build environment" % (name, req))
    states = [(defaults(mod), 0), (defaults(mod), 1)]
    for p in presets(mod):
        v = plot.coerce(controls(mod), p["values"])
        states += [(v, 0), (v, 1)]
    for i, v in enumerate(_random_states(mod, n_random, zlib.crc32(name.encode()))):
        states.append((v, i % 2))
    for v, nar in states:
        problems += check_state(name, v, nar, cfg, budget_ms)
        if len(problems) >= 8:
            problems.append("(stopped after 8 problems)")
            break
    try:
        figure_html(name, cfg=cfg)
    except FigureError as e:
        problems.append(str(e))
    return problems


# ----------------------------------------------------------------------------------------------
# CLI hooks (called by tessera.cli)

def cli_new(name, starter="slider_plot", cfg=None, kind="figure"):
    """Copy a starter to figures/<name>.py (or drawings/<name>.py for a drawing starter). Returns the path."""
    if not NAME_RE.match(name or ""):
        raise FigureError("%r is not a valid name: use lowercase letters, digits and _ (e.g. my_plot)." % (name,))
    if starter in DRAWING_STARTERS and kind == "figure" and starter not in STARTERS:
        kind = "drawing"
    pool = STARTERS if kind == "figure" else DRAWING_STARTERS
    if starter not in pool:
        raise FigureError("no %s starter %r. Choose one of: %s." % (kind, starter, ", ".join(pool)))
    src = STARTER_DIR / ("figures" if kind == "figure" else "drawings") / (starter + ".py")
    dest_dir = _figures_dir(cfg) if kind == "figure" else _root(cfg) / "drawings"
    if kind == "drawing" and cfg is not None and getattr(cfg, "drawings_dir", None):
        dest_dir = Path(cfg.drawings_dir)
    dest = dest_dir / (name + ".py")
    if dest.exists():
        raise FigureError("%s already exists; pick another name or edit that file." % dest)
    dest_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dest)
    if kind == "figure":
        problems = test_figure(name, cfg)
        if problems:
            raise FigureError("the new figure fails its test: " + "; ".join(problems[:3]))
    return dest


def cli_test(name=None, cfg=None, out=None):
    """Test one figure or all; prints a line per figure; returns the exit code (0 = all fine)."""
    out = out or sys.stdout
    names = [name] if name else sorted(discover(cfg))
    if not names:
        print("No figures found in %s." % _figures_dir(cfg), file=out)
        return 0
    bad = 0
    for n in names:
        t0 = time.perf_counter()
        problems = test_figure(n, cfg)
        ms = (time.perf_counter() - t0) * 1000
        if problems:
            bad += 1
            print("FAIL %s" % n, file=out)
            for p in problems:
                print("     " + p, file=out)
        else:
            print("ok   %s  (%.0f ms for all states)" % (n, ms), file=out)
    return 1 if bad else 0
