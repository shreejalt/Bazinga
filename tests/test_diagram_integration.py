"""Text diagrams in the rest of Tessera: ```diagram blocks in Markdown (with the file's line on a problem), the code
route (draw.flow, draw.timeline, draw.tree), the theme's stylesheet, and the Studio's diagram panel and its API."""
import http.client
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tessera import diagram_text as dt, draw  # noqa: E402

from test_core_support import render_text  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FENCE = "`" * 3


class Markdown(unittest.TestCase):
    def test_a_block_becomes_a_drawing(self):
        page, r = render_text("Intro.\n\n%sdiagram\nA -> B -> C\nB [accent]\n%s\n\nAfter.\n" % (FENCE, FENCE))
        self.assertEqual(r.issues, [])
        self.assertIn('<figure class="drawing diagram" data-diagram="flow">', r.html)
        self.assertIn("<svg", r.html)
        self.assertNotIn("A -&gt; B", r.html)                       # not shown as code
        self.assertIn("<p>After.</p>", r.html)
        ET.fromstring(re.search(r"<figure.*?</figure>", r.html, re.S).group(0))

    def test_kind_on_the_fence_line_and_caption(self):
        _, r = render_text('%sdiagram timeline\ncaption: "Ten years"\n2012: AlexNet\n2017: Transformer\n%s\n' % (FENCE, FENCE))
        self.assertIn('data-diagram="timeline"', r.html)
        self.assertIn("<figcaption>Ten years</figcaption>", r.html)
        _, r = render_text("~~~diagram tree\nRoot\n  Leaf\n~~~\n")
        self.assertIn('data-diagram="tree"', r.html)

    def test_a_problem_names_the_file_line(self):
        page, r = render_text("Intro.\n\n%sdiagram\nA -> B\nModel [acent]\n%s\n" % (FENCE, FENCE))
        self.assertEqual(len(r.issues), 1)
        issue = r.issues[0]
        self.assertEqual(issue.level, "error")
        self.assertEqual(issue.line, page.body_line + 4)              # the line of "Model [acent]" in the file
        self.assertIn("'acent' is not a style or a shape", issue.message)
        self.assertIn("did you mean accent?", issue.hint)
        self.assertEqual(issue.code, "diagram")
        self.assertIn('class="embed-error"', r.html)
        self.assertIn("Line 2 of the diagram", r.html)

    def test_inside_a_quote(self):
        _, r = render_text("> %sdiagram\n> A -> B\n> %s\n" % (FENCE, FENCE))
        self.assertIn("drawing diagram", r.html)
        self.assertEqual(r.issues, [])

    def test_other_code_blocks_are_untouched(self):
        _, r = render_text("%smarkdown\n%sdiagram\nA -> B\n%s\n%s\n" % ("~~~", FENCE, FENCE, "~~~"))
        self.assertNotIn("drawing diagram", r.html)
        self.assertIn("A -&gt; B", r.html)

    def test_search_text_names_the_boxes(self):
        _, r = render_text("## Part\n\n%sdiagram\nQuery -> Index -> Answer\n%s\n" % (FENCE, FENCE))
        text = " ".join(s["text"] for s in r.sections)
        self.assertIn("Query, Index, Answer", text)


class CodeRoute(unittest.TestCase):
    def test_flow(self):
        d = draw.flow(nodes=["Input", {"name": "Model", "style": "accent", "shape": "round", "sub": "12 layers",
                                        "note": "the big one"}, ("Output", "a label")],
                      edges=[("Input", "Model"), ("Model", "Output", "logits"),
                             {"a": "Output", "b": "Input", "line": "dashed", "heads": "both"}],
                      groups={"Network": ["Model"]}, title="A model")
        svg = d.svg()
        root = ET.fromstring(svg)
        self.assertEqual(root.get("aria-label"), "A model")
        for words in ("dg-node sh-round s-accent", "dg-frame", "NETWORK", ">logits<", "dg-edge s-dashed", "the big one"):
            self.assertIn(words, svg)
        self.assertEqual(d.layout_info["members"], {"Network": ["Model"]})
        narrow = draw.flow(nodes=["A", "B", "C"], edges=[("A", "B"), ("B", "C")], narrow=1)
        b = narrow.layout_info["boxes"]
        self.assertLess(b["A"][1], b["B"][1])                         # the phone layout runs down

    def test_flow_errors(self):
        for kwargs, words in ((dict(nodes=[{"style": "accent"}]), "needs a name"),
                              (dict(edges=[("A",)]), "two ends"),
                              (dict(edges=[{"a": "A", "b": "B", "line": "wavy"}]), "dashed or thick"),
                              (dict(nodes=[{"name": "A", "style": "pink"}]), "not a style"),
                              (dict(nodes=["A"], direction="left"), "use right or down"),
                              (dict(nodes=[], edges=[]), "at least one node"),
                              (dict(edges=[("G", "A")], groups={"G": ["A"]}), "inside it")):
            with self.subTest(words=words):
                with self.assertRaises(draw.DrawError) as cm:
                    draw.flow(**kwargs)
                self.assertIn(words, str(cm.exception))

    def test_timeline_and_tree(self):
        for d in (draw.timeline([("2017", "Transformer", "attention", "accent"), {"date": "2020", "title": "ViT"}]),
                  draw.timeline([("2017", "Transformer")], direction="down"),
                  draw.tree(("Root", ["A", ("B", ["B1"]), {"label": "C", "style": "accent"}])),
                  draw.tree({"One": ["a"], "Two": []}, direction="right"),
                  draw.tree(("Root", ["A"]), narrow=1)):
            ET.fromstring(d.svg())
        with self.assertRaises(draw.DrawError):
            draw.timeline([("", "x")])
        with self.assertRaises(draw.DrawError):
            draw.tree(42)

    def test_example_drawing(self):
        sys.path.insert(0, str(ROOT))
        try:
            from drawings import diagrams
            for narrow in (0, 1):
                ET.fromstring(diagrams.stages(narrow=narrow))
        finally:
            sys.path.remove(str(ROOT))

    def test_the_older_kit_still_draws_the_same(self):
        d = draw.Diagram(600)
        a = d.box(0, 0, 100, 50, "a")
        b = d.box(300, 0, 100, 50, "b")
        d.arrow(a, b)
        self.assertIn('d="M104 25L', d.svg())
        self.assertNotIn("dg-fit", d.svg())                            # fills the column, as before


