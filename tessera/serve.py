"""The development server: build, serve ``_site/`` on 127.0.0.1, rebuild on changes, reload the browser.

- Watches ``content/``, ``figures/``, ``drawings/``, ``static/``, ``theme/``, ``site.yml`` (and the engine's own theme)
  by polling modification times, so it needs no extra packages.
- Live reload uses a tiny Server-Sent Events endpoint (``/__tessera/events``). The script that listens to it is
  injected into HTML responses by this server only; built files never contain it.
- Errors in pages do not stop the server: they are printed and shown in the page (a lenient build).
- ``/api/ask/`` is passed to ``tessera.ask_server.handle`` when that module exists, so the "written answer" can be
  tried locally.
"""
from __future__ import annotations

import json
import mimetypes
import os
import sys
import threading
import time
import traceback
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from . import config

RELOAD_PATH = "/__tessera/events"
RELOAD_SCRIPT = (
    "<script>/* added by the development server only */(function(){if(!window.EventSource)return;"
    "var s=new EventSource('" + RELOAD_PATH + "');s.addEventListener('reload',function(){location.reload();});"
    "s.addEventListener('failed',function(e){console.warn('Tessera: the rebuild failed:\\n'+e.data);});})();</script>"
)
WATCH = ("content", "figures", "drawings", "static", "theme", "site.yml")
POLL_SECONDS = 0.5


class State:
    """Shared between the watcher thread and request handlers."""

    def __init__(self, cfg, drafts: bool = False):
        self.cfg = cfg
        self.drafts = drafts
        self.version = 0
        self.error = ""
        self.cond = threading.Condition()

    def bump(self, error: str = "") -> None:
        with self.cond:
            self.version += 1
            self.error = error
            self.cond.notify_all()


def snapshot(cfg) -> dict:
    """Modification times of every watched file (engine theme included, so theme work reloads too)."""
    from .build import ENGINE_THEME
    roots = [cfg.root / name for name in WATCH] + [ENGINE_THEME]
    stamps = {}
    for root in roots:
        if root.is_file():
            stamps[str(root)] = root.stat().st_mtime_ns
        elif root.is_dir():
            for p in root.rglob("*"):
                if p.is_file() and "__pycache__" not in p.parts and not p.name.startswith("."):
                    try:
                        stamps[str(p)] = p.stat().st_mtime_ns
                    except FileNotFoundError:
                        pass
    return stamps


def rebuild(state: State, quiet: bool = False) -> bool:
    """A lenient build: problems are printed and shown in pages, never fatal."""
    from .build import BuildError, build
    t0 = time.perf_counter()
    try:
        cfg = config.load(state.cfg.root)
        state.cfg = cfg
        result = build(cfg, drafts=state.drafts, strict=False, dev=True, quiet=True)
    except (BuildError, config.ConfigError, Exception) as exc:                 # noqa: BLE001 - keep serving
        msg = str(exc) if isinstance(exc, (BuildError, config.ConfigError)) else traceback.format_exc()
        print(f"\n  The build failed:\n{msg}", file=sys.stderr)
        state.bump(error=msg)
        return False
    errors = sum(1 for issues in result.issues.values() for i in issues if i.level == "error")
    if not quiet:
        extra = f", {errors} error(s) shown in the pages" if errors else ""
        print(f"  built {len(result.pages)} pages in {time.perf_counter() - t0:.2f}s{extra}")
        for msg in result.notes:
            print(f"  {msg}")
    state.bump()
    return True


def watch(state: State, stop: threading.Event) -> None:
    last = snapshot(state.cfg)
    while not stop.wait(POLL_SECONDS):
        now = snapshot(state.cfg)
        if now != last:
            changed = sorted(set(now) ^ set(last) | {k for k in now if last.get(k) != now[k]})
            last = now
            names = ", ".join(Path(c).name for c in changed[:3]) + (" …" if len(changed) > 3 else "")
            print(f"  changed: {names}")
            rebuild(state)
            last = snapshot(state.cfg)


