"""The Studio's guards: local binding, Host allowlist, token cookie, Origin/Sec-Fetch-Site, JSON-only writes, no CORS,
path confinement (traversal and symlinks), upload limits and atomic writes."""

import base64
import http.client
import json
import os
import shutil
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from tessera.studio import security
from tessera.studio.security import Refused, atomic_write, confine
from tessera.studio.server import StudioServer

PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg==")


def make_site(root: Path):
    (root / "content" / "posts").mkdir(parents=True)
    (root / "site.yml").write_text('site:\n  name: "Test"\n  origin: "https://example.org"\n', encoding="utf-8")
    (root / "content" / "topics.yml").write_text(
        "groups:\n  - name: Main\n    topics:\n      - {slug: writing, label: Writing}\n", encoding="utf-8")
    (root / "content" / "posts" / "hello.md").write_text(
        '---\ntitle: "Hello"\nstatus: draft\nsummary: "A test page."\ntopics: [writing]\n---\n\nHello there.\n',
        encoding="utf-8")


class ServerCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="studio-sec-"))
        cls.root = cls.tmp / "site"
        cls.root.mkdir()
        make_site(cls.root)
        cls.outside = cls.tmp / "outside.txt"
        cls.outside.write_text("secret", encoding="utf-8")
        cls.server = StudioServer(cls.root, 0)
        cls.server.quiet = True
        cls.port = cls.server.port
        cls.thread = threading.Thread(target=cls.server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
        cls.thread.start()
        cls.cookie = f"{cls.server.cookie}={cls.server.token}"
        cls.origin = f"http://127.0.0.1:{cls.port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def request(self, method, path, body=None, headers=None, host=None, cookie=True, origin=True, ctype=True):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=20)
        h = {"Host": host or f"127.0.0.1:{self.port}"}
        if cookie:
            h["Cookie"] = self.cookie
        raw = None
        if body is not None:
            raw = body if isinstance(body, bytes) else json.dumps(body).encode()
            if ctype:
                h["Content-Type"] = "application/json"
            if origin:
                h["Origin"] = self.origin
        h.update(headers or {})
        conn.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
        for k, v in h.items():
            if v is not None:
                conn.putheader(k, v)
        if raw is not None:
            conn.putheader("Content-Length", str(len(raw)))
        conn.endheaders(raw)
        res = conn.getresponse()
        data = res.read()
        conn.close()
        return res.status, dict(res.getheaders()), data

    # --- binding and Host ----------------------------------------------------------------------------------------
    def test_binds_loopback_only(self):
        self.assertEqual(self.server.server_address[0], "127.0.0.1")

    def test_host_allowlist(self):
        for host in (f"evil.com:{self.port}", f"127.0.0.1.nip.io:{self.port}", f"localhost.evil.com:{self.port}",
                     f"127.0.0.1:{self.port + 1}", "127.0.0.1", f"[::1]:{self.port}", f"0.0.0.0:{self.port}"):
            with self.subTest(host=host):
                status, headers, _ = self.request("GET", "/api/state", host=host)
                self.assertEqual(status, 403)
        status, _, _ = self.request("GET", "/api/state", host=f"localhost:{self.port}")
        self.assertEqual(status, 200)
        status, _, _ = self.request("GET", "/api/state")
        self.assertEqual(status, 200)

    def test_missing_host_refused(self):
        status, _, _ = self.request("GET", "/api/state", headers={"Host": None})
        self.assertEqual(status, 403)

    def test_rebinding_host_refused_even_with_cookie_and_origin(self):
        status, _, _ = self.request("POST", "/api/math", {"tex": "x"}, host=f"attacker.example:{self.port}",
                                    headers={"Origin": f"http://attacker.example:{self.port}"})
        self.assertEqual(status, 403)

    # --- token ---------------------------------------------------------------------------------------------------
    def test_token_needed(self):
        for path in ("/", "/api/state", "/api/pages", "/preview/post:hello", "/_studio/studio.js"):
            with self.subTest(path=path):
                status, _, _ = self.request("GET", path, cookie=False)
                self.assertEqual(status, 401)

    def test_wrong_cookie_refused(self):
        status, _, _ = self.request("GET", "/api/state", cookie=False,
                                    headers={"Cookie": f"{self.server.cookie}=nope"})
        self.assertEqual(status, 401)
        status, _, _ = self.request("GET", "/api/state", cookie=False,
                                    headers={"Cookie": f"tessera_studio_1={self.server.token}"})
        self.assertEqual(status, 401)

    def test_token_swapped_for_strict_httponly_cookie(self):
        status, headers, _ = self.request("GET", f"/?token={self.server.token}", cookie=False)
        self.assertEqual(status, 303)
        self.assertEqual(headers["Location"], "/")
        c = headers["Set-Cookie"]
        self.assertIn(f"{self.server.cookie}={self.server.token}", c)
        self.assertIn("HttpOnly", c)
        self.assertIn("SameSite=Strict", c)
        self.assertNotIn("token", headers["Location"])

    def test_wrong_token_in_url(self):
        status, headers, _ = self.request("GET", "/?token=guess", cookie=False)
        self.assertEqual(status, 403)
        self.assertNotIn("Set-Cookie", headers)

    def test_cookie_name_carries_port(self):
        self.assertEqual(self.server.cookie, f"tessera_studio_{self.port}")

    # --- writes --------------------------------------------------------------------------------------------------
    def test_write_with_matching_origin(self):
        status, _, data = self.request("POST", "/api/math", {"tex": "x^2", "display": True})
        self.assertEqual(status, 200, data)

    def test_write_with_foreign_origin_refused(self):
        for origin in ("http://evil.com", "null", f"http://127.0.0.1:{self.port + 1}", f"https://127.0.0.1:{self.port}"):
            with self.subTest(origin=origin):
                status, _, _ = self.request("POST", "/api/math", {"tex": "x"}, headers={"Origin": origin})
                self.assertEqual(status, 403)

    def test_write_without_origin_needs_same_origin_fetch_site(self):
        status, _, _ = self.request("POST", "/api/math", {"tex": "x"}, origin=False)
        self.assertEqual(status, 403)
        status, _, _ = self.request("POST", "/api/math", {"tex": "x"}, origin=False,
                                    headers={"Sec-Fetch-Site": "cross-site"})
        self.assertEqual(status, 403)
        status, _, _ = self.request("POST", "/api/math", {"tex": "x"}, origin=False,
                                    headers={"Sec-Fetch-Site": "same-site"})
        self.assertEqual(status, 403)
        status, _, _ = self.request("POST", "/api/math", {"tex": "x"}, origin=False,
                                    headers={"Sec-Fetch-Site": "same-origin"})
        self.assertEqual(status, 200)

    def test_cross_site_fetch_metadata_refused_even_with_origin(self):
        status, _, _ = self.request("POST", "/api/math", {"tex": "x"}, headers={"Sec-Fetch-Site": "cross-site"})
        self.assertEqual(status, 403)

    def test_writes_must_be_json(self):
        for ctype in ("text/plain", "application/x-www-form-urlencoded", "multipart/form-data; boundary=x"):
            with self.subTest(ctype=ctype):
                status, _, _ = self.request("POST", "/api/math", b'{"tex": "x"}', headers={"Content-Type": ctype},
                                            ctype=False)
                self.assertEqual(status, 415)
        status, _, _ = self.request("POST", "/api/math", b"not json")
        self.assertEqual(status, 400)

    def test_write_without_cookie_refused(self):
        status, _, _ = self.request("POST", "/api/page/save", {"id": "post:hello", "meta": {}, "body": "x"},
                                    cookie=False)
        self.assertEqual(status, 401)
        self.assertIn("Hello there.", (self.root / "content/posts/hello.md").read_text())

    def test_other_methods_refused_without_cors(self):
        for method in ("PUT", "DELETE", "PATCH", "OPTIONS"):
            with self.subTest(method=method):
                status, headers, _ = self.request(method, "/api/page/save", headers={
                    "Origin": "http://evil.com", "Access-Control-Request-Method": "POST"})
                self.assertEqual(status, 405)
                self.assertFalse([k for k in headers if k.lower().startswith("access-control")])

    def test_no_cors_headers_anywhere(self):
        for method, path, body in (("GET", "/", None), ("GET", "/api/state", None), ("GET", "/api/pages", None),
                                   ("POST", "/api/math", {"tex": "x"}), ("GET", "/preview/post:hello", None),
                                   ("GET", "/_studio/studio.js", None)):
            with self.subTest(path=path):
                _, headers, _ = self.request(method, path, body, headers={"Origin": self.origin})
                self.assertFalse([k for k in headers if k.lower().startswith("access-control")], headers)

    def test_app_page_has_strict_csp_and_no_framing(self):
        status, headers, body = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
        self.assertEqual(headers["X-Frame-Options"], "DENY")
        self.assertIn(b'type="importmap"', body)

    def test_large_body_refused_before_reading(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=20)
        conn.putrequest("POST", "/api/math", skip_host=True)
        for k, v in (("Host", f"127.0.0.1:{self.port}"), ("Cookie", self.cookie), ("Origin", self.origin),
                     ("Content-Type", "application/json"), ("Content-Length", str(50 * 1024 * 1024))):
            conn.putheader(k, v)
        conn.endheaders()
        res = conn.getresponse()
        self.assertEqual(res.status, 413)
        conn.close()

    # --- paths ---------------------------------------------------------------------------------------------------
    def test_page_ids_cannot_traverse(self):
        for pid in ("post:../../site", "post:..%2F..%2Fsite", "post:/etc/passwd", "../x", "post:a/b", "nope:hello",
                    "post:", "post:.hidden"):
            with self.subTest(pid=pid):
                status, _, _ = self.request("POST", "/api/page/save", {"id": pid, "meta": {"title": "x"}, "body": "x"})
                self.assertIn(status, (400, 403, 404))
        self.assertEqual(self.outside.read_text(), "secret")

    def test_code_reads_confined(self):
        for name in ("../site", "..%2Fsite", "/etc/passwd", "a.b"):
            with self.subTest(name=name):
                status, _, _ = self.request("GET", f"/api/code?kind=figure&name={name}")
                self.assertIn(status, (400, 403, 404))

    def test_static_routes_do_not_escape(self):
        (self.root / "static").mkdir(exist_ok=True)
        for path in ("/_studio/../server.py", "/_studio/%2e%2e/server.py", "/assets/../../studio/server.py",
                     "/assets/%2e%2e/%2e%2e/studio/server.py", "/static/../site.yml", "/static/%2e%2e/site.yml",
                     "/figures/../site.yml", "/figures/_os.py", "/data/../site.yml"):
            with self.subTest(path=path):
                status, _, body = self.request("GET", path)
                self.assertIn(status, (400, 403, 404))
                self.assertNotIn(b"example.org", body)

    def test_upload_limits_and_types(self):
        big = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"0" * (security.UPLOAD_LIMIT + 10)).decode()
        status, _, _ = self.request("POST", "/api/upload", {"name": "big.png", "data": big})
        self.assertEqual(status, 413)
        for name, blob in (("fake.png", b"hello, not an image"), ("x.svg", b"<svg onload=alert(1)></svg>"),
                           ("x.html", b"<!doctype html><script>1</script>")):
            with self.subTest(name=name):
                status, _, _ = self.request("POST", "/api/upload",
                                            {"name": name, "data": base64.b64encode(blob).decode()})
                self.assertEqual(status, 415)
        status, _, data = self.request("POST", "/api/upload", {"name": "../../evil.png", "data": base64.b64encode(PNG).decode(),
                                                               "slug": "hello"})
        self.assertEqual(status, 200, data)
        path = json.loads(data)["path"]
        self.assertTrue(path.startswith("static/uploads/"))
        self.assertTrue((self.root / path).is_file())
        self.assertNotIn("..", path)


