"""Markdown to HTML, with Tessera's extensions.

Rendering happens in three steps:

1. **A line-aware pre-pass** over the page body finds everything that plain Markdown would damage or not know: fenced
   code (highlighted here with Pygments), display maths ``$$ … $$`` with ``\\tag``/``{#eq:name}`` numbers, inline maths
   ``$…$``, ``[[id]]`` page links, ``[@KEY]`` citations, ``[eq:name]`` equation references, and the ``::figure`` /
   ``::drawing`` lines. Each becomes an opaque placeholder token, and every problem is recorded with its real file
   line (``page.body_line`` + offset).
2. **Python-Markdown** renders the rest (tables, footnotes, attribute lists, smart quotes), plus small extensions in
   this file: ``==mark==``, ``~~del~~``, callouts (``> [!NOTE]``), images as ``<figure>`` with a caption, scrolling
   table wrappers, and heading ids with a hover link. It also collects the table of contents and one plain-text
   section per h2/h3 (for the Ask passages).
3. **Placeholders are replaced** by their HTML.
"""
from __future__ import annotations

import html as htmllib
import re
import xml.etree.ElementTree as etree
from dataclasses import dataclass, field

import markdown as pymd
from markdown.extensions import Extension
from markdown.inlinepatterns import SimpleTagInlineProcessor
from markdown.treeprocessors import Treeprocessor
from pygments import highlight as pyg_highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name
from pygments.util import ClassNotFound

from .checks import Issue
from .content import slugify
from .mathml import MathError, looks_like_money, split_tag_label, to_mathml


# ----------------------------------------------------------------------------------------------------- data types
@dataclass
class Rendered:
    html: str
    toc: list = field(default_factory=list)        # {"level": 2|3, "id": str, "text": str}
    mentions: list = field(default_factory=list)   # page ids linked with [[...]], in order of first use
    cites: list = field(default_factory=list)      # reference keys, body order then front-matter cites
    figures: list = field(default_factory=list)
    drawings: list = field(default_factory=list)
    issues: list = field(default_factory=list)
    sections: list = field(default_factory=list)   # {"id", "title", "text"}; the first one ("" id) is the intro
    equations: dict = field(default_factory=dict)  # label -> number text


class SiteIndex:
    """What rendering one page needs to know about the rest of the site.

    ``pages`` holds the pages that may be linked (public ones, or all of them when previewing); ``hidden`` holds the
    drafts and scheduled pages left out, so a link to one gets a precise message.
    """

    def __init__(self, pages=None, references=None, topics=None, cfg=None, preview: bool = False, hidden=None):
        self.pages: dict = _by_id(pages)
        self.references: dict = dict(references or {})
        self.topics: dict = dict(topics or {})
        self.cfg = cfg
        self.preview = preview
        self.hidden: dict = _by_id(hidden)


def _by_id(pages) -> dict:
    """Accept a list of pages or a dict id -> page."""
    if isinstance(pages, dict):
        return dict(pages)
    return {p.id: p for p in (pages or [])}


# --------------------------------------------------------------------------------------------------- the pre-pass
_FENCE_OPEN = re.compile(r"^(?P<prefix>[ \t]*(?:>[ \t]?)*)(?P<fence>`{3,}|~{3,})[ \t]*(?P<info>[^`]*)$")
_DISPLAY_OPEN = re.compile(r"^(?P<prefix>[ \t]*(?:>[ \t]?)*)\$\$(?P<rest>.*)$")
_DIRECTIVE = re.compile(r"^(?P<prefix>[ \t]*(?:>[ \t]?)*)::(?P<kind>figure|drawing|pagebreak)\b[ \t]*(?P<arg>.*)$")
PAGEBREAK = '<div class="pagebreak-slot"></div>'   # ::pagebreak; the theme turns it into a memo-style page break
_EQ_LABEL = re.compile(r"^\s*\{#(eq:[A-Za-z0-9_.:-]+)\}\s*$")
_WIKILINK = re.compile(r"\[\[([^\[\]|]+?)(?:\|([^\[\]]+))?\]\]")
_CITE = re.compile(r"\[(@[^\[\]]+)\](?!\()")
_EQREF = re.compile(r"\[(eq:[A-Za-z0-9_.:-]+)\](?![(\[])")
_CITE_ITEM = re.compile(r"^@([A-Za-z0-9_:.-]+)\s*(?:,\s*(.+))?$")

