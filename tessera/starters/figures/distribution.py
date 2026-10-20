"""Starter: a normal distribution with the area within k standard deviations shaded.

Copy it with  python -m tessera figure new my_bell --from distribution  and put  ::figure my_bell  in a post.

What it shows
-------------
The bell curve of a normal distribution. The reader moves its mean and its spread, and widens the
shaded band; the readouts give the probability that a value lands in the band.

Things worth copying
--------------------
- **A shaded area under part of a curve**: a second series with the style "area" that only covers the
  x values inside the band. "area" fills down to y = 0 by default; give the series a "base" list to
  fill between two curves instead.
- **A fixed x range** wide enough for every slider position, so the axis never jumps. The y range
  follows the curve here (the peak gets much taller as the spread shrinks).
- **Exact probabilities from the standard library**: math.erf gives the normal CDF, no packages needed.
"""

import math

TITLE = "The normal distribution"
CAPTION = ("Move the mean and the spread, and widen the band: about 68% of the probability lies within "
           "one standard deviation of the mean, 95% within two.")
REQUIRES = []

X_MIN, X_MAX = -10.0, 10.0
SAMPLES = 241                     # points along the curve: plenty for a smooth line, still fast

CONTROLS = [
    {"name": "mean", "kind": "slider", "label": "Mean μ", "min": -4, "max": 4, "step": 0.1, "value": 0},
    {"name": "std", "kind": "slider", "label": "Standard deviation σ", "min": 0.5, "max": 4, "step": 0.1, "value": 1.5},
    {"name": "k", "kind": "slider", "label": "Shade within ±k σ", "min": 0.25, "max": 3, "step": 0.05, "value": 1},
]

PRESETS = [
    {"label": "Standard normal", "values": {"mean": 0, "std": 1, "k": 1}},
    {"label": "Two sigma", "values": {"k": 2}},
    {"label": "Wide and shifted", "values": {"mean": 2, "std": 3}},
]


def pdf(x, mean, std):
    """The height of the bell curve at x."""
    z = (x - mean) / std
    return math.exp(-0.5 * z * z) / (std * math.sqrt(2 * math.pi))


def cdf(x, mean, std):
    """The probability of a value at most x."""
    return 0.5 * (1 + math.erf((x - mean) / (std * math.sqrt(2))))


def compute(mean=0.0, std=1.5, k=1.0, _narrow=0):
    xs = [X_MIN + (X_MAX - X_MIN) * i / (SAMPLES - 1) for i in range(SAMPLES)]
    ys = [pdf(x, mean, std) for x in xs]

    lo, hi = mean - k * std, mean + k * std
    # The band: the curve's points that fall inside [lo, hi], plus the two exact edges so the shading
    # starts and stops precisely there rather than at the nearest sample.
    band_x = [lo] + [x for x in xs if lo < x < hi] + [hi]
    band_y = [pdf(x, mean, std) for x in band_x]
    inside = cdf(hi, mean, std) - cdf(lo, mean, std)

    peak = pdf(mean, mean, std)
    return {
        "panels": [{
            "kind": "xy",
            "series": [
                {"name": "±%.2g σ" % k, "x": band_x, "y": band_y, "style": "main area", "label_at": "none"},
                {"name": "density", "x": xs, "y": ys, "style": "main", "label_at": "none"},
            ],
            "marks": [
                {"x": mean, "label": "μ", "style": "muted"},
                {"x": lo, "style": "faint"},
                {"x": hi, "style": "faint"},
            ],
            "annotations": [{"x": hi, "y": pdf(hi, mean, std), "text": "%.1f%% inside" % (100 * inside)}],
            "x_min": X_MIN, "x_max": X_MAX, "y_min": 0,
            "x_label": "x", "y_label": "probability density",
        }],
        "readouts": [
            {"label": "Probability in the band", "value": "%.1f%%" % (100 * inside),
             "note": "from %.2f to %.2f" % (lo, hi)},
            {"label": "Peak height", "value": "%.3f" % peak, "note": "1 / (σ √(2π))"},
            {"label": "Variance", "value": "%.2f" % (std * std), "note": "σ²"},
        ],
    }
