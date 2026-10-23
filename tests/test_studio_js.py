"""The Editor's scripts: syntax, the pinned editor imports, and plain wording on screen.

``node --check file.js`` exits 0 on an ES module with a syntax error (Node's module detection hides it), so every file
is checked as a ``.mjs`` copy, which Node always parses as a module.
"""

import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "bazinga" / "studio" / "static"
FILES = sorted(STATIC.rglob("*.js"))


class Scripts(unittest.TestCase):
    def test_files_exist(self):
        names = {p.name for p in FILES}
        for n in ("studio.js", "editor.js", "cm.js", "preview.js", "library.js", "lib.js", "publish.js", "equation.js",
                  "figures.js", "cite.js", "details.js", "checks.js"):
            self.assertIn(n, names)

    @unittest.skipUnless(shutil.which("node"), "node is not installed")
    def test_node_check_as_modules(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.mjs"
            bad.write_text("export function f( {\n", encoding="utf-8")
            r = subprocess.run(["node", "--check", str(bad)], capture_output=True, text=True)
            self.assertNotEqual(r.returncode, 0, "node --check must catch a broken module")
            for f in FILES:
                with self.subTest(file=str(f.relative_to(STATIC))):
                    copy = Path(tmp) / (f.stem + ".mjs")
                    copy.write_text(f.read_text(encoding="utf-8"), encoding="utf-8")
                    r = subprocess.run(["node", "--check", str(copy)], capture_output=True, text=True)
                    self.assertEqual(r.returncode, 0, r.stderr)

    def test_imports_are_relative_or_in_the_import_map(self):
        from bazinga.studio.server import importmap
        mapped = set(importmap()["imports"])
        for f in FILES:
            for spec in re.findall(r'(?:from|import)\s*\(?\s*"([^"]+)"', f.read_text(encoding="utf-8")):
                with self.subTest(file=f.name, spec=spec):
                    self.assertTrue(spec.startswith("./") or spec.startswith("../") or spec in mapped, spec)

    def test_import_map_is_pinned(self):
        from bazinga.studio.server import IMPORTMAP, importmap
        for m in (IMPORTMAP, importmap()):
            for name, url in m["imports"].items():
                with self.subTest(name=name):
                    self.assertRegex(url, r"^https://esm\.sh/\*?(@[\w-]+/)?[\w-]+@\d+\.\d+\.\d+$")

    def test_no_machinery_named_on_screen(self):
        words = re.compile(r"(?i)\b(python|pyodide|openrouter|openai|gpt|llama|ollama|claude|BM25|subprocess)\b")
        for f in list(FILES) + [STATIC / "index.html"]:
            text = f.read_text(encoding="utf-8")
            # visible strings: the contents of "..." and `...` literals, minus code-ish ones (imports, selectors)
            for s in re.findall(r'"([^"\n]{3,})"|`([^`\n]{3,})`', text):
                s = s[0] or s[1]
                if s.startswith(("@codemirror", "./", "../", "/api/", "/_studio/")) or "python" == s:
                    continue
                with self.subTest(file=f.name, text=s[:60]):
                    self.assertNotRegex(s if "```python" not in s else s.replace("```python", ""), words)

    def test_writes_send_json(self):
        lib = (STATIC / "lib.js").read_text(encoding="utf-8")
        self.assertIn('"Content-Type": "application/json"', lib)
        self.assertNotRegex("\n".join(f.read_text(encoding="utf-8") for f in FILES), r"new FormData|EventSource\(")


    def test_writes_carry_the_write_key(self):
        lib = (STATIC / "lib.js").read_text(encoding="utf-8")
        self.assertIn('"X-Bazinga-Write": WRITE_KEY', lib)
        self.assertNotIn('headers: { "Content-Type": "application/json" }', lib)


class Layout(unittest.TestCase):
    """M3 and the Editor's phone fixes (device audit)."""

    def setUp(self):
        self.css = (STATIC / "studio.css").read_text(encoding="utf-8")
        narrow = self.css[self.css.index("@media (max-width: 980px)"):]
        self.narrow = narrow[:narrow.index("\n}\n")]

    def test_preview_alone_fills_a_narrow_screen(self):
        # the wide rule ".ed-main.only-preview { grid-template-columns: 0 0 ... }" must be overridden on narrow screens
        self.assertIn('.ed-main.only-preview { grid-template-columns: minmax(0, 1fr); grid-template-areas: "preview"; }',
                      self.narrow)
        self.assertRegex(self.css, r"\.ed-main \{[^}]*grid-row: 3;")
        js = (STATIC / "editor.js").read_text(encoding="utf-8")
        self.assertIn('matchMedia("(max-width: 980px)")', js)

    def test_top_bar_and_tabs_do_not_overlap_or_overflow(self):
        self.assertIn(".ed-top-left, .ed-top-right { display: flex; align-items: center; gap: 6px; flex: none; }", self.css)
        self.assertIn(".ed-top { overflow-x: auto;", self.narrow)
        self.assertRegex(self.css, r"\.tabs \{[^}]*overflow-x: auto")
        self.assertIn("height: 100dvh", self.css)


if __name__ == "__main__":
    unittest.main()
