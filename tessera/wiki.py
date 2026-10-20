"""The generated wiki files.

Site files (every production build, no model needed):
- ``llms.txt`` (llmstxt.org layout) and ``llms-full.txt`` (every public page as Markdown)
- ``<url>index.md``: a Markdown copy of each public page
- ``data/passages.json``: one passage per section of every page (the Ask box searches these)
- ``data/graph.json``: the map (nodes with x/y, edges, rings, series, topics)
- ``figures/_retrieve.py``: the search code, for the browser

Repo files (the agent-facing wiki, committed):
- ``wiki/index.md``: the catalog, one line per page, grouped by kind and topic
- ``wiki/log.md``: append-only, ``## [YYYY-MM-DD] op | subject``
"""
from __future__ import annotations

import datetime as _dt
import json
import re
import shutil
from pathlib import Path

from . import graph as _graph

MAX_PASSAGE = 1100


def _get(obj, *path, default=None):
    cur = obj
    for p in path:
        if cur is None:
            return default
        if isinstance(cur, dict) and p in cur:
            cur = cur.get(p)
        elif isinstance(cur, dict) and not hasattr(type(cur), p) and p not in cur.__dict__:
            cur = None
        else:
            cur = getattr(cur, p, None)
    return default if cur is None else cur


def _root(cfg) -> Path:
    r = _get(cfg, "root")
    if r is None:
        from . import config  # pragma: no cover - core provides it
        r = config.ROOT
    return Path(r)


def _origin(cfg) -> str:
    return (_get(cfg, "site", "origin", default="") or "").rstrip("/")


def _kinds(cfg, pages):
    kinds = _get(cfg, "kinds", default={}) or {}
    order = list(kinds) if isinstance(kinds, dict) else []
    for p in pages:
        if p.kind not in order:
            order.append(p.kind)
    labels = {}
    for k in order:
        info = kinds.get(k) if isinstance(kinds, dict) else None
        labels[k] = (_get(info, "label") if info else None) or k.capitalize()
    return order, labels


# ------------------------------------------------------------------------------------------------
# Passages
# ------------------------------------------------------------------------------------------------
def split_text(text: str, limit: int = MAX_PASSAGE) -> list[str]:
    """Split plain text into chunks of at most ``limit`` characters at sentence boundaries."""
    text = re.sub(r"\s+", " ", text or "").strip()
    if not text:
        return []
    if len(text) <= limit:
        return [text]
    from .retrieve import sentences
    out, cur = [], ""
    for s in sentences(text):
        while len(s) > limit:                      # one very long sentence: cut at a space
            cut = s.rfind(" ", 0, limit)
            cut = cut if cut > limit // 2 else limit
            if cur:
                out.append(cur)
                cur = ""
            out.append(s[:cut].strip())
            s = s[cut:].strip()
        if not cur:
            cur = s
        elif len(cur) + 1 + len(s) <= limit:
            cur = cur + " " + s
        else:
            out.append(cur)
            cur = s
    if cur:
        out.append(cur)
    return out


def passages(pages, rendered) -> list[dict]:
    """One passage per h2/h3 section (plus the intro) of every page, plain text, ≤ 1,100 characters."""
    out = []
    for p in sorted(pages, key=lambda p: (p.kind, p.id)):
        r = rendered.get(p.id) if rendered else None
        sections = list(_get(r, "sections", default=[]) or [])
        summary = (p.summary or "").strip()
        if not sections or sections[0].get("title"):
            sections.insert(0, {"id": "", "title": "", "text": ""})
        for i, sec in enumerate(sections):
            text = (sec.get("text") or "").strip()
            if i == 0 and summary and summary[:60] not in text:
                text = (summary + " " + text).strip()
            for chunk in split_text(text):
                out.append({
                    "id": p.id,
                    "title": p.title,
                    "url": p.url,
                    "section": sec.get("title") or "",
                    "anchor": sec.get("id") or "",
                    "text": chunk,
                })
    return out


# ------------------------------------------------------------------------------------------------
# Markdown copies
# ------------------------------------------------------------------------------------------------
_MENTION = re.compile(r"\[\[([a-z0-9_-]+:[a-z0-9._-]+)(?:\|([^\]]+))?\]\]", re.I)
_CITE = re.compile(r"\[@([A-Za-z0-9_:+-]+)(?:,\s*([^\]]+))?\]")
_FIGURE = re.compile(r"^::figure\s+([A-Za-z0-9_]+)(?:\s*\|.*)?$", re.M)
_DRAWING = re.compile(r"^::drawing\s+([A-Za-z0-9_.]+)(?:\s*\|\s*(.*))?$", re.M)
_HEADING_ID = re.compile(r"^(#{1,6} .*?)\s*\{#[^}]+\}\s*$", re.M)
_EQ_LABEL = re.compile(r"^(\$\$)\s*\{#[^}]+\}\s*$", re.M)


