import datetime as dt
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_wiki_fixtures import make_site  # noqa: E402

from bazinga import wiki  # noqa: E402


class PassagesTest(unittest.TestCase):
    def test_split_at_sentences(self):
        text = " ".join(f"Sentence number {i} says something useful about attention." for i in range(60))
        chunks = wiki.split_text(text)
        self.assertGreater(len(chunks), 1)
        for c in chunks:
            self.assertLessEqual(len(c), wiki.MAX_PASSAGE)
            self.assertTrue(c.endswith("."))
        self.assertEqual(" ".join(chunks), text)

    def test_split_one_huge_sentence(self):
        text = "word " * 600
        chunks = wiki.split_text(text)
        self.assertTrue(all(len(c) <= wiki.MAX_PASSAGE for c in chunks))
        self.assertEqual(" ".join(chunks).split(), text.split())

    def test_passages_per_section(self):
        cfg, pages, rendered, site, g = make_site()
        ps = wiki.passages(pages, rendered)
        att = [p for p in ps if p["id"] == "post:attention"]
        self.assertEqual([p["anchor"] for p in att], ["", "scaled", "many-heads"])
        self.assertEqual(att[1]["section"], "Scaled dot product")
        self.assertTrue(att[0]["text"].startswith("How a token looks"))     # summary leads the intro
        self.assertEqual(set(ps[0]), {"id", "title", "url", "section", "anchor", "text"})
        self.assertFalse(any(p["id"] == "post:draft" for p in ps))


class SiteFilesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg, cls.pages, cls.rendered, cls.site, cls.g = make_site()
        cls.out = Path(tempfile.mkdtemp()) / "_site"
        wiki.write_site_files(cls.cfg, cls.pages, cls.rendered, cls.g, cls.out)

    def test_llms_txt_layout(self):
        text = (self.out / "llms.txt").read_text()
        lines = text.splitlines()
        self.assertEqual(lines[0], "# Fixture")
        self.assertEqual(lines[2], "> Notes on attention and other things.")
        h2 = [l for l in lines if l.startswith("## ")]
        self.assertEqual(h2, ["## Writing", "## Projects", "## Optional"])
        self.assertFalse(any(l.startswith("#") and not l.startswith(("# ", "## ")) for l in lines))
        items = [l for l in lines if l.startswith("- ")]
        for l in items:
            self.assertRegex(l, r"^- \[[^\]]+\]\(https?://[^)]+\)(: .+)?$")
        self.assertIn("- [Attention, Step by Step](https://ex.org/posts/attention/index.md): How a token", text)
        opt = text.split("## Optional")[1]
        self.assertIn("/series/transformers/", opt)
        self.assertIn("/topics/attention/", opt)
        self.assertNotIn("Unfinished", text)

    def test_markdown_copies(self):
        md = (self.out / "posts" / "attention" / "index.md").read_text()
        self.assertTrue(md.startswith("# Attention, Step by Step\n\n> How a token"))
        self.assertIn("[Queries, Keys and Values](https://ex.org/posts/qkv/)", md)
        self.assertNotIn("[[", md)
        self.assertNotIn("{#scaled}", md)
        self.assertIn("Interactive figure", md)
        self.assertIn("## References", md)
        self.assertIn("https://arxiv.org/abs/1706.03762", md)
        self.assertFalse((self.out / "posts" / "draft").exists())
        full = (self.out / "llms-full.txt").read_text()
        self.assertIn("# Vision Transformers", full)
        self.assertNotIn("Secret draft", full)

    def test_data_files(self):
        ps = json.loads((self.out / "data" / "passages.json").read_text())
        self.assertTrue(any(p["anchor"] == "scaled" for p in ps))
        g = json.loads((self.out / "data" / "graph.json").read_text())
        self.assertEqual({"nodes", "edges", "rings", "series", "topics"}, set(g))
        self.assertTrue(all("x" in n and "y" in n for n in g["nodes"]))
        self.assertTrue((self.out / "figures" / "_retrieve.py").exists())


class RepoWikiTest(unittest.TestCase):
    def test_index_stable_and_rewritten_only_on_change(self):
        cfg, pages, rendered, site, g = make_site()
        self.assertTrue(wiki.write_repo_wiki(cfg, pages, g))
        path = cfg.root / "wiki" / "index.md"
        first = path.read_text()
        mtime = path.stat().st_mtime_ns
        self.assertFalse(wiki.write_repo_wiki(cfg, list(reversed(pages)), g))
        self.assertEqual(path.stat().st_mtime_ns, mtime)
        self.assertEqual(first, wiki.index_md(cfg, list(reversed(pages)), g))
        lines = [l for l in first.splitlines() if l.startswith("- [")]
        self.assertEqual(len(lines), len(pages))
        self.assertIn("- [Vision Transformers](/posts/vit/) `post:vit` — Cut an image", first)
        self.assertIn("builds on: Attention, Step by Step", first)
        self.assertIn("## Writing", first)
        self.assertIn("### Attention", first)
        self.assertNotIn("Unfinished", first)

    def test_log_append_format(self):
        cfg, *_ = make_site()
        wiki.append_log(cfg, "publish", "Attention, Step by Step", today=dt.date(2026, 10, 20))
        wiki.append_log(cfg, "ingest", "Vision  Transformers", "Proposal: proposals/ingest-vit.md", today=dt.date(2026, 10, 21))
        text = (cfg.root / "wiki" / "log.md").read_text()
        heads = re.findall(r"^## \[(\d{4}-\d\d-\d\d)\] (\w+) \| (.+)$", text, re.M)
        self.assertEqual(heads, [("2026-10-20", "publish", "Attention, Step by Step"),
                                 ("2026-10-21", "ingest", "Vision Transformers")])
        before = text
        wiki.append_log(cfg, "lint", "3 findings")
        self.assertTrue((cfg.root / "wiki" / "log.md").read_text().startswith(before))


if __name__ == "__main__":
    unittest.main()
