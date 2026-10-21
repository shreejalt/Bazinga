"""bazinga.figures: the module contract, error messages, HTML, assets, CLI hooks."""

import html
import io
import json
import re
import shutil
import tempfile
import textwrap
import types
import unittest
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path

from bazinga import figures

GOOD = '''
TITLE = "Good"
CAPTION = "A caption & more."
CONTROLS = [
    {"name": "a", "kind": "slider", "label": "Amount", "min": 0, "max": 2, "step": 0.1, "value": 1, "play": True},
    {"name": "k", "kind": "steps", "label": "Kind", "options": ["x", "y", "z"], "value": 0},
    {"name": "s", "kind": "toggle", "label": "Scale", "options": ["lin", "log"], "value": 0},
]
PRESETS = [{"label": "Big", "values": {"a": 2, "k": 2}}]
def compute(a=1.0, k=0, s=0, _narrow=0):
    return {"panels": [{"kind": "xy", "series": [{"name": "y", "y": [a * i for i in range(10)]}]}],
            "readouts": [{"label": "a", "value": "%.1f" % a}]}
'''


class _Balance(HTMLParser):
    VOID = {"input", "br", "img", "hr", "meta", "link", "source", "wbr", "col", "area", "base", "embed", "track"}

    def __init__(self):
        super().__init__()
        self.stack, self.problems = [], []

    def handle_starttag(self, tag, attrs):
        if tag not in self.VOID:
            self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        pass

    def handle_endtag(self, tag):
        if not self.stack or self.stack[-1] != tag:
            self.problems.append("unexpected </%s> (open: %s)" % (tag, self.stack[-3:]))
        else:
            self.stack.pop()


def unbalanced(markup):
    b = _Balance()
    b.feed(markup)
    b.close()
    return b.problems + (["unclosed: %s" % b.stack] if b.stack else [])


class Site:
    """A temporary site with a figures/ folder."""

    def __init__(self):
        self.dir = Path(tempfile.mkdtemp())
        (self.dir / "figures").mkdir()
        self.cfg = types.SimpleNamespace(root=self.dir, figures_dir=self.dir / "figures",
                                         drawings_dir=self.dir / "drawings")

    def add(self, name, src):
        p = self.cfg.figures_dir / (name + ".py")
        p.write_text(textwrap.dedent(src))
        return p

    def close(self):
        shutil.rmtree(self.dir, ignore_errors=True)


class Contract(unittest.TestCase):
    def setUp(self):
        self.site = Site()

    def tearDown(self):
        self.site.close()

    def err(self, src, *words, name="bad"):
        self.site.add(name, src)
        with self.assertRaises(figures.FigureError) as cm:
            figures.load(name, self.site.cfg)
        msg = str(cm.exception)
        for w in words:
            self.assertIn(w, msg)
        return msg

    def test_good(self):
        self.site.add("good", GOOD)
        mod = figures.load("good", self.site.cfg)
        self.assertEqual(figures.defaults(mod), {"a": 1.0, "k": 0, "s": 0})
        self.assertEqual(figures.test_figure("good", self.site.cfg), [])
        self.assertEqual(list(figures.discover(self.site.cfg)), ["good"])

    def test_missing_compute(self):
        self.err('TITLE = "x"\nCONTROLS = []\n', "no compute()")

    def test_missing_title(self):
        self.err("def compute(_narrow=0):\n    return {}\n", "TITLE")

    def test_bad_kind(self):
        self.err(GOOD.replace('"kind": "toggle"', '"kind": "knob"'), "unknown kind 'knob'", "slider, steps, toggle")

    def test_value_out_of_range(self):
        self.err(GOOD.replace('"step": 0.1, "value": 1', '"step": 0.1, "value": 7'), "outside 0..2")

    def test_toggle_needs_two(self):
        self.err(GOOD.replace('["lin", "log"]', '["lin", "log", "sqrt"]'), "exactly two options")

    def test_unknown_preset_control(self):
        self.err(GOOD.replace('{"a": 2, "k": 2}', '{"amount": 2}'), "'amount' is not a control")

    def test_preset_out_of_range(self):
        self.err(GOOD.replace('{"a": 2, "k": 2}', '{"k": 3}'), "option index 0..2")

    def test_reset_label_reserved(self):
        self.err(GOOD.replace('"label": "Big"', '"label": "Reset"'), "added automatically")

    def test_signature(self):
        self.err(GOOD.replace("def compute(a=1.0, k=0, s=0, _narrow=0)", "def compute(a=1.0, _narrow=0)"),
                 "does not accept k, s")

    def test_duplicate_names(self):
        self.err(GOOD.replace('"name": "k"', '"name": "a"'), "used twice")

    def test_import_error_and_line(self):
        self.err("import not_a_real_package_xyz\n", "not_a_real_package_xyz", "REQUIRES")
        msg = self.err('TITLE = "x"\nx = 1 / 0\n', "ZeroDivisionError", "line 2")
        self.assertIn("importing", msg)

    def test_syntax_error(self):
        self.err("def compute(:\n", "syntax error", "line 1")

    def test_unknown_figure(self):
        self.site.add("softmax", GOOD)
        with self.assertRaises(figures.FigureError) as cm:
            figures.load("softmx", self.site.cfg)
        self.assertIn("Did you mean 'softmax'", str(cm.exception))
        with self.assertRaises(figures.FigureError):
            figures.load("../etc", self.site.cfg)

    def test_compute_error_is_reported(self):
        self.site.add("boom", GOOD.replace("return {", "raise ValueError('nope')\n    return {"))
        with self.assertRaises(figures.FigureError) as cm:
            figures.run("boom", cfg=self.site.cfg)
        self.assertIn("ValueError: nope", str(cm.exception))
        self.assertIn("line", str(cm.exception))

    def test_bad_spec_is_reported(self):
        self.site.add("spec", GOOD.replace('"kind": "xy"', '"kind": "pie"'))
        with self.assertRaises(figures.FigureError) as cm:
            figures.run("spec", cfg=self.site.cfg)
        self.assertIn("unknown kind 'pie'", str(cm.exception))

    def test_test_figure_finds_nan_and_slowness(self):
        self.site.add("nanfig", GOOD.replace("[a * i for i in range(10)]", "[float('nan')] * 3"))
        problems = figures.test_figure("nanfig", self.site.cfg)
        self.assertTrue(any("NaN" in p for p in problems), problems)
        self.site.add("slow", GOOD.replace("return {", "import time; time.sleep(0.04)\n    return {"))
        problems = figures.test_figure("slow", self.site.cfg, n_random=1)
        self.assertTrue(any("budget" in p for p in problems), problems)

    def test_cache_reloads_on_change(self):
        p = self.site.add("ch", GOOD)
        figures.load("ch", self.site.cfg)
        p.write_text(GOOD.replace('TITLE = "Good"', 'TITLE = "Changed title"'))
        self.assertEqual(figures.load("ch", self.site.cfg).TITLE, "Changed title")


