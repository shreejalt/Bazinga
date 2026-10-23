"""bazinga.plot: every panel kind, determinism, escaping, narrow layout, errors."""

import math
import re
import time
import unittest
import xml.etree.ElementTree as ET

from bazinga import plot
import os as _os
import sys as _sys

_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from perf_support import PERF, perf_only  # noqa: E402,F401

XS = [i / 20 for i in range(101)]


def xy_spec(**extra):
    p = {"kind": "xy", "title": "Waves", "x_label": "time", "y_label": "value", "x": XS,
         "series": [{"name": "sin", "y": [math.sin(x) for x in XS]},
                    {"name": "cos", "y": [math.cos(x) for x in XS], "style": "second dashed"}]}
    p.update(extra)
    return {"panels": [p]}


def parse(svg):
    return ET.fromstring(svg)


def viewbox(svg):
    return [float(v) for v in parse(svg).get("viewBox").split()]


class Kinds(unittest.TestCase):
    def test_xy(self):
        svg, ro = plot.render(xy_spec(marks=[{"x": 2, "label": "here"}, {"y": 0.5, "label": "half"}],
                                      annotations=[{"x": 1.57, "y": 1, "text": "peak"}]))
        root = parse(svg)
        self.assertEqual(root.get("role"), "img")
        self.assertEqual(root[0].tag.split("}")[-1], "title")
        self.assertIn('class="line s-main"', svg)
        self.assertIn('class="line s-second s-dashed"', svg)
        for word in ("sin", "cos", "here", "half", "peak", "time", "value", "Waves"):
            self.assertIn(">%s<" % word, svg)
        self.assertEqual(ro, "")

    def test_area_points_and_gaps(self):
        y = [math.sin(x) if i % 17 else None for i, x in enumerate(XS)]
        y[5] = float("nan")
        svg, _ = plot.render({"panels": [{"kind": "xy", "x": XS, "series": [
            {"name": "band", "y": y, "style": "area"}, {"name": "dots", "y": [0.1] * len(XS), "style": "points"}]}]})
        parse(svg)
        self.assertIn('class="fill s-area"', svg)
        self.assertIn('class="dot s-points"', svg)
        self.assertNotRegex(svg, r"nan|inf")

    def test_log_axes(self):
        xs = [10 ** (i / 10) for i in range(-20, 31)]
        svg, _ = plot.render({"panels": [{"kind": "xy", "x_log": True, "y_log": True,
                                          "series": [{"name": "y", "x": xs, "y": [x * x for x in xs]}]}]})
        parse(svg)
        self.assertIn("10⁶", svg)  # superscript ticks for wide ranges

    def test_bars_vertical_and_horizontal(self):
        bars = [{"label": "a & b", "value": 3, "note": "3 units"}, {"label": "c", "value": -1.5, "style": "muted"}]
        for horiz in (False, True):
            svg, _ = plot.render({"panels": [{"kind": "bars", "horizontal": horiz, "bars": bars,
                                              "marks": [{"value": 1, "label": "target"}]}]})
            parse(svg)
            self.assertIn("a &amp; b", svg)
            self.assertIn("3 units", svg)
            self.assertIn('class="bar s-muted"', svg)

    def test_many_bars_rotate_labels(self):
        bars = [{"label": "category number %d" % i, "value": i} for i in range(14)]
        svg, _ = plot.render({"panels": [{"kind": "bars", "bars": bars}]})
        self.assertIn("rotate(-38", svg)

    def test_heatmap(self):
        m = [[1, -2, 3], [0.5, 0, None]]
        svg, _ = plot.render({"panels": [{"kind": "heatmap", "matrix": m, "row_labels": ["r1", "r2"],
                                          "col_labels": ["a", "b", "c"], "show_values": True, "highlight": [[0, 2]]}]})
        parse(svg)
        self.assertIn("--fig-div-pos", svg)            # diverging because the range spans 0
        self.assertIn('class="cell missing"', svg)
        self.assertIn('class="cell-hl"', svg)
        svg2, _ = plot.render({"panels": [{"kind": "heatmap", "matrix": [[0, 1], [2, 3]]}]})
        self.assertIn("--fig-seq-hi", svg2)
        self.assertNotIn("--fig-div", svg2)

    def test_scene_shapes(self):
        shapes = [
            {"type": "point", "x": 0, "y": 0, "label": "O"},
            {"type": "line", "x1": 0, "y1": 0, "x2": 2, "y2": 1},
            {"type": "arrow", "points": [[0, 0], [1, 1], [2, 0]], "label": "path", "style": "second"},
            {"type": "polygon", "points": [[0, 0], [1, 0], [0, 1]], "style": "third"},
            {"type": "circle", "x": 0, "y": 0, "r": 1},
            {"type": "circle", "x": 0, "y": 0, "rx": 9, "ry": 1, "style": "contour"},   # cut by the edge
            {"type": "rect", "x": -1, "y": -1, "w": 0.5, "h": 0.5},
            {"type": "text", "x": 1, "y": -1, "text": "<x>", "anchor": "start"},
        ]
        svg, _ = plot.render({"panels": [{"kind": "scene", "shapes": shapes, "x_min": -2, "x_max": 3,
                                          "y_min": -2, "y_max": 2}]})
        parse(svg)
        self.assertIn('class="head s-second"', svg)
        self.assertIn("poly-edge", svg)                 # the clipped ellipse is drawn as an open outline
        self.assertIn("&lt;x&gt;", svg)

    def test_equal_aspect(self):
        svg, _ = plot.render({"panels": [{"kind": "scene", "shapes": [{"type": "circle", "x": 0, "y": 0, "r": 1}]}]})
        m = re.search(r'<circle class="poly s-main" cx="[^"]+" cy="[^"]+" r="([^"]+)"', svg)
        self.assertIsNotNone(m, "an equal-aspect circle stays a <circle>")

    def test_readouts_and_note(self):
        _, ro = plot.render(dict(xy_spec(), readouts=[{"label": "Loss", "value": 0.123456, "note": "<nats>"},
                                                      {"label": "Steps", "value": "12"}], note="A & B"))
        ET.fromstring("<div>%s</div>" % ro)
        self.assertIn("0.1235", ro)
        self.assertIn("&lt;nats&gt;", ro)
        self.assertIn("A &amp; B", ro)

    def test_legend(self):
        svg, _ = plot.render(dict(xy_spec(), legend=[{"name": "sin", "style": "main"}, {"name": "cos", "style": "second"}]))
        self.assertIn('class="t-legend"', svg)


