"""A small kit for diagrams (drawings/<module>.py). Standard library only; output is SVG.

    from tessera.draw import Diagram

    def overview():
        d = Diagram(720)
        a, b, c = d.row(["Write", "Check", "Build"], y=20)
        d.chain([a, b, c])
        return d.svg()

Coordinates are SVG units (the drawing scales to the column width). Styles are names
("main", "second", "third", "fourth", "muted", "highlight", "solid", "ghost", "dashed"),
combined with spaces ("main solid"); figure.css colours them for light and dark themes.
"""

import math

__all__ = ["Diagram", "Box", "DrawError"]

FS = 15          # main text size
FS_SUB = 12.5    # second line
LINE = 1.3       # line height factor


class DrawError(ValueError):
    pass


def _esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def _f(v):
    r = round(v, 1)
    if r == 0:
        return "0"
    s = "%.1f" % r
    return s[:-2] if s.endswith(".0") else s


def _cls(base, style):
    parts = [base]
    for s in str(style or "").split():
        s = "".join(ch for ch in s if ch.isalnum() or ch in "-_")
        if s:
            parts.append("s-" + s)
    return " ".join(parts)


def text_width(s, fs):
    w = 0.0
    for ch in str(s):
        if ch in "il.,:;'|!ijtfI()[] ":
            w += 0.32
        elif ch in "mwMW@%":
            w += 0.86
        elif ch.isupper() or ch.isdigit():
            w += 0.62
        else:
            w += 0.54
    return w * fs


def wrap(text, width, fs):
    """Greedy word wrap; explicit newlines are kept."""
    lines = []
    for para in str(text).split("\n"):
        cur = ""
        for word in para.split(" "):
            trial = (cur + " " + word).strip()
            if cur and text_width(trial, fs) > width:
                lines.append(cur)
                cur = word
            else:
                cur = trial
        lines.append(cur)
    return lines


class Box:
    """A placed box. x, y is the top-left corner; cx, cy the centre."""

    def __init__(self, x, y, w, h, text="", sub="", style="", round_=8):
        self.x, self.y, self.w, self.h = float(x), float(y), float(w), float(h)
        self.text, self.sub, self.style, self.round = text, sub, style, round_

    @property
    def cx(self):
        return self.x + self.w / 2

    @property
    def cy(self):
        return self.y + self.h / 2

    @property
    def right(self):
        return self.x + self.w

    @property
    def bottom(self):
        return self.y + self.h

    def anchor(self, side):
        """Point on an edge: 'top', 'bottom', 'left', 'right' or 'center'."""
        return {"top": (self.cx, self.y), "bottom": (self.cx, self.bottom), "left": (self.x, self.cy),
                "right": (self.right, self.cy), "center": (self.cx, self.cy)}[side]

    def edge_toward(self, px, py, gap=0.0):
        """Where the line from the centre toward (px, py) leaves the box (plus a small gap)."""
        dx, dy = px - self.cx, py - self.cy
        if dx == 0 and dy == 0:
            return self.cx, self.cy
        sx = (self.w / 2) / abs(dx) if dx else float("inf")
        sy = (self.h / 2) / abs(dy) if dy else float("inf")
        s = min(sx, sy)
        n = math.hypot(dx, dy)
        return self.cx + dx * s + dx / n * gap, self.cy + dy * s + dy / n * gap


def _point(p):
    if isinstance(p, Box):
        return p.cx, p.cy
    try:
        return float(p[0]), float(p[1])
    except (TypeError, IndexError, ValueError):
        raise DrawError("expected a Box or an (x, y) pair, got %r" % (p,))


