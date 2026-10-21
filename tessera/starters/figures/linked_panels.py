"""Starter: two panels that move together (a curve and its slope).

Copy it with  python -m tessera figure new my_pair --from linked_panels  and put  ::figure my_pair  in a post.

What it shows
-------------
On the left a function with the tangent line at a point; on the right the function's slope, with
the same point marked. Moving the point moves both, which is the idea: the right panel is a picture
of how steep the left one is.

Things worth copying
--------------------
- **Several panels** in one figure: "panels" is a list, and "widths" sets how wide each one is.
  On a phone they are stacked.
- **One control drives every panel,** so the reader sees the link.
- **Choosing a function with "steps":** FUNCTIONS is a list; add your own (a name, f and its slope).
"""

import math

TITLE = "A curve and its slope"
CAPTION = "Move the point: the tangent on the left has the slope shown on the right."
REQUIRES = []

# (name shown on the button, f(x), f'(x)). Add your own.
FUNCTIONS = [
    ("x³ − 3x", lambda x: x ** 3 - 3 * x, lambda x: 3 * x ** 2 - 3),
    ("sin x", math.sin, math.cos),
    ("x² / 2", lambda x: x * x / 2, lambda x: x),
]
X_MIN, X_MAX = -2.5, 2.5

CONTROLS = [
    {"name": "fn", "kind": "steps", "label": "Function", "options": [f[0] for f in FUNCTIONS], "value": 0},
    {"name": "x0", "kind": "slider", "label": "Point", "min": X_MIN, "max": X_MAX, "step": 0.05, "value": 0.5,
     "play": True},
]
PRESETS = [{"label": "A flat spot", "values": {"fn": 0, "x0": 1}}, {"label": "Sine at zero", "values": {"fn": 1, "x0": 0}}]


def compute(fn=0, x0=0.5, _narrow=0):
    name, f, df = FUNCTIONS[fn]
    n = 120 if _narrow else 200
    xs = [X_MIN + (X_MAX - X_MIN) * i / n for i in range(n + 1)]
    ys, slopes = [f(x) for x in xs], [df(x) for x in xs]
    y0, m = f(x0), df(x0)
    lo, hi = min(ys + slopes), max(ys + slopes)
    pad = 0.1 * (hi - lo)
    lo, hi = lo - pad, hi + pad
    half = 0.9                                  # half the length of the tangent, along x
    tangent = {"name": "tangent", "x": [x0 - half, x0 + half], "y": [y0 - m * half, y0 + m * half],
               "style": "second", "label_at": "none"}
    return {
        "panels": [
            {"kind": "xy", "title": name, "x": xs,
             "series": [{"name": name, "y": ys, "style": "main", "label_at": "none"}, tangent,
                        {"name": "point", "x": [x0], "y": [y0], "style": "points highlight", "label_at": "none"}],
             "marks": [{"x": x0, "style": "faint"}],
             "x_min": X_MIN, "x_max": X_MAX, "y_min": lo, "y_max": hi, "x_label": "x", "y_label": "f(x)"},
            {"kind": "xy", "title": "its slope", "x": xs,
             "series": [{"name": "slope", "y": slopes, "style": "second", "label_at": "none"},
                        {"name": "point", "x": [x0], "y": [m], "style": "points highlight", "label_at": "none"}],
             "marks": [{"x": x0, "style": "faint"}, {"y": 0, "style": "muted"}],
             "x_min": X_MIN, "x_max": X_MAX, "y_min": lo, "y_max": hi, "x_label": "x", "y_label": "slope"},
        ],
        "widths": [1, 1],
        "readouts": [
            {"label": "Value", "value": "%.2f" % y0},
            {"label": "Slope", "value": "%.2f" % m, "note": "flat" if abs(m) < 0.05 else ("rising" if m > 0 else "falling")},
        ],
    }
