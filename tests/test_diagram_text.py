"""bazinga.diagram_text: reading the text (every feature) and the problems it reports (line + hint)."""
import unittest

from bazinga import diagram_text as dt


def names(g):
    return [n.name for n in g.nodes.values()]


def edges(g):
    return [(e.a.name, e.b.name, e.heads, e.line_style, e.label) for e in g.edges]


class Flow(unittest.TestCase):
    def test_chain_makes_boxes_in_order(self):
        g = dt.parse("Input image -> Backbone -> Encoder\nencoder -> Decoder")
        self.assertEqual(names(g), ["Input image", "Backbone", "Encoder", "Decoder"])   # case-insensitive match
        self.assertEqual([e[:2] for e in edges(g)], [("Input image", "Backbone"), ("Backbone", "Encoder"),
                                                     ("Encoder", "Decoder")])
        self.assertEqual(g.kind, "flow")
        self.assertIsNone(g.direction)

    def test_kinds_of_arrow(self):
        g = dt.parse("A <- B\nC -- D\nE <-> F\nG -.-> H\nI ==> J\nK --> L\nM <-.- N\nO --- P\nQ -.- R\nS → T")
        self.assertEqual(edges(g), [
            ("B", "A", "end", "", ""), ("C", "D", "none", "", ""), ("E", "F", "both", "", ""),
            ("G", "H", "end", "dashed", ""), ("I", "J", "end", "thick", ""), ("K", "L", "end", "", ""),
            ("N", "M", "end", "dashed", ""), ("O", "P", "none", "", ""), ("Q", "R", "none", "dashed", ""),
            ("S", "T", "end", "", "")])

    def test_labels(self):
        g = dt.parse('A -> B -> C: "last"\nA ->|first| D -> E\nX -> Y: plain words')
        lab = {(a, b): l for a, b, _h, _s, l in edges(g)}
        self.assertEqual(lab[("A", "B")], "")
        self.assertEqual(lab[("B", "C")], "last")
        self.assertEqual(lab[("A", "D")], "first")
        self.assertEqual(lab[("D", "E")], "")
        self.assertEqual(lab[("X", "Y")], "plain words")

    def test_fan_out_and_in(self):
        g = dt.parse("A -> B & C -> D")
        self.assertEqual([e[:2] for e in edges(g)], [("A", "B"), ("A", "C"), ("B", "D"), ("C", "D")])

    def test_quotes_comments_and_statements(self):
        g = dt.parse('"Step 1: load" -> "C# code"  # a comment\nA; B -> C   # two statements\n# only a comment')
        self.assertEqual(names(g), ["Step 1: load", "C# code", "A", "B", "C"])
        self.assertEqual(edges(g)[0][:2], ("Step 1: load", "C# code"))
        g = dt.parse('"two\\nlines" -> B')
        self.assertEqual(names(g)[0], "two\nlines")

    def test_shapes(self):
        g = dt.parse("(Start) -> [Load] -> {Valid?} -> ((Join)) -> [/Store/]\n([Stop])\nLinear (W_q) -> Valid?")
        shapes = {n.name: n.shape for n in g.nodes.values()}
        self.assertEqual(shapes, {"Start": "round", "Load": "box", "Valid?": "diamond", "Join": "circle",
                                  "Store": "data", "Stop": "round", "Linear (W_q)": "box"})
        self.assertEqual(g.nodes["store"].style, "data")          # a data shape takes the data colour

    def test_settings(self):
        g = dt.parse('A [accent]\nB [muted, round]\nC [style=emphasis, shape=diamond, label="Shown text", '
                     'sub="second", note="beside"]\nD [data]\nE [ shape = cylinder ]\nF [decision]')
        n = g.nodes
        self.assertEqual((n["a"].style, n["a"].shape), ("accent", "box"))
        self.assertEqual((n["b"].style, n["b"].shape), ("muted", "round"))
        self.assertEqual((n["c"].style, n["c"].shape, n["c"].label, n["c"].sub, n["c"].note),
                         ("emphasis", "diamond", "Shown text", "second", "beside"))
        self.assertEqual((n["d"].style, n["d"].shape), ("data", "data"))
        self.assertEqual(n["e"].shape, "data")
        self.assertEqual(n["f"].shape, "diamond")

    def test_second_line_and_notes(self):
        g = dt.parse('Encoder -> Decoder\nEncoder: "12 layers"\nnote Decoder: "reads it"\nnote: "under all"')
        self.assertEqual(g.nodes["encoder"].sub, "12 layers")
        self.assertEqual(g.nodes["decoder"].note, "reads it")
        self.assertEqual(g.notes, ["under all"])

    def test_groups(self):
        src = """Input -> Encoder -> Decoder
group Encoder { Attention -> Feed-forward }
group Model {
  Decoder
  group Head { Linear; Softmax }
}
Attention -> Linear"""
        g = dt.parse(src)
        enc, model, head = g.nodes["encoder"], g.nodes["model"], g.nodes["head"]
        self.assertTrue(enc.is_group and model.is_group and head.is_group)
        self.assertEqual([m.name for m in enc.children], ["Attention", "Feed-forward"])
        self.assertEqual([m.name for m in model.children], ["Decoder", "Head"])
        self.assertEqual([m.name for m in head.children], ["Linear", "Softmax"])
        self.assertIsNone(g.nodes["input"].parent)
        self.assertIs(g.nodes["linear"].parent, head)               # the first group it is written in
        self.assertIn(("Input", "Encoder"), [e[:2] for e in edges(g)])   # arrows to a group's title

    def test_group_style_and_quoted_title(self):
        g = dt.parse('group "Block x 6" [accent] { A -> B }')
        grp = g.nodes["block x 6"]
        self.assertEqual((grp.name, grp.gstyle), ("Block x 6", "accent"))

    def test_directives(self):
        for word, want in (("right", "right"), ("LR", "right"), ("down", "down"), ("TB", "down"),
                           ("top-down", "down"), ("vertical", "down")):
            self.assertEqual(dt.parse("direction: %s\nA -> B" % word).direction, want)
        g = dt.parse('title: "Screen reader name"\ncaption: Under the figure\nA -> B')
        self.assertEqual((g.title, g.caption), ("Screen reader name", "Under the figure"))

    def test_kind_from_fence_or_line(self):
        self.assertEqual(dt.parse("2017: Transformer", kind="timeline").kind, "timeline")
        self.assertEqual(dt.parse("kind: tree\nRoot\n  Leaf").kind, "tree")
        self.assertEqual(dt.parse("kind: tree\nRoot\n  Leaf", kind="timeline").kind, "tree")   # the line wins


