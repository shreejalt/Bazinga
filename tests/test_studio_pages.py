"""The Studio's file handling: front matter kept as written, new drafts from the starter, renames that keep links,
version history, and citations appended without reformatting references.yml."""

import datetime
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from tessera.studio import cite, history, pages
from tessera.studio.api import Studio
from tessera.studio.security import Refused

DOC = """---
title: "Attention, Step by Step"
# a comment the author wrote
status: draft
summary: "Two sentences."
topics: [attention]
legacy: /old/url/
---

Body text with [[post:other]] in it.
"""


class FrontMatter(unittest.TestCase):
    def test_unchanged_meta_keeps_text_byte_for_byte(self):
        fm, body = pages.split(DOC)
        meta = pages.normalise(pages.to_json(pages.load_meta(fm)))
        self.assertEqual(pages.compose(meta, body, DOC), DOC)

    def test_changed_key_keeps_comments_and_other_keys(self):
        fm, body = pages.split(DOC)
        meta = pages.to_json(pages.load_meta(fm))
        meta["topics"] = ["attention", "transformers"]
        meta["description"] = "Short: with a colon"
        out = pages.compose(pages.normalise(meta), body, DOC)
        self.assertIn("# a comment the author wrote", out)
        self.assertIn('title: "Attention, Step by Step"', out)
        self.assertIn("topics: [attention, transformers]", out)
        self.assertIn("legacy: /old/url/", out)
        back = pages.load_meta(pages.split(out)[0])
        self.assertEqual(back["description"], "Short: with a colon")
        self.assertTrue(out.endswith("Body text with [[post:other]] in it.\n"))

    def test_removed_key(self):
        fm, body = pages.split(DOC)
        meta = pages.to_json(pages.load_meta(fm))
        del meta["legacy"]
        out = pages.compose(pages.normalise(meta), body, DOC)
        self.assertNotIn("legacy", out)
        self.assertIn("# a comment", out)

    def test_set_fields_for_publish(self):
        out = pages.set_fields(DOC, status="published", date=datetime.date(2026, 10, 20))
        meta = pages.load_meta(pages.split(out)[0])
        self.assertEqual(meta["status"], "published")
        self.assertEqual(meta["date"], datetime.date(2026, 10, 20))
        self.assertIn("# a comment the author wrote", out)
        self.assertEqual(pages.split(out)[1], pages.split(DOC)[1])

    def test_tricky_values_round_trip(self):
        meta = {"title": "yes", "summary": 'He said "no": then left', "topics": ["a-b", "c"],
                "series": {"name": "Part: one", "part": 2}, "date": datetime.date(2026, 1, 2), "description": "123"}
        text = pages.compose(meta, "x")
        back = pages.load_meta(pages.split(text)[0])
        self.assertEqual(pages.to_json(back), pages.to_json(meta))

    def test_normalise_refuses_bad_names_and_dates(self):
        with self.assertRaises(Refused):
            pages.normalise({"bad key": 1})
        with self.assertRaises(Refused):
            pages.normalise({"date": "20 Oct"})
        self.assertEqual(pages.normalise({"date": "2026-10-20"})["date"], datetime.date(2026, 10, 20))
        self.assertNotIn("series", pages.normalise({"series": {"name": "", "part": 1}}))

    def test_rewrite_references(self):
        text, n = pages.rewrite_references(DOC.replace("topics: [attention]", "builds_on: [post:other]"),
                                           "post:other", "post:renamed")
        self.assertEqual(n, 2)
        self.assertIn("[[post:renamed]]", text)
        self.assertIn("builds_on: [post:renamed]", text)
        text, n = pages.rewrite_references("See [[post:other|this]] and [[post:otherwise]].", "post:other", "post:new")
        self.assertEqual(text, "See [[post:new|this]] and [[post:otherwise]].")

    def test_used_files(self):
        body = "::figure softmax\n\n```\n::figure not_this\n```\n::drawing pipeline.overview | cap\n![a](static/uploads/x.png)"
        self.assertEqual(pages.figures_used(body), ["softmax"])
        self.assertEqual(pages.drawings_used(body), ["pipeline.overview"])
        self.assertEqual(pages.uploads_used(body), ["static/uploads/x.png"])


