"""The default theme's pages: the home sections, the CV, the kinds (reads, papers, projects, external entries), the
list pager, the map data, and the local-only Write button (never in a build)."""
import json
import os
import re
import shutil
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_core_support import cleanup, copy_example, make_site, post  # noqa: E402

from bazinga import build, config, serve  # noqa: E402


class ExampleTheme(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="bazinga-theme-"))
        copy_example(cls.tmp)
        cls.cfg = config.load(cls.tmp)
        cls.result = build.build(cls.cfg, quiet=True)
        cls.out = cls.cfg.out_dir

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def html(self, rel):
        return (self.out / rel).read_text(encoding="utf-8")

    def test_home_sections(self):
        home = self.html("index.html")
        for section in ("about", "map", "experience", "education", "contact"):
            self.assertIn(f'<section class="sec" id="{section}">', home)
        self.assertEqual(home.count('<details class="role">'), 3)                # each role opens for its points
        self.assertIn("<b>MSc, Computer Science</b>", home)                      # degree and school only
        self.assertIn("Example University", home)
        self.assertIn('href="/cv/"', home)
        self.assertIn('src="/static/images/photo.svg"', home)
        self.assertIn('<a class="cta" href="/explore/">Explore the map</a>', home)
        self.assertIn('mailto:you@example.com', home)
        rail = home.split('<aside class="rail">')[1].split("</aside>")[0]
        self.assertIn('href="#about" aria-current="true">About</a>', rail)     # the home rail lists its sections

    def test_cv_page(self):
        cv = self.html("cv/index.html")
        self.assertEqual(cv.count('<li class="jobrow">'), 3)
        self.assertIn('id="skills"', cv)
        self.assertIn('href="/projects/bazinga/"', cv)                           # a role's page and open source
        self.assertIn('href="/topics/computer-vision/"', cv)
        self.assertIn('aria-current="true">CV</a>', cv)

    def test_memo_layout_of_a_read(self):
        page = self.html("reads/attention-from-scratch/index.html")
        self.assertIn('<article class="memo">', page)
        self.assertIn('<h2 id="summary">Summary</h2>', page)
        self.assertRegex(page, r'<h2 id="[^"]+">1\. ')                          # numbered sections
        self.assertIn('id="connections"', page)
        self.assertIn('<svg class="links wide"', page)
        self.assertIn('<ol class="series">', page)
        self.assertIn("[Page 1]", page)

    def test_paper_explains_and_pagebreak(self):
        page = self.html("papers/attention-is-all-you-need/index.html")
        self.assertIn("Explains: <a href=\"https://arxiv.org/abs/1706.03762\">Attention Is All You Need</a>", page)
        self.assertIn("[Page 3]", page)                                          # one ::pagebreak: three pages
        self.assertNotIn("pagebreak-slot", page)
        lst = self.html("papers/index.html")
        self.assertIn("<b>Attention Is All You Need</b>", lst)

    def test_external_entries(self):
        self.assertFalse((self.out / "elsewhere" / "the-illustrated-transformer").exists())   # no page of their own
        lst = self.html("elsewhere/index.html")
        self.assertIn('href="https://jalammar.github.io/illustrated-transformer/"', lst)
        self.assertIn("Jay Alammar", lst)
        layout = json.loads(self.html("data/map.json"))
        self.assertIn("article:the-illustrated-transformer", {n["id"] for n in layout["nodes"]})
        self.assertNotIn("jalammar", self.html("sitemap.xml"))
        self.assertNotIn("article:", json.dumps(json.loads(self.html("data/passages.json"))))

    def test_lists_have_the_pager(self):
        lst = self.html("reads/index.html")
        self.assertIn('<div class="pager" id="pager"', lst)
        self.assertIn("/assets/js/pager.js", lst)
        reads = [p for p in self.result.pages if p.kind == "reads"]
        self.assertEqual(lst.count("<tr data-text="), len(reads))                # every row; the script shows ten

    def test_map_and_views(self):
        layout = json.loads(self.html("data/map.json"))
        self.assertGreaterEqual(len(layout["nodes"]), 10)
        view = json.loads(self.html("data/view/read-attention-from-scratch.json"))
        self.assertIn("motion", view)
        self.assertTrue(view["related"])
        self.assertIn("window.SITE=", self.html("data/site.js"))

    def test_no_write_button_in_a_build(self):
        for path in self.out.rglob("*"):
            if path.suffix in (".html", ".js", ".json", ".xml", ".txt", ".md"):
                text = path.read_text(encoding="utf-8", errors="ignore")
                self.assertNotIn("__bazinga", text, path)
                self.assertNotIn(">Write</a>", text, path)
                self.assertNotIn("Edit this page", text, path)


