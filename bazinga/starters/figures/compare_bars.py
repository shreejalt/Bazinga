"""Starter: compare a few numbers as bars.

Copy it with  python -m bazinga figure new my_bars --from compare_bars

Bars suit a handful of named values (methods, models, classes). Put your own numbers in DATA; the
controls here pick which column to show and whether to sort. Write each number with its source in
your post: a figure is not a citation.
"""

TITLE = "Three ways to do the same job"
CAPTION = "Pick a measure; the best option for it is highlighted."
REQUIRES = []

# Example numbers. Replace them with yours (and say where they come from in the caption or post).
DATA = [
    # name,        speed, accuracy, memory
    ("Simple",      120,   71.0,     1.0),
    ("Balanced",     85,   78.5,     2.1),
    ("Large",        30,   82.3,     6.4),
]
MEASURES = [
    # label, column, unit, higher is better?
    ("Speed", 1, "items/s", True),
    ("Accuracy", 2, "%", True),
    ("Memory", 3, "GB", False),
]

CONTROLS = [
    # "steps" shows a row of choices; compute() receives the index of the chosen one.
    {"name": "measure", "kind": "steps", "label": "Measure", "options": [m[0] for m in MEASURES], "value": 1},
    # "toggle" is a two-way choice; also an index (0 or 1).
    {"name": "layout", "kind": "toggle", "label": "Bars", "options": ["upright", "sideways"], "value": 0},
]
PRESETS = []


def compute(measure=1, layout=0, _narrow=0):
    label, col, unit, higher_better = MEASURES[measure]
    values = [row[col] for row in DATA]
    best = max(values) if higher_better else min(values)
    bars = []
    for row in DATA:
        v = row[col]
        bars.append({
            "label": row[0],
            "value": v,
            "note": "%g %s" % (v, unit),                      # text at the end of the bar
            "style": "main" if v == best else "muted",        # colour the one that matters
        })
    return {
        "panels": [{
            "kind": "bars",
            "horizontal": layout == 1,
            "bars": bars,
            "title": "%s (%s, %s is better)" % (label, unit, "higher" if higher_better else "lower"),
        }],
        "readouts": [{"label": "Best", "value": DATA[values.index(best)][0]}],
    }
