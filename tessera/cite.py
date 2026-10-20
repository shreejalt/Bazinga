"""Add a paper to ``content/references.yml`` from its arXiv id or DOI.

``python -m tessera cite 1706.03762`` (or an arXiv URL, a DOI, a doi.org URL) fetches the record from the arXiv API
(export.arxiv.org) or Crossref (api.crossref.org), makes a key such as ``Vaswani17`` (first author's surname + the
two-digit year; ``Vaswani17b`` if taken), and appends the entry to the file without rewriting what is there.
The Studio's citation panel uses :func:`lookup` too.
"""
from __future__ import annotations

import json
import re
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml

ARXIV_API = "https://export.arxiv.org/api/query?id_list={id}"
CROSSREF_API = "https://api.crossref.org/works/{doi}"
USER_AGENT = "Tessera/0.1 (static-site engine; citation lookup)"
TIMEOUT = 20

_ARXIV_NEW = re.compile(r"^(\d{4}\.\d{4,5})(v\d+)?$")
_ARXIV_OLD = re.compile(r"^([a-z-]+(?:\.[A-Z]{2})?/\d{7})(v\d+)?$")
_DOI = re.compile(r"^10\.\d{4,9}/\S+$")


class CiteError(Exception):
    """The id could not be understood or fetched; the message says what to try."""


def parse_query(q: str) -> tuple[str, str]:
    """Classify input as ("arxiv", id) or ("doi", doi). Accepts bare ids, arXiv/doi.org URLs and arXiv DOIs."""
    q = (q or "").strip().strip("<>")
    q = re.sub(r"^(?:arxiv:|doi:)\s*", "", q, flags=re.I)
    m = re.match(r"^https?://(?:www\.)?arxiv\.org/(?:abs|pdf|html)/(.+?)(?:\.pdf)?/?$", q, re.I)
    if m:
        q = m.group(1)
    m = re.match(r"^https?://(?:dx\.)?doi\.org/(.+)$", q, re.I)
    if m:
        q = urllib.parse.unquote(m.group(1))
    m = re.match(r"^10\.48550/arxiv\.(.+)$", q, re.I)
    if m:
        q = m.group(1)
    for pattern in (_ARXIV_NEW, _ARXIV_OLD):
        m = pattern.match(q)
        if m:
            return "arxiv", m.group(1)
    if _DOI.match(q):
        return "doi", q
    raise CiteError(f"{q!r} is not an arXiv id (like 1706.03762) or a DOI (like 10.1038/nature14539)")


