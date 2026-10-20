"""Starter: an animation driven by a slider with a Play button.

Copy it with  python -m tessera figure new my_animation --from animation

Add "play": True to a slider and a Play button appears next to it. Playing moves the slider from
its current value to the end, redrawing each frame as fast as the reader's device allows. Each frame
is just compute() at that value, so the figure is still a pure function of its controls.
Here: a projectile, with the path so far, the velocity arrow and the height over time.
"""

import math

TITLE = "A thrown ball"
CAPTION = "Press Play to follow the ball. The arrow is its velocity; gravity only changes the vertical part."
REQUIRES = []

G = 9.81

CONTROLS = [
    {"name": "t", "kind": "slider", "label": "Time (s)", "min": 0, "max": 2.5, "step": 0.02, "value": 0.6, "play": True},
    {"name": "angle", "kind": "slider", "label": "Launch angle (degrees)", "min": 10, "max": 80, "step": 1, "value": 50},
]
PRESETS = [{"label": "Start", "values": {"t": 0}}, {"label": "Flat throw", "values": {"angle": 15, "t": 0}}]

SPEED = 12.0


def position(t, vx, vy):
    return vx * t, vy * t - 0.5 * G * t * t


def compute(t=0.6, angle=50, _narrow=0):
    a = math.radians(angle)
    vx, vy = SPEED * math.cos(a), SPEED * math.sin(a)
    flight = 2 * vy / G                         # time until it lands
    t_now = min(t, flight)
    ts = [flight * k / 80 for k in range(81)]
    full = [position(s, vx, vy) for s in ts]
    so_far = [position(s, vx, vy) for s in ts if s <= t_now] + [position(t_now, vx, vy)]
    x, y = position(t_now, vx, vy)
    vy_now = vy - G * t_now
    k = 0.12                                    # arrow length per m/s
    shapes = [
        {"type": "line", "points": [list(p) for p in full], "style": "muted dashed"},
        {"type": "line", "points": [list(p) for p in so_far], "style": "main"},
        {"type": "line", "x1": -1, "y1": 0, "x2": 16, "y2": 0, "style": "ink thin"},     # the ground
        {"type": "arrow", "x1": x, "y1": y, "x2": x + vx * k, "y2": y + vy_now * k, "style": "second"},
        {"type": "point", "x": x, "y": y, "r": 7, "style": "main", "label": "%.1f m high" % y},
    ]
    heights = [position(s, vx, vy)[1] for s in ts]
    return {
        "panels": [
            {"kind": "scene", "title": "Path", "shapes": shapes, "equal": True, "axes": True,
             "x_min": -1, "x_max": 16, "y_min": -0.5, "y_max": 7.5},
            {"kind": "xy", "title": "Height over time", "x": ts,
             "series": [{"name": "height", "y": heights, "style": "muted", "label_at": "none"}],
             "marks": [{"x": t_now, "style": "highlight"}],
             "annotations": [{"x": t_now, "y": y, "text": "now"}],
             "x_min": 0, "x_max": 2.5, "y_min": 0, "y_max": 7.5, "x_label": "seconds", "y_label": "metres"},
        ],
        "widths": [1.4, 1],
        "readouts": [
            {"label": "Time in the air", "value": "%.2f s" % flight},
            {"label": "Lands at", "value": "%.1f m" % (vx * flight)},
        ],
    }
