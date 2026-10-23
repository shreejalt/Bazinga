"""bazinga.diagram_text layout: deterministic, no overlaps, arrows clear of boxes, groups around their members,
labels free, a phone version, accessible SVG, and fast."""
import os
import random
import re
import sys
import time
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bazinga import diagram_text as dt  # noqa: E402

from diagram_checks import problems  # noqa: E402
import os as _os
import sys as _sys

_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from perf_support import PERF, perf_only  # noqa: E402,F401

ROOT = Path(__file__).resolve().parent.parent
SVG = "{http://www.w3.org/2000/svg}"


def guide_blocks():
    """Every ```diagram block of the guide (the ones between ~~~ are the same text shown as source)."""
    text = (ROOT / "tests" / "fixtures" / "example-site" / "content" / "reads" / "drawing-diagrams.md").read_text(encoding="utf-8")
    text = re.sub(r"^~~~markdown\n.*?^~~~$", "", text, flags=re.S | re.M)
    return re.findall(r"^```diagram([^\n]*)\n(.*?)^```$", text, flags=re.S | re.M)


def random_source(seed):
    r = random.Random(seed)
    n = r.randint(3, 13)
    words = ["Encoder", "Decoder", "Loss", "Data", "Head", "Norm", "Attention block", "Feed-forward", "Output"]
    names = ["%s %d" % (r.choice(words), i) for i in range(n)]
    lines = ["direction: " + r.choice(["right", "down"])]
    for i in range(1, n):
        lab = (': "' + r.choice(["yes", "no", "features", "x"]) + '"') if r.random() < .25 else ""
        lines.append("%s -> %s%s" % (names[r.randrange(0, i)], names[i], lab))
    for _ in range(r.randint(0, 3)):
        a, b = r.sample(names, 2)
        lines.append("%s %s %s" % (a, r.choice(["->", "-.->", "--", "<->"]), b))
    if r.random() < .5 and n > 4:
        k = r.randint(2, min(4, n - 2))
        start = r.randint(1, n - k)
        lines.append("group G { %s }" % "; ".join(names[start:start + k]))
    for nm in r.sample(names, 2):
        lines.append("%s [%s]" % (nm, r.choice(["accent", "muted", "data", "diamond", "round", "circle"])))
    if r.random() < .3:
        lines.append('note %s: "a note"' % r.choice(names))
    return "\n".join(lines)


class Examples(unittest.TestCase):
    def test_every_example_is_clean_wide_and_narrow(self):
        for ex in dt.EXAMPLES:
            g = dt.parse(ex["source"])
            if g.kind != "flow":
                continue
            for narrow in (False, True):
                with self.subTest(example=ex["name"], narrow=narrow):
                    self.assertEqual(problems(dt.layout(g, narrow=narrow)), [])

    def test_every_guide_diagram_is_clean(self):
        blocks = guide_blocks()
        self.assertGreaterEqual(len(blocks), 10)
        for info, src in blocks:
            g = dt.parse(src, info.split()[0] if info.split() else None)
            if g.kind != "flow":
                continue
            for narrow in (False, True):
                with self.subTest(src=src[:40], narrow=narrow):
                    self.assertEqual(problems(dt.layout(g, narrow=narrow)), [])

    def test_random_graphs_are_clean(self):
        for seed in range(80):
            src = random_source(seed)
            g = dt.parse(src)
            for narrow in (False, True):
                with self.subTest(seed=seed, narrow=narrow):
                    self.assertEqual(problems(dt.layout(g, narrow=narrow)), [], src)

    def test_the_checker_finds_problems(self):
        d = dt.layout(dt.parse("A -> B -> C\ngroup G { B }"))
        info = d.layout_info
        x, y, w, h = info["boxes"]["A"]
        info["boxes"]["C"] = (x + 4, y + 4, w, h)                      # overlap A
        info["routes"].append(("A", "C", [(x - 50, y + h / 2), (x + w + 50, y + h / 2)]))   # through A
        info["routes"].append(("Q", "R", [(x - 50, y + h / 2), (x + w + 50, y + h / 2)]))   # on top of it
        info["routes"].append(("A", "B", [(0, 0), (10, 10)]))          # slanted
        info["labels"].append(("over A", (x + w / 2, y + h / 2)))
        info["members"]["G"].append("A")                                # A is not inside G's frame
        found = " | ".join(problems(d))
        for words in ("overlap", "runs through", "on top of each other", "slanted", "covers", "sticks out"):
            self.assertIn(words, found)