_TOKEN = "TSRPH{:05d}X"
_TOKEN_RE = re.compile(r"TSRPH\d{5}X")
_STASH_RE = re.compile("\x02[^\x03]*\x03")

_formatter = HtmlFormatter(nowrap=True)
# Shown as typed: Markdown examples full of LaTeX would be mis-coloured (underscores read as emphasis).
_UNCOLOURED = {"markdown", "md", "text", "txt", "plain", "plaintext"}


class _Renderer:
    """Renders one page; holds the per-page state (tokens, issues, numbering)."""

    def __init__(self, page, site: SiteIndex):
        self.page, self.site = page, site
        self.issues: list = []
        self.tokens: dict = {}      # token -> html
        self.plain: dict = {}       # token -> plain text (for sections, toc, slugs)
        self.blocks: set = set()
        self.mentions: list = []
        self.cites: list = []
        self.figures: list = []
        self.drawings: list = []
        self.equations: dict = {}   # label -> number text
        self.eq_count = 0
        self.eqrefs: list = []      # (token, label, line)

    # ---- helpers
    def line(self, i: int) -> int:
        return self.page.body_line + i

    def issue(self, level, i, message, hint="", code=""):
        self.issues.append(Issue(level, self.line(i) if i is not None else None, message, hint, code))

    def math_issue(self, i: int, exc: MathError, column0: int, line_width: int = 0) -> None:
        """A maths error at its place in the file: line ``i`` (+ the line inside the formula) and a 1-based column.

        ``column0`` is where the formula starts on its first line; ``line_width`` is the prefix of later lines (a
        blockquote's ``> ``)."""
        col = exc.column if exc.column is not None else 0
        col += column0 if not exc.offset else line_width
        self.issues.append(Issue("error", self.line(i + (exc.offset or 0)), f"maths: {exc.message}", exc.hint, "math",
                                 column=col + 1, length=exc.length))

    def token(self, html: str, plain: str = "", block: bool = False) -> str:
        tok = _TOKEN.format(len(self.tokens))
        self.tokens[tok], self.plain[tok] = html, plain
        if block:
            self.blocks.add(tok)
        return tok

    # ---- the pass
    def prepass(self, body: str) -> str:
        lines = body.split("\n")
        out: list[str] = []
        i = 0
        while i < len(lines):
            line = lines[i]
            m = _FENCE_OPEN.match(line)
            if m:
                i = self._fenced(lines, i, m, out)
                continue
            m = _DISPLAY_OPEN.match(line)
            if m:
                i = self._display(lines, i, m, out)
                continue
            m = _DIRECTIVE.match(line)
            if m:
                self._directive(i, m, out)
                i += 1
                continue
            out.append(self._inline(line, i))
            i += 1
        return "\n".join(out)

    def _emit_block(self, out: list, prefix: str, tok: str) -> None:
        bare = prefix.rstrip()
        out += [bare, prefix + tok, bare]

    @staticmethod
    def _strip_prefix(line: str, prefix: str) -> str:
        if line.startswith(prefix):
            return line[len(prefix):]
        return line.lstrip(" \t>") if prefix.strip(" \t") else line.lstrip()

    def _fenced(self, lines, i, m, out) -> int:
        prefix, fence, info = m.group("prefix"), m.group("fence"), m.group("info").strip()
        lang = info.split()[0].strip("{}.") if info else ""
        body, j = [], i + 1
        while j < len(lines):
            inner = self._strip_prefix(lines[j], prefix)
            if inner.strip().startswith(fence[0] * len(fence)) and not inner.strip().strip(fence[0]):
                break
            body.append(inner)
            j += 1
        if j >= len(lines):
            self.issue("warning", i, "this code block is never closed", f"add a line with {fence} after the code",
                       "code-unclosed")
        if lang.lower() == "diagram":
            html, plain = self._diagram("\n".join(body), info.split()[1:], i)
            self._emit_block(out, prefix, self.token(html, plain, True))
            return j + 1
        self._emit_block(out, prefix, self.token(self._code_html("\n".join(body), lang, i), "\n".join(body), True))
        return j + 1

    def _diagram(self, src: str, words: list, i: int) -> tuple:
        """A ```diagram block (```diagram timeline / tree picks the kind): drawn here, at build time."""
        try:
            from . import diagram_text
        except ImportError:
            self.issue("warning", i, "this diagram is not shown: the diagram engine is not installed",
                       "this build has no tessera/diagram_text.py", "diagram-engine")
            return _embed_error("Diagram", "diagram", "The diagram engine is not available in this build."), ""
        try:
            html = diagram_text.render_html(src, kind=words[0] if words else None)
            return html, diagram_text.summary(diagram_text.parse(src, words[0] if words else None))
        except diagram_text.DiagramError as exc:
            line = i + exc.line if exc.line else i
            self.issue("error", line, f"diagram: {exc.message}", exc.hint, "diagram")
            where = f" Line {exc.line} of the diagram: " if exc.line else " "
            return (f'<div class="embed-error" role="note"><strong>This diagram could not be drawn.</strong>'
                    f"{htmllib.escape(where + exc.message)}{htmllib.escape(' (' + exc.hint + ')') if exc.hint else ''}"
                    f"</div>"), ""

    def _code_html(self, code: str, lang: str, i: int) -> str:
        lexer = None
        if lang and lang.lower() not in _UNCOLOURED:
            try:
                lexer = get_lexer_by_name(lang)
            except ClassNotFound:
                self.issue("warning", i, f"code language {lang!r} is not known, so it is not coloured",
                           "check the spelling (python, js, bash, json, yaml, latex …)", "code-lang")
        inner = pyg_highlight(code, lexer, _formatter) if lexer else htmllib.escape(code) + "\n"
        label = htmllib.escape(lang)
        return (f'<div class="code-block" data-lang="{label}"><pre class="highlight"><code>'
                f"{inner.rstrip(chr(10))}</code></pre></div>")

    def _display(self, lines, i, m, out) -> int:
        prefix, rest = m.group("prefix"), m.group("rest")
        if "$$" in rest:                                    # $$ x $$ {#eq:a} on one line
            tex, after = rest.split("$$", 1)
            j = i
        else:
            parts, j = [rest], i + 1
            while j < len(lines):
                inner = self._strip_prefix(lines[j], prefix)
                if "$$" in inner:
                    head, after = inner.split("$$", 1)
                    parts.append(head)
                    break
                parts.append(inner)
                j += 1
            else:
                self.issue("error", i, "display maths opened with $$ is never closed",
                           "add $$ on its own line after the formula", "math-unclosed")
                out.append(lines[i].replace("$$", "&#36;&#36;", 1))
                return i + 1
            tex = "\n".join(parts)
        label = None
        after = after.strip()
        if after:
            lm = _EQ_LABEL.match(after)
            if lm:
                label = lm.group(1)
            else:
                self.issue("warning", j, f"text after the closing $$ is ignored: {after!r}",
                           "only {#eq:name} may follow $$; put other text on the next line", "math-trailing")
        html = self._display_html(tex, label, i, len(prefix) + 2, len(prefix))
        self._emit_block(out, prefix, self.token(html, f"$$ {tex.strip()} $$", True))
        return j + 1

    def _display_html(self, tex: str, label: str | None, i: int, column0: int = 2, line_width: int = 0) -> str:
        tex, tag, inner_label = split_tag_label(tex)
        label = label or inner_label
        if label and not label.startswith("eq:"):
            label = "eq:" + label
        number = None
        if tag is not None:
            number = tag
        elif label:
            self.eq_count += 1
            number = str(self.eq_count)
        if label:
            if label in self.equations:
                self.issue("error", i, f"the equation name {label} is used twice", "give each equation its own name",
                           "eq-duplicate")
            self.equations[label] = number
        try:
            math = to_mathml(tex, display=True)
        except MathError as exc:
            self.math_issue(i, exc, column0, line_width)
            math = self._math_error_html(tex, exc, display=True)
        ident = f' id="{htmllib.escape(label)}"' if label else ""
        num = f'<span class="eq-number">({htmllib.escape(number)})</span>' if number else ""
        cls = "math-display numbered" if number else "math-display"
        return f'<div class="{cls}"{ident}>{math}{num}</div>'

    @staticmethod
    def _math_error_html(tex: str, exc: MathError, display: bool) -> str:
        tag = "div" if display else "span"
        return (f'<{tag} class="math-error" role="note" title="{htmllib.escape(exc.hint)}">'
                f"<code>{htmllib.escape(tex.strip())}</code> <small>{htmllib.escape(exc.message)}</small></{tag}>")

    def _directive(self, i, m, out) -> None:
        kind, arg = m.group("kind"), m.group("arg").strip()
        if kind == "pagebreak":
            self._emit_block(out, m.group("prefix"), self.token(PAGEBREAK, "", True))
            return
        name, _, opts = (p.strip() for p in arg.partition("|"))
        if not name:
            self.issue("error", i, f"::{kind} needs a name", f"write ::{kind} name", f"{kind}-name")
            return
        html = self._figure(name, opts, i) if kind == "figure" else self._drawing(name, opts, i)
        self._emit_block(out, m.group("prefix"), self.token(html, "", True))

    def _figure(self, name: str, opts: str, i: int) -> str:
        start = None
        if opts:
            om = re.match(r"^start\s*:\s*(.+)$", opts)
            if om:
                start = om.group(1).strip()
            else:
                self.issue("warning", i, f"unknown figure option {opts!r}", "the only option is | start: Preset label",
                           "figure-option")
        if name not in self.figures:
            self.figures.append(name)
        try:
            from . import figures as figmod
        except ImportError:
            self.issue("warning", i, f"figure {name!r} is not shown: the figure engine is not installed",
                       "this build has no tessera/figures.py", "figure-engine")
            return _embed_error("Figure", name, "The figure engine is not available in this build.")
        try:
            return figmod.figure_html(name, start=start, cfg=self.site.cfg)
        except figmod.FigureError as exc:
            self.issue("error", i, f"figure {name!r}: {exc}", "fix the figure file, or run: python -m tessera "
                       f"figure test {name}", "figure")
            return _embed_error("Figure", name, str(exc))

    def _drawing(self, ref: str, caption: str, i: int) -> str:
        if ref not in self.drawings:
            self.drawings.append(ref)
        try:
            from . import drawings as drawmod
        except ImportError:
            self.issue("warning", i, f"drawing {ref!r} is not shown: the drawing engine is not installed",
                       "this build has no tessera/drawings.py", "drawing-engine")
            return _embed_error("Drawing", ref, "The drawing engine is not available in this build.")
        try:
            return drawmod.drawing_html(ref, caption, cfg=self.site.cfg)
        except drawmod.DrawingError as exc:
            self.issue("error", i, f"drawing {ref!r}: {exc}", "fix the function in drawings/", "drawing")
            return _embed_error("Drawing", ref, str(exc))

    # ---- inline constructs on one line
    def _inline(self, line: str, i: int) -> str:
        out, pos, n = [], 0, len(line)
        while pos < n:
            ch = line[pos]
            if ch == "`":                                   # code span: copy verbatim up to the matching run
                run = len(line[pos:]) - len(line[pos:].lstrip("`"))
                end = line.find("`" * run, pos + run)
                if end == -1:
                    out.append(line[pos:pos + run])
                    pos += run
                    continue
                out.append(line[pos:end + run])
                pos = end + run
                continue
            if ch == "\\" and pos + 1 < n and line[pos + 1] == "$":
                out.append("&#36;")
                pos += 2
                continue
            if ch == "$":
                consumed = self._inline_math(line, pos, i, out)
                if consumed:
                    pos = consumed
                    continue
            if ch == "[":
                consumed = self._bracket(line, pos, i, out)
                if consumed:
                    pos = consumed
                    continue
            out.append(ch)
            pos += 1
        return "".join(out)

    def _inline_math(self, line: str, pos: int, i: int, out: list) -> int:
        dollars = 2 if line.startswith("$$", pos) else 1
        start = pos + dollars
        if start >= len(line) or line[start].isspace():
            return 0
        j = start
        while True:
            j = line.find("$" * dollars, j)
            if j == -1:
                return 0
            if line[j - 1] == "\\":
                j += 1
                continue
            if dollars == 1 and (line[j - 1].isspace() or (j + 1 < len(line) and line[j + 1].isdigit())):
                j += 1
                continue
            break
        tex = line[start:j]
        if dollars == 1 and (looks_like_money(tex) or (re.match(r"\s*\d", tex) and re.search(r"(?<!\\)\$", tex))):
            # "it costs $5 and you get $x$": a dollar amount, not the start of maths
            self.issues.append(Issue("warning", self.line(i), "this $ looks like money, so it is shown as a dollar sign, "
                                     "not as the start of maths", "write \\$5 for a dollar amount next to maths", "math-money",
                                     column=pos + 1, length=1))
            out.append("&#36;")
            return pos + 1
        if dollars == 2:
            self.issue("warning", i, "display maths ($$) in the middle of a line is shown inline",
                       "put $$ … $$ on its own lines for a displayed equation", "math-inline-display")
        try:
            html = to_mathml(tex, display=False)
        except MathError as exc:
            self.math_issue(i, exc, start)
            html = self._math_error_html(tex, exc, display=False)
        out.append(self.token(html, tex))
        return j + dollars

    def _bracket(self, line: str, pos: int, i: int, out: list) -> int:
        rest = line[pos:]
        m = _WIKILINK.match(rest)
        if m:
            out.append(self._wikilink(m.group(1).strip(), (m.group(2) or "").strip(), i))
            return pos + m.end()
        m = _CITE.match(rest)
        if m:
            out.append(self._citation(m.group(1), i))
            return pos + m.end()
        m = _EQREF.match(rest)
        if m:
            tok = self.token("", "")
            self.eqrefs.append((tok, m.group(1), i))
            out.append(tok)
            return pos + m.end()
        return 0

    def _wikilink(self, ident: str, text: str, i: int) -> str:
        target = self.site.pages.get(ident)
        if target is None:
            hidden = self.site.hidden.get(ident)
            if hidden is not None:
                self.issue("error", i, f"[[{ident}]] links to a page that is not public yet ({hidden.state})",
                           "publish that page first, or remove the link for now", "link-hidden")
            else:
                self.issue("error", i, f"[[{ident}]] is not a page of this site", _did_you_mean(ident, self.site.pages)
                           or "page ids look like post:slug (the file name without .md)", "link-unknown")
            label = htmllib.escape(text or ident)
            return self.token(f'<span class="xref xref-missing">{label}</span>', text or ident)
        if ident not in self.mentions:
            self.mentions.append(ident)
        label = text or target.title or ident
        return self.token(f'<a class="xref" href="{target.url}" data-id="{htmllib.escape(ident)}">'
                          f"{htmllib.escape(label)}</a>", label)

    def _citation(self, inner: str, i: int) -> str:
        parts = []
        for item in (s.strip() for s in inner.split(";")):
            m = _CITE_ITEM.match(item)
            if not m:
                self.issue("error", i, f"citation [{inner}] is not written as [@KEY] or [@KEY, p. 4]",
                           "keys come from content/references.yml", "cite-syntax")
                return self.token(htmllib.escape(f"[{inner}]"), inner)
            key, locator = m.group(1), (m.group(2) or "").strip()
            if key not in self.site.references:
                self.issue("error", i, f"[@{key}] is not in content/references.yml",
                           _did_you_mean(key, self.site.references) or "add it with: python -m tessera cite <arxiv id "
                           "or DOI>", "cite-unknown")
                parts.append("?")
                continue
            if key not in self.cites:
                self.cites.append(key)
            n = self.cites.index(key) + 1
            title = htmllib.escape(_reference_short(self.site.references[key]))
            loc = f", {htmllib.escape(locator)}" if locator else ""
            parts.append(f'<a href="#ref-{htmllib.escape(key)}" title="{title}">{n}</a>{loc}')
        return self.token(f'<span class="cite">[{", ".join(parts)}]</span>', "")

    # ---- after Markdown
    def resolve_eqrefs(self) -> None:
        for tok, label, i in self.eqrefs:
            number = self.equations.get(label)
            if number is None:
                self.issue("error", i, f"[{label}] refers to an equation that does not exist",
                           _did_you_mean(label, self.equations) or "name an equation with {#" + label + "} after its "
                           "closing $$", "eqref-unknown")
                self.tokens[tok] = f'<span class="eqref eqref-missing">({htmllib.escape(label)}?)</span>'
            else:
                self.tokens[tok] = f'<a class="eqref" href="#{htmllib.escape(label)}">({htmllib.escape(number)})</a>'
            self.plain[tok] = f"({number or '?'})"

    def fill(self, html: str) -> str:
        for tok in self.blocks:
            html = html.replace(f"<p>{tok}</p>", self.tokens[tok])
        return _TOKEN_RE.sub(lambda m: self.tokens.get(m.group(0), m.group(0)), html)

    def to_plain(self, text: str, md=None) -> str:
        """Plain text for the TOC and passages: stashed HTML (smart quotes, entities, raw HTML) becomes its text."""
        def unstash(m: re.Match) -> str:
            if md is None:
                return " "
            idx = re.search(r"(\d+)", m.group(0))
            blocks = md.htmlStash.rawHtmlBlocks
            if not idx or int(idx.group(1)) >= len(blocks):
                return " "
            raw = str(blocks[int(idx.group(1))])
            return htmllib.unescape(re.sub(r"<[^>]+>", " ", raw))
        text = _STASH_RE.sub(unstash, text)
        return _TOKEN_RE.sub(lambda m: self.plain.get(m.group(0), ""), text)


