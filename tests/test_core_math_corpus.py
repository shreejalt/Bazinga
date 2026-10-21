"""The maths corpus (tests/fixtures/math_corpus.yml): every snippet renders as MathML Core, or fails with a hint.

The validator here is independent of mathml.py's own: it parses the output and checks every element and attribute
against MathML Core, looks for leaked LaTeX, and checks the error positions the corpus gives.
"""
import re
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml

from bazinga.mathml import MathError, split_tag_label, to_mathml

CORPUS = Path(__file__).parent / "fixtures" / "math_corpus.yml"
NS = "{http://www.w3.org/1998/Math/MathML}"

ELEMENTS = {"math", "semantics", "annotation", "mrow", "mi", "mn", "mo", "mtext", "ms", "mspace", "msub", "msup",
            "msubsup", "munder", "mover", "munderover", "mmultiscripts", "mprescripts", "none", "mfrac", "msqrt",
            "mroot", "mtable", "mtr", "mtd", "mstyle", "mpadded", "mphantom", "merror"}
GLOBAL = {"style", "class", "id", "dir", "displaystyle", "scriptlevel", "mathcolor", "mathbackground", "mathsize"}
ATTRS = {"math": {"display"}, "annotation": {"encoding"}, "mi": {"mathvariant"},
         "mo": {"form", "fence", "separator", "lspace", "rspace", "stretchy", "symmetric", "maxsize", "minsize",
                "largeop", "movablelimits"},
         "mspace": {"width", "height", "depth"}, "mpadded": {"width", "height", "depth", "lspace", "voffset"},
         "mfrac": {"linethickness"}, "munder": {"accentunder"}, "mover": {"accent"},
         "munderover": {"accent", "accentunder"}, "mtd": {"columnspan", "rowspan"}}
LENGTH = re.compile(r"^-?(?:\d+\.?\d*|\.\d+)(?:em|ex|px|pt|in|cm|mm|%)?$")
BOOL = {"true", "false"}


def load():
    return yaml.safe_load(CORPUS.read_text(encoding="utf-8"))


def core_problems(mathml: str) -> list[str]:
    """Everything in ``mathml`` that is not MathML Core, or that shows LaTeX as text."""
    problems = []
    root = ET.fromstring(mathml)
    for el in root.iter():
        tag = el.tag.replace(NS, "")
        if tag not in ELEMENTS:
            problems.append(f"<{tag}> is not MathML Core")
            continue
        for attr, value in el.attrib.items():
            if attr not in GLOBAL | ATTRS.get(tag, set()):
                problems.append(f"{attr} on <{tag}> is not MathML Core")
            elif attr in ("width", "height", "depth", "lspace", "rspace", "voffset", "minsize", "maxsize") \
                    and not LENGTH.match(value):
                problems.append(f"{attr}={value!r} on <{tag}> is not a CSS length")
            elif attr in ("stretchy", "fence", "movablelimits", "accent", "accentunder", "displaystyle",
                          "largeop", "symmetric", "separator") and value not in BOOL:
                problems.append(f"{attr}={value!r} on <{tag}> is not true/false")
            elif attr == "mathvariant" and value != "normal":
                problems.append(f"mathvariant={value!r} is ignored by Chromium")
        if tag == "annotation":
            continue
        text = el.text or ""
        if tag in ("mi", "mo", "mn", "mtext") and re.search(r"\\[A-Za-z]+|\\[{}|]", text):
            problems.append(f"LaTeX leaked into <{tag}>: {text!r}")
        if tag in ("mi", "mn", "mo") and len(el):
            problems.append(f"<{tag}> has element children")
        if tag == "mi" and text == "&":
            problems.append("a literal & was printed")
    return problems


def render(item):
    display = bool(item.get("display", False))
    tex = item["tex"]
    if display:
        tex, _tag, _label = split_tag_label(tex)
    return to_mathml(tex, display)


def unescape(s: str) -> str:
    return s.replace("\\u00a0", " ")


class Corpus(unittest.TestCase):
    def test_corpus_is_large_and_unique(self):
        items = load()
        ids = [i["id"] for i in items]
        self.assertGreaterEqual(len(items), 150)
        self.assertEqual(len(ids), len(set(ids)), "corpus ids must be unique")
        self.assertGreaterEqual(sum(1 for i in items if i.get("expect", "ok") == "error"), 30)

    def test_every_item(self):
        for item in load():
            with self.subTest(id=item["id"], tex=item["tex"]):
                if item.get("expect", "ok") == "ok":
                    try:
                        out = render(item)
                    except MathError as exc:
                        self.fail(f"{item['id']}: {exc}")
                    self.assertEqual(core_problems(out), [], item["id"])
                    body = out.split("<annotation")[0]
                    for s in item.get("has", []):
                        self.assertIn(unescape(s), body, f"{item['id']}: expected {s!r}")
                    for s in item.get("lacks", []):
                        self.assertNotIn(unescape(s), body, f"{item['id']}: did not expect {s!r}")
                    self.assertIn('encoding="application/x-tex"', out)
                else:
                    with self.assertRaises(MathError) as ctx:
                        render(item)
                    exc = ctx.exception
                    self.assertTrue(exc.message.strip(), item["id"])
                    self.assertTrue(exc.hint.strip(), f"{item['id']}: every error needs a 'write this instead'")
                    self.assertIsNotNone(exc.column, f"{item['id']}: every error needs a column")
                    if "error" in item:
                        self.assertIn(item["error"], exc.message, item["id"])
                    if "hint" in item:
                        self.assertIn(item["hint"], exc.hint, item["id"])
                    if "at" in item:
                        self.assertEqual([exc.offset, exc.column], item["at"], f"{item['id']}: position")

    def test_errors_never_name_the_machinery(self):
        words = re.compile(r"(?i)\b(python|latex2mathml|converter|pyodide|parser|token|exception)\b")
        for item in load():
            if item.get("expect") != "error":
                continue
            with self.subTest(id=item["id"]):
                with self.assertRaises(MathError) as ctx:
                    render(item)
                self.assertNotRegex(ctx.exception.message + " " + ctx.exception.hint, words)


if __name__ == "__main__":
    unittest.main()
