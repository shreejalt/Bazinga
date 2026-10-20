"""markdown.py: every syntax extension, with real file line numbers on problems."""
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tessera import config, content
from tessera.markdown import references

from test_core_support import REPO, post, render_text  # noqa: E402


def other(slug="other", title="Other Page", status=None, date="2020-01-01"):
    cfg = config.load(REPO)
    fields = {"status": status} if status else {}
    return content.parse(post(title=title, date=date, **fields), Path(f"content/reads/{slug}.md"), cfg)


class Maths(unittest.TestCase):
    def test_inline_and_display(self):
        _, r = render_text("Inline $x^2$ here.\n\n$$\na + b\n$$\n")
        self.assertIn('display="inline"', r.html)
        self.assertIn('<div class="math-display">', r.html)
        self.assertIn('display="block"', r.html)
        self.assertEqual(r.issues, [])

    def test_numbering_and_references(self):
        body = "See [eq:b] and [eq:a].\n\n$$\na\n$$ {#eq:a}\n\n$$ b \\label{eq:b} $$\n\n$$\nc \\tag{★}\n$$\n"
        _, r = render_text(body)
        self.assertEqual(r.equations, {"eq:a": "1", "eq:b": "2"})
        self.assertIn('<a class="eqref" href="#eq:b">(2)</a>', r.html)
        self.assertIn('<a class="eqref" href="#eq:a">(1)</a>', r.html)
        self.assertIn('id="eq:a"', r.html)
        self.assertIn('<span class="eq-number">(★)</span>', r.html)
        self.assertEqual(r.issues, [])

    def test_unknown_equation_reference_has_line(self):
        page, r = render_text("Line one.\n\nSee [eq:nope].\n")
        self.assertEqual(len(r.issues), 1)
        self.assertEqual(r.issues[0].line, page.body_line + 2)
        self.assertIn("eq:nope", r.issues[0].message)

    def test_math_error_line_inside_multiline_display(self):
        page, r = render_text("Intro.\n\n$$\n\\begin{array}{l}\na \\\\\n\\nosuch\n\\end{array}\n$$\n")
        self.assertEqual(r.issues[0].line, page.body_line + 5)
        self.assertIn("math-error", r.html)

    def test_unclosed_display(self):
        page, r = render_text("$$\nx\n\nmore text")
        self.assertEqual(r.issues[0].code, "math-unclosed")
        self.assertEqual(r.issues[0].line, page.body_line)

    def test_dollars_that_are_money(self):
        _, r = render_text("It costs $5 and $10, or \\$3.")
        self.assertNotIn("<math", r.html)
        self.assertIn("$5 and $10", r.html)
        self.assertIn("&#36;3", r.html)

    def test_code_is_left_alone(self):
        _, r = render_text("Use `$x$` and `[[post:nope]]`.\n\n```python\nx = '$a$' # [@Nope]\n```\n")
        self.assertNotIn("<math", r.html)
        self.assertEqual(r.issues, [])

    def test_maths_in_callout(self):
        _, r = render_text("> [!NOTE]\n> Inline $a$.\n>\n> $$\n> b\n> $$\n")
        self.assertIn("callout-note", r.html)
        self.assertEqual(r.html.count("<math"), 2)


