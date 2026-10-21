"""The Studio's view of the rest of the engine.

Other parts of Bazinga (markdown, checks, build, figures, drawings, llm, wiki) are imported lazily, on first use, so
the Studio starts and stays usable while one of them is missing or broken; the screen that needs it then says it is
"not available yet" instead of failing. Work that runs the author's own code (figures, drawings) or that depends on
a site root other than the Studio's (publish dry runs) goes through :mod:`bazinga.studio.worker` in a subprocess.
"""
from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
import threading
import traceback
from pathlib import Path

ENGINE_PARENT = Path(__file__).resolve().parents[2]   # the folder that holds the bazinga package
_lock = threading.RLock()


class Unavailable(Exception):
    """A part of the engine the Studio needs is not there (yet)."""

    def __init__(self, what: str, detail: str = ""):
        super().__init__(f"{what} is not available yet." + (f" ({detail})" if detail else ""))
        self.what, self.detail = what, detail


def module(name: str):
    """Import ``bazinga.<name>`` or raise Unavailable with a short reason."""
    try:
        return importlib.import_module(f"bazinga.{name}")
    except ModuleNotFoundError as exc:
        if exc.name in (f"bazinga.{name}", "bazinga"):
            raise Unavailable(_LABELS.get(name, name)) from None
        raise Unavailable(_LABELS.get(name, name), f"missing {exc.name}") from None
    except Exception as exc:  # noqa: BLE001 - a half-written module must not take the Studio down
        raise Unavailable(_LABELS.get(name, name), f"{type(exc).__name__}: {exc}") from None


def available(name: str) -> bool:
    try:
        module(name)
        return True
    except Unavailable:
        return False


_LABELS = {"markdown": "Rendering", "checks": "Checks", "build": "Preview", "figures": "Figures",
           "drawings": "Drawings", "llm": "Suggestions", "wiki": "The wiki files", "mathml": "Equations",
           "content": "Pages", "config": "Settings"}


def lock():
    """Calls into the engine share module state (config.ROOT, caches); the Studio runs them one at a time."""
    return _lock


# --- the site index ------------------------------------------------------------------------------------------------

def site_index(cfg, override=None):
    """The SiteIndex ``override`` (a Page, or None) is checked against: every page on disk, with ``override`` in
    place of its file's version. Uses core's ``checks.site_for`` so the Studio and the build agree on what a draft
    or a public page may link to."""
    content = module("content")
    md = module("markdown")
    by_id = {}
    for path in content.content_files(cfg):
        try:
            p = content.load_file(path, cfg)
        except Exception:  # noqa: BLE001 - a broken neighbour must not stop this page's checks
            continue
        by_id[p.id] = p
    if override is not None:
        by_id[override.id] = override
    refs = _safe(lambda: content.load_references(cfg), {})
    topics = _safe(lambda: content.load_topics(cfg), {})
    checks = _optional("checks")
    if override is not None and checks is not None and hasattr(checks, "site_for"):
        return checks.site_for(override, list(by_id.values()), refs, topics, cfg)
    return md.SiteIndex(list(by_id.values()), refs, topics, cfg, preview=True)


def _safe(fn, default):
    try:
        return fn()
    except Exception:  # noqa: BLE001
        return default


def _optional(name):
    try:
        return module(name)
    except Unavailable:
        return None


def parse(cfg, path: Path, text: str):
    return module("content").parse(text, path, cfg)


# --- subprocess worker ---------------------------------------------------------------------------------------------

MARK = "\x1eBAZINGA-RESULT "


def env_for(root: Path) -> dict:
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(p for p in (str(ENGINE_PARENT), env.get("PYTHONPATH", "")) if p)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.pop("PYTHONSTARTUP", None)
    return env


def worker(root: Path, op: str, args: dict, timeout: float = 60.0) -> dict:
    """Run one worker operation in a fresh interpreter with ``root`` as the site root. Returns its JSON result."""
    cmd = [sys.executable, "-m", "bazinga.studio.worker", op, json.dumps(args)]
    try:
        proc = subprocess.run(cmd, cwd=str(root), env=env_for(root), capture_output=True, text=True,
                              timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"Stopped after {int(timeout)} seconds without finishing.",
                "output": ""}
    out = proc.stdout or ""
    idx = out.rfind(MARK)
    if idx < 0:
        tail = (proc.stderr or out).strip()[-4000:]
        return {"ok": False, "error": tail or f"exited with code {proc.returncode}", "output": out[-4000:]}
    try:
        result = json.loads(out[idx + len(MARK):].strip().splitlines()[0])
    except (ValueError, IndexError):
        return {"ok": False, "error": "unreadable result", "output": out[-4000:]}
    result.setdefault("output", out[:idx][-4000:])
    if proc.stderr and not result.get("ok", True):
        result.setdefault("stderr", proc.stderr[-4000:])
    return result


def format_exc() -> str:
    return traceback.format_exc(limit=8)
