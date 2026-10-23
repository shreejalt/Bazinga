"""A site served under a sub-path (a GitHub Pages project site, https://alice.github.io/notes/): every link, script,
data file and module the built pages ask for starts with /notes, the absolute addresses (canonical, Open Graph,
sitemap, feed, robots, llms.txt) name the full origin once, and a site at the root of its host builds exactly as
before."""
import os
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_core_support import copy_example  # noqa: E402

from bazinga import build, cli, config  # noqa: E402

ORIGIN = "https://alice.github.io/notes"
BASE = "/notes"
TEXT = (".html", ".css", ".js", ".json", ".xml", ".txt", ".md")
# a path on this site written where a browser follows it: an attribute, url(…), or a quoted string in data or scripts
ROOT_PATH = re.compile(r"""(?:\b(?:href|src|srcset|action|poster|content|data-[\w-]+)\s*=\s*["']|url\(\s*["']?|["'`]|\\")"""
                       r"""(/(?!/)[A-Za-z_][^"'`\s)<>]*)""")


def _under_base(path: str) -> bool:
    return path == BASE or path.startswith(BASE + "/") or path.startswith(BASE + "?")


class SubPathSite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="bazinga-base-"))
        copy_example(cls.tmp)
        cls.root_out, cls.out = cls.tmp / "out-root", cls.tmp / "out-notes"
        build.build(config.load(cls.tmp), quiet=True, out=cls.root_out)
        cls.cfg = config.load(cls.tmp, origin=ORIGIN)
        build.build(cls.cfg, quiet=True, out=cls.out)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def text(self, rel, out=None):
        return ((out or self.out) / rel).read_text(encoding="utf-8")

    def files(self, out=None):
        return [f for f in sorted((out or self.out).rglob("*")) if f.is_file() and f.suffix in TEXT]

    # ---- configuration
    def test_base_comes_from_the_origin(self):
        self.assertEqual(self.cfg.base, "/notes")
        self.assertEqual(self.cfg.origin, ORIGIN)
        for origin, base in (("https://example.com", ""), ("https://example.com/", ""),
                             ("https://alice.github.io/notes/", "/notes"), ("https://x.org/a/b", "/a/b")):
            self.assertEqual(config.load(self.tmp, origin=origin).base, base, origin)
        self.assertEqual(config.load(self.tmp, origin=ORIGIN, local=True).base, "")   # serve and the Editor
        with self.assertRaises(config.ConfigError):
            config.load(self.tmp, origin="https://alice.github.io/notes?x=1")

    def test_site_url(self):
        self.assertEqual(config.site_url("/notes", "/reads/x/"), "/notes/reads/x/")
        self.assertEqual(config.site_url("/notes", "/"), "/notes/")
        for other in ("https://arxiv.org/abs/1", "//cdn.example/x.js", "#ref-1", "mailto:a@b.c", "static/a.png", ""):
            self.assertEqual(config.site_url("/notes", other), other)
        self.assertEqual(config.site_url("", "/reads/x/"), "/reads/x/")
        html = '<a href="/cv/">CV</a> <img src=\'/static/a.png\'> <a href="https://x.org/">x</a> <a href="#top">t</a>'
        self.assertEqual(config.site_links("/notes", html),
                         '<a href="/notes/cv/">CV</a> <img src=\'/notes/static/a.png\'> '
                         '<a href="https://x.org/">x</a> <a href="#top">t</a>')

    def test_origin_from_the_environment(self):
        self.assertEqual(config.origin_from_env({"BAZINGA_ORIGIN": ORIGIN, "SITE_URL": "https://a.org"}), ORIGIN)
        self.assertEqual(config.origin_from_env({"SITE_URL": " https://a.org "}), "https://a.org")
        self.assertIsNone(config.origin_from_env({"BAZINGA_ORIGIN": " "}))

    def test_cli_build_takes_the_origin_from_the_environment(self):
        with mock.patch.dict(os.environ, {"BAZINGA_ORIGIN": ORIGIN}):
            with mock.patch("sys.stdout"):
                self.assertEqual(cli.main(["--root", str(self.tmp), "build", "--quiet"]), 0)
        home = self.text("index.html", self.tmp / "_site")
        self.assertIn(f'<link rel="canonical" href="{ORIGIN}/">', home)
        self.assertIn('<meta name="bazinga-base" content="/notes">', home)

    # ---- the built files
    def test_no_path_outside_the_base(self):
        found = []
        for f in self.files():
            rel = f.relative_to(self.out).as_posix()
            if f.suffix in (".md", ".txt"):
                continue                         # Markdown copies and llms files link with full addresses (below)
            text = f.read_text(encoding="utf-8")
            for m in ROOT_PATH.finditer(text):
                path = m.group(1)
                if _under_base(path):
                    continue
                before = text[max(0, m.start() - 12):m.start() + 1]
                if f.suffix == ".js" and re.search(r"(?:BASE\s*\+\s*|\$\{BASE\})[\"'`]?$", before):
                    continue                     # scripts put the base (from <meta name="bazinga-base">) in front
                if rel == "assets/js/pyworker.js" and path.startswith("/bazinga"):
                    continue                     # the in-browser file system, not an address
                if f.suffix == ".js" and re.match(r"/[gimsuy]*[,);.]", path):
                    continue                     # the end of a regular expression
                found.append(f"{rel}: {path}")
        self.assertEqual(found, [], "paths that miss the /notes base:\n" + "\n".join(found[:40]))

    def test_head_of_a_page(self):
        page = self.text("reads/welcome/index.html")
        self.assertIn(f'<link rel="canonical" href="{ORIGIN}/reads/welcome/">', page)
        self.assertIn(f'<meta property="og:url" content="{ORIGIN}/reads/welcome/">', page)
        self.assertIn('<meta name="bazinga-root" content="/notes/">', page)
        self.assertIn('<meta name="bazinga-base" content="/notes">', page)
        self.assertIn('href="/notes/reads/welcome/index.md"', page)
        self.assertIn('<script src="/notes/data/site.js?v=', page)
        self.assertIn(f'"url":"{ORIGIN}/reads/welcome/"', page)               # JSON-LD
        self.assertNotIn("/notes/notes", page)
        self.assertNotIn(ORIGIN + "/notes", page)

    def test_links_written_in_content(self):
        home = self.text("index.html")
        self.assertIn('<a href="/notes/cv/">CV</a>', home)                 # raw HTML in site.yml home.about
        self.assertIn('src="/notes/static/images/photo.svg"', home)
        welcome = self.text("reads/welcome/index.html")
        self.assertRegex(welcome, r'<a class="xref" href="/notes/[a-z]+/[a-z0-9-]+/" data-id=')   # [[id]] links

    def test_sitemap_feed_robots_llms(self):
        locs = re.findall(r"<loc>([^<]+)</loc>", self.text("sitemap.xml"))
        self.assertTrue(locs)
        self.assertEqual([u for u in locs if not u.startswith(ORIGIN + "/") or "/notes/notes" in u], [])
        self.assertIn(f"{ORIGIN}/reads/welcome/", locs)
        self.assertIn(f"Sitemap: {ORIGIN}/sitemap.xml", self.text("robots.txt"))
        feed = self.text("feed.xml")
        self.assertIn(f'<link href="{ORIGIN}/feed.xml" rel="self"/>', feed)
        self.assertNotIn('href="/reads/', feed)
        self.assertNotIn("href=&quot;/reads/", feed)                         # links inside the entries' content
        for name in ("llms.txt", "llms-full.txt", "reads/welcome/index.md"):
            links = re.findall(r"\]\((/[^)]*|https?://[^)]*)\)", self.text(name))
            self.assertEqual([u for u in links if u.startswith("/") or (u.startswith("https://alice.github.io")
                                                                        and not u.startswith(ORIGIN + "/"))], [], name)

    def test_404_page(self):
        page = self.text("404.html")
        self.assertIn('href="/notes/">home page</a>', page)
        self.assertIn('href="/notes/assets/css/site.css?v=', page)

    def test_data_files(self):
        for name in ("data/passages.json", "data/graph.json", "data/site.js"):
            urls = re.findall(r'"url":"([^"]*)"', self.text(name))
            self.assertTrue(urls, name)
            self.assertEqual([u for u in urls if u.startswith("/") and not u.startswith(BASE + "/")], [], name)

    def test_same_as_a_root_build_apart_from_the_base(self):
        """Taking the base out again gives the root build byte for byte: nothing is missed and nothing doubled."""
        differ = []
        for f in self.files(self.root_out):
            rel = f.relative_to(self.root_out)
            sub = (self.out / rel).read_text(encoding="utf-8")
            sub = sub.replace(ORIGIN, "https://example.com").replace('content="/notes">', 'content="">')
            for q in ('"', "'", "(", "`"):
                sub = sub.replace(q + "/notes/", q + "/")
            if sub != f.read_text(encoding="utf-8"):
                differ.append(rel.as_posix())
        self.assertEqual(differ, [])

    def test_root_build_is_unchanged(self):
        home = self.text("index.html", self.root_out)
        self.assertIn('<link rel="canonical" href="https://example.com/">', home)
        self.assertIn('<meta name="bazinga-root" content="/">', home)
        self.assertIn('<meta name="bazinga-base" content="">', home)
        self.assertIn('<a href="/cv/">CV</a>', home)
        self.assertIn('<a class="cta" href="/explore/">Explore the map</a>', home)
        self.assertNotIn("/notes", "".join(f.read_text(encoding="utf-8") for f in self.files(self.root_out)))


if __name__ == "__main__":
    unittest.main()
