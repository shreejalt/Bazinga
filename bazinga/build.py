"""Build the site into ``_site/``.

The order (docs/INTERFACES.md): config → pages → SiteIndex → render → graph → page templates → lists, home, topics,
series, explore, ask, 404 → figure assets → wiki files → sitemap, robots, feed → static files.

Drafts and future-dated pages are never written unless ``drafts=True`` (``python -m bazinga build --drafts``, for
previews). A production build stops on any error and lists them all with file and line; a lenient build (``serve``,
previews) shows them in the page instead. The site is built into a temporary folder and swapped in at the end, so a
running dev server never serves a half-written site.
"""
from __future__ import annotations

import hashlib
import html as html_lib
import json
import os
import re
import shutil
import sys
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import jinja2
from markupsafe import Markup

from . import checks, config, content, mapview, seo, vendor
from . import markdown as md
from .content import Page, slugify

ENGINE_THEME = Path(__file__).parent / "theme"
PER_PAGE = 10          # list pages show this many rows at a time (the pager in assets/js/pager.js)


class BuildError(Exception):
    """A production build found errors. ``problems`` is a list of (path, Issue)."""

    def __init__(self, problems: list):
        self.problems = problems
        lines = [issue.format(path) for path, issue in problems]
        super().__init__(f"{len(problems)} problem(s) stop the build:\n" + "\n".join(lines))


@dataclass
class BuildResult:
    out: Path
    pages: list
    rendered: dict
    issues: dict = field(default_factory=dict)   # page id -> [Issue]
    seconds: float = 0.0
    notes: list = field(default_factory=list)
    files: int = 0


def note(msg: str, notes: list | None = None, quiet: bool = False) -> None:
    if notes is not None:
        notes.append(msg)
    if not quiet:
        print(f"  note: {msg}", file=sys.stderr)


def _optional(name: str):
    """Import a module that another part of Bazinga provides, or None if it is not there yet."""
    import importlib
    try:
        return importlib.import_module(f"bazinga.{name}")
    except ModuleNotFoundError as exc:
        if exc.name in (f"bazinga.{name}",):
            return None
        raise


# --------------------------------------------------------------------------------------------- the site index
def make_site_index(cfg, pages, references=None, topics=None, preview=True, hidden=None) -> md.SiteIndex:
    """A SiteIndex for rendering: the Editor and previews pass every page (drafts included)."""
    if references is None:
        references = content.load_references(cfg)
    if topics is None:
        topics = content.load_topics(cfg)
    return md.SiteIndex(pages, references, topics, cfg, preview=preview, hidden=hidden)


def page_issues(page: Page, rendered: md.Rendered, site: md.SiteIndex) -> list:
    return checks.sort_issues(checks.check_front_matter(page, site) + rendered.issues + checks.check_body(page, site))


# ---------------------------------------------------------------------------------------------------- the graph
class FallbackGraph:
    """A minimal stand-in for bazinga.graph (used only while that module does not exist)."""

    def __init__(self, pages: list, rendered: dict):
        self.pages = {p.id: p for p in pages}
        self.rendered = rendered
        self.nodes = {p.id: {"id": p.id, "title": p.title, "url": p.url, "kind": p.kind, "summary": p.summary,
                             "topics": p.topics} for p in pages}
        self.edges = []

    def builds_on(self, ident):
        return [i for i in self.pages[ident].builds_on if i in self.pages]

    def read_next(self, ident):
        return [p.id for p in self.pages.values() if ident in p.builds_on]

    def backlinks(self, ident):
        return [i for i, r in self.rendered.items() if ident in r.mentions and i != ident]

    def related(self, ident, k=5):
        mine = set(self.pages[ident].topics)
        scored = [(len(mine & set(p.topics)), p.id) for p in self.pages.values() if p.id != ident]
        return [i for s, i in sorted(scored, key=lambda x: -x[0]) if s][:k]

    def series(self):
        out: dict = {}
        for p in sorted(self.pages.values(), key=lambda p: (p.series or {}).get("part", 0)):
            if p.series:
                out.setdefault(p.series["name"], []).append(p.id)
        return out

    def topic_pages(self, slug):
        return [p.id for p in self.pages.values() if slug in p.topics]

    def layout(self):
        return {}

    def to_json(self):
        return {"nodes": list(self.nodes.values()), "edges": []}


def build_graph(pages, rendered, site, notes):
    gmod = _optional("graph")
    if gmod is None:
        note("bazinga/graph.py is not there yet; connections use a simple fallback and the map is empty", notes)
        return FallbackGraph(pages, rendered)
    return gmod.build_graph(pages, rendered, site)


# -------------------------------------------------------------------------------------------------- the theme
class Theme:
    """Templates and assets, with ``<root>/theme/…`` shadowing ``bazinga/theme/…`` file by file."""

    def __init__(self, cfg):
        self.cfg = cfg
        self.dirs = [d for d in (cfg.theme_dir, ENGINE_THEME) if d.is_dir()]
        self._hash: dict = {}

    def asset_path(self, rel: str) -> Path | None:
        for d in self.dirs:
            p = d / "assets" / rel
            if p.is_file():
                return p
        return None

    def has_asset(self, rel: str) -> bool:
        return self.asset_path(rel) is not None

    def asset_url(self, rel: str) -> str:
        """``<base>/assets/<rel>?v=<hash>``: the hash changes when the file does, so browsers never use a stale copy."""
        if rel not in self._hash:
            path = self.asset_path(rel)
            self._hash[rel] = hashlib.sha256(path.read_bytes()).hexdigest()[:10] if path else "missing"
        return self.cfg.url(f"/assets/{rel}?v={self._hash[rel]}")

    def set_hash(self, rel: str, data: bytes) -> None:
        self._hash[rel] = hashlib.sha256(data).hexdigest()[:10]

    def env(self) -> jinja2.Environment:
        loader = jinja2.FileSystemLoader([str(d / "templates") for d in self.dirs])
        env = jinja2.Environment(loader=loader, autoescape=jinja2.select_autoescape(["html", "xml"]),
                                 trim_blocks=True, lstrip_blocks=True, undefined=jinja2.ChainableUndefined)
        env.filters["date"] = fmt_date
        env.filters["isodate"] = lambda d: d.isoformat() if d else ""
        env.filters["json"] = lambda v: Markup(json.dumps(v, ensure_ascii=False).replace("</", "<\\/"))
        env.filters["month_year"] = month_year
        env.filters["full_date"] = full_date
        env.filters["extract_title"] = lambda key, refs: (refs.get(key) or {}).get("title", key)
        # A site under a sub-path (site.origin https://you.github.io/repo): templates write every path on the site as
        # {{ link(p.url) }} or {{ base }}/topics/ so that it starts with /repo. Globals, so imported macros see them.
        env.globals["base"] = self.cfg.base
        env.globals["link"] = self.cfg.url
        env.filters["link"] = self.cfg.url
        env.filters["links"] = lambda html: config.site_links(self.cfg.base, html)   # hand-written HTML in site.yml
        return env

    def copy_assets(self, out: Path) -> int:
        """Engine assets first, then the site's overrides on top."""
        count = 0
        for d in reversed(self.dirs):
            src = d / "assets"
            if src.is_dir():
                shutil.copytree(src, out / "assets", dirs_exist_ok=True)
                count += sum(1 for _ in src.rglob("*") if _.is_file())
        return count


MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
TITLE_MAX = 65                 # the " — <site name>" suffix goes on a <title> only while it stays this short
MAP_TYPE = {"read": "read", "paper": "paper", "project": "proj", "external": "ext"}
LINK_LABELS = {"github": "GitHub", "x": "X", "twitter": "Twitter", "linkedin": "LinkedIn", "email": "Email",
               "scholar": "Scholar", "medium": "Medium", "mastodon": "Mastodon", "bluesky": "Bluesky",
               "youtube": "YouTube", "website": "Website", "orcid": "ORCID", "substack": "Substack"}
SKIP_HEAD = ("reference", "what came next", "connections", "conclusion", "further reading", "papers")
_H2 = re.compile(r'<h2 id="([^"]+)">(.*?)</h2>', re.S)
_ANCHOR = re.compile(r'<a [^>]*class="heading-anchor"[^>]*>.*?</a>', re.S)
_TAG = re.compile(r"<[^>]+>")
_SLOT = re.compile(r'(?:<p>)?<div class="pagebreak-slot"></div>(?:</p>)?|<h2 id="([^"]+)">(.*?)</h2>', re.S)


def fmt_date(d) -> str:
    if not d:
        return ""
    return f"{d.day} {d:%B %Y}"


def month_year(d) -> str:
    """``Oct 2026``."""
    return f"{MONTHS[d.month - 1]} {d.year}" if d else ""


def full_date(d) -> str:
    """``20 Oct 2026``."""
    return f"{d.day} {month_year(d)}" if d else ""


def fit_title(title: str, name: str) -> str:
    """The <title>: "<title> — <name>" while that stays within TITLE_MAX characters, else the title alone."""
    title = " ".join(str(title).split())
    if not name or title == name:
        return title
    full = f"{title} — {name}"
    return full if len(full) <= TITLE_MAX else title


def plain(fragment: str) -> str:
    return html_lib.unescape(_TAG.sub("", _ANCHOR.sub("", fragment))).strip()


def memo_body(body: str, pagebreak) -> tuple[str, list, int]:
    """A memo page's body: its h2 headings numbered 1. 2. 3. (unless the author numbered them) and each ``::pagebreak``
    turned into a page break. Returns (html, headings [{id, text, page}], the last page number)."""
    heads = [plain(m.group(2)) for m in _H2.finditer(body)]
    number = bool(heads) and not all(re.match(r"\s*\d", t) for t in heads)
    count = [0]

    def numbered(m):
        count[0] += 1
        inner = m.group(2)
        if number:
            inner = f"{count[0]}. {inner}"
        return f'<h2 id="{m.group(1)}">{inner}</h2>'
    body = _H2.sub(numbered, body)
    page, headings = [2], []

    def walk(m):
        if m.group(1) is None:
            out = pagebreak(page[0])
            page[0] += 1
            return out
        headings.append({"id": m.group(1), "text": plain(m.group(2)), "page": page[0]})
        return m.group(0)
    body = _SLOT.sub(walk, body)
    return body, headings, page[0]


