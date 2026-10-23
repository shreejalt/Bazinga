"""A small 3-D scene kit for figures: points, lines, arrows, polygons, surfaces, curves, planes, axes with ticks,
cameras, labels and annotations in world coordinates, drawn through a viewer that orbits the scene.

Standard library only: the same file runs when the site is built and in the reader's browser (the build ships it
next to the renderer as ``figures/_scene3d.py``; the browser installs it as ``bazinga.scene3d``). A figure imports
it with ``from bazinga import scene3d`` (or ``from bazinga.scene3d import Scene, ...``).

Every 2-D coordinate is computed here. ``Scene.render()`` returns an ordinary figure spec whose one panel has
kind ``"scene3d"``: the projected items in painter's order (farthest first), with every label already placed
(``declutter``). bazinga/plot.py draws that panel; figure.js only turns pointer moves into control values.

    from bazinga.scene3d import Scene

    CONTROLS = [{"name": "view", "kind": "orbit", "value": [35, 25]}]   # drag the picture to turn it

    def compute(view=(35, 25), _narrow=0):
        sc = Scene()                                 # z is up (Scene(up="-y") for the camera convention)
        sc.axes3d(lo=(-1, -1, -1), hi=(1, 1, 1))
        sc.box((-0.5, -0.5, -0.5), (0.5, 0.5, 0.5), faces=True)
        sc.vector((0, 0, 0), (0.8, 0.3, 0.6), label="v")
        return sc.render(view=view, narrow=_narrow, dist=5)

Controls a 3-D figure may use besides slider / steps / toggle:

- ``orbit``  the view, [azimuth, elevation] in degrees. Dragging the background of the picture turns it.
- ``pad``    a number or a short list (a point) moved by dragging a handle; its value is shown under the figure.
- ``hidden`` the same, not shown.

A handle is ``{"name", "control", "at": world point | "p": [x, y] picture units, "inset": name, "hint"}``. When
it is dragged, compute() receives ``_drag = {"handle", "name", "inset", "start", "from", "to"}`` (picture units,
or the inset's own units) and turns it into new values with ``apply_drag(_drag, rules, values, **layout(...))``.
Return the changed values as ``spec["state"]`` (``render(state=...)``) so the controls follow.

Styles are the theme's names: main, second, third, fourth, muted, faint, highlight, good, bad, ink, plus dashed,
dotted, thick, thin. Polygons: plane (translucent, the default), solid, outline, paper (an opaque sheet: an image
plane). Surfaces: surface (coloured by height).

Phones: compute() receives ``_narrow=1``; pass it on (``render(narrow=_narrow)`` or ``layout(_narrow)``). The
picture is then 480 wide, text is larger, and the insets go in rows under the scene.
"""
import math

__all__ = ["Scene", "Flat", "layout", "viewer", "apply_drag", "screen_of", "declutter", "label_report",
           "rig_controls", "rig_from", "camera_handles", "camera_drag_rules", "camera_drag_controls",
           "plot_inset", "fmt", "vec", "sig", "nice_ticks"]

# ----------------------------------------------------------------------------- vectors and 3x3 matrices (lists)

def vadd(a, b): return [a[i] + b[i] for i in range(3)]
def vsub(a, b): return [a[i] - b[i] for i in range(3)]
def vmul(a, s): return [a[i] * s for i in range(3)]
def dot(a, b): return sum(a[i] * b[i] for i in range(3))
def cross(a, b): return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]
def norm(a): return math.sqrt(dot(a, a))
def unit(a):
    n = norm(a) or 1.0
    return [x / n for x in a]