class Timeline(unittest.TestCase):
    def test_items(self):
        g = dt.parse('kind: timeline\n2012: AlexNet: "deep nets"\n- Jun 2017: Transformer [accent]: attention\n'
                     '2020-10-22: ViT\nnote: "a note"')
        self.assertEqual([(d, t, x, s) for d, t, x, s, _ in g.items],
                         [("2012", "AlexNet", "deep nets", ""), ("Jun 2017", "Transformer", "attention", "accent"),
                          ("2020-10-22", "ViT", "", "")])
        self.assertEqual(g.notes, ["a note"])


class Tree(unittest.TestCase):
    def shape(self, roots):
        return [(t.label, self.shape(t.children)) if t.children else t.label for t in roots]

    def test_indentation(self):
        g = dt.parse("kind: tree\nRoot\n  A\n    A1\n    A2\n  B [accent]\n  (C): \"second\"\n")
        self.assertEqual(self.shape(g.roots), [("Root", [("A", ["A1", "A2"]), "B", "C"])])
        b = g.roots[0].children[1]
        c = g.roots[0].children[2]
        self.assertEqual((b.style, c.shape, c.sub), ("accent", "round", "second"))

    def test_tabs_bullets_and_tree_listings(self):
        want = [("Root", [("A", ["A1"]), "B"])]
        for src in ("Root\n\tA\n\t\tA1\n\tB", "- Root\n  - A\n    - A1\n  - B",
                    "Root\n├── A\n│   └── A1\n└── B", "* Root\n    * A\n        * A1\n    * B"):
            with self.subTest(src=src):
                self.assertEqual(self.shape(dt.parse(src, kind="tree").roots), want)

    def test_forest(self):
        g = dt.parse("kind: tree\nA\n  a\nB\n  b")
        self.assertEqual(self.shape(g.roots), [("A", ["a"]), ("B", ["b"])])


