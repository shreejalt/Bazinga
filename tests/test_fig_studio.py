"""The Editor's figure panel API: the gallery, the builder (preview, save, reopen), checking unsaved code, the draft
frame and its files, and the guards on all of them (over real HTTP)."""

import http.client
import json
import shutil
import tempfile
import threading
import unittest
from pathlib import Path

from bazinga import figbuilder
from bazinga.studio.api import Editor
from bazinga.studio.security import Refused
from bazinga.studio.server import ROUTES_GET, ROUTES_POST, StudioServer

ROOT = Path(__file__).resolve().parent.parent


def make_site(root):
    shutil.copy(ROOT / "site.yml", root / "site.yml")
    (root / "content" / "reads").mkdir(parents=True)
    (root / "figures").mkdir()
    shutil.copy(ROOT / "bazinga" / "starters" / "figures" / "slider_plot.py", root / "figures" / "wave.py")
    (root / "content" / "reads" / "p.md").write_text('---\ntitle: "A page"\n---\n\n::figure wave\n', encoding="utf-8")


class Handlers(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="fig-studio-"))
        make_site(self.root)
        self.studio = Editor(self.root)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_routes_are_registered(self):
        for path in ("/api/figures/gallery", "/api/figures/open", "/api/builder/info"):
            self.assertIn(path, ROUTES_GET)
        for path in ("/api/builder/preview", "/api/builder/save", "/api/figures/check", "/api/figures/save-code"):
            self.assertIn(path, ROUTES_POST)
            self.assertTrue(callable(getattr(self.studio, ROUTES_POST[path])))

    def test_builder_info(self):
        info = self.studio.builder_info()
        self.assertTrue(info["available"])
        self.assertEqual([t["type"] for t in info["types"]], list(figbuilder.TYPES))

    def test_gallery(self):
        g = self.studio.figures_gallery()
        (wave,) = g["figures"]
        self.assertEqual(wave["name"], "wave")
        self.assertTrue(wave["ok"])
        self.assertTrue(wave["svg"].startswith("<svg"))
        self.assertEqual(wave["made"], "code")
        self.assertEqual(wave["used_in"], ["A page"])

    def test_builder_preview_save_and_reopen(self):
        spec = figbuilder.default_spec("function")
        res = self.studio.builder_preview({"name": "damped", "spec": spec})
        self.assertTrue(res["ok"], res)
        self.assertTrue(res["report"]["ok"])
        self.assertTrue(res["frame"].startswith("/frame/draft/damped?v="))
        self.assertTrue((self.root / ".studio" / "drafts" / "figures" / "damped.py").is_file())
        self.assertFalse((self.root / "figures" / "damped.py").exists())          # nothing saved yet
        status, html = self.studio.draft_frame("damped", {})
        self.assertEqual(status, 200)
        self.assertIn('<meta name="bazinga-root" content="/_draft/">', html)
        self.assertIn('data-figure="damped"', html)
        self.assertEqual(self.studio.draft_file("/_draft/figures/damped.py").name, "damped.py")
        self.assertEqual(self.studio.draft_file("/_draft/figures/_plot.py").name, "plot.py")
        for bad in ("/_draft/figures/../site.yml", "/_draft/figures/Damped.py", "/_draft/x.py", "/_draft/figures/nope.py"):
            self.assertIsNone(self.studio.draft_file(bad), bad)

        saved = self.studio.builder_save({"name": "damped", "spec": spec, "create": True})
        self.assertTrue(saved["saved"] and saved["ok"], saved)
        opened = self.studio.figure_open({"name": "damped"})
        self.assertEqual(opened["made"], "builder")
        self.assertEqual(opened["spec"]["title"], "A damped wave")
        with self.assertRaises(Refused) as cm:
            self.studio.builder_save({"name": "damped", "spec": spec, "create": True})
        self.assertEqual(cm.exception.status, 409)
        spec["title"] = "Changed"
        self.assertTrue(self.studio.builder_save({"name": "damped", "spec": spec})["saved"])

        # changed by hand: it opens as code, and the form will not overwrite it without being asked
        path = self.root / "figures" / "damped.py"
        path.write_text(path.read_text().replace("SAMPLES = 0, 10, 200", "SAMPLES = 0, 10, 300"))
        self.assertEqual(self.studio.figure_open({"name": "damped"})["made"], "edited")
        with self.assertRaises(Refused) as cm:
            self.studio.builder_save({"name": "damped", "spec": spec})
        self.assertIn("changed by hand", cm.exception.message)
        self.assertTrue(self.studio.builder_save({"name": "damped", "spec": spec, "replace": True})["saved"])
        self.assertEqual(self.studio.figure_open({"name": "damped"})["made"], "builder")

    def test_builder_problems(self):
        spec = figbuilder.default_spec("function")
        spec["curves"][0]["expr"] = "a*sin(freqq*x)"
        res = self.studio.builder_preview({"name": "damped", "spec": spec})
        self.assertFalse(res["ok"])
        self.assertEqual(res["problems"][0]["path"], "curves.0.expr")
        res = self.studio.builder_save({"name": "damped", "spec": spec, "create": True})
        self.assertFalse(res["saved"])
        self.assertFalse((self.root / "figures" / "damped.py").exists())
        with self.assertRaises(Refused):
            self.studio.builder_preview({"name": "Bad Name", "spec": spec})
        with self.assertRaises(Refused):
            self.studio.builder_preview({"name": "ok", "spec": "not a form"})

    def test_check_unsaved_code_marks_the_line(self):
        src = (self.root / "figures" / "wave.py").read_text()
        bad = src.replace("wave = [", "wave = [undefined_name + ", 1)
        res = self.studio.figure_check({"name": "wave", "source": bad})
        self.assertFalse(res["ok"])
        line = next(n for n, l in enumerate(bad.splitlines(), 1) if "undefined_name" in l)
        self.assertEqual(res["report"]["line"], line)
        self.assertEqual((self.root / "figures" / "wave.py").read_text(), src)    # the saved file is untouched
        good = self.studio.figure_check({"name": "wave", "source": src})
        self.assertTrue(good["ok"])
        self.assertIn("frame", good)

    def test_save_code(self):
        src = figbuilder.generate(figbuilder.default_spec("bars"))
        res = self.studio.figure_save_code({"name": "budget", "source": src, "create": True})
        self.assertTrue(res["saved"] and res["ok"], res)
        self.assertEqual(res["made"], "builder")
        with self.assertRaises(Refused):
            self.studio.figure_save_code({"name": "budget", "source": src, "create": True})
        with self.assertRaises(Refused):
            self.studio.figure_save_code({"name": "budget", "source": None})


