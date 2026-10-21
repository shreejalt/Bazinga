"""Figure spec -> SVG.

This file runs in two places: at build time (the static SVG in the page) and in the reader's browser,
where the same code re-renders the figure each time a control moves. It therefore uses the standard
library only, and the same spec always gives the same bytes.

    svg, readouts_html = render(spec, narrow=0, title="")

The spec is documented in docs/DESIGN.md ("Interactive figures"). In short::

    {"panels": [{"kind": "xy" | "bars" | "heatmap" | "scene", ...}, ...],
     "readouts": [{"label", "value", "note"}], "note": "...", "height": 360}

Styles are names ("main", "second", "muted", "dashed", ...), never colours: every element gets CSS
classes and figure.css colours them, so figures follow the site's theme and dark mode.
"""

import math

__all__ = ["render", "PlotError", "STYLES", "nice_ticks", "coerce"]


class PlotError(ValueError):
    """A spec that cannot be drawn. The message says which panel and field."""


STYLES = ("main", "second", "third", "fourth", "muted", "faint", "highlight", "good", "bad",
          "dashed", "dotted", "area", "points", "thick", "thin", "label", "ink")

# Layout constants. Wide figures are drawn 880 units wide (shown at about 720-1000 px);
# narrow ones 480 wide (shown at about 330-480 px on phones, so their text is set larger).
LAYOUTS = {
    0: {"W": 880, "fs": 13.5, "fs_small": 12.5, "fs_title": 14.5, "gap": 44, "pad": 6,
        "h1": 380, "h2": 330, "h3": 300},
    1: {"W": 480, "fs": 15.5, "fs_small": 14, "fs_title": 16.5, "gap": 34, "pad": 4,
        "h1": 330, "h2": 300, "h3": 280},
}

MINUS = "−"


# ----------------------------------------------------------------------------------------------
# small helpers

def _esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def _f(v):
    """Format a coordinate: one decimal, no trailing zeros, no '-0'."""
    r = round(v, 1)
    if r == 0:
        return "0"
    s = "%.1f" % r
    if s.endswith(".0"):
        s = s[:-2]
    return s


def _num(v, where):
    """A finite float, or None for a gap. numpy scalars work too."""
    if v is None:
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        raise PlotError("%s: %r is not a number" % (where, v))
    if math.isnan(x) or math.isinf(x):
        return None
    return x


def _list(v, where):
    if v is None:
        return []
    if hasattr(v, "tolist"):
        v = v.tolist()
    if not isinstance(v, (list, tuple)):
        raise PlotError("%s must be a list" % where)
    return list(v)


def _nums(v, where):
    return [_num(x, where) for x in _list(v, where)]


def _classes(style, base):
    """'main dashed' -> 'base s-main s-dashed'. Unknown names are allowed (custom CSS)."""
    parts = [base]
    for s in str(style or "").replace(",", " ").split():
        s = "".join(ch for ch in s if ch.isalnum() or ch in "-_")
        if s:
            parts.append("s-" + s)
    return " ".join(parts)


MONO_EM = 0.6     # the advance of one character in a monospaced face (Courier, Plex Mono, JetBrains Mono …)


def text_width(s, fs):
    """Rendered width of s at font size fs, never less than it would be in a monospaced face.

    Themes set figure text in their own font (a UI sans, or a monospaced face as in the default theme). Room for
    labels is reserved from this estimate, so it errs wide: a proportional font then has a little spare room, and a
    monospaced one is never clipped or overlapping."""
    w = 0.0
    for ch in str(s):
        if ch in "mwMW@%":
            w += 0.86
        elif ch.isupper() or ch in "0123456789":
            w += 0.62
        else:
            w += MONO_EM
    return w * fs


def fmt_num(v, step=None):
    """Plain number text: 0.25, 1,200, 3.5k, 2e-05 -> 2·10⁻⁵ avoided; minus sign is U+2212."""
    if v is None:
        return ""
    if v == 0:
        return "0"
    a = abs(v)
    if step is not None and step > 0:
        dec = _decimals(step)
        if a >= 1e6:
            s = _compact(v)
        elif dec == 0:
            s = "{:,.0f}".format(v)
        else:
            s = ("%." + str(min(dec, 6)) + "f") % v
    elif a >= 1e6 or a < 1e-4:
        s = "%.3g" % v
    elif a >= 1000:
        s = "{:,.0f}".format(v)
    else:
        s = "%.3g" % v
    return s.replace("-", MINUS)


def _decimals(step):
    """Digits after the point needed to write multiples of step exactly (0.25 -> 2, 5 -> 0)."""
    s = ("%.10f" % abs(step)).rstrip("0")
    return len(s.split(".")[1]) if "." in s else 0


def _compact(v):
    for div, suf in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "k")):
        if abs(v) >= div:
            x = v / div
            s = ("%.1f" % x).rstrip("0").rstrip(".")
            return s + suf
    return "%g" % v


def nice_ticks(lo, hi, n=5):
    """Round tick values covering [lo, hi] (steps of 1, 2 or 5 x 10^k, count close to n+1)."""
    if hi < lo:
        lo, hi = hi, lo
    if hi - lo < 1e-12:
        d = abs(lo) * 0.1 or 1.0
        lo, hi = lo - d, hi + d
    raw = (hi - lo) / max(1, n)
    e = math.floor(math.log10(raw))
    best = None
    for k in (e - 1, e, e + 1):
        for m in (1, 2, 5):
            step = m * 10.0 ** k
            count = math.floor(hi / step + 1e-9) - math.ceil(lo / step - 1e-9) + 1
            if count < 2:
                continue
            score = (abs(count - (n + 1)), -step)
            if best is None or score < best[0]:
                best = (score, step)
    step = best[1] if best else raw
    first = math.ceil(lo / step - 1e-9) * step
    ticks = []
    t = first
    i = 0
    while t <= hi + step * 1e-9:
        ticks.append(round(t, 12))
        i += 1
        t = first + i * step
    return ticks, step


def _nice_range(lo, hi, n=5):
    """Expand [lo, hi] outward to tick multiples."""
    if hi - lo < 1e-12:
        d = abs(lo) * 0.1 or 1.0
        lo, hi = lo - d, hi + d
    _, step = nice_ticks(lo, hi, n)
    return math.floor(lo / step + 1e-9) * step, math.ceil(hi / step - 1e-9) * step


def coerce(controls, values):
    """Clamp and round control values exactly as the build does (so browser == build).

    Sliders whose min, max and step are whole numbers give ints; other sliders give floats rounded
    to the step; steps/toggle give the option index (int)."""
    out = {}
    for c in controls:
        name = c["name"]
        v = values.get(name, c.get("value"))
        kind = c.get("kind")
        if kind == "slider":
            lo, hi, step = float(c["min"]), float(c["max"]), float(c.get("step") or 0)
            try:
                v = float(v)
            except (TypeError, ValueError):
                v = float(c.get("value", lo))
            if math.isnan(v):
                v = float(c.get("value", lo))
            v = min(hi, max(lo, v))
            if step > 0:
                v = lo + round((v - lo) / step) * step
                v = min(hi, max(lo, v))
                dec = max(0, -int(math.floor(math.log10(step) + 1e-9))) + 1
                v = round(v, dec)
            if all(float(x).is_integer() for x in (c["min"], c["max"], c.get("step") or 1)):
                v = int(round(v))
        else:
            n = len(c.get("options") or [])
            try:
                v = int(v)
            except (TypeError, ValueError):
                v = int(c.get("value", 0))
            v = min(max(0, n - 1), max(0, v))
        out[name] = v
    return out


# ----------------------------------------------------------------------------------------------
# label placement

class _Boxes:
    """Occupied rectangles; place() picks the first candidate that overlaps nothing."""

    def __init__(self, bounds):
        self.items = []
        self.bounds = bounds  # (x0, y0, x1, y1)

    def add(self, b):
        self.items.append(b)

    def _overlap(self, b):
        tot = 0.0
        for o in self.items:
            dx = min(b[2], o[2]) - max(b[0], o[0])
            dy = min(b[3], o[3]) - max(b[1], o[1])
            if dx > 0 and dy > 0:
                tot += dx * dy
        x0, y0, x1, y1 = self.bounds
        out = (max(0, x0 - b[0]) + max(0, b[2] - x1)) * (b[3] - b[1]) + \
              (max(0, y0 - b[1]) + max(0, b[3] - y1)) * (b[2] - b[0])
        return tot + out * 4

    def place(self, cands):
        best, best_cost = None, None
        for i, b in enumerate(cands):
            cost = self._overlap(b)
            if cost == 0:
                self.add(b)
                return i
            if best_cost is None or cost < best_cost - 1e-9:
                best, best_cost = i, cost
        self.add(cands[best])
        return best


def _text(x, y, s, cls, fs, anchor="start", extra=""):
    a = "" if anchor == "start" else ' text-anchor="%s"' % anchor
    return '<text class="%s" x="%s" y="%s" font-size="%s"%s%s>%s</text>' % (
        cls, _f(x), _f(y), _f(fs), a, extra, _esc(s))


