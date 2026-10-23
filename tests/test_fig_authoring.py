"""Figure authoring: the renderer's additions (dot sizes and labels, stems, grids, lines through zero, shading between
curves, label room for monospaced themes), the new starters, the test report in plain words, and the CLI's
figure new --from builder / list / preview."""

import io
import re
import shutil
import tempfile
import types
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from bazinga import cli, figbuilder, figures, plot
import os as _os
import sys as _sys

_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from perf_support import PERF, perf_only  # noqa: E402,F401

ROOT = Path(__file__).resolve().parent.parent


def site():
    tmp = Path(tempfile.mkdtemp(prefix="fig-authoring-"))
    (tmp / "figures").mkdir()
    (tmp / "content" / "reads").mkdir(parents=True)
    cfg = types.SimpleNamespace(root=tmp, figures_dir=tmp / "figures", drawings_dir=tmp / "drawings",
                                content_dir=tmp / "content")
    return tmp, cfg


class PlotAdditions(unittest.TestCase):
    def render(self, panel, narrow=0):
        svg, _ = plot.render({"panels": [panel]}, narrow=narrow)
        ET.fromstring(svg)
        return svg

    def test_dot_sizes_and_labels(self):
        svg = self.render({"kind": "xy", "series": [{"name": "s", "x": [0, 1, 2], "y": [1, 2, 3], "style": "points",
                                                      "sizes": [3, 8, None], "labels": ["a", "", "c"]}]})
        radii = re.findall(r'<circle class="dot s-points" cx="[^"]+" cy="[^"]+" r="([^"]+)"', svg)
        self.assertEqual(radii, ["3", "8", "4.5"])
        self.assertIn(">a</text>", svg)
        self.assertIn(">c</text>", svg)
        self.assertNotIn('class="end-label', svg)            # dots get no line-end label

    def test_sizes_are_clamped_and_checked(self):
        svg = self.render({"kind": "xy", "series": [{"y": [1, 2], "style": "points", "sizes": [0.1, 500]}]})
        self.assertEqual(re.findall(r'r="([^"]+)"/>', svg)[:2], ["1", "40"])
        with self.assertRaises(plot.PlotError):
            plot.render({"panels": [{"series": [{"y": [1, 2], "style": "points", "sizes": [1]}]}]})
        with self.assertRaises(plot.PlotError):
            plot.render({"panels": [{"series": [{"y": [1, 2], "style": "points", "labels": ["x"]}]}]})

    def test_stems(self):
        svg = self.render({"kind": "xy", "series": [{"x": [0, 1, 2], "y": [0.2, 0.5, 0.3], "style": "main stems"}],
                           "y_min": 0})
        self.assertEqual(svg.count('class="stem s-main s-stems"'), 1)
        self.assertEqual(len(re.findall(r'class="dot s-main s-stems"', svg)), 3)

    def test_grid_and_origin(self):
        plain = self.render({"kind": "scene", "shapes": [{"type": "point", "x": 0, "y": 0}],
                             "x_min": -2, "x_max": 2, "y_min": -2, "y_max": 2})
        grid = self.render({"kind": "scene", "shapes": [{"type": "point", "x": 0, "y": 0}], "grid": True, "origin": True,
                            "x_min": -2, "x_max": 2, "y_min": -2, "y_max": 2})
        self.assertNotIn('class="grid"', plain)
        self.assertGreater(grid.count('class="grid"'), 4)
        self.assertEqual(grid.count('class="axis zero"'), 2)

    def test_shading_between_two_curves(self):
        xs = [0, 1, 2, 3]
        svg = self.render({"kind": "xy", "x": xs, "series": [
            {"name": "gap", "y": [1, 2, 4, 8], "base": [1, 2, 3, 4], "style": "main area", "label_at": "none"},
            {"name": "top", "y": [1, 2, 4, 8]}, {"name": "bottom", "y": [1, 2, 3, 4]}]})
        self.assertEqual(svg.count('class="fill s-main s-area"'), 1)

    def test_monospaced_labels_have_room(self):
        # a monospaced face draws every character 0.6 em wide; the estimate must never be narrower
        for text in ("best fit", "iiiiii", "true line", "lllll.,"):
            self.assertGreaterEqual(plot.text_width(text, 10), len(text) * 0.6 * 10 - 1e-9)

    def test_deterministic(self):
        p = {"kind": "xy", "grid": True, "series": [{"x": [0, 1], "y": [0, 1], "style": "points", "sizes": [3, 4],
                                                      "labels": ["p", "q"]}]}
        self.assertEqual(self.render(p), self.render(p))


class NewStarters(unittest.TestCase):
    def setUp(self):
        self.tmp, self.cfg = site()
        for s in ("scatter_fit", "distribution", "matrix_transform", "step_through"):
            figures.cli_new(s, s, cfg=self.cfg)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def readouts(self, name, values=None):
        return figures.run(name, values, cfg=self.cfg)["readouts_html"]

    def test_scatter_is_seeded(self):
        a = figures.run("scatter_fit", {"sample": 3}, cfg=self.cfg)["svg"]
        b = figures.run("scatter_fit", {"sample": 3}, cfg=self.cfg)["svg"]
        c = figures.run("scatter_fit", {"sample": 4}, cfg=self.cfg)["svg"]
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)
        self.assertIn(">1.000<", self.readouts("scatter_fit", {"noise": 0}))     # no noise: a perfect fit

    def test_distribution_band(self):
        self.assertIn("68.3%", self.readouts("distribution"))
        self.assertIn("95.4%", self.readouts("distribution", {"k": 2}))

    def test_matrix_determinant(self):
        self.assertIn(">1.00<", self.readouts("matrix_transform", {"a": 1, "b": 0, "c": 0, "d": 1}))
        self.assertIn("flipped over", self.readouts("matrix_transform", {"a": -1, "b": 0, "c": 0, "d": 1}))
        self.assertIn("squashed onto a line", self.readouts("matrix_transform", {"a": 1, "b": 2, "c": 0.5, "d": 1}))

    def test_bubble_sort_ends_sorted(self):
        mod = figures.load("step_through", self.cfg)
        for k in range(3):
            values = mod.TRACE[mod.NAMES[k]][-1][0]
            self.assertEqual(values, sorted(values))
        self.assertIn("Sorted", self.readouts("step_through", {"step": 28}))