def http_get(url: str) -> bytes:
    """GET a URL (tests replace this function)."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json, */*"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:     # noqa: S310 - fixed https endpoints
            return resp.read()
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise CiteError(f"not found at {urllib.parse.urlsplit(url).netloc} (check the id)") from None
        raise CiteError(f"{urllib.parse.urlsplit(url).netloc} answered {exc.code}; try again later") from None
    except (urllib.error.URLError, TimeoutError) as exc:
        raise CiteError(f"could not reach {urllib.parse.urlsplit(url).netloc} ({exc}); are you online?") from None


def _text(el, path: str, ns: dict) -> str:
    found = el.find(path, ns)
    return " ".join((found.text or "").split()) if found is not None else ""


def fetch_arxiv(arxiv_id: str) -> dict:
    data = http_get(ARXIV_API.format(id=urllib.parse.quote(arxiv_id)))
    ns = {"a": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        raise CiteError("the arXiv API sent something unreadable; try again later") from None
    entry = root.find("a:entry", ns)
    if entry is None or not _text(entry, "a:title", ns) or _text(entry, "a:title", ns).lower() == "error":
        raise CiteError(f"arXiv has no paper {arxiv_id}")
    authors = [_text(a, "a:name", ns) for a in entry.findall("a:author", ns)]
    published = _text(entry, "a:published", ns)
    record = {"title": _text(entry, "a:title", ns), "authors": [a for a in authors if a],
              "year": int(published[:4]) if published[:4].isdigit() else None, "arxiv": arxiv_id}
    journal = _text(entry, "arxiv:journal_ref", ns)
    doi = _text(entry, "arxiv:doi", ns)
    if journal:
        record["venue"] = journal
    if doi:
        record["doi"] = doi
    return record


def fetch_crossref(doi: str) -> dict:
    raw = http_get(CROSSREF_API.format(doi=urllib.parse.quote(doi, safe="/")))
    try:
        msg = json.loads(raw)["message"]
    except (ValueError, KeyError):
        raise CiteError("Crossref sent something unreadable; try again later") from None
    authors = []
    for a in msg.get("author") or []:
        name = " ".join(x for x in (a.get("given"), a.get("family")) if x) or a.get("name", "")
        if name:
            authors.append(name)
    year = None
    for key in ("published-print", "published-online", "issued", "created"):
        parts = (msg.get(key) or {}).get("date-parts") or []
        if parts and parts[0] and parts[0][0]:
            year = int(parts[0][0])
            break
    record = {"title": " ".join(" ".join(msg.get("title") or [""]).split()), "authors": authors, "year": year,
              "doi": msg.get("DOI") or doi}
    venue = (msg.get("container-title") or [""])[0] or msg.get("publisher") or ""
    if venue:
        record["venue"] = venue
    if not record["title"]:
        raise CiteError(f"Crossref has no title for {doi}")
    return record


def lookup(q: str) -> dict:
    """Fetch the record for an arXiv id/URL or a DOI."""
    kind, ident = parse_query(q)
    return fetch_arxiv(ident) if kind == "arxiv" else fetch_crossref(ident)


fetch = lookup


def _surname(author: str) -> str:
    name = author.split(",")[0] if "," in author else (author.split() or ["Anon"])[-1]
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    letters = re.sub(r"[^A-Za-z]", "", ascii_name)
    return letters[:1].upper() + letters[1:] if letters else "Anon"


def make_key(record: dict, existing) -> str:
    """``Vaswani17``; if taken, ``Vaswani17b``, ``Vaswani17c`` …"""
    authors = record.get("authors") or ["Anon"]
    year = record.get("year")
    base = _surname(str(authors[0])) + (f"{int(year) % 100:02d}" if year else "")
    existing = set(existing)
    if base not in existing:
        return base
    for suffix in "bcdefghijklmnopqrstuvwxyz":
        if base + suffix not in existing:
            return base + suffix
    raise CiteError(f"too many references start with {base}; pass --key")


def entry_yaml(key: str, record: dict) -> str:
    """One references.yml entry as YAML text."""
    fields = {k: record[k] for k in ("title", "authors", "year", "venue", "arxiv", "doi", "url") if record.get(k)}
    body = yaml.safe_dump({key: fields}, sort_keys=False, allow_unicode=True, width=1000, default_flow_style=None)
    return body


def add_reference(cfg, record: dict, key: str | None = None) -> str:
    """Append ``record`` to content/references.yml and return its key. Refuses a key that is already used."""
    path: Path = cfg.content_dir / "references.yml"
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    existing = (yaml.safe_load(text) or {}) if text.strip() else {}
    for k, v in existing.items():
        same_arxiv = record.get("arxiv") and str((v or {}).get("arxiv")) == str(record["arxiv"])
        same_doi = record.get("doi") and str((v or {}).get("doi", "")).lower() == str(record["doi"]).lower()
        if same_arxiv or same_doi:
            return k
    if key:
        if not re.match(r"^[A-Za-z][A-Za-z0-9_:.-]*$", key):
            raise CiteError("a key is letters and digits, starting with a letter, e.g. Vaswani17")
        if key in existing:
            raise CiteError(f"{key} is already in references.yml; choose another --key")
    else:
        key = make_key(record, existing)
    sep = "" if not text or text.endswith("\n\n") else ("\n" if text.endswith("\n") else "\n\n")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text + sep + entry_yaml(key, record), encoding="utf-8")
    return key
