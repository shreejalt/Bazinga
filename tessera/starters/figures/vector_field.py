"""Starter: a field of arrows and a path that follows it (a swinging pendulum).

Copy it with  python -m tessera figure new my_field --from vector_field  and put  ::figure my_field  in a post.

What it shows
-------------
Every arrow shows where a pendulum goes next from that angle and speed. Press Play and a pendulum
released at the chosen angle traces its path through the arrows; with friction the path spirals in.

Things worth copying
--------------------
- **A "scene" panel** is a free 2-D picture made of shapes: "arrow", "line" (with "points"), "point",
  "circle", "polygon", "text". "equal": False lets the two axes have different scales.
- **Stepping an equation forward** (here a few small steps per frame) inside compute(). Change FIELD
  to draw any other system of two equations.
- **Fewer arrows on a phone:** _narrow is 1 there, so the grid is coarser.
"""

import math

TITLE = "A pendulum's arrows"
CAPTION = "Press Play to release the pendulum. Each arrow shows where the swing heads from that point; friction makes it spiral in."
REQUIRES = []

X_MIN, X_MAX = -math.pi, math.pi        # angle (radians)
Y_MIN, Y_MAX = -3.0, 3.0                # speed

CONTROLS = [
    {"name": "t", "kind": "slider", "label": "Time", "min": 0, "max": 20, "step": 0.1, "value": 6, "play": True},
    {"name": "friction", "kind": "slider", "label": "Friction", "min": 0, "max": 1, "step": 0.05, "value": 0.25},
    {"name": "start", "kind": "slider", "label": "Released at (degrees)", "min": 10, "max": 170, "step": 5, "value": 120},
]
PRESETS = [{"label": "No friction", "values": {"friction": 0, "t": 20}}, {"label": "Heavy friction", "values": {"friction": 0.9, "t": 20}}]


def field(x, y, friction):
    """How fast the angle and the speed change at (angle x, speed y)."""
    return y, -math.sin(x) - friction * y


def compute(t=6.0, friction=0.25, start=120, _narrow=0):
    shapes = []
    nx, ny = (9, 7) if _narrow else (15, 9)
    for i in range(nx):
        for j in range(ny):
            x = X_MIN + (X_MAX - X_MIN) * (i + 0.5) / nx
            y = Y_MIN + (Y_MAX - Y_MIN) * (j + 0.5) / ny
            dx, dy = field(x, y, friction)
            size = math.hypot(dx, dy) or 1.0
            k = 0.32 / size                                 # every arrow the same length; direction only
            shapes.append({"type": "arrow", "x1": x, "y1": y, "x2": x + dx * k, "y2": y + dy * k, "style": "faint"})
    # the path: small steps of the equations from the release point
    x, y, dt = math.radians(start), 0.0, 0.05
    path = [[x, y]]
    for _ in range(int(t / dt)):
        dx, dy = field(x, y, friction)
        x, y = x + dx * dt, y + dy * dt
        dx2, dy2 = field(x, y, friction)                    # one correction step keeps the path accurate
        x, y = path[-1][0] + (dx + dx2) * dt / 2, path[-1][1] + (dy + dy2) * dt / 2
        path.append([x, y])
    shapes.append({"type": "line", "points": path, "style": "main"})
    shapes.append({"type": "point", "x": x, "y": y, "r": 6, "style": "highlight"})
    energy = 0.5 * y * y + (1 - math.cos(x))
    return {
        "panels": [{"kind": "scene", "shapes": shapes, "equal": False, "axes": True,
                    "x_min": X_MIN, "x_max": X_MAX, "y_min": Y_MIN, "y_max": Y_MAX,
                    "x_label": "angle", "y_label": "speed"}],
        "readouts": [
            {"label": "Angle now", "value": "%.0f°" % math.degrees(x)},
            {"label": "Energy left", "value": "%.0f%%" % (100 * energy / (1 - math.cos(math.radians(start))))},
        ],
    }
