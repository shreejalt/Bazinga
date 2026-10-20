"""Starter: noisy data and the straight line that fits it best.

Copy it with  python -m tessera figure new my_fit --from scatter_fit  and put  ::figure my_fit  in a post.

What it shows
-------------
Points are scattered around a true line y = 0.8 x + 1. The reader turns the noise up and down and
draws a fresh sample; the least-squares line follows the points, and the readouts say how far it is
from the truth and how much of the spread it explains (R²).

Things worth copying
--------------------
- **Randomness with a fixed seed.** compute() must give the same picture for the same control
  values, at build time and in the browser. random.Random(seed) does that: the "Sample" slider *is*
  the seed, so moving it draws new points and moving it back brings the old ones back.
- **A scatter** is a series with the style "points"; "sizes" (pixels) gives each dot its own size.
- **Two layers of the same data**: a dashed muted line for the truth, a solid one for the fit.
- **Residuals** drawn as short lines from each point to the fit, shown by a toggle.
"""

import math
import random

TITLE = "Fitting a line to noisy points"
CAPTION = ("Turn up the noise and draw new samples: the fitted line wanders around the true one, "
           "and R² drops as the noise grows.")
REQUIRES = []

# The line the points are drawn around (the "truth" the fit tries to recover).
TRUE_SLOPE, TRUE_INTERCEPT = 0.8, 1.0
X_MIN, X_MAX = 0.0, 10.0

CONTROLS = [
    {"name": "noise", "kind": "slider", "label": "Noise", "min": 0, "max": 3, "step": 0.1, "value": 1},
    # A whole-number slider gives an int: here it is the seed of the random numbers.
    {"name": "sample", "kind": "slider", "label": "Sample", "min": 1, "max": 30, "step": 1, "value": 1},
    {"name": "n", "kind": "steps", "label": "Points", "options": ["10", "30", "100"], "value": 1},
    {"name": "residuals", "kind": "toggle", "label": "Residuals", "options": ["Hide", "Show"], "value": 0},
]

PRESETS = [
    {"label": "No noise", "values": {"noise": 0}},
    {"label": "Few, noisy points", "values": {"noise": 2.5, "n": 0}},
]


def least_squares(xs, ys):
    """Slope, intercept and R² of the best straight line through the points."""
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    slope = sxy / sxx
    intercept = my - slope * mx
    total = sum((y - my) ** 2 for y in ys)
    left = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(xs, ys))
    r2 = 1.0 - left / total if total > 0 else 1.0
    return slope, intercept, r2


def compute(noise=1.0, sample=1, n=1, residuals=0, _narrow=0):
    count = int(CONTROLS[2]["options"][n])          # steps controls give the index of the chosen option
    rng = random.Random(sample)                      # same sample number -> same points, everywhere
    xs = [rng.uniform(X_MIN, X_MAX) for _ in range(count)]
    ys = [TRUE_SLOPE * x + TRUE_INTERCEPT + rng.gauss(0, 1) * noise for x in xs]
    slope, intercept, r2 = least_squares(xs, ys)

    ends = [X_MIN, X_MAX]
    shapes = []
    if residuals:
        for x, y in zip(xs, ys):
            shapes.append({"type": "line", "x1": x, "y1": y, "x2": x, "y2": slope * x + intercept,
                           "style": "muted thin"})

    # Smaller dots when there are many points, so they do not merge into a blob.
    size = {10: 6, 30: 5, 100: 3.5}[count]
    return {
        "panels": [{
            "kind": "xy",
            "series": [
                {"name": "true line", "x": ends, "y": [TRUE_SLOPE * x + TRUE_INTERCEPT for x in ends],
                 "style": "muted dashed"},
                {"name": "points", "x": xs, "y": ys, "style": "second points", "sizes": [size] * count},
                {"name": "best fit", "x": ends, "y": [slope * x + intercept for x in ends], "style": "main"},
            ],
            "shapes": shapes,
            "x_min": X_MIN, "x_max": X_MAX, "y_min": -4, "y_max": 14,    # fixed, so the picture does not jump
            "x_label": "x", "y_label": "y",
        }],
        "readouts": [
            {"label": "Fitted slope", "value": "%.2f" % slope, "note": "true %.2f" % TRUE_SLOPE},
            {"label": "Fitted intercept", "value": "%.2f" % intercept, "note": "true %.2f" % TRUE_INTERCEPT},
            {"label": "R²", "value": "%.3f" % r2, "note": "share of the spread the line explains"},
        ],
    }
