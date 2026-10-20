"""Version snapshots of pages, kept in ``.studio/history/<slug>/`` (git-ignored, local only).

A snapshot is taken on an explicit save, and on autosave at most once a minute. Identical content is never stored
twice, and only the newest ``KEEP`` snapshots of a page are kept.
"""
from __future__ import annotations

import re
import time
from pathlib import Path

from .security import Refused, atomic_write

KEEP = 60
AUTOSAVE_GAP = 60.0
_NAME = re.compile(r"^\d{8}-\d{6}-\d{3}\.md$")


def folder(root: Path, kind: str, slug: str) -> Path:
    base = Path(root) / ".studio"
    base.mkdir(exist_ok=True)
    ignore = base / ".gitignore"
    if not ignore.exists():
        ignore.write_text("*\n", encoding="utf-8")
    return base / "history" / kind / slug


def snapshot(root: Path, kind: str, slug: str, text: str, explicit: bool) -> str | None:
    """Store ``text`` as a snapshot when it is new (and, for autosaves, the last one is over a minute old)."""
    d = folder(root, kind, slug)
    d.mkdir(parents=True, exist_ok=True)
    items = sorted(p for p in d.iterdir() if _NAME.match(p.name))
    if items:
        last = items[-1]
        if last.read_text(encoding="utf-8") == text:
            return None
        if not explicit and time.time() - last.stat().st_mtime < AUTOSAVE_GAP:
            return None
    now = time.time()
    name = time.strftime("%Y%m%d-%H%M%S", time.localtime(now)) + f"-{int(now * 1000) % 1000:03d}.md"
    atomic_write(d / name, text)
    for old in items[: max(0, len(items) + 1 - KEEP)]:
        old.unlink(missing_ok=True)
    return name


def list_versions(root: Path, kind: str, slug: str) -> list[dict]:
    d = folder(root, kind, slug)
    if not d.is_dir():
        return []
    out = []
    for p in sorted((p for p in d.iterdir() if _NAME.match(p.name)), reverse=True):
        text = p.read_text(encoding="utf-8")
        out.append({"name": p.name, "time": p.stat().st_mtime, "words": len(text.split()), "size": len(text)})
    return out


def read_version(root: Path, kind: str, slug: str, name: str) -> str:
    if not _NAME.match(name or ""):
        raise Refused(400, "Unknown version.")
    p = folder(root, kind, slug) / name
    if not p.exists():
        raise Refused(404, "That version no longer exists.")
    return p.read_text(encoding="utf-8")


def move(root: Path, kind: str, old_slug: str, new_slug: str) -> None:
    old, new = folder(root, kind, old_slug), folder(root, kind, new_slug)
    if old.is_dir() and not new.exists():
        new.parent.mkdir(parents=True, exist_ok=True)
        old.rename(new)