# ------------------------------------------------------------------------------------------------- the builder
class Builder:
    def __init__(self, cfg, drafts=False, strict=None, dev=False, quiet=False):
        self.cfg = cfg
        self.drafts = drafts
        self.strict = (not drafts) if strict is None else strict
        self.dev = dev
        self.quiet = quiet
        self.notes: list = []
        self.theme = Theme(cfg)
        self.env = self.theme.env()
        self.vendor = vendor.urls()
        self._mapdata = None
        self.layout = None
        self.views: dict = {}

    def link(self, path):
        """A path on this site as the built files link to it (with the base path of a site under a sub-path)."""
        return self.cfg.url(path)

    def linked(self, obj):
        """A copy of data the browser reads with every ``url`` that is a path on this site given the base path."""
        if not self.cfg.base:
            return obj
        if isinstance(obj, dict):
            return {k: (self.link(v) if k == "url" else self.linked(v)) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self.linked(v) for v in obj]
        return obj

    # ---- steps 2-5
    def load(self) -> None:
        cfg = self.cfg
        everything = content.load_pages(cfg, drafts=True)
        # A page that does not say status: draft but has a status or a date the build cannot read would quietly
        # never go out (a typo such as "publshed" or 2026/01/05): that stops a production build, with file:line.
        unreadable = [(self._rel(p.path), checks.Issue("error", line, msg + " (so this page would not be published)",
                                                       hint, "front-matter"))
                      for p in everything if not p.meant_draft for line, msg, hint in p.hidden_by]
        if unreadable and self.strict:
            raise BuildError(unreadable)
        for path, issue in unreadable:
            note(issue.format(path), self.notes, self.quiet)
        self.pages = everything if self.drafts else [p for p in everything if p.public]
        hidden = [] if self.drafts else [p for p in everything if not p.public]
        self.topics = content.load_topics(cfg)
        self.references = content.load_references(cfg)
        self.site = make_site_index(cfg, self.pages, self.references, self.topics,
                                    preview=self.drafts or not self.strict, hidden=hidden)
        self.by_id = {p.id: p for p in self.pages}

    def render_all(self) -> None:
        self.rendered, self.issues = {}, {}
        problems = []
        for page in self.pages:
            r = md.render(page, self.site)
            self.rendered[page.id] = r
            found = page_issues(page, r, self.site)
            self.issues[page.id] = found
            problems += [(self._rel(page.path), i) for i in found if i.level == "error"]
        if problems and self.strict:
            raise BuildError(problems)
        for path, issue in problems:
            note(issue.format(path), self.notes, self.quiet)

    def _rel(self, path: Path) -> str:
        try:
            return str(Path(path).resolve().relative_to(self.cfg.root.resolve()))
        except ValueError:
            return str(path)

    def problem(self, where: str, message: str, hint: str = "") -> None:
        """A problem outside the pages (cv.yml, site.yml): stops a production build, a note otherwise."""
        issue = checks.Issue("error", None, message, hint, "site")
        if self.strict:
            raise BuildError([(where, issue)])
        note(issue.format(where), self.notes, self.quiet)

    # ---- kinds and nodes
    @property
    def local_pages(self) -> list:
        return [p for p in self.pages if p.local]

    def role(self, kind: str) -> str:
        return str(self.cfg["kinds"].get(kind, {}).get("role", "read"))

    def map_type(self, kind: str) -> str:
        return MAP_TYPE.get(self.role(kind), "read")

    def kind_singular(self, kind: str) -> str:
        return str(self.cfg["kinds"].get(kind, {}).get("singular", kind))

    def node(self, ident: str) -> dict | None:
        p = self.by_id.get(ident)
        if p is None:
            return None
        series = None
        if p.series:
            ids = self.series_map.get(p.series["name"]) or []
            series = {"name": p.series["name"], "part": p.series.get("part"), "n": len(ids),
                      "url": f"/series/{slugify(p.series['name'])}/"}
        return {"id": p.id, "title": p.title, "short": str(p.meta.get("short") or p.title), "url": p.url,
                "summary": p.summary, "kind": p.kind, "kind_label": self.kind_singular(p.kind), "role": self.role(p.kind),
                "type": self.map_type(p.kind), "date": p.date, "topics": p.topics,
                "minutes": content.reading_minutes(p), "series": series, "state": p.state,
                "local": p.local, "external": p.external, "author": str(p.meta.get("author") or ""),
                "publication": str(p.meta.get("publication") or ""), "explains": p.explains,
                "github": str(p.meta.get("github") or ""), "project_type": str(p.meta.get("type") or ""),
                "launch": bool(p.meta.get("launch"))}

    def nodes(self, ids) -> list:
        return [n for n in (self.node(i) for i in ids) if n]

    def topic(self, slug: str) -> dict:
        return self.topics.get(slug) or {"slug": slug, "label": slug.replace("-", " ").title(), "blurb": "",
                                         "group": ""}

    def ref(self, key: str) -> dict:
        """A reference as the theme prints it: authors, title, year, its address and the label of that link."""
        r = self.references.get(key) or {}
        authors = [str(a) for a in r.get("authors") or []]
        names = authors[0] + " et al." if len(authors) > 3 else ", ".join(authors[:-1]) + (" and " if len(authors) > 1 else "") + (authors[-1] if authors else "")
        link = f"arXiv:{r['arxiv']}" if r.get("arxiv") else (str(r.get("venue") or "") or "paper")
        explained = [p for p in self.pages if key in p.explains]
        return {"key": key, "title": str(r.get("title") or key), "authors": names, "year": r.get("year", ""),
                "url": md.reference_url(r), "link": link, "venue": str(r.get("venue") or ""),
                "explained": [{"id": p.id, "title": p.title, "url": p.url} for p in explained]}

    # ---- the map: graph data, layout, views
    @property
    def mapdata(self) -> dict:
        if self._mapdata is None:
            self._mapdata = self.graph_data()
        return self._mapdata

    def graph_data(self) -> dict:
        """The site in the shape bazinga.mapview reads (pages in the order the site lists them, oldest first)."""
        explained: dict = {}
        for p in self.pages:
            for key in p.explains:
                explained.setdefault(key, []).append(p.id)
        prev: dict = {}
        for name, ids in self.series_map.items():
            for a, b in zip(ids, ids[1:]):
                prev[b] = a
        out = []
        order = {k: n for n, k in enumerate(self.cfg["kinds"])}
        for p in sorted(self.pages, key=lambda p: (order.get(p.kind, 99), p.date or date.min,
                                                  (p.series or {}).get("part", 0), p.slug)):
            r = self.rendered.get(p.id)
            keys = list(dict.fromkeys((r.cites if r else []) + p.cites))
            cites = sorted({t for key in keys for t in (explained.get(key) or ["ref:" + key]) if t != p.id})
            links = [b for b in p.builds_on if b in self.by_id]
            if p.id in prev and prev[p.id] not in links:
                links.append(prev[p.id])
            mentions = sorted({m for m in (r.mentions if r else []) if m in self.by_id and m != p.id})
            out.append({"id": p.id, "type": self.map_type(p.kind), "title": p.title,
                        "short": str(p.meta.get("short") or p.title), "topics": list(p.topics), "cites": cites,
                        "links": links, "mentions": mentions, "date": p.date.isoformat() if p.date else "",
                        "series": p.series["name"] if p.series else None,
                        "part": p.series.get("part") if p.series else None})
        refs = {k: {"title": str(v.get("title") or k)} for k, v in self.references.items() if k not in explained}
        topics = {s: {"title": t["label"], "group": t["group"]} for s, t in self.topics.items()}
        return {"items": out, "refs": refs, "topics": topics}

    def view(self, ident: str) -> dict:
        """What a hover or a page's Connections block shows about one page (related, reading order), with addresses."""
        if ident not in self.views:
            if self.layout is not None:
                v = mapview.view_on_map(self.mapdata, ident, self.layout)
            else:
                v = mapview.view(self.mapdata, ident)
            for entry in v["related"] + v["path"]:
                entry["url"] = self.by_id[entry["id"]].url if entry["id"] in self.by_id else "#"
                entry["kl"] = self.kind_singular(self.by_id[entry["id"]].kind) if entry["id"] in self.by_id else ""
            self.views[ident] = v
        return self.views[ident]

    @property
    def tag_counts(self) -> dict:
        counts: dict = {}
        for p in self.pages:
            for t in p.topics:
                counts[t] = counts.get(t, 0) + 1
        return counts

    def broader(self, page: Page, view: dict) -> dict:
        """The wider context of a page for its "Go broader" list: where it sits, its topics, what else carries them,
        its series."""
        close = {r["id"] for r in view["related"]} | {p["id"] for p in view["path"]} | {page.id}
        trail = [{"id": i, "title": self.by_id[i].title, "short": str(self.by_id[i].meta.get("short") or self.by_id[i].title),
                  "url": self.by_id[i].url} for i in mapview.trail(self.mapdata, page.id) if i in self.by_id]
        counts = self.tag_counts
        tags = [{"slug": t, "label": self.topic(t)["label"], "count": counts.get(t, 0), "url": f"/topics/{t}/"}
                for t in page.topics]
        under = [{"id": r["id"], "title": r["title"], "url": self.by_id[r["id"]].url, "shared": r["shared"]}
                 for r in mapview.suggest(self.mapdata, page.id, limit=12) if r["id"] not in close and r["id"] in self.by_id][:5]
        series = None
        if page.series and self.series_map.get(page.series["name"]):
            ids = self.series_map[page.series["name"]]
            series = {"name": page.series["name"], "n": len(ids), "url": self.by_id[ids[0]].url,
                      "part": ids.index(page.id) + 1 if page.id in ids else page.series.get("part")}
        short = str(page.meta.get("short") or page.title)
        return {"trail": trail, "tags": tags, "under": under, "series": series, "ask": f"What connects {short} and "}

    def site_nodes(self) -> dict:
        """What the browser knows about every page, reference and topic: where it lives and its preview card."""
        nodes = {}
        for p in self.pages:
            role = self.role(p.kind)
            by = f" · by {p.meta['author']}" if p.meta.get("author") else ""
            about = ", ".join(str((self.references.get(k) or {}).get("title") or k) for k in p.explains)
            kicker = self.kind_singular(p.kind) + by + (f" · {about}" if about else "") + \
                (f" · {month_year(p.date)}" if p.date else "")
            if not p.local:
                go = f"Read on {p.meta.get('publication') or 'the original site'} ↗"
            else:
                go = {"paper": "Read the explanation →", "project": "View the project →"}.get(role, "Read it →")
            nodes[p.id] = {"type": self.map_type(p.kind), "kl": self.kind_singular(p.kind), "title": p.title,
                           "short": str(p.meta.get("short") or ""), "url": p.url, "desc": p.summary, "kicker": kicker, "go": go}
        explained = {k for p in self.pages for k in p.explains}
        for key, r in self.references.items():
            if key in explained:
                continue
            ref = self.ref(key)
            nodes["ref:" + key] = {"type": "ref", "kl": "Reference", "title": ref["title"], "url": ref["url"],
                                   "desc": f"{ref['authors']}, {ref['year']}", "kicker": "Reference · " + ref["link"],
                                   "go": "Opens the paper ↗"}
        for slug, t in self.topics.items():
            nodes["topic:" + slug] = {"type": "topic", "kl": "Tag", "title": t["label"], "group": t["group"],
                                      "url": f"/topics/{slug}/"}
        return nodes

    def type_labels(self) -> dict:
        labels = {"ref": "Reference", "topic": "Tag"}
        for kind in self.cfg["kinds"]:
            labels.setdefault(self.map_type(kind), self.kind_singular(kind))
        return labels

    # ---- shared template context
    @property
    def site_nav(self) -> list:
        return [(str(n["href"]), str(n["label"])) for n in self.cfg["nav"]]

    def links_list(self) -> list:
        links = self.cfg["site"].get("links") or {}
        return [{"label": LINK_LABELS.get(k, k.replace("_", " ").title()), "url": str(v)}
                for k, v in links.items() if v and k != "email"]

    def theme_css(self) -> str:
        """The theme values from site.yml as CSS variables (only the ones set; the stylesheet has the defaults)."""
        theme = self.cfg["theme"]
        out = [f"--blue:{theme['accent']}"]
        names = {"accent_dark": "--blue-d", "ground": "--ground", "paper": "--paper", "tint": "--tint",
                 "ink": "--ink", "ink_2": "--ink-2", "ink_3": "--ink-3", "rule_2": "--rule-2", "rule_3": "--rule-3",
                 "ref": "--ref", "alert": "--alert"}
        for key, var in names.items():
            if theme.get(key):
                out.append(f"{var}:{theme[key]}")
        if not theme.get("accent_dark"):
            out.append("--blue-d:color-mix(in srgb,var(--blue) 78%,black)")
        fonts = {"font_text": ("--serif", 'Georgia,"Times New Roman",serif'),
                 "font_code": ("--mono", '"Courier New",Courier,monospace'),
                 "font_math": ("--math", '"STIX Two Math","Cambria Math","Latin Modern Math",serif')}
        for key, (var, fallback) in fonts.items():
            if theme.get(key):
                out.append(f'{var}:"{theme[key]}",{fallback}')
        return ";".join(out)

    def base_context(self, url: str, title: str, description: str, page: Page | None = None,
                     kind: str = "website", nav: list | None = None, here: str | None = None) -> dict:
        cfg = self.cfg
        name = cfg["site"]["name"]
        theme = cfg["theme"]
        author = cfg["site"]["author"] or name
        words = author.split()
        return {
            "cfg": cfg, "site": cfg["site"], "nav": cfg["nav"], "features": cfg["features"], "theme": theme,
            "asset": self.theme.asset_url, "has_asset": self.theme.has_asset, "vendor": self.vendor,
            "font_urls": vendor.font_urls(theme), "theme_css": self.theme_css(),
            "page_title": fit_title(title, name), "title": title, "description": description,
            "canonical": seo.absolute(cfg, url), "url": url,
            "og": seo.open_graph(cfg, title, description, url, page),
            "jsonld": seo.jsonld(cfg, page, url, kind),
            "body_page_id": page.id if page is not None else "", "body_page_title": page.title if page else "",
            "topic": self.topic, "node": self.node, "kinds": cfg["kinds"],
            "kinds_labels": {k: v["label"] for k, v in cfg["kinds"].items()},
            "dev": self.dev, "drafts": self.drafts, "year": date.today().year,
            "has_feed": bool(cfg["features"].get("feed")),
            "markdown_url": self.link(url + "index.md") if page is not None and not self.drafts else "",
            "rail_nav": self.site_nav if nav is None else nav, "here": here,
            "updated": date.today().strftime("%B %Y"),
            "author": author, "author_short": (f"{words[0][0]}. {words[-1]}" if len(words) > 1 else author),
            "surname": words[-1] if words else author,
            "links_list": self.links_list(), "email": str((cfg["site"].get("links") or {}).get("email") or ""),
            "home": cfg["home"], "cv_pdf": str(cfg["cv"].get("pdf") or ""),
            "site_data": self.site_data_url,
        }

    def write(self, url: str, template: str, ctx: dict) -> None:
        html = self.env.get_template(template).render(**ctx)
        rel = url.strip("/")
        path = self.out / rel / "index.html" if not rel.endswith(".html") else self.out / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html, encoding="utf-8")
        self.count += 1

    # ---- step 6: one page
    def page_context(self, page: Page, prev: dict | None = None, nxt: dict | None = None) -> dict:
        r = self.rendered[page.id]
        role = self.role(page.kind)
        cfg = self.cfg
        view = self.view(page.id)
        wider = self.broader(page, view)
        neigh = mapview.neighbors(self.mapdata, page.id)
        for o in neigh["out"] + neigh["in"]:
            o["url"] = self.link(self.by_id[o["id"]].url) if o["id"] in self.by_id else self.ref(o["id"][4:])["url"]
        figure = Markup(mapview.links_figure(neigh, self.type_labels())) if neigh["out"] or neigh["in"] else ""
        refs = []
        for item in md.references(r, self.site):
            ref = self.ref(item["key"])
            ref["n"] = item["n"]
            ref["explained"] = [e for e in ref["explained"] if e["id"] != page.id]
            refs.append(ref)
        author = (cfg["site"]["author"] or cfg["site"]["name"] or "?").split() or ["?"]
        surname, initial = author[-1], author[0][0]

        def pagebreak(n):
            return (f'<div class="pagebreak"><span>{html_lib.escape(surname)}</span><span>Informational</span>'
                    f'<span>[Page {n}]</span></div><div class="pagetop"><span>{html_lib.escape(initial)}. '
                    f'{html_lib.escape(surname)}</span><span>{month_year(page.date)}</span></div>')
        if role == "project":
            body, headings, last = r.html, [{"id": t["id"], "text": t["text"], "page": 1} for t in r.toc
                                            if t["level"] == 2], 1
        else:
            body, headings, last = memo_body(r.html, pagebreak)
        own_refs = any(h["text"].lstrip("0123456789. ").lower().startswith("reference") for h in headings)
        show_papers = bool(refs) and not own_refs
        n = len(headings)
        if role == "project":
            nav = [("#overview", "Overview")] + ([("#usage", "Usage")] if page.meta.get("usage") else []) + \
                ([("#write-up", "Write-up")] if not headings else [("#" + h["id"], h["text"]) for h in headings]) + \
                [("#related", "Related")] + ([("#limitations", "Limitations")] if page.meta.get("limitations") else [])
        else:
            nav = [("#summary", "Summary")] + [("#" + h["id"], h["text"]) for h in headings] + \
                [("#connections", f"{n + 1}. Connections")] + ([("#papers", f"{n + 2}. Papers")] if show_papers else [])
        series = None
        if page.series and self.series_map.get(page.series["name"]):
            ids = self.series_map[page.series["name"]]
            series = {"name": page.series["name"], "url": f"/series/{slugify(page.series['name'])}/",
                      "part": ids.index(page.id) + 1 if page.id in ids else page.series.get("part"), "n": len(ids),
                      "parts": [{"id": i, "title": self.by_id[i].title, "url": self.by_id[i].url, "part": k + 1}
                                for k, i in enumerate(ids)]}
        title = str(page.meta.get("seo_title") or page.title)
        ctx = self.base_context(page.url, title, seo.describe(page, cfg), page, nav=nav)
        ctx.update({
            "page": page, "p": self.node(page.id), "role": role, "body": Markup(body), "html": Markup(r.html),
            "toc": r.toc, "headings": headings, "last_page": last, "view": view, "wider": wider, "figure": figure,
            "builds_on": self.nodes(page.builds_on), "n_conn": n + 1, "n_refs": n + 2, "show_papers": show_papers,
            "refs": refs, "explains": [self.ref(k) for k in page.explains], "series_info": series,
            "prev": prev, "next": nxt, "page_topics": [self.topic(t) for t in page.topics],
            "kind_label": self.kind_singular(page.kind), "kind_list_url": f"/{page.kind}/",
            "kind_list_label": cfg["kinds"][page.kind]["label"], "reading_minutes": content.reading_minutes(page),
            "meta": page.meta, "has_headings": bool(headings),
            "issues": self.issues.get(page.id, []) if (self.drafts or not self.strict) else [],
        })
        return ctx

    def write_pages(self) -> None:
        for kind in self.cfg["kinds"]:
            group = sorted((p for p in self.local_pages if p.kind == kind), key=lambda p: (p.date or date.min, p.slug))
            for idx, page in enumerate(group):
                prev = self.node(group[idx - 1].id) if idx else None
                nxt = self.node(group[idx + 1].id) if idx + 1 < len(group) else None
                template = "project.html" if self.role(kind) == "project" else "page.html"
                self.write(page.url, template, self.page_context(page, prev, nxt))

    # ---- step 7: lists, home, CV
    def write_lists(self) -> None:
        cfg = self.cfg
        for kind, spec in cfg["kinds"].items():
            role = spec["role"]
            items = self.nodes(p.id for p in self.pages if p.kind == kind)
            if role == "project":
                items.sort(key=lambda n: (self.by_id[n["id"]].meta.get("order", 99), n["title"].lower()))
            url = f"/{kind}/"
            series = {}
            if role in ("read", "paper"):
                for name, ids in self.series_map.items():
                    if any(self.by_id[i].kind == kind for i in ids):
                        series[name] = self.nodes(ids)
            blurb = spec["blurb"] or f"{spec['label']} by {cfg['site']['author']}."
            ctx = self.base_context(url, spec["label"], seo.cut(blurb), here=url)
            ctx.update({"kind": kind, "role": role, "items": items, "heading": spec["label"], "blurb": blurb,
                        "placeholder": spec["placeholder"] or "filter: a word from a title or a topic …",
                        "word": spec["word"] or spec["label"].lower(), "series": series,
                        "authors": sorted({n["author"] for n in items if n["author"]}),
                        "external_kinds": [(k, s["label"]) for k, s in cfg["kinds"].items() if s["external"]],
                        "refs_by_key": {k: self.ref(k) for n in items for k in n["explains"]}})
            self.write(url, "list.html", ctx)

    def write_home(self) -> None:
        cfg = self.cfg
        home = cfg["home"]
        experience = []
        for job in home.get("experience") or []:
            job = dict(job)
            pages = []
            for ident in job.get("pages") or []:
                if ident in self.by_id:
                    pages.append(self.node(ident))
                else:
                    self.problem("site.yml", f"home.experience: unknown page {ident!r}",
                                 "use the id of a published page, e.g. project:bazinga")
            job["page_nodes"] = pages
            experience.append(job)
        sections = [("#about", "About", True), ("#map", "Explore", cfg["features"].get("explore", True)),
                    ("#experience", "Experience", bool(experience)), ("#education", "Education", bool(home.get("education"))),
                    ("#contact", "Contact", bool(home.get("contact")))]
        extra = [(h, label) for h, label in self.site_nav if h in ("/series/", "/ask/", "/cv/")]
        nav = [(h, label) for h, label, on in sections if on] + extra
        title = str(home.get("title") or cfg["site"]["name"])
        ctx = self.base_context("/", title, seo.describe(None, cfg), kind="home", nav=nav)
        ctx.update({"experience": experience,
                    "kind_buttons": [(f"/{k}/", s["label"]) for k, s in cfg["kinds"].items()],
                    "intro": Markup(md.render_inline(home.get("intro") or "", cfg.base)) if home.get("intro") else ""})
        self.write("/", "home.html", ctx)

    def write_cv(self) -> None:
        path = self.cfg.content_dir / "cv.yml"
        if not path.exists():
            return
        try:
            import yaml
            cv = content.load_yaml(path.read_text(encoding="utf-8"), "content/cv.yml") or {}
        except content.ContentError as exc:
            self.problem("content/cv.yml" + (f":{exc.line}" if exc.line else ""), exc.message, exc.hint)
            return
        except Exception as exc:                                       # noqa: BLE001
            self.problem("content/cv.yml", f"cv.yml is not valid YAML: {exc}")
            return
        for key in ("experience", "education", "patents", "achievements", "skills", "open_source"):
            cv[key] = cv.get(key) or []
        cv["contact"] = cv.get("contact") or {}
        for job in cv["experience"]:
            for t in job.get("tags") or []:
                if t not in self.topics:
                    self.problem("content/cv.yml", f"cv.yml: unknown topic {t!r} under {job.get('org', '?')}",
                                 "use a slug from content/topics.yml")
            job["tags"] = [t for t in job.get("tags") or [] if t in self.topics]
            for ident in job.get("pages") or []:
                if ident not in self.by_id:
                    self.problem("content/cv.yml", f"cv.yml: unknown page {ident!r} under {job.get('org', '?')}",
                                 "use the id of a published page, e.g. project:bazinga")
            job["pages"] = [i for i in job.get("pages") or [] if i in self.by_id]
        for o in cv["open_source"]:
            if o.get("page") and o["page"] not in self.by_id:
                self.problem("content/cv.yml", f"cv.yml: unknown page {o['page']!r} in open_source")
                o["page"] = ""
        listed = {o.get("page") for o in cv["open_source"]}
        repos = [n for n in self.nodes(p.id for p in self.pages if p.meta.get("github"))
                 if n["id"] not in listed]
        cfg = self.cfg
        role = str(cfg["home"].get("role") or "")
        desc = seo.cut(f"{cfg['site']['author']}: {len(cv['experience'])} roles, education, awards, skills and "
                       "open-source work, each tied to the pages on this site about it.")
        ctx = self.base_context("/cv/", "CV" + (f" — {cfg['site']['author']}, {role.lower()}" if role else ""), desc,
                                here="/cv/")
        ctx["page_title"] = fit_title(f"CV — {cfg['site']['author']}" + (f", {role.lower()}" if role else ""), "")
        ctx.update({"cv": cv, "repos": repos, "topics_map": self.topics})
        self.write("/cv/", "cv.html", ctx)

    def series_list(self) -> list:
        """Every declared series with its parts, each part with its highlights: the accepted ones in
        content/series/<slug>.yml, else the page's own section headings (external entries: their summary only)."""
        out = []
        for name, ids in self.series_map.items():
            parts = self.nodes(ids)
            if not parts:
                continue
            meta = self.series_meta(name)
            highlights = meta.get("parts") or {}
            figures, authors = set(), set()
            for k, part in enumerate(parts, 1):
                page = self.by_id[part["id"]]
                part["part"] = k
                hl = [str(h) for h in highlights.get(part["id"], [])][:4]
                if not hl and page.local:
                    hl = [t["text"] for t in self.rendered[page.id].toc if t["level"] == 2
                          and not t["text"].lower().startswith(SKIP_HEAD)][:5]
                part["highlights"] = hl
                names = set(self.rendered[page.id].figures)
                part["figures"] = len(names)
                figures |= names
                authors.add(part["author"])
            dates = [p["date"] for p in parts if p["date"]]
            out.append({"name": name, "slug": slugify(name), "url": f"/series/{slugify(name)}/", "parts": parts,
                        "count": len(parts), "about": str(meta.get("intro") or meta.get("about") or ""),
                        "figures": len(figures), "authors": sorted(a for a in authors if a),
                        "external": all(not p["local"] for p in parts), "latest": max(dates) if dates else date.min})
        own = sorted([s for s in out if not s["external"]], key=lambda s: s["latest"], reverse=True)
        return own + [s for s in out if s["external"]]

    def series_meta(self, name: str) -> dict:
        """Accepted highlights in content/series/<slug>.yml: {intro: str, parts: {page id: [highlight, …]}}."""
        path = self.cfg.content_dir / "series" / f"{slugify(name)}.yml"
        if not path.exists():
            return {}
        try:
            import yaml
            data = content.load_yaml(path.read_text(encoding="utf-8"), path.name) or {}
        except Exception as exc:                                       # noqa: BLE001 - optional file
            note(f"{path.name} could not be read ({exc}); its highlights are skipped", self.notes, self.quiet)
            return {}
        if "parts" not in data:
            data = {"parts": {k: v for k, v in data.items() if isinstance(v, list)}, "intro": data.get("intro", "")}
        return data

    def topic_groups(self) -> list:
        groups: dict = {}
        for slug, t in self.topics.items():
            groups.setdefault(t["group"] or "Topics", []).append(slug)
        return list(groups.items())

    def write_topics(self) -> None:
        counts = self.tag_counts
        figmod = _optional("figures")
        nfig = {}
        for slug in self.topics:
            if not counts.get(slug):
                continue
            t = self.topic(slug)
            s = mapview.series_for_tag(self.mapdata, slug) or {"parts": []}
            parts = []
            for part in s["parts"]:
                if part["id"] not in self.by_id:
                    continue
                part = dict(part, url=self.by_id[part["id"]].url, kl=self.kind_singular(self.by_id[part["id"]].kind))
                part["read_first"] = [dict(r, url=self.by_id[r["id"]].url) for r in part.get("read_first", [])
                                      if r["id"] in self.by_id]
                parts.append(part)
            figures = []
            if figmod is not None:
                for part in parts:
                    page = self.by_id[part["id"]]
                    if not page.local:
                        continue
                    for name, section, anchor in self.figure_places(page):
                        if name in {f["name"] for f in figures}:
                            continue
                        try:
                            html = Markup(figmod.figure_html(name, cfg=self.cfg))
                        except Exception:                              # noqa: BLE001 - shown on its page already
                            continue
                        figures.append({"name": name, "html": html, "section": section, "anchor": anchor,
                                        "from": {"id": page.id, "title": page.title, "url": page.url}})
            shared: dict = {}
            for p in self.pages:
                if slug in p.topics:
                    for other in p.topics:
                        if other != slug:
                            shared[other] = shared.get(other, 0) + 1
            near = [{"slug": o, "label": self.topic(o)["label"], "shared": n}
                    for o, n in sorted(shared.items(), key=lambda kv: (-kv[1], kv[0]))[:8]]
            nfig[slug] = len(figures)
            n = len(parts)
            ctx = self.base_context(f"/topics/{slug}/", t["label"],
                                    seo.cut(f"{t['label']}: {n} page{'' if n == 1 else 's'} on this site in reading "
                                            "order, with the interactive figures that explain it."), here="/topics/")
            ctx.update({"slug": slug, "t": t, "parts": parts, "figures": figures, "near": near,
                        "intro": Markup(md.render_inline(t["blurb"], self.cfg.base)) if t["blurb"] else ""})
            self.write(f"/topics/{slug}/", "topic.html", ctx)
        ctx = self.base_context("/topics/", "Topics", seo.cut("Every topic on this site: the pages about it in "
                                                               "reading order and the figures that explain it."),
                                here="/topics/")
        ctx.update({"groups": [(g, [s for s in slugs if counts.get(s)]) for g, slugs in self.topic_groups()],
                    "counts": counts, "nfig": nfig, "topics_map": self.topics})
        self.write("/topics/", "topics.html", ctx)

    def figure_places(self, page: Page) -> list:
        """(figure name, section title, section anchor) for each ::figure in a page, in order."""
        anchors = {t["text"]: t["id"] for t in self.rendered[page.id].toc}
        section, anchor, out = "", "", []
        for line in page.body.split("\n"):
            h = re.match(r"^##\s+(.+?)\s*(?:\{#([\w:-]+)\})?\s*$", line)
            if h:
                section = h.group(1).strip()
                anchor = h.group(2) or anchors.get(section, slugify(section))
            f = re.match(r"^\s*::figure\s+([\w-]+)", line)
            if f:
                out.append((f.group(1), section, anchor))
        return out

    def write_series(self) -> None:
        if not self.cfg["features"].get("series", True):
            return
        all_series = self.series_list()
        desc = "Pages written to be read in order, each series on its own page with the highlights of every part."
        ctx = self.base_context("/series/", "Series", seo.cut(desc), here="/series/")
        ctx.update({"series": all_series, "one": None})
        self.write("/series/", "series.html", ctx)
        for s in all_series:
            lead = f"{s['name']}, {s['count']} parts in reading order"
            ctx = self.base_context(s["url"], f"{s['name']}: a series", seo.cut(f"{lead}: {s['about']}" if s["about"] else lead),
                                    here="/series/")
            ctx.update({"series": all_series, "one": s})
            self.write(s["url"], "series.html", ctx)

    def write_specials(self) -> None:
        cfg = self.cfg
        counts = self.tag_counts
        if cfg["features"].get("explore", True):
            ctx = self.base_context("/explore/", "Explore", seo.cut(f"A map of everything on {cfg['site']['name']}: "
                                                                    "each page below what it builds on."),
                                    here="/explore/")
            kinds_seen = []
            for kind in cfg["kinds"]:
                t = self.map_type(kind)
                if t not in [k for k, _, _ in kinds_seen]:
                    kinds_seen.append((t, cfg["kinds"][kind]["label"], self.kind_singular(kind).lower()))
            items = sorted(({"id": p.id, "short": str(p.meta.get("short") or p.title)} for p in self.pages),
                           key=lambda i: i["short"].lower())
            ctx.update({"tag_counts": counts, "groups": self.topic_groups(), "topics_map": self.topics,
                        "map_kinds": kinds_seen, "items": items, "mapview_url": self.mapview_url})
            self.write("/explore/", "explore.html", ctx)
        if cfg["features"].get("ask", True):
            ctx = self.base_context("/ask/", "Ask", seo.cut(f"Ask a question about the pages of {cfg['site']['name']}; "
                                                            "the answer points at the pages and sections where the "
                                                            "information is."), here="/ask/")
            examples = list(cfg["home"].get("ask_examples") or [])
            if not examples:
                local = [p for p in self.local_pages if p.summary]
                if len(local) >= 2:
                    a, b = local[0], local[-1]
                    examples.append(f"What connects {a.meta.get('short') or a.title} and {b.meta.get('short') or b.title}?")
                for p in local[:3]:
                    examples.append(f"What should I read before {p.meta.get('short') or p.title}?")
            ctx.update({"examples": examples[:4]})
            self.write("/ask/", "ask.html", ctx)
        ctx = self.base_context("/404.html", "Page not found", "This page does not exist.", nav=[])
        self.write("/404.html", "404.html", ctx)

    # ---- steps 8-11
    def write_figure_assets(self) -> None:
        figmod = _optional("figures")
        used = {name for r in self.rendered.values() for name in r.figures}
        if figmod is None:
            if used:
                note("bazinga/figures.py is not there yet; figures stay static", self.notes, self.quiet)
            return
        figmod.write_assets(self.cfg, used, self.out)

    def write_data(self) -> None:
        """What the theme's scripts read: the preview cards (data/site.js), the map and every page's view."""
        data = self.out / "data"
        (data / "view").mkdir(parents=True, exist_ok=True)
        dump = lambda path, obj: path.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")),  # noqa: E731
                                                 encoding="utf-8")
        (data / "site.js").write_text("window.SITE=" + json.dumps({"nodes": self.linked(self.site_nodes()), "kinds": self.type_labels()},
                                                                   ensure_ascii=False, separators=(",", ":"))
                                      .replace("</", "<\\/") + ";\n", encoding="utf-8")
        dump(data / "map.json", self.layout)
        dump(data / "mapdata.json", self.mapdata)
        dump(data / "series.json", mapview.find_series(self.mapdata))
        for p in self.pages:
            dump(data / "view" / (p.id.replace(":", "-") + ".json"), self.linked(self.view(p.id)))
        (self.out / "figures").mkdir(parents=True, exist_ok=True)
        shutil.copyfile(Path(mapview.__file__), self.out / "figures" / "_mapview.py")

    def write_wiki(self) -> None:
        wmod = _optional("wiki")
        if wmod is None:
            note("bazinga/wiki.py is not there yet; no llms.txt, passages or map data", self.notes, self.quiet)
            return
        local = self.local_pages
        wmod.write_site_files(self.cfg, local, {i: r for i, r in self.rendered.items() if i in {p.id for p in local}},
                              self.graph, self.out)
        if not self.drafts and self.strict:
            wmod.write_repo_wiki(self.cfg, local, self.graph)

    def write_seo(self) -> None:
        cfg = self.cfg
        local = self.local_pages
        newest = max((p.updated or p.date for p in local), default=None)
        entries = [("/", newest)]
        for kind in cfg["kinds"]:
            items = [p for p in self.pages if p.kind == kind]
            entries.append((f"/{kind}/", max((p.updated or p.date for p in items), default=None)))
        entries += [(p.url, p.updated or p.date) for p in local]
        if (cfg.content_dir / "cv.yml").exists():
            entries.append(("/cv/", None))
        entries.append(("/topics/", newest))
        used = {t for p in self.pages for t in p.topics}
        entries += [(f"/topics/{t}/", max((p.updated or p.date for p in self.pages if t in p.topics), default=None))
                    for t in self.topics if t in used]
        if cfg["features"].get("series", True):
            entries += [("/series/", newest)] + [(s["url"], None) for s in self.series_list()]
        if cfg["features"].get("explore", True):
            entries.append(("/explore/", newest))
        if cfg["features"].get("ask", True):
            entries.append(("/ask/", None))
        if self.drafts:
            # A drafts build is a private preview: keep search engines out entirely.
            (self.out / "robots.txt").write_text("User-agent: *\nDisallow: /\n", encoding="utf-8")
            return
        (self.out / "sitemap.xml").write_text(seo.sitemap(cfg, entries), encoding="utf-8")
        (self.out / "robots.txt").write_text(seo.robots(cfg), encoding="utf-8")
        if cfg["features"].get("feed", True):
            html = {i: r.html for i, r in self.rendered.items()}
            (self.out / "feed.xml").write_text(seo.feed(cfg, local, html), encoding="utf-8")

    def write_static(self) -> None:
        self.theme.copy_assets(self.out)
        css = md.pygments_css().encode()
        (self.out / "assets" / "css").mkdir(parents=True, exist_ok=True)
        (self.out / "assets" / "css" / "pygments.css").write_bytes(css)
        static = self.cfg.static_dir
        if static.is_dir():
            shutil.copytree(static, self.out / "static", dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns(".DS_Store", "*.tmp"))

    # ---- the whole thing
    def prepare(self) -> None:
        """Everything the templates share: the graph, series, the map and the version stamps of the data files."""
        self.graph = build_graph(self.pages, self.rendered, self.site, self.notes if self.quiet else None)
        self.series_map = self._series_map()
        self._mapdata = None
        self.views = {}
        self.layout = mapview.layout(self.mapdata)
        stamp = hashlib.sha256(json.dumps(self.mapdata, sort_keys=True, default=str).encode()).hexdigest()[:10]
        self.site_data_url = self.link(f"/data/site.js?v={stamp}")
        self.mapview_url = self.link(f"/figures/_mapview.py?v={hashlib.sha256(Path(mapview.__file__).read_bytes()).hexdigest()[:10]}")
        self.theme.set_hash("css/pygments.css", md.pygments_css().encode())

    def run(self, out: Path | None = None) -> BuildResult:
        t0 = time.perf_counter()
        final = Path(out) if out else self.cfg.out_dir
        self.load()
        self.render_all()
        self.prepare()
        staging = final.parent / (final.name + ".partial")
        if staging.exists():
            shutil.rmtree(staging)
        staging.mkdir(parents=True)
        self.out, self.count = staging, 0
        try:
            self.write_pages()
            self.write_lists()
            self.write_home()
            self.write_cv()
            self.write_topics()
            self.write_series()
            self.write_specials()
            self.write_figure_assets()
            self.write_data()
            self.write_wiki()
            self.write_seo()
            self.write_static()
        except BaseException:
            shutil.rmtree(staging, ignore_errors=True)
            raise
        _swap(staging, final)
        self.out = final
        return BuildResult(final, self.pages, self.rendered, self.issues, time.perf_counter() - t0, self.notes,
                           self.count)

    def _series_map(self) -> dict:
        try:
            raw = self.graph.series()
        except Exception:                                              # noqa: BLE001
            raw = FallbackGraph(self.pages, self.rendered).series()
        return {name: [i for i in ids if i in self.by_id] for name, ids in raw.items()}


