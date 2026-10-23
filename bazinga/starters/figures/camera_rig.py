"""Starter: a pinhole camera, the picture it takes, and a panel to move it.

Copy it with  python -m bazinga figure new my_camera --from camera_rig  and put  ::figure my_camera  in a post.

What it shows
-------------
A camera at C looks along its axis; its image plane is drawn one unit in front. A point X sends a ray
to the centre, and where the ray crosses the image plane is the pixel the camera records. The inset is
the camera's own picture. Drag X, drag the camera, or open the camera panels under the figure to move
and turn it and to change its focal length and principal point.

Things worth copying
--------------------
- Scene(up="-y") uses the camera convention: x right, y DOWN, z forward (the ground is at y = +1).
- rig_controls() adds the camera panel (f, cₓ, c_y; the camera's position and turn), folded into two
  panels; rig_from(values) turns those values into K and the camera's R and C.
- camera_drag_controls / camera_handles / camera_drag_rules let the reader drag the camera on the ground.
- sc.camera(R, C, K) draws the camera; sc.ray(X, cam) the ray; sc.image_view(K, R, C, points=[...])
  the camera's own picture as an inset.
- Handles, _drag and state: as in the vectors_planes starter.
"""

from bazinga.scene3d import (Scene, apply_drag, layout, project, fmt, rig_controls, rig_from, camera_drag_controls,
                             camera_handles, camera_drag_rules)

TITLE = "A point becomes a pixel"
CAPTION = ("Drag the point X or the camera, or play the depth. Open the camera panels to move and turn the camera, "
           "or change its focal length and principal point.")
REQUIRES = []

CAMS = (1,)
RIG = {}                     # the camera's starting place: at the origin, looking along z
CONTROLS = [
    {"name": "X", "kind": "pad", "label": "X (across, height)", "min": [-1.6, -1.2], "max": [1.6, 1.2], "value": [0.3, -0.2]},
    {"name": "Z", "kind": "slider", "label": "Depth of X (m)", "min": 1.5, "max": 7, "step": 0.1, "value": 4, "play": True},
    {"name": "view", "kind": "orbit", "value": [-50, 18]},
] + rig_controls(cams=CAMS, defaults=RIG) + camera_drag_controls(RIG, CAMS)

START = {c["name"]: c["value"] for c in CONTROLS}
PRESETS = [
    {"label": "On the axis", "values": {"X": [0, 0]}},
    {"label": "Long lens", "values": {"f": 900}},
    {"label": "Camera to the side", "values": {"c1x": -1, "cam1": [-1, 0], "c1yaw": -15}},
]
FLOOR = 1.0                  # the ground, one metre below the camera (y is down)


def compute(_drag=None, _narrow=0, **values):
    v = dict(START, **values)                                 # every control, starting values filled in
    lay = layout(_narrow, dist=7, target=(0.4, -0.1, 2.4), height=440, narrow_dist=5.6, up="-y")   # y is down
    Z = float(v["Z"])
    rules = {"X": ("plane", (0, 0, Z), (0, 0, 1)), **camera_drag_rules(CAMS, values=v)}
    v = apply_drag(_drag, rules, v, **lay)
    if _drag and _drag.get("name") == "cam1":                 # a dragged camera writes its sliders ...
        v["c1x"], v["c1z"] = [round(max(-3.0, min(3.0, a)), 2) for a in v["cam1"]]
    v["cam1"] = [v["c1x"], v["c1z"]]                          # ... and the sliders place its handle
    X = [max(-1.6, min(1.6, v["X"][0])), max(-1.2, min(1.2, v["X"][1])), Z]

    rig = rig_from(v, CAMS)
    K, R, C = rig["K"], rig[1]["R"], rig[1]["C"]
    q = project(K, R, C, X)

    sc = Scene(up="-y")
    sc.grid(size=6, n=6, level=FLOOR, centre=(0, 3))
    cam = sc.camera(R, C, K=K, depth=1.0, style="main", frame=(640, 480))
    sc.text(C, "C", style="main", size=13, anchor="end", dx=-8, dy=18)
    hit = sc.ray(X, cam, style="main")
    sc.point(X, label="X", style="ink", r=5)
    if hit:
        sc.point(hit, style="main", r=3.5)
    sc.line(X, (X[0], FLOOR, X[2]), style="faint", dash="2 3")     # drop line to the floor
    inset = sc.image_view(K, R, C, points=[("x", X, "main")], title="The camera sees", frame=(640, 480))
    handles = [{"name": "X", "at": X, "hint": "drag the point X"}] + camera_handles(rig, CAMS)
    readouts = [
        {"label": "Pixel (u, v)", "value": "(%s, %s)" % (fmt(q[0], 1), fmt(q[1], 1)) if q else "none",
         "note": "u = f·X/Z + cₓ" if q else "X is behind the camera"},
        {"label": "Focal length", "value": "%s px" % fmt(K[0][0], 0)},
    ]
    state = {"X": X[:2], "c1x": v["c1x"], "c1z": v["c1z"], "cam1": v["cam1"]} if _drag else None
    return sc.render(view=v["view"], insets=[inset], handles=handles, readouts=readouts, state=state, **lay)
