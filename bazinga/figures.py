"""Interactive figures: figures/<name>.py modules.

A figure module declares TITLE, CAPTION, CONTROLS, optional PRESETS and REQUIRES, and a pure
``compute(**values, _narrow=0) -> spec``. This module:

- finds and imports them, checking the contract (FigureError says exactly what is wrong);
- runs compute() and renders the spec with bazinga.plot (the same renderer the browser uses);
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
import os
import random
import re
import shutil
import sys
import time
import traceback
import xml.etree.ElementTree as ET
import zlib
from pathlib import Path

from bazinga import plot
from bazinga import scene3d

__all__ = ["FigureError", "discover", "load", "run", "figure_html", "write_assets", "test_figure",
           "test_report", "defaults", "cli_new", "cli_test", "cli_list", "cli_preview", "made_with", "STARTERS"]

KINDS = ("slider", "steps", "toggle", "orbit", "pad", "hidden")
VECTOR_KINDS = ("orbit", "pad", "hidden")   # values a drag in the picture changes (3-D figures)
# kits a figure may import besides the standard library; each is shipped to figures/_<kit>.py
KITS = {"scene3d": Path(scene3d.__file__)}
_KIT_RE = {k: re.compile(r"^\s*(from\s+bazinga\s+import\s+[^\n]*\b%s\b|from\s+bazinga\.%s\s+import|import\s+bazinga\.%s\b)" % (k, k, k), re.M)
           for k in KITS}
NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
BUDGET_MS = 30.0


def default_budget_ms() -> float:
    """The time a figure may take per state: BUDGET_MS, or BAZINGA_FIGURE_BUDGET_MS when set ("inf" turns the timing
    check off; the test suite does that unless BAZINGA_PERF_TESTS=1, so a busy build machine cannot fail a deploy)."""
    raw = os.environ.get("BAZINGA_FIGURE_BUDGET_MS", "").strip()
    try:
        return float(raw) if raw else BUDGET_MS
    except ValueError:
        return BUDGET_MS
STARTER_DIR = Path(__file__).parent / "starters"
STARTERS = ("slider_plot", "compare_bars", "heatmap", "geometry2d", "animation", "scatter_fit", "distribution",
            "matrix_transform", "step_through", "data_lines", "linked_panels", "sampling", "vector_field",
            "scene_basic", "surface_plot", "vectors_planes", "camera_rig")
# ::figure starter_<name> shows a starter as it is (the template gallery uses this); a figures/ file of the same
# name wins.
STARTER_PREFIX = "starter_"
DRAWING_STARTERS = ("pipeline", "blocks", "architecture", "flowchart", "timeline", "tree")


class FigureError(Exception):
    """A figure that cannot be used. str(e) is a plain explanation with a hint."""


# ----------------------------------------------------------------------------------------------
# where things are

def _root(cfg=None):
    if cfg is not None and getattr(cfg, "root", None):
        return Path(cfg.root)
    try:
        from bazinga import config
        return Path(config.ROOT)
    except Exception:
        return Path.cwd()


def _figures_dir(cfg=None):
    if cfg is not None:
        d = getattr(cfg, "figures_dir", None)
        if d:
            return Path(d)
    return _root(cfg) / "figures"


def _path(name, cfg=None):
    """figures/<name>.py, or the starter itself for ``starter_<starter>`` when figures/ has no such file."""
    p = _figures_dir(cfg) / (name + ".py")
    if not p.is_file() and name.startswith(STARTER_PREFIX) and name[len(STARTER_PREFIX):] in STARTERS:
        return STARTER_DIR / "figures" / (name[len(STARTER_PREFIX):] + ".py")
    return p


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
    p = Path(path) if path else _path(name, cfg)
    if not p.is_file():
        known = sorted(discover(cfg))
        hint = _did_you_mean(name, known)
        raise FigureError("there is no figure %r (looked for %s).%s" % (
            name, p, hint or (" Known figures: " + ", ".join(known) if known else
                              " Create one with: python -m bazinga figure new %s --from slider_plot" % name)))
    st = p.stat()
    key = str(p.resolve())
    hit = _cache.get(key)
    if hit and hit[0] == st.st_mtime_ns and hit[1] == st.st_size:
        return hit[2]
    modname = "bazinga_figure_" + name
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
        if "group" in c and (not isinstance(c["group"], str) or not c["group"].strip()):
            raise FigureError(where + ": 'group' is the heading of a folding panel of controls, a non-empty string.")
        if k in VECTOR_KINDS:
            _check_vector_control(c, where)
            continue
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
            need_drag = ["_drag"] if any(c.get("kind") in ("pad", "hidden") for c in controls) else []
            missing = [n for n in [c["name"] for c in controls] + ["_narrow"] + need_drag if n not in params]
            if need_drag and missing == ["_drag"]:
                raise FigureError(pre + "it has a pad or hidden control, which a drag in the picture moves, so "
                                  "compute() must accept _drag, e.g. def compute(..., _drag=None, _narrow=0).")
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


def _numlist(v):
    return isinstance(v, (list, tuple)) and 1 <= len(v) <= 4 and all(_isnum(x) for x in v)


def _check_vector_control(c, where):
    """orbit: value [azimuth, elevation]; pad / hidden: a number or a list of up to 4, optional min / max alike."""
    v = c.get("value")
    if c["kind"] == "orbit":
        if not (_numlist(v) and len(v) == 2):
            raise FigureError(where + ": an orbit control's value is [azimuth, elevation] in degrees, e.g. [35, 25].")
        er = c.get("el_range")
        if er is not None and not (_numlist(er) and len(er) == 2 and er[0] < er[1]):
            raise FigureError(where + ": el_range is [lowest, highest] elevation in degrees, e.g. [-10, 89].")
        return
    if not (_isnum(v) or _numlist(v)):
        raise FigureError(where + ": a %s control's value is a number or a list of numbers, e.g. [0.5, 1.0]." % c["kind"])
    for f in ("min", "max"):
        b = c.get(f)
        if b is None:
            continue
        if _isnum(v) and not _isnum(b) or (not _isnum(v) and not (_numlist(b) and len(b) == len(v))):
            raise FigureError(where + ": %s must have the same shape as the value (%r)." % (f, v))
    if c.get("min") is not None and c.get("max") is not None:
        lo, hi = c["min"], c["max"]
        pairs = [(lo, hi)] if _isnum(v) else list(zip(lo, hi))
        if any(a > b for a, b in pairs):
            raise FigureError(where + ": min must not be above max.")


def _check_value(c, v, where):
    if c["kind"] in VECTOR_KINDS:
        d = c.get("value")
        ok = _isnum(v) if _isnum(d) else (_numlist(v) and len(v) == len(d))
        if not ok:
            raise FigureError("%s: %s must look like its starting value %r (got %r)." % (where, c["name"], d, v))
        return
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

def compute_spec(name, values=None, narrow=0, cfg=None, drag=None):
    mod = load(name, cfg)
    vals = _values_for(mod, name, values)
    try:
        spec = mod.compute(_narrow=1 if narrow else 0, **vals, **({"_drag": drag} if drag else {}))
    except Exception as e:
        raise FigureError("figure %r: compute(%s) raised %s%s" % (
            name, ", ".join("%s=%r" % kv for kv in vals.items()), _short_exc(e), _where(e, mod.__file__)))
    return mod, vals, spec


def run(name, values=None, narrow=0, cfg=None, drag=None):
    """{"svg", "readouts_html", "ms"} for the figure at these values (defaults when None); "state" too when
    compute() returned one (the values a drag changed)."""
    t0 = time.perf_counter()
    mod, vals, spec = compute_spec(name, values, narrow, cfg, drag)
    try:
        svg, ro = plot.render(spec, narrow=narrow, title=mod.TITLE)
    except plot.PlotError as e:
        raise FigureError("figure %r: the spec from compute() cannot be drawn: %s" % (name, e))
    out = {"svg": svg, "readouts_html": ro, "ms": (time.perf_counter() - t0) * 1000.0}
    if isinstance(spec, dict) and spec.get("state"):
        out["state"] = spec["state"]
    return out


# ----------------------------------------------------------------------------------------------
# HTML

def _attr(v):
    return html.escape(json.dumps(v, separators=(",", ":"), ensure_ascii=False), quote=True)


def _fmt_val(c, v):
    if c["kind"] in VECTOR_KINDS:
        return _vec_text(v)
    if c["kind"] != "slider":
        return str(c["options"][v])
    st = float(c.get("step") or 0)
    if isinstance(v, int):
        return str(v)
    dec = max(0, -int(math.floor(math.log10(st) + 1e-9))) if st > 0 else 2
    return ("%." + str(dec) + "f") % v


def _vec_text(v):
    if isinstance(v, (list, tuple)):
        return "(" + ", ".join(plot.fmt_num(round(float(x), 2)) for x in v) + ")"
    return plot.fmt_num(round(float(v), 2))


def _control_html(name, c, v):
    lab = html.escape(c.get("label", c["name"]))
    cname = html.escape(c["name"])
    if c["kind"] in ("orbit", "hidden"):
        return ""                                 # moved by dragging the picture; nothing to show
    if c["kind"] == "pad":
        return ('<div class="fig-ctl fig-pad" data-name="%s"><span class="fig-ctl-label">%s</span>'
                '<output class="fig-ctl-value">%s</output></div>') % (cname, lab, html.escape(_vec_text(v)))
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


def _controls_html(name, ctl, vals):
    """The controls in order; consecutive controls with the same "group" fold into one panel under its heading."""
    out, open_group = [], None
    for c in ctl:
        g = c.get("group")
        if g != open_group:
            if open_group:
                out.append("</div></details>")
            if g:
                out.append('<details class="fig-group"><summary>%s</summary><div class="fig-group-body">' % html.escape(g))
            open_group = g
        out.append(_control_html(name, c, vals[c["name"]]))
    if open_group:
        out.append("</div></details>")
    return "".join(out)


def uses_kits(mod):
    """The kits (e.g. scene3d) a figure module imports, read from its source."""
    try:
        src = Path(mod.__file__).read_text(encoding="utf-8")
    except (OSError, TypeError, AttributeError):
        return []
    return [k for k, rx in _KIT_RE.items() if rx.search(src)]


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
    kits = uses_kits(mod)
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
    if kits:
        data["kits"] = {k: "figures/_%s.py?v=%s" % (k, _version(KITS[k])) for k in kits}
    caption = getattr(mod, "CAPTION", "")
    parts = ['<figure class="fig" data-figure="%s" data-bazinga="%s">' % (
        html.escape(name), _attr(data))]
    parts.append('<figcaption class="fig-head"><span class="fig-title">%s</span>%s</figcaption>' % (
        html.escape(mod.TITLE), ('<span class="fig-caption">%s</span>' % html.escape(caption)) if caption else ""))
    parts.append('<div class="fig-stage"><div class="fig-svg fig-svg-wide">%s</div>'
                 '<div class="fig-svg fig-svg-narrow">%s</div></div>' % (wide["svg"], narrow["svg"]))
    parts.append('<div class="fig-out">%s</div>' % wide["readouts_html"])
    if ctl or presets(mod):
        parts.append('<form class="fig-controls" action="#" onsubmit="return false"><fieldset class="fig-fs" disabled>')
        parts.append(_controls_html(name, ctl, vals))
        btns = "".join('<button type="button" class="fig-preset" data-preset="%d">%s</button>' % (i, html.escape(p["label"]))
                       for i, p in enumerate(presets(mod)))
        hint = ""
        if any(c["kind"] == "orbit" for c in ctl):
            hint = '<span class="fig-hint">Drag the picture to turn it.</span>'
        parts.append('<div class="fig-presets">%s<button type="button" class="fig-reset">Reset</button>%s'
                     '<span class="fig-status" role="status" aria-live="polite"></span></div>' % (btns, hint))
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
    for kit, src in KITS.items():
        shutil.copyfile(src, dest / ("_%s.py" % kit))
    for name in sorted(set(used or ())):
        src = _path(name, cfg)
        if not src.is_file():
            raise FigureError("figure %r is used on a page but figures/%s.py does not exist." % (name, name))
        load(name, cfg)  # contract check
        shutil.copyfile(src, dest / (name + ".py"))
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
            if c["kind"] == "orbit":
                lo, hi = c.get("el_range") or (-89, 89)
                v[c["name"]] = [rng.uniform(-180, 180), rng.uniform(max(lo, -30), min(hi, 80))]
            elif c["kind"] in ("pad", "hidden"):
                d, lo, hi = c["value"], c.get("min"), c.get("max")
                if lo is not None and hi is not None:
                    v[c["name"]] = rng.uniform(lo, hi) if _isnum(d) else [rng.uniform(a, b) for a, b in zip(lo, hi)]
                else:
                    v[c["name"]] = d
            elif c["kind"] == "slider":
                if rng.random() < 0.15:
                    v[c["name"]] = rng.choice([c["min"], c["max"]])
                else:
                    v[c["name"]] = rng.uniform(c["min"], c["max"])
            else:
                v[c["name"]] = rng.randrange(len(c["options"]))
        states.append(plot.coerce(controls(mod), v))
    return states


def check_state(name, values, narrow=0, cfg=None, budget_ms=None, timing=None, drag=None):
    """Problems for one state (empty list = fine). The best time in ms is appended to ``timing`` when given."""
    budget_ms = default_budget_ms() if budget_ms is None else budget_ms
    label = "%s %s%s%s" % (name, json.dumps(values, sort_keys=True), " (narrow)" if narrow else "",
                           (" dragging %s" % drag.get("handle")) if drag else "")
    try:
        best = None
        for attempt in range(3):
            t0 = time.perf_counter()
            mod, vals, spec = compute_spec(name, values, narrow, cfg, drag)
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
        return ["%s: %s%s" % (label, _short_exc(e), _where_any(e, name, cfg))]
    if timing is not None:
        timing.append(best)
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
    st = spec.get("state") if isinstance(spec, dict) else None
    if st is not None:
        by = {c["name"]: c for c in controls(mod)}
        if not isinstance(st, dict):
            problems.append("%s: state must be a dict of control values" % label)
        else:
            for k, v in st.items():
                if k not in by:
                    problems.append("%s: state names %r, which is not a control" % (label, k))
                else:
                    try:
                        _check_value(by[k], plot.coerce([by[k]], {k: v})[k], "state")
                    except FigureError as e:
                        problems.append("%s: %s" % (label, e))
    return problems


def drag_cases(name, values, narrow=0, cfg=None):
    """A small drag of every handle in the figure's scene panels at these values: [(values, narrow, drag)]."""
    try:
        mod, vals, spec = compute_spec(name, values, narrow, cfg)
    except Exception:
        return []
    out = []
    for p in (spec.get("panels") or []) if isinstance(spec, dict) else []:
        if not isinstance(p, dict) or p.get("kind") != "scene3d":
            continue
        for h in p.get("handles") or []:
            ctl = h.get("control") or h.get("name")
            if ctl not in vals:
                continue
            frm = list(h.get("p") or h.get("P"))
            for d in ((14, -9), (-30, 22)):
                out.append((values, narrow, {"handle": h.get("name"), "name": ctl, "inset": h.get("inset"),
                                             "start": vals[ctl], "from": frm, "to": [frm[0] + d[0], frm[1] + d[1]]}))
    return out