def _embed_error(what: str, name: str, message: str) -> str:
    return (f'<div class="embed-error" role="note"><strong>{what} “{htmllib.escape(name)}” could not be shown.</strong>'
            f" {htmllib.escape(message)}</div>")


def _did_you_mean(word: str, options) -> str:
    import difflib
    close = difflib.get_close_matches(word, list(options), n=1, cutoff=0.6)
    return f"did you mean {close[0]}?" if close else ""


def _reference_short(ref: dict) -> str:
    authors = ref.get("authors") or []
    who = (str(authors[0]).split()[-1] + (" et al." if len(authors) > 2 else (" and " + str(authors[1]).split()[-1]
                                                                              if len(authors) == 2 else ""))) \
        if authors else ""
    return f"{who} ({ref.get('year', '')}). {ref.get('title', '')}".strip()


# ----------------------------------------------------------------------------------------- Markdown extensions
CALLOUTS = {"NOTE": ("note", "Note"), "TIP": ("tip", "Tip"), "WARNING": ("warning", "Warning"),
            "KEY": ("key", "Key idea"), "IMPORTANT": ("key", "Important"), "CAUTION": ("warning", "Caution")}
_CALLOUT_RE = re.compile(r"^\s*\[!([A-Za-z]+)\][ \t]*([^\n]*)\n?")


