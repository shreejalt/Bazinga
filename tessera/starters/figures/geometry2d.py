"""Starter: 2-D geometry drawn with shapes.

Copy it with  python -m tessera figure new my_geometry --from geometry2d

A "scene" panel draws shapes in data units: point, line, arrow, polygon, circle, rect, text.
"equal": True keeps one unit the same length on both axes, so circles stay round.
Here: a 2x2 matrix acting on the unit square and the unit circle.
"""

import math

TITLE = "Rotate and stretch"
CAPTION = "The matrix rotates by the angle and stretches along x. The unit square becomes the shaded shape."
REQUIRES = []

CONTROLS = [
    {"name": "angle", "kind": "slider", "label": "Angle (degrees)", "min": -180, "max": 180, "step": 5, "value": 30},
    {"name": "stretch", "kind": "slider", "label": "Stretch x", "min": 0.25, "max": 2.5, "step": 0.05, "value": 1.5},
]
PRESETS = [
    {"label": "Pure rotation", "values": {"stretch": 1}},
    {"label": "Squash", "values": {"angle": 0, "stretch": 0.3}},
]


def compute(angle=30, stretch=1.5, _narrow=0):
    a = math.radians(angle)
    c, s = math.cos(a), math.sin(a)
    # M = R(angle) @ diag(stretch, 1)
    m = [[c * stretch, -s], [s * stretch, c]]

    def apply(p):
        return [m[0][0] * p[0] + m[0][1] * p[1], m[1][0] * p[0] + m[1][1] * p[1]]

    square = [[0, 0], [1, 0], [1, 1], [0, 1]]
    circle = [[math.cos(2 * math.pi * k / 72), math.sin(2 * math.pi * k / 72)] for k in range(73)]
    e1, e2 = apply([1, 0]), apply([0, 1])
    det = m[0][0] * m[1][1] - m[0][1] * m[1][0]
    shapes = [
        {"type": "polygon", "points": square, "style": "muted outline dashed"},
        {"type": "line", "points": circle, "style": "muted dashed"},
        {"type": "polygon", "points": [apply(p) for p in square], "style": "main"},
        {"type": "line", "points": [apply(p) for p in circle], "style": "second"},
        {"type": "arrow", "x1": 0, "y1": 0, "x2": e1[0], "y2": e1[1], "style": "main", "label": "M e₁"},
        {"type": "arrow", "x1": 0, "y1": 0, "x2": e2[0], "y2": e2[1], "style": "third", "label": "M e₂"},
        {"type": "point", "x": 0, "y": 0, "r": 3, "style": "ink"},
    ]
    return {
        "panels": [{
            "kind": "scene", "shapes": shapes, "equal": True, "axes": True,
            "x_min": -2.6, "x_max": 2.6, "y_min": -2.6, "y_max": 2.6,   # fixed: the view does not jump
        }],
        "readouts": [
            {"label": "Area scale (determinant)", "value": "%.2f" % det},
            {"label": "Matrix", "value": "[%.2f %.2f; %.2f %.2f]" % (m[0][0], m[0][1], m[1][0], m[1][1])},
        ],
    }
