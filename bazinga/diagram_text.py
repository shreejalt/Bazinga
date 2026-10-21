"""Diagrams written as text in a post, drawn as SVG when the site is built (no script in the reader's browser).

    ```diagram
    direction: right                       # right (the default) or down
    Input image -> Backbone -> Encoder -> Decoder -> Boxes
    Backbone -> Neck: "multi-scale"        # a label on the arrow
    group Encoder { Attention; Feed-forward }
    Decoder [accent]
    note Encoder: "6 layers"
    ```

The whole syntax (also shown in the Studio and in the guide, content/reads/drawing-diagrams.md):

Boxes and arrows (kind: flow, the default)
    A name on its own makes a box; a name used in an arrow is made for you. Names are matched without regard to
    case. Put a name in quotes when it holds : ; # & [ or an arrow ("Step 1: load").
    A -> B -> C        a chain              A <- B        an arrow from B to A
    A -- B             a line, no head      A <-> B       heads at both ends
    A -.-> B           dashed               A ==> B       thick
    A -> B: "label"    a label (on a chain it goes on the last arrow);  A ->|yes| B  labels one arrow of a chain
    A -> B & C         one arrow to each of B and C (& joins names on either side)
    A; B -> C          ; separates statements on one line;  # starts a comment
    Shapes, written around the name where it first appears:  [box]  (round)  {decision}  ((circle))  [/data/]
    Name [accent]      a style: accent, muted, data, emphasis; a shape word works too: Name [diamond]
    Name [style=accent, shape=round, label="Shown text", sub="a second line", note="beside it"]
    Name: "a second line"            the quieter second line inside the box
    note Name: "text"                a note beside the box;     note: "text"   a note under the whole diagram
    group Title { A; B -> C }        a frame around boxes (also over several lines, closed by a line with } ).
                                     Arrows to the title go to the frame; groups may hold groups.
    direction: right | down    title: "for screen readers"    caption: "shown under the diagram"

Timelines (kind: timeline)
    2017: Transformer                 a date, a colon and what happened, in order
    2020: ViT: "images as patches"    a second colon adds a detail;  [accent] after the title marks one
    direction: down                   draws it top to bottom (phones always get that version)

Trees (kind: tree)
    One box per line; indent a line under another to make it a child (spaces or tabs, any consistent depth).
    Bullets (- * +) and the lines of a pasted `tree` listing are ignored. Shapes, [styles] and ": second line" work.
    direction: down (the default, root on top) | right (root on the left)

Every problem raises DiagramError(message, line, hint) with the line inside the block and a plain hint.
Layout: a layered layout (cycle breaking, longest-path layers tightened toward their neighbours, barycentre sweeps
plus adjacent swaps against crossings, a least-squares placement under order constraints), groups laid out inside
out as boxes, then every arrow routed on an orthogonal grid around the boxes (fewest bends, no shared runs between
unrelated arrows), with labels placed on free straight pieces. The same input always gives the same SVG.
"""
from __future__ import annotations

import difflib
import heapq
import html as htmllib
import math
import re

from . import draw

__all__ = ["DiagramError", "Graph", "parse", "layout", "render", "render_html", "graph_from_spec", "EXAMPLES",
           "STYLES", "SHAPES"]

# --------------------------------------------------------------------------------------------------------------------
# sizes (SVG units; the reading column is about 720)

FS, FS_SUB, FS_LABEL, FS_NOTE = 14.0, 12.0, 12.0, 12.0
LINE = draw.LINE
PAD_X, PAD_Y = 14.0, 9.0
MIN_W, MIN_H = 64.0, 38.0
TEXT_W, TEXT_W_NARROW = 172.0, 132.0       # longest line of text in a box before it wraps
CLEAR = 10.0                               # how close an arrow may pass a box
TRACK = 8.0                                # distance between parallel arrows in one channel
GROUP_PAD, GROUP_TOP = 16.0, 26.0          # frame padding; the band at the top holds the title
MARGIN = 8.0                               # around the whole drawing
MAX_NODES = 80
WIDE_LIMIT = 940.0                         # wider than this (direction right): try narrower boxes first
NARROW_FIT = 380.0                         # a drawing at most this wide needs no phone version (on a 360 px
                                           # phone it still shows its text at 80 % or more)

STYLES = ("accent", "muted", "data", "emphasis")
SHAPES = ("box", "round", "diamond", "circle", "cylinder")
_STYLE_ALIASES = {"accent": "accent", "blue": "accent", "main": "accent", "primary": "accent",
                  "muted": "muted", "quiet": "muted", "faint": "muted", "grey": "muted", "gray": "muted",
                  "data": "data", "input": "data", "output": "data", "tensor": "data",
                  "emphasis": "emphasis", "solid": "emphasis", "strong": "emphasis", "highlight": "emphasis",
                  "bold": "emphasis", "plain": "", "none": "", "default": ""}
_SHAPE_ALIASES = {"box": "box", "rect": "box", "rectangle": "box", "square": "box",
                  "round": "round", "rounded": "round", "pill": "round", "stadium": "round", "terminal": "round",
                  "diamond": "diamond", "decision": "diamond", "rhombus": "diamond", "choice": "diamond",
                  "circle": "circle", "dot": "circle", "ellipse": "circle", "oval": "circle",
                  "cylinder": "data", "database": "data", "db": "data", "store": "data", "dataset": "data"}
_SHAPE_DRAW = {"box": "box", "round": "round", "diamond": "diamond", "circle": "circle", "data": "data"}
_KINDS = {"flow": "flow", "flowchart": "flow", "graph": "flow", "boxes": "flow", "timeline": "timeline",
          "tree": "tree", "hierarchy": "tree"}
_DIRECTIONS = {"right": "right", "lr": "right", "left-to-right": "right", "horizontal": "right", "across": "right",
               "down": "down", "td": "down", "tb": "down", "top-down": "down", "top-to-bottom": "down",
               "vertical": "down"}


class DiagramError(ValueError):
    """A diagram that cannot be drawn. .line is the line inside the block (1 = the first line after ```diagram),
    .hint says what to write instead."""

    def __init__(self, message, line=None, hint=""):
        super().__init__(message)
        self.message, self.line, self.hint = message, line, hint

    def __str__(self):
        where = ("line %d: " % self.line) if self.line else ""
        return where + self.message + ((" (%s)" % self.hint) if self.hint else "")


# --------------------------------------------------------------------------------------------------------------------
# the model

class Node:
    __slots__ = ("name", "label", "sub", "shape", "style", "line", "parent", "placed", "note", "is_group",
                 "gstyle", "children", "order")

    def __init__(self, name, line, order):
        self.name, self.label, self.sub, self.shape, self.style = name, None, "", "box", ""
        self.line, self.parent, self.placed, self.note, self.is_group = line, None, False, "", False
        self.gstyle, self.children, self.order = "", [], order


class Edge:
    __slots__ = ("a", "b", "heads", "line_style", "label", "line", "index")

    def __init__(self, a, b, heads, line_style, label, line, index):
        self.a, self.b, self.heads, self.line_style, self.label, self.line = a, b, heads, line_style, label, line
        self.index = index


class Graph:
    """What a diagram says, before layout."""

    def __init__(self):
        self.kind = "flow"
        self.direction = None
        self.title = ""
        self.caption = ""
        self.nodes = {}           # key (lower-case name) -> Node, in order of first mention
        self.edges = []
        self.notes = []           # free notes under the drawing
        self.items = []           # timeline: (date, title, detail, style, line)
        self.roots = []           # tree: [TreeNode]
        self.note_lines = {}      # key -> line of its note statement (checked at the end)

    # ---- helpers for the parser and graph_from_spec
    def node(self, name, line):
        name = "\n".join(" ".join(part.split()) for part in str(name).split("\n")).strip()
        if not name:
            raise DiagramError("a box needs a name", line, 'write a word or put the name in quotes: "Step 1"')
        key = name.lower()
        n = self.nodes.get(key)
        if n is None:
            if len(self.nodes) >= MAX_NODES:
                raise DiagramError("more than %d boxes in one diagram" % MAX_NODES, line,
                                   "split it into two diagrams, or draw the details inside a group in another one")
            n = self.nodes[key] = Node(name, line, len(self.nodes))
        return n

    def edge(self, a, b, heads, line_style, label, line):
        if a is b:
            pass
        self.edges.append(Edge(a, b, heads, line_style, label, line, len(self.edges)))

    def in_group(self, n, group, line):
        """The first mention of a box inside a group places it there."""
        if group is None or n.placed or n is group:
            return
        p = group
        while p is not None:
            if p is n:
                raise DiagramError("the group %r cannot be inside itself" % n.name, line,
                                   "a group's own title cannot appear among its members")
            p = p.parent
        n.parent, n.placed = group, True
        group.children.append(n)

    def labels(self):
        return [n.label or n.name for n in self.nodes.values()]


class TreeNode:
    __slots__ = ("label", "sub", "shape", "style", "line", "children", "depth")

    def __init__(self, label, line, depth):
        self.label, self.sub, self.shape, self.style, self.line = label, "", "box", "", line
        self.children, self.depth = [], depth


# --------------------------------------------------------------------------------------------------------------------
# reading the text

_ARROWS = sorted([
    ("<-.->", "both", "dashed"), ("<==>", "both", "thick"), ("<-->", "both", ""),
    ("-.->", "end", "dashed"), ("<-.-", "start", "dashed"), ("==>", "end", "thick"), ("<==", "start", "thick"),
    ("-->", "end", ""), ("<--", "start", ""), ("<->", "both", ""), ("-.-", "none", "dashed"),
    ("===", "none", "thick"), ("---", "none", ""), ("->", "end", ""), ("<-", "start", ""), ("--", "none", ""),
    ("→", "end", ""), ("←", "start", ""), ("↔", "both", ""),
], key=lambda a: -len(a[0]))
_QUOTES = {'"': '"', "“": "”", "”": "”"}
_DIRECTIVE = re.compile(r"^(direction|layout|kind|type|title|caption)\s*:\s*(.*)$", re.I)


def _did_you_mean(word, options):
    by_lower = {}
    for o in options:
        o = getattr(o, "name", o)
        by_lower.setdefault(str(o).lower(), str(o))
    close = difflib.get_close_matches(str(word).lower(), list(by_lower), n=1, cutoff=0.6)
    return ("did you mean %s? " % by_lower[close[0]]) if close else ""


def _strip_comment(s):
    """Drop a # comment (outside quotes; # starts a comment at the start of a line or after a space)."""
    q = None
    for i, ch in enumerate(s):
        if q:
            if ch == q or (q == '"' and ch == "”"):
                q = None
        elif ch in _QUOTES:
            q = _QUOTES[ch]
        elif ch == "#" and (i == 0 or s[i - 1] in " \t"):
            return s[:i]
    return s


def _find_outside(s, chars, start=0):
    """Index of the first of `chars` outside quotes and brackets, or -1."""
    q, depth = None, 0
    i = start
    while i < len(s):
        ch = s[i]
        if q:
            if ch == "\\" and q == '"':
                i += 2
                continue
            if ch == q:
                q = None
        elif ch in _QUOTES:
            q = _QUOTES[ch]
        elif ch in "[(" and ch not in chars:
            depth += 1
        elif ch in "])" and ch not in chars and depth:
            depth -= 1
        elif ch in chars and depth == 0:
            return i
        i += 1
    return -1


def _split_statements(s):
    out, start = [], 0
    while True:
        k = _find_outside(s, ";", start)
        if k < 0:
            out.append(s[start:])
            return [p.strip() for p in out if p.strip()]
        out.append(s[start:k])
        start = k + 1


def _read_quoted(s, i, line):
    """s[i] is an opening quote; returns (text, index after the closing quote)."""
    close = _QUOTES[s[i]]
    j, buf = i + 1, []
    while j < len(s):
        ch = s[j]
        if ch == "\\" and j + 1 < len(s) and close == '"':
            nxt = s[j + 1]
            buf.append("\n" if nxt == "n" else nxt)
            j += 2
            continue
        if ch == close or (close == "”" and ch == '"'):
            return "".join(buf), j + 1
        buf.append(ch)
        j += 1
    raise DiagramError("a quote is never closed", line, 'add " at the end of the quoted text')


def _unquote(s, line):
    s = s.strip()
    if s and s[0] in _QUOTES:
        text, end = _read_quoted(s, 0, line)
        rest = s[end:].strip()
        if rest:
            raise DiagramError("text after the closing quote: %r" % rest, line,
                               "put everything inside the quotes, or remove the extra text")
        return text
    return s


