import json
import os
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_wiki_fixtures import make_site, make_state  # noqa: E402

from tessera import llm  # noqa: E402


class FakeAPI:
    """A tiny OpenAI-compatible server. ``replies`` maps model -> list of (status, content) consumed in order."""

    def __init__(self):
        self.calls = []
        self.replies = {}
        api = self

        class H(BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["content-length"])))
                api.calls.append({"path": self.path, "auth": self.headers.get("authorization"), "body": body})
                queue = api.replies.get(body["model"]) or [(200, "")]
                status, content = queue.pop(0) if len(queue) > 1 else queue[0]
                out = json.dumps({"choices": [{"message": {"role": "assistant", "content": content}}]}).encode()
                self.send_response(status)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(out)))
                self.end_headers()
                self.wfile.write(out)

            def log_message(self, *a):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/v1"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


class LLMTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.api = FakeAPI()

    @classmethod
    def tearDownClass(cls):
        cls.api.close()

    def setUp(self):
        self.api.calls.clear()
        self.api.replies.clear()
        self.site = make_site()
        self.cfg = self.site[0]
        self.cfg["llm"]["base_url"] = self.api.url
        os.environ["TESSERA_TEST_KEY"] = "test-key-not-real"
        self.state = make_state(*self.site)

    def tearDown(self):
        os.environ.pop("TESSERA_TEST_KEY", None)

    def test_configured_and_key_from_env_file(self):
        self.assertTrue(llm.configured(self.cfg))
        os.environ.pop("TESSERA_TEST_KEY")
        self.assertTrue(llm.configured(self.cfg))            # a local endpoint needs no key
        self.cfg["llm"]["base_url"] = "https://api.example.com/v1"
        self.assertFalse(llm.configured(self.cfg))
        (self.cfg.root / ".env.local").write_text("# local\nexport TESSERA_TEST_KEY='from-file'\n")
        self.assertEqual(llm.api_key(self.cfg), "from-file")
        self.assertEqual(llm.models(self.cfg), ["a/one", "b/two"])

    def test_fallback_to_next_model(self):
        self.api.replies = {"a/one": [(500, "")], "b/two": [(200, "hello")]}
        self.assertEqual(llm.chat(self.cfg, "s", "u"), "hello")
        self.assertEqual([c["body"]["model"] for c in self.api.calls], ["a/one", "b/two"])
        self.assertEqual(self.api.calls[0]["path"], "/v1/chat/completions")
        self.assertEqual(self.api.calls[0]["auth"], "Bearer test-key-not-real")

    def test_empty_reply_falls_back_and_all_fail(self):
        self.api.replies = {"a/one": [(200, "")], "b/two": [(429, "")]}
        with self.assertRaises(llm.LLMError) as ctx:
            llm.chat(self.cfg, "s", "u")
        self.assertNotIn("test-key", str(ctx.exception))

    def test_json_mode_retries_without_response_format(self):
        self.api.replies = {"a/one": [(400, ""), (200, '{"ok": 1}')]}
        self.assertEqual(llm.chat_json(self.cfg, "s", "u"), {"ok": 1})
        self.assertIn("response_format", self.api.calls[0]["body"])
        self.assertNotIn("response_format", self.api.calls[1]["body"])

    def test_parse_json_fences(self):
        self.assertEqual(llm.parse_json('```json\n{"a": [1, 2]}\n```'), {"a": [1, 2]})
        self.assertEqual(llm.parse_json('Sure! Here it is: {"a": 1} hope it helps'), {"a": 1})
        self.assertEqual(llm.parse_json('```\n["x"]\n```'), ["x"])
        with self.assertRaises(llm.LLMError):
            llm.parse_json("no json here")

    def test_ingest_validation_drops_unknown(self):
        reply = {
            "topics": ["attention", "made-up", "vision"],
            "builds_on": ["post:qkv", "post:nope", "post:vit"],
            "links": [
                {"target": "post:softmax", "sentence": "The weights then mix the values.", "anchor_text": "weights"},
                {"target": "post:ghost", "sentence": "The weights then mix the values.", "anchor_text": "weights"},
                {"target": "post:vit", "sentence": "An invented sentence.", "anchor_text": "invented"},
                {"target": "post:qkv", "sentence": "Attention lets every token look at every other token.", "anchor_text": "token"},
            ],
            "summary": "How tokens attend.", "description": "x" * 200,
            "questions": ["Why divide by the root?", "", "What is a head?", "q4"],
            "series": {"name": "Transformers", "part": "3"},
        }
        self.api.replies = {"a/one": [(200, "```json\n" + json.dumps(reply) + "\n```")]}
        out = llm.ingest(self.cfg, "post:attention", state=self.state)
        self.assertEqual(out["topics"], ["attention", "vision"])
        self.assertEqual(out["builds_on"], ["post:qkv", "post:vit"])
        self.assertEqual([l["target"] for l in out["links"]], ["post:softmax"])
        self.assertEqual(out["links"][0]["replace_with"], "The [[post:softmax|weights]] then mix the values.")
        self.assertLessEqual(len(out["description"]), 155)
        self.assertEqual(out["questions"], ["Why divide by the root?", "What is a head?", "q4"])
        self.assertEqual(out["series"], {"name": "Transformers", "part": 3})
        self.assertTrue(any("made-up" in d for d in out["dropped"]))
        self.assertTrue(any("already linked" in d for d in out["dropped"]))
        root = self.cfg.root
        self.assertTrue((root / "proposals" / "ingest-attention.md").exists())
        self.assertTrue((root / "proposals" / "ingest-attention.json").exists())
        self.assertIn("] ingest | Attention, Step by Step", (root / "wiki" / "log.md").read_text())
        # content untouched
        self.assertNotIn("post:softmax", (root / "content" / "posts" / "attention.md").read_text())

    def test_highlights_drop_invented_numbers(self):
        keep, drop = llm.check_highlights(
            ["A 224 pixel image gives 196 tokens.", "Patches are 32 pixels wide.", "Accuracy is 88.5%.", "Plain line."],
            "A 224 pixel image cut into 16 by 16 patches gives 196 tokens.")
        self.assertEqual(keep, ["A 224 pixel image gives 196 tokens.", "Plain line."])
        self.assertEqual(len(drop), 2)
        self.api.replies = {"a/one": [(200, json.dumps({"highlights": ["Three learned matrices.", "Uses 12 heads."]}))]}
        out = llm.highlights(self.cfg, "transformers", state=self.state)
        self.assertEqual(out["series"], "Transformers")
        self.assertEqual([p["id"] for p in out["parts"]], ["post:qkv", "post:vit"])
        for p in out["parts"]:
            self.assertNotIn("Uses 12 heads.", p["highlights"])
        self.assertTrue((self.cfg.root / "proposals" / "highlights-transformers.yml").exists())

    def test_describe_own_words_and_length(self):
        self.api.replies = {"a/one": [(200, "Revolutionary synergy unlocks paradigm-shifting outcomes for enterprises.")]}
        d = llm.describe(self.cfg, "post:vit", state=self.state)
        self.assertEqual(d, "Cut an image into 16 by 16 patches and treat them as tokens.")
        self.api.replies = {"a/one": [(200, "A 224 pixel image cut into 16 by 16 patches gives 196 tokens, each patch flattened and projected. " * 3)]}
        d = llm.describe(self.cfg, "post:vit", state=self.state)
        self.assertLessEqual(len(d), 155)

    def test_equation_strips_fences(self):
        self.assertEqual(llm.clean_latex("```latex\n$$a^2+b^2=c^2$$\n```"), "a^2+b^2=c^2")
        self.assertEqual(llm.clean_latex("\\[x\\]"), "x")

    def test_lint_rules(self):
        out = llm.lint(self.cfg, use_model=False, state=self.state)
        r = out["rules"]
        self.assertIn("project:robot", r["orphans"])
        self.assertIn("post:mamba", r["orphans"])
        self.assertNotIn("post:attention", r["orphans"])
        self.assertIn("robotics", r["thin_topics"])
        self.assertIn("post:qkv", r["pages_without_figures"])
        self.assertNotIn("post:attention", r["pages_without_figures"])
        self.assertIn({"from": "post:softmax", "to": "post:attention"}, r["one_way_links"])
        self.assertEqual(r["broken_links"], [])
        self.assertTrue(out["proposal"].endswith("lint-site.md"))

    def test_figure_source_check(self):
        good = "TITLE='t'\nCAPTION='c'\nCONTROLS=[]\nimport math\ndef compute(_narrow=0):\n    return {}\n"
        self.assertEqual(llm.check_figure_source(good), [])
        bad = "import numpy\nTITLE='t'\ndef f(): pass\n"
        probs = llm.check_figure_source(bad)
        self.assertTrue(any("CAPTION" in p for p in probs))
        self.assertTrue(any("compute" in p for p in probs))
        self.assertTrue(any("numpy" in p for p in probs))

    def test_cli_without_model(self):
        os.environ.pop("TESSERA_TEST_KEY")
        self.cfg["llm"]["base_url"] = "https://api.example.com/v1"
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = llm.cli(["describe", "post:vit"], cfg=self.cfg)
        self.assertEqual(code, 1)
        self.assertIn("No model configured", buf.getvalue())
        with redirect_stdout(io.StringIO()):
            self.assertEqual(llm.cli(["--help"], cfg=self.cfg), 0)


if __name__ == "__main__":
    unittest.main()