def _swap(staging: Path, final: Path) -> None:
    """Replace ``final`` with ``staging`` with only a moment where neither exists."""
    old = final.parent / (final.name + ".old")
    if old.exists():
        shutil.rmtree(old)
    if final.exists():
        os.replace(final, old)
    os.replace(staging, final)
    if old.exists():
        shutil.rmtree(old, ignore_errors=True)


# ------------------------------------------------------------------------------------------------------- public
def build(cfg=None, drafts: bool = False, strict: bool | None = None, dev: bool = False, quiet: bool = False,
          out: Path | None = None) -> BuildResult:
    """Build the whole site. Raises BuildError (production) when a page has errors."""
    cfg = cfg or config.load()
    return Builder(cfg, drafts=drafts, strict=strict, dev=dev, quiet=quiet).run(out)


_PREVIEW: dict = {}   # site root -> {"stamp", "builder", "pages", "rendered"}


def _preview_stamp(cfg) -> tuple:
    """What the other pages' rendering depends on: every content file, the references, topics and site.yml."""
    files = list(content.content_files(cfg)) + [cfg.content_dir / "references.yml", cfg.content_dir / "topics.yml",
                                                  cfg.root / "site.yml"]
    return tuple((str(f), f.stat().st_mtime_ns) for f in files if f.exists())


