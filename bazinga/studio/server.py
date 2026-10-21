"""The Studio's HTTP server: local only.

``python -m bazinga studio [--port N] [--no-browser]`` binds 127.0.0.1 (a random free port unless ``--port``),
prints ``http://127.0.0.1:<port>/?token=<random>`` and opens the browser. Every request goes through
:meth:`Handler.guard`: Host allowlist, then the token cookie, then (for writes) Origin / Sec-Fetch-Site and a JSON
body. No CORS headers are sent, ever. See security.py for the reasons.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from . import security
from .api import STATIC_DIR, Studio, guess_type
from .security import Refused

BODY_LIMIT = 2 * 1024 * 1024
UPLOAD_BODY_LIMIT = security.UPLOAD_LIMIT * 4 // 3 + 64 * 1024

# CodeMirror 6 through esm.sh, exactly the map tested in docs/research.md §6. bazinga/vendor.py may define its own
# (CODEMIRROR_IMPORT_MAP); that one wins so every pinned URL lives in one place.
IMPORTMAP = {"imports": {
    "codemirror": "https://esm.sh/*codemirror@6.0.2",
    "@codemirror/state": "https://esm.sh/*@codemirror/state@6.7.6",
    "@codemirror/view": "https://esm.sh/*@codemirror/view@6.43.13",
    "@codemirror/commands": "https://esm.sh/*@codemirror/commands@6.11.1",
    "@codemirror/language": "https://esm.sh/*@codemirror/language@6.12.4",
    "@codemirror/autocomplete": "https://esm.sh/*@codemirror/autocomplete@6.20.3",
    "@codemirror/search": "https://esm.sh/*@codemirror/search@6.7.2",
    "@codemirror/lint": "https://esm.sh/*@codemirror/lint@6.9.7",
    "@codemirror/lang-markdown": "https://esm.sh/*@codemirror/lang-markdown@6.5.2",
    "@codemirror/lang-html": "https://esm.sh/*@codemirror/lang-html@6.4.12",
    "@codemirror/lang-css": "https://esm.sh/*@codemirror/lang-css@6.3.1",
    "@codemirror/lang-javascript": "https://esm.sh/*@codemirror/lang-javascript@6.2.5",
    "@lezer/common": "https://esm.sh/*@lezer/common@1.5.3",
    "@lezer/highlight": "https://esm.sh/*@lezer/highlight@1.2.5",
    "@lezer/lr": "https://esm.sh/*@lezer/lr@1.4.10",
    "@lezer/markdown": "https://esm.sh/*@lezer/markdown@1.7.2",
    "@lezer/html": "https://esm.sh/*@lezer/html@1.3.13",
    "@lezer/css": "https://esm.sh/*@lezer/css@1.3.8",
    "@lezer/javascript": "https://esm.sh/*@lezer/javascript@1.5.6",
    "style-mod": "https://esm.sh/style-mod@4.1.4",
    "w3c-keyname": "https://esm.sh/w3c-keyname@2.2.8",
    "crelt": "https://esm.sh/crelt@1.0.7",
    "@marijn/find-cluster-break": "https://esm.sh/@marijn/find-cluster-break@1.0.4",
}}
FONTS_CSS = ("https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500"
             "&family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;0,8..60,700;1,8..60,400"
             "&family=STIX+Two+Math&display=swap")


def importmap() -> dict:
    try:
        from bazinga import vendor
        m = getattr(vendor, "CODEMIRROR_IMPORT_MAP", None)
        if isinstance(m, dict) and m.get("imports"):
            return m
        if isinstance(m, dict) and m:
            return {"imports": m}
    except Exception:  # noqa: BLE001
        pass
    return IMPORTMAP


class StudioServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False

    def __init__(self, root: Path, port: int = 0, token: str | None = None):
        super().__init__(("127.0.0.1", port), Handler)
        self.port = self.server_address[1]
        self.token = token or security.new_token()
        self.studio = Studio(root)
        self.cookie = security.cookie_name(self.port)
        self._index = None

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/?token={self.token}"

    def index_html(self) -> tuple[str, str]:
        """The app page with the import map inlined, and the CSP that allows exactly that inline script."""
        if self._index is None or os.environ.get("BAZINGA_STUDIO_DEV"):
            m = json.dumps(importmap(), indent=1)
            script = f'<script type="importmap">{m}</script>'
            digest = base64.b64encode(hashlib.sha256(m.encode()).digest()).decode()
            html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
            html = html.replace("<!--IMPORTMAP-->", script).replace("{{FONTS}}", FONTS_CSS)
            csp = ("default-src 'none'; "
                   f"script-src 'self' 'sha256-{digest}' https://esm.sh; "
                   "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                   "font-src https://fonts.gstatic.com data:; img-src 'self' data: blob:; "
                   "connect-src 'self' https://esm.sh; frame-src 'self'; base-uri 'none'; form-action 'none'; "
                   "frame-ancestors 'none'")
            self._index = (html, csp)
        return self._index


ROUTES_GET = {
    "/api/state": "state", "/api/pages": "list_pages", "/api/page": "get_page",
    "/api/checks/summary": "checks_summary", "/api/history": "history_list", "/api/history/version": "history_read",
    "/api/code": "read_code", "/api/starters": "starters",
}
ROUTES_POST = {
    "/api/page/save": "save_page", "/api/page/new": "new_page", "/api/page/rename": "rename_page",
    "/api/preview": "preview", "/api/check": "check", "/api/math": "math",
    "/api/figures/run": "figures_run", "/api/figures/new": "figure_new", "/api/figures/save": "figure_save",
    "/api/figures/draft": "figure_draft", "/api/drawings/new": "drawing_new", "/api/drawings/save": "drawing_save",
    "/api/drawings/preview": "drawing_preview", "/api/cite/lookup": "cite_lookup", "/api/cite/save": "cite_save",
    "/api/topics/add": "topic_add", "/api/upload": "upload", "/api/llm/describe": "llm_describe",
    "/api/llm/equation": "llm_equation", "/api/llm/ingest": "llm_ingest", "/api/publish/prepare": "publish_prepare",
}
# The figure panel (figpanel.py): gallery, figure builder, checking code before it is saved.
ROUTES_GET.update({"/api/figures/gallery": "figures_gallery", "/api/figures/open": "figure_open",
                   "/api/builder/info": "builder_info"})
ROUTES_POST.update({"/api/builder/preview": "builder_preview", "/api/builder/save": "builder_save",
                    "/api/figures/check": "figure_check", "/api/figures/save-code": "figure_save_code"})
# The diagram panel (diagrampanel.py): text diagrams drawn as you type, and the examples gallery.
ROUTES_GET.update({"/api/diagram/examples": "diagram_examples"})
ROUTES_POST.update({"/api/diagram/render": "diagram_render"})


class Handler(BaseHTTPRequestHandler):
    server: StudioServer
    server_version = "BazingaStudio"
    sys_version = ""
    protocol_version = "HTTP/1.0"

    # --- transport -------------------------------------------------------------------------------------------------
    def log_message(self, fmt, *args):  # quiet: only failures are printed
        if getattr(self.server, "quiet", False):
            return
        if args and isinstance(args[1] if len(args) > 1 else None, str) and str(args[1])[:1] in "45":
            sys.stderr.write("studio: %s\n" % (fmt % args))

    def _headers(self, status: int, ctype: str, length: int | None = None, extra: dict | None = None):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        if length is not None:
            self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()

    def send(self, status: int, body: bytes | str, ctype: str, extra: dict | None = None):
        raw = body.encode("utf-8") if isinstance(body, str) else body
        self._headers(status, ctype, len(raw), extra)
        if self.command != "HEAD":
            self.wfile.write(raw)

    def send_json(self, status: int, obj):
        self.send(status, json.dumps(obj, default=str), "application/json; charset=utf-8")

    def refuse(self, exc: Refused):
        if self.path.startswith("/api/"):
            self.send_json(exc.status, {"error": exc.message})
        else:
            from .api import _message_page
            self.send(exc.status, _message_page("Bazinga Studio", exc.message), "text/html; charset=utf-8",
                      {"X-Frame-Options": "DENY"})

    # --- the guard -------------------------------------------------------------------------------------------------
    def guard(self, write: bool) -> bool:
        """True when the request may proceed (Host, token cookie, and for writes Origin + JSON)."""
        port = self.server.port
        try:
            security.check_host(self.headers.get("Host"), port)
            url = urlsplit(self.path)
            if url.path == "/" and "token" in parse_qs(url.query) and self.command == "GET":
                return self._exchange_token(parse_qs(url.query)["token"][0])
            cookies = security.parse_cookies(self.headers.get("Cookie"))
            if not security.same_token(cookies.get(self.server.cookie), self.server.token):
                raise Refused(401, "Open the Studio with the link printed in the terminal.")
            if write:
                security.check_write(self.headers, port)
            return True
        except Refused as exc:
            self.refuse(exc)
            return False

    def _exchange_token(self, token: str) -> bool:
        if not security.same_token(token, self.server.token):
            self.refuse(Refused(403, "This link is not valid any more. Use the link printed in the terminal."))
            return False
        cookie = f"{self.server.cookie}={self.server.token}; HttpOnly; SameSite=Strict; Path=/"
        self.send(303, b"", "text/plain", {"Location": "/", "Set-Cookie": cookie})
        return False

    # --- methods ---------------------------------------------------------------------------------------------------
    def do_GET(self):
        if not self.guard(write=False):
            return
        try:
            self._get()
        except Refused as exc:
            self.refuse(exc)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as exc:  # noqa: BLE001
            self._crash(exc)

    do_HEAD = do_GET

    def do_POST(self):
        if not self.guard(write=True):
            return
        try:
            data = self._read_json()
            path = urlsplit(self.path).path
            if path == "/api/publish/run":
                return self._publish_stream(data)
            name = ROUTES_POST.get(path)
            if not name:
                raise Refused(404, "Unknown action.")
            self.send_json(200, getattr(self.server.studio, name)(data))
        except Refused as exc:
            self.refuse(exc)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as exc:  # noqa: BLE001
            self._crash(exc)

    def _not_allowed(self):
        if not self.guard(write=False):
            return
        self.send_json(405, {"error": "Not allowed."})

    do_PUT = do_DELETE = do_PATCH = do_OPTIONS = _not_allowed

    def _crash(self, exc):
        import traceback
        traceback.print_exc()
        try:
            self.send_json(500, {"error": f"{type(exc).__name__}: {exc}"})
        except Exception:  # noqa: BLE001
            pass

    def _read_json(self) -> dict:
        path = urlsplit(self.path).path
        limit = UPLOAD_BODY_LIMIT if path == "/api/upload" else BODY_LIMIT
        try:
            length = int(self.headers.get("Content-Length") or "x")
        except ValueError:
            raise Refused(411, "A JSON body with a length is required.") from None
        if length > limit:
            raise Refused(413, "That request is too large." if path != "/api/upload" else
                          f"Images can be at most {security.UPLOAD_LIMIT // (1024 * 1024)} MB.")
        raw = self.rfile.read(length) if length else b""
        try:
            data = json.loads(raw or b"{}")
        except ValueError:
            raise Refused(400, "The request body is not valid JSON.") from None
        if not isinstance(data, dict):
            raise Refused(400, "The request body must be a JSON object.")
        return data

    def _get(self):
        url = urlsplit(self.path)
        path = unquote(url.path)
        if "\x00" in path or "/../" in path + "/" or "\\" in path:
            raise Refused(400, "Invalid address.")
        q = {k: v[0] for k, v in parse_qs(url.query).items()}
        studio = self.server.studio
        if path in ("/", "/index.html"):
            html, csp = self.server.index_html()
            return self.send(200, html, "text/html; charset=utf-8",
                             {"Content-Security-Policy": csp, "X-Frame-Options": "DENY"})
        if path.startswith("/_studio/"):
            rel = path[len("/_studio/"):]
            p = (STATIC_DIR / rel).resolve()
            if not re.fullmatch(r"[A-Za-z0-9_./-]+", rel) or not str(p).startswith(str(STATIC_DIR) + os.sep) \
                    or not p.is_file():
                raise Refused(404, "Not found.")
            return self.send(200, p.read_bytes(), guess_type(p))
        if path in ROUTES_GET:
            return self.send_json(200, getattr(studio, ROUTES_GET[path])(q))
        if path.startswith("/api/"):
            raise Refused(404, "Unknown address.")
        frame = {"X-Frame-Options": "SAMEORIGIN", "Content-Security-Policy": "frame-ancestors 'self'"}
        m = re.fullmatch(r"/preview/([a-z0-9-]+:[a-z0-9][a-z0-9-]*)/?", path)
        if m:
            status, html = studio.preview_get(m.group(1))
            return self.send(status, html, "text/html; charset=utf-8", frame)
        m = re.fullmatch(r"/frame/draft/([a-z][a-z0-9_]*)", path)
        if m:
            status, html = studio.draft_frame(m.group(1), q)
            return self.send(status, html, "text/html; charset=utf-8", frame)
        m = re.fullmatch(r"/frame/(figure|drawing)/([A-Za-z0-9_.]+)", path)
        if m:
            status, html = studio.frame(m.group(1), m.group(2), q)
            return self.send(status, html, "text/html; charset=utf-8", frame)
        pid = studio.route_page(path)
        if pid:
            status, html = studio.preview_get(pid)
            return self.send(status, html, "text/html; charset=utf-8", frame)
        draft = studio.draft_file(path)
        if draft is not None:
            return self.send(200, draft.read_bytes(), guess_type(draft))
        gen = studio.generated_asset(path)
        if gen is not None:
            return self.send(200, gen[0], gen[1])
        f = studio.preview_file(path)
        if f is not None:
            return self.send(200, f.read_bytes(), guess_type(f))
        raise Refused(404, "Not found.")

    def _publish_stream(self, data):
        """The publish log as server-sent events on the POST's own response (read with fetch, not EventSource)."""
        self._headers(200, "text/event-stream; charset=utf-8")
        alive = {"ok": True}
        lock = threading.Lock()

        def emit(event, payload):
            if not alive["ok"]:
                return
            chunk = f"event: {event}\ndata: {json.dumps(payload, default=str)}\n\n".encode("utf-8")
            with lock:
                try:
                    self.wfile.write(chunk)
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    alive["ok"] = False   # the page went away; the pipeline still finishes

        try:
            self.server.studio.publish_run(data, emit)
        except Refused as exc:
            emit("done", {"ok": False, "error": exc.message})


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="bazinga studio", description="The local editor (127.0.0.1 only).")
    ap.add_argument("--port", type=int, default=0, help="port on 127.0.0.1 (default: a free one)")
    ap.add_argument("--no-browser", action="store_true", help="do not open the browser")
    ap.add_argument("--root", default=None, help="the site folder (default: the current folder)")
    args = list(sys.argv[1:] if argv is None else argv)
    a = ap.parse_args([x for x in args if x != "--"])
    root = Path(a.root or os.getcwd()).resolve()
    try:
        from bazinga import config
        config.set_root(root)
        config.load(root)
    except Exception as exc:  # noqa: BLE001
        print(f"Cannot start the Studio: {exc}", file=sys.stderr)
        return 1
    try:
        server = StudioServer(root, a.port)
    except OSError as exc:
        print(f"Cannot listen on 127.0.0.1:{a.port}: {exc}", file=sys.stderr)
        return 1
    print(f"Bazinga Studio for {root}")
    print(f"  {server.url}")
    print("  Local only: this address works on this computer and nowhere else. Press Ctrl+C to stop.", flush=True)
    if not a.no_browser:
        threading.Timer(0.3, lambda: webbrowser.open(server.url)).start()
    try:
        server.serve_forever(poll_interval=0.3)
    except KeyboardInterrupt:
        print("\nStudio stopped.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