class Paths(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="studio-paths-"))
        self.root = self.tmp / "site"
        make_site(self.root)
        (self.tmp / "outside").mkdir()
        (self.tmp / "outside" / "x.md").write_text("outside", encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_allowed_places(self):
        for rel in ("content/posts/a.md", "figures/f.py", "drawings/d.py", "static/uploads/a.png",
                    "content/references.yml", "content/topics.yml"):
            with self.subTest(rel=rel):
                self.assertTrue(str(confine(self.root, rel)).startswith(str(self.root.resolve())))

    def test_refused_places(self):
        for rel in ("site.yml", "../outside/x.md", "content/../site.yml", "/etc/passwd", "static/avatar.png",
                    "tessera/studio/server.py", ".git/config", "content", "static/uploads", "wiki/log.md", ""):
            with self.subTest(rel=rel):
                with self.assertRaises(Refused):
                    confine(self.root, rel)

    def test_symlink_escape_refused(self):
        link = self.root / "content" / "posts" / "link.md"
        os.symlink(self.tmp / "outside" / "x.md", link)
        with self.assertRaises(Refused):
            confine(self.root, "content/posts/link.md")
        os.symlink(self.tmp / "outside", self.root / "content" / "evil")
        with self.assertRaises(Refused):
            confine(self.root, "content/evil/x.md")
        os.symlink(self.tmp / "outside", self.root / "figures")
        with self.assertRaises(Refused):
            confine(self.root, "figures/x.py")

    def test_symlinked_page_is_not_written(self):
        from tessera.studio.api import Studio
        link = self.root / "content" / "posts" / "link.md"
        os.symlink(self.tmp / "outside" / "x.md", link)
        studio = Studio(self.root)
        with self.assertRaises(Refused):
            studio.save_page({"id": "post:link", "meta": {"title": "x"}, "body": "pwned"})
        self.assertEqual((self.tmp / "outside" / "x.md").read_text(), "outside")


class DraftGate(unittest.TestCase):
    """Model-written figure code runs automatically only when it is plain computation."""

    def test_plain_figure_passes(self):
        from tessera.studio.api import draft_gate
        src = "import math\nfrom numpy import linspace\nTITLE='x'\nCAPTION=''\nCONTROLS=[]\n" \
              "def compute(_narrow=0):\n    return {'panels': [{'kind': 'xy', 'series': [{'y': [math.sin(1)]}]}]}\n"
        self.assertEqual(draft_gate(src), [])

    def test_escapes_are_caught(self):
        from tessera.studio.api import draft_gate
        for src in ("import os", "import subprocess as s", "from pathlib import Path", "open('x')",
                    "__import__('os')", "eval('1')", "().__class__.__bases__", "import socket",
                    "from . import x", "exec('x')", "import urllib.request"):
            with self.subTest(src=src):
                self.assertTrue(draft_gate(src))


class AtomicWrite(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="studio-atomic-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_writes_and_leaves_no_temp_files(self):
        p = self.tmp / "a.md"
        atomic_write(p, "one")
        atomic_write(p, "two")
        self.assertEqual(p.read_text(), "two")
        self.assertEqual(sorted(x.name for x in self.tmp.iterdir()), ["a.md"])

    def test_failure_keeps_the_old_file(self):
        p = self.tmp / "a.md"
        p.write_text("original", encoding="utf-8")
        with mock.patch("tessera.studio.security.os.replace", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                atomic_write(p, "new text")
        self.assertEqual(p.read_text(), "original")
        self.assertEqual(sorted(x.name for x in self.tmp.iterdir()), ["a.md"])

    def test_bytes(self):
        p = self.tmp / "img.png"
        atomic_write(p, PNG)
        self.assertEqual(p.read_bytes(), PNG)

    def test_image_sniffing(self):
        self.assertEqual(security.image_type(PNG), "png")
        self.assertEqual(security.image_type(b"\xff\xd8\xff\xe0rest"), "jpg")
        self.assertEqual(security.image_type(b"GIF89a..."), "gif")
        self.assertEqual(security.image_type(b"RIFF\x00\x00\x00\x00WEBPVP8 "), "webp")
        self.assertIsNone(security.image_type(b"<svg></svg>"))
        self.assertIsNone(security.image_type(b"RIFF\x00\x00\x00\x00WAVE"))


if __name__ == "__main__":
    unittest.main()