def _preview_base(cfg) -> dict:
    """Every page rendered once, kept until a content file changes; a preview then re-renders only its own page."""
    stamp = _preview_stamp(cfg)
    cached = _PREVIEW.get(str(cfg.root))
    if cached and cached["stamp"] == stamp:
        return cached
    b = Builder(cfg, drafts=True, strict=False, quiet=True)
    b.load()
    rendered = {p.id: md.render(p, b.site) for p in b.pages}
    cached = {"stamp": stamp, "builder": b, "pages": {p.id: p for p in b.pages}, "rendered": rendered}
    _PREVIEW[str(cfg.root)] = cached
    return cached


def preview_html(page: Page, cfg) -> str:
    """One page as full HTML for the Editor preview: drafts visible, problems shown in the page, nothing written.

    The other pages are rendered once and cached (until a content file changes), so a preview costs one page render.
    """
    base = _preview_base(cfg)
    b: Builder = base["builder"]
    pages = dict(base["pages"])
    pages[page.id] = page
    b.pages = content.sort_newest(list(pages.values()))
    b.by_id = pages
    b.site = make_site_index(cfg, b.pages, b.references, b.topics, preview=True)
    b.rendered = dict(base["rendered"])
    b.rendered[page.id] = md.render(page, b.site)
    b.issues = {page.id: page_issues(page, b.rendered[page.id], b.site)}
    b.graph = build_graph(b.pages, b.rendered, b.site, b.notes)
    b.series_map = b._series_map()
    b._mapdata, b.views, b.layout = None, {}, None
    b.site_data_url = "/data/site.js"
    b.mapview_url = "/figures/_mapview.py"
    b.theme._hash.clear()
    b.theme.set_hash("css/pygments.css", md.pygments_css().encode())
    ctx = b.page_context(page)
    ctx["preview"] = True
    template = "project.html" if b.role(page.kind) == "project" else "page.html"
    return b.env.get_template(template).render(**ctx)


def main(argv=None) -> int:
    """``python -m bazinga.build`` – the same as ``python -m bazinga build``."""
    from .cli import main as cli_main
    return cli_main(["build", *(argv or [])])
