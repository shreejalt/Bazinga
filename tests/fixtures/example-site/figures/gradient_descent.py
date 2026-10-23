"""Gradient descent on a stretched quadratic bowl: the learning rate decides between crawling,
converging and zig-zagging out of control."""

import math

TITLE = "Gradient descent on a bowl"
CAPTION = ("Each step moves against the gradient of f(x, y) = x²/2 + 5y²/2, scaled by the learning "
           "rate. Above 0.4 the steep direction overshoots and the path diverges.")
REQUIRES = []

CONTROLS = [
    {"name": "lr", "kind": "slider", "label": "Learning rate", "min": 0.02, "max": 0.44, "step": 0.01, "value": 0.15},
    {"name": "steps", "kind": "slider", "label": "Steps", "min": 0, "max": 40, "step": 1, "value": 12, "play": True},
]
PRESETS = [
    {"label": "Too small", "values": {"lr": 0.03, "steps": 40}},
    {"label": "Zig-zag", "values": {"lr": 0.36, "steps": 20}},
    {"label": "Diverges", "values": {"lr": 0.42, "steps": 30}},
]

A, B = 1.0, 5.0            # curvatures along x and y
START = (-4.0, 1.6)


def f(x, y):
    return 0.5 * (A * x * x + B * y * y)


def compute(lr=0.15, steps=12, _narrow=0):
    x, y = START
    path = [(x, y)]
    for _ in range(int(steps)):
        x, y = x - lr * A * x, y - lr * B * y
        path.append((x, y))
    # level sets of the bowl are ellipses with radii sqrt(2c/A), sqrt(2c/B)
    shapes = []
    for c in (0.25, 1, 2.5, 5, 9, 14):
        shapes.append({"type": "circle", "x": 0, "y": 0, "rx": math.sqrt(2 * c / A),
                       "ry": math.sqrt(2 * c / B), "style": "contour"})
    shapes.append({"type": "line", "points": [list(q) for q in path], "style": "main"})
    for q in path[1:-1]:
        shapes.append({"type": "point", "x": q[0], "y": q[1], "r": 3, "style": "main small"})
    shapes.append({"type": "point", "x": START[0], "y": START[1], "label": "start", "style": "muted"})
    shapes.append({"type": "point", "x": path[-1][0], "y": path[-1][1], "label": "step %d" % steps, "style": "highlight"})
    shapes.append({"type": "point", "x": 0, "y": 0, "r": 3, "label": "minimum", "style": "ink"})

    losses = [f(*q) for q in path]
    ks = list(range(len(path)))
    final = losses[-1]
    factor_y = abs(1 - lr * B)
    return {
        "panels": [
            {"kind": "scene", "title": "The path", "shapes": shapes, "equal": True,
             "x_min": -5, "x_max": 5, "y_min": -2.6, "y_max": 2.6, "axes": True},
            {"kind": "xy", "title": "Loss after each step", "x": ks, "y_log": True,
             "series": [{"name": "loss", "y": [max(v, 1e-6) for v in losses], "style": "main", "label_at": "none"}],
             "x_label": "step", "x_min": 0, "x_max": 40, "y_min": 1e-6, "y_max": 1e4},
        ],
        "widths": [1.25, 1],
        "readouts": [
            {"label": "Loss now", "value": "%.3g" % final},
            {"label": "Steep direction shrinks by", "value": "×%.2f" % factor_y,
             "note": "per step; above 1 it grows"},
        ],
    }