class _Callouts(Treeprocessor):
    """``> [!NOTE] Optional title`` blockquotes become ``<div class="callout callout-note">``."""

    @staticmethod
    def _split(root) -> None:
        """``> [!TIP] …`` then a blank line then ``> [!KEY] …`` is one blockquote to Markdown; split it in two."""
        changed = True
        while changed:
            changed = False
            for parent in list(root.iter()):
                for idx, bq in enumerate(list(parent)):
                    if bq.tag != "blockquote":
                        continue
                    for k, child in enumerate(list(bq)):
                        if k and child.tag == "p" and child.text and _CALLOUT_RE.match(child.text):
                            new = etree.Element("blockquote")
                            for moved in list(bq)[k:]:
                                bq.remove(moved)
                                new.append(moved)
                            new.tail = bq.tail
                            parent.insert(idx + 1, new)
                            changed = True
                            break
                    if changed:
                        break
                if changed:
                    break

    def run(self, root):
        self._split(root)
        for bq in list(root.iter("blockquote")):
            first = bq[0] if len(bq) else None
            if first is None or first.tag != "p" or not first.text:
                continue
            m = _CALLOUT_RE.match(first.text)
            if not m or m.group(1).upper() not in CALLOUTS:
                continue
            kind, default = CALLOUTS[m.group(1).upper()]
            title = m.group(2).strip() or default
            first.text = first.text[m.end():]
            if not first.text.strip() and len(first) == 0:
                bq.remove(first)
            bq.tag = "div"
            bq.set("class", f"callout callout-{kind}")
            bq.set("role", "note")
            head = etree.Element("p", {"class": "callout-title"})
            head.text = title
            bq.insert(0, head)


