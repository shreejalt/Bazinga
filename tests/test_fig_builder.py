"""The figure builder: safe expressions with clear messages, every type generating a figure that passes the figure
test, generated files that stand alone (standard library only), and the round trip through the spec line."""

import ast
import copy
import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path

from tessera import figbuilder as fb
from tessera import figures


class Site:
    def __init__(self):
        self.dir = Path(tempfile.mkdtemp(prefix="figbuilder-"))
        (self.dir / "figures").mkdir()
        self.cfg = types.SimpleNamespace(root=self.dir, figures_dir=self.dir / "figures",
                                         drawings_dir=self.dir / "drawings")

    def add(self, name, source):
        (self.dir / "figures" / (name + ".py")).write_text(source, encoding="utf-8")

    def close(self):
        shutil.rmtree(self.dir, ignore_errors=True)


def err(text, scalars=("a", "freq", "x"), arrays=()):
    with unittest.TestCase().assertRaises(fb.ExprError) as cm:
        fb.parse_expr(text, scalars, arrays)
    return cm.exception


class Expressions(unittest.TestCase):
    def test_plain_maths(self):
        e = fb.parse_expr("a*sin(freq*x)*exp(-x)", {"a", "freq", "x"})
        self.assertEqual(e.code, "a * sin(freq * x) * exp(-x)")
        self.assertEqual(e.names, ["a", "freq", "x"])
        self.assertEqual(e.calls, {"sin", "exp"})

    def test_friendly_syntax(self):
        cases = {"x^2": "x ** 2", "2x": "2 * x", "2(x+1)": "2 * (x + 1)", "(x+1)(x-1)": "(x + 1) * (x - 1)",
                 "2pi x": "2 * pi * x", "a x": "a * x", "x²": "x ** 2", "π": "pi", "3 − x": "3 - x",
                 "a(x+1)": "a * (x + 1)", "ln(x)": "log(x)", "1e3*x": "1000.0 * x",
                 "where(x > 0, x, 0)": "x if x > 0 else 0", "2^x": "2.0 ** x"}
        for text, code in cases.items():
            with self.subTest(text=text):
                self.assertEqual(fb.parse_expr(text, {"a", "x"}).code, code)

    def test_comparisons_and_logic(self):
        self.assertEqual(fb.parse_expr("(x > 0) * (x < 1)", {"x"}).code, "(x > 0) * (x < 1)")
        self.assertEqual(fb.parse_expr("0 < x <= 1 and a != 2", {"x", "a"}).code, "0 < x <= 1 and a != 2")

    def test_aggregates_need_a_list(self):
        e = fb.parse_expr("max(y) - min(y) + at(y, 2) + area(y)", {"a"}, {"y"}, where_x="xs")
        self.assertEqual(e.code, "_max(y) - _min(y) + _at(y, xs, 2) + _area(y, xs)")
        self.assertEqual(fb.parse_expr("max(a, 2)", {"a"}, {"y"}).code, "max(a, 2)")
        self.assertIn("whole list", err("y + 1", {"a"}, {"y"}).message)
        self.assertIn("two or more numbers", err("max(a)", {"a"}).message)

    def test_unknown_name_suggests(self):
        e = err("a*sin(freqq*x)")
        self.assertEqual(e.message, "unknown name 'freqq' — did you mean 'freq'?")
        self.assertEqual("a*sin(freqq*x)"[e.col:e.end], "freqq")
        e = err("zz + 1")
        self.assertIn("unknown name 'zz'", e.message)
        self.assertIn("Names you can use here: a, freq, x", e.message)

    def test_unknown_function_suggests(self):
        e = err("sinn(x)")
        self.assertIn("'sinn' is not a function you can use — did you mean 'sin'?", e.message)
        self.assertEqual(e.col, 0)

    def test_columns_point_at_the_bad_part(self):
        text = "a + math.sin(x)"
        e = err(text)
        self.assertIn("write sin(…), not math.sin(…)", e.message)
        self.assertEqual(text[e.col:e.end], "math.sin")

    def test_refuses_code(self):
        bad = {
            "__import__('os')": "only maths functions",
            "__import__": "names starting with _",
            "x.__class__": "'.' is not allowed",
            "().__class__.__bases__": "",
            "lambda: 1": "lambda is not allowed",
            "[x for x in a]": "comprehensions are not allowed",
            "(x for x in a)": "generator",
            "{x for x in a}": "comprehensions",
            "x if a else 1": "where(condition, a, b)",
            "open('f')": "",
            "eval('1')": "",
            "exec('1')": "",
            "globals()": "",
            "'text'": "text in quotes",
            "a[0]": "indexing",
            "(x := 2)": "':='",
            "x & 1": "operator '&'",
            "~x": "not supported",
            "not x": "'not' is not supported",
            "1j": "imaginary",
            "True": "not a number",
            "sin(x=1)": "without name=value",
            "sin(*a)": "unpacking",
            "x = 2": "'=' is not allowed",
            "f'{x}'": "quotes",
            "a, x": "comma",
            "sin x": "brackets",
            "sin": "is a function",
            "x +": "ends with an operator",
            "(x": "never closed",
            "x)": "no '('",
            "": "write an expression",
            "x # y": "cannot be used",
            "x\\": "cannot be used",
            "a @ x": "operator '@'",
        }
        for text, words in bad.items():
            with self.subTest(text=text):
                e = err(text)
                self.assertTrue(e.message)
                self.assertIn(words, e.message)

    def test_scalars_only_where_declared(self):
        self.assertIn("x is only defined inside a curve", err("x + 1", {"a"}).message)
        self.assertIn("i (the row)", err("i", {"a"}).message)

    def test_too_long(self):
        self.assertIn("too long", err("x+" * 300 + "x").message)
        self.assertIn("too long", err("+".join(["x"] * 150)).message)

    def test_huge_powers_overflow_instead_of_hanging(self):
        code = fb.parse_expr("9^9^9", {"x"}).code
        self.assertEqual(code, "9.0 ** 9.0 ** 9")
        with self.assertRaises(OverflowError):
            eval(compile(code, "<test>", "eval"), {})   # the code the builder writes overflows at once