def _closing(s, i, open_, close, line, what):
    depth, j, q = 0, i, None
    while j < len(s):
        ch = s[j]
        if q:
            if ch == q:
                q = None
        elif ch in _QUOTES and open_ not in _QUOTES:
            q = _QUOTES[ch]
        elif s.startswith(open_, j):
            depth += 1
            j += len(open_)
            continue
        elif s.startswith(close, j):
            depth -= 1
            if depth == 0:
                return j
            j += len(close)
            continue
        j += 1
    raise DiagramError("%s is opened with %s but never closed" % (what, open_), line, "add %s after the name" % close)


def _lex(s, line, amp=True):
    """Tokens of one statement: ('name', text, shape|None, quoted), ('attr', dict), ('arrow', heads, style, label),
    ('amp',), ('colon', text)."""
    toks, buf = [], []
    i = 0

    def pending():
        return "".join(buf).strip()

    def flush():
        text = " ".join(pending().split())
        buf.clear()
        if text:
            toks.append(("name", text, None, False))

    def at_name_start():
        return not pending() and (not toks or toks[-1][0] in ("arrow", "amp"))

    while i < len(s):
        ch = s[i]
        arrow = next((a for a in _ARROWS if s.startswith(a[0], i)), None)
        if arrow:
            flush()
            i += len(arrow[0])
            label = ""
            k = i
            while k < len(s) and s[k] == " ":
                k += 1
            if k < len(s) and s[k] == "|":
                end = s.find("|", k + 1)
                if end < 0:
                    raise DiagramError("a label |…| on an arrow is never closed", line, "write A ->|yes| B")
                label = s[k + 1:end].strip()
                label = _unquote(label, line) if label else ""
                i = end + 1
            toks.append(("arrow", arrow[1], arrow[2], label))
            continue
        if ch in _QUOTES:
            if pending():
                raise DiagramError("a quoted name right after another name", line,
                                   "join the two with an arrow, or put the whole name in quotes")
            text, i = _read_quoted(s, i, line)
            toks.append(("name", text, None, True))
            continue
        if amp and ch == "&" and (i == 0 or s[i - 1] in " \t") and (i + 1 >= len(s) or s[i + 1] in " \t"):
            flush()
            toks.append(("amp",))
            i += 1
            continue
        if ch == ":":
            flush()
            toks.append(("colon", _unquote(s[i + 1:], line)))
            break
        if ch == "[":
            if at_name_start():
                if s.startswith("[/", i):
                    j = s.find("/]", i + 2)
                    if j < 0:
                        raise DiagramError("a data shape [/…/] is never closed", line, "write [/Dataset/]")
                    toks.append(("name", _unquote(s[i + 2:j], line), "data", True))
                    i = j + 2
                    continue
                j = _closing(s, i, "[", "]", line, "a box")
                toks.append(("name", _unquote(s[i + 1:j], line), "box", True))
                i = j + 1
                continue
            j = _closing(s, i, "[", "]", line, "a list of settings")
            flush()
            if not toks or toks[-1][0] != "name":
                raise DiagramError("[…] settings must come right after a name", line, "write Decoder [accent]")
            toks.append(("attr", _attrs(s[i + 1:j], line)))
            i = j + 1
            continue
        if ch in "({" and at_name_start():
            if s.startswith("((", i):
                j = _closing(s, i, "((", "))", line, "a circle")
                toks.append(("name", _unquote(s[i + 2:j], line), "circle", True))
                i = j + 2
            elif s.startswith("([", i):
                j = s.find("])", i)
                if j < 0:
                    raise DiagramError("a rounded box ([…]) is never closed", line, "write ([Start])")
                toks.append(("name", _unquote(s[i + 2:j], line), "round", True))
                i = j + 2
            elif ch == "(":
                j = _closing(s, i, "(", ")", line, "a rounded box")
                toks.append(("name", _unquote(s[i + 1:j], line), "round", True))
                i = j + 1
            else:
                j = _closing(s, i, "{", "}", line, "a decision")
                toks.append(("name", _unquote(s[i + 1:j], line), "diamond", True))
                i = j + 1
            continue
        if ch in "{}" and not pending():
            raise DiagramError("a stray %s" % ch, line, "groups are written: group Title { A; B }")
        buf.append(ch)
        i += 1
    flush()
    return toks


def _attrs(inner, line):
    """'accent, shape=round, label="x"' -> {'style': 'accent', 'shape': 'round', 'label': 'x'}"""
    out = {}
    parts, start = [], 0
    while True:
        k = _find_outside(inner, ", ", start)
        piece = inner[start:] if k < 0 else inner[start:k]
        if piece.strip():
            parts.append(piece.strip())
        if k < 0:
            break
        start = k + 1
    # 'shape = round' written with spaces around = splits into three pieces: join them back
    merged = []
    for p in parts:
        if merged and (p == "=" or p.startswith("=") or merged[-1].endswith("=")):
            merged[-1] = merged[-1] + p
        else:
            merged.append(p)
    for p in merged:
        if "=" in p:
            k, v = p.split("=", 1)
            k, v = k.strip().lower(), _unquote(v, line)
            if k in ("style", "color", "colour"):
                out["style"] = _style(v, line)
            elif k == "shape":
                out["shape"] = _shape(v, line)
            elif k in ("label", "text"):
                out["label"] = v
            elif k in ("sub", "detail", "second"):
                out["sub"] = v
            elif k == "note":
                out["note"] = v
            else:
                raise DiagramError("unknown setting %r" % k, line,
                                   _did_you_mean(k, ["style", "shape", "label", "sub", "note"])
                                   + "settings are style, shape, label, sub and note")
        else:
            w = _unquote(p, line).lower()
            if w == "data":                       # [data]: the colour and the cylinder
                out["style"] = "data"
                out.setdefault("shape", "data")
            elif w in _STYLE_ALIASES:
                out["style"] = _STYLE_ALIASES[w]
            elif w in _SHAPE_ALIASES:
                out["shape"] = _SHAPE_ALIASES[w]
            else:
                raise DiagramError("%r is not a style or a shape" % w, line,
                                   _did_you_mean(w, list(STYLES) + list(SHAPES))
                                   + "styles: " + ", ".join(STYLES) + "; shapes: " + ", ".join(SHAPES))
    return out


def _style(v, line):
    w = str(v).strip().lower()
    if w in _STYLE_ALIASES:
        return _STYLE_ALIASES[w]
    raise DiagramError("%r is not a style" % v, line, _did_you_mean(w, STYLES) + "use one of " + ", ".join(STYLES))


def _shape(v, line):
    w = str(v).strip().lower()
    if w in _SHAPE_ALIASES:
        return _SHAPE_ALIASES[w]
    if w == "data":
        return "data"
    raise DiagramError("%r is not a shape" % v, line, _did_you_mean(w, SHAPES) + "use one of " + ", ".join(SHAPES))


def _apply(n, shape, attrs):
    if shape:
        n.shape = shape
        if shape == "data" and not n.style:
            n.style = "data"
    for k, v in (attrs or {}).items():
        if k == "style":
            n.style = v
        elif k == "shape":
            n.shape = v
        elif k == "label":
            n.label = v
        elif k == "sub":
            n.sub = v
        elif k == "note":
            n.note = v


def parse(src, kind=None):
    """Read a diagram block (the text between ```diagram and ```). `kind` comes from the fence
    (```diagram timeline); a `kind:` line in the block wins. Raises DiagramError."""
    lines = str(src).replace("\r\n", "\n").replace("\t", "    ").split("\n")
    g = Graph()
    if kind:
        k = _KINDS.get(str(kind).strip().lower())
        if not k:
            raise DiagramError("%r is not a kind of diagram" % kind, None,
                               _did_you_mean(kind, _KINDS) + "use flow, timeline or tree")
        g.kind = k
    for n, raw in enumerate(lines, 1):
        m = _DIRECTIVE.match(_strip_comment(raw).strip())
        if m and m.group(1).lower() in ("kind", "type"):
            v = _unquote(m.group(2), n).lower()
            if v not in _KINDS:
                raise DiagramError("%r is not a kind of diagram" % v, n,
                                   _did_you_mean(v, _KINDS) + "use flow, timeline or tree")
            g.kind = _KINDS[v]
    if g.kind == "timeline":
        _parse_timeline(g, lines)
    elif g.kind == "tree":
        _parse_tree(g, lines)
    else:
        _parse_flow(g, lines)
    return g


def _directive(g, key, value, n):
    key = key.lower()
    if key in ("kind", "type"):
        return
    value = _unquote(value, n)
    if key in ("direction", "layout"):
        d = _DIRECTIONS.get(value.lower())
        if not d:
            hint = ("left and up are not offered: write right or down and turn the arrows around"
                    if value.lower() in ("left", "up", "rl", "bt") else
                    _did_you_mean(value, _DIRECTIONS) + "use right or down")
            raise DiagramError("%r is not a direction" % value, n, hint)
        g.direction = d
    elif key == "title":
        g.title = value
    elif key == "caption":
        g.caption = value


def _parse_flow(g, lines):
    stack = []                      # open groups: (Node, line)
    for n, raw in enumerate(lines, 1):
        s = _strip_comment(raw).strip()
        if not s:
            continue
        group = stack[-1][0] if stack else None
        if s.startswith("}"):
            if not stack:
                raise DiagramError("a } with no group to close", n, "groups start with: group Title {")
            stack.pop()
            if s[1:].strip():
                raise DiagramError("text after }", n, "put the next statement on its own line")
            continue
        m = _DIRECTIVE.match(s)
        if m:
            if stack and m.group(1).lower() not in ("title", "caption", "kind", "type"):
                raise DiagramError("%s: goes at the top of the diagram, not inside a group" % m.group(1), n,
                                   "move it above the group")
            _directive(g, m.group(1), m.group(2), n)
            continue
        m = re.match(r"^group\b(.*)$", s, re.I)
        if m:
            rest = m.group(1)
            has_arrow = any(a[0] in rest for a in _ARROWS)
            if _find_outside(rest, "{") >= 0:
                _group(g, rest, n, stack)
                continue
            if not has_arrow:
                raise DiagramError("a group needs { after its title", n,
                                   'write group Encoder { Attention; Feed-forward }, or quote a box whose name '
                                   'starts with "group"')
        m = re.match(r"^note\s*:(.*)$", s, re.I)
        if m:
            text = _unquote(m.group(1), n)
            if not text:
                raise DiagramError("an empty note", n, 'write note: "what to say"')
            g.notes.append(text)
            continue
        m = re.match(r"^note\s+(.+)$", s, re.I)
        if m:
            k = _find_outside(m.group(1), ":")
            head = m.group(1)[:k] if k >= 0 else m.group(1)
            if k >= 0 and not any(a[0] in head for a in _ARROWS):
                name = _unquote(head, n)
                text = _unquote(m.group(1)[k + 1:], n)
                if not text:
                    raise DiagramError("an empty note", n, 'write note %s: "what to say"' % name)
                key = " ".join(name.split()).lower()
                g.note_lines[key] = (n, name, text)
                continue
        for stmt in _split_statements(s):
            _statement(g, stmt, n, group)
    if stack:
        raise DiagramError("the group %r is never closed" % stack[-1][0].name, stack[-1][1],
                           "add a line with } after its members")
    for key, (n, name, text) in g.note_lines.items():
        node = g.nodes.get(key)
        if node is None:
            raise DiagramError("note on %r, which is not in the diagram" % name, n,
                               _did_you_mean(key, g.nodes.values()) + "a note goes beside a box that exists")
        node.note = text
    if not g.nodes:
        raise DiagramError("this diagram is empty", 1, "write two names joined by an arrow: Input -> Model")
    for e in g.edges:
        _check_edge(g, e)


def _ancestors(n):
    out = []
    p = n.parent
    while p is not None:
        out.append(p)
        p = p.parent
    return out


def _check_edge(g, e):
    if e.a.is_group and e.a in _ancestors(e.b) or e.b.is_group and e.b in _ancestors(e.a):
        grp, member = (e.a, e.b) if e.a.is_group and e.a in _ancestors(e.b) else (e.b, e.a)
        raise DiagramError("an arrow joins the group %r to %r, which is inside it" % (grp.name, member.name), e.line,
                           "draw the arrow to a box outside the group, or between two boxes inside it")


