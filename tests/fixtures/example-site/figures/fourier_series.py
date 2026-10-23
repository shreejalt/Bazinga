"""A square wave built from sines: the partial sums of its Fourier series."""

import numpy as np

TITLE = "Building a square wave from sines"
CAPTION = ("A square wave is the sum of sin(kx)/k over odd k, times 4/π. Adding terms sharpens the "
           "edges, but the overshoot next to each jump stays near 9% (the Gibbs phenomenon).")
REQUIRES = ["numpy"]

CONTROLS = [
    {"name": "n", "kind": "slider", "label": "Terms", "min": 1, "max": 40, "step": 1, "value": 3, "play": True},
    {"name": "parts", "kind": "toggle", "label": "Show", "options": ["sum only", "sum and terms"], "value": 1},
]
PRESETS = [
    {"label": "One term", "values": {"n": 1}},
    {"label": "Many terms", "values": {"n": 40, "parts": 0}},
]

X = np.linspace(-np.pi, np.pi, 481)
SQUARE = np.sign(np.sin(X))


def compute(n=3, parts=1, _narrow=0):
    ks = 2 * np.arange(int(n)) + 1                       # 1, 3, 5, ...
    terms = (4 / np.pi) * np.sin(np.outer(ks, X)) / ks[:, None]
    total = terms.sum(axis=0)
    series = [{"name": "square wave", "y": SQUARE.tolist(), "style": "muted", "label_at": "none"}]
    if parts:
        for i, row in enumerate(terms[:4]):
            series.append({"name": "sin(%dx) term" % ks[i], "y": row.tolist(),
                           "style": "faint", "label_at": "none"})
    series.append({"name": "sum", "y": total.tolist(), "style": "main thick", "label_at": "none"})
    overshoot = (float(total.max()) - 1.0) / 2.0          # as a share of the jump from -1 to 1
    err = float(np.sqrt(np.mean((total - SQUARE) ** 2)))
    legend = [{"name": "square wave", "style": "muted"}, {"name": "sum of %d term%s" % (n, "" if n == 1 else "s"), "style": "main thick"}]
    if parts:
        legend.insert(1, {"name": "first terms", "style": "faint"})
    return {
        "legend": legend,
        "panels": [{
            "kind": "xy", "x": X.tolist(), "series": series,
            "x_ticks": [[-np.pi, "−π"], [-np.pi / 2, "−π/2"], [0, "0"],
                        [np.pi / 2, "π/2"], [np.pi, "π"]],
            "y_min": -1.5, "y_max": 1.5, "x_label": "x",
        }],
        "readouts": [
            {"label": "Highest term", "value": "sin(%dx)/%d" % (ks[-1], ks[-1])},
            {"label": "Overshoot", "value": "%.1f%%" % (100 * overshoot), "note": "of the jump"},
            {"label": "RMS error", "value": "%.3f" % err},
        ],
    }
