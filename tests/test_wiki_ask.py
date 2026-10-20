import importlib.util
import json
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_wiki_fixtures import make_site  # noqa: E402

from tessera import ask_server, wiki  # noqa: E402

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


if __name__ == "__main__":
    unittest.main()