def _label_candidates(px, py, w, h, gap=7):
    """Boxes (x0,y0,x1,y1) around a point, in preference order, plus text anchor info."""
    return [
        ((px + gap, py - h - 2, px + gap + w, py - 2), "start", px + gap, py - 6),        # up-right
        ((px + gap, py + 2, px + gap + w, py + h + 2), "start", px + gap, py + h - 2),    # down-right
        ((px - gap - w, py - h - 2, px - gap, py - 2), "end", px - gap, py - 6),          # up-left
        ((px - gap - w, py + 2, px - gap, py + h + 2), "end", px - gap, py + h - 2),      # down-left
        ((px - w / 2, py - h - gap, px + w / 2, py - gap), "middle", px, py - gap - 4),   # above
        ((px - w / 2, py + gap, px + w / 2, py + gap + h), "middle", px, py + gap + h - 4),  # below
        ((px + gap, py - h / 2, px + gap + w, py + h / 2), "start", px + gap, py + h / 2 - 4),
        ((px - gap - w, py - h / 2, px - gap, py + h / 2), "end", px - gap, py + h / 2 - 4),
    ]


# ----------------------------------------------------------------------------------------------
# clipping (no clipPath ids, so two copies of a figure on one page never clash)

def _clip_seg(x0, y0, x1, y1, r):
    xmin, ymin, xmax, ymax = r
    dx, dy = x1 - x0, y1 - y0
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, x0 - xmin), (dx, xmax - x0), (-dy, y0 - ymin), (dy, ymax - y0)):
        if p == 0:
            if q < 0:
                return None
        else:
            t = q / p
            if p < 0:
                if t > t1:
                    return None
                t0 = max(t0, t)
            else:
                if t < t0:
                    return None
                t1 = min(t1, t)
    return (x0 + t0 * dx, y0 + t0 * dy, x0 + t1 * dx, y0 + t1 * dy)


def _polyline_path(pts, rect):
    """pts: list of (x, y) or None (gap) in pixels -> path d, clipped to rect."""
    d = []
    pen = None
    prev = None
    for p in pts:
        if p is None:
            prev = None
            pen = None
            continue
        if prev is None:
            prev = p
            if rect[0] <= p[0] <= rect[2] and rect[1] <= p[1] <= rect[3]:
                d.append("M%s %s" % (_f(p[0]), _f(p[1])))
                pen = p
            continue
        seg = _clip_seg(prev[0], prev[1], p[0], p[1], rect)
        if seg is not None:
            a = (seg[0], seg[1])
            b = (seg[2], seg[3])
            if pen is None or abs(pen[0] - a[0]) > 0.05 or abs(pen[1] - a[1]) > 0.05:
                d.append("M%s %s" % (_f(a[0]), _f(a[1])))
            d.append("L%s %s" % (_f(b[0]), _f(b[1])))
            pen = b
        else:
            pen = None
        prev = p
    # single isolated point with nothing else: draw nothing (points style handles dots)
    return "".join(d)


def _clip_poly(pts, r):
    """Sutherland-Hodgman polygon clip to rect r."""
    xmin, ymin, xmax, ymax = r
    edges = (
        (lambda p: p[0] >= xmin, lambda a, b: _ix(a, b, xmin, None)),
        (lambda p: p[0] <= xmax, lambda a, b: _ix(a, b, xmax, None)),
        (lambda p: p[1] >= ymin, lambda a, b: _ix(a, b, None, ymin)),
        (lambda p: p[1] <= ymax, lambda a, b: _ix(a, b, None, ymax)),
    )
    out = list(pts)
    for inside, inter in edges:
        if not out:
            break
        inp, out = out, []
        s = inp[-1]
        for e in inp:
            if inside(e):
                if not inside(s):
                    out.append(inter(s, e))
                out.append(e)
            elif inside(s):
                out.append(inter(s, e))
            s = e
    return out


def _ix(a, b, x=None, y=None):
    if x is not None:
        t = (x - a[0]) / ((b[0] - a[0]) or 1e-12)
        return (x, a[1] + t * (b[1] - a[1]))
    t = (y - a[1]) / ((b[1] - a[1]) or 1e-12)
    return (a[0] + t * (b[0] - a[0]), y)


def _poly_d(pts, close=True):
    if not pts:
        return ""
    s = "M" + " L".join("%s %s" % (_f(x), _f(y)) for x, y in pts)
    return s + ("Z" if close else "")


# ----------------------------------------------------------------------------------------------
# scales

class _Scale:
    def __init__(self, lo, hi, a, b, log=False):
        self.lo, self.hi, self.a, self.b, self.log = lo, hi, a, b, log
        if log:
            self._lo, self._hi = math.log10(lo), math.log10(hi)
        else:
            self._lo, self._hi = lo, hi
        if self._hi - self._lo == 0:
            self._hi = self._lo + 1

    def __call__(self, v):
        if v is None:
            return None
        if self.log:
            if v <= 0:
                return None
            v = math.log10(v)
        return self.a + (v - self._lo) / (self._hi - self._lo) * (self.b - self.a)

    def per_unit(self):
        return (self.b - self.a) / (self._hi - self._lo)


def _log_ticks(lo, hi):
    e0, e1 = math.floor(math.log10(lo) + 1e-9), math.ceil(math.log10(hi) - 1e-9)
    mults = (1,) if e1 - e0 > 3 else ((1, 2, 5) if e1 - e0 > 1 else (1, 2, 3, 5))
    every = 1 if e1 - e0 <= 6 else (2 if e1 - e0 <= 12 else 3)
    ticks = []
    for e in range(e0, e1 + 1):
        if (e - e0) % every:
            continue
        for m in mults:
            t = m * 10 ** e
            if lo * (1 - 1e-9) <= t <= hi * (1 + 1e-9):
                ticks.append(t)
    return ticks


def _fmt_log(t, wide=False):
    if not wide and 1e-3 <= t < 1e5:
        return fmt_num(t)
    e = int(round(math.log10(t)))
    if abs(t - 10 ** e) < 1e-9 * t:
        sup = str(e).translate(str.maketrans("-0123456789", "⁻⁰¹²³⁴⁵⁶⁷⁸⁹"))
        return "10" + sup
    return "%.0e" % t


def _explicit_ticks(v, where):
    out = []
    for t in _list(v, where):
        if isinstance(t, (list, tuple)) and len(t) == 2:
            out.append((_num(t[0], where), str(t[1])))
        else:
            x = _num(t, where)
            out.append((x, None))
    return [(x, l) for x, l in out if x is not None]


# ----------------------------------------------------------------------------------------------
# panels

class _Ctx:
    def __init__(self, narrow):
        self.narrow = narrow
        self.L = LAYOUTS[1 if narrow else 0]
        self.out = []
        self.force = (0, 0)     # minimum (top, bottom) so panels in a row line up
        self.metrics = None     # (top, bottom) the last panel wanted

    def add(self, s):
        self.out.append(s)


def _align(ctx, top, bottom):
    ctx.metrics = (top, bottom)
    return max(top, ctx.force[0]), max(bottom, ctx.force[1])


def _occupy_path(boxes, pts, step=10.0, r=3.0):
    """Mark a drawn polyline as occupied so labels avoid it."""
    prev = None
    for q in pts:
        if q is None:
            prev = None
            continue
        if prev is not None:
            d = math.hypot(q[0] - prev[0], q[1] - prev[1])
            n = max(1, int(d / step))
            for k in range(n):
                t = k / n
                x = prev[0] + (q[0] - prev[0]) * t
                y = prev[1] + (q[1] - prev[1]) * t
                boxes.add((x - r, y - r, x + r, y + r))
        prev = q
    if prev is not None:
        boxes.add((prev[0] - r, prev[1] - r, prev[0] + r, prev[1] + r))


def _panel_frame(ctx, p, x, y, w, h):
    """Title + y label above the plot; returns top offset used."""
    L = ctx.L
    top = 0
    title = p.get("title")
    if title:
        ctx.add(_text(x, y + L["fs_title"], title, "t-title", L["fs_title"]))
        top += L["fs_title"] + 10
    return top


def _xy_ranges(p, kind, where):
    xs, ys = [], []
    for i, s in enumerate(_list(p.get("series"), where + ".series")):
        if not isinstance(s, dict):
            raise PlotError("%s.series[%d] must be a dict with 'y'" % (where, i))
        sy = _nums(s.get("y"), "%s.series[%d].y" % (where, i))
        sx = _nums(s.get("x", p.get("x")), "%s.series[%d].x" % (where, i)) if (s.get("x") is not None or p.get("x") is not None) else list(range(len(sy)))
        if len(sx) != len(sy):
            raise PlotError("%s.series[%d]: x has %d values but y has %d" % (where, i, len(sx), len(sy)))
        xs.extend(v for v in sx if v is not None)
        ys.extend(v for v in sy if v is not None)
        base = s.get("base")
        if base is not None:
            if isinstance(base, (list, tuple)) or hasattr(base, "tolist"):
                ys.extend(v for v in _nums(base, where) if v is not None)
            else:
                b = _num(base, where)
                if b is not None:
                    ys.append(b)
    for sh in _list(p.get("shapes"), where + ".shapes"):
        for (sx, sy) in _shape_points(sh, where):
            xs.append(sx)
            ys.append(sy)
    for m in _list(p.get("marks"), where + ".marks"):
        if "x" in m and m["x"] is not None:
            xs.append(_num(m["x"], where))
        if "y" in m and m["y"] is not None:
            ys.append(_num(m["y"], where))
    for a in _list(p.get("annotations"), where + ".annotations"):
        if a.get("x") is not None and a.get("y") is not None:
            xs.append(_num(a["x"], where))
            ys.append(_num(a["y"], where))
    xs = [v for v in xs if v is not None]
    ys = [v for v in ys if v is not None]
    return xs, ys


