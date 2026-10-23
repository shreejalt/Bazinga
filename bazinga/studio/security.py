"""The Editor's guards: who may talk to it, where it may write, and how it writes.

The Editor can change files and run git, so a web page the author happens to visit must never be able to reach it.
The rules (docs/research.md §3, after Vite's CVE-2025-24010):

1. The server binds 127.0.0.1 only (server.py).
2. ``Host`` must be ``127.0.0.1:<port>`` or ``localhost:<port>``; anything else is refused, which stops DNS rebinding
   (an attacker's name pointing at 127.0.0.1 still sends the attacker's name as Host).
3. Every request needs the per-launch token. It arrives once in the launch URL and is swapped for an HttpOnly,
   ``SameSite=Strict`` cookie; the cookie's name carries the port because cookies are shared between ports.
4. A write is a POST with a JSON body, an ``Origin`` equal to the Editor's own origin (or, without Origin,
   ``Sec-Fetch-Site: same-origin``) and the per-launch write key in the ``X-Bazinga-Write`` header. The key is
   written into the Editor's own page only, so a script that runs anywhere else (a preview, a figure) cannot write
   even when it reaches the Editor with the cookie. Cross-site form posts and fetches are refused.
5. No CORS headers are ever sent.
5a. Previews run the page's own scripts, so they are served from a second port (another origin): they cannot read
   the Editor's pages or its answers, and their writes carry the wrong Origin and no write key.
6. Paths are resolved (symlinks included) and must stay inside the allowed folders.
7. Files are written atomically: a temp file in the same folder, fsync, then ``os.replace``.
"""
from __future__ import annotations

import hmac
import os
import secrets
import tempfile
from pathlib import Path

# Folders (relative to the site root) the Editor may write into, and single files it may write.
WRITE_DIRS = ("content", "figures", "drawings", "static/uploads")
WRITE_FILES = ("content/references.yml", "content/topics.yml")

# Uploads: images only, checked by their first bytes, not by the name the browser gives.
UPLOAD_LIMIT = 8 * 1024 * 1024
IMAGE_TYPES = {
    "png": (b"\x89PNG\r\n\x1a\n",),
    "jpg": (b"\xff\xd8\xff",),
    "gif": (b"GIF87a", b"GIF89a"),
    "webp": (b"RIFF",),           # plus "WEBP" at offset 8, checked below
    "avif": (b"",),               # "ftypavif" at offset 4, checked below
}


class Refused(Exception):
    """A request or path the Editor will not serve. ``status`` is the HTTP status to answer with."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status, self.message = status, message


def new_token() -> str:
    return secrets.token_urlsafe(32)


def cookie_name(port: int) -> str:
    return f"bazinga_studio_{port}"


def same_token(a: str | None, b: str) -> bool:
    return bool(a) and hmac.compare_digest(str(a).encode(), b.encode())


def allowed_hosts(port: int) -> set[str]:
    return {f"127.0.0.1:{port}", f"localhost:{port}"}


def allowed_origins(port: int) -> set[str]:
    return {f"http://127.0.0.1:{port}", f"http://localhost:{port}"}


def check_host(host: str | None, port: int) -> None:
    if not host or host.strip().lower() not in allowed_hosts(port):
        raise Refused(403, "This address is not allowed. Open the Editor at the link it printed in the terminal.")


WRITE_HEADER = "X-Bazinga-Write"


def check_write(headers, port: int, key: str | None = None) -> None:
    """A state-changing request must come from the Editor's own page, carry its write key and be JSON."""
    origin = headers.get("Origin")
    site = (headers.get("Sec-Fetch-Site") or "").strip().lower()
    if origin is not None:
        if origin.strip().lower() not in allowed_origins(port):
            raise Refused(403, "Writes are accepted only from the Editor's own page.")
    elif site != "same-origin":
        raise Refused(403, "Writes are accepted only from the Editor's own page.")
    if site and site not in ("same-origin", "none"):
        raise Refused(403, "Writes are accepted only from the Editor's own page.")
    if key is not None and not same_token(headers.get(WRITE_HEADER), key):
        raise Refused(403, "Writes are accepted only from the Editor's own page. Reload the Editor.")
    ctype = (headers.get("Content-Type") or "").split(";")[0].strip().lower()
    if ctype != "application/json":
        raise Refused(415, "Writes must be JSON.")


def parse_cookies(header: str | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for part in (header or "").split(";"):
        if "=" in part:
            k, v = part.split("=", 1)
            out[k.strip()] = v.strip()
    return out


# --- paths -------------------------------------------------------------------------------------------------------

def confine(root: Path, rel: str | Path, write: bool = True) -> Path:
    """Resolve ``rel`` under ``root`` and make sure it lands inside an allowed folder or file.

    ``Path.resolve`` follows symlinks, so a link inside ``content/`` that points elsewhere is caught too. The
    allowed folders themselves are resolved as well (a site may legitimately keep ``static`` behind a link only if
    the link stays inside the root).
    """
    root = Path(root).resolve()
    rel = str(rel)
    if not rel or "\x00" in rel:
        raise Refused(400, "Empty or invalid path.")
    candidate = Path(rel)
    if candidate.is_absolute():
        raise Refused(403, "Paths must be relative to the site folder.")
    target = (root / candidate).resolve()
    if not _within(target, root):
        raise Refused(403, "That path is outside the site folder.")
    for name in WRITE_FILES:
        if target == (root / name).resolve():
            return target
    for name in WRITE_DIRS:
        base = (root / name).resolve()
        if not _within(base, root):
            raise Refused(403, f"{name}/ points outside the site folder.")
        if _within(target, base) and target != base:
            return target
    raise Refused(403, "The Editor only writes in content/, figures/, drawings/ and static/uploads/.")


def _within(path: Path, base: Path) -> bool:
    try:
        path.relative_to(base)
        return True
    except ValueError:
        return False


def atomic_write(path: Path, data: str | bytes) -> None:
    """Write ``data`` to ``path`` so that readers see the old file or the new one, never half of it."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = data.encode("utf-8") if isinstance(data, str) else data
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(raw)
            fh.flush()
            os.fsync(fh.fileno())
        if path.exists():
            try:
                os.chmod(tmp, path.stat().st_mode & 0o777)
            except OSError:
                pass
        else:
            os.chmod(tmp, 0o644)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def image_type(data: bytes) -> str | None:
    """The image type from the file's first bytes, or None when it is not an allowed image."""
    if data.startswith(IMAGE_TYPES["png"][0]):
        return "png"
    if data.startswith(IMAGE_TYPES["jpg"][0]):
        return "jpg"
    if data[:6] in IMAGE_TYPES["gif"]:
        return "gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    if data[4:12] in (b"ftypavif", b"ftypavis"):
        return "avif"
    return None
