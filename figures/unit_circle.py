"""Sine and cosine on the circle

Made with the figure builder (a shapes and curves). Open it in the Studio to change it with the form, or edit
this file by hand: it is an ordinary figure file, and the Studio then opens it as code.

How it works: compute() receives the value of every control and returns a description of the picture
(panels, lines, bars, readouts). The site draws it when the page is built, and again in the reader's
browser each time a control moves, so compute() must be quick and give the same picture for the same
values. Styles are names (main, second, muted, dashed …); the site's theme gives them their colours.
"""

import math
from math import cos, radians, sin, pi

TITLE = "Sine and cosine on the circle"
CAPTION = "Move the angle: the point's height is the sine of the angle, its distance across the cosine."
REQUIRES = []

# The controls under the figure, in order. compute() receives each one by its name.
CONTROLS = [
    {"name": "angle", "kind": "slider", "label": "Angle (degrees)", "min": 0, "max": 360, "step": 1, "value": 40, "play": True},
]

PRESETS = []

def compute(angle=40, _narrow=0):
    # _narrow is 1 when the figure is drawn for a phone.
    # values worked out from the controls (None where one is not defined)
    a = _value(lambda: radians(angle))   # radians(angle)

    shapes = []
    t0, t1 = 0, _value(lambda: 2 * pi)
    if t0 is not None and t1 is not None:
        ts = [t0 + (t1 - t0) * n / 119 for n in range(120)]
        pts = [[_value(lambda: cos(t)), _value(lambda: sin(t))] for t in ts]   # x(t), y(t)
        shapes.append({"type": "line", "points": pts, "style": "muted"})
    _add(shapes, {"type": "line", "x1": 0, "y1": 0, "x2": _value(lambda: cos(a)), "y2": _value(lambda: sin(a)), "style": "main"}, ["x1", "y1", "x2", "y2"])
    _add(shapes, {"type": "line", "x1": _value(lambda: cos(a)), "y1": 0, "x2": _value(lambda: cos(a)), "y2": _value(lambda: sin(a)), "style": "second dashed", "label": "sin = " + _fmt(_value(lambda: sin(a)), 2)}, ["x1", "y1", "x2", "y2"])
    _add(shapes, {"type": "point", "x": _value(lambda: cos(a)), "y": _value(lambda: sin(a)), "style": "main", "label": "P"}, ["x", "y"])

    return {
        "panels": [{
            "kind": "scene",
            "shapes": shapes,
            "x_min": -1.5,
            "x_max": 1.5,
            "y_min": -1.5,
            "y_max": 1.5,
            "equal": True,
            "axes": True,
            "origin": True,
        }],
        "readouts": [
            {"label": "sin", "value": _fmt(_value(lambda: sin(a)), 3)},
            {"label": "cos", "value": _fmt(_value(lambda: cos(a)), 3)},
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


def _add(items, shape, needs):
    """Add a shape unless one of its numbers is not defined."""
    if all(shape.get(k) is not None for k in needs) and shape.get("r", 0) >= 0:
        items.append(shape)


# --------------------------------------------------------------------------------------------------------------
# The figure builder's settings. The Studio uses this line to reopen the figure in the builder; once
# the code above is changed by hand, it opens the figure as code instead and leaves this line alone.
# bazinga-builder: {"v":1,"hash":"cc80b8559295816e","spec":{"type":"shapes","title":"Sine and cosine on the circle","caption":"Move the angle: the point's height is the sine of the angle, its distance across the cosine.","controls":[{"name":"angle","kind":"slider","label":"Angle (degrees)","min":0,"max":360,"step":1,"value":40,"play":true}],"values":[{"name":"a","expr":"radians(angle)"}],"items":[{"type":"curve","x":"cos(t)","y":"sin(t)","t_min":"0","t_max":"2*pi","style":"muted"},{"type":"line","x1":"0","y1":"0","x2":"cos(a)","y2":"sin(a)","style":"main"},{"type":"line","x1":"cos(a)","y1":"0","x2":"cos(a)","y2":"sin(a)","style":"second dashed","label":"sin = {sin(a):.2f}"},{"type":"point","x":"cos(a)","y":"sin(a)","style":"main","label":"P"}],"x_min":-1.5,"x_max":1.5,"y_min":-1.5,"y_max":1.5,"axes":true,"origin":true,"readouts":[{"label":"sin","expr":"sin(a)","decimals":3},{"label":"cos","expr":"cos(a)","decimals":3}]}}