class Links(unittest.TestCase):
    def test_wikilinks(self):
        _, r = render_text("Read [[read:other]] and [[read:other|this one]].", others=[other()])
        self.assertIn('<a class="xref" href="/reads/other/" data-id="read:other">Other Page</a>', r.html)
        self.assertIn(">this one</a>", r.html)
        self.assertEqual(r.mentions, ["read:other"])

    def test_unknown_link_is_an_error_with_did_you_mean(self):
        page, r = render_text("x\n[[read:othr]]", others=[other()])
        self.assertEqual(r.issues[0].line, page.body_line + 1)
        self.assertIn("did you mean read:other", r.issues[0].hint)

    def test_citations_are_numbered_in_order(self):
        _, r = render_text("A [@Kingma14], B [@Vaswani17, p. 4], A again [@Kingma14; @Vaswani17].")
        self.assertEqual(r.cites, ["Kingma14", "Vaswani17"])
        self.assertIn('href="#ref-Vaswani17"', r.html)
        self.assertIn("</a>, p. 4]", r.html)
        refs = references(r, type("S", (), {"references": {"Kingma14": {"title": "Adam", "authors": ["D. Kingma"],
                                                                         "year": 2014, "arxiv": "1412.6980"},
                                                            "Vaswani17": {"title": "Att", "year": 2017}}})())
        self.assertEqual([x["n"] for x in refs], [1, 2])
        self.assertEqual(refs[0]["url"], "https://arxiv.org/abs/1412.6980")

    def test_unknown_citation(self):
        _, r = render_text("x [@Nobody99].")
        self.assertEqual(r.issues[0].code, "cite-unknown")


class Blocks(unittest.TestCase):
    def test_callouts(self):
        _, r = render_text("> [!TIP]\n> One.\n\n> [!KEY] Remember this\n> Two.\n\n> [!WARNING]\n> Three.\n")
        self.assertIn('class="callout callout-tip"', r.html)
        self.assertIn('<p class="callout-title">Remember this</p>', r.html)
        self.assertIn('class="callout callout-warning"', r.html)
        self.assertNotIn("[!", r.html)

    def test_plain_blockquote_stays(self):
        _, r = render_text("> Just a quote.")
        self.assertIn("<blockquote>", r.html)

    def test_footnotes_tables_mark_del(self):
        _, r = render_text("Text.[^1] ==hi== ~~old~~\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n[^1]: Note.")
        self.assertIn('class="footnote"', r.html)
        self.assertIn("<mark>hi</mark>", r.html)
        self.assertIn("<del>old</del>", r.html)
        self.assertIn('<div class="table-wrap"><table>', r.html)

    def test_code_is_highlighted_with_classes(self):
        _, r = render_text("```python\ndef f():\n    return 1\n```")
        self.assertIn('<div class="code-block" data-lang="python">', r.html)
        self.assertIn('<span class="k">def</span>', r.html)
        _, r = render_text("```pyhton\nx\n```")
        self.assertEqual(r.issues[0].code, "code-lang")

    def test_image_becomes_figure_with_caption(self):
        _, r = render_text('![A cat](static/uploads/cat.png "The cat.")')
        self.assertIn('<figure class="image"><img alt="A cat"', r.html)
        self.assertIn('src="/static/uploads/cat.png"', r.html)
        self.assertIn("<figcaption>The cat.</figcaption>", r.html)

    def test_headings_get_ids_anchors_toc_and_sections(self):
        _, r = render_text("Intro text.\n\n## First part\n\nAdam's words.\n\n### Detail {#fixed}\n\nMore.\n\n"
                           "## First part\n\nAgain.")
        self.assertEqual([t["id"] for t in r.toc], ["first-part", "fixed", "first-part-2"])
        self.assertIn('class="heading-anchor" href="#fixed"', r.html)
        self.assertEqual(r.sections[0]["id"], "")
        self.assertIn("Adam’s words.", r.sections[1]["text"])     # apostrophes survive

    def test_figure_and_drawing_hooks(self):
        _, r = render_text("::figure softmax_temperature | start: Sharp\n\n::drawing pipeline.overview | Cap\n",
                           cfg=config.load(REPO))
        self.assertEqual(r.figures, ["softmax_temperature"])
        self.assertEqual(r.drawings, ["pipeline.overview"])

    def test_missing_figure_is_an_error_box_with_line(self):
        page, r = render_text("Text.\n\n::figure no_such_figure\n", preview=True)
        self.assertIn("embed-error", r.html)
        self.assertEqual(r.issues[0].line, page.body_line + 2)


if __name__ == "__main__":
    unittest.main()