class Diagram:
    """Collects boxes, arrows, labels and groups; svg() writes them out.

    width: the drawing's width in SVG units (720 matches the reading column).
    height: leave None to fit the content.
    title: the accessible name (screen readers); not drawn.
    """

    def __init__(self, width=720, height=None, title="Diagram"):
        self.width = float(width)
        self.height = height
        self.title = title
        self._groups = []
        self._boxes = []
        self._arrows = []
        self._labels = []
        self._extent = [0.0, 0.0, self.width, 0.0]

    # ------------------------------------------------------------------ elements

    def box(self, x, y, w=150, h=None, text="", style="", sub="", round=8):
        """A rounded box with a bold first line and an optional second line (sub).
        h=None fits the text."""
        if w <= 0:
            raise DrawError("box %r: width must be positive" % text)
        if h is None:
            n = len(wrap(text, w - 20, FS)) if text else 0
            m = len(wrap(sub, w - 20, FS_SUB)) if sub else 0
            h = max(44.0, n * FS * LINE + m * FS_SUB * LINE + 24)
        b = Box(x, y, w, h, text, sub, style, round)
        self._boxes.append(b)
        self._grow(b.x, b.y, b.right, b.bottom)
        return b

    def arrow(self, a, b, label="", style="", bend=0, start=None, end=None, both=False):
        """An arrow from a to b (Boxes or points). It leaves and enters at the box edges facing each
        other; start/end force a side ('top', 'bottom', 'left', 'right'). bend curves it (units,
        positive = to the left of the direction of travel)."""
        self._arrows.append((a, b, label, style, bend, start, end, both))
        return self

    def label(self, x, y, text, style="", anchor="middle", size=None):
        if anchor not in ("start", "middle", "end"):
            raise DrawError("label anchor must be start, middle or end")
        self._labels.append(("label", x, y, text, style, anchor, size or FS_SUB))
        w = text_width(text, size or FS_SUB)
        x0 = x - (w / 2 if anchor == "middle" else (w if anchor == "end" else 0))
        self._grow(x0, y - FS_SUB, x0 + w, y + 4)
        return self

    def note(self, text, x=None, y=None, anchor="middle"):
        """A quiet italic note; by default centred under everything drawn so far."""
        if y is None:
            y = self._extent[3] + 26
        if x is None:
            x = self.width / 2
        lines = wrap(text, self.width - 40, FS_SUB)
        for i, line in enumerate(lines):
            self._labels.append(("note", x, y + i * FS_SUB * LINE, line, "", anchor, FS_SUB))
        self._grow(0, y - FS_SUB, self.width, y + (len(lines) - 1) * FS_SUB * LINE + 4)
        return self

    def group(self, label, items, pad=16, style=""):
        """A dashed frame around items (Boxes) with a small caps label on top."""
        items = [i for i in items if isinstance(i, Box)]
        if not items:
            raise DrawError("group %r needs at least one Box" % label)
        x0 = min(i.x for i in items) - pad
        y0 = min(i.y for i in items) - pad - (FS_SUB + 6 if label else 0)
        x1 = max(i.right for i in items) + pad
        y1 = max(i.bottom for i in items) + pad
        g = Box(x0, y0, x1 - x0, y1 - y0, label, "", style, 12)
        self._groups.append(g)
        self._grow(x0, y0, x1, y1)
        return g

    # ------------------------------------------------------------------ layouts

    def _items(self, items):
        out = []
        for it in items:
            if isinstance(it, dict):
                out.append((it.get("text", ""), it.get("sub", ""), it.get("style")))
            elif isinstance(it, (tuple, list)):
                out.append((it[0], it[1] if len(it) > 1 else "", it[2] if len(it) > 2 else None))
            else:
                out.append((str(it), "", None))
        return out

    def row(self, items, y=0, x=None, w=None, h=None, gap=36, style="main"):
        """Boxes side by side. items: strings, (text, sub[, style]) or dicts. Centred when x is None;
        w=None shares the width evenly. Returns the Boxes."""
        items = self._items(items)
        n = len(items)
        if n == 0:
            return []
        if w is None:
            avail = self.width - 2 * 8 - gap * (n - 1)
            w = min(180.0, avail / n)
        total = n * w + (n - 1) * gap
        x0 = (self.width - total) / 2 if x is None else x
        if h is None:
            hs = []
            for t, sub, _ in items:
                nl = len(wrap(t, w - 20, FS)) if t else 0
                ml = len(wrap(sub, w - 20, FS_SUB)) if sub else 0
                hs.append(max(44.0, nl * FS * LINE + ml * FS_SUB * LINE + 24))
            h = max(hs)
        return [self.box(x0 + i * (w + gap), y, w, h, t, st or style, sub) for i, (t, sub, st) in enumerate(items)]

    def column(self, items, x=None, y=0, w=200, h=None, gap=28, style="main"):
        """Boxes stacked top to bottom (centred horizontally when x is None)."""
        items = self._items(items)
        x0 = (self.width - w) / 2 if x is None else x
        out = []
        cy = y
        for t, sub, st in items:
            b = self.box(x0, cy, w, h, t, st or style, sub)
            out.append(b)
            cy = b.bottom + gap
        return out

    def grid(self, items, cols, x=None, y=0, w=None, h=None, gap=24, style="main"):
        """Boxes in rows of `cols`, left to right then top to bottom."""
        items = self._items(items)
        if cols < 1:
            raise DrawError("grid needs cols >= 1")
        if w is None:
            w = min(180.0, (self.width - 16 - gap * (cols - 1)) / cols)
        total = cols * w + (cols - 1) * gap
        x0 = (self.width - total) / 2 if x is None else x
        if h is None:
            h = max(max(44.0, len(wrap(t, w - 20, FS)) * FS * LINE + (len(wrap(s, w - 20, FS_SUB)) * FS_SUB * LINE if s else 0) + 24)
                    for t, s, _ in items) if items else 44.0
        out = []
        for i, (t, sub, st) in enumerate(items):
            r, c = divmod(i, cols)
            out.append(self.box(x0 + c * (w + gap), y + r * (h + gap), w, h, t, st or style, sub))
        return out

    def chain(self, boxes, labels=None, style=""):
        """Arrows between consecutive boxes."""
        labels = labels or [""] * (len(boxes) - 1)
        for i in range(len(boxes) - 1):
            self.arrow(boxes[i], boxes[i + 1], labels[i] if i < len(labels) else "", style)
        return self

    # ------------------------------------------------------------------ output

    def _grow(self, x0, y0, x1, y1):
        e = self._extent
        e[0], e[1], e[2], e[3] = min(e[0], x0), min(e[1], y0), max(e[2], x1), max(e[3], y1)

    def _arrow_svg(self, a, b, label, style, bend, start, end, both):
        pa, pb = _point(a), _point(b)
        # end points on the facing edges
        if isinstance(a, Box):
            pa = a.anchor(start) if start else a.edge_toward(*(b.anchor(end) if (end and isinstance(b, Box)) else _point(b)), gap=4)
        if isinstance(b, Box):
            pb = b.anchor(end) if end else b.edge_toward(*pa, gap=4)
            if end:
                # step back from the edge so the head does not touch it
                pb = {"top": (pb[0], pb[1] - 4), "bottom": (pb[0], pb[1] + 4), "left": (pb[0] - 4, pb[1]),
                      "right": (pb[0] + 4, pb[1])}[end]
        if isinstance(a, Box) and start:
            pa = {"top": (pa[0], pa[1] - 4), "bottom": (pa[0], pa[1] + 4), "left": (pa[0] - 4, pa[1]),
                  "right": (pa[0] + 4, pa[1])}[start]
        # straighten nearly aligned arrows between boxes in a row or column
        if isinstance(a, Box) and isinstance(b, Box) and not bend and not start and not end:
            if abs(a.cy - b.cy) < 1 and (a.right < b.x or b.right < a.x):
                pa = (a.right + 4, a.cy) if a.cx < b.cx else (a.x - 4, a.cy)
                pb = (b.x - 4, b.cy) if a.cx < b.cx else (b.right + 4, b.cy)
            elif abs(a.cx - b.cx) < 1 and (a.bottom < b.y or b.bottom < a.y):
                pa = (a.cx, a.bottom + 4) if a.cy < b.cy else (a.cx, a.y - 4)
                pb = (b.cx, b.y - 4) if a.cy < b.cy else (b.cx, b.bottom + 4)
        (x0, y0), (x1, y1) = pa, pb
        dx, dy = x1 - x0, y1 - y0
        n = math.hypot(dx, dy) or 1.0
        size = 8.0
        out = []
        if bend:
            mx, my = (x0 + x1) / 2 - dy / n * bend, (y0 + y1) / 2 + dx / n * bend
            # head direction: tangent at the end of the quadratic curve
            tx, ty = x1 - mx, y1 - my
            tn = math.hypot(tx, ty) or 1.0
            ex, ey = x1 - tx / tn * size * 0.8, y1 - ty / tn * size * 0.8
            d = "M%s %sQ%s %s %s %s" % (_f(x0), _f(y0), _f(mx), _f(my), _f(ex), _f(ey))
            head_from = (mx, my)
            lx, ly = (x0 + 2 * mx + x1) / 4, (y0 + 2 * my + y1) / 4
        else:
            ex, ey = x1 - dx / n * size * 0.8, y1 - dy / n * size * 0.8
            sx, sy = (x0 + dx / n * size * 0.8, y0 + dy / n * size * 0.8) if both else (x0, y0)
            d = "M%s %sL%s %s" % (_f(sx), _f(sy), _f(ex), _f(ey))
            head_from = (x0, y0)
            lx, ly = (x0 + x1) / 2, (y0 + y1) / 2
        out.append('<path class="%s" d="%s"/>' % (_cls("dg-arrow", style), d))
        out.append(self._head(head_from, (x1, y1), size, style))
        if both:
            out.append(self._head((x1, y1) if not bend else (mx, my), (x0, y0), size, style))
        if label:
            w = text_width(label, FS_SUB) + 10
            horizontal = abs(dx) >= abs(dy)
            if horizontal and not bend:
                ty = ly - 8
                out.append('<text class="dg-arrow-label" x="%s" y="%s" font-size="%s" text-anchor="middle">%s</text>' % (
                    _f(lx), _f(ty), _f(FS_SUB), _esc(label)))
                self._grow(lx - w / 2, ty - FS_SUB, lx + w / 2, ty)
            else:
                out.append('<rect class="dg-arrow-label-bg" x="%s" y="%s" width="%s" height="%s" rx="4"/>' % (
                    _f(lx - w / 2), _f(ly - FS_SUB * 0.8), _f(w), _f(FS_SUB * 1.5)))
                out.append('<text class="dg-arrow-label" x="%s" y="%s" font-size="%s" text-anchor="middle">%s</text>' % (
                    _f(lx), _f(ly + FS_SUB * 0.35), _f(FS_SUB), _esc(label)))
                self._grow(lx - w / 2, ly - FS_SUB, lx + w / 2, ly + FS_SUB)
        self._grow(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
        return "".join(out)

    def _head(self, frm, to, size, style):
        (x0, y0), (x1, y1) = frm, to
        dx, dy = x1 - x0, y1 - y0
        n = math.hypot(dx, dy) or 1.0
        ux, uy = dx / n, dy / n
        bx, by = x1 - ux * size, y1 - uy * size
        w = size * 0.55
        pts = [(x1, y1), (bx - uy * w, by + ux * w), (bx + ux * size * 0.25, by + uy * size * 0.25), (bx + uy * w, by - ux * w)]
        return '<path class="%s" d="M%sZ"/>' % (_cls("dg-head", style), " L".join("%s %s" % (_f(a), _f(b)) for a, b in pts))

    def _box_svg(self, b):
        out = ['<rect class="%s" x="%s" y="%s" width="%s" height="%s" rx="%s"/>' % (
            _cls("dg-box", b.style), _f(b.x), _f(b.y), _f(b.w), _f(b.h), _f(b.round))]
        main = wrap(b.text, b.w - 20, FS) if b.text else []
        sub = wrap(b.sub, b.w - 20, FS_SUB) if b.sub else []
        total = len(main) * FS * LINE + len(sub) * FS_SUB * LINE
        y = b.cy - total / 2
        t = []
        for line in main:
            y += FS * LINE
            t.append('<text class="dg-text-main" x="%s" y="%s" font-size="%s" text-anchor="middle">%s</text>' % (
                _f(b.cx), _f(y - FS * (LINE - 1) - 2), _f(FS), _esc(line)))
        for line in sub:
            y += FS_SUB * LINE
            t.append('<text class="dg-text-sub" x="%s" y="%s" font-size="%s" text-anchor="middle">%s</text>' % (
                _f(b.cx), _f(y - FS_SUB * (LINE - 1) - 2), _f(FS_SUB), _esc(line)))
        out.append('<g class="%s">%s</g>' % (_cls("dg-text", b.style), "".join(t)))
        return "".join(out)

    def svg(self):
        body = []
        for g in self._groups:
            body.append('<rect class="%s" x="%s" y="%s" width="%s" height="%s" rx="12"/>' % (
                _cls("dg-group", g.style), _f(g.x), _f(g.y), _f(g.w), _f(g.h)))
            if g.text:
                body.append('<text class="dg-group-label" x="%s" y="%s" font-size="%s">%s</text>' % (
                    _f(g.x + 14), _f(g.y + FS_SUB + 8), _f(FS_SUB - 1), _esc(str(g.text).upper())))
        arrows = [self._arrow_svg(*a) for a in self._arrows]
        body.extend(arrows)
        body.extend(self._box_svg(b) for b in self._boxes)
        for kind, x, y, text, style, anchor, size in self._labels:
            body.append('<text class="%s" x="%s" y="%s" font-size="%s"%s>%s</text>' % (
                _cls("dg-note" if kind == "note" else "dg-label", style), _f(x), _f(y), _f(size),
                "" if anchor == "start" else ' text-anchor="%s"' % anchor, _esc(text)))
        x0, y0, x1, y1 = self._extent
        pad = 6
        x0, y0 = min(0.0, x0 - pad), min(0.0, y0 - pad)
        w = max(self.width, x1 + pad) - x0
        h = (self.height if self.height else y1 + pad) - y0
        return ('<svg xmlns="http://www.w3.org/2000/svg" class="dg" viewBox="%s %s %s %s" role="img">'
                '<title>%s</title>%s</svg>') % (_f(x0), _f(y0), _f(w), _f(h), _esc(self.title), "".join(body))
