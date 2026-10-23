"""Starter: a cube and three axes you can turn by dragging.

Copy it with  python -m bazinga figure new my_scene --from scene_basic  and put  ::figure my_scene  in a post.

How a 3-D figure works
----------------------
- You build a Scene out of points, lines, arrows, boxes, planes and surfaces, in ordinary x, y, z
  coordinates (z is up), and return sc.render(...). The site works out where everything lands on the
  screen, hides what is behind, and keeps the labels apart.
- An "orbit" control is the direction you look from: [turn around, height above], in degrees. It has
  no slider; readers drag the picture to change it.
- Pass _narrow on to render() so phones get a picture laid out for them.
"""

from bazinga.scene3d import Scene

TITLE = "A cube you can turn"
CAPTION = "Drag the picture to look at the cube from another side; the slider grows it."
REQUIRES = []

CONTROLS = [
    {"name": "view", "kind": "orbit", "value": [35, 25]},      # drag the picture to change it
    {"name": "size", "kind": "slider", "label": "Size of the cube", "min": 0.2, "max": 1, "step": 0.05, "value": 0.6},
]

PRESETS = [
    {"label": "From the front", "values": {"view": [0, 0]}},
    {"label": "From above", "values": {"view": [0, 89]}},
]


def compute(view=(35, 25), size=0.6, _narrow=0):
    sc = Scene()
    sc.axes3d(lo=(-1, -1, -1), hi=(1.2, 1.2, 1.2), ticks=4)        # x, y, z with numbered ticks
    h = size / 2
    sc.box((-h, -h, -h), (h, h, h), style="main", faces=True)      # 12 edges and 6 see-through faces
    sc.point((h, h, h), label="corner", style="second")
    return sc.render(view=view, narrow=_narrow, dist=4.3,
                     readouts=[{"label": "Volume", "value": "%.3f" % size ** 3}])
