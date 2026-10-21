"""Maths errors that teach: positions in the file, the specific messages, money signs, check() and the CLI."""
import io
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from bazinga import cli  # noqa: E402
from bazinga.mathml import MathError, check, looks_like_money, to_mathml  # noqa: E402
from test_core_support import REPO, render_text  # noqa: E402


def math_issues(body):
    _page, r = render_text(body)
    return [i for i in r.issues if i.code.startswith("math")]


class Positions(unittest.TestCase):
    def test_inline_error_has_file_line_and_column(self):
        issues = math_issues("Intro.\n\nThe value $x^10$ grows.")
        self.assertEqual(len(issues), 1)
        i = issues[0]
        # front matter is 5 lines (--- title date summary topics ---) + 1: the body starts on line 7
        self.assertEqual(i.line, 9)
        self.assertEqual(i.column, 13)                  # the ^ (1-based)
        self.assertIn("only the 1", i.message)
        self.assertIn("^{10}", i.hint)
        self.assertEqual(i.length, 3)

    def test_display_error_on_a_later_line(self):
        issues = math_issues("$$\n\\begin{aligned}\na &= b \\\\\nc &= \\nosuch\n\\end{aligned}\n$$")
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].line, 7 + 3)
        self.assertEqual(issues[0].column, 6)
        self.assertIn("\\nosuch", issues[0].message)

    def test_display_error_on_the_opening_line(self):
        issues = math_issues("$$ \\frac{a}{b $$")
        self.assertEqual(issues[0].line, 7)
        self.assertEqual(issues[0].column, 3 + 8 + 1)   # after "$$ " the { of {b

    def test_format_shows_line_and_column(self):
        issue = math_issues("$x^10$")[0]
        self.assertIn("t.md:7:3: error: maths:", issue.format("t.md"))
        self.assertEqual(issue.to_dict()["column"], 3)

    def test_every_error_names_a_fix(self):
        for tex, display in [("{a", False), ("a}", False), (r"\left( a", False), ("a & b", False),
                             (r"a \\ b", False), (r"\begin{pmatrix} a", True), ("x_1_2", False), ("$", False),
                             (r"\frac{a}", False), (r"\boxed", False), (r"\text{$x$}", False), ("x^", False),
                             (r"\color{nope!}{x}", False), (r"\newcommand{\a}{b}", True)]:
            with self.subTest(tex=tex):
                with self.assertRaises(MathError) as ctx:
                    to_mathml(tex, display)
                e = ctx.exception
                self.assertTrue(e.hint)
                self.assertIsNotNone(e.column)
                self.assertIsNotNone(e.index)


class Money(unittest.TestCase):
    def test_prices_stay_text(self):
        self.assertEqual(math_issues("It costs $5 and $10 a month."), [])

    def test_price_before_real_maths_is_explained(self):
        _page, r = render_text("It costs $5, and then $x$ is the rest of it.")
        codes = [i.code for i in r.issues]
        self.assertIn("math-money", codes)
        self.assertNotIn("math", codes)
        self.assertIn("&#36;5", r.html.replace("$5", "&#36;5"))

    def test_heuristic(self):
        self.assertTrue(looks_like_money("5 for the basic plan and "))
        self.assertFalse(looks_like_money("x + y"))
        self.assertFalse(looks_like_money(r"2\pi r"))

    def test_escaped_dollar_in_maths(self):
        self.assertIn("$", to_mathml(r"\$5 + x", False).split("<annotation")[0])


class Check(unittest.TestCase):
    def test_ok_with_tag_and_label(self):
        res = check(r"E = mc^2 \tag{3} \label{eq:energy}", True)
        self.assertTrue(res["ok"])
        self.assertEqual((res["tag"], res["label"]), ("3", "eq:energy"))
        self.assertIn("<math", res["mathml"])

    def test_error_dict(self):
        res = check(r"a + \alpah", False)
        self.assertFalse(res["ok"])
        self.assertEqual(res["error"]["column"], 4)
        self.assertEqual(res["error"]["length"], 6)
        self.assertIn("\\alpha", res["error"]["hint"])

    def test_tag_positions_are_kept(self):
        res = check("a \\tag{1} + \\nosuch", True)
        self.assertEqual(res["error"]["column"], 12)


class Cli(unittest.TestCase):
    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cli.main(["math", *args])
        return code, out.getvalue(), err.getvalue()

    def test_ok_prints_mathml(self):
        code, out, _ = self.run_cli(r"\frac{a}{b}")
        self.assertEqual(code, 0)
        self.assertIn("<mfrac>", out)

    def test_error_shows_place_and_fix(self):
        code, _, err = self.run_cli("x^10 + y")
        self.assertEqual(code, 1)
        self.assertIn("line 1, column 2:", err)
        self.assertIn("    x^10 + y\n     ^^^", err)
        self.assertIn("Instead: write ^{10}", err)

    def test_display_and_html(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "f.html"
            code, out, _ = self.run_cli(r"a \\ b", "--display", "--html", str(target))
            self.assertEqual(code, 0)
            html = target.read_text(encoding="utf-8")
            self.assertIn('display="block"', html)
            self.assertIn("<mtable", html)

    def test_as_a_process(self):
        r = subprocess.run([sys.executable, "-m", "bazinga", "math", r"\sqrt{x}"], capture_output=True, text=True,
                           cwd=str(REPO))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("<msqrt>", r.stdout)


if __name__ == "__main__":
    unittest.main()