def _handle_problems(name, mod, values, narrow, cfg):
    """Handles must drive real controls, and compute() must take _drag when there are handles."""
    try:
        _, vals, spec = compute_spec(name, values, narrow, cfg)
    except Exception:
        return []
    probs = []
    names = {c["name"] for c in controls(mod)}
    for p in (spec.get("panels") or []) if isinstance(spec, dict) else []:
        for h in (p.get("handles") or []) if isinstance(p, dict) else []:
            ctl = h.get("control") or h.get("name")
            if ctl not in names:
                probs.append("figure %r: the handle %r drives %r, which is not a control (add a pad or hidden control "
                             "with that name)" % (name, h.get("name"), ctl))
    if probs or not any((p.get("handles") if isinstance(p, dict) else None) for p in spec.get("panels") or []):
        return probs
    try:
        params = inspect.signature(mod.compute).parameters
        if "_drag" not in params and not any(q.kind == q.VAR_KEYWORD for q in params.values()):
            probs.append("figure %r: it has handles to drag, so compute() must accept _drag "
                         "(def compute(..., _drag=None, _narrow=0))" % name)
    except (TypeError, ValueError):
        pass
    return probs


def test_figure(name, cfg=None, n_random=20, budget_ms=None):
    """All problems found for a figure: defaults (wide + narrow), every preset, 20 seeded random states."""
    budget_ms = default_budget_ms() if budget_ms is None else budget_ms
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
    if len(problems) < 8:
        for nar in (0, 1):
            problems += _handle_problems(name, mod, defaults(mod), nar, cfg)
        if not problems:
            for v, nar, drag in drag_cases(name, defaults(mod), 0, cfg) + drag_cases(name, defaults(mod), 1, cfg):
                problems += check_state(name, v, nar, cfg, budget_ms, drag=drag)
                if len(problems) >= 8:
                    break
    try:
        figure_html(name, cfg=cfg)
    except FigureError as e:
        problems.append(str(e))
    return problems


