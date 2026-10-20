"""Build the site into ``_site/``.

The order (docs/INTERFACES.md): config → pages → SiteIndex → render → graph → page templates → lists, home, topics,
series, explore, ask, 404 → figure assets → wiki files → sitemap, robots, feed → static files.

Drafts and future-dated pages are never written unless ``drafts=True`` (``python -m tessera build --drafts``, for
previews). A production build stops on any error and lists them all with file and line; a lenient build (``serve``,
previews) shows them in the page instead. The site is built into a temporary folder and swapped in at the end, so a
running dev server never serves a half-written site.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import jinja2
from markupsafe import Markup

from . import checks, config, content, seo, vendor
from . import markdown as md
from .content import Page, slugify

ENGINE_THEME = Path(__file__).parent / "theme"
PER_PAGE = 10
LATEST_ON_HOME = 6


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
    """Import a module that another part of Tessera provides, or None if it is not there yet."""
    import importlib
    try:
        return importlib.import_module(f"tessera.{name}")
    except ModuleNotFoundError as exc:
        if exc.name in (f"tessera.{name}",):
            return None
        raise


# --------------------------------------------------------------------------------------------- the site index
def make_site_index(cfg, pages, references=None, topics=None, preview=True, hidden=None) -> md.SiteIndex:
    """A SiteIndex for rendering: the Studio and previews pass every page (drafts included)."""
    if references is None:
        references = content.load_references(cfg)
    if topics is None:
        topics = content.load_topics(cfg)
    return md.SiteIndex(pages, references, topics, cfg, preview=preview, hidden=hidden)


def page_issues(page: Page, rendered: md.Rendered, site: md.SiteIndex) -> list:
    return checks.sort_issues(checks.check_front_matter(page, site) + rendered.issues + checks.check_body(page, site))


# ---------------------------------------------------------------------------------------------------- the graph
class FallbackGraph:
    """A minimal stand-in for tessera.graph (used only while that module does not exist)."""

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
        note("tessera/graph.py is not there yet; connections use a simple fallback and the map is empty", notes)
        return FallbackGraph(pages, rendered)
    return gmod.build_graph(pages, rendered, site)


# -------------------------------------------------------------------------------------------------- the theme
class Theme:
    """Templates and assets, with ``<root>/theme/…`` shadowing ``tessera/theme/…`` file by file."""

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
        """``/assets/<rel>?v=<hash>``: the hash changes when the file does, so browsers never use a stale copy."""
        if rel not in self._hash:
            path = self.asset_path(rel)
            self._hash[rel] = hashlib.sha256(path.read_bytes()).hexdigest()[:10] if path else "missing"
        return f"/assets/{rel}?v={self._hash[rel]}"

    def set_hash(self, rel: str, data: bytes) -> None:
        self._hash[rel] = hashlib.sha256(data).hexdigest()[:10]

    def env(self) -> jinja2.Environment:
        loader = jinja2.FileSystemLoader([str(d / "templates") for d in self.dirs])
        env = jinja2.Environment(loader=loader, autoescape=jinja2.select_autoescape(["html", "xml"]),
                                 trim_blocks=True, lstrip_blocks=True, undefined=jinja2.ChainableUndefined)
        env.filters["date"] = fmt_date
        env.filters["isodate"] = lambda d: d.isoformat() if d else ""
        env.filters["json"] = lambda v: Markup(json.dumps(v, ensure_ascii=False).replace("</", "<\\/"))
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


def fmt_date(d) -> str:
    if not d:
        return ""
    return f"{d.day} {d:%B %Y}"


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

    # ---- steps 2-5
    def load(self) -> None:
        cfg = self.cfg
        everything = content.load_pages(cfg, drafts=True)
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

    # ---- shared template context
    def node(self, ident: str) -> dict | None:
        p = self.by_id.get(ident)
        if p is None:
            return None
        return {"id": p.id, "title": p.title, "url": p.url, "summary": p.summary, "kind": p.kind,
                "kind_label": self.kind_singular(p.kind), "date": p.date, "topics": p.topics,
                "minutes": content.reading_minutes(p), "series": p.series, "state": p.state}

    def nodes(self, ids) -> list:
        return [n for n in (self.node(i) for i in ids) if n]

    def kind_singular(self, kind: str) -> str:
        return str(self.cfg["kinds"].get(kind, {}).get("singular", kind))

    def topic(self, slug: str) -> dict:
        return self.topics.get(slug) or {"slug": slug, "label": slug.replace("-", " ").title(), "blurb": "",
                                         "group": ""}

    def base_context(self, url: str, title: str, description: str, page: Page | None = None,
                     kind: str = "website") -> dict:
        cfg = self.cfg
        full_title = title if title == cfg["site"]["name"] else f"{title} · {cfg['site']['name']}"
        theme = cfg["theme"]
        return {
            "cfg": cfg, "site": cfg["site"], "nav": cfg["nav"], "features": cfg["features"], "theme": theme,
            "asset": self.theme.asset_url, "has_asset": self.theme.has_asset, "vendor": self.vendor,
            "font_urls": vendor.font_urls(theme),
            "page_title": full_title, "title": title, "description": description,
            "canonical": seo.absolute(cfg, url), "url": url,
            "og": seo.open_graph(cfg, title, description, url, page),
            "jsonld": seo.jsonld(cfg, page, url, kind),
            "body_page_id": page.id if page is not None else "",
            "topic": self.topic, "node": self.node, "kinds": cfg["kinds"],
            "kinds_labels": {k: v["label"] for k, v in cfg["kinds"].items()},
            "dev": self.dev, "drafts": self.drafts, "year": date.today().year,
            "has_feed": bool(cfg["features"].get("feed")),
            "markdown_url": (url + "index.md") if page is not None and not self.drafts else "",
        }

    def write(self, url: str, template: str, ctx: dict) -> None:
        html = self.env.get_template(template).render(**ctx)
        rel = url.strip("/")
        path = self.out / rel / "index.html" if not rel.endswith(".html") else self.out / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html, encoding="utf-8")
        self.count += 1

    # ---- step 6
    def page_context(self, page: Page) -> dict:
        r = self.rendered[page.id]
        g = self.graph
        shown: set = {page.id}

        def fresh(ids):
            out = [i for i in ids if i not in shown and i in self.by_id]
            shown.update(out)
            return out

        connections = {"builds_on": self.nodes(fresh(g.builds_on(page.id))),
                       "read_next": self.nodes(fresh(g.read_next(page.id))),
                       "backlinks": self.nodes(fresh(g.backlinks(page.id))),
                       "related": self.nodes(fresh(g.related(page.id, 5)))}
        ctx = self.base_context(page.url, page.title, seo.describe(page, self.cfg), page)
        ctx.update({
            "page": page, "html": Markup(r.html), "toc": r.toc, "connections": connections,
            "has_connections": any(connections.values()),
            "references": md.references(r, self.site), "series_nav": self.series_nav(page),
            "reading_minutes": content.reading_minutes(page),
            "page_topics": [self.topic(t) for t in page.topics], "kind_label": self.kind_singular(page.kind),
            "kind_list_url": f"/{page.kind}/", "kind_list_label": self.cfg["kinds"][page.kind]["label"],
            "issues": self.issues.get(page.id, []) if (self.drafts or not self.strict) else [],
        })
        return ctx

    def series_nav(self, page: Page) -> dict | None:
        if not page.series:
            return None
        name = page.series["name"]
        ids = self.series_map.get(name) or []
        if page.id not in ids:
            return None
        idx = ids.index(page.id)
        return {"name": name, "url": f"/series/{slugify(name)}/", "parts": self.nodes(ids), "index": idx,
                "prev": self.node(ids[idx - 1]) if idx > 0 else None,
                "next": self.node(ids[idx + 1]) if idx + 1 < len(ids) else None, "total": len(ids)}

    def write_pages(self) -> None:
        for page in self.pages:
            self.write(page.url, "page.html", self.page_context(page))

    # ---- step 7
    def write_lists(self) -> None:
        for kind, spec in self.cfg["kinds"].items():
            items = [p for p in self.pages if p.kind == kind]
            chunks = [items[i:i + PER_PAGE] for i in range(0, len(items), PER_PAGE)] or [[]]
            for n, chunk in enumerate(chunks, 1):
                url = f"/{kind}/" if n == 1 else f"/{kind}/page/{n}/"
                title = spec["label"] if n == 1 else f"{spec['label']} (page {n})"
                ctx = self.base_context(url, title, seo.cut(f"{spec['label']} by {self.cfg['site']['author']}."))
                ctx.update({"kind": kind, "label": spec["label"], "items": self.nodes(p.id for p in chunk),
                            "pager": self.pager(kind, n, len(chunks)), "total": len(items)})
                self.write(url, "list.html", ctx)

    @staticmethod
    def pager(kind: str, n: int, total: int) -> dict | None:
        if total <= 1:
            return None
        link = lambda k: f"/{kind}/" if k == 1 else f"/{kind}/page/{k}/"  # noqa: E731
        return {"page": n, "total": total, "prev": link(n - 1) if n > 1 else None,
                "next": link(n + 1) if n < total else None, "pages": [(k, link(k)) for k in range(1, total + 1)]}

    def write_home(self) -> None:
        cfg = self.cfg
        ctx = self.base_context("/", cfg["site"]["name"], seo.describe(None, cfg), kind="home")
        ctx.update({
            "intro": Markup(md.render_inline(cfg["home"].get("intro") or "")),
            "show": cfg["home"].get("show") or [],
            "latest": self.nodes(p.id for p in self.pages[:LATEST_ON_HOME]),
            "series_list": self.series_list()[:4],
            "map_svg": Markup(self.map_teaser()), "page_count": len(self.pages),
        })
        self.write("/", "home.html", ctx)

    def map_teaser(self) -> str:
        """A small static picture of the map: dots at the graph layout, lines for the strong edges."""
        try:
            pos = self.graph.layout()
        except Exception:                                              # noqa: BLE001 - the teaser is optional
            pos = {}
        if not pos:
            return ""
        w, h, pad = 560, 260, 18
        xy = {k: (pad + v[0] * (w - 2 * pad), pad + v[1] * (h - 2 * pad)) for k, v in pos.items() if k in self.by_id}
        lines = []
        for e in getattr(self.graph, "edges", []):
            if e.get("type") in ("topic",) or e.get("source") not in xy or e.get("target") not in xy:
                continue
            (x1, y1), (x2, y2) = xy[e["source"]], xy[e["target"]]
            lines.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}"/>')
        dots = []
        for k, (x, y) in xy.items():
            p = self.by_id[k]
            title = jinja2.utils.markupsafe.escape(p.title)
            dots.append(f'<a href="{p.url}"><circle cx="{x:.1f}" cy="{y:.1f}" r="5"><title>{title}</title>'
                        "</circle></a>")
        return (f'<svg class="map-teaser" viewBox="0 0 {w} {h}" role="img" aria-label="A map of the pages and how '
                f'they connect"><g class="edges">{"".join(lines)}</g><g class="dots">{"".join(dots)}</g></svg>')

    def series_list(self) -> list:
        out = []
        for name, ids in self.series_map.items():
            parts = self.nodes(ids)
            if parts:
                out.append({"name": name, "slug": slugify(name), "url": f"/series/{slugify(name)}/", "parts": parts,
                            "count": len(parts), "intro": self.series_meta(name).get("intro", "")})
        return out

    def series_meta(self, name: str) -> dict:
        """Accepted highlights in content/series/<slug>.yml: {intro: str, parts: {page id: [highlight, …]}}."""
        path = self.cfg.content_dir / "series" / f"{slugify(name)}.yml"
        if not path.exists():
            return {}
        try:
            import yaml
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception as exc:                                       # noqa: BLE001 - optional file
            note(f"{path.name} could not be read ({exc}); its highlights are skipped", self.notes, self.quiet)
            return {}
        if "parts" not in data:
            data = {"parts": {k: v for k, v in data.items() if isinstance(v, list)}, "intro": data.get("intro", "")}
        return data

    def write_topics(self) -> None:
        used: dict = {}
        for p in self.pages:
            for t in p.topics:
                used.setdefault(t, []).append(p.id)
        groups: dict = {}
        for slug, t in self.topics.items():
            groups.setdefault(t["group"] or "Topics", []).append({**t, "count": len(used.get(slug, []))})
        ctx = self.base_context("/topics/", "Topics", seo.cut(f"Every topic on {self.cfg['site']['name']}."))
        ctx.update({"groups": groups})
        self.write("/topics/", "topics.html", ctx)
        figmod = _optional("figures")
        for slug in self.topics:
            ids = used.get(slug, [])
            t = self.topic(slug)
            figs = []
            if figmod is not None:
                for ident in ids:
                    for name in self.rendered[ident].figures:
                        if name not in [f["name"] for f in figs] and len(figs) < 4:
                            try:
                                figs.append({"name": name, "html": Markup(figmod.figure_html(name, cfg=self.cfg)),
                                             "from": self.node(ident)})
                            except Exception:                          # noqa: BLE001 - shown on the page already
                                pass
            ctx = self.base_context(f"/topics/{slug}/", t["label"], seo.cut(t["blurb"] or t["label"]))
            ctx.update({"t": t, "items": self.nodes(ids), "figures": figs,
                        "intro": Markup(md.render_inline(t["blurb"])) if t["blurb"] else ""})
            self.write(f"/topics/{slug}/", "topic.html", ctx)

    def write_series(self) -> None:
        if not self.cfg["features"].get("series", True):
            return
        all_series = self.series_list()
        ctx = self.base_context("/series/", "Series", seo.cut(f"Series of connected posts on {self.cfg['site']['name']}."))
        ctx.update({"series_list": all_series})
        self.write("/series/", "series.html", ctx)
        for s in all_series:
            meta = self.series_meta(s["name"])
            highlights = meta.get("parts") or {}
            for part in s["parts"]:
                part["highlights"] = [str(h) for h in highlights.get(part["id"], [])][:4]
            ctx = self.base_context(s["url"], s["name"], seo.cut(meta.get("intro") or
                                                                 f"A series in {s['count']} parts."))
            ctx.update({"series": s, "one": True, "intro": Markup(md.render_inline(meta.get("intro") or ""))})
            self.write(s["url"], "series.html", ctx)

    def write_specials(self) -> None:
        cfg = self.cfg
        if cfg["features"].get("explore", True):
            ctx = self.base_context("/explore/", "Map", seo.cut(f"A map of every page on {cfg['site']['name']} and "
                                                                "how they connect."))
            groups: dict = {}
            for p in self.pages:
                groups.setdefault(self.topic(p.topics[0])["label"] if p.topics else "Other", []).append(self.node(p.id))
            ctx.update({"groups": groups, "map_svg": Markup(self.map_teaser())})
            self.write("/explore/", "explore.html", ctx)
        if cfg["features"].get("ask", True):
            ctx = self.base_context("/ask/", "Ask", seo.cut(f"Ask a question and get an answer from the pages of "
                                                            f"{cfg['site']['name']}."))
            ctx.update({"suggestions": [p.title for p in self.pages[:3]]})
            self.write("/ask/", "ask.html", ctx)
        ctx = self.base_context("/404.html", "Page not found", "This page does not exist.")
        ctx.update({"latest": self.nodes(p.id for p in self.pages[:5])})
        self.write("/404.html", "404.html", ctx)

    # ---- steps 8-11
    def write_figure_assets(self) -> None:
        figmod = _optional("figures")
        used = {name for r in self.rendered.values() for name in r.figures}
        if figmod is None:
            if used:
                note("tessera/figures.py is not there yet; figures stay static", self.notes, self.quiet)
            return
        figmod.write_assets(self.cfg, used, self.out)

    def write_wiki(self) -> None:
        wmod = _optional("wiki")
        if wmod is None:
            note("tessera/wiki.py is not there yet; no llms.txt, passages or map data", self.notes, self.quiet)
            return
        wmod.write_site_files(self.cfg, self.pages, self.rendered, self.graph, self.out)
        if not self.drafts and self.strict:
            wmod.write_repo_wiki(self.cfg, self.pages, self.graph)

    def write_seo(self) -> None:
        cfg = self.cfg
        newest = max((p.updated or p.date for p in self.pages), default=None)
        entries = [("/", newest)]
        for kind in cfg["kinds"]:
            items = [p for p in self.pages if p.kind == kind]
            entries.append((f"/{kind}/", max((p.updated or p.date for p in items), default=None)))
        entries += [(p.url, p.updated or p.date) for p in self.pages]
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
            (self.out / "feed.xml").write_text(seo.feed(cfg, self.pages, html), encoding="utf-8")

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
    def run(self, out: Path | None = None) -> BuildResult:
        t0 = time.perf_counter()
        final = Path(out) if out else self.cfg.out_dir
        self.load()
        self.render_all()
        self.graph = build_graph(self.pages, self.rendered, self.site, self.notes if self.quiet else None)
        self.series_map = self._series_map()
        self.theme.set_hash("css/pygments.css", md.pygments_css().encode())
        staging = final.parent / (final.name + ".partial")
        if staging.exists():
            shutil.rmtree(staging)
        staging.mkdir(parents=True)
        self.out, self.count = staging, 0
        try:
            self.write_pages()
            self.write_lists()
            self.write_home()
            self.write_topics()
            self.write_series()
            self.write_specials()
            self.write_figure_assets()
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
    """One page as full HTML for the Studio preview: drafts visible, problems shown in the page, nothing written.

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
    b.theme._hash.clear()
    b.theme.set_hash("css/pygments.css", md.pygments_css().encode())
    ctx = b.page_context(page)
    ctx["preview"] = True
    return b.env.get_template("page.html").render(**ctx)


def main(argv=None) -> int:
    """``python -m tessera.build`` – the same as ``python -m tessera build``."""
    from .cli import main as cli_main
    return cli_main(["build", *(argv or [])])