class Site(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="studio-pages-"))
        (self.root / "content" / "posts").mkdir(parents=True)
        (self.root / "site.yml").write_text('site:\n  origin: "https://example.org"\n', encoding="utf-8")
        (self.root / "content" / "posts" / "other.md").write_text(
            '---\ntitle: "Other"\nstatus: draft\n---\n\nText.\n', encoding="utf-8")
        (self.root / "content" / "posts" / "linker.md").write_text(
            '---\ntitle: "Linker"\nstatus: draft\nbuilds_on: [post:other]\n---\n\nSee [[post:other]].\n',
            encoding="utf-8")
        self.studio = Studio(self.root)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_new_page_from_starter(self):
        res = self.studio.new_page({"title": "Softmax, step by step", "kind": "posts"})
        self.assertEqual(res["id"], "post:softmax-step-by-step")
        text = (self.root / "content/posts/softmax-step-by-step.md").read_text()
        meta = pages.load_meta(pages.split(text)[0])
        self.assertEqual(meta["title"], "Softmax, step by step")
        self.assertEqual(meta["status"], "draft")
        self.assertNotIn("date", meta)
        res2 = self.studio.new_page({"title": "Softmax, step by step", "kind": "posts"})
        self.assertEqual(res2["id"], "post:softmax-step-by-step-2")

    def test_save_and_conflict(self):
        page = self.studio.get_page({"id": "post:other"})
        res = self.studio.save_page({"id": "post:other", "meta": page["meta"], "body": "New text.", "base": page["hash"]})
        self.assertTrue(res["ok"])
        self.assertIn("New text.", (self.root / "content/posts/other.md").read_text())
        with self.assertRaises(Refused) as ctx:     # the old hash: someone else changed the file meanwhile
            self.studio.save_page({"id": "post:other", "meta": page["meta"], "body": "Mine.", "base": page["hash"]})
        self.assertEqual(ctx.exception.status, 409)

    def test_rename_updates_links_and_history(self):
        page = self.studio.get_page({"id": "post:other"})
        self.studio.save_page({"id": "post:other", "meta": page["meta"], "body": "v2", "explicit": True})
        res = self.studio.rename_page({"id": "post:other", "slug": "Other Name"})
        self.assertEqual(res["id"], "post:other-name")
        self.assertFalse((self.root / "content/posts/other.md").exists())
        linker = (self.root / "content/posts/linker.md").read_text()
        self.assertIn("[[post:other-name]]", linker)
        self.assertIn("builds_on: [post:other-name]", linker)
        self.assertTrue(history.list_versions(self.root, "posts", "other-name"))
        with self.assertRaises(Refused):
            self.studio.rename_page({"id": "post:other-name", "slug": "linker"})

    def test_history_snapshots(self):
        with mock.patch.object(history, "AUTOSAVE_GAP", 0.0):
            history.snapshot(self.root, "posts", "x", "one", explicit=False)
            history.snapshot(self.root, "posts", "x", "one", explicit=True)   # identical: not stored again
            time.sleep(0.002)
            history.snapshot(self.root, "posts", "x", "two", explicit=True)
        versions = history.list_versions(self.root, "posts", "x")
        self.assertEqual(len(versions), 2)
        self.assertEqual(history.read_version(self.root, "posts", "x", versions[0]["name"]), "two")
        with self.assertRaises(Refused):
            history.read_version(self.root, "posts", "x", "../../site.yml")
        self.assertEqual((self.root / ".studio/.gitignore").read_text(), "*\n")

    def test_autosave_snapshots_at_most_once_a_minute(self):
        history.snapshot(self.root, "posts", "y", "a", explicit=False)
        history.snapshot(self.root, "posts", "y", "b", explicit=False)
        self.assertEqual(len(history.list_versions(self.root, "posts", "y")), 1)

    def test_topic_add_appends(self):
        (self.root / "content/topics.yml").write_text(
            "# my topics\ngroups:\n  - name: Main\n    topics:\n      - {slug: writing, label: Writing}\n",
            encoding="utf-8")
        res = self.studio.topic_add({"label": "Signal Processing"})
        self.assertEqual(res["slug"], "signal-processing")
        text = (self.root / "content/topics.yml").read_text()
        self.assertTrue(text.startswith("# my topics\n"))
        self.studio.topic_add({"label": "Optics"})
        from tessera import content
        from tessera import config
        topics = content.load_topics(config.load(self.root))
        self.assertIn("signal-processing", topics)
        self.assertIn("optics", topics)


class Citations(unittest.TestCase):
    def test_parse_query(self):
        self.assertEqual(cite.parse_query("1706.03762"), ("arxiv", "1706.03762"))
        self.assertEqual(cite.parse_query("https://arxiv.org/abs/1706.03762v7"), ("arxiv", "1706.03762"))
        self.assertEqual(cite.parse_query("arxiv.org/pdf/2312.00752.pdf"), ("arxiv", "2312.00752"))
        self.assertEqual(cite.parse_query("https://doi.org/10.1145/3065386"), ("doi", "10.1145/3065386"))
        with self.assertRaises(Refused):
            cite.parse_query("attention is all you need")

    def test_key(self):
        rec = {"authors": ["Ashish Vaswani", "Noam Shazeer"], "year": 2017}
        self.assertEqual(cite.fallback_key(rec, {}), "VASW17")
        self.assertEqual(cite.fallback_key(rec, {"VASW17": {}}), "VASW17a")
        self.assertEqual(cite.fallback_key({"authors": ["Kaiming He"], "year": 2016}, {}), "HE16")
        key = cite.suggest_key(rec, {})
        self.assertTrue(key and key not in {}, key)
        self.assertNotEqual(cite.suggest_key(rec, {key: {}}), key)

    def test_save_appends_without_reformatting(self):
        root = Path(tempfile.mkdtemp(prefix="studio-cite-"))
        try:
            (root / "content").mkdir()
            original = "# my library\nOLD20: {title: \"Old\", authors: [A B], year: 2020}\n"
            (root / "content/references.yml").write_text(original, encoding="utf-8")
            cite.save(root, "NEW21", {"title": "New: a paper", "authors": ["C D", "E F"], "year": "2021",
                                      "arxiv": "2101.00001", "junk": "x"})
            text = (root / "content/references.yml").read_text()
            self.assertTrue(text.startswith(original))
            data = cite.load(root)
            self.assertEqual(data["NEW21"]["title"], "New: a paper")
            self.assertEqual(data["NEW21"]["year"], 2021)
            self.assertNotIn("junk", data["NEW21"])
            with self.assertRaises(Refused):
                cite.save(root, "NEW21", {"title": "again"})
            with self.assertRaises(Refused):
                cite.save(root, "bad key!", {"title": "x"})
        finally:
            shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