# ----------------------------------------------------------------------------------------------
# CLI hooks (called by bazinga.cli)

def cli_new(name, starter="slider_plot", cfg=None, kind="figure"):
    """Copy a starter to figures/<name>.py (or drawings/<name>.py for a drawing starter). Returns the path.
    ``builder`` or ``builder:<type>`` writes the figure builder's example of that type instead (the Editor can then
    open it in the builder's form)."""
    if kind == "figure" and (starter or "").startswith("builder"):
        return _cli_new_builder(name, starter, cfg)
    if not NAME_RE.match(name or ""):
        raise FigureError("%r is not a valid name: use lowercase letters, digits and _ (e.g. my_plot)." % (name,))
    if starter in DRAWING_STARTERS and kind == "figure" and starter not in STARTERS:
        kind = "drawing"
    pool = STARTERS if kind == "figure" else DRAWING_STARTERS
    if starter not in pool:
        raise FigureError("no %s starter %r. Choose one of: %s%s." % (
            kind, starter, ", ".join(pool), " (or builder, builder:<type> for the form)" if kind == "figure" else ""))
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


def _starter_meta(path):
    """TITLE and CAPTION of a starter, read without running it."""
    import ast
    out = {}
    for node in ast.parse(Path(path).read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and getattr(node.targets[0], "id", "") in ("TITLE", "CAPTION"):
            try:
                out[node.targets[0].id] = ast.literal_eval(node.value)
            except ValueError:
                pass
    return out


def cli_starters(out=None):
    """Print every starter with what it draws and the command that copies it."""
    out = out or sys.stdout
    for kind, pool, sub, place in (("Figures (figures/)", STARTERS, "figures", "::figure my_name"),
                                   ("Drawings from code (drawings/)", DRAWING_STARTERS, "drawings", "::drawing my_name.<function>")):
        print(kind, file=out)
        for s in pool:
            meta = _starter_meta(STARTER_DIR / sub / (s + ".py"))
            print("  %-17s %s" % (s, meta.get("TITLE", "")), file=out)
        print("  copy one:  python -m bazinga figure new my_name --from <starter>   then write  %s\n" % place, file=out)
    print("See them all, live: the \"Templates for Figures and Diagrams\" page of the example site.", file=out)
    return 0


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


# ----------------------------------------------------------------------------------------------
# the test in plain words (the Editor), and what a figure was made with

_LINE_RE = re.compile(r"\bline (\d+)\b")


def _where_any(e, name, cfg):
    try:
        return _where(e, _figures_dir(cfg) / (name + ".py"))
    except Exception:
        return ""


def line_of(text):
    """The line number a problem message points at, or None."""
    m = _LINE_RE.search(str(text or ""))
    return int(m.group(1)) if m else None


def test_report(name, cfg=None, n_random=20, budget_ms=None):
    """The figure test as a list of plain checks: {"ok", "checks": [{"label", "ok", "detail"}], "problems",
    "slowest_ms", "line"}. The same states as test_figure()."""
    budget_ms = default_budget_ms() if budget_ms is None else budget_ms
    try:
        mod = load(name, cfg)
    except FigureError as e:
        return {"ok": False, "problems": [str(e)], "slowest_ms": None, "line": line_of(e),
                "checks": [{"label": "The file loads and follows the figure contract", "ok": False, "detail": str(e)}]}
    checks, problems, times = [], [], []
    for req in getattr(mod, "REQUIRES", []):
        try:
            importlib.import_module(req)
        except ImportError:
            problems.append("figure %r: REQUIRES %r but it is not installed in the build environment" % (name, req))
            checks.append({"label": "Its packages are installed", "ok": False, "detail": problems[-1]})
    groups = [("It draws at its starting values, wide and on a phone", [(defaults(mod), 0), (defaults(mod), 1)])]
    ps = presets(mod)
    if ps:
        states = []
        for p in ps:
            v = plot.coerce(controls(mod), p["values"])
            states += [(v, 0), (v, 1)]
        groups.append(("Every preset draws (%d)" % len(ps), states))
    if controls(mod):
        rnd = [(v, i % 2) for i, v in enumerate(_random_states(mod, n_random, zlib.crc32(name.encode())))]
        groups.append(("%d random settings of the controls draw" % n_random, rnd))
    slow = []
    for label, states in groups:
        found = []
        for v, nar in states:
            for pr in check_state(name, v, nar, cfg, budget_ms, timing=times):
                (slow if " took " in pr and "budget" in pr else found).append(pr)
            if len(found) >= 4:
                break
        problems += found
        checks.append({"label": label, "ok": not found, "detail": found[0] if found else ""})
    drags = drag_cases(name, defaults(mod), 0, cfg) + drag_cases(name, defaults(mod), 1, cfg)
    hp = _handle_problems(name, mod, defaults(mod), 0, cfg) + _handle_problems(name, mod, defaults(mod), 1, cfg)
    if drags or hp:
        found = list(hp)
        if not found:
            for v, nar, drag in drags:
                for pr in check_state(name, v, nar, cfg, budget_ms, timing=times, drag=drag):
                    (slow if " took " in pr and "budget" in pr else found).append(pr)
                if len(found) >= 4:
                    break
        problems += found
        checks.append({"label": "Dragging each point in the picture works", "ok": not found,
                       "detail": found[0] if found else ""})
    slowest = max(times) if times else None
    if slowest is not None:
        ok = not slow
        checks.append({"label": "Fast enough: the slowest setting took %.1f ms (the limit is %.0f ms)" % (slowest, budget_ms),
                       "ok": ok, "detail": slow[0] if slow else ""})
        problems += slow[:2]
    try:
        figure_html(name, cfg=cfg)
    except FigureError as e:
        problems.append(str(e))
        checks.append({"label": "It can be placed in a page", "ok": False, "detail": str(e)})
    line = next((line_of(p) for p in problems if line_of(p)), None)
    return {"ok": not problems, "checks": checks, "problems": problems, "slowest_ms": slowest, "line": line}


def made_with(source):
    """'builder' (made with the form, unchanged), 'edited' (made with the form, then changed by hand) or 'code'."""
    try:
        from bazinga import figbuilder
    except ImportError:
        return "code"
    info = figbuilder.read_spec(source)
    if info is None:
        return "code"
    return "edited" if info["edited"] else "builder"


def _builder_source(name, starter):
    from bazinga import figbuilder
    kind = starter.split(":", 1)[1] if ":" in starter else "function"
    if kind not in figbuilder.TYPES:
        raise FigureError("no builder type %r. Choose one of: %s (for example --from builder:%s)." % (
            kind, ", ".join(figbuilder.TYPES), next(iter(figbuilder.TYPES))))
    spec = figbuilder.default_spec(kind)
    return figbuilder.generate(spec)


def _cli_new_builder(name, starter, cfg):
    """figures/<name>.py written by the figure builder from its example of a type (``builder:<type>``)."""
    if not NAME_RE.match(name or ""):
        raise FigureError("%r is not a valid name: use lowercase letters, digits and _ (e.g. my_plot)." % (name,))
    dest_dir = _figures_dir(cfg)
    dest = dest_dir / (name + ".py")
    if dest.exists():
        raise FigureError("%s already exists; pick another name or edit that file." % dest)
    src = _builder_source(name, starter)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest.write_text(src, encoding="utf-8")
    problems = test_figure(name, cfg)
    if problems:
        raise FigureError("the new figure fails its test: " + "; ".join(problems[:3]))
    return dest


def _uses(cfg):
    """{figure name: [content files that place it]} from ::figure lines."""
    root = _root(cfg)
    content = Path(getattr(cfg, "content_dir", None) or root / "content")
    out = {}
    if content.is_dir():
        for p in sorted(content.rglob("*.md")):
            try:
                text = p.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            for m in re.finditer(r"^\s*::figure\s+([a-z][a-z0-9_]*)", text, re.M):
                out.setdefault(m.group(1), [])
                rel = str(p.relative_to(content))
                if rel not in out[m.group(1)]:
                    out[m.group(1)].append(rel)
    return out


def cli_list(cfg=None, out=None):
    """Print every figure: name, title, how it was made, its controls, and the pages that use it."""
    out = out or sys.stdout
    found = discover(cfg)
    if not found:
        print("No figures yet. Make one with: python -m bazinga figure new my_plot --from builder", file=out)
        return 0
    uses = _uses(cfg)
    rows = []
    for name, path in found.items():
        src = path.read_text(encoding="utf-8")
        how = {"builder": "form", "edited": "form, then code", "code": "code"}[made_with(src)]
        try:
            mod = load(name, cfg)
            title = mod.TITLE
            ctl = "%d control%s, %d preset%s" % (len(controls(mod)), "" if len(controls(mod)) == 1 else "s",
                                               len(presets(mod)), "" if len(presets(mod)) == 1 else "s")
        except FigureError as e:
            title, ctl = "(does not load: %s)" % str(e)[:60], ""
        rows.append((name, title, how, ctl, ", ".join(uses.get(name, [])) or "not used yet"))
    w0 = max(len(r[0]) for r in rows)
    w1 = min(42, max(len(r[1]) for r in rows))
    w2 = max(len(r[2]) for r in rows)
    for r in rows:
        title = r[1] if len(r[1]) <= w1 else r[1][:w1 - 1] + "…"
        print("%-*s  %-*s  %-*s  %s; %s" % (w0, r[0], w1, title, w2, r[2], r[3], r[4]), file=out)
    print("\n%d figure%s. Test them with: python -m bazinga figure test" % (len(rows), "" if len(rows) == 1 else "s"), file=out)
    return 0


def preview_page(name, cfg=None):
    """A standalone HTML page for one figure: the figure (interactive when the folder is served over http), the
    picture at every preset and on a phone, and the test results."""
    mod = load(name, cfg)
    report = test_report(name, cfg)
    fig = figure_html(name, cfg=cfg)
    parts = []
    for p in presets(mod):
        r = run(name, plot.coerce(controls(mod), p["values"]), 0, cfg)
        parts.append('<section><h3>Preset: %s</h3><div class="fig">%s%s</div></section>' % (
            html.escape(p["label"]), r["svg"], r["readouts_html"]))
    narrow = run(name, None, 1, cfg)
    checks = "".join('<li class="%s">%s%s</li>' % ("ok" if c["ok"] else "bad", html.escape(c["label"]),
                                                    ("<pre>%s</pre>" % html.escape(c["detail"])) if c["detail"] else "")
                     for c in report["checks"])
    return ("<!doctype html><html lang=en><head><meta charset=utf-8>"
            "<meta name=viewport content='width=device-width,initial-scale=1'>"
            "<meta name=bazinga-root content='./'><title>%s · figure preview</title>"
            "<link rel=stylesheet href='assets/css/tokens.css'><link rel=stylesheet href='assets/css/figure.css'>"
            "<style>body{margin:0 auto;max-width:1000px;padding:24px 16px 64px;font:16px/1.55 system-ui,sans-serif;"
            "background:var(--bg,#fcfcfa);color:var(--text,#1d1c1a)}h1{font-size:22px;margin:0 0 4px}"
            "h2{font-size:17px;margin:40px 0 12px}h3{font-size:14px;font-weight:600;margin:24px 0 8px}"
            ".muted{color:#777;font-size:14px}.checks{list-style:none;padding:0}.checks li{padding:4px 0}"
            ".checks li.ok::before{content:'✓ ';color:#1a7f37}.checks li.bad::before{content:'✗ ';color:#b3261e}"
            ".checks pre{white-space:pre-wrap;font-size:12px;background:#f4f3ef;padding:8px;border-radius:6px}"
            ".phone{max-width:390px}figure.fig{margin:0}</style></head><body>"
            "<h1>%s</h1><p class=muted>figures/%s.py. Moving the controls works when this folder is served over "
            "http; opened as a file, the figure stays at its starting values.</p>%s"
            "<h2>The test</h2><ul class=checks>%s</ul>"
            "%s<h2>On a phone</h2><div class='fig phone'>%s%s</div>"
            "<script src='assets/js/figure.js' defer></script></body></html>") % (
        html.escape(mod.TITLE), html.escape(mod.TITLE), html.escape(name), fig, checks,
        ("<h2>At each preset</h2>" + "".join(parts)) if parts else "", narrow["svg"], narrow["readouts_html"])


def cli_preview(name, cfg=None, out=None, dest=None):
    """Write a standalone preview of one figure (with the files it needs) and print where it is."""
    out = out or sys.stdout
    root = _root(cfg)
    dest = Path(dest) if dest else root / ".studio" / "figure-preview"
    page = preview_page(name, cfg)
    theme = Path(__file__).parent / "theme" / "assets"
    for rel in ("css/tokens.css", "css/figure.css", "js/figure.js", "js/pyworker.js"):
        src = (root / "theme" / "assets" / rel)
        src = src if src.is_file() else theme / rel
        if src.is_file():
            (dest / "assets" / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dest / "assets" / rel)
    write_assets(cfg, {name}, dest)
    path = dest / (name + ".html")
    path.write_text(page, encoding="utf-8")
    print(str(path), file=out)
    return path
