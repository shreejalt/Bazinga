import json
import unittest

from bazinga.graph import build_graph, series_slug
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_wiki_fixtures import make_site  # noqa: E402
import os as _os
import sys as _sys

_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from perf_support import PERF, perf_only  # noqa: E402,F401


class GraphTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg, cls.pages, cls.rendered, cls.site, cls.g = make_site()

    def edges(self, type_):
        return {(e["source"], e["target"]) for e in self.g.edges if e["type"] == type_}

    def test_drafts_are_not_nodes(self):
        self.assertNotIn("post:draft", self.g.nodes)
        self.assertEqual(len(self.g.nodes), 6)

    def test_edge_types(self):
        self.assertIn(("post:attention", "post:qkv"), self.edges("builds_on"))
        self.assertIn(("post:vit", "post:attention"), self.edges("builds_on"))
        self.assertIn(("post:softmax", "post:attention"), self.edges("mentions"))
        # attention mentions qkv too, but that pair is already a builds_on edge
        self.assertNotIn(("post:attention", "post:qkv"), self.edges("mentions"))
        self.assertIn(("post:attention", "post:qkv"), self.edges("cites"))       # both cite VASW17
        self.assertIn(("post:qkv", "post:vit"), self.edges("series"))
        topic = self.edges("topic")
        self.assertTrue(("post:attention", "post:vit") in topic or ("post:vit", "post:attention") in topic)
        for e in self.g.edges:
            self.assertNotEqual(e["source"], e["target"])

    def test_backlinks_builds_on_read_next(self):
        self.assertEqual(self.g.backlinks("post:attention"), ["post:vit", "post:softmax"])   # newest first
        self.assertEqual(self.g.builds_on("post:vit"), ["post:attention"])
        self.assertEqual(self.g.read_next("post:attention"), ["post:vit"])
        self.assertEqual(self.g.backlinks("project:robot"), [])

    def test_related(self):
        rel = self.g.related("post:attention")
        self.assertNotIn("post:attention", rel)
        self.assertNotIn("post:qkv", rel)          # already shown as "builds on"
        self.assertNotIn("post:vit", rel)          # already shown as "read next"
        self.assertEqual(rel[0], "post:softmax")
        self.assertEqual(self.g.related("project:robot"), [])

    def test_series_and_topics(self):
        self.assertEqual(self.g.series(), {"Transformers": ["post:qkv", "post:vit"]})
        self.assertEqual(self.g.topic_pages("attention"), ["post:attention", "post:softmax", "post:qkv"])
        self.assertEqual(series_slug("Transformers in Vision!"), "transformers-in-vision")

    def test_rings(self):
        r = self.g.rings("post:attention")
        self.assertEqual(r["post:attention"], 0)
        self.assertEqual(r["post:qkv"], 1)
        self.assertEqual(r["post:vit"], 1)
        self.assertNotIn("project:robot", r)
        self.assertNotIn("post:mamba", r)
        self.assertEqual(self.g.rings("project:robot"), {"project:robot": 0})

    def test_layout_deterministic_and_in_unit_square(self):
        a = self.g.layout()
        _, pages, rendered, site, _ = make_site()
        b = build_graph(pages, rendered, site).layout()
        self.assertEqual(a, b)
        for x, y in a.values():
            self.assertTrue(0 <= x <= 1 and 0 <= y <= 1)
        pts = list(a.values())
        for i, p in enumerate(pts):
            for q in pts[i + 1:]:
                self.assertGreater(((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2) ** 0.5, 0.05)

    def test_layout_scales(self):
        import time
        from types import SimpleNamespace
        import datetime as dt
        pages, rendered = [], {}
        topics = [f"t{i}" for i in range(12)]
        for i in range(400):
            pid = f"post:p{i}"
            pages.append(SimpleNamespace(id=pid, title=f"P {i}", url=f"/posts/p{i}/", kind="posts", summary="",
                                         topics=[topics[i % 12], topics[(i * 7) % 12]], date=dt.date(2026, 1, 1) + dt.timedelta(days=i),
                                         series=None, builds_on=[f"post:p{i - 1}"] if i % 5 else [], cites=[]))
            rendered[pid] = SimpleNamespace(mentions=[], cites=[], figures=[])
        t = time.perf_counter()
        g = build_graph(pages, rendered, SimpleNamespace(topics={}))
        pos = g.layout()
        if PERF:
            self.assertLess(time.perf_counter() - t, 20)
        self.assertEqual(len(pos), 400)

    def test_to_json(self):
        j = self.g.to_json()
        s = json.dumps(j)
        self.assertEqual(s, json.dumps(make_site()[4].to_json()))
        node = next(n for n in j["nodes"] if n["id"] == "post:attention")
        for k in ("id", "title", "url", "kind", "summary", "topics", "x", "y", "degree", "date"):
            self.assertIn(k, node)
        self.assertEqual(j["rings"]["post:attention"][0], ["post:qkv", "post:softmax", "post:vit"])
        self.assertIn("attention", j["topics"])
        self.assertNotIn("post:draft", s)


if __name__ == "__main__":
    unittest.main()