class _Figures(Treeprocessor):
    """Images alone in a paragraph become ``<figure>`` with the title as caption; tables get a scrolling wrapper."""

    def run(self, root):
        for parent in list(root.iter()):
            for idx, child in enumerate(list(parent)):
                if child.tag == "table":
                    wrap = etree.Element("div", {"class": "table-wrap"})
                    parent.remove(child)
                    wrap.append(child)
                    parent.insert(idx, wrap)
                    continue
                if child.tag != "p" or len(child) != 1 or child[0].tag != "img":
                    continue
                if (child.text or "").strip() or (child[0].tail or "").strip():
                    continue
                img = child[0]
                caption = img.attrib.pop("title", "")
                child.tag, child.text = "figure", None
                child.set("class", "image")
                img.tail = None
                if caption:
                    cap = etree.SubElement(child, "figcaption")
                    cap.text = caption
        for img in root.iter("img"):
            src = img.get("src", "")
            if src and not re.match(r"^(?:[a-z]+:|/|#|data:)", src):
                img.set("src", "/" + src.lstrip("./"))
            img.set("loading", "lazy")
            img.set("decoding", "async")


class _Headings(Treeprocessor):
    """Give every heading a stable id and a hover link; collect the TOC and the plain-text sections."""

    def __init__(self, md, renderer: _Renderer):
        super().__init__(md)
        self.r = renderer

    def run(self, root):
        used: set = {"references", "connections", "top", "footnotes"}
        toc, sections = [], [{"id": "", "title": "", "text": []}]
        for el in list(root):
            if el.tag in ("h2", "h3", "h4", "h5", "h6"):
                text = " ".join(self.r.to_plain("".join(el.itertext()), self.md).split())
                ident = el.get("id") or slugify(text)
                base, n = ident, 2
                while ident in used:
                    ident, n = f"{base}-{n}", n + 1
                used.add(ident)
                el.set("id", ident)
                link = etree.SubElement(el, "a", {"class": "heading-anchor", "href": f"#{ident}",
                                                  "aria-label": f"Link to “{text}”"})
                link.text = "#"
                if el.tag in ("h2", "h3"):
                    toc.append({"level": int(el.tag[1]), "id": ident, "text": text})
                    sections.append({"id": ident, "title": text, "text": []})
                    continue
            if el.tag == "div" and "footnote" in (el.get("class") or ""):
                continue
            sections[-1]["text"].append(self.r.to_plain("".join(el.itertext()), self.md))
        self.r.toc = toc
        self.r.sections = [{"id": s["id"], "title": s["title"], "text": " ".join(" ".join(s["text"]).split())}
                           for s in sections if s["id"] or " ".join(s["text"]).strip()]