class Report(unittest.TestCase):
    def setUp(self):
        self.tmp, self.cfg = site()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_plain_checks(self):
        figures.cli_new("good", "slider_plot", cfg=self.cfg)
        r = figures.test_report("good", self.cfg)
        self.assertTrue(r["ok"])
        labels = [c["label"] for c in r["checks"]]
        self.assertEqual(labels[0], "It draws at its starting values, wide and on a phone")
        self.assertIn("Every preset draws (2)", labels)
        self.assertTrue(any(l.startswith("Fast enough") for l in labels))
        if PERF:
            self.assertLess(r["slowest_ms"], figures.BUDGET_MS)

    def test_failure_points_at_the_line(self):
        src = (self.tmp / "figures").joinpath("bad.py")
        figures.cli_new("bad", "slider_plot", cfg=self.cfg)
        text = src.read_text().replace("wave = [", "wave = [undefined_name + ", 1)
        src.write_text(text)
        r = figures.test_report("bad", self.cfg)
        self.assertFalse(r["ok"])
        line = next(n for n, l in enumerate(text.splitlines(), 1) if "undefined_name" in l)
        self.assertEqual(r["line"], line)
        self.assertFalse(r["checks"][0]["ok"])
        self.assertIn("undefined_name", r["checks"][0]["detail"])

    def test_syntax_error(self):
        (self.tmp / "figures" / "broken.py").write_text("TITLE = 'x'\ndef compute(:\n")
        r = figures.test_report("broken", self.cfg)
        self.assertFalse(r["ok"])
        self.assertEqual(r["line"], 2)

    def test_made_with(self):
        src = figbuilder.generate(figbuilder.default_spec("bars"))
        self.assertEqual(figures.made_with(src), "builder")
        self.assertEqual(figures.made_with(src.replace("bar_list = []", "bar_list = []  # mine", 1)), "edited")
        self.assertEqual(figures.made_with("TITLE = 'x'"), "code")


class Cli(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="fig-cli-"))
        shutil.copy(ROOT / "tests" / "fixtures" / "example-site" / "site.yml", self.tmp / "site.yml")
        (self.tmp / "content" / "reads").mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        import contextlib
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(["--root", str(self.tmp), *args])
        return code, out.getvalue(), err.getvalue()

    def test_new_from_builder_and_starters(self):
        code, out, err = self.run_cli("figure", "new", "wave", "--from", "builder")
        self.assertEqual(code, 0, err)
        self.assertIn("::figure wave", out)
        self.assertEqual(figures.made_with((self.tmp / "figures" / "wave.py").read_text()), "builder")
        code, out, err = self.run_cli("figure", "new", "heat", "--from", "builder:heatmap")
        self.assertEqual(code, 0, err)
        code, out, err = self.run_cli("figure", "new", "x", "--from", "builder:nope")
        self.assertEqual(code, 1)
        self.assertIn("no builder type 'nope'", err)
        code, out, err = self.run_cli("figure", "new", "sorting", "--from", "step_through")
        self.assertEqual(code, 0, err)
        code, out, err = self.run_cli("figure", "new", "y", "--from", "nope")
        self.assertIn("or builder", err)

    def test_list_test_preview(self):
        self.run_cli("figure", "new", "wave", "--from", "builder")
        self.run_cli("figure", "new", "fit", "--from", "scatter_fit")
        (self.tmp / "content" / "reads" / "p.md").write_text("---\ntitle: P\n---\n\n::figure fit\n")
        code, out, _ = self.run_cli("figure", "list")
        self.assertEqual(code, 0)
        self.assertRegex(out, r"wave\s+A damped wave\s+form\s+3 controls, 1 preset; not used yet")
        self.assertRegex(out, r"fit\s+Fitting a line to noisy points\s+code\s+4 controls, 2 presets; reads/p.md")
        code, out, _ = self.run_cli("figure", "test")
        self.assertEqual(code, 0)
        self.assertIn("ok   wave", out)
        code, out, err = self.run_cli("figure", "preview", "fit")
        self.assertEqual(code, 0, err)
        path = Path(out.strip())
        self.assertTrue(path.is_file())
        page = path.read_text()
        self.assertIn('<figure class="fig" data-figure="fit"', page)
        self.assertIn("Preset: No noise", page)
        self.assertIn("On a phone", page)
        for f in ("assets/js/figure.js", "assets/js/pyworker.js", "assets/css/figure.css", "figures/fit.py",
                  "figures/_plot.py"):
            self.assertTrue((path.parent / f).is_file(), f)
        self.assertNotRegex(re.sub(r"<[^>]+>", " ", page), r"(?i)python|pyodide")
        code, out, err = self.run_cli("figure", "preview", "missing")
        self.assertEqual(code, 1)
        code, out, err = self.run_cli("figure", "preview")
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
