"""mathml.py: every pre-processing rule, the post-processing fixes, the rejection list and error lines."""
import unittest

from tessera.mathml import MathError, preprocess, split_tag_label, to_mathml


def body(tex, display=False):
    """The MathML without the LaTeX annotation."""
    return to_mathml(tex, display).split("<annotation")[0]


class Preprocess(unittest.TestCase):
    def test_aligned_becomes_array(self):
        for env in ("aligned", "align", "align*", "split"):
            out, _ = preprocess(rf"\begin{{{env}}} a &= b \\ c &= d \end{{{env}}}")
            self.assertIn(r"\begin{array}{rl}", out, env)
            self.assertNotIn(env + "}", out.replace("array}", ""))

    def test_gather_is_centred(self):
        out, _ = preprocess(r"\begin{gather} a \\ b \end{gather}")
        self.assertIn(r"\begin{array}{c}", out)

    def test_aligned_output_has_no_literal_ampersand_or_linebreak(self):
        html = body(r"\begin{aligned} a &= b \\ c &= d \end{aligned}", True)
        self.assertNotIn("<mi>&amp;</mi>", html)
        self.assertNotIn("linebreak", html)
        self.assertEqual(html.count("<mtr>"), 2)

    def test_relation_after_ampersand_gets_left_operand(self):
        out, _ = preprocess(r"\begin{aligned} a &= b \end{aligned}")
        self.assertIn("&{}=", out)

    def test_row_spacing_is_dropped(self):
        out, _ = preprocess(r"\begin{array}{l} a \\[4pt] b \end{array}")
        self.assertNotIn("4pt", out)
        self.assertNotIn("4pt", body(r"\begin{aligned} a \\[4pt] b \end{aligned}", True))

    def test_arg_argmax_argmin_operatorname_star(self):
        self.assertIn(r"\operatorname{arg}", preprocess(r"\arg z")[0])
        out, starred = preprocess(r"\argmax_x f + \argmin_y g + \operatorname*{arg\,max}_t h")
        self.assertNotIn(r"\argmax", out)
        self.assertNotIn(r"\,", out)
        self.assertEqual(starred, {"argmax", "argmin"})
        self.assertIn(">argmax</mo>", body(r"\operatorname*{arg\,max}_\theta L"))

    def test_bold_symbol(self):
        self.assertIn(r"\mathbf", preprocess(r"\boldsymbol{x} + \bm{y}")[0])
        self.assertNotIn("bold-italic", body(r"\boldsymbol{x}"))
        self.assertIn("\U0001d73d", body(r"\boldsymbol{\theta}"))     # bold italic theta
        self.assertIn("\U0001d6ba", body(r"\mathbf{\Sigma}"))         # bold Sigma

    def test_big_delimiters_dropped(self):
        for cmd in (r"\big(", r"\Big[", r"\bigg\{", r"\Bigg(", r"\bigl(", r"\bigr)", r"\Bigm|", r"\big\|"):
            out, _ = preprocess(cmd + " x")
            self.assertNotIn("big", out.lower(), cmd)
        self.assertNotIn("minsize", body(r"\bigl( x \bigr)"))

    def test_text_keeps_spaces(self):
        html = body(r"\text{ if } x")
        self.assertIn("<mtext> if </mtext>", html)

    def test_tag_and_label_taken_out(self):
        tex, tag, label = split_tag_label(r"a = b \tag{3} \label{eq:x}")
        self.assertEqual((tag, label), ("3", "eq:x"))
        self.assertNotIn("tag", tex)
        self.assertNotIn("label", tex)

    def test_not_equal_and_upright_d(self):
        self.assertIn("≠", body(r"a \not= b"))
        self.assertIn("<mtext>d</mtext>", body(r"\mathrm{d}x"))


