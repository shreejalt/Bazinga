"""Starter: an animation of data piling up (rolling a die many times).

Copy it with  python -m tessera figure new my_sampling --from sampling  and put  ::figure my_sampling  in a post.

What it shows
-------------
Press Play and the die is rolled again and again. On the left, the running average settles towards
3.5; on the right, the counts of each face even out. The "Run" slider draws a different sequence.

Things worth copying
--------------------
- **Play over a count.** The "rolls" slider has "play": True, so Play adds rolls one frame at a time.
  Each frame is compute() at that count: the figure stays a function of its controls.
- **Randomness with a fixed seed:** the same run and count always give the same picture, in the build
  and in the browser.
- **Fixed axes** (x_max, y_min, y_max) so the picture does not jump while it plays.
"""

import random

TITLE = "Rolling a die again and again"
CAPTION = "Press Play: the average of the rolls settles near 3.5 and the six counts even out."
REQUIRES = []

MAX_ROLLS = 600
EXPECTED = 3.5

CONTROLS = [
    {"name": "rolls", "kind": "slider", "label": "Rolls", "min": 1, "max": MAX_ROLLS, "step": 1, "value": 30,
     "play": True},
    {"name": "run", "kind": "slider", "label": "Run", "min": 1, "max": 20, "step": 1, "value": 1},
]
PRESETS = [{"label": "Start over", "values": {"rolls": 1}}, {"label": "All rolls", "values": {"rolls": MAX_ROLLS}}]


def compute(rolls=30, run=1, _narrow=0):
    rng = random.Random(run)
    seq = [rng.randint(1, 6) for _ in range(MAX_ROLLS)][:rolls]
    xs, means, total = [], [], 0
    for i, r in enumerate(seq, start=1):
        total += r
        xs.append(i)
        means.append(total / i)
    counts = [seq.count(face) for face in range(1, 7)]
    top = max(10, max(counts))
    return {
        "panels": [
            {"kind": "xy", "title": "Average so far", "x": xs,
             "series": [{"name": "average", "y": means, "style": "main", "label_at": "none"}],
             "marks": [{"y": EXPECTED, "style": "muted dashed", "label": "3.5"}],
             "x_min": 0, "x_max": MAX_ROLLS, "y_min": 1, "y_max": 6, "x_label": "rolls", "y_label": "average"},
            {"kind": "bars", "title": "Counts",
             "bars": [{"label": str(face), "value": c, "style": "second"} for face, c in zip(range(1, 7), counts)],
             "y_min": 0, "y_max": top, "x_label": "face"},
        ],
        "widths": [1.5, 1],
        "readouts": [
            {"label": "Rolls", "value": str(rolls)},
            {"label": "Average", "value": "%.3f" % means[-1], "note": "%+.3f from 3.5" % (means[-1] - EXPECTED)},
        ],
    }