def _shape_points(sh, where):
    t = sh.get("type")
    pts = []
    try:
        if t in ("point", "text", "circle"):
            x, y = _num(sh.get("x"), where), _num(sh.get("y"), where)
            if x is not None and y is not None:
                if t == "circle":
                    r = _num(sh.get("r", sh.get("rx", 0)), where) or 0
                    ry = _num(sh.get("ry", r), where) or 0
                    pts += [(x - r, y - ry), (x + r, y + ry)]
                else:
                    pts.append((x, y))
        elif t in ("line", "arrow"):
            if sh.get("points") is not None:
                for q in _list(sh["points"], where):
                    a, b = _num(q[0], where), _num(q[1], where)
                    if a is not None and b is not None:
                        pts.append((a, b))
            else:
                for k in (("x1", "y1"), ("x2", "y2")):
                    a, b = _num(sh.get(k[0]), where), _num(sh.get(k[1]), where)
                    if a is not None and b is not None:
                        pts.append((a, b))
        elif t == "polygon":
            for q in _list(sh.get("points"), where):
                a, b = _num(q[0], where), _num(q[1], where)
                if a is not None and b is not None:
                    pts.append((a, b))
        elif t == "rect":
            x, y = _num(sh.get("x"), where), _num(sh.get("y"), where)
            w, h = _num(sh.get("w", 0), where) or 0, _num(sh.get("h", 0), where) or 0
            if x is not None and y is not None:
                pts += [(x, y), (x + w, y + h)]
    except (TypeError, IndexError, KeyError):
        raise PlotError("%s: a %s shape has malformed coordinates" % (where, t))
    return pts