class Problems(unittest.TestCase):
    CASES = [
        ("A -> ", 1, "this arrow has nothing on its right", "write A -> B"),
        ("-> B", 1, "this arrow has nothing on its left", "write A -> B"),
        ('A -> B\n"one" "two"', 2, "two names in a row", "join them with an arrow"),
        ("A -> -> B", 1, "two arrows in a row", "A -> B -> C"),
        ("A & -> B", 1, "two arrows in a row", ""),
        ('A -> "open', 1, "a quote is never closed", 'add "'),
        ("Model [acent]", 1, "'acent' is not a style or a shape", "did you mean accent?"),
        ("Model [style=blu]", 1, "'blu' is not a style", "use one of accent"),
        ("Model [shape=hexagon]", 1, "'hexagon' is not a shape", "use one of box"),
        ("Model [colour=red, size=2]", 1, "'red' is not a style", ""),
        ("Model [size=2]", 1, "unknown setting 'size'", "settings are style"),
        ("A -> {B", 1, "a decision is opened with { but never closed", "add }"),
        ("A -> [/B", 1, "a data shape [/…/] is never closed", "[/Dataset/]"),
        ("group Encoder", 1, "a group needs { after its title", "group Encoder { Attention"),
        ("group { A }", 1, "a group needs a title", ""),
        ("A -> B\ngroup Encoder {\n  C\n", 2, "the group 'Encoder' is never closed", "add a line with }"),
        ("A -> B\n}", 2, "a } with no group to close", ""),
        ("group G { A }\ngroup g { B }", 2, "two groups are called 'G'", ""),
        ("group G {\n  direction: down\n}", 2, "direction: goes at the top of the diagram", ""),
        ('Decoder -> X\nnote Decoderr: "x"', 2, "note on 'Decoderr', which is not in the diagram",
         "did you mean Decoder?"),
        ('note A:', 1, "an empty note", ""),
        ("", 1, "this diagram is empty", "Input -> Model"),
        ("# just a comment", 1, "this diagram is empty", ""),
        ("direction: left\nA -> B", 1, "'left' is not a direction", "turn the arrows around"),
        ("direction: sideways\nA -> B", 1, "'sideways' is not a direction", "use right or down"),
        ("kind: pie\nA", 1, "'pie' is not a kind of diagram", "use flow, timeline or tree"),
        ("group G { A -> B }\nG -> A", 2, "an arrow joins the group 'G' to 'A', which is inside it", ""),
        ("A -> B\n{ stray", 2, "a decision is opened with { but never closed", ""),
        ("kind: timeline\n2017 Transformer", 2, "a timeline item is a date, a colon and what happened",
         "write 2017: Transformer"),
        ("kind: timeline\n: Transformer", 2, "this item has no date", ""),
        ("kind: timeline\n2017:", 2, "this item says when but not what", ""),
        ("kind: timeline", 1, "this timeline has no items", ""),
        ("kind: tree\nRoot\n  A -> B", 3, "a tree has no arrows", "indent a line"),
        ("kind: tree\nRoot\n    A\n  B", 4, "this line's indent does not match any line above it", ""),
        ("kind: tree\n  Root\nOther", 3, "this line's indent does not match any line above it", ""),
        ("kind: tree", 1, "this tree is empty", ""),
    ]

    def test_messages_lines_and_hints(self):
        for src, line, words, hint in self.CASES:
            with self.subTest(src=src):
                with self.assertRaises(dt.DiagramError) as cm:
                    dt.parse(src)
                e = cm.exception
                self.assertEqual(e.line, line)
                self.assertIn(words, e.message)
                self.assertIn(hint, e.hint)
                self.assertTrue(str(e).startswith("line %d: " % line))

    def test_too_many_boxes(self):
        src = "\n".join("N%d -> N%d" % (i, i + 1) for i in range(dt.MAX_NODES + 2))
        with self.assertRaises(dt.DiagramError) as cm:
            dt.parse(src)
        self.assertIn("more than %d boxes" % dt.MAX_NODES, cm.exception.message)
        self.assertIn("split it", cm.exception.hint)

    def test_kind_argument(self):
        with self.assertRaises(dt.DiagramError) as cm:
            dt.parse("A", kind="pie")
        self.assertIn("did you mean", cm.exception.hint + " did you mean")

    def test_the_guide_table_is_true(self):
        # content/reads/drawing-diagrams.md lists these messages; keep it honest
        for src, words in (("Input -> ", "this arrow has nothing on its right (write A -> B)"),
                           ("Model [acent]", "'acent' is not a style or a shape (did you mean accent?"),
                           ("group Encoder", "a group needs { after its title"),
                           ('Decoder -> X\nnote Decoderr: "x"',
                            "note on 'Decoderr', which is not in the diagram (did you mean Decoder?"),
                           ("kind: timeline\n2017 Transformer", "a timeline item is a date, a colon and what happened")):
            with self.subTest(src=src):
                with self.assertRaises(dt.DiagramError) as cm:
                    dt.parse(src)
                self.assertIn(words, str(cm.exception))


if __name__ == "__main__":
    unittest.main()
