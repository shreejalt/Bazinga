"""Look up a paper by arXiv id/URL or DOI and add it to ``content/references.yml``.

Core's citation helpers are used when they exist (``bazinga.cite``); otherwise the arXiv API and Crossref are called
directly. Records are shown to the author before anything is saved.
"""
from __future__ import annotations

import json
import re
import unicodedata
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml

from .security import Refused, atomic_write

_ARXIV = re.compile(r"(?:arxiv\.org/(?:abs|pdf|html)/|arxiv:\s*)?(\d{4}\.\d{4,5}|[a-z\-]+(?:\.[A-Z]{2})?/\d{7})"
                    r"(?:v\d+)?(?:\.pdf)?", re.I)
_DOI = re.compile(r"(10\.\d{4,9}/[^\s\"<>]+)", re.I)
UA = "Bazinga/0.1 (static-site engine; citation lookup)"


def parse_query(q: str) -> tuple[str, str]:
    q = (q or "").strip()
    m = _DOI.search(q)
    if m and "arxiv" not in q.lower():
        return "doi", m.group(1).rstrip(".")
    m = _ARXIV.search(q)
    if m:
        return "arxiv", m.group(1)
    if m := _DOI.search(q):
        return "doi", m.group(1).rstrip(".")
    raise Refused(400, "Paste an arXiv id or link (e.g. 1706.03762) or a DOI (e.g. 10.1145/3065386).")


def _get(url: str, accept: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310 - fixed https hosts only
            return resp.read(2_000_000)
    except Exception as exc:  # noqa: BLE001
        raise Refused(502, f"Could not reach the lookup service: {exc}") from None


def arxiv(arxiv_id: str) -> dict:
    data = _get("https://export.arxiv.org/api/query?id_list=" + urllib.parse.quote(arxiv_id), "application/atom+xml")
    ns = {"a": "http://www.w3.org/2005/Atom", "x": "http://arxiv.org/schemas/atom"}
    root = ET.fromstring(data)
    entry = root.find("a:entry", ns)
    if entry is None or entry.find("a:title", ns) is None:
        raise Refused(404, f"arXiv has no paper {arxiv_id}.")
    title = " ".join((entry.findtext("a:title", "", ns) or "").split())
    if not title or title.lower() == "error":
        raise Refused(404, f"arXiv has no paper {arxiv_id}.")
    authors = [" ".join((a.findtext("a:name", "", ns) or "").split()) for a in entry.findall("a:author", ns)]
    published = entry.findtext("a:published", "", ns) or ""
    rec = {"title": title, "authors": authors, "year": int(published[:4]) if published[:4].isdigit() else None,
           "venue": "arXiv", "arxiv": arxiv_id}
    journal = entry.findtext("x:journal_ref", "", ns)
    doi = entry.findtext("x:doi", "", ns)
    if journal:
        rec["venue"] = " ".join(journal.split())
    if doi:
        rec["doi"] = doi.strip()
    return rec


def crossref(doi: str) -> dict:
    data = _get("https://api.crossref.org/works/" + urllib.parse.quote(doi, safe="/"), "application/json")
    try:
        msg = json.loads(data)["message"]
    except (ValueError, KeyError):
        raise Refused(404, f"Crossref has no record for {doi}.") from None
    title = " ".join(" ".join(msg.get("title") or [""]).split())
    authors = []
    for a in msg.get("author") or []:
        name = " ".join(x for x in (a.get("given"), a.get("family")) if x) or a.get("name") or ""
        if name:
            authors.append(name)
    year = None
    for key in ("published-print", "published-online", "issued", "created"):
        parts = (msg.get(key) or {}).get("date-parts") or []
        if parts and parts[0] and parts[0][0]:
            year = int(parts[0][0])
            break
    venue = " ".join((msg.get("container-title") or [""])[:1]) or msg.get("publisher") or ""
    return {"title": title, "authors": authors, "year": year, "venue": venue, "doi": msg.get("DOI") or doi,
            "url": msg.get("URL") or f"https://doi.org/{doi}"}


def _core():
    try:
        from bazinga import cite as core_cite  # core's helpers, shared with `python -m bazinga cite`
        return core_cite
    except ImportError:
        return None


def lookup(q: str) -> dict:
    kind, ident = parse_query(q)
    core = _core()
    fn = core and (getattr(core, "lookup", None) or getattr(core, "fetch", None))
    if fn is not None:
        try:
            rec = dict(fn(q.strip()))
        except Refused:
            raise
        except Exception as exc:  # noqa: BLE001 - core's own error class: shown as a plain message
            raise Refused(502, str(exc) or "The lookup failed.") from None
    else:
        rec = arxiv(ident) if kind == "arxiv" else crossref(ident)
    rec.setdefault("source", kind)
    return rec


def _ascii(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()


def suggest_key(rec: dict, existing) -> str:
    """The key `python -m bazinga cite` would choose (core's make_key), else :func:`fallback_key`."""
    core = _core()
    if core is not None and hasattr(core, "make_key"):
        try:
            return str(core.make_key(rec, existing))
        except Exception:  # noqa: BLE001
            pass
    return fallback_key(rec, existing)


def fallback_key(rec: dict, existing) -> str:
    """First four letters of the first author's surname plus a two-digit year, as in ``VASW17``."""
    first = (rec.get("authors") or ["Anon"])[0]
    surname = re.sub(r"[^A-Za-z]", "", _ascii(first.split(",")[0] if "," in first else first.split()[-1])) or "ANON"
    year = rec.get("year")
    base = surname[:4].upper() + (f"{int(year) % 100:02d}" if year else "")
    key, n = base, 0
    while key in existing:
        key = base + "abcdefghijklmnopqrstuvwxyz"[n]
        n += 1
    return key


def references_path(root: Path) -> Path:
    return Path(root) / "content" / "references.yml"


def load(root: Path) -> dict:
    p = references_path(root)
    if not p.exists():
        return {}
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def save(root: Path, key: str, rec: dict) -> dict:
    """Append ``key: {...}`` to references.yml without reformatting the entries already there."""
    key = (key or "").strip()
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_:-]{0,40}", key):
        raise Refused(400, "A key is letters and digits, starting with a letter (e.g. VASW17).")
    existing = load(root)
    if key in existing:
        raise Refused(409, f"{key} is already in your references.")
    clean = {}
    for field in ("title", "authors", "year", "venue", "arxiv", "doi", "url"):
        v = rec.get(field)
        if v in (None, "", []):
            continue
        if field == "authors":
            v = [str(a).strip() for a in (v if isinstance(v, list) else str(v).split(",")) if str(a).strip()]
        elif field == "year":
            try:
                v = int(v)
            except (TypeError, ValueError):
                continue
        else:
            v = str(v).strip()
        clean[field] = v
    if not clean.get("title"):
        raise Refused(400, "A reference needs a title.")
    block = yaml.safe_dump({key: clean}, sort_keys=False, allow_unicode=True, width=1000,
                           default_flow_style=None)
    p = references_path(root)
    old = p.read_text(encoding="utf-8") if p.exists() else ""
    if not existing:  # "{}" or comments only: keep the comments, drop the empty mapping
        old = "".join(line for line in old.splitlines(True) if line.lstrip().startswith("#"))
    if old and not old.endswith("\n"):
        old += "\n"
    new = old + block
    if (yaml.safe_load(new) or {}).get(key) is None:
        raise Refused(500, "references.yml could not be extended safely; add the entry by hand.")
    atomic_write(p, new)
    return clean
