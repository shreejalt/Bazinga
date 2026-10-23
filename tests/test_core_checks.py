"""checks.py rules, cite.py (network mocked), the CLI, vendor pins and site.js syntax."""
import io
import json
import os
import shutil
import subprocess
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_core_support import EXAMPLE, REPO, cleanup, make_site, post  # noqa: E402

from bazinga import checks, cite, cli, config, content, vendor  # noqa: E402


def issues_for(text, others=None, name="t"):
    """Check one page of a temp site; returns {code: Issue}."""
    root = make_site({f"posts/{name}": text, **(others or {})})
    try:
        cfg = config.load(root)
        pages = [content.load_file(p, cfg) for p in content.content_files(cfg)]
        page = next(p for p in pages if p.slug == name)
        site = checks.site_for(page, pages, content.load_references(cfg), content.load_topics(cfg), cfg)
        return {i.code: i for i in checks.check_page(page, site)}
    finally:
        cleanup(root)


class Rules(unittest.TestCase):
    def test_clean_page_has_no_issues(self):
        self.assertEqual(issues_for(post(body="Fine [@Vaswani17].")), {})

    def test_front_matter(self):
        found = issues_for('---\ntitle: ""\ndate: 2020-01-01\ntopics: [attentoin]\ndescription: "' + "x" * 160 + '"\n---\nx')
        self.assertEqual(found["title"].level, "error")
        self.assertEqual(found["summary"].level, "error")                  # published pages need one
        self.assertIn("did you mean attention", found["topic-unknown"].hint)
        self.assertEqual(found["topic-unknown"].line, 4)
        self.assertEqual(found["description"].line, 5)

    def test_draft_missing_summary_is_only_a_warning(self):
        found = issues_for(post(status="draft", summary=None))
        self.assertEqual(found["summary"].level, "warning")

    def test_builds_on_and_too_many_topics(self):
        found = issues_for(post(builds_on="[post:missing]", topics="[a, b, c, d, e]"))
        self.assertEqual(found["builds-on"].level, "error")
        self.assertIn("at most 4", found["topics"].message)

    def test_body_style_rules(self):
        body = ("# Big heading\n\n## Part\n\n#### Too deep\n\n![](static/nope.png)\n\n[](https://x.org)\n\n"
                "[see](/posts/missing/)\n\n> [!DANGER]\n> x\n\n$$\n" + "a + " * 40 + "b\n$$\n")
        found = issues_for(post(body=body))
        for code in ("heading-h1", "heading-skip", "image-alt", "file-missing", "link-text", "link-broken",
                     "callout", "math-long"):
            self.assertIn(code, found, code)
        self.assertEqual(found["heading-h1"].line, 7)

    def test_render_problems_are_included_with_lines(self):
        found = issues_for(post(body="ok\nsee $\\alpah$"))
        self.assertEqual(found["math"].line, 8)
        self.assertEqual(found["math"].column, 6)
        self.assertIn("\\alpha", found["math"].hint)


class Cite(unittest.TestCase):
    ARXIV = b"""<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
      <entry><title>Attention Is All
        You Need</title><published>2017-06-12T17:57:34Z</published>
      <author><name>Ashish Vaswani</name></author><author><name>Noam Shazeer</name></author></entry></feed>"""
    CROSSREF = json.dumps({"message": {"title": ["Deep learning"], "DOI": "10.1038/nature14539",
                                       "author": [{"given": "Yann", "family": "LeCun"}],
                                       "issued": {"date-parts": [[2015, 5, 27]]}, "container-title": ["Nature"]}})

    def test_parse_query(self):
        self.assertEqual(cite.parse_query("https://arxiv.org/abs/1706.03762v5"), ("arxiv", "1706.03762"))
        self.assertEqual(cite.parse_query("arXiv:1706.03762"), ("arxiv", "1706.03762"))
        self.assertEqual(cite.parse_query("10.48550/arXiv.1706.03762"), ("arxiv", "1706.03762"))
        self.assertEqual(cite.parse_query("https://doi.org/10.1038/nature14539"), ("doi", "10.1038/nature14539"))
        self.assertEqual(cite.parse_query("hep-th/9901001"), ("arxiv", "hep-th/9901001"))
        with self.assertRaises(cite.CiteError):
            cite.parse_query("not an id")

    def test_keys_are_surname_year_and_collision_safe(self):
        rec = {"authors": ["José Ñúñez"], "year": 2017}
        self.assertEqual(cite.make_key(rec, set()), "Nunez17")
        self.assertEqual(cite.make_key(rec, {"Nunez17"}), "Nunez17b")
        self.assertEqual(cite.make_key(rec, {"Nunez17", "Nunez17b"}), "Nunez17c")

    def test_lookup_and_append(self):
        root = make_site()
        try:
            cfg = config.load(root)
            with mock.patch.object(cite, "http_get", return_value=self.ARXIV) as get:
                rec = cite.lookup("1706.03762")
                self.assertIn("export.arxiv.org/api/query?id_list=1706.03762", get.call_args[0][0])
            self.assertEqual(rec["title"], "Attention Is All You Need")
            self.assertEqual(cite.add_reference(cfg, rec), "Vaswani17")          # already there: same arXiv id
            with mock.patch.object(cite, "http_get", return_value=self.CROSSREF.encode()) as get:
                rec = cite.lookup("10.1038/nature14539")
                self.assertIn("api.crossref.org/works/10.1038/nature14539", get.call_args[0][0])
            before = (root / "content" / "references.yml").read_text()
            self.assertEqual(cite.add_reference(cfg, rec), "LeCun15")
            after = (root / "content" / "references.yml").read_text()
            self.assertTrue(after.startswith(before))                              # appended, not rewritten
            refs = content.load_references(cfg)
            self.assertEqual(refs["LeCun15"]["venue"], "Nature")
            with self.assertRaises(cite.CiteError):
                cite.add_reference(cfg, {"title": "x", "authors": ["A B"], "year": 2020}, key="LeCun15")
        finally:
            cleanup(root)


