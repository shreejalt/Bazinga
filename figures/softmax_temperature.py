"""Softmax with a temperature: how dividing the scores by T sharpens or flattens the probabilities."""

import math

TITLE = "Softmax temperature"
CAPTION = ("The same scores, divided by a temperature before the softmax. Low temperatures put almost "
           "all the probability on the top class; high ones spread it out.")
REQUIRES = []

CONTROLS = [
    {"name": "t", "kind": "slider", "label": "Temperature", "min": 0.1, "max": 5, "step": 0.05, "value": 1},
    {"name": "k", "kind": "steps", "label": "Classes", "options": ["3", "5", "8"], "value": 1},
]
PRESETS = [
    {"label": "Sharp", "values": {"t": 0.2}},
    {"label": "Flat", "values": {"t": 4}},
]

# Fixed scores (logits) for up to eight classes, largest first.
SCORES = [3.0, 2.2, 1.6, 1.1, 0.4, 0.0, -0.6, -1.2]
NAMES = ["cat", "dog", "fox", "owl", "elk", "bee", "eel", "yak"]


def softmax(z, t):
    m = max(z)
    e = [math.exp((v - m) / t) for v in z]
    s = sum(e)
    return [v / s for v in e]


def compute(t=1.0, k=1, _narrow=0):
    n = int(CONTROLS[1]["options"][k])
    z = SCORES[:n]
    p = softmax(z, t)
    entropy = -sum(q * math.log(q) for q in p if q > 0)
    top = max(range(n), key=lambda i: p[i])
    bars = [{"label": NAMES[i], "value": p[i], "note": "%.0f%%" % (100 * p[i]) if p[i] >= 0.005 else "<1%",
             "style": "main" if i == top else "muted"} for i in range(n)]
    # the curve: probability of the top class as the temperature changes
    ts = [0.1 + 0.05 * i for i in range(99)]
    curve = [softmax(z, tt)[0] for tt in ts]
    uniform = 1.0 / n
    return {
        "panels": [
            {"kind": "bars", "title": "Probabilities at T = %.2f" % t, "bars": bars,
             "y_min": 0, "y_max": 1, "y_label": "probability"},
            {"kind": "xy", "title": "Top class as T changes", "x": ts,
             "series": [{"name": "top class", "y": curve}],
             "marks": [{"x": t, "label": "T = %.2f" % t, "style": "highlight"},
                       {"y": uniform, "label": "uniform 1/%d" % n}],
             "x_label": "temperature", "y_min": 0, "y_max": 1, "x_min": 0, "x_max": 5},
        ],
        "readouts": [
            {"label": "Top class", "value": "%s, %.0f%%" % (NAMES[top], 100 * p[top])},
            {"label": "Entropy", "value": "%.2f" % entropy, "note": "of at most %.2f nats" % math.log(n)},
        ],
    }