class Layout(unittest.TestCase):
    def test_determinism(self):
        spec = xy_spec(marks=[{"x": 1}])
        self.assertEqual(plot.render(spec), plot.render(spec))
        self.assertEqual(plot.render(spec, 1), plot.render(spec, 1))

    def test_narrow_is_480_wide_and_stacks(self):
        spec = {"panels": [xy_spec()["panels"][0], {"kind": "bars", "bars": [{"label": "a", "value": 1}]}]}
        wide, narrow = viewbox(plot.render(spec)[0]), viewbox(plot.render(spec, 1)[0])
        self.assertEqual(wide[2], 880)
        self.assertEqual(narrow[2], 480)
        self.assertGreater(narrow[3], wide[3])        # panels stacked
        self.assertIn("fig-plot narrow", plot.render(spec, 1)[0])

    def test_escaping(self):
        spec = xy_spec(title='<script>"x"</script> & co')
        svg, _ = plot.render(spec, title="T <b>")
        parse(svg)
        self.assertNotIn("<script>", svg)
        self.assertIn("&lt;script&gt;&quot;x&quot;&lt;/script&gt; &amp; co", svg)
        self.assertIn("<title>T &lt;b&gt;</title>", svg)

    def test_end_labels_do_not_overlap(self):
        series = [{"name": "series %d" % i, "y": [1.0 + i * 0.001] * len(XS)} for i in range(4)]
        svg, _ = plot.render({"panels": [{"kind": "xy", "x": XS, "series": series}]})
        ys = sorted(float(m) for m in re.findall(r'<g class="end-label[^"]*"><text class="t-label" x="[^"]+" y="([^"]+)"', svg))
        self.assertEqual(len(ys), 4)
        for a, b in zip(ys, ys[1:]):
            self.assertGreaterEqual(b - a, 12)

    def test_numpy_like_values(self):
        class Arr(list):
            def tolist(self):
                return list(self)
        svg, _ = plot.render({"panels": [{"kind": "xy", "x": Arr(XS), "series": [{"name": "y", "y": Arr(XS)}]}]})
        parse(svg)

    @perf_only
    def test_fast(self):
        spec = {"panels": [xy_spec()["panels"][0], {"kind": "heatmap", "matrix": [[i * j for j in range(12)] for i in range(12)]}]}
        t = time.perf_counter()
        for _ in range(10):
            plot.render(spec)
        self.assertLess((time.perf_counter() - t) / 10 * 1000, 10)


class Errors(unittest.TestCase):
    def check(self, spec, words):
        with self.assertRaises(plot.PlotError) as cm:
            plot.render(spec)
        for w in words:
            self.assertIn(w, str(cm.exception))

    def test_messages(self):
        self.check([], ["must return a dict"])
        self.check({}, ["no panels"])
        self.check({"panels": [{"kind": "pie"}]}, ["unknown kind", "pie"])
        self.check({"panels": [{"kind": "xy", "x": [1, 2], "series": [{"y": [1, 2, 3]}]}]}, ["x has 2 values but y has 3"])
        self.check({"panels": [{"kind": "xy", "series": [{"y": ["a"]}]}]}, ["not a number"])
        self.check({"panels": [{"kind": "heatmap", "matrix": [[1, 2], [3]]}]}, ["row 1 has 1 values"])
        self.check({"panels": [{"kind": "scene", "shapes": [{"type": "star"}]}]}, ["unknown shape type", "star"])
        self.check({"panels": [{"kind": "xy"}] * 5}, ["at most 4 panels"])


class Helpers(unittest.TestCase):
    def test_ticks(self):
        ticks, step = plot.nice_ticks(0, 1, 5)
        self.assertEqual(step, 0.2)
        self.assertEqual([plot.fmt_num(t, step) for t in ticks], ["0", "0.2", "0.4", "0.6", "0.8", "1.0"])
        self.assertEqual(plot.fmt_num(-2.5, 0.5), "−2.5")
        self.assertEqual(plot.fmt_num(12000, 2000), "12,000")

    def test_coerce(self):
        controls = [{"name": "t", "kind": "slider", "min": 0.1, "max": 5, "step": 0.05, "value": 1},
                    {"name": "n", "kind": "slider", "min": 1, "max": 40, "step": 1, "value": 3},
                    {"name": "k", "kind": "steps", "options": ["a", "b"], "value": 0}]
        v = plot.coerce(controls, {"t": 0.30000000000000004, "n": 7.0, "k": 5})
        self.assertEqual(v, {"t": 0.3, "n": 7, "k": 1})
        self.assertIsInstance(v["n"], int)
        self.assertEqual(plot.coerce(controls, {"t": 99}), {"t": 5.0, "n": 3, "k": 0})


if __name__ == "__main__":
    unittest.main()
