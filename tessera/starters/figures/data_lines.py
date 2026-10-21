"""Starter: your own data as lines, with one series picked out.

Copy it with  python -m tessera figure new my_chart --from data_lines  and put  ::figure my_chart  in a post.

What it shows
-------------
A small table of numbers (paste your own over DATA) drawn as one line per column. The reader picks a
series to bring forward (the others fade), smooths the lines with a moving average, and switches
between the raw values and the change from the first row.

Things worth copying
--------------------
- **Data in the file.** DATA is a plain table: the first column is the x value, the others are series.
  Replace it with your own numbers; nothing else needs to change.
- **"steps" built from the data,** so the choices follow the columns you paste.
- **Fading the rest:** the chosen series gets "main", the others "faint".
"""

TITLE = "Readers per month"
CAPTION = "Pick a series to bring it forward, smooth the lines, or show each one as a change from the first month."
REQUIRES = []

# Example numbers. Replace them with your own: one row per x value, one column per series.
COLUMNS = ["Month", "Post A", "Post B", "Post C"]
DATA = [
    [1, 120, 40, 15],
    [2, 135, 52, 18],
    [3, 128, 75, 22],
    [4, 160, 90, 30],
    [5, 150, 130, 34],
    [6, 172, 118, 52],
    [7, 165, 140, 61],
    [8, 190, 160, 70],
    [9, 185, 151, 96],
    [10, 210, 175, 120],
    [11, 205, 168, 150],
    [12, 230, 190, 171],
]
X_LABEL, Y_LABEL = "month", "readers"
SERIES = COLUMNS[1:]

CONTROLS = [
    {"name": "pick", "kind": "steps", "label": "Bring forward", "options": ["All"] + SERIES, "value": 0},
    {"name": "window", "kind": "slider", "label": "Smoothing (rows)", "min": 1, "max": 5, "step": 1, "value": 1},
    {"name": "change", "kind": "toggle", "label": "Show", "options": ["Values", "Change from first row"], "value": 0},
]
PRESETS = [
    {"label": "Smooth", "values": {"window": 3}},
    {"label": "Growth of Post C", "values": {"pick": 3, "change": 1}},
]


def moving_average(ys, window):
    """The mean of the last `window` values at each point (fewer at the start)."""
    out = []
    for i in range(len(ys)):
        part = ys[max(0, i - window + 1): i + 1]
        out.append(sum(part) / len(part))
    return out


def compute(pick=0, window=1, change=0, _narrow=0):
    xs = [row[0] for row in DATA]
    series, latest = [], []
    for j, name in enumerate(SERIES, start=1):
        ys = moving_average([row[j] for row in DATA], window)
        if change:
            ys = [y - ys[0] for y in ys]
        chosen = pick == 0 or pick == j
        style = ("main", "second", "third", "fourth")[min(j - 1, 3)] if pick == 0 else ("main thick" if chosen else "faint")
        series.append({"name": name, "y": ys, "style": style})
        latest.append((name, ys[-1]))
    shown = latest if pick == 0 else [latest[pick - 1]]
    return {
        "panels": [{
            "kind": "xy", "x": xs, "series": series,
            "x_label": X_LABEL, "y_label": ("change in " + Y_LABEL) if change else Y_LABEL,
            "marks": [{"y": 0, "style": "muted"}] if change else [],
        }],
        "readouts": [{"label": name, "value": ("%+.0f" if change else "%.0f") % v, "note": "last row"}
                     for name, v in shown],
    }
