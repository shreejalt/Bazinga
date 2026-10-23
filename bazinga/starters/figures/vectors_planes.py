"""Starter: two vectors, their cross product, and the plane they span.

Copy it with  python -m bazinga figure new my_vectors --from vectors_planes  and put  ::figure my_vectors  in a post.

What it shows
-------------
Two arrows u and v from the origin. Their cross product u × v stands at right angles to both, and its
length is the area of the parallelogram they make. The shaded sheet is the plane through u and v.

Things worth copying
--------------------
- Points you drag: the tips of u and v are handles. A "pad" control holds each tip (x, y); dragging a
  handle sends compute() a _drag, and apply_drag() turns it into new values (here: the tip slides in
  the flat plane z = its height, which a slider sets).
- render(state=...) hands the new values back, so the controls under the figure follow the drag.
- sc.vector(origin, v), sc.poly(corners) and sc.plane(point, normal) for linear algebra pictures.
"""

from bazinga.scene3d import Scene, apply_drag, layout, cross, norm, fmt

TITLE = "The cross product"
CAPTION = ("Drag the tips of u and v, or change their heights. u × v is at right angles to both; its length is "
           "the area of the shaded parallelogram.")
REQUIRES = []

CONTROLS = [
    {"name": "u", "kind": "pad", "label": "u (x, y)", "min": [-2, -2], "max": [2, 2], "value": [1.5, 0.2]},
    {"name": "v", "kind": "pad", "label": "v (x, y)", "min": [-2, -2], "max": [2, 2], "value": [0.4, 1.4]},
    {"name": "uz", "kind": "slider", "label": "Height of u", "min": -1, "max": 1, "step": 0.05, "value": 0},
    {"name": "vz", "kind": "slider", "label": "Height of v", "min": -1, "max": 1, "step": 0.05, "value": 0.3},
    {"name": "view", "kind": "orbit", "value": [30, 22]},
]

PRESETS = [
    {"label": "At right angles", "values": {"u": [1.5, 0], "v": [0, 1.5], "uz": 0, "vz": 0}},
    {"label": "Pointing the same way", "values": {"u": [1, 1], "v": [1.4, 1.4], "uz": 0.2, "vz": 0.28}},
]


def compute(u=(1.5, 0.2), v=(0.4, 1.4), uz=0.0, vz=0.3, view=(30, 22), _drag=None, _narrow=0):
    lay = layout(_narrow, dist=6.5, target=(0, 0, 0.6))
    # a dragged tip slides in the plane z = its height; apply_drag returns the values with the dragged one moved
    rules = {"u": ("plane", (0, 0, uz), (0, 0, 1), (0, 1)), "v": ("plane", (0, 0, vz), (0, 0, 1), (0, 1))}
    vals = apply_drag(_drag, rules, {"u": list(u), "v": list(v), "view": list(view)}, **lay)
    clamp = lambda p: [max(-2.0, min(2.0, c)) for c in p]  # noqa: E731
    U, V = clamp(vals["u"]) + [uz], clamp(vals["v"]) + [vz]
    W = cross(U, V)

    sc = Scene()
    sc.grid(size=4, n=4, level=0)
    sc.axes3d(lo=(-2, -2, -1), hi=(2.3, 2.3, 2.3), ticks=0)
    sc.poly([(0, 0, 0), U, [U[i] + V[i] for i in range(3)], V], style="main")      # the parallelogram
    if norm(W) > 1e-6:
        sc.plane([0, 0, 0], W, size=3.2, style="faint")                             # the plane through u and v
    sc.vector((0, 0, 0), U, label="u", style="main thick")
    sc.vector((0, 0, 0), V, label="v", style="third thick")
    sc.vector((0, 0, 0), W, label="u × v", style="second thick")
    handles = [{"name": "u", "at": U, "hint": "drag the tip of u"}, {"name": "v", "at": V, "hint": "drag the tip of v"}]
    return sc.render(view=view, handles=handles, state={"u": U[:2], "v": V[:2]} if _drag else None,
                     readouts=[{"label": "u × v", "value": "(%s)" % ", ".join(fmt(c) for c in W)},
                               {"label": "Area", "value": fmt(norm(W)), "note": "the length of u × v"}],
                     **lay)
