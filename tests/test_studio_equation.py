"""The Studio's equation helper: the maths API (one formula or many), and the helper's palette and templates.

Every palette snippet and every template is rendered through the real converter, so nothing the helper offers can
insert a formula that fails.
"""
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tessera.mathml import check
from tessera.studio.api import Studio
from tessera.studio.security import Refused

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "tessera" / "studio" / "static"
EQUATION = (STATIC / "panels" / "equation.js").read_text(encoding="utf-8")
TIPS = (STATIC / "mathtips.js").read_text(encoding="utf-8")
BOX = "□"


def js_strings(block: str) -> list[str]:
    """The string literals ("…" and `…`) in a piece of the helper's source, as Python strings."""
    out = []
    for m in re.finditer(r'"((?:[^"\\\n]|\\.)*)"|`((?:[^`\\]|\\.)*)`', block):
        if m.group(1) is not None:
            out.append(json.loads('"' + m.group(1) + '"'))
        else:
            out.append(m.group(2).replace("\\\\", "\\").replace("${BOX}", BOX).replace("\\n", "\n"))
    return out


def const_block(name: str) -> str:
    start = EQUATION.index(f"const {name} = [")
    end = EQUATION.index("];", start)
    return EQUATION[start:end]


class Api(unittest.TestCase):
    def setUp(self):
        self.studio = Studio(ROOT)

    def test_one_formula(self):
        res = self.studio.math({"tex": r"\frac{a}{b}", "display": True})
        self.assertTrue(res["available"])
        self.assertIn("<mfrac>", res["mathml"])

    def test_error_has_place_and_fix(self):
        res = self.studio.math({"tex": r"a + \alpah", "display": False})
        self.assertNotIn("mathml", res)
        self.assertIn(r"\alpah", res["error"])
        self.assertIn(r"\alpha", res["hint"])
        self.assertEqual((res["line"], res["column"], res["index"], res["length"]), (0, 4, 4, 6))

    def test_tag_and_label_in_display(self):
        res = self.studio.math({"tex": r"E = mc^2 \tag{4} \label{eq:e}", "display": True})
        self.assertEqual((res["tag"], res["label"]), ("4", "eq:e"))

    def test_many_at_once(self):
        res = self.studio.math({"items": [{"tex": "x^2", "display": False}, {"tex": "x^10", "display": False},
                                          {"tex": r"\sum_i x_i", "display": True}]})
        r = res["results"]
        self.assertEqual(len(r), 3)
        self.assertIn("mathml", r[0])
        self.assertIn("only the 1", r[1]["error"])
        self.assertIn("<munder>", r[2]["mathml"])

    def test_limits(self):
        with self.assertRaises(Refused):
            self.studio.math({"items": [{"tex": "x"}] * 401})
        with self.assertRaises(Refused):
            self.studio.math({"tex": "x" * 20001})


class Helper(unittest.TestCase):
    def test_every_palette_snippet_renders(self):
        n = 0
        for name in ("GREEK", "OPERATORS", "ARROWS", "ACCENTS", "BIG", "BRACKETS", "STRUCTURES"):
            strings = js_strings(const_block(name))
            snippets = strings[1::3] if name != "GREEK" else strings[1::2]
            for s in snippets:
                with self.subTest(group=name, snippet=s):
                    tex = s.replace(BOX, "x")
                    if tex.startswith(("^", "_")) or tex == "'":
                        tex = "y" + tex
                    res = check(tex, True)
                    self.assertTrue(res["ok"], f"{s}: {res.get('error')}")
                    n += 1
        self.assertGreater(n, 140)

    def test_templates_render_and_cover_the_list(self):
        block = EQUATION[EQUATION.index("export const TEMPLATES = ["):EQUATION.index("];", EQUATION.index("export const TEMPLATES"))]
        strings = js_strings(block)
        names, texs = strings[0::2], strings[1::2]
        self.assertGreaterEqual(len(names), 20)
        for want in ("Softmax", "Cross-entropy", "Attention", "Gradient descent", "Adam", "KL divergence", "Bayes' rule",
                     "Normal density", "Expectation", "Variance", "Mean squared error", "Sigmoid", "ReLU", "Convolution",
                     "Layer norm", "Chain rule", "Matrix product", "L2 norm", "Logistic regression", "Entropy"):
            self.assertIn(want, names)
        for name, tex in zip(names, texs):
            with self.subTest(template=name):
                for display in (True, False):
                    res = check(tex, display)
                    self.assertTrue(res["ok"], f"{name}: {res.get('error')}")

    def test_builders_render(self):
        for kind in ("pmatrix", "bmatrix", "vmatrix", "Bmatrix", "matrix"):
            tex = "\\begin{" + kind + "}\n" + " \\\\\n".join([" & ".join(["x"] * 3)] * 2) + "\n\\end{" + kind + "}"
            self.assertTrue(check(tex, True)["ok"], kind)
        cases = "\\begin{cases}\nx & \\text{if } x \\\\\nx & \\text{otherwise}\n\\end{cases}"
        self.assertTrue(check(cases, True)["ok"])
        aligned = "\\begin{aligned}\nx &= x \\\\\n&= x \\\\\n&= x\n\\end{aligned}"
        self.assertTrue(check(aligned, True)["ok"])
        self.assertIn("export function matrixSnippet", EQUATION)
        self.assertIn("export function casesSnippet", EQUATION)
        self.assertIn("export function alignedSnippet", EQUATION)

    def test_features_are_wired(self):
        for needle in ('"Number this equation"', "[eq:${", "{#eq:${nm}}", "/api/llm/equation", "state.llm",
                       '"Inside a sentence"', '"On its own line"', "Mod-Enter", "Shift-Tab", "mathAt(",
                       '"Insert reference"', "Templates", "Matrix", "Cases", "Derivation"):
            self.assertIn(needle, EQUATION, needle)
        for needle in ("hoverTooltip", "linter(", "showTooltip", '"Edit equation"', "/api/math"):
            self.assertIn(needle, TIPS, needle)
        editor = (STATIC / "editor.js").read_text(encoding="utf-8")
        self.assertIn("mathExtensions(", editor)

    @unittest.skipUnless(shutil.which("node"), "node is not installed")
    def test_scripts_parse_as_modules(self):
        with tempfile.TemporaryDirectory() as tmp:
            for f in (STATIC / "panels" / "equation.js", STATIC / "mathtips.js"):
                copy = Path(tmp) / (f.stem + ".mjs")
                copy.write_text(f.read_text(encoding="utf-8"), encoding="utf-8")
                r = subprocess.run(["node", "--check", str(copy)], capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, r.stderr)

    def test_named_equation_numbers_match_the_page(self):
        """The helper numbers equations the way the page does: only named ones, \\tag sets its own."""
        self.assertIn("if (tag) number = tag[1];", TIPS)
        self.assertIn("n += 1", TIPS)


if __name__ == "__main__":
    unittest.main()