def page_markdown(page, cfg, by_id: dict, references: dict | None = None, cites: list | None = None) -> str:
    """Clean Markdown for one page: title, summary, body with links resolved, references at the end."""
    origin = _origin(cfg)
    refs = references or {}
    order: list[str] = []

    def mention(m):
        target, text = m.group(1), m.group(2)
        node = by_id.get(target)
        if node is None:
            return text or target
        return f"[{text or node['title']}]({origin}{node['url']})"

    def cite(m):
        key = m.group(1)
        if key not in order:
            order.append(key)
        loc = f", {m.group(2).strip()}" if m.group(2) else ""
        return f"[{order.index(key) + 1}{loc}]"

    body = page.body or ""
    body = _MENTION.sub(mention, body)
    body = _CITE.sub(cite, body)
    body = _FIGURE.sub(lambda m: f"*[Interactive figure: {m.group(1).replace('_', ' ')} — open the page to use it.]*", body)
    body = _DRAWING.sub(lambda m: f"*[Diagram{': ' + m.group(2).strip() if m.group(2) else ''}]*", body)
    body = _HEADING_ID.sub(r"\1", body)
    body = _EQ_LABEL.sub(r"\1", body)
    lines = [f"# {page.title}", ""]
    if page.summary:
        lines += [f"> {page.summary.strip()}", ""]
    meta = []
    if getattr(page, "date", None):
        meta.append(f"Published {page.date.isoformat() if hasattr(page.date, 'isoformat') else page.date}")
    if getattr(page, "updated", None):
        meta.append(f"updated {page.updated.isoformat() if hasattr(page.updated, 'isoformat') else page.updated}")
    if page.topics:
        meta.append("topics: " + ", ".join(page.topics))
    meta.append(f"source: {origin}{page.url}")
    lines += [" · ".join(meta), "", body.strip(), ""]
    for k in cites or []:
        if k not in order:
            order.append(k)
    if order:
        lines += ["## References", ""]
        for n, key in enumerate(order, 1):
            lines.append(f"{n}. {_ref_text(key, refs.get(key))}")
        lines.append("")
    return "\n".join(lines)


def _ref_text(key, ref) -> str:
    if not ref:
        return key
    authors = ref.get("authors") or []
    if isinstance(authors, str):
        authors = [authors]
    who = ", ".join(authors[:3]) + (" et al." if len(authors) > 3 else "")
    parts = [p for p in (who, f"({ref.get('year')})" if ref.get("year") else "", f"*{ref.get('title')}*" if ref.get("title") else "", ref.get("venue") or "") if p]
    link = ""
    if ref.get("arxiv"):
        link = f"https://arxiv.org/abs/{ref['arxiv']}"
    elif ref.get("doi"):
        link = f"https://doi.org/{ref['doi']}"
    elif ref.get("url"):
        link = ref["url"]
    return " ".join(parts) + (f" {link}" if link else "")


def _references(cfg):
    try:
        from . import content
        return content.load_references(cfg) or {}
    except Exception:
        return {}


# ------------------------------------------------------------------------------------------------
# llms.txt
# ------------------------------------------------------------------------------------------------
def llms_txt(cfg, pages, graph) -> str:
    origin = _origin(cfg)
    name = _get(cfg, "site", "name", default="Site")
    desc = (_get(cfg, "site", "description", default="") or _get(cfg, "site", "tagline", default="") or "").strip()
    author = _get(cfg, "site", "author", default="")
    order, labels = _kinds(cfg, pages)
    lines = [f"# {name}", ""]
    if desc:
        lines += [f"> {desc}", ""]
    intro = f"Pages by {author}. " if author else ""
    intro += ("Every page below is also available as Markdown at the same address followed by `index.md`. "
              f"The whole site as one file: {origin}/llms-full.txt")
    lines += [intro, ""]
    for kind in order:
        ps = sorted([p for p in pages if p.kind == kind], key=lambda p: (_iso_neg(p), p.title.lower()))
        if not ps:
            continue
        lines += [f"## {labels[kind]}", ""]
        for p in ps:
            note = _one_line(p.summary)
            lines.append(f"- [{p.title}]({origin}{p.url}index.md)" + (f": {note}" if note else ""))
        lines.append("")
    optional = []
    for name_, ids in (graph.series().items() if graph else []):
        optional.append(f"- [Series: {name_}]({origin}/series/{_graph.series_slug(name_)}/): {len(ids)} parts in reading order")
    used = sorted({t for p in pages for t in p.topics})
    for t in used:
        label = (graph.topics.get(t) if graph else None) or t
        n = sum(1 for p in pages if t in p.topics)
        optional.append(f"- [Topic: {label}]({origin}/topics/{t}/): {n} page{'s' if n != 1 else ''}")
    optional.append(f"- [Map of the site]({origin}/data/graph.json): every page and how they connect, as JSON")
    optional.append(f"- [Full text]({origin}/llms-full.txt): every page above in one Markdown file")
    lines += ["## Optional", ""] + optional + [""]
    return "\n".join(lines)