class OverHttp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="fig-studio-http-"))
        make_site(cls.tmp)
        cls.server = StudioServer(cls.tmp, 0)
        cls.server.quiet = True
        cls.thread = threading.Thread(target=cls.server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def request(self, method, path, body=None, cookie=True):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.port, timeout=60)
        h = {"Host": f"127.0.0.1:{self.server.port}"}
        if cookie:
            h["Cookie"] = f"{self.server.cookie}={self.server.token}"
        raw = None
        if body is not None:
            raw = json.dumps(body).encode()
            h.update({"Content-Type": "application/json", "Origin": f"http://127.0.0.1:{self.server.port}",
                      "Content-Length": str(len(raw))})
        conn.request(method, path, body=raw, headers=h)
        res = conn.getresponse()
        data = res.read()
        conn.close()
        return res.status, res.getheader("Content-Type"), data

    def test_flow(self):
        status, _, data = self.request("POST", "/api/builder/preview",
                                       {"name": "circle", "spec": figbuilder.default_spec("shapes")})
        self.assertEqual(status, 200)
        frame = json.loads(data)["frame"]
        status, ctype, html = self.request("GET", frame)
        self.assertEqual(status, 200)
        self.assertIn(b"bazinga-root", html)
        status, ctype, code = self.request("GET", "/_draft/figures/circle.py")
        self.assertEqual(status, 200)
        self.assertIn(figbuilder.MARK.encode(), code)
        status, _, _ = self.request("GET", "/_draft/figures/_plot.py")
        self.assertEqual(status, 200)
        status, _, data = self.request("GET", "/api/figures/gallery")
        self.assertEqual(status, 200)
        self.assertEqual([f["name"] for f in json.loads(data)["figures"]], ["wave"])

    def test_guarded(self):
        for method, path, body in (("GET", "/api/figures/gallery", None), ("GET", "/frame/draft/x", None),
                                   ("GET", "/_draft/figures/_plot.py", None),
                                   ("POST", "/api/builder/save", {"name": "x", "spec": {}})):
            status, _, _ = self.request(method, path, body, cookie=False)
            self.assertEqual(status, 401, path)


if __name__ == "__main__":
    unittest.main()
