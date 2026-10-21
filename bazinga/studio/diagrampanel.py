"""The Editor's diagram panel: text diagrams (```diagram blocks) drawn as the author types.

Drawing a text diagram runs no author code (it only reads the text), so it happens in the Editor's own process,
fast enough for a live preview. Installed onto :class:`bazinga.studio.api.Editor` by ``install``.
"""
from __future__ import annotations

from .security import Refused

MAX_SOURCE = 50_000


def diagram_render(self, data) -> dict:
    """{source, kind?} -> the drawing (wide and phone versions, and the HTML the post will show) or the problem."""
    src = data.get("source")
    if not isinstance(src, str):
        raise Refused(400, "The diagram's text is missing.")
    if len(src) > MAX_SOURCE:
        raise Refused(413, "That diagram is too long.")
    kind = data.get("kind") or None
    try:
        from bazinga import diagram_text as dt
    except Exception as exc:  # noqa: BLE001 - shown as "not available", never a crash
        return {"available": False, "ok": False, "error": f"Diagrams are not available yet ({exc})."}
    try:
        g, wide, narrow, _w = dt.variants(src, kind)
        return {"available": True, "ok": True, "svg": wide, "narrow": narrow or wide,
                "html": dt.render_html(src, kind), "kind": g.kind, "summary": dt.summary(g),
                "boxes": _count_boxes(g), "arrows": len(g.edges)}
    except dt.DiagramError as exc:
        return {"available": True, "ok": False, "error": exc.message, "hint": exc.hint, "line": exc.line}


def _count_boxes(g):
    if g.kind == "timeline":
        return len(g.items)
    if g.kind == "tree":
        n = 0
        stack = list(g.roots)
        while stack:
            t = stack.pop()
            n += 1
            stack.extend(t.children)
        return n
    return sum(1 for n in g.nodes.values() if not n.is_group)


def diagram_examples(self, _q=None) -> dict:
    """The gallery: a working example of each kind of diagram."""
    try:
        from bazinga import diagram_text as dt
    except Exception:  # noqa: BLE001
        return {"available": False, "examples": []}
    return {"available": True, "examples": [
        {"name": e["name"], "title": e["title"], "caption": e.get("caption", ""), "source": e["source"]}
        for e in dt.EXAMPLES]}


def install(cls) -> None:
    cls.diagram_render = diagram_render
    cls.diagram_examples = diagram_examples
