"""Checks on a page: front matter, rendering problems and writing-style rules.

One function, :func:`check_page`, serves the build, ``python -m tessera check`` and the Studio's checks drawer. Every
:class:`Issue` has a level (``error`` blocks a production build and publishing; ``warning`` does not), the file line
when there is one, a plain-English message and a hint saying how to fix it.
"""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from pathlib import Path

DESCRIPTION_MAX = 155
SUMMARY_MAX = 320
DISPLAY_LINE_MAX = 60   # visible symbols in one row of a displayed equation (about a phone's width)
TOPICS_MAX = 4


@dataclass
class Issue:
    level: str                 # "error" | "warning"
    line: int | None
    message: str
    hint: str = ""
    code: str = ""

    def format(self, path=None) -> str:
        where = f"{path}:{self.line}" if path and self.line else (str(path) if path else f"line {self.line}"
                                                                     if self.line else "")
        text = f"{where}: {self.level}: {self.message}" if where else f"{self.level}: {self.message}"
        return text + (f"\n    hint: {self.hint}" if self.hint else "")

    def to_dict(self) -> dict:
        return {"level": self.level, "line": self.line, "message": self.message, "hint": self.hint, "code": self.code}


def _did_you_mean(word: str, options) -> str:
    close = difflib.get_close_matches(word, list(options), n=1, cutoff=0.6)
    return f"did you mean {close[0]}?" if close else ""


# ------------------------------------------------------------------------------------------------ front matter
def check_front_matter(page, site) -> list[Issue]:
    issues: list[Issue] = [Issue("error", line, msg, hint, "front-matter") for line, msg, hint in page.problems]
    published = page.status == "published"
    level = "error" if published else "warning"
    first = 1

    if not page.title:
        issues.append(Issue("error", page.line_of("title") or first, "the page has no title",
                            'add a line: title: "Your title"', "title"))
    if published and page.date is None and "date" not in page.meta:
        issues.append(Issue("error", first, "a published page needs a date",
                            "add date: YYYY-MM-DD (a future date schedules it)", "date"))
    if not page.summary:
        issues.append(Issue(level, page.line_of("summary") or first, "the page has no summary",
                            "add summary: two or three sentences shown in lists, the map and search results",
                            "summary"))
    elif len(page.summary) > SUMMARY_MAX:
        issues.append(Issue("warning", page.line_of("summary"), f"the summary is long ({len(page.summary)} characters)",
                            f"lists read best under {SUMMARY_MAX} characters; move detail into the page", "summary"))
    if len(page.description) > DESCRIPTION_MAX:
        issues.append(Issue("error", page.line_of("description"),
                            f"the description is {len(page.description)} characters; search engines cut it at "
                            f"{DESCRIPTION_MAX}", "shorten it, or remove it to use the summary", "description"))
    issues += _check_topics(page, site, level)
    issues += _check_builds_on(page, site)
    for key in page.explains:
        if site.references and key not in site.references:
            hint = _did_you_mean(key, site.references) or "add the paper to content/references.yml first"
            issues.append(Issue("error", page.line_of("explains"), f"explains: unknown reference key {key!r}", hint,
                                "explains-unknown"))
    if page.external and not str(page.external).startswith(("http://", "https://")):
        issues.append(Issue("error", page.line_of("external"), f"external: {page.external!r} is not a web address",
                            "write the full address, e.g. external: https://medium.com/…", "external"))
    if page.external and page.body.strip():
        issues.append(Issue("warning", page.line_of("external") or 1, "an external entry has text below its header",
                            "external entries open elsewhere and have no page here; the text is not shown",
                            "external-body"))
    if page.series is not None and page.series.get("part", 0) < 1:
        issues.append(Issue("error", page.line_of("series"), "the series part must be 1 or more",
                            'write series: {name: "…", part: 1}', "series"))
    if page.updated and page.date and page.updated < page.date:
        issues.append(Issue("warning", page.line_of("updated"), "updated is earlier than date",
                            "updated is the date of a real revision after publishing", "updated"))
    if page.cover and site.cfg is not None and not (site.cfg.root / page.cover.lstrip("/")).exists():
        issues.append(Issue("warning", page.line_of("cover"), f"the cover image {page.cover} does not exist",
                            "put the file under static/ and give its path, e.g. static/uploads/cover.png", "cover"))
    return issues