class Shape(unittest.TestCase):
    def test_deterministic(self):
        for ex in dt.EXAMPLES:
            with self.subTest(example=ex["name"]):
                a = dt.render_html(ex["source"])
                b = dt.render_html(ex["source"])
                self.assertEqual(a, b)
                self.assertEqual(dt.render(ex["source"]), dt.layout(dt.parse(ex["source"])).svg())

    def test_a_chain_is_a_straight_line(self):
        d = dt.layout(dt.parse("A -> Bee -> Sea -> Dee"))
        ys = set()
        for _a, _b, pts in d.layout_info["routes"]:
            self.assertEqual(len(pts), 2)
            ys.add(round(pts[0][1], 1))
            ys.add(round(pts[1][1], 1))
        self.assertEqual(len(ys), 1)

    def test_a_decision_lines_up_with_its_first_answer(self):
        d = dt.layout(dt.parse(dt.EXAMPLES[2]["source"]))
        b = d.layout_info["boxes"]
        cx = lambda k: b[k][0] + b[k][2] / 2  # noqa: E731
        self.assertAlmostEqual(cx("Loss finite?"), cx("Take a step"), delta=0.5)
        self.assertAlmostEqual(cx("Take a step"), cx("Last batch?"), delta=0.5)
        self.assertAlmostEqual(cx("Last batch?"), cx("Done"), delta=0.5)

    def test_layers_follow_the_arrows(self):
        d = dt.layout(dt.parse("A -> B -> C\nA -> C"))
        b = d.layout_info["boxes"]
        self.assertLess(b["A"][0], b["B"][0])
        self.assertLess(b["B"][0], b["C"][0])
        d = dt.layout(dt.parse("direction: down\nA -> B -> C"))
        b = d.layout_info["boxes"]
        self.assertLess(b["A"][1], b["B"][1])

    def test_groups_hold_their_members(self):
        d = dt.layout(dt.parse("X -> Encoder -> Y\ngroup Encoder { P -> Q }\ngroup Outer { Encoder }"))
        info = d.layout_info
        gx, gy, gw, gh = info["groups"]["Encoder"]
        for m in ("P", "Q"):
            x, y, w, h = info["boxes"][m]
            self.assertTrue(gx < x and gy < y and x + w < gx + gw and y + h < gy + gh)
        ox, oy, ow, oh = info["groups"]["Outer"]
        self.assertTrue(ox < gx and oy < gy and gx + gw < ox + ow and gy + gh < oy + oh)
        self.assertEqual(problems(d), [])

    def test_labels_are_drawn_on_a_patch(self):
        svg = dt.render('A -> B: "first"\nB -> C: "second"')
        self.assertEqual(svg.count('class="dg-halo"'), 2)
        self.assertIn(">first</text>", svg)
        self.assertIn(">second</text>", svg)

    def test_long_names_wrap(self):
        d = dt.layout(dt.parse("A rather long name for a box that will need to wrap -> B"))
        x, y, w, h = d.layout_info["boxes"]["A rather long name for a box that will need to wrap"]
        self.assertLessEqual(w, dt.TEXT_W + 2 * dt.PAD_X + 1)
        self.assertGreater(h, dt.MIN_H)

    def test_loops_and_cycles(self):
        for src in ("A -> B -> C -> A", "A -> A\nA -> B", "direction: down\nA -> B -> A"):
            with self.subTest(src=src):
                d = dt.layout(dt.parse(src))
                ET.fromstring(d.svg())
                self.assertEqual(problems(d), [])


class Phones(unittest.TestCase):
    def test_a_wide_flow_gets_a_top_to_bottom_phone_version(self):
        g, wide, narrow, nw = dt.variants(dt.EXAMPLES[0]["source"])
        self.assertIsNotNone(narrow)
        wv = [float(v) for v in ET.fromstring(wide).get("viewBox").split()]
        nv = [float(v) for v in ET.fromstring(narrow).get("viewBox").split()]
        self.assertLess(nv[2], wv[2] / 2)          # much narrower
        self.assertGreater(nv[3], wv[3])           # and taller
        self.assertLessEqual(nw, 400)
        html = dt.render_html(dt.EXAMPLES[0]["source"])
        self.assertIn('class="drawing-svg drawing-wide drawing-fit"', html)
        self.assertIn('class="drawing-svg drawing-narrow drawing-fit"', html)

    def test_a_small_diagram_needs_no_phone_version(self):
        g, wide, narrow, w = dt.variants("direction: down\nA -> B -> C")
        self.assertIsNone(narrow)
        self.assertIn('<div class="drawing-svg drawing-fit">', dt.render_html("direction: down\nA -> B -> C"))

    def test_timeline_and_tree_phone_versions(self):
        for ex in dt.EXAMPLES[3:]:
            with self.subTest(example=ex["name"]):
                g, wide, narrow, nw = dt.variants(ex["source"])
                self.assertIsNotNone(narrow)
                self.assertLess(nw, 380)

    def test_a_very_wide_phone_version_scrolls_with_readable_text(self):
        src = "direction: down\n" + "\n".join("Top -> Box number %d" % i for i in range(6))
        html = dt.render_html(src)
        self.assertIn("dg-scroll", html)
        self.assertIn('tabindex="0"', html)
        self.assertRegex(html, r'style="--dg-w:\d+px"')


class Accessible(unittest.TestCase):
    def test_title_label_and_description(self):
        svg = dt.render('title: "How a request is served"\nBrowser -> Server: "GET"\nServer -> Database')
        root = ET.fromstring(svg)
        self.assertEqual(root.get("role"), "img")
        self.assertEqual(root.get("aria-label"), "How a request is served")
        self.assertEqual(root.find(SVG + "title").text, "How a request is served")
        desc = root.find(SVG + "desc").text
        self.assertIn("Browser leads to Server (GET)", desc)
        self.assertIn("Server leads to Database", desc)

    def test_default_title_lists_the_boxes(self):
        root = ET.fromstring(dt.render("A -> B -> C"))
        self.assertEqual(root.get("aria-label"), "Diagram: A, B, C")

    def test_every_kind_is_well_formed_and_escaped(self):
        for src in ('"<b> & co" -> B', "kind: timeline\n2017: <x> & y", "kind: tree\n<root>\n  & child"):
            with self.subTest(src=src):
                for narrow in (False, True):
                    ET.fromstring(dt.render(src, narrow=narrow))

    def test_sized_to_its_content(self):
        root = ET.fromstring(dt.render("A -> B"))
        self.assertIn("dg-fit", root.get("class"))
        self.assertEqual(root.get("width"), root.get("viewBox").split()[2])


@perf_only
class Speed(unittest.TestCase):
    def test_examples_draw_quickly(self):
        for ex in dt.EXAMPLES:
            with self.subTest(example=ex["name"]):
                t = time.perf_counter()
                dt.render_html(ex["source"])
                self.assertLess(time.perf_counter() - t, 0.5)


if __name__ == "__main__":
    unittest.main()
