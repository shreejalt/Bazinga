import importlib.util
import json
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_wiki_fixtures import make_site  # noqa: E402

from bazinga import ask_server, wiki  # noqa: E402

ENV = {"LLM_API_KEY": "k-test", "LLM_MODEL": "m/one", "ASK_PER_VISITOR": "2", "ASK_DAILY_CAP": "3"}


class AskServerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _, pages, rendered, _, g = make_site()
        cls.data = {"passages": wiki.passages(pages, rendered), "graph": g.to_json()}

    def setUp(self):
        ask_server.reset_limits()
        self.prompts = []

    def chat(self, cfg, system, user, **kw):
        self.prompts.append((cfg, system, user))
        return "The score is divided by the square root of the key dimension [2]."

    def post(self, body, ip="1.1.1.1", env=ENV):
        raw = body if isinstance(body, bytes) else json.dumps(body).encode()
        return ask_server.handle("POST", raw, ip, env, lambda: self.data, chat=self.chat)

    def test_off_without_key(self):
        self.assertEqual(ask_server.handle("GET", b"", "ip", {}, lambda: self.data), (200, {"on": False}))
        status, body = ask_server.handle("POST", b'{"q": "hello there"}', "ip", {"LLM_MODEL": "x"}, lambda: self.data)
        self.assertEqual(status, 503)
        self.assertFalse(body["on"])

    def test_get_on(self):
        self.assertEqual(ask_server.handle("GET", b"", "ip", ENV, None), (200, {"on": True, "limit": 2, "left": 2}))

    def test_answer_with_sources(self):
        status, body = self.post({"q": "why divide by the square root of the key dimension", "page": "post:attention"})
        self.assertEqual(status, 200)
        self.assertIn("[2]", body["answer"])
        self.assertEqual([s["n"] for s in body["sources"]], [2])
        self.assertEqual(set(body["sources"][0]), {"n", "title", "url", "section", "anchor"})
        self.assertEqual(body["left"], 1)
        cfg, system, user = self.prompts[0]
        self.assertIn("ONLY", system)
        self.assertIn("[1]", user)
        self.assertEqual(cfg["_key"], "k-test")
        self.assertEqual(cfg["llm"]["model"], "m/one")

    def test_limits_per_ip_and_daily_cap(self):
        q = {"q": "square root of the key dimension"}
        self.assertEqual(self.post(q)[0], 200)
        self.assertEqual(self.post(q)[0], 200)
        status, body = self.post(q)
        self.assertEqual(status, 429)
        self.assertEqual(body["left"], 0)
        self.assertEqual(self.post(q, ip="2.2.2.2")[0], 200)          # cap is 3
        self.assertEqual(self.post(q, ip="3.3.3.3")[0], 429)

    def test_bad_requests(self):
        self.assertEqual(self.post(b"not json")[0], 400)
        self.assertEqual(self.post({"q": "hi"})[0], 400)
        self.assertEqual(self.post({"q": "x" * 1000})[0], 400)
        self.assertEqual(ask_server.handle("PUT", b"", "ip", ENV, None)[0], 405)
        self.assertEqual(self.prompts, [])

    def test_no_match_does_not_call_model_or_count(self):
        status, body = self.post({"q": "zebra quokka giraffe"})
        self.assertEqual(status, 200)
        self.assertEqual(body["sources"], [])
        self.assertEqual(self.prompts, [])
        self.assertEqual(body["left"], 2)

    def test_model_failure_refunds(self):
        def boom(*a, **k):
            raise RuntimeError("down")
        status, body = ask_server.handle("POST", b'{"q": "square root of the key"}', "ip", ENV, lambda: self.data, chat=boom)
        self.assertEqual(status, 502)
        self.assertEqual(body["left"], 2)

    def test_site_yml_defaults(self):
        cfg = {"ask": {"per_visitor": 9, "daily_cap": 50}, "llm": {"model": "x/y", "key_env": "MY_KEY"}}
        s = ask_server.settings({"MY_KEY": "k"}, cfg)
        self.assertEqual((s["on"], s["per_visitor"], s["daily_cap"], s["model"]), (True, 9, 50, "x/y"))
        s = ask_server.settings({"MY_KEY": "k"}, {"ask": {"written_answers": False}, "llm": {"model": "x", "key_env": "MY_KEY"}})
        self.assertFalse(s["on"])