class Generated(unittest.TestCase):
    def setUp(self):
        self.site = Site()

    def tearDown(self):
        self.site.close()

    def check(self, name, spec):
        src = fb.generate(spec)
        self.site.add(name, src)
        self.assertEqual(figures.test_figure(name, self.site.cfg), [], src)
        return src

    def test_every_type_passes_the_figure_test(self):
        for kind in fb.TYPES:
            with self.subTest(type=kind):
                src = self.check("made_" + kind, fb.default_spec(kind))
                self.assertTrue(figures.figure_html("made_" + kind, cfg=self.site.cfg).startswith("<figure"))

    def test_generated_files_stand_alone(self):
        for kind in fb.TYPES:
            with self.subTest(type=kind):
                src = fb.generate(fb.default_spec(kind))
                tree = ast.parse(src)
                imported = set()
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        imported |= {a.name for a in node.names}
                    elif isinstance(node, ast.ImportFrom):
                        imported.add(node.module)
                self.assertLessEqual(imported, {"math"})
                self.assertNotIn("tessera", src.split(fb.MARK)[0])
                self.assertNotIn("eval(", src)
                self.assertNotIn("exec(", src)
                # the file runs on a bare interpreter with only the standard library
                ns = {}
                exec(compile(src, "<generated>", "exec"), ns)
                spec = ns["compute"](**{c["name"]: c["value"] for c in ns["CONTROLS"]})
                self.assertIn("panels", spec)

    def test_round_trip(self):
        spec = fb.default_spec("function")
        src = fb.generate(spec)
        info = fb.read_spec(src)
        self.assertFalse(info["edited"])
        self.assertEqual(info["spec"]["curves"][0]["expr"], "a*sin(f*x)*exp(-d*x)")
        self.assertEqual(fb.generate(info["spec"]), src)            # same spec, same file
        edited = src.replace("SAMPLES = 0, 10, 200", "SAMPLES = 0, 10, 300")
        self.assertNotEqual(edited, src)
        self.assertTrue(fb.read_spec(edited)["edited"])
        self.assertTrue(fb.read_spec(src + "\nprint(1)\n")["edited"])
        self.assertIsNone(fb.read_spec("TITLE = 'x'\n"))
        self.assertIsNone(fb.read_spec(src.replace(fb.MARK, "# tessera-builder:{bad")))

    def test_problems_name_the_field(self):
        spec = fb.default_spec("function")
        spec["curves"][0]["expr"] = "a*sin(freqq*x)"
        spec["controls"][0]["max"] = -1
        spec["readouts"][0]["expr"] = "max(wav)"
        spec["presets"] = [{"label": "Reset", "values": {"d": 0}}, {"label": "X", "values": {"dd": 1}}]
        probs = {p["path"]: p for p in fb.validate(spec)}
        self.assertIn("curves.0.expr", probs)
        self.assertIn("unknown name 'freqq'", probs["curves.0.expr"]["message"])
        self.assertEqual(probs["curves.0.expr"]["text"][probs["curves.0.expr"]["col"]:probs["curves.0.expr"]["end"]], "freqq")
        self.assertIn("controls.0.max", probs)
        self.assertIn("did you mean 'wave'", probs["readouts.0.expr"]["message"])
        self.assertIn("presets.0.label", probs)
        self.assertIn("did you mean 'd'", probs["presets.1.values"]["message"])
        with self.assertRaises(fb.SpecError) as cm:
            fb.generate(spec)
        self.assertTrue(str(cm.exception))

    def test_names(self):
        spec = fb.default_spec("function")
        for bad, words in (("x", "position across"), ("sin", "maths function"), ("Freq", "lowercase"),
                           ("pi", "constant"), ("a", "used twice"), ("lambda", "already means"), ("", "short name")):
            s = copy.deepcopy(spec)
            s["controls"][1]["name"] = bad
            with self.subTest(name=bad):
                msgs = [p["message"] for p in fb.validate(s) if p["path"] == "controls.1.name"]
                self.assertTrue(msgs and words in msgs[0], msgs)

    def test_function_features(self):
        spec = {"type": "function", "title": "Features",
                "controls": [
                    {"name": "a", "kind": "slider", "label": "a", "min": 0.1, "max": 2, "step": 0.1, "value": 1, "play": True},
                    {"name": "env", "kind": "toggle", "label": "Envelope", "options": ["Hide", "Show"], "value": 1},
                    {"name": "n", "kind": "steps", "label": "Terms", "options": "1, 3, 9", "value": 1}],
                "values": [{"name": "half", "expr": "ln(2)/a"}, {"name": "twice", "expr": "2 half"}],
                "curves": [{"name": "y", "expr": "exp(-a x) sin(n x)", "label": "y at a = {a:.1f}", "fill": "zero"},
                           {"name": "top", "expr": "exp(-a*x)", "style": "muted dashed", "show": "env", "fill": "y"},
                           {"name": "hole", "expr": "1/(x-2)", "style": "third"}],
                "marks": [{"axis": "x", "expr": "half", "label": "half-life"}, {"axis": "y", "expr": "0"}],
                "points": [{"x": "argmax(y)", "y": "max(y)", "label": "peak {max(y):.2f}"}],
                "x_min": 0, "x_max": 6, "samples": 300, "y_min": -1.5, "y_max": 1.5,
                "readouts": [{"label": "Area", "expr": "area(y)", "decimals": 3, "unit": "units²"},
                             {"label": "Twice", "expr": "twice", "note": "a is {a}"},
                             {"label": "Undefined", "expr": "log(-a)"}],
                "presets": [{"label": "Slow", "values": {"a": 0.2, "n": "9"}}],
                "note": "half-life {half:.2f}"}
        src = self.check("features", spec)
        self.assertIn("n = (1, 3, 9)[n]", src)
        r = figures.run("features", cfg=self.site.cfg)
        self.assertIn("—", r["readouts_html"])            # log(-a) is not defined: a dash, not an error
        self.assertIn("half-life 0.69", r["readouts_html"])
        self.assertIn("y at a = 1.0", r["svg"])

    def test_log_axes(self):
        spec = {"type": "function", "title": "Power law", "x_min": 0.1, "x_max": 100, "x_log": True, "y_log": True,
                "curves": [{"name": "y", "expr": "x^2"}]}
        self.check("loglog", spec)
        spec["x_min"] = 0
        self.assertIn("x_min", [p["path"] for p in fb.validate(spec)])

    def test_shapes_repeat_polygon_text(self):
        spec = {"type": "shapes", "title": "Polygon", "x_min": -2, "x_max": 2, "y_min": -2, "y_max": 2,
                "controls": [{"name": "n", "kind": "slider", "label": "Corners", "min": 3, "max": 12, "step": 1, "value": 5}],
                "items": [{"type": "point", "repeat": "n", "x": "cos(2pi k/n)", "y": "sin(2pi k/n)", "label": "{k+1}"},
                          {"type": "polygon", "points": "0, 0\n1, 0\nmax(0.5, 1/n), 1"},
                          {"type": "circle", "x": "0", "y": "0", "r": "1 - 3/n"},
                          {"type": "rect", "x": "-1.5", "y": "-1.5", "w": "0.5", "h": "0.5", "style": "muted"},
                          {"type": "arrow", "x1": "0", "y1": "0", "x2": "1", "y2": "1", "label": "v"},
                          {"type": "text", "x": "0", "y": "1.8", "label": "{n} corners"}],
                "grid": True, "axes": True}
        self.check("polygon", spec)
        bad = copy.deepcopy(spec)
        bad["items"][1]["points"] = "0, 0\n1"
        self.assertIn("items.1.points", [p["path"] for p in fb.validate(bad)])
        bad["items"][0]["x"] = "cos(t)"
        self.assertIn("t is only defined inside a parametric curve",
                      [p["message"] for p in fb.validate(bad) if p["path"] == "items.0.x"][0])

    def test_bars_and_heatmap_options(self):
        bars = {"type": "bars", "title": "Bars", "horizontal": True, "highlight": "min", "show_values": True,
                "controls": [{"name": "m", "kind": "slider", "label": "m", "min": 1, "max": 8, "step": 1, "value": 4}],
                "bars": [{"label": "k = {k}", "expr": "exp(-k/m)", "repeat": "m"}, {"label": "fixed", "expr": "0.5"}],
                "marks": [{"axis": "y", "expr": "mean(bars)", "label": "average"}],
                "readouts": [{"label": "Largest at", "expr": "argmax(bars)"}]}
        self.check("bars_k", bars)
        heat = {"type": "heatmap", "title": "Heat", "rows": "n", "cols": "4", "expr": "i - j",
                "controls": [{"name": "n", "kind": "steps", "label": "Rows", "options": ["2", "6"], "value": 1}],
                "row_labels": "row {i+1}", "col_labels": "a, b, c, d", "show_values": True, "decimals": 0}
        self.check("heat", heat)

    def test_every_distribution(self):
        for fam in fb.FAMILIES:
            for mode in ("none", "sigma", "range"):
                spec = {"type": "distribution", "title": "Dist", "family": fam, "cdf_toggle": mode == "range",
                        "interval": {"mode": mode, "lo": "mean - 1", "hi": "mean + 1"},
                        "readouts": [{"label": "Spread", "expr": "std"}]}
                with self.subTest(family=fam, mode=mode):
                    self.check("d_%s_%s" % (fam, mode), spec)
        spec = {"type": "distribution", "title": "Dist", "family": "binomial", "params": {"n": {"max": 40.5}}}
        self.assertIn("params.n.max", [p["path"] for p in fb.validate(spec)])
        spec = {"type": "distribution", "title": "Dist", "family": "normal",
                "presets": [{"label": "Wide", "values": {"sigma": 2}}]}
        self.check("d_preset", spec)

    def test_data_table(self):
        spec = fb.default_spec("data")
        src = self.check("table", spec)
        self.assertIn('"height_cm": [152, 158', src)
        r = figures.run("table", cfg=self.site.cfg)
        self.assertIn("R²", r["readouts_html"])
        r2 = figures.run("table", {"fit": 0}, cfg=self.site.cfg)
        self.assertNotIn("fitted line", r2["svg"])
        bars = {"type": "data", "title": "Sales", "chart": "bar", "csv": "month;sales\nJan;3\nFeb;\nMar;4.5",
                "readouts": [{"label": "Total", "expr": "sum(sales)"}]}
        self.check("sales", bars)
        lines = {"type": "data", "title": "Two lines", "chart": "line", "csv": "t\tup\tdown\n0\t1\t5\n1\t2\t4\n2\t3\t3",
                 "x": "t", "y": ["up", "down"], "controls": [{"name": "m", "kind": "slider", "label": "m", "min": 0,
                                                              "max": 2, "step": 0.1, "value": 1}],
                 "curves": [{"name": "model", "expr": "m*x + 1", "style": "third dashed"}]}
        self.check("two_lines", lines)
        bad = copy.deepcopy(lines)
        bad["csv"], bad["y"] = "t,up\n0,1\nx,2", ["up"]
        self.assertIn("text in row 3", [p["message"] for p in fb.validate(bad) if p["path"] == "x"][0])
        bad["csv"] = "t,up\n0,1,2"
        self.assertTrue(any(p["path"] == "csv" for p in fb.validate(bad)))
        bad["csv"] = ""
        self.assertTrue(any(p["path"] == "csv" for p in fb.validate(bad)))

    def test_messages_for_whole_spec(self):
        self.assertEqual(fb.validate({"type": "nope"})[0]["path"], "type")
        self.assertTrue(fb.validate(None))
        self.assertIn("title", [p["path"] for p in fb.validate({"type": "function", "curves": [{"expr": "x"}]})])
        self.assertEqual(fb.where_words("curves.0.expr"), "curve 1, expression")

    def test_describe(self):
        d = fb.describe()
        self.assertEqual([t["type"] for t in d["types"]], list(fb.TYPES))
        self.assertIn("sin", [f["name"] for f in d["functions"]])
        self.assertIn("normal", d["families"])
        for kind in fb.TYPES:
            self.assertEqual(fb.validate(d["examples"][kind]), [])

    def test_fast(self):
        import time
        for kind in fb.TYPES:
            t = time.perf_counter()
            fb.generate(fb.default_spec(kind))
            self.assertLess((time.perf_counter() - t) * 1000, 100)


if __name__ == "__main__":
    unittest.main()