class _TesseraExtension(Extension):
    def __init__(self, renderer: _Renderer):
        super().__init__()
        self.r = renderer

    def extendMarkdown(self, md):
        md.inlinePatterns.register(SimpleTagInlineProcessor(r"()==(?!\s)(.+?)(?<!\s)==", "mark"), "mark", 65)
        md.inlinePatterns.register(SimpleTagInlineProcessor(r"()~~(?!\s)(.+?)(?<!\s)~~", "del"), "del", 66)
        md.treeprocessors.register(_Callouts(md), "tessera-callouts", 5)
        md.treeprocessors.register(_Figures(md), "tessera-figures", 4)
        md.treeprocessors.register(_Headings(md, self.r), "tessera-headings", 3)


def _markdown(renderer: _Renderer) -> pymd.Markdown:
    return pymd.Markdown(
        extensions=["extra", "sane_lists", "smarty", _TesseraExtension(renderer)],
        extension_configs={"footnotes": {"BACKLINK_TITLE": "Back to the text"}},
        output_format="html",
    )


# --------------------------------------------------------------------------------------------------------- public
def render(page, site: SiteIndex) -> Rendered:
    """Render a page's body. Problems never raise: they are returned in ``issues`` with file line numbers."""
    r = _Renderer(page, site)
    r.toc, r.sections = [], []
    source = r.prepass(page.body)
    r.resolve_eqrefs()
    body_html = _markdown(r).convert(source)
    html_out = r.fill(body_html)
    cites = list(r.cites)
    for key in page.cites:
        if key not in cites:
            if key in site.references:
                cites.append(key)
            else:
                r.issues.append(Issue("error", page.line_of("cites"), f"cites: {key} is not in content/references.yml",
                                      _did_you_mean(key, site.references) or "add it with: python -m tessera cite "
                                      "<arxiv id or DOI>", "cite-unknown"))
    return Rendered(html=html_out, toc=r.toc, mentions=r.mentions, cites=cites, figures=r.figures,
                    drawings=r.drawings, issues=r.issues, sections=r.sections, equations=dict(r.equations))


