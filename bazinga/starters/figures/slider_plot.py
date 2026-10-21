"""Starter: a function plot with sliders.

Copy it with  python -m bazinga figure new my_plot --from slider_plot  and put  ::figure my_plot  in a post.

How a figure works
------------------
- The build calls compute() once with the default control values and puts the SVG it draws into the
  page, so the figure shows even without JavaScript.
- When a reader moves a slider, the same compute() runs again in their browser and the picture is
  redrawn. Keep compute() *pure*: same inputs, same output; no files, no network, no randomness
  without a fixed seed.
- compute() returns a plain dict (the "spec"); the site draws it. You never pick colours: you pick
  style names ("main", "second", "muted", ...) and the theme colours them, in light and dark mode.
- Budget: compute() + drawing must take under 30 ms. A few hundred points per line is plenty.
- Test it with  python -m bazinga figure test my_plot
"""

import math

# Shown above the figure, then a one- or two-sentence caption saying what the controls do.
TITLE = "A damped wave"
CAPTION = "Change the frequency and the damping and watch the envelope hold the wave in."

# Extra packages the figure needs, e.g. ["numpy"]. Standard library only loads fastest.
REQUIRES = []

# One entry per control, shown in this order. compute() receives each by its "name".
# A slider gives an int when min, max and step are whole numbers, otherwise a float.
CONTROLS = [
    {"name": "freq", "kind": "slider", "label": "Frequency", "min": 0.5, "max": 6, "step": 0.1, "value": 2},
    {"name": "damping", "kind": "slider", "label": "Damping", "min": 0, "max": 1, "step": 0.02, "value": 0.3},
]

# Optional buttons that set several controls at once. "Reset" is added for you.
PRESETS = [
    {"label": "No damping", "values": {"damping": 0}},
    {"label": "Fast and heavy", "values": {"freq": 5.5, "damping": 0.8}},
]


def compute(freq=2.0, damping=0.3, _narrow=0):
    # _narrow is 1 when the figure is drawn for a phone: you may show less (fewer panels, labels).
    xs = [i / 40 for i in range(0, 401)]                      # 0 .. 10
    wave = [math.exp(-damping * x) * math.cos(freq * x) for x in xs]
    envelope = [math.exp(-damping * x) for x in xs]
    half_life = math.log(2) / damping if damping > 0 else None

    marks = []
    if half_life is not None and half_life <= 10:
        marks.append({"x": half_life, "label": "half-life"})

    return {
        "panels": [{
            "kind": "xy",                    # xy | bars | heatmap | scene
            "x": xs,                         # shared x for every series (a series may bring its own "x")
            "series": [
                # "name" labels the end of the line; "label_at": "none" hides it.
                {"name": "envelope", "y": envelope, "style": "muted dashed"},
                {"name": "wave", "y": wave, "style": "main"},
            ],
            "marks": marks,                  # reference lines: {"x": ...} vertical, {"y": ...} horizontal
            "x_label": "time",
            "y_label": "amplitude",
            "y_min": -1, "y_max": 1,         # fix the axes so the picture does not jump as values change
        }],
        # Number tiles under the figure. Values are text: format them yourself.
        "readouts": [
            {"label": "Half-life", "value": ("%.2f" % half_life) if half_life else "never", "note": "time units"},
            {"label": "Period", "value": "%.2f" % (2 * math.pi / freq)},
        ],
    }