def lerp(a, b, t): return [a[i] + (b[i] - a[i]) * t for i in range(3)]
def mat_vec(M, v): return [dot(M[i], v) for i in range(3)]
def mat_mul(A, B): return [[sum(A[i][k] * B[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
def transpose(M): return [[M[j][i] for j in range(3)] for i in range(3)]
def identity(): return [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]


def rot_x(deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return [[1, 0, 0], [0, c, -s], [0, s, c]]


def rot_y(deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return [[c, 0, s], [0, 1, 0], [-s, 0, c]]


def rot_z(deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return [[c, -s, 0], [s, c, 0], [0, 0, 1]]


def K_matrix(f=500.0, cx=320.0, cy=240.0, s=0.0, fy=None):
    """A pinhole camera's intrinsics: focal length f (pixels), principal point (cx, cy), skew s."""
    return [[f, s, cx], [0.0, f if fy is None else fy, cy], [0.0, 0.0, 1.0]]


def look_at(C, target, up=(0, -1, 0)):
    """The rotation of a camera at C looking at `target`: its rows are the camera's x (right), y (down on the
    picture) and z (forward) axes in world coordinates. `up` is the world's up direction."""
    z = unit(vsub(target, C))
    x = unit(cross(z, list(up)))
    if norm(cross(z, list(up))) < 1e-9:
        x = [1.0, 0.0, 0.0]
    y = cross(z, x)
    return [x, y, z]


def to_camera(R, C, X):
    """Camera coordinates of a world point: X_c = R (X - C)."""
    return mat_vec(R, vsub(X, C))


def project(K, R, C, X):
    """x = K [R | -RC] X for one world point: (u, v, depth), or None when the point is behind the camera."""
    Xc = to_camera(R, C, X)
    if Xc[2] <= 1e-9:
        return None
    x, y = Xc[0] / Xc[2], Xc[1] / Xc[2]
    return (K[0][0] * x + K[0][1] * y + K[0][2], K[1][1] * y + K[1][2], Xc[2])


def backproject(K, R, C, u, v, depth):
    """The world point at `depth` along the ray of pixel (u, v)."""
    y = (v - K[1][2]) / K[1][1]
    x = (u - K[0][2] - K[0][1] * y) / K[0][0]
    return vadd(C, mat_vec(transpose(R), [x * depth, y * depth, depth]))


def ray_plane(origin, direction, plane_point, plane_normal):
    d = dot(direction, plane_normal)
    if abs(d) < 1e-12:
        return None
    t = dot(vsub(plane_point, origin), plane_normal) / d
    return vadd(origin, vmul(direction, t)) if t > 0 else None


def fmt(v, n=2):
    """A number for the page: no trailing zeros, a real minus sign."""
    if v is None:
        return "—"
    if abs(v) < 0.5 * 10 ** (-n):                        # rounds to zero: never print "−0"
        v = 0.0
    s = ("%." + str(n) + "f") % v
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    if s in ("-0", ""):
        s = "0"
    return s.replace("-", "−")


def vec(v, n=2):
    return "(" + ", ".join(fmt(x, n) for x in v) + ")"


def sig(v, n=3):
    """A number with n significant digits (for readouts whose entries span many magnitudes)."""
    if abs(v) < 1e-12:
        return "0"
    if abs(v) < 1e-3 or abs(v) >= 1e5:
        mant, exp = (("%." + str(n - 1) + "e") % v).split("e")
        return (mant + "e" + str(int(exp))).replace("-", "−")
    d = max(0, n - 1 - int(math.floor(math.log10(abs(v)))))
    return fmt(v, d)


def nice_ticks(lo, hi, n=4):
    """About n round numbers between lo and hi."""
    span = hi - lo or 1
    step0 = span / n
    mag = 10 ** math.floor(math.log10(step0))
    step = next((m * mag for m in (1, 2, 2.5, 5, 10) if span / (m * mag) <= n), 10 * mag)
    out, v = [], math.ceil(lo / step - 1e-9) * step
    while v <= hi + step * 1e-6:
        out.append(round(v, 10))
        v += step
    return out


# ----------------------------------------------------------------------------- the viewer (the reader's eye)

# Each world convention: (up, forward at azimuth 0, right). "z": z is up (maths, surfaces). "-y": y points down,
# z forward (the camera convention of computer vision). "y": y is up, z toward the reader (graphics).
UPS = {
    "z": ((0.0, 0.0, 1.0), (0.0, 1.0, 0.0), (1.0, 0.0, 0.0)),
    "-y": ((0.0, -1.0, 0.0), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0)),
    "y": ((0.0, 1.0, 0.0), (0.0, 0.0, -1.0), (1.0, 0.0, 0.0)),
}
WIDE_W, NARROW_W, GAP = 880, 480, 44                    # the renderer's picture widths (bazinga/plot.py)
TEXT_SCALE = {0: 1.1, 1: 1.65}       # scene text is set larger than its nominal size (on phones: 10 -> 16.5)
NEAR = 0.05


def viewer(az, el, dist, target=(0, 0, 0), fov=40.0, width=WIDE_W, height=460, up="z"):
    """The orbiting camera that draws the scene: (K, R, C). az turns around the up axis, el raises the eye."""
    U, F, Rt = UPS.get(up or "z", UPS["z"])
    a, e = math.radians(az), math.radians(el)
    d = [math.cos(e) * (math.sin(a) * Rt[i] - math.cos(a) * F[i]) + math.sin(e) * U[i] for i in range(3)]
    C = [target[i] + dist * d[i] for i in range(3)]
    R = look_at(C, list(target), U)
    f = (height / 2) / math.tan(math.radians(fov) / 2)
    return K_matrix(f, width / 2, height / 2), R, C


def layout(narrow=False, dist=6.0, target=(0, 0, 0), width=None, height=None, fov=40.0, up=None, columns=1,
           narrow_dist=None, narrow_target=None, narrow_height=None):
    """The scene's framing, shared by render() and apply_drag() so a drag lands where the picture was drawn.
    columns: how many panels share the row (wide layout only), so the scene is laid out at its true width.
    On phones (narrow) the picture is 480 wide and may be framed differently (narrow_dist, narrow_target).
    up: the world's up axis, as in Scene(up=...); give it here too ("-y" for cameras) when the figure has drags."""
    narrow = bool(narrow)
    if narrow:
        w = NARROW_W
        h = narrow_height or (max(320, int((height or 460) * 0.85)))
        return dict(narrow=True, dist=narrow_dist or dist * 0.85, target=tuple(narrow_target or target), width=w,
                    height=h, fov=fov, up=up, framed=True)
    w = width or (WIDE_W - GAP * (columns - 1)) / float(columns)
    h = height or int(max(300, min(480, w * 0.52)))
    return dict(narrow=False, dist=dist, target=tuple(target), width=w, height=h, fov=fov, up=up, framed=True)


def _clip(Xa, Xb, R, C, near=NEAR):
    """Clip a world segment at a camera's near plane; return the visible part or None."""
    za, zb = to_camera(R, C, Xa)[2], to_camera(R, C, Xb)[2]
    if za < near and zb < near:
        return None
    if za < near:
        Xa = lerp(Xa, Xb, (near - za) / (zb - za))
    elif zb < near:
        Xb = lerp(Xb, Xa, (near - zb) / (za - zb))
    return Xa, Xb


def _clip_poly(pts, R, C, near=NEAR):
    """Sutherland–Hodgman against a camera's near plane."""
    out = []
    n = len(pts)
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        za, zb = to_camera(R, C, a)[2], to_camera(R, C, b)[2]
        if za >= near:
            out.append(a)
        if (za >= near) != (zb >= near):
            out.append(lerp(a, b, (near - za) / (zb - za)))
    return out


def _finite(v):
    try:
        v = float(v)
    except (TypeError, ValueError, OverflowError):
        return None
    return v if math.isfinite(v) else None


# ----------------------------------------------------------------------------- the scene

class Scene:
    """Items in world coordinates. up: "z" (default), "-y" (cameras: y down, z forward) or "y"."""

    def __init__(self, up="z"):
        if up not in UPS:
            raise ValueError("up must be one of %s" % ", ".join(UPS))
        self.up = up
        self.items = []

    def _add(self, it, hover=None):
        if hover:
            it["hover"] = hover
        self.items.append(it)
        return it

    # ---- primitives
    def point(self, p, label=None, style="main", r=4, fill=True, hover=None):
        return self._add(dict(type="point", p=list(p), label=label, style=style, r=r, fill=fill), hover)

    def line(self, a, b, style="ink", label=None, dash=None, arrow=False, hover=None, w=None):
        return self._add(dict(type="line", pts=[list(a), list(b)], style=style, label=label, dash=dash, arrow=arrow, w=w), hover)

    def path(self, pts, style="ink", closed=False, dash=None, hover=None):
        pts = [list(p) for p in pts]
        for a, b in zip(pts, pts[1:] + ([pts[0]] if closed else [])):
            self.line(a, b, style=style, dash=dash, hover=hover)

    def poly(self, pts, style="plane", label=None, hover=None, opacity=None, split=1):
        """A flat polygon. split=n cuts a four-cornered one into n x n pieces, so it sorts correctly against a
        surface it touches or crosses (the edges of the pieces show, like a grid on the sheet)."""
        if split > 1 and len(pts) == 4:
            a, b, c, d = [list(p) for p in pts]
            n = int(split)
            at = lambda u, v: lerp(lerp(a, b, u), lerp(d, c, u), v)  # noqa: E731
            for i in range(n):
                for j in range(n):
                    self.poly([at(i / n, j / n), at((i + 1) / n, j / n), at((i + 1) / n, (j + 1) / n), at(i / n, (j + 1) / n)],
                              style=style, hover=hover, opacity=opacity)
            if label:
                self.text(at(0.5, 0.5), label, style=style.split()[0] if style else "ink", anchor="middle")
            return None
        it = dict(type="poly", pts=[list(p) for p in pts], style=style, label=label)
        if opacity is not None:
            it["opacity"] = opacity
        return self._add(it, hover)

    def text(self, p, label, style="ink", size=12, anchor="start", dx=0, dy=0):
        return self._add(dict(type="text", p=list(p), label=label, style=style, size=size, anchor=anchor, dx=dx, dy=dy))

    def vector(self, origin, v, label=None, style="main", w=None, hover=None):
        """An arrow from `origin` along v (so it ends at origin + v)."""
        return self.line(origin, vadd(list(origin), list(v)), style=style, label=label, arrow=True, w=w, hover=hover)

    def curve(self, f, t0, t1, n=100, style="main", label=None, chunk=12):
        """A parametric curve t -> f(t) = (x, y, z), sampled n times; a gap where f gives None. It is drawn in short
        pieces so it sorts correctly against surfaces and planes; the label goes at its end."""
        pts = []
        for i in range(n):
            t = t0 + (t1 - t0) * i / (n - 1)
            try:
                q = f(t)
                q = [_finite(c) for c in q] if q is not None else None
            except (ArithmeticError, ValueError, TypeError):
                q = None
            pts.append(q if q and None not in q else None)
        runs, cur = [], []
        for q in pts:
            if q is None:
                if len(cur) > 1:
                    runs.append(cur)
                cur = []
            else:
                cur.append(q)
        if len(cur) > 1:
            runs.append(cur)
        last = None
        for run in runs:
            for k in range(0, len(run) - 1, chunk):
                last = self._add(dict(type="polyline", pts=run[k:k + chunk + 1], style=style, label=None))
        if last is not None and label:
            last["label"] = label
        return runs

    # ---- annotations
    def callout(self, p, label, dx=36, dy=-28, style="ink"):
        """A label on a short leader line from the world point p, offset (dx, dy) picture units."""
        return self._add(dict(type="callout", p=list(p), label=label, style=style, dx=dx, dy=dy))

    def dim(self, a, b, label, style="muted", offset=(0, 0, 0)):
        """A dimension line between two world points, with end ticks and its label at the middle."""
        a, b = vadd(a, offset), vadd(b, offset)
        return self._add(dict(type="dim", pts=[list(a), list(b)], label=label, style=style))

    def arc(self, centre, a, b, label=None, radius=0.5, style="muted", n=16, normal=None):
        """The angle at `centre` from direction (a - centre) to (b - centre), drawn as an arc with a label.
        `normal` fixes the plane of the arc (needed when the two directions are opposite)."""
        u, w = unit(vsub(a, centre)), unit(vsub(b, centre))
        ang = math.acos(max(-1.0, min(1.0, dot(u, w))))
        if ang < 1e-6:
            return None
        k = cross(u, w)
        if normal is not None:
            k = list(normal) if dot(k, normal) >= 0 or norm(k) < 1e-9 else vmul(list(normal), -1.0)
        elif norm(k) < 1e-9:
            k = cross(u, [0, 1, 0]) if abs(u[1]) < 0.9 else cross(u, [1, 0, 0])
        k = unit(k)
        perp = cross(k, u)
        pts = [vadd(centre, vmul(vadd(vmul(u, math.cos(t)), vmul(perp, math.sin(t))), radius)) for t in (ang * i / n for i in range(n + 1))]
        mid = vadd(centre, vmul(vadd(vmul(u, math.cos(ang / 2)), vmul(perp, math.sin(ang / 2))), radius * 1.35))
        return self._add(dict(type="arc", pts=pts, label=label, at=mid, style=style))

    # ---- frames of reference
    def axes(self, length=1.0, origin=(0, 0, 0), labels=("x", "y", "z"), style="muted", R=None):
        """Three arrows from `origin`; with R, the axes of that camera (its rows), else the world's."""
        o = list(origin)
        dirs = R if R else identity()
        for k, lab in enumerate(labels):
            self.line(o, vadd(o, vmul(dirs[k], length)), style=style, label=lab, arrow=True)

    def axes3d(self, lo=(-1, -1, -1), hi=(1, 1, 1), ticks=4, labels=("x", "y", "z"), style="muted", origin=None):
        """Three axes through `origin` (default: 0, kept inside the box lo..hi), each from lo to hi with an arrow,
        its name at the tip and about `ticks` numbered tick marks (0 for none)."""
        o = list(origin) if origin is not None else [min(max(0.0, lo[i]), hi[i]) for i in range(3)]
        span = max(hi[i] - lo[i] for i in range(3)) or 1.0
        for k in range(3):
            pieces = 8                                   # in short pieces, so surfaces hide the right parts
            for m in range(pieces):
                a, b = list(o), list(o)
                a[k] = lo[k] + (hi[k] - lo[k]) * m / pieces
                b[k] = lo[k] + (hi[k] - lo[k]) * (m + 1) / pieces
                last = m == pieces - 1
                self.line(a, b, style=style, label=(labels[k] if labels else None) if last else None, arrow=last)
            if not ticks:
                continue
            side = (k + 1) % 3 if k != 2 else 0           # tick marks lie along another axis
            for t in nice_ticks(lo[k], hi[k], ticks):
                if abs(t - o[k]) < 1e-9 or t >= hi[k] - 1e-9 * span:
                    continue
                p = list(o)
                p[k] = t
                q = list(p)
                q[side] += span * 0.025
                self.line(p, q, style=style)
                q2 = list(p)
                q2[side] -= span * 0.07
                self.text(q2, fmt(t), style="muted", size=10, anchor="middle")

    def grid(self, size=2.0, n=4, level=0.0, style="faint", centre=(0, 0)):
        """A square grid on the ground (the plane through `level` across the up axis): z = level when z is up,
        y = level for the camera convention (y down, so a positive level is below the origin)."""
        h = size / 2
        k_up = {"z": 2, "-y": 1, "y": 1}[self.up]
        i, j = [a for a in range(3) if a != k_up]

        def P(u, v):
            p = [0.0, 0.0, 0.0]
            p[i], p[j], p[k_up] = u, v, level
            return p
        for m in range(n + 1):
            t = -h + m * size / n
            self.line(P(centre[0] - h, centre[1] + t), P(centre[0] + h, centre[1] + t), style=style)
            self.line(P(centre[0] + t, centre[1] - h), P(centre[0] + t, centre[1] + h), style=style)

    def plane(self, point, normal, size=2.0, style="plane", label=None, grid=0):
        """A square piece of the plane through `point` with this normal, `size` across; `grid` lines on it.
        Returns its four corners."""
        nrm = unit(list(normal))
        helper = [0.0, 0.0, 1.0] if abs(nrm[2]) < 0.9 else [1.0, 0.0, 0.0]
        u = unit(cross(nrm, helper))
        w = cross(nrm, u)
        h = size / 2
        P = lambda a, b: vadd(list(point), vadd(vmul(u, a), vmul(w, b)))  # noqa: E731
        corners = [P(-h, -h), P(h, -h), P(h, h), P(-h, h)]
        self.poly(corners, style=style, label=label)
        for m in range(1, grid):
            t = -h + m * size / grid
            self.line(P(t, -h), P(t, h), style="faint")
            self.line(P(-h, t), P(h, t), style="faint")
        return corners

    def box(self, lo, hi, style="ink", faces=False, face_style="plane"):
        """A box between two corners: its 12 edges, and (faces=True) its 6 faces, translucent. Returns the corners."""
        x0, y0, z0 = lo
        x1, y1, z1 = hi
        c = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
        if faces:
            for f in ((0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (2, 3, 7, 6), (1, 2, 6, 5), (0, 3, 7, 4)):
                self.poly([c[i] for i in f], style=face_style)
        for i, j in ((0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4), (0, 4), (1, 5), (2, 6), (3, 7)):
            self.line(c[i], c[j], style=style)
        return c

    def surface(self, f, x=(-2, 2), y=(-2, 2), n=18, z_range=None, style="surface", mesh=True):
        """The surface z = f(x, y) over the rectangle x by y, as n x n small faces coloured by height (sorted far to
        near, so it hides itself correctly). f may return None where it is not defined (a hole). z_range = (lo, hi)
        fixes the colours and cuts the surface off there, so the picture does not jump as sliders move. Use it with
        the default Scene(up="z"). Returns {"lo", "hi", "z": rows of values}."""
        nx = ny = max(2, int(n))
        xs = [x[0] + (x[1] - x[0]) * i / nx for i in range(nx + 1)]
        ys = [y[0] + (y[1] - y[0]) * j / ny for j in range(ny + 1)]
        Z = []
        for yy in ys:
            row = []
            for xx in xs:
                try:
                    row.append(_finite(f(xx, yy)))
                except (ArithmeticError, ValueError, TypeError):
                    row.append(None)
            Z.append(row)
        known = [v for row in Z for v in row if v is not None]
        if not known:
            return {"lo": None, "hi": None, "z": Z}
        lo, hi = z_range if z_range else (min(known), max(known))
        if hi - lo < 1e-12:
            hi = lo + 1.0
        for j in range(ny):
            for i in range(nx):
                q = (Z[j][i], Z[j][i + 1], Z[j + 1][i + 1], Z[j + 1][i])
                if None in q:
                    continue
                q = [min(max(v, lo), hi) for v in q]
                pts = [[xs[i], ys[j], q[0]], [xs[i + 1], ys[j], q[1]], [xs[i + 1], ys[j + 1], q[2]], [xs[i], ys[j + 1], q[3]]]
                t = (sum(q) / 4 - lo) / (hi - lo)
                self.items.append(dict(type="face", pts=pts, style=style, shade=round(min(1.0, max(0.0, t)), 2),
                                       mesh=bool(mesh)))
        return {"lo": lo, "hi": hi, "z": Z}

    # ---- cameras (use with Scene(up="-y"): x right, y down, z forward)
    def camera(self, R, C, K=None, depth=1.0, label=None, style="ink", image=True, axes=False, principal=True,
               sub="", frame=None):
        """A pinhole camera: centre C, rotation R (rows are its x, y, z axes), and its image plane drawn `depth`
        world units in front of the centre with the sensor's true shape (from K, or frame=(width, height) pixels).
        Returns a dict with the plane's corners, used by on_image() and ray()."""
        K = K or K_matrix()
        w, h = frame if frame else (2 * K[0][2], 2 * K[1][2])
        corners = [backproject(K, R, C, u, v, depth) for u, v in ((0, 0), (w, 0), (w, h), (0, h))]
        if image:
            self.poly(corners, style="paper")
        for c in corners:
            self.line(C, c, style="faint")
        self.point(C, label=label, style=style, r=4)
        pp = backproject(K, R, C, K[0][2], K[1][2], depth)
        if principal:
            self.line(C, backproject(K, R, C, K[0][2], K[1][2], depth * 1.8), style="muted", dash="3 3")
            self.point(pp, style="muted", r=2.2)
        if axes:
            self.axes(0.35, origin=C, labels=("x" + sub, "y" + sub, "z" + sub), style=style, R=R)
        return dict(R=R, C=list(C), K=K, depth=depth, corners=corners, principal=pp)

    def on_image(self, cam, X):
        """Where the world point X meets the drawn image plane of `cam` (world coordinates), or None if behind."""
        q = project(cam["K"], cam["R"], cam["C"], X)
        if q is None:
            return None
        return backproject(cam["K"], cam["R"], cam["C"], q[0], q[1], cam["depth"])

    def ray(self, X, cam, style="second dashed", label=None, extend=0.0):
        """The ray from a world point to a camera centre, split where it crosses the image plane so the painter's
        order stays right; returns the crossing (None when X is behind the camera)."""
        hit = self.on_image(cam, X)
        C = cam["C"]
        if hit is None:
            self.line(X, C, style="bad dotted")
            return None
        self.line(X, hit, style=style, label=label)
        self.line(hit, C, style=style)
        if extend:
            self.line(X, vadd(X, vmul(unit(vsub(X, C)), extend)), style=style + " dotted")
        return hit

    def image_view(self, K, R, C, points=(), lines=(), polys=(), title="The camera sees", name="cam", w=240, h=180,
                   place="tr", ticks=True, cross=True, zoom=1.0, frame=None):
        """A small 2-D picture of what a camera sees, shown beside the scene: its frame scaled to w x h, the
        principal point, and the given world points (label, X, style), segments (a, b, style[, label]) and
        polygons (pts, style) projected. A point outside the frame becomes an arrow at the edge with its pixel
        written beside it; a point behind the camera is named in the title. Returns an inset for render(insets=)."""
        W, H = frame if frame else (2 * K[0][2], 2 * K[1][2])
        RW, RH = W * zoom, H * zoom
        u0, v0 = W / 2 - RW / 2, H / 2 - RH / 2
        sx, sy = w / RW, h / RH
        items, behind, pix = [], [], {}

        def S(u, v):
            return [round((u - u0) * sx, 1), round((v - v0) * sy, 1)]

        items.append(dict(type="poly", pts=[S(0, 0), S(W, 0), S(W, H), S(0, H)], style="paper"))
        if cross:
            cx, cy = S(K[0][2], K[1][2])
            items.append(dict(type="line", pts=[[cx - 5, cy], [cx + 5, cy]], style="muted"))
            items.append(dict(type="line", pts=[[cx, cy - 5], [cx, cy + 5]], style="muted"))
        for pts, st in polys:
            q = [project(K, R, C, p) for p in pts]
            if all(q):
                items.append(dict(type="poly", pts=[S(a[0], a[1]) for a in q], style=st))
        for entry in lines:
            a, b, st = entry[0], entry[1], entry[2]
            lab = entry[3] if len(entry) > 3 else None
            seg = _clip(list(a), list(b), R, C, near=1e-3)
            if not seg:
                continue
            qa, qb = project(K, R, C, seg[0]), project(K, R, C, seg[1])
            if qa and qb:
                cl = _clip2(qa[0] - u0, qa[1] - v0, qb[0] - u0, qb[1] - v0, RW, RH)
                if cl:
                    items.append(dict(type="line", pts=[[round(cl[0] * sx, 1), round(cl[1] * sy, 1)],
                                                        [round(cl[2] * sx, 1), round(cl[3] * sy, 1)]], style=st, label=lab))
        for entry in points:
            lab, X, st = entry[0], entry[1], entry[2]
            q = project(K, R, C, X)
            if q is None:
                behind.append(lab)
                continue
            pix[lab] = (q[0], q[1])
            if u0 <= q[0] <= u0 + RW and v0 <= q[1] <= v0 + RH:
                items.append(dict(type="point", p=S(q[0], q[1]), style=st, r=3.5, label=lab,
                                  hover="%s = (%s, %s) px" % (lab, fmt(q[0], 1), fmt(q[1], 1))))
            else:
                items.extend(_edge_arrow(lab, q[0], q[1], (u0, v0, RW, RH), (sx, sy), st))
        return dict(name=name, title=title + (" (behind it: %s)" % ", ".join(behind) if behind else ""), w=w, h=h,
                    frame=[W, H], items=items, place=place, ticks=ticks and zoom == 1.0, scale=[sx, sy], origin=[u0, v0],
                    pixels=pix)

    def as_inset(self, rendered, name, title, w=220, h=150, place="row"):
        """A whole rendered scene (its panel: render(...)["panels"][0]) shrunk into an inset."""
        k = min(w / rendered["width"], h / rendered["scene_h"])
        items = []
        for it in rendered["items"]:
            it = dict(it)
            for key in ("p", "at"):
                if key in it:
                    it[key] = [round(it[key][0] * k, 1), round(it[key][1] * k, 1)]
            if "pts" in it:
                it["pts"] = [[round(p[0] * k, 1), round(p[1] * k, 1)] for p in it["pts"]]
            it.pop("L", None)
            if it.get("label"):
                it["size"] = max(9.0, round((it.get("size") or 12) * max(k, 0.75), 1))
            if "dx" in it:
                it["dx"], it["dy"] = round(it["dx"] * k, 1), round(it["dy"] * k, 1)
            items.append(it)
        return dict(name=name, title=title, w=w, h=h, frame=[w, h], items=items, place=place, ticks=False,
                    scale=[k, k], origin=[0, 0])

    # ---- the render
    def render(self, view=(35.0, 25.0), readouts=None, note=None, insets=None, handles=None, state=None, **kw):
        """The figure spec: {"panels": [the scene panel], "readouts", "note", "state"}. Takes the framing as
        keywords (dist, target, fov, width, height, up, narrow) or as **layout(...)."""
        spec = {"panels": [self.panel(view=view, insets=insets, handles=handles, **kw)], "readouts": readouts or []}
        if note:
            spec["note"] = note
        if state:
            spec["state"] = state
        return spec

    def panel(self, view=(35.0, 25.0), insets=None, handles=None, narrow=False, dist=6.0, target=(0, 0, 0),
              fov=40.0, width=None, height=None, up=None, columns=1, near=NEAR, framed=False, **_ignored):
        """Just the scene panel, to put beside other panels: {"panels": [sc.panel(..., columns=2), {...}]}."""
        if framed:                                       # **layout(...): use its framing as it is
            lay = dict(narrow=bool(narrow), dist=dist, target=tuple(target), width=width, height=height, fov=fov,
                       up=up or self.up)
        else:
            lay = layout(narrow, dist=dist, target=target, width=width, height=height, fov=fov, up=up or self.up,
                         columns=columns)
        narrow, width, height = lay["narrow"], lay["width"], lay["height"]
        ts = TEXT_SCALE[1 if narrow else 0]
        view = [float(view[0]), float(view[1])]
        K, R, C = viewer(view[0], view[1], lay["dist"], lay["target"], fov, width, height, lay["up"])

        def P(p):
            q = project(K, R, C, p)
            return None if q is None else [round(q[0], 1), round(q[1], 1), q[2]]

        out = []
        for it in self.items:
            t = it["type"]
            if t in ("point", "text", "callout"):
                q = P(it["p"])
                if q:
                    out.append(dict(it, p=q[:2], depth=q[2]))
            elif t in ("line", "dim"):
                seg = _clip(it["pts"][0], it["pts"][1], R, C, near=near)
                if seg:
                    qa, qb = P(seg[0]), P(seg[1])
                    if qa and qb:
                        out.append(dict(it, pts=[qa[:2], qb[:2]], depth=(qa[2] + qb[2]) / 2))
            elif t == "polyline":
                run, ds = [], []
                for a, b in zip(it["pts"], it["pts"][1:]):
                    seg = _clip(a, b, R, C, near=near)
                    if not seg:
                        continue
                    qa, qb = P(seg[0]), P(seg[1])
                    if qa and qb:
                        if not run:
                            run.append(qa[:2])
                        run.append(qb[:2])
                        ds.append((qa[2] + qb[2]) / 2)
                if len(run) > 1:
                    out.append(dict(it, pts=run, depth=sum(ds) / len(ds)))
            elif t == "arc":
                qs = [P(p) for p in it["pts"]]
                at = P(it["at"])
                if all(qs) and at:
                    out.append(dict(it, pts=[q[:2] for q in qs], at=at[:2], depth=sum(q[2] for q in qs) / len(qs)))
            else:                                        # a polygon or a face: clipped at the viewer's near plane
                pts = _clip_poly(it["pts"], R, C, near=near)
                qs = [P(p) for p in pts]
                if len(qs) >= 3 and all(qs):
                    out.append(dict(it, pts=[q[:2] for q in qs], depth=sum(q[2] for q in qs) / len(qs)))
        for it in out:                                    # an arrow seen end-on has no room for its name
            if it["type"] == "line" and it.get("arrow") and it.get("label"):
                (ax, ay), (bx, by) = it["pts"][0], it["pts"][-1]
                if math.hypot(bx - ax, by - ay) < 12:
                    it.pop("label", None)
        # geometry in painter's order (farthest first); annotations, points and labels on top of it
        layer = {"dim": 0, "point": 1, "text": 2, "callout": 3}
        back = sorted((it for it in out if it["type"] not in layer), key=lambda it: -it["depth"])
        front = sorted((it for it in out if it["type"] in layer), key=lambda it: (layer[it["type"]], -it["depth"]))
        out = back + front
        insets = [dict(n) for n in (insets or [])]
        total_h = _place_insets(insets, width, height, narrow)
        declutter(out, width, height, ts, [n["box"] for n in insets if not n.get("below")])
        for n in insets:
            declutter(n["items"], n["w"], n["h"], 1.0)
        cw = CHAR * 12 * ts
        for it in out:                                   # keep callout text inside the picture
            if it["type"] == "callout":
                tw = cw * len(str(it["label"]))
                x0, y0 = it["p"]
                if (it["dx"] >= 0 and x0 + it["dx"] + tw > width - 6) or (it["dx"] < 0 and x0 + it["dx"] - tw < 6):
                    it["dx"] = -it["dx"]
                ty = y0 + it["dy"]
                if ty < 14 or ty > height - 6:
                    it["dy"] = -it["dy"]
        for it in out:
            it["depth"] = round(it["depth"], 3)
        hs = []
        pos = {n["name"]: n for n in insets}
        for h in handles or []:
            h = dict(h)
            if "at" in h:                                # a handle given as a world point
                q = P(h.pop("at"))
                h["p"] = q[:2] if q else None
            if not h.get("p"):
                continue
            h.setdefault("control", h.get("name"))
            n = pos.get(h.get("inset"))
            h["P"] = [round(n["x"] + h["p"][0] * n["s"], 1), round(n["y"] + h["p"][1] * n["s"], 1)] if n else list(h["p"])
            hs.append(h)
        return dict(kind="scene3d", width=width, height=total_h, scene_h=height, items=out, insets=insets, handles=hs,
                    view=view, text_scale=ts, narrow=narrow)


def _place_insets(insets, W0, H0, narrow):
    """Where each inset goes (x, y, scale s), as the renderer draws it: overlaid at the top right (or tl, bl, br)
    on wide pictures, in rows under the scene (place="row", and always on phones). Returns the panel's height."""
    total, x = H0, W0
    rows = [n for n in insets if narrow or n.get("place") == "row"]
    ticked = any(n.get("ticks") for n in rows)
    lead, gap = (30 if ticked else 0), (34 if ticked else 14)
    for j, n in enumerate(insets):
        w, h, t = n["w"], n["h"], n.get("ticks")
        if n in rows:
            if narrow:
                s = min(1.4, (W0 - 60) / w)
                ix, iy = (W0 - w * s) / 2, total + 30
                total = iy + h * s + (18 if t else 8)
            else:
                k = rows.index(n)
                s = min(1.2, (W0 - lead - gap * (len(rows) - 1)) / len(rows) / w)
                ix, iy = lead + k * (w * s + gap), H0 + 30
                total = max(total, iy + h * s + (18 if t else 8))
            n["below"] = True
        else:
            s = 1.0
            pl = n.get("place", "tr")
            if pl == "tl":
                k = [m for m in insets if m.get("place") == "tl"].index(n)
                ix, iy = 34 + k * (w + 44), 26
            elif pl == "bl":
                ix, iy = 34, H0 - h - (26 if t else 12)
            elif pl == "br":
                ix, iy = W0 - w - 10, H0 - h - (26 if t else 12)
            else:
                x -= w + 12
                ix, iy = x, 26
            n["below"] = False
        n["x"], n["y"], n["s"] = round(ix, 1), round(iy, 1), round(s, 3)
        n["box"] = (ix - (30 if t else 4), iy - 20, ix + w * s + 4, iy + h * s + (20 if t else 4))
    return int(math.ceil(total))


def _clip2(x0, y0, x1, y1, W, H):
    """Liang–Barsky: the part of a 2-D segment inside [0, W] x [0, H], or None."""
    dx, dy = x1 - x0, y1 - y0
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, x0), (dx, W - x0), (-dy, y0), (dy, H - y0)):
        if abs(p) < 1e-12:
            if q < 0:
                return None
        else:
            r = q / p
            if p < 0:
                t0 = max(t0, r)
            else:
                t1 = min(t1, r)
            if t0 > t1:
                return None
    return (x0 + t0 * dx, y0 + t0 * dy, x0 + t1 * dx, y0 + t1 * dy)


def _edge_arrow(label, u, v, region, scale, style="ink"):
    """A point outside an inset's region: an arrow at the edge pointing toward it, with its pixel written beside."""
    u0, v0, RW, RH = region
    sx, sy = scale
    cu, cv = u0 + RW / 2, v0 + RH / 2
    du, dv = u - cu, v - cv
    t = min((RW / 2 - 4 / sx) / abs(du) if du else 1e9, (RH / 2 - 4 / sy) / abs(dv) if dv else 1e9)
    eu, ev = cu + du * t, cv + dv * t
    n = math.hypot(du * sx, dv * sy) or 1
    tip = [round((eu - u0) * sx, 1), round((ev - v0) * sy, 1)]
    tail = [round(tip[0] - du * sx / n * 16, 1), round(tip[1] - dv * sy / n * 16, 1)]
    w, h = RW * sx, RH * sy
    anchor = "end" if tip[0] > w * 0.6 else "start"
    lx = tip[0] - 4 if anchor == "end" else tip[0] + 4
    ly = min(max(tip[1] + (17 if tip[1] < h / 2 else -11), 11), h - 3)
    return [dict(type="line", pts=[tail, tip], style=style, arrow=True),
            dict(type="text", p=[lx, ly], label="%s (%s, %s)" % (label, fmt(u, 0), fmt(v, 0)), style=style, size=10.5,
                 anchor=anchor)]


def plot_inset(name, xs, series, x_label="", y_label="", marker=None, w=240, h=160, title="", place="row",
               x_range=None, y_range=None):
    """A small line plot as an inset: series = [(label, ys, style)], marker = (x, label)."""
    x0, x1 = x_range or (min(xs), max(xs))
    allv = [v for _, ys, _ in series for v in ys if v is not None]
    y0, y1 = y_range or ((min(allv), max(allv)) if allv else (0, 1))
    if y1 - y0 < 1e-12:
        y1 = y0 + 1
    if x1 - x0 < 1e-12:
        x1 = x0 + 1
    L, B, T, Rm = 34, 22, 8, 8
    X = lambda x: L + (x - x0) / (x1 - x0) * (w - L - Rm)  # noqa: E731
    Y = lambda y: h - B - (min(max(y, y0), y1) - y0) / (y1 - y0) * (h - B - T)  # noqa: E731
    items = [dict(type="poly", pts=[[0, 0], [w, 0], [w, h], [0, h]], style="paper"),
             dict(type="line", pts=[[L, T], [L, h - B]], style="muted"),
             dict(type="line", pts=[[L, h - B], [w - Rm, h - B]], style="muted")]
    for t in nice_ticks(y0, y1, 3):
        items += [dict(type="line", pts=[[L - 3, round(Y(t), 1)], [L, round(Y(t), 1)]], style="muted"),
                  dict(type="tick", p=[L - 5, round(Y(t) + 3, 1)], label=fmt(t, 2), style="muted", size=9.5, anchor="end")]
    for t in nice_ticks(x0, x1, 4):
        items += [dict(type="line", pts=[[round(X(t), 1), h - B], [round(X(t), 1), h - B + 3]], style="muted"),
                  dict(type="tick", p=[round(X(t), 1), h - B + 13], label=fmt(t, 2), style="muted", size=9.5, anchor="middle")]
    for lab, ys, st in series:
        pts = [[round(X(x), 1), round(Y(y), 1)] for x, y in zip(xs, ys) if y is not None]
        if len(pts) > 1:
            items.append(dict(type="polyline", pts=pts, style=st))
    if marker:
        mx, mlab = marker[0], marker[1]
        items.append(dict(type="line", pts=[[round(X(mx), 1), T], [round(X(mx), 1), h - B]], style="faint", dash="2 3"))
        for lab, ys, st in series:
            k = min(range(len(xs)), key=lambda i: abs(xs[i] - mx))
            if ys[k] is not None:
                items.append(dict(type="point", p=[round(X(xs[k]), 1), round(Y(ys[k]), 1)], style=st, r=3.5))
        if mlab:
            right = X(mx) < w - Rm - 7 * len(mlab) - 6
            items.append(dict(type="tick", p=[round(X(mx) + (4 if right else -4), 1), T + 10], label=mlab, style="ink",
                              size=10.5, anchor="start" if right else "end"))
    if x_label:
        items.append(dict(type="tick", p=[w - Rm, h - B - 4], label=x_label, style="muted", size=9.5, anchor="end"))
    if y_label:
        items.append(dict(type="tick", p=[L + 4, T + 9], label=y_label, style="muted", size=9.5, anchor="start"))
    return dict(name=name, title=title, w=w, h=h, frame=[w, h], items=items, place=place, ticks=False, scale=[1, 1],
                origin=[0, 0])


class Flat:
    """The same items in plain 2-D picture coordinates (no projection): `scale` maps units to picture units."""

    def __init__(self, width=WIDE_W, height=380, scale=1.0, origin=(0, 0), narrow=False):
        self.items, self.width, self.height, self.scale, self.origin = [], width, height, scale, origin
        self.narrow = bool(narrow)

    def P(self, p):
        return [round(self.origin[0] + p[0] * self.scale, 1), round(self.origin[1] + p[1] * self.scale, 1)]

    def point(self, p, label=None, style="main", r=4, fill=True, hover=None):
        it = dict(type="point", p=self.P(p), label=label, style=style, r=r, fill=fill)
        if hover:
            it["hover"] = hover
        self.items.append(it)

    def line(self, a, b, style="ink", label=None, dash=None, arrow=False, w=None):
        self.items.append(dict(type="line", pts=[self.P(a), self.P(b)], style=style, label=label, dash=dash, arrow=arrow, w=w))

    def path(self, pts, style="ink", closed=False, dash=None, w=None):
        pts = list(pts) + ([pts[0]] if closed else [])
        self.items.append(dict(type="polyline", pts=[self.P(p) for p in pts], style=style, dash=dash, w=w))

    def poly(self, pts, style="plane", label=None, opacity=None):
        it = dict(type="poly", pts=[self.P(p) for p in pts], style=style, label=label)
        if opacity is not None:
            it["opacity"] = opacity
        self.items.append(it)

    def text(self, p, label, style="ink", size=12, anchor="start", dx=0, dy=0):
        self.items.append(dict(type="text", p=self.P(p), label=label, style=style, size=size, anchor=anchor, dx=dx, dy=dy))

    def callout(self, p, label, dx=36, dy=-28, style="ink"):
        self.items.append(dict(type="callout", p=self.P(p), label=label, style=style, dx=dx, dy=dy))

    def dim(self, a, b, label, style="muted"):
        self.items.append(dict(type="dim", pts=[self.P(a), self.P(b)], label=label, style=style))

    def render(self, readouts=None, note=None, handles=None, state=None, insets=None):
        ts = TEXT_SCALE[1 if self.narrow else 0]
        insets = [dict(n) for n in (insets or [])]
        total = _place_insets(insets, self.width, self.height, self.narrow)
        declutter(self.items, self.width, self.height, ts, [n["box"] for n in insets if not n.get("below")])
        for n in insets:
            declutter(n["items"], n["w"], n["h"], 1.0)
        hs = []
        for h in handles or []:
            h = dict(h)
            h.setdefault("control", h.get("name"))
            h["P"] = list(h["p"])
            hs.append(h)
        spec = {"panels": [dict(kind="scene3d", width=self.width, height=total, scene_h=self.height, items=self.items,
                                insets=insets, handles=hs, view=None, text_scale=ts, narrow=self.narrow)],
                "readouts": readouts or []}
        if note:
            spec["note"] = note
        if state:
            spec["state"] = state
        return spec


# ----------------------------------------------------------------------------- dragging

def screen_of(view, p, dist=6.0, target=(0, 0, 0), fov=40.0, width=WIDE_W, height=460, up="z", **_ignored):
    """Where a world point lands in the scene picture (or None when it is behind the viewer)."""
    K, R, C = viewer(view[0], view[1], dist, target, fov, width, height, up)
    q = project(K, R, C, p)
    return None if q is None else [round(q[0], 1), round(q[1], 1)]


def apply_drag(drag, rules, values, dist=6.0, target=(0, 0, 0), fov=40.0, width=WIDE_W, height=460, up="z",
               view_name="view", **_ignored):
    """Turn a pointer drag into new control values. drag = {"handle", "name", "start", "from", "to"} in picture
    units (an inset's own units for a handle in an inset). rules[handle or control name] is one of
        ("plane", point, normal[, axes])   a world point dragged within a plane through `point` (keeps the grab
                                           offset); `axes` picks which world coordinates the value holds, e.g. (0, 2)
        ("inset", inset[, (u_min, v_min, u_max, v_max)])   a pixel dragged inside a camera's picture
        ("slider", "u"|"v", scale[, lo, hi])   one number driven by horizontal or vertical motion
        ("orbit",)                         the view itself: [azimuth, elevation]
    `values` holds the current values (values[view_name] is the view); returns an updated copy."""
    if not drag:
        return values
    key = drag.get("handle") if drag.get("handle") in rules else drag.get("name")
    if key not in rules:
        return values
    name, rule = drag.get("name") or key, rules[key]
    start, a, b = drag.get("start"), drag["from"], drag["to"]
    out = dict(values)
    if rule[0] == "orbit":
        az0, el0 = start if isinstance(start, (list, tuple)) else values[view_name]
        out[name] = [az0 - 0.4 * (b[0] - a[0]), max(-89.0, min(89.0, el0 + 0.4 * (b[1] - a[1])))]
    elif rule[0] == "inset":
        sx, sy = rule[1]["scale"]
        new = [start[0] + (b[0] - a[0]) / sx, start[1] + (b[1] - a[1]) / sy]
        if len(rule) > 2:
            lo_u, lo_v, hi_u, hi_v = rule[2]
            new = [max(lo_u, min(hi_u, new[0])), max(lo_v, min(hi_v, new[1]))]
        out[name] = new
    elif rule[0] == "plane":
        view = values.get(view_name) or [35, 25]
        K, R, C = viewer(view[0], view[1], dist, target, fov, width, height, up)

        def ray(s):
            return mat_vec(transpose(R), [(s[0] - K[0][2]) / K[0][0], (s[1] - K[1][2]) / K[1][1], 1.0])
        nrm = unit(list(rule[2]))
        pa, pb = ray_plane(C, ray(a), rule[1], nrm), ray_plane(C, ray(b), rule[1], nrm)
        if pa and abs(dot(unit(ray(a)), nrm)) < 0.5:
            # the plane is seen almost edge-on, where a small move of the pointer would throw the point far away:
            # move it on a plane facing the eye instead, then keep only the part of the move that lies in the plane
            qa, qb = ray_plane(C, ray(a), pa, R[2]), ray_plane(C, ray(b), pa, R[2])
            if qa and qb:
                m = vsub(qb, qa)
                pb = vadd(pa, vsub(m, vmul(nrm, dot(m, nrm))))
        if pa and pb:
            moved = vsub(pb, pa)
            st = list(start) if isinstance(start, (list, tuple)) else [start]
            axes = rule[3] if len(rule) > 3 else (0, 1, 2)[:len(st)]
            out[name] = [st[k] + moved[axes[k]] for k in range(len(st))]
    elif rule[0] == "slider":
        k = 0 if rule[1] == "u" else 1
        v = start + (b[k] - a[k]) * rule[2]
        if len(rule) > 4:
            v = max(rule[3], min(rule[4], v))
        out[name] = v
    return out


# ----------------------------------------------------------------------------- label placement

CHAR = 0.62                     # a character's width in em (errs wide: figure text may be set in a monospace)


def _box(x, y, text, size, anchor, lines=None):
    rows = lines or [str(text)]
    w = CHAR * size * max(len(r) for r in rows)
    x0 = x if anchor == "start" else (x - w if anchor == "end" else x - w / 2)
    return (x0, y - size * 0.82, x0 + w, y + size * 0.22 + (len(rows) - 1) * size * 1.15)


def _wrap(text, size, maxw):
    words, rows, cur = str(text).split(" "), [], ""
    for wd in words:
        t = (cur + " " + wd).strip()
        if cur and CHAR * size * len(t) > maxw:
            rows.append(cur)
            cur = wd
        else:
            cur = t
    rows.append(cur)
    return rows


def _hit(a, b, pad=1.5):
    return not (a[2] + pad <= b[0] or b[2] + pad <= a[0] or a[3] + pad <= b[1] or b[3] + pad <= a[1])


def _seg_hits_box(p, q, b):
    return _clip2(p[0] - b[0], p[1] - b[1], q[0] - b[0], q[1] - b[1], b[2] - b[0], b[3] - b[1]) is not None


def _base_size(it):
    return it.get("size") or (13 if it["type"] == "point" else 12)


def _candidates(it, size):
    """Positions to try for an item's label, best first: (x, y, anchor)."""
    t = it["type"]
    if t == "point":
        x, y = it["p"]
        d = (it.get("r") or 4) + 4
        return [(x + d, y - d, "start"), (x + d, y + d + size * 0.6, "start"), (x - d, y - d, "end"), (x - d, y + d + size * 0.6, "end"),
                (x, y - d - 3, "middle"), (x, y + d + size * 0.8, "middle"), (x + d + 2, y + size * 0.3, "start"), (x - d - 2, y + size * 0.3, "end"),
                (x + 2 * d, y - 2 * d, "start"), (x - 2 * d, y - 2 * d, "end"), (x + 2 * d, y + 2 * d + size * 0.6, "start"), (x - 2 * d, y + 2 * d + size * 0.6, "end")]
    if t in ("line", "polyline"):
        e, b = it["pts"][-1], it["pts"][-2] if len(it["pts"]) > 1 else it["pts"][-1]
        dx, dy = e[0] - b[0], e[1] - b[1]
        n = math.hypot(dx, dy) or 1
        ux, uy = dx / n, dy / n
        out = [(e[0] + ux * k, e[1] + uy * k + size * 0.35, "middle") for k in (11, 18, 28)]
        for side in (1, -1):
            out.append((e[0] - uy * 10 * side - ux * 6, e[1] + ux * 10 * side - uy * 6 + size * 0.35, "middle"))
        m = [(b[0] + e[0]) / 2, (b[1] + e[1]) / 2]
        for side in (1, -1):
            out.append((m[0] - uy * 12 * side, m[1] + ux * 12 * side + size * 0.35, "middle"))
        for f in (0.75, 0.25):
            q = [b[0] + (e[0] - b[0]) * f, b[1] + (e[1] - b[1]) * f]
            for side in (1, -1):
                out.append((q[0] - uy * 14 * side, q[1] + ux * 14 * side + size * 0.35, "middle"))
        return out
    if t == "dim":
        a, b = it["pts"]
        dx, dy = b[0] - a[0], b[1] - a[1]
        n = math.hypot(dx, dy) or 1
        nx, ny = -dy / n, dx / n
        m = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2]
        out = [(m[0] + nx * k, m[1] + ny * k + size * 0.35, "middle") for k in (13, -13, 24, -24, 36, -36)]
        for f in (0.25, 0.75):
            q = [a[0] + dx * f, a[1] + dy * f]
            out += [(q[0] + nx * 14, q[1] + ny * 14 + size * 0.35, "middle"), (q[0] - nx * 14, q[1] - ny * 14 + size * 0.35, "middle")]
        return out
    if t == "arc":
        x, y = it["at"]
        c = it["pts"][len(it["pts"]) // 2]
        dx, dy = x - c[0], y - c[1]
        return [(x + dx * k, y + dy * k + size * 0.35, "middle") for k in (0, 0.6, 1.3, 2.2)] + \
               [(x + 14, y + size * 0.35, "start"), (x - 14, y + size * 0.35, "end")]
    if t in ("poly", "face"):
        cx = sum(p[0] for p in it["pts"]) / len(it["pts"])
        cy = sum(p[1] for p in it["pts"]) / len(it["pts"])
        return [(cx, cy + size * 0.35, "middle"), (cx, cy - size, "middle"), (cx, cy + size * 1.6, "middle")]
    if t == "text":
        x, y = it["p"][0] + it.get("dx", 0), it["p"][1] + it.get("dy", 0) + size * 0.35
        a = it.get("anchor") or "start"
        return [(x, y, a), (x, y - size * 1.2, a), (x, y + size * 1.2, a), (x + 12, y, a), (x - 12, y, a),
                (x, y - size * 2.4, a), (x, y + size * 2.4, a)]
    if t == "callout":
        x, y = it["p"]
        dx, dy = it.get("dx", 36), it.get("dy", -28)
        out = []
        for sx, sy in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
            for k in (1.0, 1.5, 0.7):
                tx, ty = x + dx * sx * k, y + dy * sy * k
                anchor = "start" if dx * sx >= 0 else "end"
                out.append((tx + (3 if anchor == "start" else -3), ty + (-3 if dy * sy < 0 else 12), anchor))
        for ddx, ddy in ((40, 0), (-40, 0), (0, -34), (0, 34)):
            anchor = "start" if ddx >= 0 else "end"
            out.append((x + ddx, y + ddy + (4 if ddy == 0 else (-3 if ddy < 0 else 12)), anchor))
        return out
    return []


def declutter(items, width, height, scale=1.0, blocked=()):
    """Choose where every label goes: inside the picture, off other labels, off points and, where possible, off
    lines and the boxes in `blocked` (the inset pictures). Writes it["L"] = [x, y, anchor] on each labelled item
    (the renderer draws the label there); `scale` is the text scale. Returns how many label pairs still overlap."""
    if scale is True or scale is False:                  # older calls passed `narrow`
        scale = TEXT_SCALE[1 if scale else 0]
    blocked = list(blocked)
    labelled = []
    for it in items:
        lab = it.get("label")
        if lab in (None, "") or it["type"] not in ("point", "line", "polyline", "dim", "arc", "poly", "face", "text", "callout"):
            continue
        labelled.append((it, _base_size(it) * scale))
    order = {"point": 0, "callout": 1, "dim": 2, "arc": 3, "line": 4, "polyline": 4, "poly": 5, "face": 5, "text": 6}
    labelled.sort(key=lambda t: order[t[0]["type"]])
    pts = [((it["p"][0] - (it.get("r") or 4) - 1, it["p"][1] - (it.get("r") or 4) - 1,
             it["p"][0] + (it.get("r") or 4) + 1, it["p"][1] + (it.get("r") or 4) + 1)) for it in items if it["type"] == "point"]
    segs = []
    for it in items:
        if it["type"] in ("line", "polyline", "dim") and "faint" not in str(it.get("style")):
            p = it["pts"]
            for i in range(len(p) - 1):
                a, c = p[i], p[i + 1]
                segs.append(((min(a[0], c[0]), min(a[1], c[1]), max(a[0], c[0]), max(a[1], c[1])), a, c))

    def place(it, size, lines, others):
        best, best_score = None, None
        cands = [(x, y, a, _box(x, y, it["label"], size, a, lines)) for x, y, a in _candidates(it, size)]
        if not cands:
            return None
        u = (min(c[3][0] for c in cands), min(c[3][1] for c in cands), max(c[3][2] for c in cands), max(c[3][3] for c in cands))
        others = [q for q in others if _hit(u, q)]
        near_blocked = [q for q in blocked if _hit(u, q)]
        near_pts = [q for q in pts if _hit(u, q, 0)]
        near_segs = [s for s in segs if _hit(s[0], u, 0)]
        own = it.get("p") if it["type"] == "point" else None
        for k, (x, y, a, b) in enumerate(cands):
            score = k * 0.4
            if b[0] < 2 or b[1] < 2 or b[2] > width - 2 or b[3] > height - 2:
                score += 1000
            score += 60 * sum(1 for q in others if _hit(b, q)) + 45 * sum(1 for q in near_blocked if _hit(b, q))
            score += 25 * sum(1 for q in near_pts if _hit(b, q, 0) and not (own and abs((q[0] + q[2]) / 2 - own[0]) < 0.5
                                                                            and abs((q[1] + q[3]) / 2 - own[1]) < 0.5))
            score += 2 * sum(1 for bb, p, q in near_segs if _hit(bb, b, 0) and _seg_hits_box(p, q, b))
            if best_score is None or score < best_score:
                best, best_score = (x, y, a, b), score
        x, y, a, b = best
        if best_score >= 1000:                           # nothing fits inside: clamp the best one in
            w = b[2] - b[0]
            x = min(max(x, 2 + (w if a == "end" else w / 2 if a == "middle" else 0)),
                    width - 2 - (0 if a == "end" else w / 2 if a == "middle" else w))
            y = min(max(y, size * 0.82 + 2), height - size * 0.22 - 2 - (len(lines) - 1 if lines else 0) * size * 1.15)
            b = _box(x, y, it["label"], size, a, lines)
        return x, y, a, b

    done = []
    for it, size in labelled:
        lines = None
        if it["type"] in ("text", "callout") and CHAR * size * len(str(it["label"])) > width - 8:
            lines = _wrap(it["label"], size, width - 12)
            it["lines"] = lines
        r = place(it, size, lines, [d[3] for d in done])
        if r:
            it["L"] = [round(r[0], 1), round(r[1], 1), r[2]]
            done.append([it, size, lines, r[3]])
    for _ in range(2):                                   # second look: a label still on another moves, knowing the rest
        moved = False
        for i, d in enumerate(done):
            others = [e[3] for j, e in enumerate(done) if j != i]
            if not any(_hit(d[3], q, 0) for q in others):
                continue
            r = place(d[0], d[1], d[2], others)
            if r and not any(_hit(r[3], q, 0) for q in others):
                d[0]["L"], d[3], moved = [round(r[0], 1), round(r[1], 1), r[2]], r[3], True
        if not moved:
            break
    return sum(1 for i, d in enumerate(done) for e in done[:i] if _hit(d[3], e[3], 0))


def label_report(spec):
    """For tests: label boxes that overlap each other or leave their picture, in every scene panel and inset."""
    problems = []

    def check(items, width, height, where, scale):
        boxes = []
        for it in items:
            if "L" not in it or it.get("label") in (None, ""):
                continue
            b = _box(it["L"][0], it["L"][1], it["label"], _base_size(it) * scale, it["L"][2], it.get("lines"))
            if b[0] < 0 or b[1] < 0 or b[2] > width or b[3] > height:
                problems.append("%s: %r leaves the picture" % (where, it["label"]))
            for q, lab in boxes:
                if _hit(b, q, -1):
                    problems.append("%s: %r overlaps %r" % (where, it["label"], lab))
            boxes.append((b, it["label"]))

    panels = spec.get("panels", [spec]) if isinstance(spec, dict) else []
    for i, p in enumerate(panels):
        if p.get("kind") != "scene3d":
            continue
        check(p.get("items", []), p["width"], p["scene_h"], "panel %d" % i, p.get("text_scale", 1.0))
        for n in p.get("insets", []):
            check(n["items"], n["w"], n["h"], "inset " + n.get("name", ""), 1.0)
    return problems


# ----------------------------------------------------------------------------- the camera panel (shared controls)

def rig_controls(cams=(1,), intrinsics=True, move=True, turn=True, defaults=None, group_label=None):
    """Controls that let a reader move every camera and change its intrinsics, grouped so the page folds them
    into panels. Names: f, cx, cy (shared) and, per camera n: c{n}x, c{n}y, c{n}z (centre; y is down) and
    c{n}yaw, c{n}pitch (degrees). `defaults` overrides any default, e.g. {"c2x": 1}. rig_from(values) turns
    them into K, R, C."""
    d = {"f": 500, "cx": 320, "cy": 240}
    for n in cams:
        d.update({"c%dx" % n: 0.0, "c%dy" % n: 0.0, "c%dz" % n: 0.0, "c%dyaw" % n: 0.0, "c%dpitch" % n: 0.0})
    d.update(defaults or {})
    out = []
    if intrinsics:
        g = group_label or "Camera: focal length and principal point"
        out += [{"name": "f", "kind": "slider", "label": "focal length f (px)", "min": 150, "max": 1200, "step": 10, "value": d["f"], "group": g},
                {"name": "cx", "kind": "slider", "label": "principal point cₓ (px)", "min": 160, "max": 480, "step": 2, "value": d["cx"], "group": g},
                {"name": "cy", "kind": "slider", "label": "principal point c_y (px)", "min": 120, "max": 360, "step": 2, "value": d["cy"], "group": g}]
    for n in cams:
        g = "Camera %d: move it and turn it" % n
        if move:
            out += [{"name": "c%dx" % n, "kind": "slider", "label": "camera %d sideways x (m)" % n, "min": -3, "max": 3, "step": 0.05, "value": d["c%dx" % n], "group": g},
                    {"name": "c%dy" % n, "kind": "slider", "label": "camera %d height (m, up is −)" % n, "min": -2, "max": 1, "step": 0.05, "value": d["c%dy" % n], "group": g},
                    {"name": "c%dz" % n, "kind": "slider", "label": "camera %d forward z (m)" % n, "min": -3, "max": 3, "step": 0.05, "value": d["c%dz" % n], "group": g}]
        if turn:
            out += [{"name": "c%dyaw" % n, "kind": "slider", "label": "camera %d turn left/right (°)" % n, "min": -60, "max": 60, "step": 1, "value": d["c%dyaw" % n], "group": g},
                    {"name": "c%dpitch" % n, "kind": "slider", "label": "camera %d tilt up/down (°)" % n, "min": -45, "max": 45, "step": 1, "value": d["c%dpitch" % n], "group": g}]
    return out


def rig_from(values, cams=(1,)):
    """K and each camera's (R, C) from the panel's values. R = R_pitch · R_yaw: positive yaw turns the camera to
    its left (toward −x), positive pitch tilts it down."""
    K = K_matrix(float(values.get("f", 500)), float(values.get("cx", 320)), float(values.get("cy", 240)))
    out = {"K": K}
    for n in cams:
        yaw, pitch = float(values.get("c%dyaw" % n, 0)), float(values.get("c%dpitch" % n, 0))
        R = mat_mul(rot_x(pitch), rot_y(yaw))
        C = [float(values.get("c%dx" % n, 0)), float(values.get("c%dy" % n, 0)), float(values.get("c%dz" % n, 0))]
        out[n] = dict(K=K, R=R, C=C)
    return out


def camera_drag_rules(cams=(1,), ground_y=0.0, values=None):
    """apply_drag rules for dragging camera centres: handle "cam{n}" moves c{n}x / c{n}z on a plane parallel to
    the ground, at the camera's own height when `values` is given. Pair with camera_handles()."""
    return {"cam%d" % n: ("plane", (0, float(values.get("c%dy" % n, ground_y)) if values else ground_y, 0), (0, 1, 0), (0, 2))
            for n in cams}


def camera_handles(rig, cams=(1,)):
    """Drag handles on the camera centres (they drive the hidden controls cam{n} = [x, z])."""
    return [{"name": "cam%d" % n, "control": "cam%d" % n, "at": rig[n]["C"], "hint": "drag camera %d" % n} for n in cams]


def camera_drag_controls(values, cams=(1,)):
    """Hidden controls the camera handles drive; keep them equal to c{n}x / c{n}z before and after apply_drag."""
    return [{"name": "cam%d" % n, "kind": "hidden", "value": [float(values.get("c%dx" % n, 0.0)), float(values.get("c%dz" % n, 0.0))]}
            for n in cams]