class VercelFunctionTest(unittest.TestCase):
    def test_import(self):
        path = Path(__file__).resolve().parent.parent / "api" / "ask.py"
        spec = importlib.util.spec_from_file_location("api_ask", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        from http.server import BaseHTTPRequestHandler
        self.assertTrue(issubclass(mod.handler, BaseHTTPRequestHandler))
        self.assertTrue(hasattr(mod.handler, "do_GET") and hasattr(mod.handler, "do_POST"))


class VercelFunctionOverHttp(unittest.TestCase):
    """api/ask.py driven over HTTP (B1): the data address never comes from the request, links stay on the site,
    the cache is per address, and the body length must be a plain number."""

    def setUp(self):
        import shutil
        import tempfile
        import threading
        from http.server import ThreadingHTTPServer
        from unittest import mock
        path = Path(__file__).resolve().parent.parent / "api" / "ask.py"
        spec = importlib.util.spec_from_file_location("api_ask_http", path)
        self.mod = mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.tmp = Path(tempfile.mkdtemp(prefix="ask-fn-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        mod.ROOT = self.tmp                       # no local _site/data: the function must fetch
        mod._cache["cfg"] = {"site": {"origin": "https://example.com"}}
        self.fetched = []
        good = {"id": "read:a", "title": "A", "url": "/reads/a/", "section": "s", "anchor": "s",
                "text": "softmax temperature attention softmax temperature"}
        full = dict(good, id="read:b", url="https://site.test/reads/b/")
        evil = [dict(good, id="read:x", url="javascript:alert(document.domain)"),
                dict(good, id="read:y", url="//evil.example/x"), dict(good, id="read:z", url="https://evil.example/")]
        self.evil = evil

        def fake_fetch(url):
            self.fetched.append(url)
            return [good, full] + evil if url.endswith("passages.json") else {}
        mod._fetch = fake_fetch
        env = mock.patch.dict(os.environ, {"LLM_API_KEY": "k", "LLM_MODEL": "m/x"}, clear=False)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("SITE_URL", None)
        ask_server.reset_limits()
        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), mod.handler)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.addCleanup(self.srv.server_close)
        self.addCleanup(self.srv.shutdown)

    def post(self, body, headers=None, raw=None):
        import http.client
        c = http.client.HTTPConnection("127.0.0.1", self.srv.server_address[1], timeout=10)
        data = raw if raw is not None else json.dumps(body).encode()
        h = {"Content-Type": "application/json", "Content-Length": str(len(data))}
        h.update(headers or {})
        c.putrequest("POST", "/api/ask/", skip_host="Host" in h)
        for k, v in h.items():
            c.putheader(k, v)
        c.endheaders(data)
        r = c.getresponse()
        out = r.status, json.loads(r.read() or b"{}")
        c.close()
        return out

    def test_host_is_never_the_data_address(self):
        status, out = self.post({"q": "softmax temperature"}, {"Host": "attacker.example",
                                                                "X-Forwarded-Host": "attacker.example"})
        self.assertEqual(status, 503)
        self.assertIn("SITE_URL", out["error"])
        self.assertEqual(self.fetched, [])

    def test_site_address_and_links_on_the_site_only(self):
        from unittest import mock
        os.environ["SITE_URL"] = "https://site.test/"
        self.addCleanup(os.environ.pop, "SITE_URL", None)
        loaded = self.mod._loader(self.mod._base())()
        self.assertEqual(self.fetched[0], "https://site.test/data/passages.json")
        self.assertEqual([p["url"] for p in loaded["passages"]], ["/reads/a/", "https://site.test/reads/b/"])
        with mock.patch.object(ask_server, "handle", return_value=(200, {"ok": True})) as h:
            self.post({"q": "x"}, {"Host": "attacker.example"})
        self.assertEqual(h.call_args[0][4]()["passages"], loaded["passages"])
        # the cache is kept per site address
        self.assertIn("https://site.test", self.mod._cache["data"])
        self.assertNotIn("https://attacker.example", self.mod._cache["data"])

    def test_body_length_must_be_a_number(self):
        for length in ("-1", "abc", "1e3"):
            with self.subTest(length=length):
                status, _ = self.post(None, {"Content-Length": length}, raw=b"{}")
                self.assertEqual(status, 411)

    def test_ask_js_keeps_links_on_the_site(self):
        import shutil
        import subprocess
        node = shutil.which("node")
        if not node:
            self.skipTest("node is not installed")
        js = (Path(__file__).resolve().parent.parent / "bazinga/theme/assets/js/ask.js").read_text(encoding="utf-8")
        line = next(x for x in js.splitlines() if x.strip().startswith("const siteURL ="))
        for use in ("passages: onSite(passages)", "onSite((res && res.passages)", "const src = onSite(r.sources)"):
            self.assertIn(use, js)
        prog = ("const location = {origin: 'https://site.test'};" + line +
                "console.log(JSON.stringify(['/a/', 'https://site.test/b/', 'javascript:alert(1)', '//evil/x',"
                "'https://evil.example/', 'https://site.test.evil/x', ' javascript:x'].map(siteURL)));")
        out = subprocess.run([node, "-e", prog], capture_output=True, text=True, check=True).stdout
        self.assertEqual(json.loads(out), ["/a/", "https://site.test/b/", None, None, None, None, None])


if __name__ == "__main__":
    unittest.main()