def _check_topics(page, site, level) -> list[Issue]:
    issues = []
    line = page.line_of("topics")
    if not page.topics:
        issues.append(Issue(level, line or 1, "the page has no topics",
                            "add topics: [one, two] using slugs from content/topics.yml", "topics"))
    if len(page.topics) > TOPICS_MAX:
        issues.append(Issue("error", line, f"{len(page.topics)} topics; use at most {TOPICS_MAX}",
                            "keep the topics the page is really about", "topics"))
    for t in page.topics:
        if site.topics and t not in site.topics:
            hint = _did_you_mean(t, site.topics) or "add it to content/topics.yml first, or pick an existing one"
            issues.append(Issue("error", line, f"unknown topic {t!r}", hint, "topic-unknown"))
    return issues


def _check_builds_on(page, site) -> list[Issue]:
    issues = []
    line = page.line_of("builds_on")
    for ident in page.builds_on:
        if ident == page.id:
            issues.append(Issue("error", line, "a page cannot build on itself", "remove its own id", "builds-on"))
        elif ident in site.hidden:
            issues.append(Issue("error", line, f"builds_on: {ident} is not public yet ({site.hidden[ident].state})",
                                "publish it first, or remove it from builds_on", "builds-on"))
        elif ident not in site.pages:
            hint = _did_you_mean(ident, site.pages) or "ids look like post:slug"
            issues.append(Issue("error", line, f"builds_on: {ident} is not a page of this site", hint, "builds-on"))
    return issues


# --------------------------------------------------------------------------------------------------- body style
_FENCE = re.compile(r"^\s*(?:>\s*)*(`{3,}|~{3,})")
_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_IMAGE = re.compile(r"!\[([^\]]*)\]\(\s*([^)\s]+)")
_LINK = re.compile(r"(?<!!)\[([^\]]*)\]\(\s*([^)\s]+)")
_CALLOUT = re.compile(r"^\s*>\s*\[!([A-Za-z]+)\]")
_KNOWN_CALLOUTS = {"NOTE", "TIP", "WARNING", "KEY", "IMPORTANT", "CAUTION"}


def _body_lines(page):
    """Yield (file line, text, in_math) for body lines outside fenced code."""
    fence = None
    in_math = False
    for i, line in enumerate(page.body.split("\n")):
        m = _FENCE.match(line)
        if fence:
            if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence):
                fence = None
            continue
        if m:
            fence = m.group(1)
            continue
        stripped = line.lstrip(" >")
        if stripped.startswith("$$"):
            closes_same_line = stripped.count("$$") >= 2
            if in_math:
                in_math = False
                continue
            if not closes_same_line:
                in_math = True
                continue
            yield page.body_line + i, line, True
            continue
        yield page.body_line + i, line, in_math


def visible_length(tex: str) -> int:
    """Roughly how many symbols a row of LaTeX shows: commands count as one symbol, markup counts as none."""
    tex = re.sub(r"\\(?:left|right|big|Big|bigg|Bigg|operatorname\*?|mathrm|mathbf|mathbb|mathcal|boldsymbol|text|"
                 r"frac|dfrac|tfrac|sqrt|begin|end|quad|qquad|limits|displaystyle)(?![A-Za-z])", "", tex)
    tex = re.sub(r"\\[A-Za-z]+", "x", tex)
    tex = re.sub(r"\{#eq:[^}]*\}|\\.|[{}^_&\s$]", "", tex)
    return len(tex)


