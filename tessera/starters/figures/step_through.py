"""Starter: an algorithm you can step through, one move at a time (bubble sort on eight bars).

Copy it with  python -m tessera figure new my_steps --from step_through  and put  ::figure my_steps  in a post.

What it shows
-------------
Bubble sort compares neighbours and swaps them when they are out of order. The "Step" slider has a
Play button; each step is one comparison. The two bars being compared are highlighted, and the bars
that have reached their final place turn green.

Things worth copying
--------------------
- **Record the whole run once, then show one frame.** The sort is run in full when the figure loads
  (TRACE below); compute() only picks the frame for the slider's step. Each frame is cheap, so Play
  is smooth.
- **"play": True** on a slider adds the Play button. Playing moves the slider to its end.
- **A fixed slider range**: bubble sort on 8 items always makes 8·7/2 = 28 comparisons, so the slider
  runs from 0 to 28 whatever the starting order.
- **Bars with styles per bar**: "highlight", "good" and "muted" are colours from the theme.
"""

TITLE = "Bubble sort, one comparison at a time"
CAPTION = ("Press Play, or drag the step. The highlighted pair is being compared; green bars are in their "
           "final place.")
REQUIRES = []

START_ORDERS = {
    "Shuffled": [5, 2, 7, 1, 8, 4, 6, 3],
    "Reversed": [8, 7, 6, 5, 4, 3, 2, 1],
    "Nearly sorted": [1, 2, 4, 3, 5, 6, 8, 7],
}
NAMES = list(START_ORDERS)
N = 8
STEPS = N * (N - 1) // 2          # 28 comparisons, for any starting order

CONTROLS = [
    {"name": "step", "kind": "slider", "label": "Step", "min": 0, "max": STEPS, "step": 1, "value": 0, "play": True},
    {"name": "order", "kind": "steps", "label": "Start from", "options": NAMES, "value": 0},
]

PRESETS = [
    {"label": "Halfway", "values": {"step": 14}},
    {"label": "Done", "values": {"step": STEPS}},
]


def bubble_sort_trace(values):
    """Every state of the sort: (list, compared pair, swapped?, number of bars already in place)."""
    a = list(values)
    frames = [(list(a), None, False, 0)]
    for done in range(N - 1):                       # after pass `done`, the last done+1 bars are final
        for i in range(N - 1 - done):
            swapped = a[i] > a[i + 1]
            if swapped:
                a[i], a[i + 1] = a[i + 1], a[i]
            last = i == N - 2 - done
            frames.append((list(a), (i, i + 1), swapped, done + 1 if last else done))
    return frames


# Run each sort once, when the figure is loaded.
TRACE = {name: bubble_sort_trace(order) for name, order in START_ORDERS.items()}


def compute(step=0, order=0, _narrow=0):
    frames = TRACE[NAMES[order]]
    values, pair, swapped, placed = frames[step]
    if step == STEPS:
        placed = N
    swaps = sum(1 for f in frames[1:step + 1] if f[2])

    bars = []
    for i, v in enumerate(values):
        if i >= N - placed:
            style = "good"                          # in its final place
        elif pair and i in pair:
            style = "highlight"
        else:
            style = "muted"
        bars.append({"label": str(i + 1), "value": v, "style": style, "note": str(v)})

    if step == 0:
        what = "Not started"
    elif step == STEPS:
        what = "Sorted"
    else:
        what = ("Swapped %d and %d" if swapped else "Kept %d before %d") % (
            (values[pair[1]], values[pair[0]]) if swapped else (values[pair[0]], values[pair[1]]))
    return {
        "panels": [{
            "kind": "bars", "bars": bars, "y_min": 0, "y_max": 9,
            "title": "Step %d of %d" % (step, STEPS), "x_label": "position",
        }],
        "readouts": [
            {"label": "This step", "value": what},
            {"label": "Comparisons", "value": str(step)},
            {"label": "Swaps so far", "value": str(swaps)},
        ],
    }