def make_handler(state: State):
    class Handler(BaseHTTPRequestHandler):
        server_version = "TesseraDev"

        def log_message(self, fmt, *args):            # quiet: only errors are interesting
            if args and str(args[1]).startswith(("4", "5")) and RELOAD_PATH not in str(args[0]):
                sys.stderr.write("  %s %s\n" % (args[1], args[0]))

        # ---- routing
        def do_GET(self):
            path = urlsplit(self.path).path
            if path == RELOAD_PATH:
                return self.events()
            if path.rstrip("/") == "/api/ask":
                return self.ask("GET")
            return self.static(path)

        def do_HEAD(self):
            return self.static(urlsplit(self.path).path, head=True)

        def do_POST(self):
            if urlsplit(self.path).path.rstrip("/") == "/api/ask":
                return self.ask("POST")
            self.send_error(HTTPStatus.METHOD_NOT_ALLOWED)

        # ---- files
        def resolve(self, path: str) -> Path | None:
            out = state.cfg.out_dir.resolve()
            rel = unquote(path).lstrip("/")
            target = (out / rel).resolve()
            if out not in target.parents and target != out:
                return None
            if target.is_dir():
                target = target / "index.html"
            elif not target.exists() and not Path(rel).suffix:
                target = (out / rel / "index.html").resolve()
            return target if target.is_file() else None

        def static(self, path: str, head: bool = False):
            target = self.resolve(path)
            status = HTTPStatus.OK
            if target is not None and target.name == "index.html" and not path.endswith("/") and \
                    not path.endswith(".html"):
                self.send_response(HTTPStatus.MOVED_PERMANENTLY)
                self.send_header("Location", path + "/")
                self.end_headers()
                return
            if target is None:
                status = HTTPStatus.NOT_FOUND
                target = state.cfg.out_dir / "404.html"
                if not target.exists():
                    return self.send_error(HTTPStatus.NOT_FOUND)
            data = target.read_bytes()
            ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            if target.suffix == ".md":
                ctype = "text/markdown"
            if ctype == "text/html":
                data = inject_reload(data)
            if ctype.startswith("text/") or ctype in ("application/javascript", "application/json", "image/svg+xml"):
                ctype += "; charset=utf-8"
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            if not head:
                self.wfile.write(data)

        # ---- live reload
        def events(self):
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            seen = state.version
            try:
                self.wfile.write(b": connected\n\n")
                self.wfile.flush()
                while True:
                    with state.cond:
                        state.cond.wait_for(lambda: state.version != seen, timeout=15)
                        version, error = state.version, state.error
                    if version == seen:
                        self.wfile.write(b": ping\n\n")
                    else:
                        seen = version
                        if error:
                            payload = "\n".join("data: " + line for line in error.splitlines()[-20:])
                            self.wfile.write(f"event: failed\n{payload}\n\n".encode())
                        else:
                            self.wfile.write(b"event: reload\ndata: 1\n\n")
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, OSError):
                return

        # ---- /api/ask/
        def ask(self, method: str):
            try:
                from . import ask_server
            except ImportError:
                return self.json(HTTPStatus.NOT_FOUND, {"enabled": False, "error": "Written answers are not set up."})
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(min(length, 64 * 1024)) if length else b""
            env = dict(os.environ)
            env.update(_dotenv(state.cfg.root / ".env.local"))
            data_dir = state.cfg.out_dir / "data"

            def loader():
                def read(name, empty):
                    path = data_dir / name
                    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else empty
                return {"passages": read("passages.json", []), "graph": read("graph.json", None)}

            try:
                status, payload = ask_server.handle(method, body, self.client_address[0], env, loader,
                                                    cfg=state.cfg)
            except Exception as exc:                                               # noqa: BLE001
                status, payload = 500, {"error": f"The answer failed: {exc}"}
            self.json(status, payload)

        def json(self, status, payload):
            data = json.dumps(payload).encode()
            self.send_response(int(status))
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

    return Handler


class DevServer(ThreadingHTTPServer):
    """Threads per request; a browser closing a connection early is normal and not worth a traceback."""

    daemon_threads = True

    def handle_error(self, request, client_address):
        exc = sys.exc_info()[1]
        if isinstance(exc, (ConnectionResetError, BrokenPipeError, TimeoutError)):
            return
        super().handle_error(request, client_address)


def inject_reload(html: bytes) -> bytes:
    marker = b"</body>"
    idx = html.rfind(marker)
    script = RELOAD_SCRIPT.encode()
    return html[:idx] + script + html[idx:] if idx != -1 else html + script


def _dotenv(path: Path) -> dict:
    """KEY=value lines from .env.local (never committed)."""
    out = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                out[k.strip().removeprefix("export ").strip()] = v.strip().strip("'\"")
    return out


def serve(cfg=None, port: int = 8000, host: str = "127.0.0.1", watch_files: bool = True, open_browser: bool = False,
          drafts: bool = False):
    """Build, then serve until Ctrl+C. With ``drafts`` the preview includes drafts and scheduled pages."""
    cfg = cfg or config.load()
    state = State(cfg, drafts)
    print(f"Building {cfg['site']['name']} …")
    rebuild(state)
    httpd = DevServer((host, port), make_handler(state))
    stop = threading.Event()
    if watch_files:
        threading.Thread(target=watch, args=(state, stop), daemon=True).start()
    url = f"http://{host}:{httpd.server_address[1]}/"
    print(f"\n  Serving at {url}  (Ctrl+C to stop; pages reload when you save)\n")
    if open_browser:
        import webbrowser
        webbrowser.open(url)
    try:
        httpd.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        print("\n  Stopped.")
    finally:
        stop.set()
        httpd.server_close()
    return 0