class ThemeRules(unittest.TestCase):
    def test_list_with_many_pages(self):
        root = make_site({f"posts/p{i:02d}": post(f"Post {i}", date=f"2020-01-{i + 1:02d}") for i in range(12)})
        try:
            cfg = config.load(root)
            build.build(cfg, quiet=True)
            lst = (cfg.out_dir / "posts" / "index.html").read_text()
            self.assertEqual(lst.count("<tr data-text="), 12)
            self.assertIn('data-word="writing"', lst)
        finally:
            cleanup(root)

    def test_unknown_cv_topic_stops_the_build(self):
        root = make_site({"posts/a": post("A")})
        try:
            (root / "content" / "cv.yml").write_text("experience:\n- {org: X, role: Y, tags: [nope]}\n")
            with self.assertRaises(build.BuildError):
                build.build(config.load(root), quiet=True)
        finally:
            cleanup(root)

    def test_unknown_explains_key_is_an_error(self):
        root = make_site({"posts/a": post("A", explains="[Nope99]")})
        try:
            with self.assertRaises(build.BuildError) as ctx:
                build.build(config.load(root), quiet=True)
            self.assertIn("Nope99", str(ctx.exception))
        finally:
            cleanup(root)


class Stylesheet(unittest.TestCase):
    """E-2: the rail is light now, so it keeps the global blue focus ring, and its dark-rail colours are gone."""

    def test_rail_keeps_the_global_focus_ring(self):
        import re
        css = (Path(__file__).resolve().parent.parent / "bazinga/theme/assets/css/site.css").read_text(encoding="utf-8")
        self.assertIn(":focus-visible{outline:2px solid var(--blue)", css)
        self.assertNotRegex(css, r"\.rail[^{]*:focus-visible\s*\{[^}]*outline-color")
        first = css.split("/* ---------- man-page sections", 1)[0]
        self.assertNotIn("var(--on-dark)", first.split(".rail{", 1)[1])   # dead dark-rail colours are gone


class LocalWriteButton(unittest.TestCase):
    PAGE = b'<html><body class="post" data-page="read:welcome"><aside class="rail"><!-- local-tools --></aside></body></html>'

    def test_injected_only_with_the_studio(self):
        self.assertEqual(serve.inject_local(self.PAGE, False), self.PAGE)
        html = serve.inject_local(self.PAGE, True).decode()
        self.assertIn('<a class="cta write" href="/__bazinga/write">Write</a>', html)
        self.assertIn('href="/__bazinga/write?page=read:welcome">Edit this page</a>', html)

    def test_redirect_goes_to_the_studio_with_its_token(self):
        root = make_site({"posts/a": post("A")})
        httpd = None
        try:
            state = serve.State(config.load(root))
            state.studio = type("FakeStudio", (), {"url": "http://127.0.0.1:9/?token=abc"})()
            httpd = ThreadingHTTPServer(("127.0.0.1", 0), serve.make_handler(state))
            state.port = httpd.server_address[1]
            threading.Thread(target=httpd.serve_forever, daemon=True).start()

            class NoRedirect(urllib.request.HTTPRedirectHandler):
                def redirect_request(self, *a, **k):
                    return None
            opener = urllib.request.build_opener(NoRedirect)
            base = f"http://127.0.0.1:{state.port}/__bazinga/write"
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                opener.open(base + "?page=post:a")
            self.assertEqual(ctx.exception.code, 302)
            self.assertEqual(ctx.exception.headers["Location"], "http://127.0.0.1:9/?token=abc#/edit/post:a")
            req = urllib.request.Request(base, headers={"Sec-Fetch-Site": "cross-site"})
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                opener.open(req)
            self.assertEqual(ctx.exception.code, 403)
        finally:
            if httpd:
                httpd.shutdown()
                httpd.server_close()
            cleanup(root)


if __name__ == "__main__":
    unittest.main()