def references(rendered: Rendered, site: SiteIndex) -> list[dict]:
    """The numbered reference list for a page: ``[{key, n, text, html, url}]``."""
    out = []
    for n, key in enumerate(rendered.cites, 1):
        ref = site.references.get(key) or {}
        url = reference_url(ref)
        out.append({"key": key, "n": n, "text": format_reference(ref), "html": format_reference_html(ref),
                    "url": url})
    return out


def reference_url(ref: dict) -> str:
    if ref.get("url"):
        return str(ref["url"])
    if ref.get("arxiv"):
        return f"https://arxiv.org/abs/{ref['arxiv']}"
    if ref.get("doi"):
        return f"https://doi.org/{ref['doi']}"
    return ""


def _authors(ref: dict) -> str:
    authors = [str(a) for a in ref.get("authors") or []]
    if len(authors) > 3:
        return f"{authors[0]} et al."
    if len(authors) > 1:
        return ", ".join(authors[:-1]) + " and " + authors[-1]
    return authors[0] if authors else ""


def _venue(ref: dict) -> str:
    venue = str(ref.get("venue") or "")
    if not venue and ref.get("arxiv"):
        venue = f"arXiv:{ref['arxiv']}"
    return venue


def format_reference(ref: dict) -> str:
    """Plain text: ``Authors (Year). Title. Venue.``"""
    bits = [f"{_authors(ref)} ({ref.get('year', 'n.d.')}).", f"{ref.get('title', '')}."]
    if _venue(ref):
        bits.append(_venue(ref) + ".")
    return " ".join(b for b in bits if b.strip(". "))


