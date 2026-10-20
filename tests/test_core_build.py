"""build.py, content.py, seo.py and config.py: drafts and scheduled pages never public, theme overrides, SEO files,
and the example site building end to end in a temporary copy."""
import json
import os
import shutil
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_core_support import cleanup, copy_example, make_site, post  # noqa: E402

from tessera import build, config, content, seo  # noqa: E402

FUTURE = (date.today() + timedelta(days=30)).isoformat()


def all_text(out: Path) -> str:
    return "\n".join(p.read_text(errors="ignore") for p in out.rglob("*") if p.is_file()
                     and p.suffix in (".html", ".xml", ".txt", ".json", ".md"))


class Config(unittest.TestCase):
    def test_defaults_and_attribute_access(self):
        root = make_site()
        try:
            cfg = config.load(root)
            self.assertEqual(cfg.site.name, "Test Site")
            self.assertEqual(cfg["theme"]["accent"], "#3b5bdb")        # default filled in
            self.assertEqual(cfg.out_dir, root.resolve() / "_site")
        finally:
            cleanup(root)

    def test_bad_values_are_explained(self):
        root = make_site(site_yml="theme: {accent: blue}\n")
        try:
            with self.assertRaises(config.ConfigError) as ctx:
                config.load(root)
            self.assertIn("hex colour", str(ctx.exception))
        finally:
            cleanup(root)


class Content(unittest.TestCase):
    def setUp(self):
        self.cfg = config.load(make_site())

    def tearDown(self):
        cleanup(self.cfg.root)

    def parse(self, text, name="x"):
        return content.parse(text, Path(f"content/posts/{name}.md"), self.cfg)

    def test_ids_urls_and_body_line(self):
        page = self.parse(post(body="First body line."), "my-post")
        self.assertEqual((page.id, page.url), ("post:my-post", "/posts/my-post/"))
        self.assertEqual(page.body.split("\n")[0], "First body line.")
        self.assertEqual(page.body_line, 7)

    def test_states(self):
        self.assertEqual(self.parse(post()).state, "published")
        self.assertTrue(self.parse(post()).public)
        draft = self.parse(post(status="draft"))
        self.assertFalse(draft.public)
        self.assertEqual(draft.state, "draft")
        scheduled = self.parse(post(date=FUTURE))
        self.assertTrue(scheduled.scheduled)
        self.assertFalse(scheduled.public)

    def test_scheduled_goes_public_on_its_date(self):
        page = self.parse(post(date=FUTURE))
        later = date.today() + timedelta(days=31)
        with mock.patch("tessera.content.today", return_value=later):
            self.assertTrue(page.public)

    def test_problems_carry_lines(self):
        page = self.parse('---\ntitle: x\ndate: 20-1-2020\ntopics: a, b\n---\n')
        lines = sorted(line for line, _, _ in page.problems)
        self.assertEqual(lines, [3, 4])

    def test_broken_yaml_raises_with_line(self):
        with self.assertRaises(content.ContentError) as ctx:
            self.parse('---\ntitle: x\nsummary: "unclosed\n---\n')
        self.assertIsNotNone(ctx.exception.line)


