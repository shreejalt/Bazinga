"""Starter: a surface z = f(x, y) with sliders, that you can turn.

Copy it with  python -m bazinga figure new my_surface --from surface_plot  and put  ::figure my_surface  in a post.

What it shows
-------------
A wave on a square sheet: z = a · sin(k·x) · cos(k·y). The sliders change its height a and how many
ripples it has k; drag the picture to look at it from anywhere.

Things worth copying
--------------------
- sc.surface(f, x=(lo, hi), y=(lo, hi), n=18) draws the surface as n x n small faces coloured by
  height, sorted far to near so it hides itself correctly. f may return None for a hole.
- z_range=(-1, 1) fixes the colours and the height, so the picture does not jump as the sliders move.
- n x n faces cost time: 18 x 18 stays well inside the 30 ms budget, on phones too.
- A curve on the surface: sc.curve(lambda t: (x(t), y(t), z(t)), t0, t1).
"""

import math

from bazinga.scene3d import Scene

TITLE = "A wave on a sheet"
CAPTION = "z = a · sin(k·x) · cos(k·y). Change the height and the ripples; drag the picture to turn it."
REQUIRES = []

CONTROLS = [
    {"name": "a", "kind": "slider", "label": "Height a", "min": 0, "max": 1, "step": 0.05, "value": 0.6},
    {"name": "k", "kind": "slider", "label": "Ripples k", "min": 0.5, "max": 3, "step": 0.1, "value": 1.5, "play": True},
    {"name": "view", "kind": "orbit", "value": [30, 30]},
]

PRESETS = [
    {"label": "Flat", "values": {"a": 0}},
    {"label": "Many ripples", "values": {"k": 3, "a": 0.8}},
]

SPAN = 2.0      # x and y run from -SPAN to SPAN


def compute(a=0.6, k=1.5, view=(30, 30), _narrow=0):
    def f(x, y):
        return a * math.sin(k * x) * math.cos(k * y)

    sc = Scene()
    sc.axes3d(lo=(-SPAN, -SPAN, -1), hi=(SPAN + 0.4, SPAN + 0.4, 1.4), ticks=4)
    sc.surface(f, x=(-SPAN, SPAN), y=(-SPAN, SPAN), n=18, z_range=(-1, 1))
    # the line x = y across the sheet, drawn on top of it
    sc.curve(lambda t: (t, t, f(t, t) + 0.02), -SPAN, SPAN, n=60, style="second thick", label="x = y")
    return sc.render(view=view, narrow=_narrow, dist=6.8, target=(0, 0, -0.1),
                     readouts=[{"label": "Highest point", "value": "%.2f" % abs(a)},
                               {"label": "Ripple length", "value": "%.2f" % (2 * math.pi / k)}])
