"""``::drawing module.fn | caption`` -> a static SVG diagram from drawings/<module>.py."""

import html
import importlib.util
import re
import traceback
import xml.etree.ElementTree as ET
from pathlib import Path

__all__ = ["DrawingError", "drawing_html", "render", "discover"]

REF_RE = re.compile(r"^([a-z_][a-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)$")


class DrawingError(Exception):
    """A drawing that cannot be made. str(e) explains what to fix."""


def _drawings_dir(cfg=None):
    if cfg is not None and getattr(cfg, "drawings_dir", None):
        return Path(cfg.drawings_dir)
    try:
        from bazinga import config
        return Path(config.ROOT) / "drawings"
    except Exception:
        return Path.cwd() / "drawings"


def discover(cfg=None):
    """{module: [function names]} for drawings/*.py (public functions only)."""
    out = {}
    d = _drawings_dir(cfg)
    if not d.is_dir():
        return out
    for p in sorted(d.glob("*.py")):
        if p.name.startswith("_"):
            continue
        try:
            mod = _load(p.stem, cfg)
        except DrawingError:
            continue
        out[p.stem] = sorted(n for n, v in vars(mod).items()
                             if callable(v) and not n.startswith("_") and getattr(v, "__module__", "") == mod.__name__)
    return out


_cache = {}


def _load(module, cfg=None):
    p = _drawings_dir(cfg) / (module + ".py")
    if not p.is_file() and module.startswith("starter_"):   # ::drawing starter_<starter>.fn shows a starter as it is
        from bazinga.figures import STARTER_DIR, DRAWING_STARTERS
        if module[len("starter_"):] in DRAWING_STARTERS:
            p = STARTER_DIR / "drawings" / (module[len("starter_"):] + ".py")
    if not p.is_file():
        raise DrawingError("there is no drawings/%s.py. Create it from a starter: "
                           "python -m bazinga figure new %s --from pipeline" % (module, module))
    st = p.stat()
    key = str(p.resolve())
    hit = _cache.get(key)
    if hit and hit[0] == (st.st_mtime_ns, st.st_size):
        return hit[1]
    spec = importlib.util.spec_from_file_location("bazinga_drawing_" + module, p)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except SyntaxError as e:
        raise DrawingError("drawings/%s.py has a syntax error at line %s: %s" % (module, e.lineno, e.msg))
    except Exception as e:
        raise DrawingError("drawings/%s.py failed while importing: %s: %s%s" % (module, type(e).__name__, e, _line(e, p)))
    _cache[key] = ((st.st_mtime_ns, st.st_size), mod)
    return mod


def _line(e, path):
    line = None
    for fr in traceback.extract_tb(e.__traceback__):
        if Path(fr.filename).resolve() == Path(path).resolve():
            line = fr.lineno
    return (" (line %d)" % line) if line else ""


def _takes_narrow(f):
    import inspect
    try:
        return "narrow" in inspect.signature(f).parameters
    except (TypeError, ValueError):
        return False


def render(ref, cfg=None, narrow=None):
    """The SVG string for 'module.fn'. A function that has a `narrow` parameter is called with
    narrow=0 or 1 (1 = a phone layout, about 400 units wide); others are called without it."""
    m = REF_RE.match(str(ref or "").strip())
    if not m:
        raise DrawingError("%r is not a drawing reference; write ::drawing module.function, "
                           "for example ::drawing pipeline.overview" % (ref,))
    module, fn = m.groups()
    mod = _load(module, cfg)
    f = getattr(mod, fn, None)
    if f is None or not callable(f):
        names = [n for n, v in vars(mod).items() if callable(v) and not n.startswith("_")
                 and getattr(v, "__module__", "") == mod.__name__]
        import difflib
        close = difflib.get_close_matches(fn, names, n=1)
        raise DrawingError("drawings/%s.py has no function %s().%s" % (
            module, fn, (" Did you mean %s()?" % close[0]) if close else (" It has: " + ", ".join(sorted(names)) if names else "")))
    try:
        svg = f(narrow=1 if narrow else 0) if (narrow is not None and _takes_narrow(f)) else f()
    except Exception as e:
        raise DrawingError("drawings/%s.py: %s() raised %s: %s%s" % (module, fn, type(e).__name__, e, _line(e, mod.__file__)))
    if hasattr(svg, "svg") and callable(svg.svg):
        svg = svg.svg()  # a Diagram returned without .svg()
    if not isinstance(svg, str) or not svg.lstrip().startswith("<svg"):
        raise DrawingError("drawings/%s.py: %s() must return an SVG string (end it with `return d.svg()`)." % (module, fn))
    try:
        ET.fromstring(svg)
    except ET.ParseError as e:
        raise DrawingError("drawings/%s.py: %s() returned SVG that is not well-formed: %s" % (module, fn, e))
    return svg


def _fit(svg):
    """A drawing made with bazinga.draw is shown at its own size (never blown up to the column), like a ```diagram."""
    return " drawing-fit" if 'class="dg dg-fit"' in svg[:300] else ""


def _inline(text):
    """A caption's `code` and **bold**, everything else as plain text."""
    out = html.escape(text)
    out = re.sub(r"`([^`]+)`", r"<code>\1</code>", out)
    return re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", out)


def drawing_html(ref, caption="", cfg=None):
    """<figure class="drawing"> with the SVG and an optional caption."""
    m = REF_RE.match(str(ref or "").strip())
    mod = _load(m.group(1), cfg) if m else None
    f = getattr(mod, m.group(2), None) if m else None
    cap = ('<figcaption>%s</figcaption>' % _inline(caption.strip())) if caption and caption.strip() else ""
    if f is not None and callable(f) and _takes_narrow(f):
        wide, narrow = render(ref, cfg, narrow=0), render(ref, cfg, narrow=1)
        body = ('<div class="drawing-svg drawing-wide%s">%s</div><div class="drawing-svg drawing-narrow%s">%s</div>'
                % (_fit(wide), wide, _fit(narrow), narrow))
    else:
        svg = render(ref, cfg)
        body = '<div class="drawing-svg%s">%s</div>' % (_fit(svg), svg)
    return '<figure class="drawing" data-drawing="%s">%s%s</figure>' % (html.escape(str(ref).strip()), body, cap)
