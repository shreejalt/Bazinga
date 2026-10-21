"""Heads in n tosses

Made with the figure builder (a distribution). Open it in the Editor to change it with the form, or edit
this file by hand: it is an ordinary figure file, and the Editor then opens it as code.

How it works: compute() receives the value of every control and returns a description of the picture
(panels, lines, bars, readouts). The site draws it when the page is built, and again in the reader's
browser each time a control moves, so compute() must be quick and give the same picture for the same
values. Styles are names (main, second, muted, dashed …); the site's theme gives them their colours.
"""

import math

TITLE = "Heads in n tosses"
CAPTION = "The chance of each number of heads. The highlighted counts lie within the chosen number of standard deviations of the mean."
REQUIRES = []

# The controls under the figure, in order. compute() receives each one by its name.
CONTROLS = [
    {"name": "n", "kind": "slider", "label": "Tosses n", "min": 1, "max": 40, "step": 1, "value": 20},
    {"name": "p", "kind": "slider", "label": "Chance of heads p", "min": 0, "max": 1, "step": 0.01, "value": 0.5},
    {"name": "width", "kind": "slider", "label": "Shaded band (± σ)", "min": 0.25, "max": 3, "step": 0.05, "value": 1},
]

PRESETS = []

# The values the variable can take: 0, 1, 2 … K_MAX (wide enough for every slider position).
K_MAX = 40


def pmf(k, n, p):
    """The chance of exactly k successes in n tries."""
    n = int(round(n))
    if k > n:
        return 0.0
    return math.comb(n, k) * p ** k * (1 - p) ** (n - k)


def moments(n, p):
    return n * p, n * p * (1 - p)


def compute(n=20, p=0.5, width=1, _narrow=0):
    # _narrow is 1 when the figure is drawn for a phone.
    mean, variance = moments(n, p)
    std = math.sqrt(variance)
    ks = list(range(K_MAX + 1))
    probs = [pmf(k, n, p) for k in ks]
    heights = probs
    lo, hi = mean - width * std, mean + width * std   # the shaded band
    prob = sum(v for k, v in zip(ks, probs) if lo is not None and hi is not None and lo <= k <= hi)

    series = [{"name": "probability", "x": ks, "y": heights, "style": "main stems", "sizes": [4] * len(ks)}]
    inside = [h if lo is not None and hi is not None and lo <= k <= hi else None for k, h in zip(ks, heights)]
    series.append({"name": "in the band", "x": ks, "y": inside, "style": "highlight stems", "sizes": [5] * len(ks)})
    y_label = "probability"
    return {
        "panels": [{
            "kind": "xy",
            "series": series,
            "y_min": 0,
            "y_label": y_label,
            "x_label": "number of heads",
            "x_min": -0.5,
            "x_max": K_MAX + 0.5,
            "marks": [{"x": mean, "label": "mean", "style": "muted"}],
        }],
        "readouts": [
            {"label": "Mean", "value": _fmt(mean, 2)},
            {"label": "Variance", "value": _fmt(variance, 2)},
            {"label": "Standard deviation", "value": _fmt(std, 2)},
            {"label": "Chance of the band", "value": _fmt(None if prob is None else 100 * prob, 1) + "%", "note": "from " + _fmt(lo, 2) + " to " + _fmt(hi, 2)},
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


# --------------------------------------------------------------------------------------------------------------
# The figure builder's settings. The Editor uses this line to reopen the figure in the builder; once
# the code above is changed by hand, it opens the figure as code instead and leaves this line alone.
# bazinga-builder: {"v":1,"hash":"23cd1c4c4bb41fe0","spec":{"type":"distribution","family":"binomial","title":"Heads in n tosses","caption":"The chance of each number of heads. The highlighted counts lie within the chosen number of standard deviations of the mean.","params":{"n":{"label":"Tosses n","max":40,"value":20},"p":{"label":"Chance of heads p","value":0.5}},"interval":{"mode":"sigma"},"x_label":"number of heads"}}
