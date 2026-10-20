"""Pages, topics and references: the site's content, read from ``content/``.

A page is ``content/<kind>/<slug>.md``: YAML front matter between ``---`` lines, then Markdown. :func:`parse` turns one
file into a :class:`Page` without touching any other file, so the Studio can parse an unsaved buffer. Problems that a
build should report (a malformed date, a list given as a string) are kept on ``page.problems`` with their line
number; ``checks.py`` turns them into issues.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

import yaml

from .config import kind_id_prefix

_FENCE = re.compile(r"^---\s*$")
_SLUG_OK = re.compile(r"^[a-z0-9][a-z0-9-]*$")


class ContentError(Exception):
    """A content file cannot be read at all (for example, broken YAML)."""

    def __init__(self, message: str, path: Path | None = None, line: int | None = None, hint: str = ""):
        super().__init__(message)
        self.message, self.path, self.line, self.hint = message, path, line, hint

    def __str__(self) -> str:
        where = f"{self.path}:{self.line}: " if self.path and self.line else (f"{self.path}: " if self.path else "")
        return f"{where}{self.message}" + (f" ({self.hint})" if self.hint else "")


def today() -> date:
    """Today's date. Tests patch this to check scheduled pages."""
    return date.today()


@dataclass
class Page:
    id: str
    kind: str
    slug: str
    path: Path
    url: str
    meta: dict
    body: str
    body_line: int
    title: str = ""
    date: date | None = None
    updated: date | None = None
    status: str = "published"
    summary: str = ""
    description: str = ""
    topics: list = field(default_factory=list)
    series: dict | None = None
    builds_on: list = field(default_factory=list)
    cites: list = field(default_factory=list)
    cover: str = ""
    problems: list = field(default_factory=list)   # [(line, message, hint)] found while parsing the front matter
    meta_lines: dict = field(default_factory=dict)  # front-matter key -> line number in the file

    @property
    def public(self) -> bool:
        """Published and dated today or earlier: the only pages a production build writes."""
        return self.status == "published" and self.date is not None and self.date <= today()

    @property
    def scheduled(self) -> bool:
        """Published with a future date: it goes live on the first build after that date."""
        return self.status == "published" and self.date is not None and self.date > today()

    @property
    def state(self) -> str:
        """``draft``, ``scheduled`` or ``published`` (for labels)."""
        if self.status != "published":
            return "draft"
        return "scheduled" if self.scheduled or self.date is None else "published"

    def line_of(self, key: str) -> int | None:
        """The file line of a front-matter key, for issue messages."""
        return self.meta_lines.get(key)


def split_front_matter(text: str) -> tuple[str, str, int]:
    """Split a file into (front-matter YAML, body, line number of the body's first line).

    A file without front matter is all body, starting on line 1.
    """
    lines = text.split("\n")
    if not lines or not _FENCE.match(lines[0]):
        return "", text, 1
    for i in range(1, len(lines)):
        if _FENCE.match(lines[i]):
            return "\n".join(lines[1:i]), "\n".join(lines[i + 1:]), i + 2
    raise ContentError("the front matter starts with --- but never ends", line=1,
                       hint="add a line with only --- after the last front-matter field")


def _key_lines(fm: str) -> dict:
    """Map each top-level front-matter key to its line in the file (front matter starts on line 2)."""
    out = {}
    for i, line in enumerate(fm.split("\n")):
        m = re.match(r"^([A-Za-z_][\w-]*)\s*:", line)
        if m:
            out[m.group(1)] = i + 2
    return out


def _as_date(value, key: str, line, problems: list) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value).strip())
    except ValueError:
        problems.append((line, f"{key}: {value!r} is not a date", "write dates as YYYY-MM-DD, e.g. 2026-10-20"))
        return None


def _as_list(value, key: str, line, problems: list) -> list:
    if value in (None, ""):
        return []
    if isinstance(value, str):
        # "a, b" is a common slip; accept it but say how to write a list.
        items = [v.strip() for v in value.split(",") if v.strip()]
        if len(items) > 1:
            problems.append((line, f"{key} is written as text, not a list", f"write it as {key}: [{', '.join(items)}]"))
        return items
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    problems.append((line, f"{key} must be a list", f"write it as {key}: [a, b]"))
    return []


def kind_and_slug(path: Path, cfg) -> tuple[str, str]:
    """``content/posts/attention.md`` -> (``posts``, ``attention``)."""
    path = Path(path)
    kind = path.parent.name
    if kind not in cfg["kinds"]:
        kind = next(iter(cfg["kinds"]))
    return kind, path.stem


