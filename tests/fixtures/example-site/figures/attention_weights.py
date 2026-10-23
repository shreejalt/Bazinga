"""Scaled dot-product attention on five tokens: what dividing the scores by √d does to the weights.

Every query and key is a vector of d random numbers with mean 0 and variance 1 (the setting of the
footnote in "Attention Is All You Need"). A bigger d keeps the first numbers and adds more, so the
vectors grow and their dot products spread out roughly like √d. Divided by √d, the spread stays near 1.
"""

import math

TITLE = "Attention weights for five tokens"
CAPTION = ("Each row is one word's query, softmaxed over its scores against every key. Without the division "
           "by √d the scores spread out as d grows and each row collapses onto one word.")
REQUIRES = []

TOKENS = ["the", "cat", "chased", "a", "mouse"]
D_OPTIONS = ["4", "16", "64"]
D_MAX = 64

CONTROLS = [
    {"name": "d", "kind": "steps", "label": "Vector size d", "options": D_OPTIONS, "value": 2},
    {"name": "raw", "kind": "toggle", "label": "Scores", "options": ["divided by √d", "not divided"], "value": 0},
    {"name": "temperature", "kind": "slider", "label": "Temperature", "min": 0.25, "max": 4, "step": 0.05, "value": 1},
]
PRESETS = [
    {"label": "Not divided", "values": {"d": 2, "raw": 1, "temperature": 1}},
    {"label": "Small d", "values": {"d": 0, "raw": 1, "temperature": 1}},
]


def _normals(count, seed):
    """Deterministic standard normal numbers (a small LCG and Box-Muller), the same on every machine."""
    state = seed
    out = []
    while len(out) < count:
        state = (1103515245 * state + 12345) % 2147483648
        u1 = (state + 1) / 2147483649
        state = (1103515245 * state + 12345) % 2147483648
        u2 = state / 2147483648
        r = math.sqrt(-2.0 * math.log(u1))
        out += [r * math.cos(2 * math.pi * u2), r * math.sin(2 * math.pi * u2)]
    return out[:count]


def _vectors(seed):
    flat = _normals(len(TOKENS) * D_MAX, seed)
    return [flat[i * D_MAX:(i + 1) * D_MAX] for i in range(len(TOKENS))]


QUERIES = _vectors(11)
KEYS = _vectors(29)


def softmax(row, t):
    m = max(row)
    e = [math.exp((v - m) / t) for v in row]
    s = sum(e)
    return [v / s for v in e]


def scores(d, scaled):
    """q·k for every pair, using the first d numbers of each vector; divided by √d when scaled."""
    div = math.sqrt(d) if scaled else 1.0
    return [[sum(q[i] * k[i] for i in range(d)) / div for k in KEYS] for q in QUERIES]


def compute(d=2, raw=0, temperature=1.0, _narrow=0):
    size = int(D_OPTIONS[int(d)])
    s = scores(size, scaled=not raw)
    weights = [softmax(row, temperature) for row in s]
    flat = [v for row in s for v in row]
    mean = sum(flat) / len(flat)
    spread = math.sqrt(sum((v - mean) ** 2 for v in flat) / len(flat))
    top = sum(max(r) for r in weights) / len(weights)
    entropy = sum(-sum(w * math.log(w) for w in r if w > 0) for r in weights) / len(weights)
    focus = [max(range(len(r)), key=lambda j: r[j]) for r in weights]
    label = "raw scores, d = %d" % size if raw else "scores ÷ √%d" % size
    return {
        "panels": [{
            "kind": "heatmap",
            "title": "Attention weights (%s)" % label,
            "matrix": weights,
            "row_labels": TOKENS,
            "col_labels": TOKENS,
            "range": [0, 1],
            "show_values": True,
            "decimals": 2,
            "highlight": [[i, j] for i, j in enumerate(focus)],
            "legend": "weight",
            "x_label": "key (attends to)",
        }],
        "readouts": [
            {"label": "Spread of scores", "value": "%.1f" % spread, "note": "standard deviation"},
            {"label": "Average top weight", "value": "%.2f" % top},
            {"label": "Average entropy", "value": "%.2f" % entropy, "note": "of at most %.2f nats" % math.log(len(TOKENS))},
        ],
        "description": "A five by five grid of attention weights; each row sums to one.",
    }
