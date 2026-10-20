"""Starter: a 2 x 2 matrix moving the whole plane.

Copy it with  python -m tessera figure new my_matrix --from matrix_transform  and put  ::figure my_matrix  in a post.

What it shows
-------------
Four sliders are the four entries of a matrix M = [[a, b], [c, d]]. The faint grid is the plane
before; the coloured grid is where M sends it. The unit square becomes a parallelogram whose area is
|det M|, and when the determinant turns negative the picture is flipped over.

Things worth copying
--------------------
- **A "scene" panel** draws shapes in data units: lines, arrows, polygons, points and text.
  "equal": True keeps one unit the same length across and up, so squares stay square.
- **A grid made of lines**: each grid line is mapped through the matrix, so the grid bends with it.
  ("grid": True on a panel draws a fixed background grid at the tick marks instead.)
- **"origin": True** draws the two axes through (0, 0).
- **Presets** that each tell a story: rotation, shear, reflection, and a matrix that squashes the
  plane onto a line.
"""

TITLE = "What a matrix does to the plane"
CAPTION = ("Each slider is one entry of the matrix. The square becomes a parallelogram with area |det M|; "
           "a negative determinant flips the plane over.")
REQUIRES = []

CONTROLS = [
    {"name": "a", "kind": "slider", "label": "a (top left)", "min": -2, "max": 2, "step": 0.05, "value": 1},
    {"name": "b", "kind": "slider", "label": "b (top right)", "min": -2, "max": 2, "step": 0.05, "value": 0.5},
    {"name": "c", "kind": "slider", "label": "c (bottom left)", "min": -2, "max": 2, "step": 0.05, "value": 0},
    {"name": "d", "kind": "slider", "label": "d (bottom right)", "min": -2, "max": 2, "step": 0.05, "value": 1},
]

PRESETS = [
    {"label": "Identity", "values": {"a": 1, "b": 0, "c": 0, "d": 1}},
    {"label": "Rotate 90°", "values": {"a": 0, "b": -1, "c": 1, "d": 0}},
    {"label": "Shear", "values": {"a": 1, "b": 1, "c": 0, "d": 1}},
    {"label": "Mirror", "values": {"a": -1, "b": 0, "c": 0, "d": 1}},
    {"label": "Squash flat", "values": {"a": 1, "b": 2, "c": 0.5, "d": 1}},
]

SPAN = 2          # grid lines from -SPAN to SPAN
VIEW = 4.2        # half the width of the view


def compute(a=1.0, b=0.5, c=0.0, d=1.0, _narrow=0):
    def move(x, y):
        """Where M sends the point (x, y)."""
        return [a * x + b * y, c * x + d * y]

    det = a * d - b * c
    shapes = []
    # the plane before (faint) and after (coloured): vertical and horizontal grid lines
    for k in range(-SPAN, SPAN + 1):
        shapes.append({"type": "line", "x1": k, "y1": -SPAN, "x2": k, "y2": SPAN, "style": "faint thin"})
        shapes.append({"type": "line", "x1": -SPAN, "y1": k, "x2": SPAN, "y2": k, "style": "faint thin"})
    for k in range(-SPAN, SPAN + 1):
        p, q = move(k, -SPAN), move(k, SPAN)
        shapes.append({"type": "line", "x1": p[0], "y1": p[1], "x2": q[0], "y2": q[1], "style": "main thin"})
        p, q = move(-SPAN, k), move(SPAN, k)
        shapes.append({"type": "line", "x1": p[0], "y1": p[1], "x2": q[0], "y2": q[1], "style": "third thin"})

    # the unit square and its image; "bad" colours it when the plane is flipped
    square = [[0, 0], [1, 0], [1, 1], [0, 1]]
    shapes.append({"type": "polygon", "points": square, "style": "muted outline dashed"})
    shapes.append({"type": "polygon", "points": [move(x, y) for x, y in square],
                   "style": "main" if det >= 0 else "bad"})

    # the images of the two basis vectors: the columns of M
    e1, e2 = move(1, 0), move(0, 1)
    shapes.append({"type": "arrow", "x1": 0, "y1": 0, "x2": e1[0], "y2": e1[1], "style": "main thick", "label": "M e₁"})
    shapes.append({"type": "arrow", "x1": 0, "y1": 0, "x2": e2[0], "y2": e2[1], "style": "third thick", "label": "M e₂"})

    if abs(det) < 1e-9:
        effect = "squashed onto a line"
    elif det < 0:
        effect = "flipped over"
    else:
        effect = "same orientation"
    return {
        "panels": [{
            "kind": "scene", "shapes": shapes, "equal": True, "origin": True,
            "x_min": -VIEW, "x_max": VIEW, "y_min": -VIEW, "y_max": VIEW,
        }],
        "readouts": [
            {"label": "det M", "value": ("%.2f" % det).replace("-", "−"), "note": effect},
            {"label": "Area of the square", "value": "%.2f" % abs(det), "note": "was 1"},
            {"label": "M", "value": "[[%g, %g], [%g, %g]]" % (a, b, c, d)},
        ],
    }
