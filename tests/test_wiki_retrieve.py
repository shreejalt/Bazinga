import os
import random
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_wiki_fixtures import make_site  # noqa: E402

from bazinga import retrieve, wiki  # noqa: E402


class TokenizerTest(unittest.TestCase):
    def test_tokens(self):
        self.assertEqual(retrieve.tokenize("What are the Queries and keys?"), ["query", "key"])
        self.assertEqual(retrieve.tokenize("Café naïve"), ["cafe", "naiv"])
        self.assertEqual(retrieve.stem("running"), "run")
        for group in (("divide", "divides", "divided", "dividing"), ("update", "updates", "updated"), ("query", "queries")):
            self.assertEqual(len({retrieve.stem(w) for w in group}), 1, group)
        self.assertIn("16", retrieve.tokenize("16 by 16 patches"))

    def test_sentences(self):
        self.assertEqual(retrieve.sentences("One. Two is here! Three?"), ["One.", "Two is here!", "Three?"])
        self.assertEqual(len(retrieve.sentences("We use e.g. this. Next one.")), 2)


class RankingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg, pages, rendered, site, g = make_site()
        cls.ps = wiki.passages(pages, rendered)
        cls.graph = g.to_json()

    def top(self, q, **kw):
        return retrieve.answer(q, self.ps, self.graph, **kw)

    def test_expected_top_hits(self):
        r = self.top("why divide by the square root of the key dimension")
        self.assertEqual((r["passages"][0]["id"], r["passages"][0]["anchor"]), ("post:attention", "scaled"))
        self.assertIn("square root", r["answer"])
        r = self.top("how many tokens does a 224 pixel image give")
        self.assertEqual(r["passages"][0]["anchor"], "patches-as-tokens")
        self.assertIn("196 tokens", r["answer"])
        r = self.top("selective scan linear time")
        self.assertEqual(r["passages"][0]["id"], "post:mamba")
        self.assertEqual(r["pages"][0], {"id": "post:mamba", "title": "Mamba and Selective Scan", "url": "/posts/mamba/"})
        self.assertEqual(r["count"], len(self.ps))

    def test_no_match(self):
        r = self.top("zebra quokka")
        self.assertEqual((r["answer"], r["passages"], r["pages"]), ("", [], []))
        r = self.top("the and of")
        self.assertEqual(r["passages"], [])

    def test_page_boost(self):
        q = "token"
        plain = self.top(q)
        boosted = self.top(q, page="post:mamba")
        self.assertEqual(boosted["passages"][0]["id"], "post:mamba")
        self.assertNotEqual(plain["passages"][0]["id"], "post:mamba")

    def test_neighbour_boost(self):
        ids = retrieve.neighbours(self.graph, "post:attention")
        self.assertEqual(ids, {"post:qkv", "post:vit", "post:softmax"})

    def test_answer_deduplicated_and_short(self):
        r = self.top("softmax weights")
        sents = retrieve.sentences(r["answer"])
        self.assertLessEqual(len(sents), 3)
        self.assertEqual(len(sents), len(set(sents)))

    def test_cached_load(self):
        retrieve.load(self.ps, self.graph)
        r = retrieve.answer("selective scan", None, None, page=None)
        self.assertEqual(r["passages"][0]["id"], "post:mamba")

    def test_speed_2000_passages(self):
        rnd = random.Random(1)
        words = ("attention token query key value softmax image patch scan state model layer head embedding "
                 "position linear time sequence vision transformer weight score matrix depth width camera").split()
        big = []
        for i in range(2000):
            text = " ".join(rnd.choice(words) for _ in range(140)) + "."
            big.append({"id": f"post:p{i % 200}", "title": f"Page {i % 200}", "url": f"/posts/p{i % 200}/",
                        "section": rnd.choice(words), "anchor": f"s{i}", "text": text})
        retrieve.answer("warm up", big)              # builds the index once
        t = time.perf_counter()
        for q in ("why scale the attention score", "patch embedding position", "state scan linear time"):
            r = retrieve.answer(q, big, None, page="post:p3")
            self.assertTrue(r["passages"])
        per = (time.perf_counter() - t) / 3 * 1000
        self.assertLess(per, 50, f"{per:.1f} ms per question")


if __name__ == "__main__":
    unittest.main()