class Postprocess(unittest.TestCase):
    def test_display_attribute_and_annotation(self):
        out = to_mathml("x^2", True)
        self.assertIn('display="block"', out)
        self.assertIn('<annotation encoding="application/x-tex">x^2</annotation>', out)
        self.assertIn('display="inline"', to_mathml("x", False))

    def test_bold_digits_and_upright_words(self):
        self.assertIn("\U0001d7cf", body(r"\mathbf{1}"))
        self.assertIn("<mi>ReLU</mi>", body(r"\mathrm{ReLU}(x)"))

    def test_symbols_become_operators(self):
        html = body(r"\langle q, k \rangle \pm 1")
        self.assertIn("<mo>⟨</mo>", html)
        self.assertIn("<mo>±</mo>", html)

    def test_function_names_are_spaced(self):
        html = body(r"y_i \log p_i")
        self.assertIn('<mo lspace="0.1667em" rspace="0.1667em">log</mo>', html)
        self.assertIn('rspace="0">exp</mo>', body(r"\exp(z)"))     # no space before a bracket
        self.assertIn('rspace="0">softmax</mo>', body(r"\operatorname{softmax}(x)"))

    def test_limits_under_operators_in_display(self):
        self.assertIn("<munder>", body(r"\max_x f", True))
        self.assertIn("<msub>", body(r"\max_x f", False))
        self.assertIn("<munder>", body(r"\argmax_x f", True))

    def test_display_arrays_use_display_style_but_matrices_do_not(self):
        self.assertIn('displaystyle="true"', body(r"\begin{aligned} a &= \frac{1}{2} \end{aligned}", True))
        self.assertNotIn('displaystyle="true"', body(r"\begin{pmatrix} a & b \end{pmatrix}", True))

    def test_negative_space_has_a_width(self):
        self.assertIn('width="-0.1667em"', body(r"a\!b"))


class Rejections(unittest.TestCase):
    def assertRejects(self, tex, words, display=True):
        with self.assertRaises(MathError) as ctx:
            to_mathml(tex, display)
        self.assertIn(words, str(ctx.exception))
        self.assertTrue(ctx.exception.hint)
        return ctx.exception

    def test_unknown_command(self):
        exc = self.assertRejects(r"\foo x", r"\foo")
        self.assertIn(r"\operatorname{foo}", exc.hint)
        self.assertIn(r"\operatorname{softmax}", self.assertRejects(r"\softmax(x)", r"\softmax").hint)

    def test_menclose_commands(self):
        for cmd in (r"\cancel{x}", r"\boxed{x}", r"\bcancel{x}", r"\xcancel{x}", r"\fbox{x}"):
            self.assertRejects(cmd, "browsers")

    def test_linebreak_outside_array(self):
        self.assertRejects(r"a \\ b", "line break")

    def test_eqref_inside_maths(self):
        exc = self.assertRejects(r"\eqref{eq:a}", r"\eqref")
        self.assertIn("[eq:name]", exc.hint)

    def test_tag_inline(self):
        self.assertRejects(r"\tag{1} x", "display", display=False)

    def test_unbalanced_braces_and_empty(self):
        self.assertRejects("{x", "braces")
        self.assertRejects("  ", "empty")

    def test_error_offset_is_the_line_inside_the_formula(self):
        exc = self.assertRejects("a = b \\\\\n c = \\nosuch", r"\nosuch")
        self.assertEqual(exc.offset, 1)

    def test_valid_output_has_no_forbidden_markup(self):
        for tex in (r"\frac{a}{b}", r"\sqrt[3]{x}", r"\begin{cases} 1 & x>0 \\ 0 & \text{else} \end{cases}",
                    r"\hat{y} = \sum_{i=1}^n w_i x_i", r"\mathbb{E}_{x\sim p}[x]", r"\binom{n}{k}"):
            html = body(tex, True)
            for bad in ("<mi>\\", "menclose", "mfenced", "linebreak="):
                self.assertNotIn(bad, html, tex)


if __name__ == "__main__":
    unittest.main()