def check_body(page, site) -> list[Issue]:
    issues: list[Issue] = []
    last_level = 1
    known_urls = _known_urls(site)
    for line_no, line, in_math in _body_lines(page):
        if in_math:
            if visible_length(line) > DISPLAY_LINE_MAX:
                issues.append(Issue("warning", line_no, "this equation line is long and will scroll on phones",
                                    "break it into rows with \\begin{array}{l} … \\\\ … \\end{array}", "math-long"))
            continue
        h = _HEADING.match(line)
        if h:
            level = len(h.group(1))
            if level == 1:
                issues.append(Issue("warning", line_no, "a # heading inside the page repeats the title level",
                                    "the title is already the page heading; start sections with ##", "heading-h1"))
            elif level > last_level + 1 and last_level >= 1:
                issues.append(Issue("warning", line_no, f"the heading jumps from level {last_level} to {level}",
                                    f"use {'#' * (last_level + 1)} here so the outline has no gaps", "heading-skip"))
            last_level = level
        for m in _IMAGE.finditer(line):
            if not m.group(1).strip():
                issues.append(Issue("warning", line_no, "an image has no alt text",
                                    "describe the picture in the brackets: ![what it shows](…)", "image-alt"))
            issues += _check_target(m.group(2), line_no, site, known_urls, image=True)
        for m in _LINK.finditer(line):
            if not m.group(1).strip():
                issues.append(Issue("warning", line_no, "a link has no text", "write [the words to click](…)",
                                    "link-text"))
            issues += _check_target(m.group(2), line_no, site, known_urls, image=False)
        c = _CALLOUT.match(line)
        if c and c.group(1).upper() not in _KNOWN_CALLOUTS:
            issues.append(Issue("warning", line_no, f"[!{c.group(1)}] is not a callout type",
                                "use [!NOTE], [!TIP], [!WARNING] or [!KEY]", "callout"))
    return issues


def _known_urls(site) -> set:
    urls = {"/", "/explore/", "/ask/", "/topics/", "/series/", "/feed.xml", "/sitemap.xml", "/llms.txt",
            "/llms-full.txt"}
    for p in site.pages.values():
        urls.add(p.url)
    if site.cfg is not None:
        urls |= {f"/{k}/" for k in site.cfg["kinds"]}
    urls |= {f"/topics/{t}/" for t in site.topics}
    return urls


def _check_target(target: str, line_no, site, known_urls, image: bool) -> list[Issue]:
    target = target.strip("<>")
    if re.match(r"^(?:[a-z][a-z0-9+.-]*:|#|//)", target, re.I):
        return []
    path = target.split("#", 1)[0].split("?", 1)[0]
    if not path:
        return []
    root: Path | None = site.cfg.root if site.cfg is not None else None
    rel = path.lstrip("/").lstrip("./")
    if rel.startswith("static/"):
        if root is not None and not (root / rel).exists():
            return [Issue("warning" if not image else "error", line_no, f"{path} does not exist",
                          "put the file in static/ (uploads go in static/uploads/)", "file-missing")]
        return []
    if image:
        if root is not None and not (root / rel).exists():
            return [Issue("error", line_no, f"image {path} does not exist", "images live in static/, e.g. "
                          "static/uploads/picture.png", "file-missing")]
        return []
    url = "/" + rel if not path.startswith("/") else path
    if not url.endswith("/") and "." not in url.rsplit("/", 1)[-1]:
        url += "/"
    if url.startswith("/topics/") or url.startswith("/series/") or url in known_urls:
        return []
    return [Issue("warning", line_no, f"the link {target} does not match a page of this site",
                  "link pages with [[post:slug]] so the link is checked and kept up to date", "link-broken")]


# -------------------------------------------------------------------------------------------------------- public
def check_page(page, site) -> list[Issue]:
    """Every check on one page, sorted by line. Rendering problems (maths, ids, citations, figures) are included."""
    from .markdown import render

    issues = check_front_matter(page, site)
    issues += render(page, site).issues
    issues += check_body(page, site)
    return sort_issues(issues)


def sort_issues(issues: list[Issue]) -> list[Issue]:
    seen, out = set(), []
    for issue in sorted(issues, key=lambda x: (x.line or 0, x.level != "error", x.message)):
        key = (issue.line, issue.message)
        if key not in seen:
            seen.add(key)
            out.append(issue)
    return out


def site_for(page, all_pages, references, topics, cfg):
    """The SiteIndex a page is checked against: a public page may only link public pages; a draft may link any."""
    from .markdown import SiteIndex

    if page.public:
        visible = [p for p in all_pages if p.public]
        hidden = [p for p in all_pages if not p.public]
        return SiteIndex(visible, references, topics, cfg, preview=False, hidden=hidden)
    return SiteIndex(all_pages, references, topics, cfg, preview=True)