def _iso_neg(p):
    return _graph._neg_date(p.date.isoformat() if getattr(p, "date", None) and hasattr(p.date, "isoformat") else "")


def _one_line(s) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


# ------------------------------------------------------------------------------------------------
# Site files
# ------------------------------------------------------------------------------------------------
def _write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_site_files(cfg, pages, rendered, graph, out: Path):
    out = Path(out)
    pages = [p for p in pages if getattr(p, "public", True)]
    by_id = {p.id: {"title": p.title, "url": p.url} for p in pages}
    refs = _references(cfg)
    feats = _get(cfg, "features", default={}) or {}
    llms_on = _get(feats, "llms_txt", default=True) is not False

    docs = []
    for p in sorted(pages, key=lambda p: (_iso_neg(p), p.id)):
        r = rendered.get(p.id) if rendered else None
        md = page_markdown(p, cfg, by_id, refs, list(_get(r, "cites", default=[]) or []))
        _write(out / p.url.strip("/") / "index.md", md)
        docs.append(md)
    if llms_on:
        _write(out / "llms.txt", llms_txt(cfg, pages, graph))
        _write(out / "llms-full.txt", "\n\n---\n\n".join(docs))
    ps = passages(pages, rendered or {})
    _write(out / "data" / "passages.json", json.dumps(ps, ensure_ascii=False, separators=(",", ":")))
    _write(out / "data" / "graph.json", json.dumps(graph.to_json(), ensure_ascii=False, separators=(",", ":")))
    (out / "figures").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(Path(__file__).with_name("retrieve.py"), out / "figures" / "_retrieve.py")
    return {"passages": len(ps), "pages": len(pages)}


# ------------------------------------------------------------------------------------------------
# Repo wiki: index + log
# ------------------------------------------------------------------------------------------------
def index_md(cfg, pages, graph) -> str:
    name = _get(cfg, "site", "name", default="Site")
    order, labels = _kinds(cfg, pages)
    topics = graph.topics if graph else {}
    titles = {p.id: p.title for p in pages}
    lines = [
        f"# {name} — wiki index",
        "",
        "Generated by the build from the public pages; do not edit by hand. One line per page: "
        "title and link, summary, topics, what it builds on. Read this first, then the pages.",
        "",
        f"{len(pages)} pages. Log: [log.md](log.md). Schema: [AGENTS.md](../AGENTS.md).",
        "",
    ]
    for kind in order:
        ps = [p for p in pages if p.kind == kind]
        if not ps:
            continue
        lines += [f"## {labels[kind]}", ""]
        groups: dict[str, list] = {}
        for p in ps:
            groups.setdefault(p.topics[0] if p.topics else "", []).append(p)
        for t in sorted(groups, key=lambda t: (t == "", (topics.get(t) or t).lower())):
            lines += [f"### {topics.get(t) or t or 'Other'}", ""]
            for p in sorted(groups[t], key=lambda p: (_iso_neg(p), p.title.lower())):
                bits = [f"- [{p.title}]({p.url}) `{p.id}`"]
                if p.summary:
                    bits.append(f" — {_one_line(p.summary)}")
                extra = []
                if p.topics:
                    extra.append("topics: " + ", ".join(p.topics))
                b = graph.builds_on(p.id) if graph else []
                if b:
                    extra.append("builds on: " + ", ".join(titles.get(x, x) for x in b))
                s = getattr(p, "series", None)
                if isinstance(s, dict) and s.get("name"):
                    extra.append(f"series: {s['name']} {s.get('part', '')}".rstrip())
                if extra:
                    bits.append(" · " + " · ".join(extra))
                lines.append("".join(bits))
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_repo_wiki(cfg, pages, graph) -> bool:
    """Write wiki/index.md; returns True when the file changed."""
    pages = [p for p in pages if getattr(p, "public", True)]
    path = _root(cfg) / "wiki" / "index.md"
    text = index_md(cfg, pages, graph)
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    _write(path, text)
    return True


LOG_HEADER = ("# Log\n\nAppend-only record of what happened to the wiki. Each entry starts with "
              "`## [YYYY-MM-DD] op | subject`, so `grep '^## \\[' wiki/log.md | tail -5` shows the latest.\n")


def append_log(cfg, op: str, subject: str, details: str = "", today: _dt.date | None = None) -> str:
    """Append ``## [YYYY-MM-DD] op | subject`` (and optional detail lines) to wiki/log.md."""
    path = _root(cfg) / "wiki" / "log.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    day = (today or _dt.date.today()).isoformat()
    op = re.sub(r"\s+", " ", op).strip()
    subject = re.sub(r"\s+", " ", subject).strip()
    entry = f"\n## [{day}] {op} | {subject}\n"
    if details.strip():
        entry += "\n" + details.strip() + "\n"
    if not path.exists():
        path.write_text(LOG_HEADER, encoding="utf-8")
    with path.open("a", encoding="utf-8") as f:
        f.write(entry)
    return entry