class Builds(unittest.TestCase):
    def test_drafts_and_scheduled_never_public(self):
        root = make_site({
            "posts/live": post("Live page", body="Visible text."),
            "posts/secret": post("Secret draft", status="draft", body="SECRETDRAFTTEXT"),
            "posts/later": post("Scheduled page", date=FUTURE, body="SCHEDULEDTEXT"),
        })
        try:
            cfg = config.load(root)
            result = build.build(cfg, quiet=True)
            self.assertEqual([p.id for p in result.pages], ["post:live"])
            text = all_text(cfg.out_dir)
            for secret in ("SECRETDRAFTTEXT", "SCHEDULEDTEXT", "Secret draft", "Scheduled page", "/posts/secret/"):
                self.assertNotIn(secret, text, secret)
            self.assertFalse((cfg.out_dir / "posts" / "secret").exists())
            # --drafts includes them, and keeps search engines out.
            build.build(cfg, drafts=True, quiet=True)
            self.assertTrue((cfg.out_dir / "posts" / "secret" / "index.html").exists())
            self.assertIn("Disallow: /", (cfg.out_dir / "robots.txt").read_text())
            self.assertFalse((cfg.out_dir / "sitemap.xml").exists())
        finally:
            cleanup(root)

    def test_link_to_a_draft_fails_the_production_build(self):
        root = make_site({"posts/a": post("A", body="See [[post:b]]."), "posts/b": post("B", status="draft")})
        try:
            with self.assertRaises(build.BuildError) as ctx:
                build.build(config.load(root), quiet=True)
            self.assertIn("content/posts/a.md:7", str(ctx.exception))
            self.assertIn("not public yet", str(ctx.exception))
            self.assertFalse((root / "_site").exists())                  # nothing half-written
            build.build(config.load(root), strict=False, quiet=True)      # lenient builds go on
        finally:
            cleanup(root)

    def test_theme_override_shadows_by_path(self):
        root = make_site({"posts/a": post("A")})
        try:
            (root / "theme" / "templates").mkdir(parents=True)
            (root / "theme" / "assets" / "css").mkdir(parents=True)
            (root / "theme" / "templates" / "404.html").write_text("CUSTOM 404 {{ site.name }}")
            (root / "theme" / "assets" / "css" / "site.css").write_text("/* mine */")
            cfg = config.load(root)
            build.build(cfg, quiet=True)
            self.assertEqual((cfg.out_dir / "404.html").read_text(), "CUSTOM 404 Test Site")
            self.assertEqual((cfg.out_dir / "assets" / "css" / "site.css").read_text(), "/* mine */")
            self.assertTrue((cfg.out_dir / "assets" / "css" / "tokens.css").exists())   # the rest still copied
            html = (cfg.out_dir / "posts" / "a" / "index.html").read_text()
            self.assertRegex(html, r'/assets/css/site.css\?v=[0-9a-f]{10}')
        finally:
            cleanup(root)

    def test_seo_files(self):
        root = make_site({"posts/a": post("Alpha", date="2020-01-02", updated="2020-03-04"),
                          "posts/b": post("Beta", date="2020-01-01")})
        try:
            cfg = config.load(root)
            build.build(cfg, quiet=True)
            out = cfg.out_dir
            sitemap = (out / "sitemap.xml").read_text()
            self.assertIn("<loc>https://test.example/posts/a/</loc><lastmod>2020-03-04</lastmod>", sitemap)
            self.assertIn("<loc>https://test.example/posts/b/</loc><lastmod>2020-01-01</lastmod>", sitemap)
            self.assertNotIn("/topics/optimization/", sitemap)                 # unused topic
            self.assertEqual((out / "robots.txt").read_text().splitlines()[-1],
                             "Sitemap: https://test.example/sitemap.xml")
            feed = (out / "feed.xml").read_text()
            self.assertIn('<feed xmlns="http://www.w3.org/2005/Atom">', feed)
            self.assertEqual(feed.count("<entry>"), 2)
            html = (out / "posts" / "a" / "index.html").read_text()
            self.assertIn('<link rel="canonical" href="https://test.example/posts/a/">', html)
            self.assertIn('<meta property="og:title" content="Alpha">', html)
            ld = json.loads(html.split('<script type="application/ld+json">')[1].split("</script>")[0])
            self.assertEqual(ld["@type"], "BlogPosting")
            self.assertEqual(ld["dateModified"], "2020-03-04")
            home = (out / "index.html").read_text()
            self.assertIn('"@type":"WebSite"', home)
            self.assertIn('"@type":"Person"', home)
        finally:
            cleanup(root)

    def test_feed_is_capped_at_thirty(self):
        cfg = config.load(make_site())
        try:
            pages = [content.parse(post(f"P{i}", date=f"2020-01-{1 + i % 28:02d}"), Path(f"content/posts/p{i}.md"), cfg)
                     for i in range(40)]
            self.assertEqual(seo.feed(cfg, pages).count("<entry>"), 30)
        finally:
            cleanup(cfg.root)

    def test_description_is_cut_at_a_sentence(self):
        first = "The first sentence of this summary is long enough to stand on its own as a description."
        self.assertEqual(seo.cut(first + " " + "word " * 60), first)
        self.assertLessEqual(len(seo.cut("a" * 400)), 155)


class ExampleSite(unittest.TestCase):
    def test_example_site_builds_end_to_end(self):
        tmp = Path(tempfile.mkdtemp(prefix="tessera-example-"))
        try:
            copy_example(tmp)
            cfg = config.load(tmp)
            result = build.build(cfg, quiet=True)
            out = cfg.out_dir
            ids = {p.id for p in result.pages}
            self.assertIn("read:welcome", ids)
            self.assertIn("read:writing-math", ids)
            self.assertIn("paper:attention-is-all-you-need", ids)
            self.assertNotIn("read:notes-on-attention", ids)                   # the example draft
            welcome = (out / "reads" / "welcome" / "index.html").read_text()
            self.assertGreater(welcome.count("<math"), 5)
            self.assertIn('class="callout callout-key"', welcome)
            self.assertIn('id="papers"', welcome)
            self.assertNotIn("embed-error", welcome)
            self.assertNotIn("math-error", welcome)
            for page in ("index.html", "reads/index.html", "papers/index.html", "projects/index.html",
                         "elsewhere/index.html", "cv/index.html", "data/site.js", "data/map.json",
                         "data/view/read-welcome.json", "figures/_mapview.py", "topics/index.html", "series/index.html",
                         "series/getting-started/index.html", "explore/index.html", "ask/index.html", "404.html",
                         "assets/css/site.css", "assets/css/math.css", "assets/js/site.js", "assets/css/pygments.css"):
                self.assertTrue((out / page).exists(), page)
            # No visible text names the machinery.
            for name in ("Pyodide", "BM25", "pyodide"):
                for html in out.rglob("*.html"):
                    visible = html.read_text().split("<body", 1)[1]
                    visible = visible.split("<script", 1)[0]
                    self.assertNotIn(name, visible.replace("tessera-pyodide", ""), f"{name} in {html}")
            self.assertFalse(any("studio" in str(p.relative_to(out)).lower() for p in out.rglob("*")))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_preview_html_shows_drafts_and_their_problems(self):
        tmp = Path(tempfile.mkdtemp(prefix="tessera-preview-"))
        try:
            copy_example(tmp)
            cfg = config.load(tmp)
            page = content.load_file(tmp / "content" / "reads" / "notes-on-attention.md", cfg)
            html = build.preview_html(page, cfg)
            self.assertIn("Draft.", html)
            page.body += "\n\nBroken [[read:nope]].\n"
            html = build.preview_html(page, cfg)
            self.assertIn("preview-issues", html)
            self.assertIn("read:nope", html)
            self.assertFalse((tmp / "_site").exists())                          # nothing written
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
