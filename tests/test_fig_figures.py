"""Every figure in figures/ and every starter passes the figure test (defaults, presets,
20 random states, < 30 ms, no NaN, well-formed SVG)."""

import shutil
import tempfile
import types
import unittest
from pathlib import Path

from tessera import figures

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


if __name__ == "__main__":
    unittest.main()