def _group(g, rest, n, stack):
    k = _find_outside(rest, "{")
    if k < 0:
        raise DiagramError("a group needs { after its title", n, "group Encoder { Attention; Feed-forward }")
    head, body = rest[:k].strip(), rest[k + 1:]
    toks = _lex(head, n) if head else []
    if not toks or toks[0][0] != "name" or any(t[0] not in ("name", "attr") for t in toks) or \
            sum(1 for t in toks if t[0] == "name") != 1:
        raise DiagramError("a group needs a title", n, "group Encoder { Attention; Feed-forward }")
    title = toks[0][1]
    node = g.node(title, n)
    if node.is_group:
        raise DiagramError("two groups are called %r" % node.name, n, "give each group its own title")
    node.is_group = True
    node.line = n
    parent = stack[-1][0] if stack else None
    g.in_group(node, parent, n)
    for t in toks[1:]:
        if "style" in t[1]:
            node.gstyle = t[1]["style"]
        if "label" in t[1]:
            node.label = t[1]["label"]
    end = _find_outside(body, "}")
    if end >= 0:
        if body[end + 1:].strip():
            raise DiagramError("text after the group's }", n, "put the next statement on its own line")
        for stmt in _split_statements(body[:end]):
            _statement(g, stmt, n, node)
    else:
        stack.append((node, n))
        for stmt in _split_statements(body):
            _statement(g, stmt, n, node)


def _statement(g, stmt, n, group):
    toks = _lex(stmt, n)
    if not toks:
        return
    parts, cur, arrows, colon = [], [], [], None
    expect = True
    for t in toks:
        kind = t[0]
        if kind == "name":
            if not expect:
                raise DiagramError("two names in a row: %r and %r" % (cur[-1][0], t[1]), n,
                                   "join them with an arrow, put each on its own line, or quote a name with "
                                   "special characters")
            cur.append([t[1], t[2], {}])
            expect = False
        elif kind == "attr":
            cur[-1][2].update(t[1])
        elif kind == "amp":
            if expect:
                raise DiagramError("& needs a name on each side", n, "write A -> B & C")
            expect = True
        elif kind == "arrow":
            if expect:
                if not parts and not cur:
                    raise DiagramError("this arrow has nothing on its left", n, "write A -> B")
                raise DiagramError("two arrows in a row, or & right before an arrow", n, "write A -> B -> C")
            parts.append(cur)
            cur = []
            arrows.append(t)
            expect = True
        elif kind == "colon":
            colon = t[1]
    if expect:
        if arrows and not cur:
            raise DiagramError("this arrow has nothing on its right", n, "write A -> B")
        if cur or parts:
            raise DiagramError("& needs a name on each side", n, "write A -> B & C")
        raise DiagramError("this line has a label but no box", n, 'write Name: "second line"')
    parts.append(cur)
    resolved = []
    for refs in parts:
        row = []
        for name, shape, attrs in refs:
            node = g.node(name, n)
            _apply(node, shape, attrs)
            g.in_group(node, group, n)
            row.append(node)
        resolved.append(row)
    if not arrows:
        if colon:
            for node in resolved[0]:
                node.sub = colon
        return
    for k, (_, heads, style, label) in enumerate(arrows):
        if k == len(arrows) - 1 and colon is not None:
            label = colon
        for a in resolved[k]:
            for b in resolved[k + 1]:
                if heads == "start":
                    g.edge(b, a, "end", style, label, n)
                else:
                    g.edge(a, b, heads, style, label, n)


def _parse_timeline(g, lines):
    for n, raw in enumerate(lines, 1):
        s = _strip_comment(raw).strip()
        if not s:
            continue
        m = _DIRECTIVE.match(s)
        if m:
            _directive(g, m.group(1), m.group(2), n)
            continue
        m = re.match(r"^note\s*:(.*)$", s, re.I)
        if m:
            g.notes.append(_unquote(m.group(1), n))
            continue
        s = re.sub(r"^[-*+]\s+", "", s)
        k = _find_outside(s, ":")
        if k < 0:
            raise DiagramError("a timeline item is a date, a colon and what happened", n, "write 2017: Transformer")
        date = _unquote(s[:k], n)
        rest = s[k + 1:].strip()
        k2 = _find_outside(rest, ":")
        title, detail = (rest[:k2], _unquote(rest[k2 + 1:], n)) if k2 >= 0 else (rest, "")
        toks = _lex(title.strip(), n, amp=False) if title.strip() else []
        if not date:
            raise DiagramError("this item has no date", n, "write 2017: Transformer")
        if not toks or toks[0][0] != "name" or any(t[0] not in ("name", "attr") for t in toks[1:]) \
                or sum(1 for t in toks if t[0] == "name") != 1:
            raise DiagramError("this item says when but not what", n, "write 2017: Transformer")
        style = ""
        for t in toks[1:]:
            style = t[1].get("style", style)
        g.items.append((date, toks[0][1], detail, style, n))
    if not g.items:
        raise DiagramError("this timeline has no items", 1, "write one item per line: 2017: Transformer")
    if len(g.items) > 40:
        raise DiagramError("more than 40 items in one timeline", g.items[40][4], "split it into two timelines")


_TREE_JUNK = re.compile(r"^[\s│├└─┬┼┴┐┌┘┤|`'\\+-]*")


def _parse_tree(g, lines):
    stack = []          # (indent, TreeNode)
    count = 0
    for n, raw in enumerate(lines, 1):
        s = _strip_comment(raw).rstrip()
        if not s.strip():
            continue
        m = _DIRECTIVE.match(s.strip())
        if m and not s[:1].isspace():
            _directive(g, m.group(1), m.group(2), n)
            continue
        junk = _TREE_JUNK.match(s).group(0)
        # a line drawn by `tree` (├── x) or a Markdown bullet (- x): the marks count as indentation
        if junk.strip() and not re.match(r"^\s*-[>-]", s):
            indent = len(junk)
            content = s[len(junk):]
        else:
            indent = len(s) - len(s.lstrip(" "))
            content = s.strip()
            bm = re.match(r"^[*+]\s+", content)
            if bm:
                content = content[bm.end():]
        content = content.strip()
        if not content:
            continue
        toks = _lex(content, n, amp=False)
        if any(t[0] == "arrow" for t in toks):
            raise DiagramError("a tree has no arrows", n, "indent a line under another to make it a child")
        names = [t for t in toks if t[0] == "name"]
        if len(names) != 1 or toks[0][0] != "name":
            raise DiagramError("one box per line in a tree", n, "put each box on its own line")
        node = TreeNode(names[0][1], n, 0)
        shape = names[0][2]
        if shape:
            node.shape = shape
            if shape == "data":
                node.style = "data"
        for t in toks:
            if t[0] == "attr":
                node.style = t[1].get("style", node.style)
                node.shape = t[1].get("shape", node.shape)
                node.label = t[1].get("label", node.label)
                node.sub = t[1].get("sub", node.sub)
            elif t[0] == "colon":
                node.sub = t[1]
        count += 1
        if count > MAX_NODES:
            raise DiagramError("more than %d boxes in one tree" % MAX_NODES, n, "split it into two trees")
        while stack and stack[-1][0] >= indent:
            last = stack.pop()
            if stack and stack[-1][0] < indent < last[0]:
                raise DiagramError("this line's indent does not match any line above it", n,
                                   "indent it like its brothers and sisters, or further to make it a child")
        if not stack:
            if g.roots and indent != g.roots[0].depth:
                raise DiagramError("this line's indent does not match any line above it", n,
                                   "a new top-level box starts at the left edge, like the first line")
            node.depth = indent
            g.roots.append(node)
        else:
            node.depth = indent
            stack[-1][1].children.append(node)
        stack.append((indent, node))
    if not g.roots:
        raise DiagramError("this tree is empty", 1, "write one box per line, indenting children under parents")


def graph_from_spec(nodes=(), edges=(), groups=None, notes=None, title=None, direction="right", caption_note=None):
    """The Graph for draw.flow(): the same model the text builds, from Python values."""
    g = Graph()
    d = _DIRECTIONS.get(str(direction or "right").lower())
    if not d:
        raise draw.DrawError("direction %r: use right or down" % (direction,))
    g.direction = d
    g.title = title or ""
    try:
        for item in nodes or ():
            if isinstance(item, dict):
                if "name" not in item:
                    raise draw.DrawError("a node dict needs a name: %r" % (item,))
                node = g.node(item["name"], None)
                _apply(node, None, {k: (_style(v, None) if k == "style" else _shape(v, None) if k == "shape" else v)
                                    for k, v in item.items() if k in ("style", "shape", "label", "sub", "note")})
            elif isinstance(item, (tuple, list)):
                node = g.node(item[0], None)
                if len(item) > 1:
                    node.sub = str(item[1])
            else:
                g.node(item, None)
        for e in edges or ():
            if isinstance(e, dict):
                a, b, label = e.get("a"), e.get("b"), e.get("label", "")
                style = e.get("line", e.get("style", ""))
                heads = e.get("heads", "end")
            else:
                if len(e) < 2:
                    raise draw.DrawError("an edge needs two ends: %r" % (e,))
                a, b, label = e[0], e[1], (e[2] if len(e) > 2 else "")
                style, heads = "", "end"
            if style not in ("", "dashed", "thick"):
                raise draw.DrawError("edge line %r: use dashed or thick" % (style,))
            if heads not in ("end", "both", "none", "start"):
                raise draw.DrawError("edge heads %r: use end, both or none" % (heads,))
            na, nb = g.node(a, None), g.node(b, None)
            if heads == "start":
                na, nb, heads = nb, na, "end"
            g.edge(na, nb, heads, style, str(label or ""), None)
        if isinstance(groups, dict):
            groups = [{"title": k, "members": v} for k, v in groups.items()]
        for grp in groups or ():
            gn = g.node(grp["title"], None)
            if gn.is_group:
                raise draw.DrawError("two groups are called %r" % gn.name)
            gn.is_group = True
            gn.gstyle = _style(grp["style"], None) if grp.get("style") else ""
            for m in grp.get("members", ()):
                g.in_group(g.node(m, None), gn, None)
        for k, v in (notes or {}).items():
            node = g.nodes.get(" ".join(str(k).split()).lower())
            if node is None:
                raise draw.DrawError("note on %r, which is not a node" % (k,))
            node.note = str(v)
        if caption_note:
            g.notes.append(caption_note)
        for e in g.edges:
            _check_edge(g, e)
    except DiagramError as exc:
        raise draw.DrawError(exc.message + ((" (%s)" % exc.hint) if exc.hint else "")) from None
    if not g.nodes:
        raise draw.DrawError("flow() needs at least one node")
    return g


def graph_from_timeline(items, direction="right", title=None, notes=None):
    """The Graph for draw.timeline(): items are (date, title[, detail[, style]]) tuples or dicts."""
    g = Graph()
    g.kind = "timeline"
    g.direction = _DIRECTIONS.get(str(direction or "right").lower())
    if not g.direction:
        raise draw.DrawError("direction %r: use right or down" % (direction,))
    g.title = title or ""
    for it in items or ():
        if isinstance(it, dict):
            date, what, detail, style = it.get("date"), it.get("title"), it.get("detail", ""), it.get("style", "")
        else:
            it = list(it) + ["", ""]
            date, what, detail, style = it[0], it[1], it[2], it[3]
        if not str(date or "").strip() or not str(what or "").strip():
            raise draw.DrawError("a timeline item needs a date and a title: %r" % (it,))
        try:
            style = _style(style, None) if style else ""
        except DiagramError as exc:
            raise draw.DrawError(str(exc)) from None
        g.items.append((str(date), str(what), str(detail or ""), style, None))
    if not g.items:
        raise draw.DrawError("timeline() needs at least one item")
    g.notes.extend(notes or [])
    return g


