"""Every figure in figures/ and every starter passes the figure test (defaults, presets,
20 random states, < 30 ms, no NaN, well-formed SVG)."""

import shutil
import tempfile
import types
import unittest
from pathlib import Path

from bazinga import figures

ROOT = Path(__file__).resolve().parent.parent


class SiteFigures(unittest.TestCase):
    def test_every_figure(self):
        cfg = types.SimpleNamespace(root=ROOT, figures_dir=ROOT / "figures", drawings_dir=ROOT / "drawings")
        found = figures.discover(cfg)
        self.assertTrue(found, "figures/ has no figures")
        for name in found:
            with self.subTest(figure=name):
                self.assertEqual(figures.test_figure(name, cfg), [])


class Starters(unittest.TestCase):
    def test_every_starter_works_when_copied(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            cfg = types.SimpleNamespace(root=tmp, figures_dir=tmp / "figures", drawings_dir=tmp / "drawings")
            for starter in figures.STARTERS:
                with self.subTest(starter=starter):
                    figures.cli_new("copy_of_" + starter, starter, cfg=cfg)   # runs test_figure itself
                    self.assertEqual(figures.test_figure("copy_of_" + starter, cfg), [])
                    self.assertTrue(figures.figure_html("copy_of_" + starter, cfg=cfg).startswith("<figure"))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_a_page_can_show_a_starter_as_it_is(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            cfg = types.SimpleNamespace(root=tmp, figures_dir=tmp / "figures", drawings_dir=tmp / "drawings")
            self.assertTrue(figures.figure_html("starter_sampling", cfg=cfg).startswith("<figure"))
            out = tmp / "site"
            figures.write_assets(cfg, ["starter_sampling"], out)
            self.assertTrue((out / "figures" / "starter_sampling.py").is_file())
            with self.assertRaises(figures.FigureError):
                figures.figure_html("starter_nothing", cfg=cfg)
            from bazinga import drawings
            self.assertIn("<svg", drawings.drawing_html("starter_tree.taxonomy", cfg=cfg))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_starters_are_listed_with_their_titles(self):
        import io
        buf = io.StringIO()
        self.assertEqual(figures.cli_starters(buf), 0)
        for starter in figures.STARTERS + figures.DRAWING_STARTERS:
            self.assertIn(starter, buf.getvalue())


if __name__ == "__main__":
    unittest.main()