def format_reference_html(ref: dict) -> str:
    """HTML: authors, year, the title (linked when there is a URL) and the venue."""
    esc = htmllib.escape
    url = reference_url(ref)
    title = esc(str(ref.get("title", "")))
    title_html = f'<a href="{esc(url)}">{title}</a>' if url else title
    venue = f' <span class="ref-venue">{esc(_venue(ref))}</span>' if _venue(ref) else ""
    return (f'<span class="ref-authors">{esc(_authors(ref))}</span> ({esc(str(ref.get("year", "n.d.")))}). '
            f'<span class="ref-title">{title_html}</span>.{venue}')


def render_inline(text: str) -> str:
    """Render a short Markdown snippet (site intro, summaries) without the page extensions' bookkeeping."""
    return pymd.markdown(text or "", extensions=["smarty"], output_format="html")


def pygments_css() -> str:
    """Code colours for light and dark mode, scoped to ``.highlight``. Dark applies with the theme toggle or OS."""
    light = HtmlFormatter(style="default").get_style_defs(".highlight")
    dark = HtmlFormatter(style="github-dark").get_style_defs(":root[data-theme=dark] .highlight")
    auto_dark = HtmlFormatter(style="github-dark").get_style_defs(":root:not([data-theme=light]) .highlight")
    strip = lambda css: "\n".join(l for l in css.splitlines()   # noqa: E731 - keep colours, drop backgrounds
                                  if not re.search(r"\.highlight\s*\{|\.hll\b|^pre\b|^td\.linenos|^span\.linenos", l)
                                  and "pre {" not in l)
    return ("/* Generated from Pygments at build time. */\n" + strip(light) + "\n" + strip(dark) +
            "\n@media (prefers-color-scheme: dark) {\n" + strip(auto_dark) + "\n}\n")
