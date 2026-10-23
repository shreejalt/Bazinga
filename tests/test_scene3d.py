"""The 3-D figure kit (bazinga/scene3d.py), its renderer (plot.py's scene3d panels), every scene figure and
starter, the new control kinds, and the figure builder's 3-D type.

Run:  python -m unittest discover tests -v
"""
import json
import math
import os
import re
import shutil
import tempfile
import time
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace

from bazinga import figbuilder, figures, plot
from bazinga import scene3d as k

ROOT = Path(__file__).resolve().parent.parent
BUDGET_MS = 15 * (3 if os.environ.get("CI") or os.environ.get("VERCEL") else 1)   # per compute, in this interpreter
MAX_ITEMS = 450
CFG = SimpleNamespace(root=ROOT, figures_dir=ROOT / "figures")     # this repository's figures, whatever other tests set
SCENE_STARTERS = ("scene_basic", "surface_plot", "vectors_planes", "camera_rig")


def close(a, b, tol=1e-6):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def scene_figures():
    """[(name, module)] for every figure in figures/ and every starter whose compute() returns a scene3d panel."""
    out = []
    names = sorted(figures.discover(CFG)) + [figures.STARTER_PREFIX + s for s in figures.STARTERS]
    for name in names:
        mod = figures.load(name, CFG)
        if any(isinstance(p, dict) and p.get("kind") == "scene3d"
               for p in figures.compute_spec(name, None, 0, CFG)[2].get("panels", [])):
            out.append((name, mod))
    return out