class Html(unittest.TestCase):
    def setUp(self):
        self.site = Site()
        self.site.add("good", GOOD)

    def tearDown(self):
        self.site.close()

    def test_figure_html(self):
        h = figures.figure_html("good", cfg=self.site.cfg)
        self.assertEqual(unbalanced(h), [])
        self.assertTrue(h.startswith('<figure class="fig" data-figure="good"'))
        data = json.loads(html.unescape(re.search(r'data-bazinga="([^"]*)"', h).group(1)))
        self.assertRegex(data["module"], r"^figures/good\.py\?v=[0-9a-f]{10}$")
        self.assertRegex(data["plot"], r"^figures/_plot\.py\?v=[0-9a-f]{10}$")
        self.assertEqual(data["values"], {"a": 1.0, "k": 0, "s": 0})
        self.assertEqual(len(data["controls"]), 3)
        self.assertIn('<input type="range" name="a" min="0" max="2" step="0.1" value="1">', h)
        self.assertIn('<span class="fig-ctl-label">Amount</span>', h)
        self.assertIn('class="fig-play"', h)
        self.assertEqual(h.count('type="radio"'), 5)
        self.assertIn(">Big</button>", h)
        self.assertIn(">Reset</button>", h)
        self.assertIn("fig-svg-wide", h)
        self.assertIn("fig-svg-narrow", h)
        self.assertIn("A caption &amp; more.", h)
        for word in ("Python", "Pyodide", "pyodide"):
            self.assertNotIn(word, re.sub(r"<[^>]+>", " ", h))

    def test_start_preset(self):
        h = figures.figure_html("good", start="Big", cfg=self.site.cfg)
        self.assertIn('value="2"', h)
        with self.assertRaises(figures.FigureError) as cm:
            figures.figure_html("good", start="Bgi", cfg=self.site.cfg)
        self.assertIn("Did you mean 'Big'", str(cm.exception))

    def test_write_assets(self):
        out = self.site.dir / "_site"
        figures.write_assets(self.site.cfg, {"good"}, out)
        self.assertTrue((out / "figures/good.py").is_file())
        self.assertTrue((out / "figures/_plot.py").is_file())
        with self.assertRaises(figures.FigureError):
            figures.write_assets(self.site.cfg, {"missing"}, out)


class Cli(unittest.TestCase):
    def setUp(self):
        self.site = Site()

    def tearDown(self):
        self.site.close()

    def test_new_and_test(self):
        p = figures.cli_new("my_plot", "slider_plot", cfg=self.site.cfg)
        self.assertEqual(p, self.site.cfg.figures_dir / "my_plot.py")
        buf = io.StringIO()
        self.assertEqual(figures.cli_test(cfg=self.site.cfg, out=buf), 0)
        self.assertIn("ok   my_plot", buf.getvalue())
        with self.assertRaises(figures.FigureError):
            figures.cli_new("my_plot", "slider_plot", cfg=self.site.cfg)   # exists
        with self.assertRaises(figures.FigureError):
            figures.cli_new("My-Plot", "slider_plot", cfg=self.site.cfg)
        with self.assertRaises(figures.FigureError) as cm:
            figures.cli_new("x", "nope", cfg=self.site.cfg)
        self.assertIn("slider_plot", str(cm.exception))

    def test_new_drawing(self):
        p = figures.cli_new("steps_one", "pipeline", cfg=self.site.cfg)
        self.assertEqual(p, self.site.cfg.drawings_dir / "steps_one.py")

    def test_cli_test_reports_failure(self):
        self.site.add("bad", GOOD.replace('"kind": "xy"', '"kind": "pie"'))
        buf = io.StringIO()
        self.assertEqual(figures.cli_test(cfg=self.site.cfg, out=buf), 1)
        self.assertIn("FAIL bad", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