def _panel_xy(ctx, p, X, Y, W, H, where, scene=False):
    L = ctx.L
    fs, fss = L["fs"], L["fs_small"]
    axes = p.get("axes", not scene)
    equal = p.get("equal", scene)
    xs, ys = _xy_ranges(p, "scene" if scene else "xy", where)
    x_log, y_log = bool(p.get("x_log")), bool(p.get("y_log"))
    if x_log:
        xs = [v for v in xs if v > 0]
    if y_log:
        ys = [v for v in ys if v > 0]

    top = _panel_frame(ctx, p, X, Y, W, H)
    y_label = p.get("y_label")
    if y_label and axes:
        ctx.add(_text(X, Y + top + fss, y_label, "t-axis-label", fss))
        top += fss + 8

    # data ranges
    def rng(vals, lo_key, hi_key, log, pad_frac, nice=True):
        lo = _num(p.get(lo_key), where + "." + lo_key)
        hi = _num(p.get(hi_key), where + "." + hi_key)
        if vals:
            dlo, dhi = min(vals), max(vals)
        else:
            dlo, dhi = (1.0, 10.0) if log else (0.0, 1.0)
        auto_lo, auto_hi = lo is None, hi is None
        lo = dlo if lo is None else lo
        hi = dhi if hi is None else hi
        if log:
            lo = max(lo, 1e-12)
            hi = max(hi, lo * 10 if hi <= lo else hi)
            if auto_lo:
                lo = 10 ** math.floor(math.log10(lo) + 1e-9)
            if auto_hi:
                hi = 10 ** math.ceil(math.log10(hi) - 1e-9)
            if hi <= lo:
                hi = lo * 10
        else:
            if hi - lo < 1e-12:
                d = abs(lo) * 0.1 or 1.0
                lo, hi = (lo - d if auto_lo else lo), (hi + d if auto_hi else hi)
                if hi <= lo:
                    hi = lo + 1
            if pad_frac:
                span = hi - lo
                if auto_lo:
                    lo -= span * pad_frac
                if auto_hi:
                    hi += span * pad_frac
            elif (auto_lo or auto_hi) and nice:
                nlo, nhi = _nice_range(lo, hi)
                lo = nlo if auto_lo else lo
                hi = nhi if auto_hi else hi
        return lo, hi, auto_lo, auto_hi

    pad = 0.06 if scene else 0
    # x follows the data exactly (a line should reach both edges); y is rounded out to ticks
    xlo, xhi, _, _ = rng(xs, "x_min", "x_max", x_log, pad, nice=False)
    ylo, yhi, _, _ = rng(ys, "y_min", "y_max", y_log, pad, nice=p.get("y_ticks") is None)

    # tick labels decide the margins
    if x_log:
        wide_ = xhi / xlo > 1e5
        xt = [(t, _fmt_log(t, wide_)) for t in _log_ticks(xlo, xhi)]
    elif p.get("x_ticks") is not None:
        xt = [(t, l if l is not None else fmt_num(t)) for t, l in _explicit_ticks(p["x_ticks"], where + ".x_ticks")]
    else:
        ticks, st = nice_ticks(xlo, xhi, 4 if ctx.narrow else 6)
        xt = [(t, fmt_num(t, st)) for t in ticks if xlo - 1e-9 <= t <= xhi + 1e-9]
    if y_log:
        wide_ = yhi / ylo > 1e5
        yt = [(t, _fmt_log(t, wide_)) for t in _log_ticks(ylo, yhi)]
    elif p.get("y_ticks") is not None:
        yt = [(t, l if l is not None else fmt_num(t)) for t, l in _explicit_ticks(p["y_ticks"], where + ".y_ticks")]
    else:
        ticks, st = nice_ticks(ylo, yhi, 4 if ctx.narrow else 5)
        yt = [(t, fmt_num(t, st)) for t in ticks if ylo - 1e-9 <= t <= yhi + 1e-9]

    left = (max([text_width(l, fss) for _, l in yt] + [0]) + 10) if axes else 4
    bottom = (fss + 10 + ((fss + 10) if p.get("x_label") else 0)) if axes else 4
    top, bottom = _align(ctx, top, bottom)

    # end labels need room on the right
    series = _list(p.get("series"), where + ".series")
    end_labels = [s for s in series if s.get("name") and s.get("label_at", "end") == "end"
                  and not ({"points", "stems"} & set(str(s.get("style", "")).split()))]
    right = 8
    if end_labels:
        right = min(W * 0.32, max(text_width(s["name"], fss) for s in end_labels) + 16)
    if axes and xt:
        right = max(right, text_width(xt[-1][1], fss) / 2 + 2)

    px0, py0 = X + left, Y + top + 4
    px1, py1 = X + W - right, Y + H - bottom
    if equal:
        # same units per pixel on both axes: widen the tighter range (centred)
        pw, ph = px1 - px0, py1 - py0
        sx, sy = (xhi - xlo) / pw, (yhi - ylo) / ph
        if sx > sy:
            c, half = (ylo + yhi) / 2, sx * ph / 2
            if p.get("y_min") is None and p.get("y_max") is None:
                ylo, yhi = c - half, c + half
            else:
                # y is fixed: use less height, centred
                # y is fixed: use less height, keeping the x axis where it is (lines up with neighbours)
                nh = (yhi - ylo) / sx
                py0 = py1 - nh
        else:
            c, half = (xlo + xhi) / 2, sy * pw / 2
            if p.get("x_min") is None and p.get("x_max") is None:
                xlo, xhi = c - half, c + half
            else:
                nw = (xhi - xlo) / sy
                px0 += (pw - nw) / 2
                px1 = px0 + nw
        if not x_log and p.get("x_ticks") is None:
            ticks, st = nice_ticks(xlo, xhi, 4 if ctx.narrow else 6)
            xt = [(t, fmt_num(t, st)) for t in ticks if xlo - 1e-9 <= t <= xhi + 1e-9]
        if not y_log and p.get("y_ticks") is None:
            ticks, st = nice_ticks(ylo, yhi, 4 if ctx.narrow else 5)
            yt = [(t, fmt_num(t, st)) for t in ticks if ylo - 1e-9 <= t <= yhi + 1e-9]

    sx = _Scale(xlo, xhi, px0, px1, x_log)
    sy = _Scale(ylo, yhi, py1, py0, y_log)
    rect = (px0, py0, px1, py1)
    boxes = _Boxes((X, Y, X + W, Y + H))

    # grid + axes. "grid": True (or "x" / "y") adds grid lines at the ticks in both (or one) directions, also in
    # scenes without axes; "origin": True draws the lines x = 0 and y = 0 when they are in view.
    g = []
    grid = p.get("grid")
    if grid:
        gx = grid in (True, "x", "both")
        gy = grid in (True, "y", "both") and not axes     # with axes the y grid is already there
        if gx:
            for t, _l in xt:
                xx = sx(t)
                if xx is not None and px0 + 0.5 < xx < px1 - 0.5:
                    g.append('<path class="grid" d="M%s %sV%s"/>' % (_f(xx), _f(py0), _f(py1)))
        if gy:
            for t, _l in yt:
                yy = sy(t)
                if yy is not None and py0 + 0.5 < yy < py1 - 0.5:
                    g.append('<path class="grid" d="M%s %sH%s"/>' % (_f(px0), _f(yy), _f(px1)))
    if p.get("origin"):
        if not x_log and xlo < 0 < xhi:
            g.append('<path class="axis zero" d="M%s %sV%s"/>' % (_f(sx(0)), _f(py0), _f(py1)))
        if not y_log and ylo < 0 < yhi and not axes:
            g.append('<path class="axis zero" d="M%s %sH%s"/>' % (_f(px0), _f(sy(0)), _f(px1)))
    if axes:
        for t, l in yt:
            yy = sy(t)
            if yy is None:
                continue
            g.append('<path class="grid" d="M%s %sH%s"/>' % (_f(px0), _f(yy), _f(px1)))
            g.append(_text(px0 - 8, yy + fss * 0.35, l, "t-tick", fss, "end"))
        for t, l in xt:
            xx = sx(t)
            if xx is None:
                continue
            g.append('<path class="tick" d="M%s %sv5"/>' % (_f(xx), _f(py1)))
            g.append(_text(xx, py1 + fss + 7, l, "t-tick", fss, "middle"))
        # baseline: y=0 when visible, else the bottom
        y0 = sy(0) if (not y_log and ylo < 0 < yhi) else None
        g.append('<path class="axis" d="M%s %sH%s"/>' % (_f(px0), _f(py1), _f(px1)))
        if y0 is not None:
            g.append('<path class="axis zero" d="M%s %sH%s"/>' % (_f(px0), _f(y0), _f(px1)))
        if p.get("x_label"):
            g.append(_text((px0 + px1) / 2, py1 + 2 * fss + 18, p["x_label"], "t-axis-label", fss, "middle"))
    ctx.add('<g class="axes">%s</g>' % "".join(g))
    for t, l in yt:
        yy = sy(t)
        if yy is not None and axes:
            boxes.add((px0 - 8 - text_width(l, fss), yy - fss * 0.6, px0 - 8, yy + fss * 0.4))

    # reference marks (lines now, labels after the data so they avoid it)
    mark_labels = []
    for i, m in enumerate(_list(p.get("marks"), where + ".marks")):
        lab = m.get("label", "")
        cls = _classes(m.get("style", "muted"), "mark")
        if m.get("x") is not None:
            xx = sx(_num(m["x"], where))
            if xx is not None and px0 - 0.5 <= xx <= px1 + 0.5:
                ctx.add('<path class="%s" d="M%s %sV%s"/>' % (cls, _f(xx), _f(py0), _f(py1)))
                if lab:
                    w = text_width(lab, fss)
                    cands = [((xx + 5, py0, xx + 5 + w, py0 + fss + 2), "start", xx + 5, py0 + fss),
                             ((xx - 5 - w, py0, xx - 5, py0 + fss + 2), "end", xx - 5, py0 + fss),
                             ((xx + 5, py1 - fss - 6, xx + 5 + w, py1 - 4), "start", xx + 5, py1 - 7),
                             ((xx - 5 - w, py1 - fss - 6, xx - 5, py1 - 4), "end", xx - 5, py1 - 7),
                             ((xx + 5, (py0 + py1) / 2 - fss / 2, xx + 5 + w, (py0 + py1) / 2 + fss / 2), "start", xx + 5, (py0 + py1) / 2 + fss * 0.35)]
                    mark_labels.append((cands, lab))
        elif m.get("y") is not None:
            yy = sy(_num(m["y"], where))
            if yy is not None and py0 - 0.5 <= yy <= py1 + 0.5:
                ctx.add('<path class="%s" d="M%s %sH%s"/>' % (cls, _f(px0), _f(yy), _f(px1)))
                if lab:
                    w = text_width(lab, fss)
                    mx = (px0 + px1) / 2
                    cands = [((px1 - w, yy - fss - 4, px1, yy - 3), "end", px1, yy - 6),
                             ((px1 - w, yy + 3, px1, yy + fss + 4), "end", px1, yy + fss + 1),
                             ((px0 + 4, yy - fss - 4, px0 + 4 + w, yy - 3), "start", px0 + 4, yy - 6),
                             ((px0 + 4, yy + 3, px0 + 4 + w, yy + fss + 4), "start", px0 + 4, yy + fss + 1),
                             ((mx - w / 2, yy - fss - 4, mx + w / 2, yy - 3), "middle", mx, yy - 6),
                             ((mx - w / 2, yy + 3, mx + w / 2, yy + fss + 4), "middle", mx, yy + fss + 1)]
                    mark_labels.append((cands, lab))

    # series
    ends = []
    dots = []
    point_labels = []
    for i, s in enumerate(series):
        w_ = "%s.series[%d]" % (where, i)
        y = _nums(s.get("y"), w_ + ".y")
        x = _nums(s.get("x", p.get("x")), w_ + ".x") if (s.get("x") is not None or p.get("x") is not None) else list(range(len(y)))
        style = str(s.get("style", "main" if i == 0 else ("second", "third", "fourth", "muted")[min(i - 1, 3)]))
        names = style.split()
        pts = []
        for a, b in zip(x, y):
            pa, pb = sx(a), sy(b)
            pts.append(None if pa is None or pb is None else (pa, pb))
        title = s.get("name", "")
        if "area" in names:
            base = s.get("base", 0 if not y_log else ylo)
            if isinstance(base, (list, tuple)) or hasattr(base, "tolist"):
                bl = _nums(base, w_ + ".base")
            else:
                bl = [_num(base, w_ + ".base")] * len(y)
            # contiguous runs only
            run_t, run_b = [], []
            runs = []
            for a, b, c in zip(x, y, bl):
                pa, pb, pc = sx(a), sy(b), sy(c if c is not None else (ylo if y_log else 0))
                if pa is None or pb is None or pc is None:
                    if run_t:
                        runs.append((run_t, run_b))
                    run_t, run_b = [], []
                    continue
                pc = min(max(pc, py0), py1)
                run_t.append((pa, pb))
                run_b.append((pa, pc))
            if run_t:
                runs.append((run_t, run_b))
            for rt, rb in runs:
                poly = _clip_poly(rt + rb[::-1], rect)
                if poly:
                    ctx.add('<path class="%s" d="%s"/>' % (_classes(style, "fill"), _poly_d(poly)))
        if "points" in names or "stems" in names:
            # dots (a scatter); "sizes" gives each dot its own radius in pixels, "labels" a text beside it;
            # "stems" also draws a line from the baseline up to each dot (a probability mass function, say)
            sizes = None
            if s.get("sizes") is not None:
                sizes = _nums(s["sizes"], w_ + ".sizes")
                if len(sizes) != len(y):
                    raise PlotError("%s: sizes has %d values but y has %d" % (w_, len(sizes), len(y)))
            plabels = None
            if s.get("labels") is not None:
                plabels = [("" if v is None else str(v)) for v in _list(s["labels"], w_ + ".labels")]
                if len(plabels) != len(y):
                    raise PlotError("%s: labels has %d values but y has %d" % (w_, len(plabels), len(y)))
            r0 = 4.5 if not ctx.narrow else 5
            if "stems" in names:
                b0 = sy(ylo if y_log else min(max(0.0, ylo), yhi))
                stems = []
                for q in pts:
                    if q and px0 - 0.5 <= q[0] <= px1 + 0.5:
                        top_ = min(max(q[1], py0), py1)
                        stems.append("M%s %sV%s" % (_f(q[0]), _f(b0), _f(top_)))
                if stems:
                    ctx.add('<path class="%s" d="%s"/>' % (_classes(style, "stem"), "".join(stems)))
            for k, q in enumerate(pts):
                if q and px0 - 1 <= q[0] <= px1 + 1 and py0 - 1 <= q[1] <= py1 + 1:
                    r = r0 if sizes is None or sizes[k] is None else max(1.0, min(40.0, sizes[k]))
                    dots.append('<circle class="%s" cx="%s" cy="%s" r="%s"/>' % (
                        _classes(style, "dot"), _f(q[0]), _f(q[1]), _f(r)))
                    boxes.add((q[0] - r, q[1] - r, q[0] + r, q[1] + r))
                    if plabels and plabels[k]:
                        point_labels.append((q, plabels[k], r))
        else:
            d = _polyline_path(pts, rect)
            if d:
                ctx.add('<path class="%s" d="%s"><title>%s</title></path>' % (_classes(style, "line"), d, _esc(title)))
                stride = max(1, len(pts) // 120)
                vis = [q if (q and rect[0] - 1 <= q[0] <= rect[2] + 1 and rect[1] - 1 <= q[1] <= rect[3] + 1) else None
                       for q in pts[::stride] + pts[-1:]]
                _occupy_path(boxes, vis, step=14.0, r=2.5)
        last = None
        for q in reversed(pts):
            if q and px0 - 0.5 <= q[0] <= px1 + 0.5 and py0 - 0.5 <= q[1] <= py1 + 0.5:
                last = q
                break
        if last and title and s.get("label_at", "end") == "end" and not ({"points", "stems"} & set(names)):
            ends.append((last, title, style))
            dots.append('<circle class="%s" cx="%s" cy="%s" r="%s"/>' % (
                _classes(style, "end-dot"), _f(last[0]), _f(last[1]), "3.5"))

    shapes_svg = _shapes(ctx, p, sx, sy, rect, boxes, where)
    ctx.add(shapes_svg)
    ctx.add("".join(dots))
    for cands, lab in mark_labels:
        k = boxes.place([c[0] for c in cands])
        ctx.add(_text(cands[k][2], cands[k][3], lab, "t-mark", fss, cands[k][1]))

    # end labels: sort by y, spread so they don't overlap, leader lines when moved
    early = [e for e in ends if e[0][0] < px1 - 2]
    ends = [e for e in ends if e[0][0] >= px1 - 2]
    for (q, name, style) in early:
        w = text_width(name, fss)
        cands = _label_candidates(q[0], q[1], w, fss + 2)
        k = boxes.place([c[0] for c in cands])
        _, anchor, tx, ty = cands[k]
        ctx.add('<g class="%s">%s</g>' % (_classes(style, "end-label"), _text(tx, ty, name, "t-label", fss, anchor)))
    if ends:
        h = fss + 3
        ends.sort(key=lambda e: e[0][1])
        ys_ = [e[0][1] for e in ends]
        lo_b, hi_b = py0 + h / 2, py1 - h / 2 + fss
        placed = list(ys_)
        for _ in range(60):
            moved = False
            for k in range(1, len(placed)):
                if placed[k] - placed[k - 1] < h:
                    mid = (placed[k] + placed[k - 1]) / 2
                    placed[k - 1], placed[k] = mid - h / 2, mid + h / 2
                    moved = True
            for k in range(len(placed)):
                placed[k] = min(max(placed[k], lo_b - fss), hi_b)
            if not moved:
                break
        lx = px1 + 10
        for (q, name, style), ly in zip(ends, placed):
            if abs(ly - q[1]) > 2:
                ctx.add('<path class="leader" d="M%s %sL%s %s"/>' % (_f(q[0] + 4), _f(q[1]), _f(lx - 3), _f(ly)))
            ctx.add('<g class="%s">%s</g>' % (_classes(style, "end-label"),
                                             _text(lx, ly + fss * 0.35, name, "t-label", fss)))

    # labels beside dots (series "labels")
    for q, txt, r in point_labels:
        w = text_width(txt, fss)
        cands = _label_candidates(q[0], q[1], w, fss + 2, gap=r + 4)
        k = boxes.place([c[0] for c in cands])
        _, anchor, tx, ty = cands[k]
        ctx.add(_text(tx, ty, txt, "t-label", fss, anchor))

    # annotations
    for i, a in enumerate(_list(p.get("annotations"), where + ".annotations")):
        ax, ay = sx(_num(a.get("x"), where)), sy(_num(a.get("y"), where))
        if ax is None or ay is None:
            continue
        txt = str(a.get("text", ""))
        w = text_width(txt, fss)
        cands = _label_candidates(ax, ay, w, fss + 2)
        k = boxes.place([c[0] for c in cands])
        _, anchor, tx, ty = cands[k]
        ctx.add('<circle class="anno-dot" cx="%s" cy="%s" r="3"/>' % (_f(ax), _f(ay)))
        ctx.add(_text(tx, ty, txt, "t-anno", fss, anchor))


def _inside(pts, r):
    return all(r[0] - 0.01 <= x <= r[2] + 0.01 and r[1] - 0.01 <= y <= r[3] + 0.01 for x, y in pts)


def _poly_svg(pts, rect, style):
    """A filled, outlined polygon (pixels). When it is cut by the plot edge, the fill is clipped as an
    area and the outline as a line, so no outline is drawn along the plot's border."""
    if len(pts) < 3:
        return ""
    if _inside(pts, rect):
        return '<path class="%s" d="%s"/>' % (_classes(style, "poly"), _poly_d(pts))
    out = []
    fill = _clip_poly(pts, rect)
    if fill:
        out.append('<path class="%s" d="%s"/>' % (_classes(style, "poly no-edge"), _poly_d(fill)))
    edge = _polyline_path(list(pts) + [pts[0]], rect)
    if edge:
        out.append('<path class="%s" d="%s"/>' % (_classes(style, "poly-edge"), edge))
    return "".join(out)


def _arrow_head(x0, y0, x1, y1, size):
    dx, dy = x1 - x0, y1 - y0
    n = math.hypot(dx, dy) or 1
    ux, uy = dx / n, dy / n
    bx, by = x1 - ux * size, y1 - uy * size
    w = size * 0.5
    return [(x1, y1), (bx - uy * w, by + ux * w), (bx + uy * w, by - ux * w)]


def _shapes(ctx, p, sx, sy, rect, boxes, where):
    L = ctx.L
    fss = L["fs_small"]
    out = []
    labels = []
    for i, sh in enumerate(_list(p.get("shapes"), where + ".shapes")):
        w_ = "%s.shapes[%d]" % (where, i)
        if not isinstance(sh, dict):
            raise PlotError(w_ + " must be a dict")
        t = sh.get("type")
        style = sh.get("style", "main")
        lab = sh.get("label", "")
        if t == "point":
            x, y = sx(_num(sh.get("x"), w_)), sy(_num(sh.get("y"), w_))
            if x is None or y is None:
                continue
            if not (rect[0] - 1 <= x <= rect[2] + 1 and rect[1] - 1 <= y <= rect[3] + 1):
                continue
            r = _num(sh.get("r", 5), w_) or 5
            out.append('<circle class="%s" cx="%s" cy="%s" r="%s"/>' % (_classes(style, "dot"), _f(x), _f(y), _f(r)))
            boxes.add((x - r, y - r, x + r, y + r))
            if lab:
                labels.append((x, y, str(lab), r))
        elif t in ("line", "arrow"):
            if sh.get("points") is not None:
                raw = [(_num(q[0], w_), _num(q[1], w_)) for q in _list(sh["points"], w_)]
            else:
                raw = [(_num(sh.get("x1"), w_), _num(sh.get("y1"), w_)),
                       (_num(sh.get("x2"), w_), _num(sh.get("y2"), w_))]
            pts = [None if a is None or b is None or sx(a) is None or sy(b) is None else (sx(a), sy(b)) for a, b in raw]
            d = _polyline_path(pts, rect)
            if d:
                out.append('<path class="%s" d="%s"/>' % (_classes(style, "line"), d))
                _occupy_path(boxes, [q if (q and rect[0] <= q[0] <= rect[2] and rect[1] <= q[1] <= rect[3]) else None for q in pts])
            if t == "arrow":
                good = [q for q in pts if q]
                if len(good) >= 2:
                    (x0, y0), (x1, y1) = good[-2], good[-1]
                    if rect[0] - 1 <= x1 <= rect[2] + 1 and rect[1] - 1 <= y1 <= rect[3] + 1 and math.hypot(x1 - x0, y1 - y0) > 1:
                        size = 9 if not ctx.narrow else 10
                        out.append('<path class="%s" d="%s"/>' % (_classes(style, "head"), _poly_d(_arrow_head(x0, y0, x1, y1, size))))
            if lab:
                good = [q for q in pts if q]
                if good and t == "arrow" and len(good) >= 2:
                    # an arrow is named at its head, just past the tip, so arrows from one point keep their names apart
                    (x0, y0), (x1, y1) = good[-2], good[-1]
                    n = math.hypot(x1 - x0, y1 - y0) or 1.0
                    labels.append((x1 + 6 * (x1 - x0) / n, y1 + 6 * (y1 - y0) / n, str(lab), 2))
                elif good:
                    q = good[len(good) // 2] if len(good) > 2 else ((good[0][0] + good[-1][0]) / 2, (good[0][1] + good[-1][1]) / 2)
                    labels.append((q[0], q[1], str(lab), 2))
        elif t == "polygon":
            raw = [(sx(_num(q[0], w_)), sy(_num(q[1], w_))) for q in _list(sh.get("points"), w_)]
            raw = [q for q in raw if q[0] is not None and q[1] is not None]
            poly = _clip_poly(raw, rect) if len(raw) >= 3 else []
            if poly:
                out.append(_poly_svg(raw, rect, style))
                if lab:
                    cx = sum(q[0] for q in poly) / len(poly)
                    cy = sum(q[1] for q in poly) / len(poly)
                    out.append(_text(cx, cy + fss * 0.35, lab, "t-label", fss, "middle"))
                    w = text_width(lab, fss)
                    boxes.add((cx - w / 2, cy - fss / 2, cx + w / 2, cy + fss / 2))
        elif t == "circle":
            cx, cy = sx(_num(sh.get("x"), w_)), sy(_num(sh.get("y"), w_))
            if cx is None or cy is None:
                continue
            r = _num(sh.get("r", sh.get("rx")), w_)
            ry = _num(sh.get("ry", r), w_)
            if r is None or r < 0 or ry is None or ry < 0:
                raise PlotError(w_ + ": a circle needs a radius r >= 0")
            rx_px = abs(r * sx.per_unit()) if not sx.log else r
            ry_px = abs(ry * sy.per_unit()) if not sy.log else ry
            if cx + rx_px < rect[0] or cx - rx_px > rect[2] or cy + ry_px < rect[1] or cy - ry_px > rect[3]:
                continue
            if not _inside([(cx - rx_px, cy - ry_px), (cx + rx_px, cy + ry_px)], rect):
                k = 96
                ring = [(cx + rx_px * math.cos(2 * math.pi * i / k), cy + ry_px * math.sin(2 * math.pi * i / k)) for i in range(k)]
                out.append(_poly_svg(ring, rect, style))
            elif abs(rx_px - ry_px) < 0.05:
                out.append('<circle class="%s" cx="%s" cy="%s" r="%s"/>' % (_classes(style, "poly"), _f(cx), _f(cy), _f(rx_px)))
            else:
                out.append('<ellipse class="%s" cx="%s" cy="%s" rx="%s" ry="%s"/>' % (
                    _classes(style, "poly"), _f(cx), _f(cy), _f(rx_px), _f(ry_px)))
            if lab:
                labels.append((cx + rx_px * 0.7071, cy - ry_px * 0.7071, str(lab), 2))
        elif t == "rect":
            x, y = _num(sh.get("x"), w_), _num(sh.get("y"), w_)
            w, h = _num(sh.get("w"), w_), _num(sh.get("h"), w_)
            if None in (x, y, w, h):
                raise PlotError(w_ + ": a rect needs x, y, w, h")
            a, b = sx(x), sy(y)
            c, d = sx(x + w), sy(y + h)
            if None in (a, b, c, d):
                continue
            out.append(_poly_svg([(a, b), (c, b), (c, d), (a, d)], rect, style))
            if lab:
                labels.append((min(a, c), min(b, d), str(lab), 0))
        elif t == "text":
            x, y = sx(_num(sh.get("x"), w_)), sy(_num(sh.get("y"), w_))
            if x is None or y is None:
                continue
            txt = str(sh.get("text", lab))
            anchor = sh.get("anchor", "middle")
            if anchor not in ("start", "middle", "end"):
                raise PlotError(w_ + ": anchor must be start, middle or end")
            w = text_width(txt, fss)
            x0 = x if anchor == "start" else (x - w / 2 if anchor == "middle" else x - w)
            boxes.add((x0, y - fss * 0.65, x0 + w, y + fss * 0.35))
            out.append('<g class="%s">%s</g>' % (_classes(style, "shape-text"), _text(x, y + fss * 0.35, txt, "t-label", fss, anchor)))
        else:
            raise PlotError("%s: unknown shape type %r (use point, line, arrow, polygon, circle, rect or text)" % (w_, t))
    for (x, y, txt, r) in labels:
        w = text_width(txt, fss)
        cands = _label_candidates(x, y, w, fss + 2, gap=r + 5)
        k = boxes.place([c[0] for c in cands])
        _, anchor, tx, ty = cands[k]
        out.append(_text(tx, ty, txt, "t-label", fss, anchor))
    return "".join(out)


def _panel_bars(ctx, p, X, Y, W, H, where):
    L = ctx.L
    fs, fss = L["fs"], L["fs_small"]
    bars = _list(p.get("bars"), where + ".bars")
    for i, b in enumerate(bars):
        if not isinstance(b, dict) or "value" not in b:
            raise PlotError("%s.bars[%d] must be a dict with 'label' and 'value'" % (where, i))
    vals = [_num(b["value"], "%s.bars[%d].value" % (where, i)) for i, b in enumerate(bars)]
    horiz = bool(p.get("horizontal", False))
    top = _panel_frame(ctx, p, X, Y, W, H)
    val_label = p.get("y_label") if not horiz else p.get("x_label")
    cat_label = p.get("x_label") if not horiz else p.get("y_label")
    if val_label and not horiz:
        ctx.add(_text(X, Y + top + fss, val_label, "t-axis-label", fss))
        top += fss + 8

    finite = [v for v in vals if v is not None]
    lo_k, hi_k = ("x_min", "x_max") if horiz else ("y_min", "y_max")
    lo = _num(p.get(lo_k), where)
    hi = _num(p.get(hi_k), where)
    if p.get("range") is not None:
        r = _list(p["range"], where + ".range")
        lo, hi = _num(r[0], where), _num(r[1], where)
    dlo = min(finite + [0.0])
    dhi = max(finite + [0.0])
    auto_lo, auto_hi = lo is None, hi is None
    if lo is None or hi is None:
        nlo, nhi = _nice_range(dlo, dhi if dhi > dlo else dlo + 1)
        lo = nlo if lo is None else lo
        hi = nhi if hi is None else hi
    if hi <= lo:
        hi = lo + 1
    ticks, st = nice_ticks(lo, hi, 4 if ctx.narrow else 5)
    ticks = [t for t in ticks if lo - 1e-9 <= t <= hi + 1e-9]
    labels = [str(b.get("label", "")) for b in bars]
    notes = [str(b.get("note", "")) if b.get("note") is not None else "" for b in bars]
    n = max(1, len(bars))
    boxes = []
    out = []

    if horiz:
        lab_w = min(W * 0.4, max([text_width(l, fs) for l in labels] + [0]) + 12)
        note_w = max([text_width(t, fss) for t in notes] + [0]) + 10
        bottom = fss + 12 + ((fss + 10) if val_label else 0)
        top, bottom = _align(ctx, top, bottom)
        px0, px1 = X + lab_w, X + W - max(note_w, 14)
        py0, py1 = Y + top + 2, Y + H - bottom
        s = _Scale(lo, hi, px0, px1)
        band = (py1 - py0) / n
        th = min(band * 0.68, 34 if not ctx.narrow else 36)
        for t in ticks:
            xx = s(t)
            out.append('<path class="grid" d="M%s %sV%s"/>' % (_f(xx), _f(py0), _f(py1)))
            out.append(_text(xx, py1 + fss + 8, fmt_num(t, st), "t-tick", fss, "middle"))
        if val_label:
            out.append(_text((px0 + px1) / 2, py1 + 2 * fss + 18, val_label, "t-axis-label", fss, "middle"))
        z = s(min(max(0, lo), hi))
        for i, (b, v) in enumerate(zip(bars, vals)):
            cy = py0 + band * (i + 0.5)
            lab = labels[i]
            while len(lab) > 3 and text_width(lab, fs) > lab_w - 10:
                lab = lab[:-2] + "…"
            out.append(_text(px0 - 10, cy + fs * 0.35, lab, "t-cat", fs, "end"))
            if v is None:
                continue
            xv = min(max(s(v), px0), px1)
            a, c = min(z, xv), max(z, xv)
            out.append(_bar_path(a, cy - th / 2, c - a, th, "right" if v >= 0 else "left",
                                 _classes(b.get("style", "main"), "bar"), "%s: %s" % (labels[i], notes[i] or fmt_num(v))))
            if notes[i]:
                if v >= 0:
                    out.append(_text(c + 6, cy + fss * 0.35, notes[i], "t-note", fss, "start"))
                else:
                    out.append(_text(a - 6, cy + fss * 0.35, notes[i], "t-note", fss, "end"))
        out.append('<path class="axis" d="M%s %sV%s"/>' % (_f(z), _f(py0), _f(py1)))
    else:
        tick_w = max([text_width(fmt_num(t, st), fss) for t in ticks] + [0]) + 10
        px0, px1 = X + tick_w, X + W - 6
        band = (px1 - px0) / n
        cat_fs = fs if n <= 12 else fss
        widest = max([text_width(l, cat_fs) for l in labels] + [0])
        rotate = widest > band * 0.95
        cat_h = (min(widest, 120) * 0.62 + cat_fs + 8) if rotate else (cat_fs + 12)
        bottom = cat_h + ((fs + 12) if cat_label else 0)
        has_notes = any(notes)
        top += (fss + 8) if has_notes else 4
        top, bottom = _align(ctx, top, bottom)
        py0 = Y + top
        py1 = Y + H - bottom
        s = _Scale(lo, hi, py1, py0)
        tw = min(band * 0.64, 64 if not ctx.narrow else 56)
        for t in ticks:
            yy = s(t)
            out.append('<path class="grid" d="M%s %sH%s"/>' % (_f(px0), _f(yy), _f(px1)))
            out.append(_text(px0 - 8, yy + fss * 0.35, fmt_num(t, st), "t-tick", fss, "end"))
        z = s(min(max(0, lo), hi))
        for i, (b, v) in enumerate(zip(bars, vals)):
            cx = px0 + band * (i + 0.5)
            lab = labels[i]
            if rotate:
                if len(lab) > 18:
                    lab = lab[:17] + "…"
                out.append('<text class="t-cat" x="%s" y="%s" font-size="%s" text-anchor="end" transform="rotate(-38 %s %s)">%s</text>' % (
                    _f(cx + 4), _f(py1 + cat_fs + 4), _f(cat_fs), _f(cx + 4), _f(py1 + cat_fs + 4), _esc(lab)))
            else:
                out.append(_text(cx, py1 + cat_fs + 8, lab, "t-cat", cat_fs, "middle"))
            if v is None:
                continue
            yv = min(max(s(v), py0), py1)
            a, c = min(z, yv), max(z, yv)
            out.append(_bar_path(cx - tw / 2, a, tw, c - a, "up" if v >= 0 else "down",
                                 _classes(b.get("style", "main"), "bar"), "%s: %s" % (labels[i], notes[i] or fmt_num(v))))
            if notes[i]:
                if v >= 0:
                    out.append(_text(cx, a - 7, notes[i], "t-note", fss, "middle"))
                else:
                    out.append(_text(cx, c + fss + 4, notes[i], "t-note", fss, "middle"))
        out.append('<path class="axis" d="M%s %sH%s"/>' % (_f(px0), _f(z), _f(px1)))
        if cat_label:
            out.append(_text((px0 + px1) / 2, Y + H - 4, cat_label, "t-axis-label", fs, "middle"))

    for i, m in enumerate(_list(p.get("marks"), where + ".marks")):
        v = _num(m.get("y" if not horiz else "x", m.get("value")), where + ".marks")
        if v is None:
            continue
        cls = _classes(m.get("style", "muted"), "mark")
        lab = str(m.get("label", ""))
        if horiz:
            xx = s(v)
            if px0 - 0.5 <= xx <= px1 + 0.5:
                out.append('<path class="%s" d="M%s %sV%s"/>' % (cls, _f(xx), _f(py0 - 4), _f(py1)))
                if lab:
                    out.append(_text(xx + 4, py0 + fss - 2, lab, "t-mark", fss))
        else:
            yy = s(v)
            if py0 - 0.5 <= yy <= py1 + 0.5:
                out.append('<path class="%s" d="M%s %sH%s"/>' % (cls, _f(px0), _f(yy), _f(px1)))
                if lab:
                    out.append(_text(px1, yy - 5, lab, "t-mark", fss, "end"))
    ctx.add("".join(out))


def _bar_path(x, y, w, h, grow, cls, title):
    """A bar with 3px rounded corners at its data end, square at the baseline."""
    r = max(0.0, min(3.0, w / 2, h / 2))
    if w <= 0.05 or h <= 0.05:
        return '<path class="%s" d="M%s %sh%sv%sz"><title>%s</title></path>' % (cls, _f(x), _f(y), _f(max(w, 0.5)), _f(max(h, 0.5)), _esc(title))
    x1, y1 = x + w, y + h
    if grow == "up":
        d = "M%s %sV%sQ%s %s %s %sH%sQ%s %s %s %sV%sZ" % (
            _f(x), _f(y1), _f(y + r), _f(x), _f(y), _f(x + r), _f(y), _f(x1 - r), _f(x1), _f(y), _f(x1), _f(y + r), _f(y1))
    elif grow == "down":
        d = "M%s %sV%sQ%s %s %s %sH%sQ%s %s %s %sV%sZ" % (
            _f(x), _f(y), _f(y1 - r), _f(x), _f(y1), _f(x + r), _f(y1), _f(x1 - r), _f(x1), _f(y1), _f(x1), _f(y1 - r), _f(y))
    elif grow == "right":
        d = "M%s %sH%sQ%s %s %s %sV%sQ%s %s %s %sH%sZ" % (
            _f(x), _f(y), _f(x1 - r), _f(x1), _f(y), _f(x1), _f(y + r), _f(y1 - r), _f(x1), _f(y1), _f(x1 - r), _f(y1), _f(x))
    else:
        d = "M%s %sH%sQ%s %s %s %sV%sQ%s %s %s %sH%sZ" % (
            _f(x1), _f(y), _f(x + r), _f(x), _f(y), _f(x), _f(y + r), _f(y1 - r), _f(x), _f(y1), _f(x + r), _f(y1), _f(x1))
    return '<path class="%s" d="%s"><title>%s</title></path>' % (cls, d, _esc(title))


def _panel_heatmap(ctx, p, X, Y, W, H, where):
    L = ctx.L
    fs, fss = L["fs"], L["fs_small"]
    rows = _list(p.get("matrix"), where + ".matrix")
    if not rows:
        raise PlotError(where + ": a heatmap needs a non-empty 'matrix' (a list of rows)")
    M = [_nums(r, "%s.matrix[%d]" % (where, i)) for i, r in enumerate(rows)]
    nc = len(M[0])
    for i, r in enumerate(M):
        if len(r) != nc:
            raise PlotError("%s.matrix: row %d has %d values but row 0 has %d" % (where, i, len(r), nc))
    nr = len(M)
    rl = [str(v) for v in _list(p.get("row_labels"), where + ".row_labels")]
    cl = [str(v) for v in _list(p.get("col_labels"), where + ".col_labels")]
    if rl and len(rl) != nr:
        raise PlotError("%s: %d row_labels for %d rows" % (where, len(rl), nr))
    if cl and len(cl) != nc:
        raise PlotError("%s: %d col_labels for %d columns" % (where, len(cl), nc))
    finite = [v for r in M for v in r if v is not None]
    if p.get("range") is not None:
        rr = _list(p["range"], where + ".range")
        lo, hi = _num(rr[0], where + ".range"), _num(rr[1], where + ".range")
    else:
        lo, hi = (min(finite), max(finite)) if finite else (0.0, 1.0)
    if hi <= lo:
        hi = lo + 1
    diverging = p.get("diverging")
    if diverging is None:
        diverging = lo < 0 < hi
    top = _panel_frame(ctx, p, X, Y, W, H)
    lab_fs = fs if max(nr, nc) <= 12 else fss
    left = (max([text_width(v, lab_fs) for v in rl] + [0]) + 10) if rl else 2
    legend_w = 0 if ctx.narrow else 70
    legend_h = (fss + 26) if ctx.narrow else 0
    widest_col = max([text_width(v, lab_fs) for v in cl] + [0])
    avail_w = W - left - legend_w - 4
    cell_w = avail_w / nc
    rot_cols = bool(cl) and widest_col > cell_w * 0.92
    colh = 0
    if cl:
        colh = (min(widest_col, 110) * 0.7 + lab_fs + 6) if rot_cols else lab_fs + 10
    xl = p.get("x_label")
    avail_h = H - top - colh - legend_h - ((fs + 10) if xl else 0) - 4
    cell = min(cell_w, avail_h / nr)
    if p.get("square", True) is False:
        cw, ch = cell_w, avail_h / nr
    else:
        cw = ch = cell
    # centre the grid (and the legend beside it) in the panel
    gx0 = X + left + max(0.0, (avail_w - nc * cw) / 2)
    gy0 = Y + top + 2
    out = []
    show = bool(p.get("show_values"))
    mag = max(abs(lo), abs(hi)) or 1.0
    val_dec = int(p.get("decimals", max(0, min(4, 2 - math.floor(math.log10(mag))))))
    val_fs = min(fs, ch * 0.42, cw * 0.32) if show else 0
    hl = set()
    for q in _list(p.get("highlight"), where + ".highlight"):
        hl.add((int(q[0]), int(q[1])))
    gap = 2 if min(cw, ch) > 10 else (1 if min(cw, ch) > 4 else 0)
    for i in range(nr):
        for j in range(nc):
            v = M[i][j]
            x, y = gx0 + j * cw, gy0 + i * ch
            tip = "%s%s%s" % ((rl[i] + ", ") if rl else "", (cl[j] + ": ") if cl else "", fmt_num(v) if v is not None else "missing")
            if v is None:
                out.append('<rect class="cell missing" x="%s" y="%s" width="%s" height="%s"><title>%s</title></rect>' % (
                    _f(x + gap / 2), _f(y + gap / 2), _f(max(0.5, cw - gap)), _f(max(0.5, ch - gap)), _esc(tip)))
                continue
            fill, t = _cell_fill(v, lo, hi, diverging)
            out.append('<rect class="cell" x="%s" y="%s" width="%s" height="%s" rx="%s" style="fill:%s"><title>%s</title></rect>' % (
                _f(x + gap / 2), _f(y + gap / 2), _f(max(0.5, cw - gap)), _f(max(0.5, ch - gap)), "2" if gap > 1 else "0", fill, _esc(tip)))
            if show and val_fs >= 7:
                cls = "t-cell hi" if t > 0.55 else "t-cell"
                out.append(_text(x + cw / 2, y + ch / 2 + val_fs * 0.36, ("%." + str(val_dec) + "f") % v, cls, val_fs, "middle"))
    for (i, j) in sorted(hl):
        if 0 <= i < nr and 0 <= j < nc:
            out.append('<rect class="cell-hl" x="%s" y="%s" width="%s" height="%s" rx="3"/>' % (
                _f(gx0 + j * cw + 0.5), _f(gy0 + i * ch + 0.5), _f(cw - 1), _f(ch - 1)))
    for i, v in enumerate(rl):
        out.append(_text(gx0 - 8, gy0 + (i + 0.5) * ch + lab_fs * 0.35, v, "t-cat", lab_fs, "end"))
    gy1 = gy0 + nr * ch
    for j, v in enumerate(cl):
        cx = gx0 + (j + 0.5) * cw
        if rot_cols:
            vv = v if len(v) <= 16 else v[:15] + "…"
            out.append('<text class="t-cat" x="%s" y="%s" font-size="%s" text-anchor="end" transform="rotate(-40 %s %s)">%s</text>' % (
                _f(cx + 3), _f(gy1 + lab_fs + 2), _f(lab_fs), _f(cx + 3), _f(gy1 + lab_fs + 2), _esc(vv)))
        else:
            out.append(_text(cx, gy1 + lab_fs + 6, v, "t-cat", lab_fs, "middle"))
    if xl:
        out.append(_text(gx0 + nc * cw / 2, gy1 + colh + fs + 4, xl, "t-axis-label", fs, "middle"))
    if p.get("y_label"):
        pass  # rows already carry labels; y_label is shown in the legend title below
    # legend: a stepped bar
    steps = 24
    legend_title = p.get("legend", p.get("y_label", ""))
    if not ctx.narrow:
        lx = gx0 + nc * cw + 22
        lh = min(nr * ch, 220)
        ly0 = gy0
        if legend_title:
            out.append(_text(lx - 4, ly0 + fss, legend_title, "t-axis-label", fss))
            ly0 += fss + 8
            lh = min(lh, nr * ch - fss - 8) if nr * ch > 80 else lh
        for k in range(steps):
            v = hi - (hi - lo) * (k + 0.5) / steps
            fill, _ = _cell_fill(v, lo, hi, diverging)
            out.append('<rect x="%s" y="%s" width="12" height="%s" style="fill:%s"/>' % (
                _f(lx), _f(ly0 + lh * k / steps), _f(lh / steps + 0.4), fill))
        out.append(_text(lx + 17, ly0 + fss * 0.8, fmt_num(_round_sig(hi)), "t-tick", fss))
        out.append(_text(lx + 17, ly0 + lh, fmt_num(_round_sig(lo)), "t-tick", fss))
        if diverging and lo < 0 < hi:
            yz = ly0 + lh * (hi / (hi - lo))
            out.append(_text(lx + 17, yz + fss * 0.35, "0", "t-tick", fss))
    else:
        lw = min(W - left - 70, 240)
        lx = gx0
        ly = Y + H - legend_h + 6
        for k in range(steps):
            v = lo + (hi - lo) * (k + 0.5) / steps
            fill, _ = _cell_fill(v, lo, hi, diverging)
            out.append('<rect x="%s" y="%s" width="%s" height="10" style="fill:%s"/>' % (
                _f(lx + lw * k / steps), _f(ly), _f(lw / steps + 0.4), fill))
        out.append(_text(lx, ly + 12 + fss, fmt_num(_round_sig(lo)), "t-tick", fss))
        out.append(_text(lx + lw, ly + 12 + fss, fmt_num(_round_sig(hi)), "t-tick", fss, "end"))
        if legend_title:
            out.append(_text(lx + lw + 10, ly + 10, legend_title, "t-axis-label", fss))
    ctx.add("".join(out))


def _round_sig(v, n=3):
    if v == 0 or v is None:
        return v
    return round(v, -int(math.floor(math.log10(abs(v)))) + (n - 1))


def _cell_fill(v, lo, hi, diverging):
    """Colour as a CSS color-mix of theme variables, in 2% steps (keeps output short and stable)."""
    if diverging:
        m = max(abs(lo), abs(hi)) or 1
        t = max(-1.0, min(1.0, v / m))
        pct = int(round(abs(t) * 50)) * 2
        if pct == 0:
            return "var(--fig-div-mid)", 0.0
        pole = "var(--fig-div-pos)" if t > 0 else "var(--fig-div-neg)"
        return "color-mix(in oklab,%s %d%%,var(--fig-div-mid))" % (pole, pct), abs(t)
    t = max(0.0, min(1.0, (v - lo) / (hi - lo)))
    pct = int(round(t * 50)) * 2
    return "color-mix(in oklab,var(--fig-seq-hi) %d%%,var(--fig-seq-lo))" % pct, t


# ----------------------------------------------------------------------------------------------
# top level

def _readouts(spec):
    ro = _list(spec.get("readouts"), "readouts")
    parts = []
    if ro:
        items = []
        for i, r in enumerate(ro):
            if not isinstance(r, dict) or "label" not in r:
                raise PlotError("readouts[%d] must be a dict with 'label' and 'value'" % i)
            v = r.get("value", "")
            if isinstance(v, float):
                v = ("%.4g" % v).replace("-", MINUS) if not (math.isnan(v) or math.isinf(v)) else "\u2014"
            note = r.get("note")
            items.append('<div class="fig-readout%s"><span class="fig-readout-label">%s</span>'
                         '<span class="fig-readout-value">%s</span>%s</div>' % (
                             (" " + _classes(r["style"], "")[1:].strip()) if r.get("style") else "",
                             _esc(r["label"]), _esc(v),
                             ('<span class="fig-readout-note">%s</span>' % _esc(note)) if note else ""))
        parts.append('<div class="fig-readouts">%s</div>' % "".join(items))
    if spec.get("note"):
        parts.append('<p class="fig-note">%s</p>' % _esc(spec["note"]))
    return "".join(parts)


def _legend(ctx, items, X, Y, W):
    """A row of swatch + name, wrapping; returns height used."""
    fss = ctx.L["fs_small"]
    x, y = X, Y
    out = []
    for name, style, kind in items:
        w = text_width(name, fss) + 30
        if x + w > X + W and x > X:
            x = X
            y += fss + 10
        if kind == "line":
            out.append('<path class="%s" d="M%s %sh18"/>' % (_classes(style, "line key"), _f(x), _f(y + fss * 0.5)))
        else:
            out.append('<rect class="%s" x="%s" y="%s" width="12" height="12" rx="2"/>' % (
                _classes(style, "bar key"), _f(x + 3), _f(y + fss * 0.5 - 6)))
        out.append(_text(x + 24, y + fss * 0.85, name, "t-legend", fss))
        x += w + 8
    ctx.add("".join(out))
    return y - Y + fss + 12


def render(spec, narrow=0, title=None):
    """Render a figure spec to (svg, readouts_html). Same spec -> same bytes."""
    if not isinstance(spec, dict):
        raise PlotError("compute() must return a dict like {'panels': [...]}, got %s" % type(spec).__name__)
    panels = _list(spec.get("panels"), "panels")
    if not panels:
        raise PlotError("the spec has no panels: return {'panels': [{'kind': 'xy', ...}]}")
    if len(panels) > 4:
        raise PlotError("at most 4 panels per figure (got %d)" % len(panels))
    narrow = 1 if narrow else 0
    ctx = _Ctx(narrow)
    L = ctx.L
    W = L["W"]
    n = len(panels)
    for i, p in enumerate(panels):
        if not isinstance(p, dict):
            raise PlotError("panels[%d] must be a dict" % i)
        k = p.get("kind", "xy")
        if k not in ("xy", "bars", "heatmap", "scene"):
            raise PlotError("panels[%d]: unknown kind %r (use xy, bars, heatmap or scene)" % (i, k))

    # legend (optional): spec["legend"] = [{"name", "style", "kind": "line"|"box"}]
    y = 0
    leg = _list(spec.get("legend"), "legend")
    if leg:
        items = [(str(l.get("name", "")), l.get("style", "main"), l.get("kind", "line")) for l in leg]
        y += _legend(ctx, items, 0, 2, W)

    default_h = spec.get("height")
    if narrow:
        # column of panels
        for i, p in enumerate(panels):
            h = _panel_height(p, W, default_h, L["h1"], narrow)
            _draw_panel(ctx, p, 0, y, W, h, "panels[%d]" % i)
            y += h + (L["gap"] if i < n - 1 else 0)
        H = y
    else:
        if n > 1:
            # measure each panel once, then draw them all with the same top and bottom margins
            tops, bottoms = [], []
            widths_ = _list(spec.get("widths"), "widths") if spec.get("widths") else [1] * n
            if len(widths_) == n:
                tot_ = float(sum(widths_))
                avail_ = W - L["gap"] * (n - 1)
                for i, p in enumerate(panels):
                    if p.get("kind", "xy") in ("xy", "bars"):
                        m = _Ctx(narrow)
                        _draw_panel(m, p, 0, 0, avail_ * widths_[i] / tot_, 400, "panels[%d]" % i)
                        if m.metrics:
                            tops.append(m.metrics[0])
                            bottoms.append(m.metrics[1])
            ctx.force = (max(tops + [0]), max(bottoms + [0]))
        widths = _list(spec.get("widths"), "widths") if spec.get("widths") else [1] * n
        if len(widths) != n:
            raise PlotError("widths has %d entries for %d panels" % (len(widths), n))
        tot = float(sum(widths))
        avail = W - L["gap"] * (n - 1)
        base_h = L["h1"] if n == 1 else (L["h2"] if n == 2 else L["h3"])
        hs = [_panel_height(p, avail * widths[i] / tot, default_h, base_h, narrow) for i, p in enumerate(panels)]
        h = max(hs)
        x = 0.0
        for i, p in enumerate(panels):
            w = avail * widths[i] / tot
            _draw_panel(ctx, p, x, y, w, h, "panels[%d]" % i)
            x += w + L["gap"]
        H = y + h
    H = int(math.ceil(H + L["pad"]))
    label = title if title else (spec.get("title") or " / ".join(str(p.get("title", "")) for p in panels if p.get("title")) or "Figure")
    desc = spec.get("description")
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" class="fig-plot%s" viewBox="0 0 %d %d" role="img">'
           '<title>%s</title>%s%s</svg>') % (
        " narrow" if narrow else "", W, H, _esc(label),
        ("<desc>%s</desc>" % _esc(desc)) if desc else "", "".join(ctx.out))
    return svg, _readouts(spec)


def _panel_height(p, w, default_h, base_h, narrow):
    h = p.get("height") or default_h
    if h:
        h = float(h)
        return h * (0.9 if narrow else 1.0)
    if p.get("kind") == "scene" and p.get("equal", True):
        # follow the data's aspect when it is known, within reason
        try:
            xs, ys = _xy_ranges(p, "scene", "panel")
            lo_x = p.get("x_min", min(xs) if xs else 0)
            hi_x = p.get("x_max", max(xs) if xs else 1)
            lo_y = p.get("y_min", min(ys) if ys else 0)
            hi_y = p.get("y_max", max(ys) if ys else 1)
            ar = (float(hi_y) - float(lo_y)) / max(1e-9, float(hi_x) - float(lo_x))
            title_h = 30 if p.get("title") else 0
            return max(220.0, min(w * ar + title_h + 10, 560.0 if not narrow else 520.0))
        except (PlotError, TypeError, ValueError):
            return base_h
    if p.get("kind") == "heatmap":
        rows = len(_list(p.get("matrix"), "matrix")) or 1
        cols = len(_list(p.get("matrix"), "matrix")[0]) if rows else 1
        cell = (w - 120) / max(1, cols)
        return max(200.0, min(rows * cell + 80, 560.0))
    if p.get("kind") == "bars" and p.get("horizontal"):
        nb = len(_list(p.get("bars"), "bars"))
        return max(base_h * 0.6, min(nb * (40 if narrow else 36) + 60, 600))
    return float(base_h)


def _draw_panel(ctx, p, x, y, w, h, where):
    k = p.get("kind", "xy")
    ctx.add('<g class="panel panel-%s">' % k)
    if k == "xy":
        _panel_xy(ctx, p, x, y, w, h, where)
    elif k == "scene":
        _panel_xy(ctx, p, x, y, w, h, where, scene=True)
    elif k == "bars":
        _panel_bars(ctx, p, x, y, w, h, where)
    else:
        _panel_heatmap(ctx, p, x, y, w, h, where)
    ctx.add("</g>")