def parse(text: str, path: Path, cfg) -> Page:
    """Parse one content file. Never reads other files; raises ContentError only for unreadable front matter."""
    path = Path(path)
    kind, slug = kind_and_slug(path, cfg)
    try:
        fm, body, body_line = split_front_matter(text)
    except ContentError as exc:
        exc.path = path
        raise
    try:
        meta = yaml.safe_load(fm) if fm.strip() else {}
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        line = mark.line + 2 if mark else 1
        raise ContentError(f"the front matter is not valid YAML: {getattr(exc, 'problem', exc)}", path, line,
                           "check quotes and colons; text containing ': ' needs quotes") from None
    if not isinstance(meta, dict):
        raise ContentError("the front matter must be key: value lines", path, 2)

    lines = _key_lines(fm)
    problems: list = []
    page = Page(
        id=f"{kind_id_prefix(cfg, kind)}:{slug}", kind=kind, slug=slug, path=path, url=f"/{kind}/{slug}/",
        meta=meta, body=body, body_line=body_line, meta_lines=lines, problems=problems,
    )
    page.title = str(meta.get("title") or "").strip()
    page.status = str(meta.get("status") or "published").strip().lower()
    if page.status not in ("draft", "published"):
        problems.append((lines.get("status"), f"status {page.status!r} is not draft or published",
                         "write status: draft while writing, and status: published (or leave it out) to publish"))
        page.status = "draft"
    page.date = _as_date(meta.get("date"), "date", lines.get("date"), problems)
    page.updated = _as_date(meta.get("updated"), "updated", lines.get("updated"), problems)
    page.summary = " ".join(str(meta.get("summary") or "").split())
    page.description = " ".join(str(meta.get("description") or "").split())
    page.topics = _as_list(meta.get("topics"), "topics", lines.get("topics"), problems)
    page.builds_on = _as_list(meta.get("builds_on"), "builds_on", lines.get("builds_on"), problems)
    page.cites = _as_list(meta.get("cites"), "cites", lines.get("cites"), problems)
    page.cover = str(meta.get("cover") or "")
    page.series = _series(meta.get("series"), lines.get("series"), problems)
    if not _SLUG_OK.match(slug):
        problems.append((None, f"the file name {path.name!r} is not a clean URL",
                         "use lowercase letters, digits and dashes, e.g. my-first-post.md"))
    return page


def _series(value, line, problems: list) -> dict | None:
    if value in (None, ""):
        return None
    if not isinstance(value, dict) or "name" not in value:
        problems.append((line, "series must be {name: ..., part: n}", 'write series: {name: "Transformers", part: 2}'))
        return None
    try:
        part = int(value.get("part", 0))
    except (TypeError, ValueError):
        problems.append((line, "series part must be a number", "write part: 2"))
        part = 0
    return {"name": str(value["name"]).strip(), "part": part}


def load_file(path: Path, cfg) -> Page:
    path = Path(path)
    return parse(path.read_text(encoding="utf-8"), path, cfg)


def content_files(cfg) -> list[Path]:
    """Every Markdown file of every configured kind, in a stable order."""
    files = []
    for kind in cfg["kinds"]:
        folder = cfg.content_dir / kind
        if folder.is_dir():
            files += sorted(p for p in folder.glob("*.md") if not p.name.startswith(("_", ".")))
    return files


def sort_newest(pages: list[Page]) -> list[Page]:
    return sorted(pages, key=lambda p: (p.date or date.min, p.title.lower()), reverse=True)


def load_pages(cfg, drafts: bool = False) -> list[Page]:
    """All pages, newest first. Only public pages unless ``drafts`` (previews, the Studio, ``build --drafts``)."""
    pages = [load_file(p, cfg) for p in content_files(cfg)]
    if not drafts:
        pages = [p for p in pages if p.public]
    return sort_newest(pages)


def load_topics(cfg) -> dict[str, dict]:
    """``content/topics.yml`` as slug -> {slug, label, blurb, group}, in file order."""
    path = cfg.content_dir / "topics.yml"
    if not path.exists():
        return {}
    data = _yaml_file(path) or {}
    out: dict[str, dict] = {}
    for group in data.get("groups") or []:
        for t in group.get("topics") or []:
            slug = str(t.get("slug") or "").strip()
            if slug:
                out[slug] = {"slug": slug, "label": str(t.get("label") or slug.replace("-", " ").title()),
                             "blurb": str(t.get("blurb") or ""), "group": str(group.get("name") or "")}
    return out


def load_references(cfg) -> dict[str, dict]:
    """``content/references.yml`` as KEY -> {title, authors, year, venue, arxiv, doi, url}."""
    path = cfg.content_dir / "references.yml"
    if not path.exists():
        return {}
    data = _yaml_file(path) or {}
    return {str(k): dict(v or {}) for k, v in data.items()}


def _yaml_file(path: Path):
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        raise ContentError(f"not valid YAML: {getattr(exc, 'problem', exc)}", path,
                           mark.line + 1 if mark else None) from None


def slugify(text: str) -> str:
    """A URL slug: lowercase ASCII words joined by dashes."""
    import unicodedata
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "page"


def word_count(text: str) -> int:
    """Words of prose, ignoring code fences, math and Markdown punctuation (for reading time)."""
    text = re.sub(r"^\s*(`{3,}|~{3,}).*?^\s*\1", " ", text, flags=re.S | re.M)   # fenced code
    text = re.sub(r"`[^`\n]*`", " x ", text)                                        # inline code
    text = re.sub(r"^\s*\$\$.*?\$\$", " x ", text, flags=re.S | re.M)              # display maths
    return len(re.findall(r"[A-Za-z0-9À-ɏ]+(?:['’][A-Za-z]+)?", text))


def reading_minutes(page: Page) -> int:
    return max(1, round(word_count(page.body) / 230))