class CommandLine(unittest.TestCase):
    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        saved = config.ROOT
        try:
            with redirect_stdout(out), redirect_stderr(err):
                code = cli.main(list(args))
        finally:
            config.set_root(saved)
        return code, out.getvalue() + err.getvalue()

    def test_new_check_build(self):
        root = make_site()
        try:
            code, text = self.run_cli("--root", str(root), "new", "My First Idea")
            self.assertEqual(code, 0, text)
            path = root / "content" / "posts" / "my-first-idea.md"
            page = content.load_file(path, config.load(root))
            self.assertEqual((page.title, page.status), ("My First Idea", "draft"))
            code, text = self.run_cli("--root", str(root), "check", str(path))
            self.assertIn("Checked 1 page(s)", text)
            code, text = self.run_cli("--root", str(root), "build")
            self.assertEqual(code, 0, text)
            path.write_text(post(body="[[post:nope]]"))
            code, text = self.run_cli("--root", str(root), "build")
            self.assertEqual(code, 1)
            self.assertIn("my-first-idea.md:7", text)
        finally:
            cleanup(root)

    def test_new_writes_valid_yaml_and_refuses_odd_slugs(self):
        """C-9: a title with a backslash or quotes broke the front matter; --slug ../x wrote outside content/."""
        root = make_site()
        try:
            title = 'Paths like C:\\new and "quotes" \\q: here'
            code, text = self.run_cli("--root", str(root), "new", title)
            self.assertEqual(code, 0, text)
            made = sorted((root / "content/posts").glob("*.md"))
            self.assertEqual(len(made), 1)
            page = content.load_file(made[0], config.load(root))
            self.assertEqual(page.title, title)
            for slug in ("../evil", "a/b", "..", "/abs", "Caps", "a\\b", ".hidden"):
                with self.subTest(slug=slug):
                    code, text = self.run_cli("--root", str(root), "new", "X", "--slug", slug)
                    self.assertEqual(code, 2, text)
            self.assertFalse((root / "content/evil.md").exists())
            self.assertEqual(len(list(root.rglob("*.md"))), 1)
        finally:
            cleanup(root)

    def test_unreadable_status_or_date_stops_the_build(self):
        """C-1: a page that is not status: draft but has a status or date the build cannot read used to vanish."""
        for field, line_text in (("status", "status: publshed"), ("date", "date: 2026/01/05")):
            with self.subTest(field=field):
                text = post(title="Lonely") if field == "status" else post(title="Lonely", date="2026/01/05")
                if field == "status":
                    text = text.replace("date:", line_text + "\ndate:", 1)
                root = make_site({"posts/lonely": text, "posts/other": post(title="Other")})
                try:
                    code, out = self.run_cli("--root", str(root), "build")
                    self.assertEqual(code, 1, out)
                    line = 1 + text.split("\n").index(line_text)
                    self.assertIn(f"content/posts/lonely.md:{line}: error:", out)
                    self.assertIn("would not be published", out)
                finally:
                    cleanup(root)
        # a page that says status: draft may keep an unfinished date
        root = make_site({"posts/lonely": post(title="Lonely", date="2026/01/05", status="draft"),
                          "posts/other": post(title="Other")})
        try:
            code, out = self.run_cli("--root", str(root), "build")
            self.assertEqual(code, 0, out)
        finally:
            cleanup(root)

    def test_impossible_dates_are_reported_with_file_and_line(self):
        """C-3: 2026-02-30 used to end in a ValueError traceback, in pages and in every YAML file."""
        cases = {
            "page": ("content/posts/bad.md:3", lambda r: (r / "content/posts/bad.md").write_text(post(date="2026-02-30"))),
            "references": ("content/references.yml:4", lambda r: (r / "content/references.yml").write_text(
                (r / "content/references.yml").read_text() + "X1: {title: x, year: 2020, seen: 2026-02-30}\n")),
            "site.yml": ("site.yml:6", lambda r: (r / "site.yml").write_text((r / "site.yml").read_text()
                                                                             + "extra: {launched: 2026-13-01}\n")),
            "cv": ("content/cv.yml:2", lambda r: (r / "content/cv.yml").write_text("name: A\nupdated: 2025-02-29\n")),
        }
        for name, (where, setup) in cases.items():
            with self.subTest(name=name):
                root = make_site({"posts/ok": post()})
                try:
                    setup(root)
                    code, out = self.run_cli("--root", str(root), "build")
                    self.assertNotEqual(code, 0, out)
                    self.assertNotIn("Traceback", out)
                    self.assertIn(where, out)
                    self.assertIn("not a real date", out)
                finally:
                    cleanup(root)

    def test_check_counts_unreadable_files_and_reports_only_named_ones(self):
        """C-2: front matter that cannot be read was printed but not counted (exit 0), and named files got
        everyone's parse errors."""
        root = make_site({"posts/ok": post(), "posts/broken": '---\ntitle: "x\n---\nbody\n'})
        try:
            code, out = self.run_cli("--root", str(root), "check")
            self.assertEqual(code, 1, out)
            self.assertIn("content/posts/broken.md:2: error: the front matter is not valid YAML", out)
            self.assertIn("1 error(s)", out)
            code, out = self.run_cli("--root", str(root), "check", str(root / "content/posts/ok.md"))
            self.assertEqual(code, 0, out)
            self.assertNotIn("broken", out)
            self.assertIn("Checked 1 page(s): 0 error(s)", out)
            code, out = self.run_cli("--root", str(root), "check", str(root / "content/posts/broken.md"))
            self.assertEqual(code, 1, out)
            self.assertIn("Checked 1 page(s): 1 error(s)", out)
        finally:
            cleanup(root)

    def test_editor_port_and_its_old_name(self):
        """E-11: --editor-port is the name; --studio-port keeps working."""
        root = make_site()
        try:
            for flag in ("--editor-port", "--studio-port"):
                with self.subTest(flag=flag), mock.patch("bazinga.serve.serve", return_value=0) as serve:
                    code, text = self.run_cli("--root", str(root), "serve", flag, "9123", "--port", "9122")
                    self.assertEqual(code, 0, text)
                    self.assertEqual(serve.call_args.kwargs["studio_port"], 9123)
        finally:
            cleanup(root)

    def test_no_studio_names_or_made_up_email_in_what_people_see(self):
        from bazinga.studio import cite as studio_cite
        from bazinga.studio import server
        self.assertNotIn("@", studio_cite.UA)
        self.assertNotIn("Studio", studio_cite.UA)
        self.assertNotIn("Studio", server.Handler.server_version)
        src = (REPO / "bazinga/studio/server.py").read_text(encoding="utf-8")
        self.assertNotIn("Studio stopped", src)

    def test_passthrough_keeps_options(self):
        with mock.patch("bazinga.cli._module") as module:
            module.return_value.main = mock.Mock(return_value=0)
            self.run_cli("studio", "--port", "9999", "--no-browser")
            argv = module.return_value.main.call_args[0][0]
            self.assertEqual(argv[:3], ["--port", "9999", "--no-browser"])


class Vendor(unittest.TestCase):
    def test_every_url_is_pinned(self):
        for url in vendor.pinned_urls():
            self.assertRegex(url, r"@\d+\.\d+\.\d+|/v\d+\.\d+\.\d+/", url)
            self.assertNotIn("latest", url)

    def test_font_urls(self):
        urls = vendor.font_urls(config.load(EXAMPLE)["theme"])
        self.assertTrue(any("STIX+Two+Math" in u for u in urls))


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class Scripts(unittest.TestCase):
    def test_site_js_syntax(self):
        path = REPO / "bazinga" / "theme" / "assets" / "js" / "site.js"
        proc = subprocess.run(["node", "--check", str(path)], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)


if __name__ == "__main__":
    unittest.main()
