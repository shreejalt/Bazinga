"""The Studio is never part of the built site: building the example site copies no file of tessera/studio/ into
_site/, and nothing in _site/ refers to the Studio's addresses."""

import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STUDIO = ROOT / "tessera" / "studio"
SKIP = {".git", ".venv", "venv", "_site", "tessera", "node_modules", ".studio", "__pycache__", "proposals", ".worktrees"}


def studio_hashes() -> dict:
    out = {}
    for p in STUDIO.rglob("*"):
        if p.is_file() and "__pycache__" not in p.parts:
            out[hashlib.sha256(p.read_bytes()).hexdigest()] = str(p.relative_to(ROOT))
    return out


class NotInSite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import tessera.build  # noqa: F401
            import tessera.cli  # noqa: F401
        except ImportError as exc:
            raise unittest.SkipTest(f"the core build is not available yet ({exc})")
        cls.tmp = Path(tempfile.mkdtemp(prefix="studio-site-"))
        cls.site = cls.tmp / "site"
        cls.site.mkdir()
        for item in ROOT.iterdir():
            if item.name in SKIP:
                continue
            dest = cls.site / item.name
            if item.is_dir():
                shutil.copytree(item, dest, ignore=shutil.ignore_patterns("__pycache__"))
            else:
                shutil.copy2(item, dest)
        env = dict(os.environ, PYTHONPATH=str(ROOT))
        for args in (["build"], ["build", "--drafts"]):
            proc = subprocess.run([sys.executable, "-m", "tessera", *args], cwd=cls.site, env=env,
                                  capture_output=True, text=True, timeout=600)
            if proc.returncode != 0:
                raise AssertionError(f"build {' '.join(args)} failed:\n{proc.stdout[-2000:]}\n{proc.stderr[-2000:]}")
            mode = "drafts" if "--drafts" in args else "prod"
            out = cls.site / f"_site_{mode}"
            (cls.site / "_site").rename(out)
            setattr(cls, "out_" + mode, out)
            setattr(cls, "files_" + mode, [p for p in out.rglob("*") if p.is_file()])

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_built(self):
        self.assertTrue(self.files_prod)

    def test_no_studio_file_is_copied(self):
        hashes = studio_hashes()
        for out, files in ((self.out_prod, self.files_prod), (self.out_drafts, self.files_drafts)):
            for p in files:
                rel = p.relative_to(out)
                self.assertNotIn("studio", [part.lower() for part in rel.parts[:-1]], rel)
                self.assertNotIn(p.name, {"studio.js", "studio.css", "cm.js", "publish.js", "server.py", "api.py"}, rel)
                digest = hashlib.sha256(p.read_bytes()).hexdigest()
                self.assertNotIn(digest, hashes, f"{rel} is a copy of {hashes.get(digest)}")

    def test_no_page_points_at_the_studio(self):
        for p in self.files_prod:
            if p.suffix not in (".html", ".js", ".json", ".xml", ".txt", ".md", ".css"):
                continue
            text = p.read_text(encoding="utf-8", errors="replace")
            for needle in ("/_studio/", "tessera_studio_", "/api/publish", "/api/page/save"):
                self.assertNotIn(needle, text, p.relative_to(self.site))


if __name__ == "__main__":
    unittest.main()
