"""M2: on a phone a figure's narrow picture (480 units wide) is shown about 316 px wide on a 360-px screen, so its
smallest text must be at least 16.5 units (about 10 px) after every scale() on the way, in every figure and starter,
at their defaults and presets. The theme's phone margins that give the picture that width are checked too."""
import contextlib
import io
import re
import shutil
import tempfile
import types
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from bazinga import figures, plot

ROOT = Path(__file__).resolve().parent.parent
MIN_UNITS = plot.NARROW_MIN_FS


def smallest_text(svg: str) -> float:
    root = ET.fromstring(svg)
    best = [float("inf")]

    def walk(el, k):
        m = re.search(r"scale\(([\d.]+)", el.get("transform") or "")
        if m:
            k *= float(m.group(1))
        if el.tag.endswith("text") and el.get("font-size"):
            best[0] = min(best[0], float(el.get("font-size")) * k)
        for c in el:
            walk(c, k)
    walk(root, 1.0)
    return best[0]


class PhoneText(unittest.TestCase):
    def test_layout_constants(self):
        self.assertGreaterEqual(plot.LAYOUTS[1]["fs_small"], MIN_UNITS)
        self.assertGreaterEqual(plot.LAYOUTS[1]["fs"], MIN_UNITS)

    def test_every_figure_and_starter_on_a_phone(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        site = types.SimpleNamespace(root=ROOT, figures_dir=ROOT / "figures")
        mine = types.SimpleNamespace(root=tmp, figures_dir=tmp / "figures", drawings_dir=tmp / "drawings")
        todo = [(n, site) for n in figures.discover(site)]
        for s in figures.STARTERS:
            with contextlib.redirect_stdout(io.StringIO()):
                figures.cli_new("st_" + s, s, cfg=mine)
            todo.append(("st_" + s, mine))
        for name, cfg in todo:
            try:
                mod = figures.load(name, cfg)
            except figures.FigureNeedsPackage:
                continue
            states = [figures.defaults(mod)] + [dict(figures.defaults(mod), **p["values"]) for p in figures.presets(mod)]
            for values in states:
                with self.subTest(figure=name, values=values):
                    svg = figures.run(name, values, 1, cfg)["svg"]
                    self.assertGreaterEqual(round(smallest_text(svg), 1), MIN_UNITS)

    def test_phone_margins_leave_room_for_figures(self):
        css = (ROOT / "bazinga/theme/assets/css/site.css").read_text(encoding="utf-8")
        block = css[css.index("/* ---------- phones: more width for figures"):]
        self.assertIn(".sheet{padding:22px 14px 44px}", block)
        self.assertIn(".memo .body > .fig", block)


if __name__ == "__main__":
    unittest.main()