def graph_from_tree(root, direction="down", title=None, notes=None):
    """The Graph for draw.tree(). A node is a string (a leaf), a (label, [children]) pair, a dict
    {label: [children]} (several keys: several roots), or a dict with label, children, sub, style and shape."""
    g = Graph()
    g.kind = "tree"
    g.direction = _DIRECTIONS.get(str(direction or "down").lower())
    if not g.direction:
        raise draw.DrawError("direction %r: use right or down" % (direction,))
    g.title = title or ""
    count = [0]

    def make(x, depth):
        count[0] += 1
        if count[0] > MAX_NODES:
            raise draw.DrawError("more than %d boxes in one tree" % MAX_NODES)
        if isinstance(x, str):
            return [TreeNode(x, None, depth)]
        if isinstance(x, dict) and "label" in x:
            t = TreeNode(str(x["label"]), None, depth)
            t.sub = str(x.get("sub", ""))
            try:
                t.style = _style(x["style"], None) if x.get("style") else ""
                t.shape = _shape(x["shape"], None) if x.get("shape") else "box"
            except DiagramError as exc:
                raise draw.DrawError(str(exc)) from None
            for c in x.get("children", ()):
                t.children.extend(make(c, depth + 1))
            return [t]
        if isinstance(x, dict):
            out = []
            for k, v in x.items():
                t = TreeNode(str(k), None, depth)
                for c in (v or ()):
                    t.children.extend(make(c, depth + 1))
                out.append(t)
            return out
        if isinstance(x, (tuple, list)) and len(x) == 2 and isinstance(x[0], str) and isinstance(x[1], (list, tuple)):
            t = TreeNode(x[0], None, depth)
            for c in x[1]:
                t.children.extend(make(c, depth + 1))
            return [t]
        raise draw.DrawError("a tree node is a string, (label, [children]) or a dict; got %r" % (x,))

    g.roots = make(root, 0)
    g.notes.extend(notes or [])
    return g


# --------------------------------------------------------------------------------------------------------------------
# measuring

_BOXLIKE = ("box", "round", "data")


def _measure(label, sub, shape, maxw):
    """(w, h, lines, sub_lines) of a shape holding the text; the text wraps at maxw."""
    room = {"diamond": maxw * 0.62, "circle": maxw * 0.6}.get(shape, maxw)
    lines = draw.mono_wrap(label, room, FS) if label else []
    sub_lines = draw.mono_wrap(sub, room, FS_SUB) if sub else []
    tw = max([draw.mono_width(t, FS) for t in lines] + [draw.mono_width(t, FS_SUB) for t in sub_lines] + [0])
    th = len(lines) * FS * LINE + len(sub_lines) * FS_SUB * LINE
    if shape == "diamond":
        # the text's box (p, q half sizes) fits inside when p/a + q/b <= 1 (a, b: the diamond's half sizes)
        p, q = tw / 2 + 4, th / 2
        b = max(q + 19, 29.0)
        a = p / (1 - q / b)
        w, h = max(92.0, 2 * a), 2 * b
    elif shape == "circle":
        d = max(48.0, tw / 0.72 + 4, th + 24)
        w = h = d
    elif shape == "round":
        w, h = max(MIN_W, tw + 36), max(MIN_H, th + 2 * PAD_Y)
    elif shape == "data":
        w, h = max(MIN_W, tw + 2 * PAD_X), max(MIN_H + 8, th + 2 * PAD_Y + 12)
    else:
        w, h = max(MIN_W, tw + 2 * PAD_X), max(MIN_H, th + 2 * PAD_Y)
    return math.ceil(w), math.ceil(h), lines, sub_lines


def _title_w(t):
    return len(t) * (0.6 * 11 + 0.99)


def _wrap_title(title, width):
    def wrap(wd):
        lines, cur = [], ""
        for word in title.split():
            trial = (cur + " " + word).strip()
            if cur and _title_w(trial) > wd:
                lines.append(cur)
                cur = word
            else:
                cur = trial
        lines.append(cur)
        return lines
    lines = wrap(width)
    if len(lines) > 1:                       # balance the lines: the narrowest width that needs no more of them
        wd = _title_w(title) / len(lines)
        while wd < width:
            trial = wrap(wd)
            if len(trial) == len(lines):
                return trial
            wd += 7.6
    return lines


def _pav(target, mass):
    """Isotonic (non-decreasing) least squares: the y closest to target with y[0] <= y[1] <= ..."""
    blocks = []                                     # [value, weight, count]
    for t, m in zip(target, mass):
        blocks.append([t, m, 1])
        while len(blocks) > 1 and blocks[-2][0] > blocks[-1][0] + 1e-9:
            v2, w2, c2 = blocks.pop()
            v1, w1, c1 = blocks.pop()
            w = w1 + w2
            blocks.append([(v1 * w1 + v2 * w2) / w, w, c1 + c2])
    out = []
    for v, _, c in blocks:
        out.extend([v] * c)
    return out


# --------------------------------------------------------------------------------------------------------------------
# boxes and arrows: the layered layout

class _Item:
    __slots__ = ("key", "node", "dummy", "w", "h", "a", "b", "flow", "layer", "up", "down", "edge")

    def __init__(self, key, node=None, dummy=False):
        self.key, self.node, self.dummy = key, node, dummy
        self.w = self.h = self.a = self.b = self.flow = 0.0
        self.layer = 0
        self.up, self.down = [], []          # (item, weight) in the layer before / after
        self.edge = None


class _Flow:
    def __init__(self, g, direction, narrow, text_w=None):
        self.g, self.dir, self.narrow = g, direction, narrow
        self.right = direction == "right"
        self.maxw = text_w or (TEXT_W_NARROW if narrow else TEXT_W)
        self.size, self.text, self.rel, self.abs = {}, {}, {}, {}
        self.note_geo = {}            # node -> (dx, dy, w, h, lines): relative to the box's top-left corner
        self.content_off = {}         # group -> (dx, dy) of its content inside the frame
        self.loops = {e.a for e in g.edges if e.a is e.b}
        self.titles = {}              # group -> (title lines, width)
        self.labelled_gaps = {}

    # ---- sizes
    def _measure_node(self, n):
        w, h, lines, sub = _measure(n.label or n.name, n.sub, n.shape, self.maxw)
        self.size[n] = [w, h]
        self.text[n] = (lines, sub)

    def _note(self, n):
        if not n.note:
            return None
        w = self.size[n][0]
        room = max(w, 120.0) if self.right else min(max(w, 120.0), 170.0)
        lines = draw.mono_wrap(n.note, room, FS_NOTE)
        nw = max(draw.mono_width(t, FS_NOTE) for t in lines)
        nh = len(lines) * FS_NOTE * LINE
        if self.right:
            return ((w - nw) / 2, self.size[n][1] + 7, nw, nh, lines)
        return (w + 9, (self.size[n][1] - nh) / 2, nw, nh, lines)

    # ---- one container (the whole drawing, or the inside of a group)
    def kids(self, cont):
        if cont is None:
            return [n for n in self.g.nodes.values() if n.parent is None]
        return list(cont.children)

    @staticmethod
    def child_of(cont, n):
        p = n
        while p is not None:
            if p.parent is cont:
                return p
            p = p.parent
        return None

    def layout_container(self, cont):
        kids = self.kids(cont)
        for k in kids:
            if k.is_group:
                self.layout_container(k)
            else:
                self._measure_node(k)
        cedges = []
        for e in self.g.edges:
            if e.a is e.b:
                continue
            a, b = self.child_of(cont, e.a), self.child_of(cont, e.b)
            if a is None or b is None or a is b:
                continue
            cedges.append((a, b, e))
        W, H = self._layered(kids, cedges)
        if cont is None:
            self.total = (W, H)
            return
        title = (cont.label or cont.name).upper()
        if self.right:
            lines = [title]
        else:
            # arrows come in from the top: keep the title left of the middle, where the first box is entered
            lines = _wrap_title(title, max(100.0, W / 2 - 22))
        tw = max(_title_w(t) for t in lines)
        top = GROUP_TOP + (len(lines) - 1) * 13
        fw = max(W + 2 * GROUP_PAD, tw + 26)
        if not self.right:
            fw = max(fw, 2 * (tw + 26))
        self.titles[cont] = (lines, tw)
        self.size[cont] = [math.ceil(fw), math.ceil(H + top + GROUP_PAD)]
        self.content_off[cont] = ((fw - W) / 2, top)

    def _layered(self, kids, cedges):
        n = len(kids)
        if n == 0:
            return 0.0, 0.0
        idx = {k: i for i, k in enumerate(kids)}
        # 1. break cycles: depth first in the order things were written; an edge back to an open node turns round
        out_adj = [[] for _ in range(n)]
        for a, b, e in cedges:
            out_adj[idx[a]].append((idx[b], e.index))
        state, rev = [0] * n, set()
        for s in range(n):
            if state[s]:
                continue
            state[s] = 1
            stack = [(s, iter(out_adj[s]))]
            while stack:
                v, it = stack[-1]
                nxt = next(it, None)
                if nxt is None:
                    state[v] = 2
                    stack.pop()
                    continue
                w, ei = nxt
                if state[w] == 1:
                    rev.add(ei)
                elif state[w] == 0:
                    state[w] = 1
                    stack.append((w, iter(out_adj[w])))
        # an arrow that turns back is left out of the placement: it is routed around the boxes afterwards
        dag = []
        for a, b, e in cedges:
            u, v = idx[a], idx[b]
            if e.index not in rev:
                dag.append((u, v, e))
        preds = [[] for _ in range(n)]
        succs = [[] for _ in range(n)]
        for u, v, e in dag:
            preds[v].append(u)
            succs[u].append(v)
        # 2. layers: longest path, then each box moves toward its neighbours where that shortens arrows
        indeg = [len(p) for p in preds]
        ready = [i for i in range(n) if indeg[i] == 0]
        heapq.heapify(ready)
        layer = [0] * n
        while ready:
            u = heapq.heappop(ready)
            for v in succs[u]:
                layer[v] = max(layer[v], layer[u] + 1)
                indeg[v] -= 1
                if indeg[v] == 0:
                    heapq.heappush(ready, v)
        for _ in range(2 * n + 2):
            changed = False
            for v in range(n):
                P = [layer[u] for u in preds[v]]
                S = [layer[w] for w in succs[v]]
                if not P and not S:
                    continue
                lo = max(P) + 1 if P else None
                hi = min(S) - 1 if S else None
                if P and S:
                    new = lo if len(P) > len(S) else hi if len(P) < len(S) else min(max(layer[v], lo), hi)
                elif S:
                    new = hi
                else:
                    new = lo
                if new != layer[v]:
                    layer[v] = new
                    changed = True
            if not changed:
                break
        ranks = sorted(set(layer))
        rank = {r: i for i, r in enumerate(ranks)}
        layer = [rank[x] for x in layer]
        L = len(ranks)
        # 3. items, with a stand-in on every layer a long arrow crosses
        items = []
        for i, k in enumerate(kids):
            it = _Item(("n", i), k)
            it.layer = layer[i]
            items.append(it)
        segs = []                                             # (from item, to item, edge, first?)
        for u, v, e in dag:
            prev = items[u]
            first = True
            for l in range(layer[u] + 1, layer[v]):
                d = _Item(("d", e.index, l), None, True)
                d.layer, d.edge = l, e
                items.append(d)
                segs.append((prev, d, e, first))
                prev, first = d, False
            segs.append((prev, items[v], e, first))
        seen_from = {}
        for a, b, e, _first in segs:
            w = 10.0 if a.dummy and b.dummy else 6.0 if (a.dummy or b.dummy) else 1.0
            if not a.dummy and a.node.shape == "diamond" and not a.node.is_group:
                # a decision lines up with its first answer (straight down or across); the others leave by a side
                k = seen_from.get(a, 0)
                seen_from[a] = k + 1
                w *= 4.0 if k == 0 else 0.05
            a.down.append((b, w))
            b.up.append((a, w))
        # sizes, made even along each layer (a column of boxes shares a width, a row shares a height)
        layers = [[] for _ in range(L)]
        for it in items:
            layers[it.layer].append(it)
        for row in layers:
            same = [it for it in row if not it.dummy and not it.node.is_group and it.node.shape in _BOXLIKE]
            if len(same) > 1:
                k = 0 if self.right else 1
                m = max(self.size[it.node][k] for it in same)
                for it in same:
                    self.size[it.node][k] = m
        spine = [row[0] for row in layers if len(row) == 1 and not row[0].dummy and not row[0].node.is_group
                 and row[0].node.shape in _BOXLIKE]
        if len(spine) > 1:
            k = 1 if self.right else 0
            m = max(self.size[it.node][k] for it in spine)
            if all(self.size[it.node][k] >= m * 0.6 for it in spine):
                for it in spine:
                    self.size[it.node][k] = m
        for it in items:
            if it.dummy:
                it.a = it.b = 2.0
                continue
            w, h = self.size[it.node]
            note = self._note(it.node)
            self.note_geo[it.node] = note
            loop = it.node in self.loops
            if self.right:
                it.flow = max(w, note[2] if note else 0) + (20 if loop else 0)
                it.a = h / 2 + (22 if loop else 0)
                it.b = h / 2 + (note[1] + note[3] - h if note else 0)
            else:
                it.flow = max(h, note[3] if note else 0) + (22 if loop else 0)
                it.a = w / 2
                it.b = w / 2 + (note[0] + note[2] - w if note else 0) + (22 if loop else 0)
        # 4. order within layers: barycentre sweeps, then swaps of neighbours
        for row in layers:
            row.sort(key=lambda it: (it.dummy, it.key))
        self._order(layers)
        # 5. positions across the layers: least squares under order and spacing constraints
        sep_nn = 26.0 if self.right else (22.0 if self.narrow else 30.0)

        def gap(p, q):
            s = sep_nn if not (p.dummy or q.dummy) else (TRACK + 4 if p.dummy and q.dummy else sep_nn)
            return p.b + q.a + s

        c = {}
        for row in layers:
            cur = 0.0
            for i, it in enumerate(row):
                if i:
                    cur += gap(row[i - 1], it)
                c[it] = cur
            shift = cur / 2
            for it in row:
                c[it] -= shift

        def place(row, use_up, use_down):
            desired, mass = [], []
            for it in row:
                ns = (it.up if use_up else []) + (it.down if use_down else [])
                if ns:
                    tot = sum(w for _, w in ns)
                    desired.append(sum(c[o] * w for o, w in ns) / tot)
                    mass.append(tot)
                else:
                    desired.append(c[it])
                    mass.append(0.05)
            offs, cur = [], 0.0
            for i, it in enumerate(row):
                if i:
                    cur += gap(row[i - 1], it)
                offs.append(cur)
            ys = _pav([d - o for d, o in zip(desired, offs)], mass)
            for it, y, o in zip(row, ys, offs):
                c[it] = y + o

        for _ in range(8):
            for l in range(1, L):
                place(layers[l], True, False)
            for l in range(L - 2, -1, -1):
                place(layers[l], False, True)
        for _ in range(4):
            for l in range(L):
                place(layers[l], True, True)
            for l in range(L - 1, -1, -1):
                place(layers[l], True, True)
        # snap: a box a few units off the box it hangs from moves under it, when its neighbours leave room
        for l in range(1, L):
            row = layers[l]
            for i, it in enumerate(row):
                if it.dummy or not it.up:
                    continue
                u = max(it.up, key=lambda t: t[1])[0]
                delta = c[u] - c[it]
                if not 0.01 < abs(delta) < 12:
                    continue
                # move it, pushing its neighbours along on the side it moves toward (that only widens gaps)
                c[it] += delta
                if delta > 0:
                    for k in range(i + 1, len(row)):
                        need = c[row[k - 1]] + gap(row[k - 1], row[k])
                        if c[row[k]] >= need - 1e-6:
                            break
                        c[row[k]] = need
                else:
                    for k in range(i - 1, -1, -1):
                        need = c[row[k + 1]] - gap(row[k], row[k + 1])
                        if c[row[k]] <= need + 1e-6:
                            break
                        c[row[k]] = need
        # 6. positions along the flow: each layer as deep as its deepest box; gaps wide enough for labels
        fsize = [max([it.flow for it in row if not it.dummy] + [0.0]) for row in layers]
        base = (40.0 if self.narrow else 46.0) if not self.right else 46.0
        gaps = []
        for l in range(L - 1):
            need = base
            switch = 0
            for a, b, e, first in segs:
                if a.layer != l:
                    continue
                if abs(c[a] - c[b]) > 1:
                    switch += 1
                if e.label and first:
                    lw = draw.mono_width(e.label, FS_LABEL) + 10
                    need = max(need, lw + 2 * CLEAR + 22 if self.right else 18 + 2 * CLEAR + 24)
            need = max(need, 2 * CLEAR + (switch + 1) * TRACK + 8)
            gaps.append(need)
        fpos, cur = [], 0.0
        for l in range(L):
            fpos.append(cur)
            cur += fsize[l] + (gaps[l] if l < L - 1 else 0)
        # 7. boxes, relative to the container
        boxes = {}
        lo_c = min(c[it] - it.a for it in items)
        for it in items:
            if it.dummy:
                continue
            w, h = self.size[it.node]
            fc = fpos[it.layer] + fsize[it.layer] / 2
            cc = c[it] - lo_c
            if self.right:
                x, y = fc - w / 2, cc - h / 2
            else:
                x, y = cc - w / 2, fc - h / 2
            boxes[it.node] = [x, y, w, h]
        # the extent, notes and loops included
        x0 = y0 = float("inf")
        x1 = y1 = float("-inf")
        for node, (x, y, w, h) in boxes.items():
            ex = [(x, y, x + w, y + h)]
            note = self.note_geo.get(node)
            if note:
                ex.append((x + note[0], y + note[1], x + note[0] + note[2], y + note[1] + note[3]))
            if node in self.loops:
                ex.append((x + w - 30, y - 24, x + w + 24, y + h))
            for a0, b0, a1, b1 in ex:
                x0, y0, x1, y1 = min(x0, a0), min(y0, b0), max(x1, a1), max(y1, b1)
        for node, b in boxes.items():
            self.rel[node] = (b[0] - x0, b[1] - y0, b[2], b[3])
        return x1 - x0, y1 - y0

    def _order(self, layers):
        L = len(layers)

        def pos_map():
            return {it: i for row in layers for i, it in enumerate(row)}

        def crossings(l, pos):
            es = [(pos[a], pos[b]) for a in layers[l] for b, _ in a.down]
            n = 0
            for i in range(len(es)):
                p, q = es[i]
                for j in range(i + 1, len(es)):
                    r, s = es[j]
                    if (p - r) * (q - s) < 0:
                        n += 1
            return n

        def total(pos):
            return sum(crossings(l, pos) for l in range(L - 1))

        pos = pos_map()
        best = [list(r) for r in layers]
        best_c = total(pos)
        for _ in range(12):
            if best_c == 0:
                break
            for sweep in (range(1, L), range(L - 2, -1, -1)):
                for l in sweep:
                    row = layers[l]
                    down = sweep.step == -1 if isinstance(sweep, range) else False
                    keyed = []
                    for it in row:
                        ns = it.down if down else it.up
                        bary = (sum(pos[o] for o, _ in ns) / len(ns)) if ns else pos[it]
                        keyed.append((bary, pos[it], it))
                    keyed.sort(key=lambda t: (t[0], t[1]))
                    layers[l] = [t[2] for t in keyed]
                    for i, it in enumerate(layers[l]):
                        pos[it] = i
            cc = total(pos)
            if cc < best_c:
                best_c, best = cc, [list(r) for r in layers]
        layers[:] = [list(r) for r in best]
        pos = pos_map()

        def pair_cross(x, y):
            # crossings between x's and y's edges when x stands left of y
            n = 0
            for nx, ny in ((x.up, y.up), (x.down, y.down)):
                for o, _ in nx:
                    for p, _ in ny:
                        if pos[o] > pos[p]:
                            n += 1
            return n

        for _ in range(6):
            improved = False
            for l in range(L):
                row = layers[l]
                for i in range(len(row) - 1):
                    x, y = row[i], row[i + 1]
                    if pair_cross(y, x) < pair_cross(x, y):
                        row[i], row[i + 1] = y, x
                        pos[x], pos[y] = i + 1, i
                        improved = True
            if not improved:
                break

    # ---- absolute positions
    def place(self):
        self.layout_container(None)
        self._absolute(None, MARGIN, MARGIN)

    def _absolute(self, cont, ox, oy):
        for k in self.kids(cont):
            x, y, w, h = self.rel[k]
            self.abs[k] = (ox + x, oy + y, w, h)
            if k.is_group:
                dx, dy = self.content_off[k]
                self._absolute(k, ox + x + dx, oy + y + dy)


