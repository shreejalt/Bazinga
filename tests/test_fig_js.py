"""The figure scripts: syntax (node --check), the pinned runtime, and plain visible wording."""

import re
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "tessera" / "theme" / "assets" / "js"
FILES = [JS / "figure.js", JS / "pyworker.js"]


class Scripts(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "node is not installed")
    def test_node_check(self):
        for f in FILES:
            with self.subTest(file=f.name):
                r = subprocess.run(["node", "--check", str(f)], capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, r.stderr)

    def test_pinned_runtime(self):
        urls = set()
        for f in FILES:
            urls |= set(re.findall(r"https://cdn\.jsdelivr\.net/pyodide/[^\"']+", f.read_text()))
        self.assertEqual(urls, {"https://cdn.jsdelivr.net/pyodide/v314.0.7/full/"})

    def test_module_worker(self):
        self.assertIn('{ type: "module" }', (JS / "figure.js").read_text())
        self.assertNotIn("importScripts", (JS / "pyworker.js").read_text())

    def test_visible_text_is_plain(self):
        src = (JS / "figure.js").read_text()
        shown = re.findall(r'(?:say|textContent\s*=)\(?\s*"([^"]*)"', src)
        self.assertTrue(shown)
        for s in shown:
            self.assertNotRegex(s, r"(?i)python|pyodide|worker|wasm")


if __name__ == "__main__":
    unittest.main()
