"""Every figure in figures/ and every starter passes the figure test (defaults, presets,
20 random states, < 30 ms, no NaN, well-formed SVG)."""

import importlib.util
import shutil
import tempfile
import types
import unittest
from pathlib import Path

from bazinga import figures
import os as _os
import sys as _sys

_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from perf_support import PERF, perf_only  # noqa: E402,F401

ROOT = Path(__file__).resolve().parent.parent


class SiteFigures(unittest.TestCase):
    def test_every_figure(self):
        cfg = types.SimpleNamespace(root=ROOT, figures_dir=ROOT / "figures", drawings_dir=ROOT / "drawings")  # noqa: site (this site's own figures, skipped when it has none)
        found = figures.discover(cfg)
        if not found:
            self.skipTest("this site has no figures of its own")
        for name in found:
            with self.subTest(figure=name):
                missing = [r for r in figures._declared_requires(ROOT / "figures" / f"{name}.py")
                           if importlib.util.find_spec(r) is None]
                if missing:
                    self.skipTest(f"{name} needs {missing} (optional; see requirements.txt)")
                self.assertEqual(figures.test_figure(name, cfg), [])


class MissingPackage(unittest.TestCase):
    """E-1: a figure whose declared package (numpy) is not installed does not stop the build."""

    def test_a_missing_declared_package_is_a_note_not_a_failure(self):
        import io
        from contextlib import redirect_stderr, redirect_stdout
        from test_core_support import cleanup, make_site, post
        from bazinga import cli, config
        root = make_site({"posts/a": post(body="Before.\n\n::figure needs_pkg\n\nAfter.")})
        try:
            (root / "figures").mkdir()
            (root / "figures" / "needs_pkg.py").write_text(
                "import bazinga_not_installed_pkg as np\nTITLE = 'x'\nCAPTION = ''\nREQUIRES = ['bazinga_not_installed_pkg']\n"
                "CONTROLS = []\n\ndef compute(_narrow=0):\n    return {'panels': []}\n", encoding="utf-8")
            out = io.StringIO()
            saved = config.ROOT
            try:
                with redirect_stdout(out), redirect_stderr(out):
                    code = cli.main(["--root", str(root), "build"])
            finally:
                config.set_root(saved)
            self.assertEqual(code, 0, out.getvalue())
            html = (root / "_site/posts/a/index.html").read_text(encoding="utf-8")
            self.assertIn("is not shown in this build", html)
            self.assertIn("bazinga_not_installed_pkg", html)
            with self.assertRaises(figures.FigureNeedsPackage):
                figures.load("needs_pkg", types.SimpleNamespace(root=root, figures_dir=root / "figures"))
            # an import the figure does not declare is still an error
            (root / "figures" / "needs_pkg.py").write_text("import bazinga_not_installed_pkg\n", encoding="utf-8")
            with self.assertRaises(figures.FigureError) as cm:
                figures.load("needs_pkg", types.SimpleNamespace(root=root, figures_dir=root / "figures"))
            self.assertNotIsInstance(cm.exception, figures.FigureNeedsPackage)
        finally:
            cleanup(root)

    def test_requirements_install_on_python_3_11(self):
        req = (ROOT / "requirements.txt").read_text(encoding="utf-8")
        self.assertIn('numpy==2.4.6; python_version < "3.12"', req)     # numpy 2.5 needs Python 3.12
        self.assertIn('numpy==2.5.4; python_version >= "3.12"', req)
        self.assertNotRegex(req, r"(?m)^numpy==[^;\n]*$")


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
