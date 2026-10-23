"""What search engines and feed readers read: canonical URLs, Open Graph, JSON-LD, sitemap, robots.txt, Atom feed.

All functions are pure: they take the configuration and pages and return strings or dicts. ``build.py`` writes them.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from xml.sax.saxutils import escape

from .content import Page

FEED_SIZE = 30
DESCRIPTION_MAX = 155


def absolute(cfg, url: str) -> str:
    """``/posts/x/`` -> ``https://example.com/posts/x/``; absolute URLs pass through."""
    if re.match(r"^https?://", url or ""):
        return url
    return cfg["site"]["origin"] + "/" + (url or "").lstrip("/")


def describe(page: Page | None, cfg) -> str:
    """The meta description: the page's ``description``, else its summary cut at a sentence or clause."""
    if page is None:
        return cut(cfg["site"]["description"] or cfg["site"]["tagline"])
    return page.description or cut(page.summary)


def cut(text: str, limit: int = DESCRIPTION_MAX) -> str:
    """Shorten to ``limit`` characters at a sentence end, else a clause, else a word, adding an ellipsis."""
    text = " ".join((text or "").split())
    if len(text) <= limit:
        return text
    head = text[:limit]
    for sep in (". ", "; ", ", ", " "):
        idx = head.rfind(sep)
        if idx > limit * 0.5:
            piece = head[:idx + (1 if sep == ". " else 0)].rstrip(",;: ")
            return piece if sep == ". " else piece + "…"
    return head[: limit - 1].rstrip() + "…"


def share_image(cfg, page: Page | None) -> str:
    if page is not None and page.cover:
        return absolute(cfg, "/" + page.cover.lstrip("/"))
    avatar = str(cfg["site"].get("avatar") or "").lstrip("/")      # static/a.png and /static/a.png both work
    if avatar and (cfg.root / avatar).exists():
        return absolute(cfg, "/" + str(avatar).lstrip("/"))
    return ""


def open_graph(cfg, title: str, description: str, url: str, page: Page | None = None) -> dict:
    """Open Graph and Twitter values as a flat dict of property -> content (templates print them)."""
    og = {
        "og:site_name": cfg["site"]["name"],
        "og:title": title,
        "og:description": description,
        "og:url": absolute(cfg, url),
        "og:type": "article" if page is not None else "website",
        "og:locale": cfg["site"]["language"].replace("-", "_"),
        "twitter:card": "summary_large_image" if page is not None and page.cover else "summary",
    }
    image = share_image(cfg, page)
    if image:
        og["og:image"] = image
    if page is not None and page.date:
        og["article:published_time"] = page.date.isoformat()
        if page.updated:
            og["article:modified_time"] = page.updated.isoformat()
        og["article:author"] = cfg["site"]["author"]
    return og


def _person(cfg) -> dict:
    links = [v for v in (cfg["site"].get("links") or {}).values() if v and str(v).startswith("http")]
    person = {"@type": "Person", "name": cfg["site"]["author"], "url": cfg["site"]["origin"] + "/"}
    if links:
        person["sameAs"] = links
    return person


def jsonld(cfg, page: Page | None = None, url: str = "/", kind: str = "website") -> str:
    """JSON-LD for a post (BlogPosting), the home page (WebSite + Person) or another page (WebPage)."""
    if page is not None:
        data = {
            "@context": "https://schema.org", "@type": "BlogPosting",
            "headline": page.title, "description": describe(page, cfg),
            "url": absolute(cfg, page.url), "mainEntityOfPage": absolute(cfg, page.url),
            "author": _person(cfg), "publisher": _person(cfg),
            "inLanguage": cfg["site"]["language"],
        }
        if page.date:
            data["datePublished"] = page.date.isoformat()
            data["dateModified"] = (page.updated or page.date).isoformat()
        if page.topics:
            data["keywords"] = ", ".join(page.topics)
        image = share_image(cfg, page)
        if image:
            data["image"] = image
    elif kind == "home":
        data = {"@context": "https://schema.org", "@graph": [
            {"@type": "WebSite", "name": cfg["site"]["name"], "url": cfg["site"]["origin"] + "/",
             "description": describe(None, cfg), "inLanguage": cfg["site"]["language"], "author": _person(cfg)},
            _person(cfg)]}
    else:
        data = {"@context": "https://schema.org", "@type": "WebPage", "url": absolute(cfg, url),
                "isPartOf": {"@type": "WebSite", "name": cfg["site"]["name"], "url": cfg["site"]["origin"] + "/"}}
    # "</script" would end the block early and "<!--" would change how it is parsed: no "<" goes in as itself
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")


# ---------------------------------------------------------------------------------------------- files at the root
def sitemap(cfg, entries: list[tuple[str, date | None]]) -> str:
    """``entries`` are (url, lastmod). Pages use ``updated`` or ``date``; list pages pass their newest page's date."""
    rows = []
    for url, lastmod in entries:
        row = f"  <url><loc>{escape(absolute(cfg, url))}</loc>"
        if lastmod:
            row += f"<lastmod>{lastmod.isoformat()}</lastmod>"
        rows.append(row + "</url>")
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(rows) + "\n</urlset>\n")


def robots(cfg) -> str:
    return f"User-agent: *\nAllow: /\n\nSitemap: {cfg['site']['origin']}/sitemap.xml\n"


def _rfc3339(d: date) -> str:
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


def feed(cfg, pages: list[Page], html_by_id: dict | None = None) -> str:
    """An Atom feed of the newest public pages (at most 30), with summaries and full content when given."""
    html_by_id = html_by_id or {}
    pages = sorted((p for p in pages if p.public), key=lambda p: (p.updated or p.date, p.date), reverse=True)
    pages = sorted(pages[:FEED_SIZE], key=lambda p: p.date, reverse=True)
    origin = cfg["site"]["origin"]
    newest = max(((p.updated or p.date) for p in pages), default=date.today())
    entries = []
    for p in pages:
        content = html_by_id.get(p.id)
        body = f'\n    <content type="html">{escape(content)}</content>' if content else ""
        cats = "".join(f'\n    <category term="{escape(t)}"/>' for t in p.topics)
        entries.append(
            f"  <entry>\n    <title>{escape(p.title)}</title>\n"
            f'    <link href="{escape(absolute(cfg, p.url))}"/>\n    <id>{escape(absolute(cfg, p.url))}</id>\n'
            f"    <published>{_rfc3339(p.date)}</published>\n    <updated>{_rfc3339(p.updated or p.date)}</updated>\n"
            f"    <summary>{escape(p.summary)}</summary>{cats}{body}\n  </entry>")
    return ('<?xml version="1.0" encoding="utf-8"?>\n<feed xmlns="http://www.w3.org/2005/Atom">\n'
            f"  <title>{escape(cfg['site']['name'])}</title>\n"
            f"  <subtitle>{escape(cfg['site']['tagline'])}</subtitle>\n"
            f'  <link href="{origin}/feed.xml" rel="self"/>\n  <link href="{origin}/"/>\n'
            f"  <id>{origin}/</id>\n  <updated>{_rfc3339(newest)}</updated>\n"
            f"  <author><name>{escape(cfg['site']['author'])}</name></author>\n" + "\n".join(entries) + "\n</feed>\n")
