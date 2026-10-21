"""tessera.draw and tessera.drawings: the kit, the example drawing, the starters, the errors."""

import shutil
import tempfile
import types
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from tessera import draw, drawings, figures

ROOT = Path(__file__).resolve().parent.parent


class Kit(unittest.TestCase):
    def test_boxes_arrows_groups(self):
        d = draw.Diagram(600, title="T & U")
        a, b, c = d.row(["One", ("Two", "second line"), {"text": "Three", "style": "second"}], y=10)
        d.chain([a, b, c], labels=["x", "y"])
        d.arrow(c, a, "back", bend=-30, start="bottom", end="bottom", style="muted dashed")
        col = d.column(["p", "q"], x=10, y=200, w=120)
        g = d.grid(["r", "s", "t", "u"], cols=2, x=300, y=200, w=100)
        d.group("Group <1>", col)
        d.label(300, 400, "a label")
        d.note("a note at the bottom")
        svg = d.svg()
        root = ET.fromstring(svg)
        self.assertEqual(root[0].tag.split("}")[-1], "title")
        self.assertIn("T &amp; U", svg)
        self.assertIn("GROUP &lt;1&gt;", svg)
        self.assertEqual(svg.count('class="dg-head'), 3)
        self.assertIn("dg-box s-second", svg)
        self.assertEqual(svg, d.svg())                        # deterministic
        vb = [float(v) for v in root.get("viewBox").split()]
        self.assertGreaterEqual(vb[3], 400)                   # height fits the content
        self.assertEqual(len(g), 4)

    def test_arrow_endpoints_sit_on_edges(self):
        d = draw.Diagram(600)
        a = d.box(0, 0, 100, 50, "a")
        b = d.box(300, 0, 100, 50, "b")
        d.arrow(a, b)
        svg = d.svg()
        self.assertIn('d="M104 25L', svg)                    # leaves the right edge, mid-height

    def test_text_wraps(self):
        d = draw.Diagram(400)
        b = d.box(0, 0, 120, None, "a rather long piece of text that must wrap")
        self.assertGreater(b.h, 60)
        self.assertGreater(d.svg().count("dg-text-main"), 2)

    def test_errors(self):
        d = draw.Diagram(400)
        with self.assertRaises(draw.DrawError):
            d.box(0, 0, 0, 10, "x")
        with self.assertRaises(draw.DrawError):
            d.group("empty", [])
        with self.assertRaises(draw.DrawError):
            d.arrow("nope", (1, 2)).svg()


class Drawings(unittest.TestCase):
    def setUp(self):
        self.cfg = types.SimpleNamespace(root=ROOT, figures_dir=ROOT / "figures", drawings_dir=ROOT / "drawings")

    def test_example(self):
        h = drawings.drawing_html("pipeline.overview", "Write & publish", cfg=self.cfg)
        self.assertTrue(h.startswith('<figure class="drawing" data-drawing="pipeline.overview">'))
        self.assertIn('<div class="drawing-svg drawing-wide"><svg', h)        # overview() has a phone layout
        self.assertIn('<div class="drawing-svg drawing-narrow"><svg', h)
        self.assertIn("<figcaption>Write &amp; publish</figcaption>", h)
        ET.fromstring(h)

    def test_every_drawing_function(self):
        for module, fns in drawings.discover(self.cfg).items():
            for fn in fns:
                if fn[0].isupper():
                    continue
                with self.subTest(drawing="%s.%s" % (module, fn)):
                    ET.fromstring(drawings.render("%s.%s" % (module, fn), self.cfg))

    def test_errors(self):
        cases = [("pipeline", "module.function"), ("nope.fn", "no drawings/nope.py"),
                 ("pipeline.overveiw", "Did you mean overview()"), ("../x.y", "not a drawing reference")]
        for ref, words in cases:
            with self.subTest(ref=ref):
                with self.assertRaises(drawings.DrawingError) as cm:
                    drawings.drawing_html(ref, cfg=self.cfg)
                self.assertIn(words, str(cm.exception))

    def test_bad_return_and_exception(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            (tmp / "drawings").mkdir()
            (tmp / "drawings" / "bad.py").write_text("def text():\n    return 'hello'\n\ndef boom():\n    return 1 / 0\n")
            cfg = types.SimpleNamespace(root=tmp, drawings_dir=tmp / "drawings")
            with self.assertRaises(drawings.DrawingError) as cm:
                drawings.render("bad.text", cfg)
            self.assertIn("must return an SVG string", str(cm.exception))
            with self.assertRaises(drawings.DrawingError) as cm:
                drawings.render("bad.boom", cfg)
            self.assertIn("ZeroDivisionError", str(cm.exception))
            self.assertIn("line 5", str(cm.exception))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_starters(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            cfg = types.SimpleNamespace(root=tmp, figures_dir=tmp / "figures", drawings_dir=tmp / "drawings")
            for starter in figures.DRAWING_STARTERS:
                figures.cli_new("s_" + starter, starter, cfg=cfg)
            # steps() has a phone layout (narrow=1), so the page gets both versions
            self.assertIn('<div class="drawing-svg drawing-wide drawing-fit"><svg', drawings.drawing_html("s_pipeline.steps", cfg=cfg))
            found = drawings.discover(cfg)
            self.assertEqual(sorted(found), ["s_architecture", "s_blocks", "s_flowchart", "s_pipeline", "s_timeline",
                                             "s_tree"])
            self.assertEqual(found["s_blocks"], ["by_hand", "stack"])
            for module, fns in found.items():
                for fn in fns:
                    for narrow in (0, 1):
                        with self.subTest(drawing="%s.%s" % (module, fn), narrow=narrow):
                            ET.fromstring(drawings.render("%s.%s" % (module, fn), cfg, narrow=narrow))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
