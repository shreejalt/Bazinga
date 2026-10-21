"""Starter: a matrix as a heatmap.

Copy it with  python -m bazinga figure new my_matrix --from heatmap

Each cell is coloured by its value. When the range runs from negative to positive the colours
diverge around zero (two hues, grey in the middle); otherwise they run light to dark in one hue.
Here: attention weights, a softmax over similarity scores between tokens, with a temperature.
"""

import math

TITLE = "Attention weights"
CAPTION = "Each row is one token's attention over the sentence. Lower the temperature to make it pick one word."
REQUIRES = []

TOKENS = ["the", "cat", "sat", "on", "the", "mat"]
# A made-up similarity score between tokens (row attends to column). Replace with your own matrix.
SCORES = [
    [2.0, 0.5, 0.1, 0.3, 1.8, 0.2],
    [0.4, 2.5, 1.2, 0.1, 0.3, 0.9],
    [0.1, 1.6, 2.2, 0.8, 0.1, 0.7],
    [0.3, 0.2, 0.9, 2.0, 0.4, 1.1],
    [1.8, 0.3, 0.1, 0.4, 2.0, 0.6],
    [0.2, 1.0, 0.6, 1.0, 0.5, 2.4],
]

CONTROLS = [
    {"name": "temperature", "kind": "slider", "label": "Temperature", "min": 0.1, "max": 3, "step": 0.05, "value": 1},
    {"name": "values", "kind": "toggle", "label": "Numbers", "options": ["hide", "show"], "value": 1},
]
PRESETS = [{"label": "Almost one-hot", "values": {"temperature": 0.15}}]


def softmax(row, t):
    m = max(row)
    e = [math.exp((v - m) / t) for v in row]
    s = sum(e)
    return [v / s for v in e]


def compute(temperature=1.0, values=1, _narrow=0):
    weights = [softmax(row, temperature) for row in SCORES]
    focus = [max(range(len(r)), key=lambda j: r[j]) for r in weights]
    return {
        "panels": [{
            "kind": "heatmap",
            "matrix": weights,                     # a list of rows
            "row_labels": TOKENS,
            "col_labels": TOKENS,
            "range": [0, 1],                       # fixed range: colours mean the same at every setting
            "show_values": bool(values),
            "highlight": [[i, j] for i, j in enumerate(focus)],   # outline these cells
            "legend": "weight",
            "x_label": "attends to",
        }],
        "readouts": [{"label": "Largest weight", "value": "%.2f" % max(max(r) for r in weights)}],
    }
