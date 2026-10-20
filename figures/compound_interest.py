"""Interest on interest

Made with the figure builder (a function plot). Open it in the Studio to change it with the form, or edit
this file by hand: it is an ordinary figure file, and the Studio then opens it as code.

How it works: compute() receives the value of every control and returns a description of the picture
(panels, lines, bars, readouts). The site draws it when the page is built, and again in the reader's
browser each time a control moves, so compute() must be quick and give the same picture for the same
values. Styles are names (main, second, muted, dashed …); the site's theme gives them their colours.
"""

import math
from math import log

TITLE = "Interest on interest"
CAPTION = "The same 100 saved at the same rate, with and without the interest itself earning interest. The shaded gap is interest on interest."
REQUIRES = []

# The controls under the figure, in order. compute() receives each one by its name.
CONTROLS = [
    {"name": "r", "kind": "slider", "label": "Interest rate (% a year)", "min": 0, "max": 12, "step": 0.5, "value": 5},
]

# Buttons that set several controls at once (Reset is added for you).
PRESETS = [
    {"label": "Savings account", "values": {"r": 2}},
    {"label": "Stock market", "values": {"r": 7}},
]

# Where the curves are drawn: SAMPLES points from X_MIN to X_MAX.
X_MIN, X_MAX, SAMPLES = 0, 30, 121


def compound_at(x, r):
    """compound = 100 (1 + r/100)^x"""
    return 100 * (1 + r / 100) ** x


def simple_at(x, r):
    """simple = 100 (1 + r x/100)"""
    return 100 * (1 + r * x / 100)


def compute(r=5, _narrow=0):
    # _narrow is 1 when the figure is drawn for a phone.
    xs = [X_MIN + (X_MAX - X_MIN) * n / (SAMPLES - 1) for n in range(SAMPLES)]
    # each curve's value at every x (None where it is not defined, which leaves a gap)
    compound = [_value(compound_at, x, r) for x in xs]
    simple = [_value(simple_at, x, r) for x in xs]

    series = []
    series.append({"name": "compound", "x": xs, "y": compound, "base": simple, "style": "main area", "label_at": "none"})
    series.append({"name": "compound", "x": xs, "y": compound, "style": "main"})
    series.append({"name": "simple", "x": xs, "y": simple, "style": "muted dashed"})

    return {
        "panels": [{
            "kind": "xy",
            "series": series,
            "x_min": X_MIN,
            "x_max": X_MAX,
            "x_label": "years",
            "y_label": "balance",
            "y_min": 0,
            "y_max": 3000,
        }],
        "readouts": [
            {"label": "After 30 years", "value": _fmt(_value(lambda: _last(compound)), 0)},
            {"label": "Interest on interest", "value": _fmt(_value(lambda: _last(compound) - _last(simple)), 0)},
            {"label": "Doubles after", "value": _fmt(_value(lambda: log(2) / log(1 + r / 100)), 1) + " years"},
        ],
    }


# --------------------------------------------------------------------------------------------------------------
# Small helpers used above.

def _value(fn, *args):
    """fn(*args) as a plain number, or None where it is not defined (log of 0, 1/0, an overflow …)."""
    try:
        v = fn(*args)
    except (ArithmeticError, ValueError, TypeError):
        return None
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    if not isinstance(v, (int, float)):
        return None
    try:
        v = float(v)
    except OverflowError:
        return None
    return v if math.isfinite(v) else None


def _fmt(v, decimals=None):
    """A number as readable text (− for minus); a dash when it is not defined."""
    if v is None:
        return "—"
    if decimals is not None:
        text = "%.*f" % (decimals, v)
    elif v == 0:
        text = "0"
    elif abs(v) >= 10000:
        text = "{:,.0f}".format(v)
    elif abs(v) >= 0.001:
        text = "%.4g" % v
    else:
        text = "%.2e" % v
    if text.lstrip("-").strip("0.") == "":
        text = text.lstrip("-")
    return text.replace("-", "−")


def _known(ys, xs=None):
    """The (position, value) pairs where a value is defined; positions count from 1 when there is no x."""
    xs = xs if xs is not None else range(1, len(ys) + 1)
    return [(x, y) for x, y in zip(xs, ys) if y is not None and x is not None]


def _last(ys):
    return _known(ys)[-1][1]


# --------------------------------------------------------------------------------------------------------------
# The figure builder's settings. The Studio uses this line to reopen the figure in the builder; once
# the code above is changed by hand, it opens the figure as code instead and leaves this line alone.
# tessera-builder: {"v":1,"hash":"9fcbdfa4efd09a4c","spec":{"type":"function","title":"Interest on interest","caption":"The same 100 saved at the same rate, with and without the interest itself earning interest. The shaded gap is interest on interest.","controls":[{"name":"r","kind":"slider","label":"Interest rate (% a year)","min":0,"max":12,"step":0.5,"value":5}],"curves":[{"name":"compound","label":"compound","expr":"100 (1 + r/100)^x","style":"main","fill":"simple"},{"name":"simple","label":"simple","expr":"100 (1 + r x/100)","style":"muted dashed"}],"x_min":0,"x_max":30,"samples":121,"y_min":0,"y_max":3000,"x_label":"years","y_label":"balance","readouts":[{"label":"After 30 years","expr":"last(compound)","decimals":0},{"label":"Interest on interest","expr":"last(compound) - last(simple)","decimals":0},{"label":"Doubles after","expr":"log(2)/log(1 + r/100)","decimals":1,"unit":"years"}],"presets":[{"label":"Savings account","values":{"r":2}},{"label":"Stock market","values":{"r":7}}]}}