class Theme(unittest.TestCase):
    def test_stylesheet_uses_the_theme(self):
        css = (ROOT / "tessera" / "theme" / "assets" / "css" / "diagram.css").read_text(encoding="utf-8")
        for var in ("--paper", "--ink", "--blue", "--ref", "--fig-c1", "--mono"):
            self.assertIn(var, css)
        self.assertIn("vector-effect:non-scaling-stroke", css)
        self.assertNotRegex(css, r"(?i)python|pyodide")
        base = (ROOT / "tessera" / "theme" / "templates" / "base.html").read_text(encoding="utf-8")
        self.assertIn("css/diagram.css", base)

    def test_every_style_and_shape_has_a_rule(self):
        css = (ROOT / "tessera" / "theme" / "assets" / "css" / "diagram.css").read_text(encoding="utf-8")
        for style in dt.STYLES:
            self.assertIn(".s-" + style, css)
        for cls in ("dg-node", "dg-edge", "dg-tip", "dg-halo", "dg-frame", "dg-frame-title", "dg-anno", "dg-lid"):
            self.assertIn("." + cls, css)


class StudioPanel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tessera.studio.server import StudioServer
        from test_studio_security import make_site
        cls.tmp = Path(tempfile.mkdtemp(prefix="studio-diagram-"))
        cls.root = cls.tmp / "site"
        cls.root.mkdir()
        make_site(cls.root)
        cls.server = StudioServer(cls.root, 0)
        cls.server.quiet = True
        cls.thread = threading.Thread(target=cls.server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def call(self, method, path, body=None):
        port = self.server.port
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=20)
        headers = {"Host": f"127.0.0.1:{port}", "Cookie": f"{self.server.cookie}={self.server.token}"}
        raw = None
        if body is not None:
            raw = json.dumps(body).encode()
            headers.update({"Content-Type": "application/json", "Origin": f"http://127.0.0.1:{port}"})
        conn.request(method, path, body=raw, headers=headers)
        res = conn.getresponse()
        data = res.read()
        conn.close()
        return res.status, json.loads(data) if data[:1] in (b"{", b"[") else data

    def test_render(self):
        status, res = self.call("POST", "/api/diagram/render", {"source": dt.EXAMPLES[0]["source"]})
        self.assertEqual(status, 200)
        self.assertTrue(res["ok"])
        self.assertEqual((res["kind"], res["boxes"], res["arrows"]), ("flow", 7, 7))
        ET.fromstring(res["svg"])
        ET.fromstring(res["narrow"])
        self.assertIn('<figure class="drawing diagram"', res["html"])

    def test_render_reports_the_line(self):
        status, res = self.call("POST", "/api/diagram/render", {"source": "A -> B\nB -> \n"})
        self.assertEqual(status, 200)
        self.assertFalse(res["ok"])
        self.assertEqual(res["line"], 2)
        self.assertIn("nothing on its right", res["error"])
        self.assertEqual(res["hint"], "write A -> B")

    def test_render_kind_and_limits(self):
        status, res = self.call("POST", "/api/diagram/render", {"source": "2017: Transformer", "kind": "timeline"})
        self.assertEqual((status, res["kind"], res["boxes"]), (200, "timeline", 1))
        status, _ = self.call("POST", "/api/diagram/render", {"source": "A -> B" * 20000})
        self.assertEqual(status, 413)
        status, _ = self.call("POST", "/api/diagram/render", {})
        self.assertEqual(status, 400)

    def test_examples(self):
        status, res = self.call("GET", "/api/diagram/examples")
        self.assertEqual(status, 200)
        self.assertEqual([e["name"] for e in res["examples"]], ["pipeline", "architecture", "flowchart", "timeline", "tree"])
        for e in res["examples"]:
            dt.parse(e["source"])

    def test_writes_need_the_studio_origin(self):
        port = self.server.port
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=20)
        conn.request("POST", "/api/diagram/render", body=b'{"source": "A -> B"}',
                     headers={"Host": f"127.0.0.1:{port}", "Cookie": f"{self.server.cookie}={self.server.token}",
                              "Content-Type": "application/json", "Origin": "https://evil.example"})
        self.assertEqual(conn.getresponse().status, 403)
        conn.close()

    def test_panel_files(self):
        static = ROOT / "tessera" / "studio" / "static"
        js = (static / "panels" / "diagram.js").read_text(encoding="utf-8")
        self.assertIn("/api/diagram/render", js)
        self.assertIn("/api/diagram/examples", js)
        self.assertTrue((static / "panels" / "diagram.css").exists())
        editor = (static / "editor.js").read_text(encoding="utf-8")
        self.assertIn('diagram: "./panels/diagram.js"', editor)
        self.assertIn("diagramButtons", editor)
        node = shutil.which("node")
        if node:
            tmp = Path(tempfile.mkdtemp())
            try:
                copy = tmp / "diagram.mjs"
                copy.write_text(js, encoding="utf-8")
                r = subprocess.run([node, "--check", str(copy)], capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, r.stderr)
            finally:
                shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
