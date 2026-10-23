"""Vercel Python function for /api/ask/: the "written answer".

A thin wrapper over ``bazinga.ask_server.handle``. It reads ``site.yml`` for the ``llm:`` and ``ask:`` defaults, the
key from the environment variable named by ``llm.key_env`` (set it in the Vercel project, never in a file), and the
passages from the deployed ``/data/passages.json``. The site's address comes from the ``SITE_URL`` environment variable
or ``site.origin`` in site.yml, never from the request (a visitor chooses the Host header). Passages whose link is not
on the site are dropped. Nothing is stored.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from http.server import BaseHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bazinga import ask_server  # noqa: E402

_cache = {"data": {}, "cfg": None}     # data: base URL -> (time, data)
CACHE_SECONDS = 600


def _cfg():
    if _cache["cfg"] is None:
        cfg = {}
        try:
            import yaml
            cfg = yaml.safe_load((ROOT / "site.yml").read_text(encoding="utf-8")) or {}
        except Exception:
            cfg = {}
        _cache["cfg"] = cfg if isinstance(cfg, dict) else {}
    return _cache["cfg"]


def _base() -> str:
    """The site's own address: SITE_URL, else site.origin. Never the request's Host."""
    base = (os.environ.get("SITE_URL") or "").strip()
    if not base:
        site = _cfg().get("site")
        base = str((site or {}).get("origin") or "").strip() if isinstance(site, dict) else ""
    base = base.rstrip("/")
    if not base.startswith(("https://", "http://")) or base in ("https://example.com", "http://example.com"):
        return ""
    return base


def on_site(url, base: str) -> bool:
    """A passage's link must be a path on this site or start with the site's own address."""
    url = str(url or "")
    if url.startswith("/") and not url.startswith("//"):
        return True
    return bool(base) and (url == base or url.startswith(base + "/"))


def _clean(data: dict, base: str) -> dict:
    ps = data.get("passages")
    data["passages"] = [p for p in ps if isinstance(p, dict) and on_site(p.get("url"), base)] \
        if isinstance(ps, list) else []
    return data


def _loader(base: str):
    def load():
        now = time.time()
        hit = _cache["data"].get(base)
        if hit is not None and now - hit[0] < CACHE_SECONDS:
            return hit[1]
        data = None
        for local in (ROOT / "_site" / "data", ROOT / "data"):
            if (local / "passages.json").exists():
                data = {"passages": json.loads((local / "passages.json").read_text(encoding="utf-8"))}
                if (local / "graph.json").exists():
                    data["graph"] = json.loads((local / "graph.json").read_text(encoding="utf-8"))
                break
        if data is None:
            if not base:
                raise RuntimeError("The site's address is not set: set SITE_URL in the project's environment "
                                   "or site.origin in site.yml.")
            data = {"passages": _fetch(base + "/data/passages.json")}
            try:
                data["graph"] = _fetch(base + "/data/graph.json")
            except Exception:
                data["graph"] = None
        data = _clean(data, base)
        _cache["data"][base] = (now, data)
        return data
    return load


def _fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "bazinga-ask"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode("utf-8"))


class handler(BaseHTTPRequestHandler):
    def _ip(self):
        fwd = self.headers.get("x-forwarded-for") or ""
        return fwd.split(",")[0].strip() or self.headers.get("x-real-ip") or self.client_address[0]

    def _send(self, status, body):
        data = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _run(self, method, body=b""):
        base = _base()
        if not base and not any((d / "passages.json").exists() for d in (ROOT / "_site" / "data", ROOT / "data")):
            self._send(503, {"on": False, "error": "The written answer is off: the site's address is not set. Set "
                                                   "SITE_URL in the project's environment or site.origin in site.yml."})
            return
        status, out = ask_server.handle(method, body, self._ip(), dict(os.environ), _loader(base), cfg=_cfg())
        self._send(status, out)

    def do_GET(self):
        self._run("GET")

    def do_POST(self):
        raw = (self.headers.get("content-length") or "0").strip()
        if not (raw.isascii() and raw.isdigit()):
            self._send(411, {"error": "A body with a length is required."})
            return
        n = int(raw)
        if n > 8192:
            self._send(413, {"error": "Too long."})
            return
        self._run("POST", self.rfile.read(n) if n else b"")

    def log_message(self, *args):   # never log questions
        pass