# --------------------------------------------------------------------------------------------------------------------
# routing: every arrow on an orthogonal grid around the boxes

BEND_, CROSS_, SIDE_SOFT, SIDE_HARD = 22.0, 10.0, 16.0, 60.0
_DI, _DJ = (1, 0, -1, 0), (0, 1, 0, -1)          # E S W N
_SIDE_DIR = {"E": 0, "S": 1, "W": 2, "N": 3}       # direction that leaves a box through that side


class _Router:
    def __init__(self, flow):
        self.f = flow
        self.boxes = {}                 # node -> (x0, y0, x1, y1): leaves and group frames, absolute
        for n, (x, y, w, h) in flow.abs.items():
            self.boxes[n] = (x, y, x + w, y + h)
        self.hard = []                  # obstacles every arrow avoids (expanded leaves, notes, frame titles)
        self.groups = {}                # group -> expanded frame (avoided unless an end is inside it)
        for n, (x0, y0, x1, y1) in self.boxes.items():
            if n.is_group:
                self.groups[n] = (x0 - CLEAR, y0 - CLEAR, x1 + CLEAR, y1 + CLEAR)
                lines, tw = flow.titles[n]
                self.hard.append((x0 + 8, y0 + 5, x0 + 16 + tw, y0 + 23 + (len(lines) - 1) * 13))
            else:
                self.hard.append((x0 - CLEAR, y0 - CLEAR, x1 + CLEAR, y1 + CLEAR))
            note = flow.note_geo.get(n)
            if note:
                nx, ny = x0 + note[0], y0 + note[1]
                self.hard.append((nx - 4, ny - 4, nx + note[2] + 4, ny + note[3] + 4))
        edges = [e for e in flow.g.edges if e.a is not e.b]
        xs, ys = set(), set()
        bnd_x, bnd_y = set(), set()
        for r in self.hard + list(self.groups.values()):
            bnd_x.update((r[0], r[2]))
            bnd_y.update((r[1], r[3]))
        for n, (x0, y0, x1, y1) in self.boxes.items():
            xs.add((x0 + x1) / 2)
            ys.add((y0 + y1) / 2)
            if self._rectish(n):                        # second ports, a quarter in from each corner
                xs.update((x0 + (x1 - x0) / 4, x1 - (x1 - x0) / 4))
                ys.update((y0 + (y1 - y0) / 4, y1 - (y1 - y0) / 4))
        for e in edges:
            for s, t in ((e.a, e.b), (e.b, e.a)):
                sx0, sy0, sx1, sy1 = self.boxes[s]
                tx0, ty0, tx1, ty1 = self.boxes[t]
                if self._rectish(s):
                    cy, cx = (ty0 + ty1) / 2, (tx0 + tx1) / 2
                    if sy0 + 0.2 * (sy1 - sy0) <= cy <= sy0 + 0.8 * (sy1 - sy0):
                        ys.add(cy)
                    if sx0 + 0.2 * (sx1 - sx0) <= cx <= sx0 + 0.8 * (sx1 - sx0):
                        xs.add(cx)
        allx = sorted(bnd_x | xs)
        ally = sorted(bnd_y | ys)
        for vals, out in ((sorted(bnd_x | xs), xs), (sorted(bnd_y | ys), ys)):
            for p, q in zip(vals, vals[1:]):
                gap = q - p
                if gap > 2 * TRACK:
                    mid = (p + q) / 2
                    out.add(mid)
                    k = 1
                    while k <= 3 and gap / 2 - k * TRACK >= TRACK:
                        out.add(mid - k * TRACK)
                        out.add(mid + k * TRACK)
                        k += 1
        lo_x, hi_x = min(allx) - 2 * CLEAR, max(allx) + 2 * CLEAR
        lo_y, hi_y = min(ally) - 2 * CLEAR, max(ally) + 2 * CLEAR
        xs.update((lo_x, hi_x))
        ys.update((lo_y, hi_y))
        self.xs = sorted({round(v, 2) for v in xs | bnd_x})
        self.ys = sorted({round(v, 2) for v in ys | bnd_y})
        bx = {round(v, 2) for v in bnd_x} - {round(v, 2) for v in xs}
        by = {round(v, 2) for v in bnd_y} - {round(v, 2) for v in ys}
        self.wx = [1.25 if v in bx else 1.0 for v in self.xs]      # weight of running along x = xs[i]
        self.wy = [1.25 if v in by else 1.0 for v in self.ys]
        self.ix = {v: i for i, v in enumerate(self.xs)}
        self.iy = {v: j for j, v in enumerate(self.ys)}
        self.NX, self.NY = len(self.xs), len(self.ys)
        N = self.NX * self.NY
        self.base_h = bytearray(N)
        self.base_v = bytearray(N)
        for r in self.hard:
            self._fill(r, self.base_h, self.base_v)
        self.group_masks = {}
        for gnode, r in self.groups.items():
            mh, mv = bytearray(N), bytearray(N)
            self._fill(r, mh, mv)
            self.group_masks[gnode] = (mh, mv)
        self.hown, self.vown = {}, {}
        self.hpts, self.vpts = set(), set()
        self.port_own = {}
        self.side_own = {}

    def _rectish(self, n):
        return n.is_group or n.shape in _BOXLIKE

    def _fill(self, r, mh, mv):
        x0, y0, x1, y1 = (round(v, 2) for v in r)
        xs, ys, NY = self.xs, self.ys, self.NY
        i0 = self._lo(xs, x0)
        i1 = self._lo(xs, x1)
        j0 = self._lo(ys, y0)
        j1 = self._lo(ys, y1)
        # horizontal pieces strictly inside: rows strictly between y0 and y1, columns from x0 to x1
        for j in range(j0, j1 + 1):
            if not (y0 < ys[j] < y1):
                continue
            for i in range(i0, i1):
                if xs[i] >= x0 and xs[i + 1] <= x1:
                    mh[i * NY + j] = 1
        for i in range(i0, i1 + 1):
            if not (x0 < xs[i] < x1):
                continue
            for j in range(j0, j1):
                if ys[j] >= y0 and ys[j + 1] <= y1:
                    mv[i * NY + j] = 1

    @staticmethod
    def _lo(vals, v):
        lo, hi = 0, len(vals) - 1
        while lo < hi:
            mid = (lo + hi) // 2
            if vals[mid] < v - 1e-6:
                lo = mid + 1
            else:
                hi = mid
        return lo

    def _ports(self, n, other, out_end, forward, back=False):
        """[(grid index, direction leaving the box, cost, point on the box)] for one end of an arrow."""
        x0, y0, x1, y1 = self.boxes[n]
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        ox0, oy0, ox1, oy1 = self.boxes[other]
        ocx, ocy = (ox0 + ox1) / 2, (oy0 + oy1) / 2
        right = self.f.right
        if right:
            main = "E" if out_end else "W"
            back = "W" if out_end else "E"
            cross = ("N", "S")
        else:
            main = "S" if out_end else "N"
            back = "N" if out_end else "S"
            cross = ("W", "E")
        ports = []
        cand = [("E", x1, cy, 0.0), ("W", x0, cy, 0.0), ("S", cx, y1, 0.0), ("N", cx, y0, 0.0)]
        if self._rectish(n):
            # a rectangle may be entered anywhere along the middle 70 % of a side (off-centre costs a little),
            # so an arrow runs straight whenever the two boxes overlap
            hw, hh = (x1 - x0) / 2, (y1 - y0) / 2
            for x in self.xs[self._lo(self.xs, x0 + 0.15 * (x1 - x0)):]:
                if x > x1 - 0.15 * (x1 - x0):
                    break
                if abs(x - cx) > 0.01:
                    c = 2.0 + 6.0 * abs(x - cx) / hw
                    cand += [("S", x, y1, c), ("N", x, y0, c)]
            for y in self.ys[self._lo(self.ys, y0 + 0.15 * (y1 - y0)):]:
                if y > y1 - 0.15 * (y1 - y0):
                    break
                if abs(y - cy) > 0.01:
                    c = 2.0 + 6.0 * abs(y - cy) / hh
                    cand += [("E", x1, y, c), ("W", x0, y, c)]
        elif n.shape in ("circle", "diamond"):
            # near a point of a diamond or the top of a circle, a slightly shifted arrow still meets the outline
            rx, ry = (x1 - x0) / 2, (y1 - y0) / 2
            lim = 0.35 if n.shape == "circle" else 0.18
            for x in self.xs[self._lo(self.xs, cx - lim * rx):]:
                if x > cx + lim * rx:
                    break
                if abs(x - cx) > 0.01:
                    u = abs(x - cx) / rx
                    dy = ry * (math.sqrt(max(0.0, 1 - u * u)) if n.shape == "circle" else 1 - u)
                    c = 3.0 + 8.0 * u / lim
                    cand += [("S", x, cy + dy, c), ("N", x, cy - dy, c)]
            for y in self.ys[self._lo(self.ys, cy - lim * ry):]:
                if y > cy + lim * ry:
                    break
                if abs(y - cy) > 0.01:
                    u = abs(y - cy) / ry
                    dx = rx * (math.sqrt(max(0.0, 1 - u * u)) if n.shape == "circle" else 1 - u)
                    c = 3.0 + 8.0 * u / lim
                    cand += [("E", cx + dx, y, c), ("W", cx - dx, y, c)]
        for side, px, py, extra in cand:
            if forward:
                cost = 0.0 if side == main else SIDE_HARD if side == back else SIDE_SOFT
            else:
                # an arrow that turns back goes over or under the boxes, never back along the main line
                cost = 0.0 if side in cross else (SIDE_HARD * 2 if back else SIDE_SOFT)
                # toward the other end costs least
                if side in cross:
                    toward = (side == "S") == (ocy > cy) if right else (side == "E") == (ocx > cx)
                    cost = 0.0 if toward else 8.0
            cost += extra
            d = _SIDE_DIR[side]
            gx = {"E": x1 + CLEAR, "W": x0 - CLEAR}.get(side, px)
            gy = {"S": y1 + CLEAR, "N": y0 - CLEAR}.get(side, py)
            i, j = self.ix.get(round(gx, 2)), self.iy.get(round(gy, 2))
            if i is None or j is None:
                continue
            ports.append((i * self.NY + j, d, cost, (px, py)))
        return ports

    def route(self, e, owner):
        s, t = e.a, e.b
        sx0, sy0, sx1, sy1 = self.boxes[s]
        tx0, ty0, tx1, ty1 = self.boxes[t]
        forward = (tx0 >= sx1 - 1) if self.f.right else (ty0 >= sy1 - 1)
        back = (tx1 <= sx0 + 1) if self.f.right else (ty1 <= sy0 + 1)
        starts = self._ports(s, t, True, forward, back)
        goals = self._ports(t, s, False, forward, back)
        mh, mv = bytearray(self.base_h), bytearray(self.base_v)
        inside = set(_ancestors(s)) | set(_ancestors(t))
        for gnode, (gh, gv) in self.group_masks.items():
            if gnode in inside:
                continue
            for k, val in enumerate(gh):
                if val:
                    mh[k] = 1
            for k, val in enumerate(gv):
                if val:
                    mv[k] = 1
        # the expanded frame of a group at an end blocks the inside of that frame only
        # a port another arrow already leaves from is shared only where sharing is allowed
        def busy(n, c, d):
            if not all(self._share_ok(o, owner) for o in self.port_own.get((n, c), ())):
                return 150.0
            # arrows that may share a side come together at one port (one arrowhead, one line)
            mates = [cc for (o, cc) in self.side_own.get((n, d), ()) if self._share_ok(o, owner)]
            return 30.0 if mates and c not in mates else 0.0
        starts = [(c, d, cost + busy(s, c, d), pt) for c, d, cost, pt in starts]
        goals = [(c, d, cost + busy(t, c, d), pt) for c, d, cost, pt in goals]
        path = self._astar(starts, goals, mh, mv, owner, back)
        if path is None:
            (sp, tp) = (starts[0][3] if starts else ((sx0 + sx1) / 2, (sy0 + sy1) / 2),
                        goals[0][3] if goals else ((tx0 + tx1) / 2, (ty0 + ty1) / 2))
            pts = [sp, (sp[0], tp[1]) if self.f.right is False else (tp[0], sp[1]), tp]
            return _simplify(pts)
        cells, sp, tp = path
        self.port_own.setdefault((s, cells[0]), []).append(owner)
        self.port_own.setdefault((t, cells[-1]), []).append(owner)
        d0 = next(d for c, d, _cost, _pt in starts if c == cells[0])
        d1 = next(d for c, d, _cost, _pt in goals if c == cells[-1])
        self.side_own.setdefault((s, d0), []).append((owner, cells[0]))
        self.side_own.setdefault((t, d1), []).append((owner, cells[-1]))
        grid = [(self.xs[c // self.NY], self.ys[c % self.NY]) for c in cells]
        sp = (grid[0][0], sp[1]) if abs(grid[0][0] - sp[0]) < 0.05 else (sp[0], grid[0][1])
        tp = (grid[-1][0], tp[1]) if abs(grid[-1][0] - tp[0]) < 0.05 else (tp[0], grid[-1][1])
        pts = [sp] + grid + [tp]
        self._claim(cells, owner)
        return _simplify(pts)

    def _claim(self, cells, owner):
        NY = self.NY
        for a, b in zip(cells, cells[1:]):
            ia, ja, ib, jb = a // NY, a % NY, b // NY, b % NY
            if ja == jb:
                k = min(ia, ib) * NY + ja
                self.hown.setdefault(k, []).append(owner)
                self.hpts.update((a, b))
            else:
                k = ia * NY + min(ja, jb)
                self.vown.setdefault(k, []).append(owner)
                self.vpts.update((a, b))

    @staticmethod
    def _share_ok(o, me):
        # arrows into one box may merge; arrows from one box may run together before they split, unless one has a
        # label (it would sit on the shared part) or they leave a decision (yes and no leave by different sides)
        return o[1] is me[1] or (o[0] is me[0] and not (o[2] or me[2] or me[3]))

    def _astar(self, starts, goals, mh, mv, owner, back=False):
        """Cheapest path from a start port to a goal port. An arrow that loops back pays less for length and
        more for bends and crossings: it may go the long way round to stay out of the main flow."""
        if not starts or not goals:
            return None
        lw = 0.6 if back else 1.0
        BEND = 2 * BEND_ if back else BEND_
        CROSS = 3 * CROSS_ if back else CROSS_
        xs, ys, NY, NX = self.xs, self.ys, self.NY, self.NX
        gpts = {}
        for cell, d, cost, pt in goals:
            gpts.setdefault(cell, []).append(((d + 2) % 4, cost, pt))       # arriving: moving into the box
        gxy = [(xs[c // NY], ys[c % NY]) for c in gpts]

        def h(cell):
            x, y = xs[cell // NY], ys[cell % NY]
            return lw * min(abs(x - a) + abs(y - b) for a, b in gxy)

        INF = float("inf")
        best = {}
        parent = {}
        heap = []
        tick = 0
        for cell, d, cost, pt in starts:
            st = cell * 4 + d
            if cost < best.get(st, INF):
                best[st] = cost
                parent[st] = ("S", pt)
                heap.append((cost + h(cell), tick, cost, st))
                tick += 1
        heapq.heapify(heap)
        hown, vown, hpts, vpts = self.hown, self.vown, self.hpts, self.vpts
        wx, wy = self.wx, self.wy
        share_ok = self._share_ok
        pops = 0
        while heap:
            f, _, g, st = heapq.heappop(heap)
            if st < 0:                                    # a finished route
                end = parent[st]
                cells = []
                cur = end[1]
                while True:
                    cells.append(cur // 4)
                    p = parent[cur]
                    if p[0] == "S":
                        sp = p[1]
                        break
                    cur = p[1]
                cells.reverse()
                return cells, sp, end[2]
            if g > best.get(st, INF):
                continue
            pops += 1
            if pops > 60000:
                return None
            cell, d = divmod(st, 4)
            i, j = divmod(cell, NY)
            if cell in gpts:
                for din, cost, pt in gpts[cell]:
                    fin = g + cost + (0.0 if d == din else BEND)
                    key = -1 - (st * 8 + din)
                    if fin < best.get(key, INF):
                        best[key] = fin
                        parent[key] = ("E", st, pt)
                        heapq.heappush(heap, (fin, tick, fin, key))
                        tick += 1
            for nd in range(4):
                if nd == (d + 2) % 4:
                    continue
                ni, nj = i + _DI[nd], j + _DJ[nd]
                if ni < 0 or nj < 0 or ni >= NX or nj >= NY:
                    continue
                ncell = ni * NY + nj
                if nd % 2 == 0:                            # along x
                    k = min(i, ni) * NY + j
                    if mh[k]:
                        continue
                    length = abs(xs[ni] - xs[i])
                    step = length * wy[j] * lw
                    owners = hown.get(k)
                    if ncell in vpts:
                        step += CROSS
                else:
                    k = i * NY + min(j, nj)
                    if mv[k]:
                        continue
                    length = abs(ys[nj] - ys[j])
                    step = length * wx[i] * lw
                    owners = vown.get(k)
                    if ncell in hpts:
                        step += CROSS
                if owners:
                    for o in owners:
                        if not share_ok(o, owner):
                            step += 400.0 + 4 * length
                            break
                if nd != d:
                    step += BEND
                ng = g + step
                nst = ncell * 4 + nd
                if ng < best.get(nst, INF) - 1e-9:
                    best[nst] = ng
                    parent[nst] = ("P", st)
                    heapq.heappush(heap, (ng + h(ncell), tick, ng, nst))
                    tick += 1
        return None


def _simplify(pts):
    out = []
    for p in pts:
        p = (float(p[0]), float(p[1]))
        if out and abs(p[0] - out[-1][0]) < 0.05 and abs(p[1] - out[-1][1]) < 0.05:
            continue
        out.append(p)
    changed = True
    while changed and len(out) > 2:
        changed = False
        for k in range(1, len(out) - 1):
            (x0, y0), (x1, y1), (x2, y2) = out[k - 1], out[k], out[k + 1]
            if (abs(x0 - x1) < 0.05 and abs(x1 - x2) < 0.05) or (abs(y0 - y1) < 0.05 and abs(y1 - y2) < 0.05):
                del out[k]
                changed = True
                break
    return out


def _rects_hit(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _seg_hits_rect(p, q, r):
    x0, y0 = min(p[0], q[0]), min(p[1], q[1])
    x1, y1 = max(p[0], q[0]), max(p[1], q[1])
    return x0 <= r[2] and r[0] <= x1 and y0 <= r[3] and r[1] <= y1


def _place_label(text, pts, blockers, other_routes, prefer_first):
    """Centre of a label on the route pts that touches no box, label or other arrow (or the best try)."""
    w, h = draw.mono_width(text, FS_LABEL) + 10, 18.0
    segs = []
    for k, (p, q) in enumerate(zip(pts, pts[1:])):
        segs.append((k, p, q, math.hypot(q[0] - p[0], q[1] - p[1])))
    order = sorted(segs, key=lambda s: (s[0] if prefer_first else 0, -s[3], s[0]))
    fallback = None
    for strict in (True, False):
        for k, p, q, length in order:
            horiz = abs(p[1] - q[1]) < 1e-6
            need = (w if horiz else h) + 14
            if length < need and strict:
                continue
            for t in (0.5, 0.4, 0.6, 0.3, 0.7, 0.2, 0.8):
                cx, cy = p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t
                r = (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
                if fallback is None:
                    fallback = (cx, cy)
                if any(_rects_hit(r, b) for b in blockers):
                    continue
                if strict and any(_seg_hits_rect(a, b, r) for route in other_routes for a, b in zip(route, route[1:])):
                    continue
                return (cx, cy), r
    for k, p, q, length in order:                  # beside the line: above or below it, left or right of it
        horiz = abs(p[1] - q[1]) < 1e-6
        for t in (0.5, 0.3, 0.7):
            cx, cy = p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t
            for dx, dy in (((0, -h / 2 - 3), (0, h / 2 + 3)) if horiz else ((w / 2 + 4, 0), (-w / 2 - 4, 0))):
                r = (cx + dx - w / 2, cy + dy - h / 2, cx + dx + w / 2, cy + dy + h / 2)
                if not any(_rects_hit(r, b) for b in blockers):
                    return (cx + dx, cy + dy), r
    if fallback is None:
        p, q = pts[0], pts[-1]
        fallback = ((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)
    cx, cy = fallback
    return fallback, (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)


def _loop_points(box, right):
    x0, y0, x1, y1 = box
    if right:
        return [(x1 - 18, y0), (x1 - 18, y0 - 18), (x1 + 18, y0 - 18), (x1 + 18, y0 + (y1 - y0) * 0.3),
                (x1, y0 + (y1 - y0) * 0.3)]
    return [(x1, y0 + (y1 - y0) * 0.3), (x1 + 18, y0 + (y1 - y0) * 0.3), (x1 + 18, y1 + 16),
            (x1 - 18, y1 + 16), (x1 - 18, y1)]


def _edge_style(e):
    return " ".join(s for s in (e.line_style,) if s)


def _describe(g):
    def name(n):
        return n.label or n.name
    parts = []
    for e in g.edges:
        verb = "leads to" if e.heads == "end" else "and" if e.heads == "none" else "connects both ways with"
        tail = " (%s)" % e.label if e.label else ""
        parts.append("%s %s %s%s" % (name(e.a), verb, name(e.b), tail))
    groups = [n for n in g.nodes.values() if n.is_group]
    for grp in groups:
        members = [name(m) for m in grp.children]
        if members:
            parts.append("%s holds %s" % (name(grp), ", ".join(members)))
    for n in g.nodes.values():
        if n.note:
            parts.append("note on %s: %s" % (name(n), n.note))
    parts.extend(g.notes)
    return ". ".join(parts) + ("." if parts else "")


def _title(g, what="Diagram"):
    if g.title:
        return g.title
    labels = g.labels() if g.kind == "flow" else [t for _d, t, *_ in g.items] if g.kind == "timeline" else []
    if g.kind == "tree":
        labels = []

        def walk(nodes):
            for t in nodes:
                labels.append(t.label)
                walk(t.children)
        walk(g.roots)
    shown = labels[:8]
    more = len(labels) - len(shown)
    return "%s: %s%s" % (what, ", ".join(shown), (" and %d more" % more) if more > 0 else "")


def _flow_diagram(g, direction, narrow, text_w=None):
    f = _Flow(g, direction, narrow, text_w)
    f.place()
    W, H = f.total
    d = draw.Diagram(W + 2 * MARGIN, title=_title(g), desc=_describe(g))
    d.fit = True
    # frames, outer first
    def depth(n):
        return len(_ancestors(n))
    for n in sorted((n for n in g.nodes.values() if n.is_group), key=lambda n: (depth(n), n.order)):
        x, y, w, h = f.abs[n]
        d.frame(x, y, w, h, "\n".join(f.titles[n][0]), style=n.gstyle or n.style, depth=depth(n))
    router = _Router(f)
    owners = {}
    # the straightest arrows first (they keep the main line clean), then the short ones
    order = sorted((e for e in g.edges if e.a is not e.b),
                   key=lambda e: (_backward(f.abs[e.a], f.abs[e.b], f.right),
                                  not _can_be_straight(f.abs[e.a], f.abs[e.b], f.right), bool(e.label),
                                  _dist(f.abs[e.a], f.abs[e.b]), e.index))
    routes = {}
    for e in order:
        owner = (e.a, e.b, bool(e.label), e.a.shape == "diamond" if not e.a.is_group else False)
        owners[e] = owner
        routes[e] = router.route(e, owner)
    for e in g.edges:
        if e.a is e.b:
            x, y, w, h = f.abs[e.a]
            routes[e] = _loop_points((x, y, x + w, y + h), f.right)
    # labels: off the boxes, the notes, each other and (when possible) the other arrows
    blockers = [(x - 2, y - 2, x + w + 2, y + h + 2) for n, (x, y, w, h) in f.abs.items() if not n.is_group]
    for n, (x, y, w, h) in f.abs.items():
        note = f.note_geo.get(n)
        if note:
            blockers.append((x + note[0] - 2, y + note[1] - 2, x + note[0] + note[2] + 2, y + note[1] + note[3] + 2))
        if n.is_group:
            lines, tw = f.titles[n]
            blockers.append((x + 8, y + 4, x + 16 + tw, y + 24 + (len(lines) - 1) * 13))
            # a label never sits across a frame's edge
            blockers += [(x - 1, y - 1, x + w + 1, y + 1), (x - 1, y + h - 1, x + w + 1, y + h + 1),
                         (x - 1, y - 1, x + 1, y + h + 1), (x + w - 1, y - 1, x + w + 1, y + h + 1)]
    label_at = {}
    for e in sorted((e for e in g.edges if e.label), key=lambda e: e.index):
        others = [r for k, r in routes.items() if k is not e]
        at, rect = _place_label(e.label, routes[e], blockers, others, e.a.shape == "diamond")
        label_at[e] = at
        blockers.append(rect)
    for e in g.edges:
        heads = {"end": "end", "both": "both", "none": "none"}[e.heads]
        d.route(routes[e], style=_edge_style(e), label=e.label, heads=heads, label_at=label_at.get(e))
    for n, (x, y, w, h) in f.abs.items():
        if n.is_group:
            continue
        lines, sub = f.text[n]
        b = d.node(x, y, w, h, n.label or n.name, n.sub, style=n.style, shape=_SHAPE_DRAW.get(n.shape, "box"))
        b.lines, b.sub_lines = lines, sub
    for n, (x, y, w, h) in f.abs.items():
        note = f.note_geo.get(n)
        if note:
            nx, ny, nw, nh, lines = note
            if f.right:
                d.anno(x + w / 2, y + ny + FS_NOTE * 0.95, lines, anchor="middle")
            else:
                d.anno(x + nx, y + ny + FS_NOTE * 0.95, lines, anchor="start")
    _free_notes(d, g.notes, W + 2 * MARGIN, H + MARGIN)
    # what was placed where (the tests check it: no overlaps, arrows clear of boxes, groups around their members)
    d.layout_info = {
        "boxes": {n.name: tuple(f.abs[n]) for n in g.nodes.values() if not n.is_group},
        "groups": {n.name: tuple(f.abs[n]) for n in g.nodes.values() if n.is_group},
        "members": {n.name: [m.name for m in n.children] for n in g.nodes.values() if n.is_group},
        "shapes": {n.name: n.shape for n in g.nodes.values() if not n.is_group},
        "routes": [(e.a.name, e.b.name, routes[e]) for e in g.edges],
        "labels": [(e.label, label_at[e]) for e in g.edges if e.label],
    }
    return d


def _backward(a, b, right):
    return b[0] + b[2] <= a[0] + 1 if right else b[1] + b[3] <= a[1] + 1


def _can_be_straight(a, b, right):
    k, n = (1, 3) if right else (0, 2)
    ca, cb = a[k] + a[n] / 2, b[k] + b[n] / 2
    return abs(ca - cb) <= 0.3 * min(a[n], b[n]) + 0.5


def _offset(a, b, right):
    return abs((a[1] + a[3] / 2) - (b[1] + b[3] / 2)) if right else abs((a[0] + a[2] / 2) - (b[0] + b[2] / 2))


def _dist(a, b):
    return abs((a[0] + a[2] / 2) - (b[0] + b[2] / 2)) + abs((a[1] + a[3] / 2) - (b[1] + b[3] / 2))


def _free_notes(d, notes, width, bottom):
    y = bottom + 20
    for text in notes:
        lines = draw.mono_wrap(text, max(160.0, width - 24), FS_NOTE)
        d.anno(width / 2, y, lines, anchor="middle", style="free")
        y += len(lines) * FS_NOTE * LINE + 6


# --------------------------------------------------------------------------------------------------------------------
# timelines

def _timeline_diagram(g, vertical, narrow):
    items = g.items
    width_text = 172.0 if not vertical else (210.0 if narrow else 300.0)
    blocks = []
    for date, title, detail, style, _line in items:
        tl = draw.mono_wrap(title, width_text, FS)
        dl = draw.mono_wrap(detail, width_text, FS_SUB) if detail else []
        bw = max([draw.mono_width(t, FS) for t in tl] + [draw.mono_width(t, FS_SUB) for t in dl])
        bh = len(tl) * FS * LINE + len(dl) * FS_SUB * LINE
        blocks.append((date, tl, dl, bw, bh, style))
    d = draw.Diagram(10, title=_title(g, "Timeline"),
                     desc=". ".join("%s: %s%s" % (it[0], it[1], (" (%s)" % it[2]) if it[2] else "") for it in items)
                     + ".")
    d.fit = True
    if vertical:
        dates = [draw.mono_wrap(b[0], 96.0, 13.0) for b in blocks]
        dw = max(draw.mono_width(t, 13.0) for ls in dates for t in ls)
        ax = MARGIN + dw + 18
        y = MARGIN + 18
        ys = []
        for (date, tl, dl, bw, bh, style), dlines in zip(blocks, dates):
            hgt = max(bh, len(dlines) * 13 * LINE)
            ys.append((y, hgt))
            y += hgt + 18
        top, bottom = MARGIN + 4, y - 4
        d.route([(ax, top), (ax, bottom + 6)], style="axis", heads="end")
        for (date, tl, dl, bw, bh, style), dlines, (yy, hgt) in zip(blocks, dates, ys):
            cy = yy + FS * LINE / 2
            d.node(ax - 5, cy - 5, 10, 10, "", style=("tick " + style).strip(), shape="circle")
            d.anno(ax - 14, cy + 13 * 0.34, dlines, anchor="end", style=("date " + style).strip(), fs=13)
            d.anno(ax + 16, cy + FS * 0.34, tl, anchor="start", style=("event " + style).strip(), fs=FS)
            if dl:
                d.anno(ax + 16, cy + FS * 0.34 + len(tl) * FS * LINE - (FS - FS_SUB) * 0.3, dl, anchor="start",
                       style="detail", fs=FS_SUB)
        _free_notes(d, g.notes, max(ax + 16 + max(b[3] for b in blocks), 240) + MARGIN, bottom + 6)
        return d
    n = len(blocks)
    dates = [draw.mono_width(b[0], 13.0) for b in blocks]
    pitch = 70.0
    for i in range(n):
        if i + 2 < n:
            pitch = max(pitch, ((blocks[i][3] + blocks[i + 2][3]) / 2 + 22) / 2,
                        ((dates[i] + dates[i + 2]) / 2 + 16) / 2)
        if i + 1 < n:
            pitch = max(pitch, (dates[i] + dates[i + 1]) / 2 / 2 + 6)
    above = max([b[4] for k, b in enumerate(blocks) if k % 2 == 0] + [0])
    below = max([b[4] for k, b in enumerate(blocks) if k % 2 == 1] + [0])
    stem = 26.0
    left = MARGIN + max(blocks[0][3] / 2, dates[0] / 2, 20) + 4
    axis_y = MARGIN + above + stem + 6
    xs = [left + i * pitch for i in range(n)]
    d.route([(xs[0] - 22, axis_y), (xs[-1] + 34, axis_y)], style="axis", heads="end")
    for k, ((date, tl, dl, bw, bh, style), x) in enumerate(zip(blocks, xs)):
        up = k % 2 == 0
        d.route([(x, axis_y + (-6 if up else 6)), (x, axis_y + (-stem if up else stem))], style="stem", heads="none")
        d.node(x - 5, axis_y - 5, 10, 10, "", style=("tick " + style).strip(), shape="circle")
        d.anno(x, axis_y + (20 if up else -11), [date], anchor="middle", style=("date " + style).strip(), fs=13)
        if up:
            y0 = axis_y - stem - 6 - bh
        else:
            y0 = axis_y + stem + 6
        d.anno(x, y0 + FS * 0.95, tl, anchor="middle", style=("event " + style).strip(), fs=FS)
        if dl:
            d.anno(x, y0 + len(tl) * FS * LINE + FS_SUB * 0.95, dl, anchor="middle", style="detail", fs=FS_SUB)
    bottom = axis_y + stem + 6 + below if n > 1 else axis_y + 28
    W = xs[-1] + max(blocks[-1][3] / 2, 40) + MARGIN
    _free_notes(d, g.notes, W, bottom)
    return d


# --------------------------------------------------------------------------------------------------------------------
# trees

def _tree_measure(nodes, maxw, out):
    for t in nodes:
        out[t] = _measure(t.label, t.sub, t.shape, maxw)
        _tree_measure(t.children, maxw, out)


def _tree_diagram(g, direction, narrow):
    size = {}
    _tree_measure(g.roots, 168.0 if direction == "outline" else 150.0, size)
    d = draw.Diagram(10, title=_title(g, "Tree"), desc=_tree_desc(g.roots))
    d.fit = True
    pos = {}
    if direction == "outline":
        y = [MARGIN]

        def walk(nodes, depth):
            for t in nodes:
                w, h = size[t][0], size[t][1]
                pos[t] = (MARGIN + depth * 30, y[0], w, h)
                y[0] += h + 10
                walk(t.children, depth + 1)
        walk(g.roots, 0)
        for t in pos:
            x, yy, w, h = pos[t]
            for c in t.children:
                cx, cy, cw, ch = pos[c]
                d.route([(x + 15, yy + h), (x + 15, cy + ch / 2), (cx, cy + ch / 2)], style="tree", heads="none")
    else:
        down = direction == "down"
        gap_level, gap_sib = (40.0, 18.0) if down else (44.0, 12.0)
        depth_of = {}

        def walk_depth(nodes, k):
            for t in nodes:
                depth_of[t] = k
                walk_depth(t.children, k + 1)
        walk_depth(g.roots, 0)
        levels = max(depth_of.values()) + 1
        lev = [0.0] * levels
        for t, k in depth_of.items():
            lev[k] = max(lev[k], size[t][1] if down else size[t][0])
        lpos, cur = [], MARGIN
        for k in range(levels):
            lpos.append(cur)
            cur += lev[k] + gap_level
        span = {}

        def extent(t):
            own = size[t][0] if down else size[t][1]
            kids = sum(extent(c) for c in t.children) + gap_sib * (len(t.children) - 1) if t.children else 0
            span[t] = max(own, kids)
            return span[t]

        def assign(t, start):
            own = size[t][0] if down else size[t][1]
            k = depth_of[t]
            if t.children:
                kids = sum(span[c] for c in t.children) + gap_sib * (len(t.children) - 1)
                s = start + (span[t] - kids) / 2
                centres = []
                for c in t.children:
                    centres.append(assign(c, s))
                    s += span[c] + gap_sib
                mid = (centres[0] + centres[-1]) / 2
                mid = min(max(mid, start + own / 2), start + span[t] - own / 2)
            else:
                mid = start + span[t] / 2
            w, h = size[t][0], size[t][1]
            if down:
                pos[t] = (mid - w / 2, lpos[k] + (lev[k] - h) / 2, w, h)
            else:
                pos[t] = (lpos[k] + (lev[k] - w) / 2, mid - h / 2, w, h)
            return mid

        s = MARGIN
        for r in g.roots:
            extent(r)
            assign(r, s)
            s += span[r] + gap_sib * 2
        for t in pos:
            x, y, w, h = pos[t]
            for c in t.children:
                cx, cy, cw, ch = pos[c]
                if down:
                    bus = y + h + (lpos[depth_of[t] + 1] - (y + h)) / 2 if False else lpos[depth_of[t]] + lev[depth_of[t]] + gap_level / 2
                    pts = [(x + w / 2, y + h), (x + w / 2, bus), (cx + cw / 2, bus), (cx + cw / 2, cy)]
                else:
                    bus = lpos[depth_of[t]] + lev[depth_of[t]] + gap_level / 2
                    pts = [(x + w, y + h / 2), (bus, y + h / 2), (bus, cy + ch / 2), (cx, cy + ch / 2)]
                d.route(_simplify(pts), style="tree", heads="none", radius=5)
    for t, (x, y, w, h) in pos.items():
        b = d.node(x, y, w, h, t.label, t.sub, style=t.style, shape=_SHAPE_DRAW.get(t.shape, "box"))
        b.lines, b.sub_lines = size[t][2], size[t][3]
    W = max(x + w for x, y, w, h in pos.values()) + MARGIN
    H = max(y + h for x, y, w, h in pos.values())
    _free_notes(d, g.notes, W, H)
    return d


def _tree_desc(roots):
    parts = []

    def walk(t):
        if t.children:
            parts.append("%s has %s" % (t.label, ", ".join(c.label for c in t.children)))
        for c in t.children:
            walk(c)
    for r in roots:
        walk(r)
    return ". ".join(parts) + ("." if parts else "")


# --------------------------------------------------------------------------------------------------------------------
# the entry points

def _width(d):
    return d._extent[2] - min(0.0, d._extent[0])


def layout(g, narrow=False, direction=None):
    """The Diagram for a Graph: the wide layout, or the phone layout when narrow."""
    if g.kind == "timeline":
        vertical = narrow or (direction or g.direction) == "down"
        return _timeline_diagram(g, vertical, narrow)
    if g.kind == "tree":
        if narrow:
            return _tree_diagram(g, "outline", True)
        return _tree_diagram(g, direction or g.direction or "down", False)
    if narrow:
        return _flow_diagram(g, "down", True)
    dirn = direction or g.direction or "right"
    d = _flow_diagram(g, dirn, False)
    if dirn == "right" and _width(d) > WIDE_LIMIT:
        d2 = _flow_diagram(g, dirn, False, text_w=118.0)
        if _width(d2) < _width(d):
            d = d2
    return d


def variants(src, kind=None):
    """(graph, wide svg, phone svg or None, phone width): None when the wide drawing already suits a phone."""
    g = parse(src, kind)
    wide = layout(g)
    wsvg = wide.svg()
    W = _width(wide)
    needs = g.kind == "timeline" and (g.direction or "right") == "right" or \
        g.kind == "flow" and ((g.direction or "right") == "right" or W > NARROW_FIT) or \
        g.kind == "tree" and W > NARROW_FIT
    if not needs or W <= NARROW_FIT and g.kind != "timeline":
        return g, wsvg, None, W
    nar = layout(g, narrow=True)
    return g, wsvg, nar.svg(), _width(nar)


def render(src, kind=None, narrow=False):
    """The SVG for a diagram block (narrow=True: the phone layout). Raises DiagramError."""
    g = parse(src, kind)
    return layout(g, narrow=narrow).svg()


def render_html(src, kind=None, caption=None):
    """<figure class="drawing diagram"> with the drawing (and its phone version) and the caption."""
    g, wsvg, nsvg, nw = variants(src, kind)
    cap = caption if caption is not None else g.caption
    capf = ('<figcaption>%s</figcaption>' % htmllib.escape(cap.strip())) if cap and cap.strip() else ""
    if nsvg is None:
        body = '<div class="drawing-svg drawing-fit">%s</div>' % wsvg
    else:
        scroll = nw > NARROW_FIT + 20
        attrs = (' tabindex="0" role="region" aria-label="Diagram (scrolls sideways)" style="--dg-w:%dpx"' % round(nw)
                 if scroll else "")
        body = ('<div class="drawing-svg drawing-wide drawing-fit">%s</div>'
                '<div class="drawing-svg drawing-narrow drawing-fit%s"%s>%s</div>'
                % (wsvg, " dg-scroll" if scroll else "", attrs, nsvg))
    return '<figure class="drawing diagram" data-diagram="%s">%s%s</figure>' % (g.kind, body, capf)


def summary(g):
    """A plain sentence about the drawing (for search passages and the Studio)."""
    if g.kind == "timeline":
        return "Timeline: " + "; ".join("%s %s" % (d, t) for d, t, *_ in g.items) + "."
    return _title(g) + "."


# --------------------------------------------------------------------------------------------------------------------
# examples (the Studio's gallery, the guide and the tests use these)

EXAMPLES = [
    {"name": "pipeline", "title": "Pipeline", "caption": "Steps left to right, a side branch and a group",
     "source": """# A detection model, left to right
Input image [data] -> Backbone -> Encoder -> Decoder -> Boxes [data]
Backbone -> Neck: "multi-scale"
Neck -> Encoder
group Encoder { Attention -> Feed-forward }
Decoder [accent]
note Encoder: "6 layers"
"""},
    {"name": "architecture", "title": "Model architecture", "caption": "Layers top to bottom, a block as a group",
     "source": """direction: down
title: "An encoder-only Transformer for classification"
[/Tokens/] -> Embedding -> Self-attention
group "Encoder block x 6" {
  Self-attention -> norm1 -> Feed-forward -> norm2
}
norm1 [label="Add & norm", muted]
norm2 [label="Add & norm", muted]
Embedding -.-> norm1: "residual"
norm2 -> Classifier [accent] -> [/Label/]
"""},
    {"name": "flowchart", "title": "Flowchart", "caption": "Decisions with yes and no, and loops back",
     "source": """direction: down
(Start) -> Load a batch -> {Loss finite?}
Loss finite? ->|yes| Take a step -> {Last batch?}
Loss finite? ->|no| Halve the learning rate -> Load a batch
Last batch? ->|no| Load a batch
Last batch? ->|yes| (Done) [emphasis]
"""},
    {"name": "timeline", "title": "Timeline", "caption": "Dated events in order",
     "source": """kind: timeline
2012: AlexNet: "deep nets win ImageNet"
2015: ResNet: "152 layers, with skips"
2017: Transformer [accent]: "attention only"
2020: ViT: "images as patches"
2022: Diffusion at scale
"""},
    {"name": "tree", "title": "Tree", "caption": "A hierarchy by indentation",
     "source": """kind: tree
Machine learning
  Supervised
    Classification
    Regression
  Unsupervised
    Clustering
    Embeddings
  Reinforcement [accent]
"""},
]
