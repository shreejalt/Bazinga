"""Vercel Python function for /api/ask/: the "written answer".

A thin wrapper over ``bazinga.ask_server.handle``. It reads ``site.yml`` for the ``llm:`` and ``ask:`` defaults, the
key from the environment variable named by ``llm.key_env`` (set it in the Vercel project, never in a file), and the
passages from the deployed ``/data/passages.json`` (``SITE_URL`` or the request's own host). Nothing is stored.
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

_cache = {"data": None, "at": 0.0, "cfg": None}
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


def _loader(host):
    def load():
        now = time.time()
        if _cache["data"] is not None and now - _cache["at"] < CACHE_SECONDS:
            return _cache["data"]
        data = None
        for local in (ROOT / "_site" / "data", ROOT / "data"):
            if (local / "passages.json").exists():
                data = {"passages": json.loads((local / "passages.json").read_text(encoding="utf-8"))}
                if (local / "graph.json").exists():
                    data["graph"] = json.loads((local / "graph.json").read_text(encoding="utf-8"))
                break
        if data is None:
            base = (os.environ.get("SITE_URL") or (f"https://{host}" if host else "")).rstrip("/")
            if not base:
                raise RuntimeError("no SITE_URL and no host")
            data = {"passages": _fetch(base + "/data/passages.json")}
            try:
                data["graph"] = _fetch(base + "/data/graph.json")
            except Exception:
                data["graph"] = None
        _cache.update(data=data, at=now)
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
        host = self.headers.get("x-forwarded-host") or self.headers.get("host") or ""
        status, out = ask_server.handle(method, body, self._ip(), dict(os.environ), _loader(host), cfg=_cfg())
        self._send(status, out)

    def do_GET(self):
        self._run("GET")

    def do_POST(self):
        n = int(self.headers.get("content-length") or 0)
        if n > 8192:
            self._send(413, {"error": "Too long."})
            return
        self._run("POST", self.rfile.read(n) if n else b"")

    def log_message(self, *args):   # never log questions
        pass
