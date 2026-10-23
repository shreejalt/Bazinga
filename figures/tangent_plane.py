"""The tangent plane of a surface, and the way uphill.

A 3-D example figure: the surface z = (a·x² + b·y²) / 2, a point P on it that the reader drags, the flat plane that
touches the surface at P, and the arrow of steepest climb (the gradient, lifted onto the plane). Drag the
background to turn the picture.
"""
import math

from bazinga.scene3d import Scene, apply_drag, layout, fmt

TITLE = "The tangent plane and the way uphill"
CAPTION = ("Drag the point P over the surface; the flat sheet touches the surface at P and the arrow points the "
           "steepest way up. Make a or b negative for a saddle. Drag the background to turn the picture.")
REQUIRES = []

CONTROLS = [
    {"name": "a", "kind": "slider", "label": "Curvature across, a", "min": -1, "max": 1, "step": 0.05, "value": 0.6},
    {"name": "b", "kind": "slider", "label": "Curvature along, b", "min": -1, "max": 1, "step": 0.05, "value": 0.3},
    {"name": "p", "kind": "pad", "label": "P (x, y)", "min": [-1.8, -1.8], "max": [1.8, 1.8], "value": [0.9, -0.6]},
    {"name": "view", "kind": "orbit", "value": [28, 28]},
]

PRESETS = [
    {"label": "A bowl", "values": {"a": 0.8, "b": 0.8}},
    {"label": "A saddle", "values": {"a": 0.8, "b": -0.8, "p": [0.8, 0.8]}},
    {"label": "At the bottom", "values": {"a": 0.6, "b": 0.3, "p": [0, 0]}},
]

SPAN = 2.0


def compute(a=0.6, b=0.3, p=(0.9, -0.6), view=(28, 28), _drag=None, _narrow=0):
    def f(x, y):
        return (a * x * x + b * y * y) / 2

    lay = layout(_narrow, dist=7, target=(0, 0, 0.3))
    # P slides in the flat plane at its own height, so it stays under the pointer
    z0 = f(p[0], p[1])
    vals = apply_drag(_drag, {"p": ("plane", (0, 0, z0), (0, 0, 1), (0, 1))}, {"p": list(p), "view": list(view)}, **lay)
    x0, y0 = [max(-1.8, min(1.8, c)) for c in vals["p"]]
    z0 = f(x0, y0)
    gx, gy = a * x0, b * y0                           # the gradient: how fast z grows across and along
    slope = math.hypot(gx, gy)

    sc = Scene()
    sc.axes3d(lo=(-SPAN, -SPAN, -2), hi=(SPAN + 0.4, SPAN + 0.4, 2.4), ticks=0)
    sc.surface(f, x=(-SPAN, SPAN), y=(-SPAN, SPAN), n=16, z_range=(-2, 2))
    h = 0.6                                           # half the size of the tangent sheet
    plane = [(x0 + dx, y0 + dy, z0 + gx * dx + gy * dy + 0.01) for dx, dy in ((-h, -h), (h, -h), (h, h), (-h, h))]
    sc.poly(plane, style="second", split=4)        # in pieces, so the surface hides the right parts
    P = (x0, y0, z0 + 0.02)
    if slope > 1e-6:
        k = 0.8 / math.sqrt(slope * slope + slope ** 4)   # an arrow 0.8 long along (gx, gy, gx² + gy²)
        sc.vector(P, (gx * k, gy * k, slope * slope * k), label="uphill", style="second thick")
    sc.point(P, label="P", style="ink", r=5)
    sc.line((x0, y0, 0), P, style="faint", dash="2 3")

    return sc.render(view=view, handles=[{"name": "p", "at": P, "hint": "drag the point P"}],
                     state={"p": [round(x0, 3), round(y0, 3)]} if _drag else None,
                     readouts=[{"label": "Height at P", "value": fmt(z0)},
                               {"label": "Gradient", "value": "(%s, %s)" % (fmt(gx), fmt(gy)), "note": "(a·x, b·y)"},
                               {"label": "Steepest slope", "value": fmt(slope)}],
                     **lay)