class Kit(unittest.TestCase):
    def test_project_backproject_round_trip(self):
        K, R, C = k.K_matrix(500), k.mat_mul(k.rot_y(10), k.rot_x(-5)), [1.0, -0.2, 0.3]
        for X in ([0.3, -0.2, 4.0], [-1, 0.5, 6], [2, 1, 9]):
            u, v, d = k.project(K, R, C, X)
            self.assertTrue(close(k.backproject(K, R, C, u, v, d), X, 1e-9))

    def test_a_worked_pixel(self):
        """A camera at the origin with f = 500 and principal point (320, 240) sees (0.3, -0.2, 4) at (357.5, 215)."""
        u, v, d = k.project(k.K_matrix(500), k.identity(), [0, 0, 0], [0.3, -0.2, 4])
        self.assertTrue(close((u, v, d), (357.5, 215.0, 4.0)))

    def test_behind_the_camera(self):
        self.assertIsNone(k.project(k.K_matrix(500), k.identity(), [0, 0, 0], [0, 0, -1]))

    def test_look_at_is_right_handed(self):
        for up in ((0, -1, 0), (0, 0, 1)):
            for C, T in (([0, 0, -5], [0, 0, 0]), ([3, -2, 1], [0, 0, 4]), ([-4, -1, 6], [0.5, 0, 2])):
                x, y, z = k.look_at(C, T, up)
                self.assertTrue(close(k.cross(x, y), z, 1e-9))
                self.assertTrue(close(z, k.unit(k.vsub(T, C)), 1e-9))
                self.assertLessEqual(k.dot(y, up), 1e-9)                  # the picture's down is never the world's up

    def test_up_stays_up(self):
        """From any orbit, a point above the target is drawn higher on the screen, in every world convention."""
        for up, above in (("z", [0, 0, 1]), ("-y", [0, -1, 0]), ("y", [0, 1, 0])):
            for az in (-150, -60, 0, 40, 120):
                for el in (-20, 5, 30, 60, 85):
                    K, R, C = k.viewer(az, el, 7, (0, 0, 0), up=up)
                    a, b = k.project(K, R, C, [0, 0, 0]), k.project(K, R, C, above)
                    self.assertLess(b[1], a[1], (up, az, el))

    def test_drags_follow_the_pointer(self):
        """A point dragged in a plane moves the way the pointer moves, from several views, in both conventions."""
        cases = (("-y", (0, 0, 4), (0, 0, 1), [0.6, -0.4], (0, 1), 1),     # frontal plane; screen down = +y
                 ("z", (0, 0, 0.5), (0, 0, 1), [0.6, -0.4], (0, 1), None))  # ground plane, z up
        for up, point, normal, start, axes, down_sign in cases:
            for view in ((-52, 18), (0, 10), (40, 30)):
                lay = k.layout(False, dist=8, target=(0, 0, 2.4) if up == "-y" else (0, 0, 0), up=up)
                X = [start[0], start[1], point[2]] if up == "-y" else [start[0], start[1], 0.5]
                p = k.screen_of(view, X, **lay)
                for d in ((40, 0), (-40, 0)):
                    out = k.apply_drag({"name": "X", "start": start, "from": p, "to": [p[0] + d[0], p[1] + d[1]]},
                                       {"X": ("plane", point, normal, axes)}, {"X": start, "view": list(view)}, **lay)
                    Q = [out["X"][0], out["X"][1], X[2]]
                    q = k.screen_of(view, Q, **lay)
                    self.assertGreater((q[0] - p[0]) * d[0], 0, (up, view, d))
                    self.assertTrue(close(q, [p[0] + d[0], p[1] + d[1]], 0.6), (up, view, d, q))   # under the pointer

    def test_render_and_drags_share_the_framing(self):
        """A handle is drawn where screen_of / apply_drag think the point is, wide and on phones."""
        for narrow in (0, 1):
            lay = k.layout(narrow, dist=7, target=(0, 0, 1), up="-y")
            sc = k.Scene(up="-y")
            sc.point((0.5, -0.3, 3))
            o = sc.render(view=(20, 15), handles=[{"name": "p", "at": (0.5, -0.3, 3)}], **lay)["panels"][0]
            self.assertTrue(close(o["handles"][0]["P"], k.screen_of((20, 15), (0.5, -0.3, 3), **lay), 0.11), narrow)
            self.assertEqual(o["width"], 480 if narrow else 880)

    def test_a_plane_seen_edge_on_does_not_throw_the_point(self):
        lay = k.layout(False, dist=8, target=(0, 0, 2.4), up="-y")
        for view in ((-88, 10), (90, 5), (-80, 20)):
            p = k.screen_of(view, [0.3, -0.2, 4], **lay)
            for d in ((40, 0), (0, -40), (30, 30)):
                out = k.apply_drag({"name": "X", "start": [0.3, -0.2], "from": p, "to": [p[0] + d[0], p[1] + d[1]]},
                                   {"X": ("plane", (0, 0, 4), (0, 0, 1))}, {"X": [0.3, -0.2], "view": list(view)}, **lay)
                self.assertLess(math.hypot(out["X"][0] - 0.3, out["X"][1] + 0.2), 1.0, (view, d, out["X"]))

    def test_near_plane_clipping_keeps_segments(self):
        sc = k.Scene()
        sc.line([0, -20, 0], [0, 20, 0])                                 # passes through the eye
        o = sc.panel(view=(0, 0), dist=6)
        self.assertEqual(len([i for i in o["items"] if i["type"] == "line"]), 1)

    def test_image_view_clips_lines_to_the_frame(self):
        sc = k.Scene(up="-y")
        inset = sc.image_view(k.K_matrix(500), k.identity(), [0, 0, 0], lines=[([-50, 0, 4], [50, 0, 4], "second")])
        line = [i for i in inset["items"] if i["type"] == "line" and i["style"] == "second"][0]
        for x, y in line["pts"]:
            self.assertTrue(-0.5 <= x <= inset["w"] + 0.5 and -0.5 <= y <= inset["h"] + 0.5)

    def test_surface_faces_are_sorted_far_to_near(self):
        sc = k.Scene()
        info = sc.surface(lambda x, y: x * y, n=6, z_range=(-1, 1))
        self.assertEqual((info["lo"], info["hi"]), (-1, 1))
        o = sc.panel(view=(30, 30), dist=6)
        depths = [i["depth"] for i in o["items"] if i["type"] == "face"]
        self.assertEqual(len(depths), 36)
        self.assertEqual(depths, sorted(depths, reverse=True))
        self.assertTrue(all(0 <= i["shade"] <= 1 for i in o["items"] if i["type"] == "face"))

    def test_surface_holes_and_curves_skip_undefined_values(self):
        sc = k.Scene()
        sc.surface(lambda x, y: None if x < 0 else math.log(x), x=(-1, 1), y=(-1, 1), n=4)
        sc.curve(lambda t: (t, 0, 1 / t), -1, 1, n=21)                  # 1/0 in the middle: two pieces
        faces = [i for i in sc.items if i["type"] == "face"]
        self.assertTrue(0 < len(faces) < 16)
        self.assertNotIn("nan", json.dumps(sc.render()).lower())

    def test_helpers(self):
        sc = k.Scene()
        corners = sc.plane((0, 0, 0), (0, 0, 1), size=2)
        self.assertTrue(all(abs(c[2]) < 1e-12 for c in corners))
        sc.box((0, 0, 0), (1, 1, 1), faces=True)
        self.assertEqual(len([i for i in sc.items if i["type"] == "poly"]), 7)
        it = sc.vector((1, 1, 1), (1, 0, 0), label="v")
        self.assertEqual(it["pts"][1], [2, 1, 1])
        self.assertTrue(it["arrow"])
        sc.axes3d(lo=(-1, -1, -1), hi=(1, 1, 1), ticks=4)
        self.assertTrue(any(i["type"] == "text" and i["label"] == "0.5" for i in sc.items))

    def test_fmt(self):
        self.assertEqual(k.fmt(-0.0), "0")
        self.assertEqual(k.fmt(357.5, 1), "357.5")
        self.assertEqual(k.fmt(-2.40), "−2.4")

    def test_stdlib_only(self):
        import ast
        tree = ast.parse((ROOT / "bazinga" / "scene3d.py").read_text(encoding="utf-8"))
        imports = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        imports |= {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        self.assertEqual(imports, {"math"})


class Renderer(unittest.TestCase):
    def spec(self, narrow=0):
        sc = k.Scene()
        sc.axes3d()
        sc.surface(lambda x, y: x * x - y * y, x=(-1, 1), y=(-1, 1), n=8)
        sc.point((0.5, 0.5, 0), label="P <&>")
        cam = k.Scene(up="-y")
        inset = cam.image_view(k.K_matrix(), k.identity(), [0, 0, 0], points=[("x", [0.2, 0.1, 3], "main")])
        return sc.render(view=(30, 25), narrow=narrow, insets=[inset], dist=5,
                         handles=[{"name": "p", "at": (0.5, 0.5, 0), "hint": "drag P"},
                                  {"name": "q", "inset": "cam", "p": [40, 30]}],
                         readouts=[{"label": "a", "value": "1"}])

    def test_draws_well_formed_svg_wide_and_narrow(self):
        for narrow in (0, 1):
            svg, ro = plot.render(self.spec(narrow), narrow=narrow)
            ET.fromstring(svg)
            self.assertIn('class="s3', svg)
            self.assertIn("P &lt;&amp;&gt;", svg)
            self.assertIn('data-inset="cam"', svg)
            self.assertEqual(svg.count('class="s3-handle"'), 2)
            self.assertNotRegex(svg, r'="[^"]*\b(nan|inf)\b')
            self.assertNotIn("clipPath", svg)
            self.assertIn("color-mix", svg)              # faces follow the theme's colours

    def test_same_spec_same_bytes(self):
        self.assertEqual(plot.render(self.spec())[0], plot.render(self.spec())[0])

    def test_inset_handles_are_placed_on_their_inset(self):
        o = self.spec()["panels"][0]
        n = o["insets"][0]
        h = [h for h in o["handles"] if h["name"] == "q"][0]
        self.assertTrue(close(h["P"], [n["x"] + 40 * n["s"], n["y"] + 30 * n["s"]], 0.11))

    def test_phone_insets_go_underneath(self):
        o = self.spec(1)["panels"][0]
        self.assertEqual(o["width"], 480)
        self.assertGreater(o["height"], o["scene_h"])
        self.assertGreaterEqual(o["insets"][0]["y"], o["scene_h"])

    def test_beside_another_panel(self):
        sc = k.Scene()
        sc.box((0, 0, 0), (1, 1, 1))
        spec = {"panels": [sc.panel(columns=2), {"kind": "xy", "series": [{"name": "a", "x": [0, 1], "y": [0, 1]}]}]}
        self.assertLess(abs(spec["panels"][0]["width"] - 418), 1)
        ET.fromstring(plot.render(spec)[0])

    def test_bad_items_say_where(self):
        with self.assertRaises(plot.PlotError) as e:
            plot.render({"panels": [{"kind": "scene3d", "width": 100, "height": 100, "items": [{"type": "blob"}]}]})
        self.assertIn("items[0]", str(e.exception))


class Controls(unittest.TestCase):
    def test_coerce_vector_kinds(self):
        ctl = [{"name": "view", "kind": "orbit", "value": [35, 25]},
               {"name": "p", "kind": "pad", "value": [0, 0], "min": [-1, -1], "max": [1, 1]},
               {"name": "h", "kind": "hidden", "value": 0.5}]
        v = plot.coerce(ctl, {"view": [370, 120], "p": [5, -0.25], "h": "x"})
        self.assertEqual(v, {"view": [10.0, 89.0], "p": [1.0, -0.25], "h": 0.5})
        self.assertEqual(plot.coerce(ctl, {"p": [1, 2, 3]})["p"], [0.0, 0.0])     # wrong shape: the default

    def test_contract_messages(self):
        mod = SimpleNamespace(TITLE="t", compute=lambda view=(0, 0), _narrow=0: {},
                              CONTROLS=[{"name": "view", "kind": "orbit", "value": [1]}])
        with self.assertRaises(figures.FigureError) as e:
            figures.validate(mod, "t")
        self.assertIn("[azimuth, elevation]", str(e.exception))
        mod = SimpleNamespace(TITLE="t", compute=lambda p=(0, 0), _narrow=0: {},
                              CONTROLS=[{"name": "p", "kind": "pad", "value": [0, 0]}])
        with self.assertRaises(figures.FigureError) as e:
            figures.validate(mod, "t")
        self.assertIn("_drag", str(e.exception))
        mod = SimpleNamespace(TITLE="t", compute=lambda p=(0, 0), _drag=None, _narrow=0: {},
                              CONTROLS=[{"name": "p", "kind": "pad", "value": [0, 0], "min": [0], "max": [1, 1]}])
        with self.assertRaises(figures.FigureError) as e:
            figures.validate(mod, "t")
        self.assertIn("same shape", str(e.exception))

    def test_figure_html_for_a_scene(self):
        html = figures.figure_html("starter_camera_rig", cfg=CFG)
        data = json.loads(re.search(r'data-bazinga="([^"]*)"', html).group(1).replace("&quot;", '"').replace("&amp;", "&"))
        self.assertTrue(data["kits"]["scene3d"].startswith("figures/_scene3d.py?v="))
        self.assertIn('class="fig-group"', html)
        self.assertIn('class="fig-ctl fig-pad"', html)
        self.assertIn("Drag the picture to turn it.", html)
        self.assertNotRegex(html, r'class="fig-ctl[^"]*" data-name="cam1"')    # a hidden control shows nothing
        self.assertNotIn("kits", json.dumps(json.loads(re.search(r'data-bazinga="([^"]*)"', figures.figure_html(
            "starter_slider_plot", cfg=CFG)).group(1).replace("&quot;", '"').replace("&amp;", "&"))))

    def test_assets_ship_the_kit(self):
        with tempfile.TemporaryDirectory() as d:
            figures.write_assets(None, set(), d)
            self.assertEqual((Path(d) / "figures" / "_scene3d.py").read_bytes(), (ROOT / "bazinga" / "scene3d.py").read_bytes())

    def test_drags_are_tested(self):
        rep = figures.test_report("starter_vectors_planes", CFG)
        self.assertTrue(rep["ok"], rep["problems"])
        self.assertTrue(any(c["label"].startswith("Dragging") and c["ok"] for c in rep["checks"]))
        out = figures.run("starter_vectors_planes", None, 0, CFG, drag={"handle": "u", "name": "u", "start": [1.5, 0.2],
                                                                    "from": [0, 0], "to": [30, 0]})
        self.assertIn("u", out["state"])


class SceneFigures(unittest.TestCase):
    """Every figure and starter that draws a scene: no NaN at its defaults, at the ends of every control and from
    several views, under MAX_ITEMS items, fast enough to follow a drag, handles on real controls."""

    def test_scene_figures(self):
        found = scene_figures()
        self.assertGreaterEqual(len(found), 5)
        for name, mod in found:
            with self.subTest(figure=name):
                ctl = figures.controls(mod)
                base = figures.defaults(mod)
                cases = [base]
                for c in ctl:
                    if c["kind"] == "slider":
                        cases += [dict(base, **{c["name"]: c["min"]}), dict(base, **{c["name"]: c["max"]})]
                    elif c["kind"] == "orbit":
                        cases += [dict(base, **{c["name"]: v}) for v in ([0, 5], [90, 40], [-120, 70], [180, -10])]
                    elif c["kind"] == "pad" and "min" in c:
                        cases += [dict(base, **{c["name"]: c["min"]}), dict(base, **{c["name"]: c["max"]})]
                t = time.perf_counter()
                n = 0
                for v in cases:
                    for nar in (0, 1):
                        spec = figures.compute_spec(name, v, nar, CFG)[2]
                        n += 1
                        self.assertNotIn("nan", json.dumps(spec).lower())
                        for p in spec["panels"]:
                            if p.get("kind") == "scene3d":
                                count = len(p["items"]) + sum(len(i["items"]) for i in p["insets"])
                                self.assertLess(count, MAX_ITEMS)
                                names = {c["name"] for c in ctl}
                                for h in p["handles"]:
                                    self.assertIn(h["control"], names)
                per = (time.perf_counter() - t) / n * 1000
                self.assertLess(per, BUDGET_MS, "%s: %.1f ms per compute" % (name, per))
                self.assertEqual(figures.test_figure(name, CFG), [])

    def test_no_overlapping_labels(self):
        bad = []
        for name, mod in scene_figures():
            base = figures.defaults(mod)
            cases = [("start", base)] + [(p["label"], dict(base, **p["values"])) for p in figures.presets(mod)]
            for label, v in cases:
                for nar in (0, 1):
                    for pr in k.label_report(figures.compute_spec(name, v, nar, CFG)[2]):
                        bad.append("%s [%s%s] %s" % (name, label, ", phone" if nar else "", pr))
        self.assertEqual(bad, [], "\n" + "\n".join(bad[:40]))


class Builder(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "figures").mkdir()
        self.cfg = SimpleNamespace(root=self.tmp, figures_dir=self.tmp / "figures")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write(self, spec, name="scene"):
        src = figbuilder.generate(spec)
        (self.tmp / "figures" / (name + ".py")).write_text(src, encoding="utf-8")
        return src

    def test_the_example_works_and_reopens(self):
        spec = figbuilder.default_spec("scene3d")
        src = self.write(spec)
        imports = set(re.findall(r"^(?:import|from)\s+([\w.]+)", src, re.M))
        self.assertEqual(imports, {"math", "bazinga.scene3d"})
        self.assertEqual(figures.test_figure("scene", self.cfg), [])
        self.assertEqual(figures.made_with(src), "builder")
        self.assertEqual(figbuilder.read_spec(src)["spec"]["type"], "scene3d")
        self.assertIn("scene3d", [t["type"] for t in figbuilder.describe()["types"]])

    def test_points_segments_boxes_and_repeats(self):
        spec = {"type": "scene3d", "title": "Many", "view": [10, 40],
                "controls": [{"name": "n", "kind": "slider", "min": 1, "max": 8, "step": 1, "value": 4}],
                "points": [{"x": "cos(2pi k/n)", "y": "sin(2pi k/n)", "z": "0", "repeat": "n", "label": "{k}"}],
                "segments": [{"x1": "0", "y1": "0", "z1": "0", "x2": "0", "y2": "0", "z2": "1", "arrow": True, "label": "up"}],
                "boxes": [{"x1": "-0.2", "y1": "-0.2", "z1": "-0.2", "x2": "0.2", "y2": "0.2", "z2": "0.2", "faces": False}],
                "axes": False, "presets": [{"label": "Top", "values": {"view": [0, 89], "n": 6}}]}
        self.assertEqual(figbuilder.validate(spec), [])
        self.write(spec)
        self.assertEqual(figures.test_figure("scene", self.cfg), [])
        o = figures.compute_spec("scene", {"n": 6}, 0, self.cfg)[2]["panels"][0]
        self.assertEqual(len([i for i in o["items"] if i["type"] == "point"]), 6)

    def test_problems_point_at_the_field(self):
        cases = [({"surface": "sin(x)*yy"}, "surface", "did you mean 'y'"),
                 ({"points": [{"x": "1", "y": "b", "z": "0"}]}, "points.0.y", "unknown name"),
                 ({"surface": "x", "x_min": 2, "x_max": 1}, "x_max", "smaller to a larger"),
                 ({"surface": "x", "samples": 60}, "samples", "between 4 and 24"),
                 ({"surface": "x", "view": [1]}, "view", "[turn, height]"),
                 ({}, "points", "add a point")]
        for extra, path, words in cases:
            spec = dict({"type": "scene3d", "title": "t"}, **extra)
            probs = figbuilder.validate(spec)
            self.assertTrue(any(p["path"] == path and words in p["message"] for p in probs), (extra, probs))

    def test_a_control_named_y_cannot_shadow_the_surface(self):
        spec = {"type": "scene3d", "title": "t", "surface": "y",
                "controls": [{"name": "y", "kind": "slider", "min": 0, "max": 1, "value": 0}]}
        self.assertTrue(any(p["path"] == "surface" for p in figbuilder.validate(spec)))


if __name__ == "__main__":
    unittest.main()
