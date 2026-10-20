"""The site graph: one graph over the public pages.

Edges
-----
- ``builds_on``  page -> prerequisite (directed, from front matter)
- ``mentions``   page -> page linked with ``[[id]]`` in the body (directed)
- ``cites``      two pages that cite the same reference key (undirected, one edge per pair)
- ``topic``      two pages that share a topic (undirected, weak; bounded per topic)
- ``series``     consecutive parts of a series (earlier -> later)

Everything here is deterministic: the same pages give the same JSON, byte for byte.
Standard library only.
"""
from __future__ import annotations

import math
import random
from collections import defaultdict, deque

WEIGHTS = {"builds_on": 3.0, "series": 2.5, "mentions": 2.0, "cites": 1.0, "topic": 0.5}
STRONG = ("builds_on", "mentions", "cites", "series")
DIRECT = ("builds_on", "mentions", "series")   # what the map's rings follow
TOPIC_NEIGHBOURS = 6          # a page is tied to at most this many same-topic pages (by date) per topic
RING_DEPTH = 3                # hover rings go this many steps out
SEED = 7


def _attr(obj, name, default=None):
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _iso(d):
    if d is None:
        return ""
    return d.isoformat() if hasattr(d, "isoformat") else str(d)


def series_slug(name: str) -> str:
    """The URL slug of a series name (the same rule as content.slugify)."""
    import re
    import unicodedata
    text = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "page"


class Graph:
    def __init__(self):
        self.nodes: dict[str, dict] = {}
        self.edges: list[dict] = []
        self.topics: dict[str, str] = {}      # slug -> label (for the map's chips)
        self._adj: dict[str, dict[str, float]] = defaultdict(dict)
        self._strong: dict[str, set] = defaultdict(set)
        self._direct: dict[str, set] = defaultdict(set)
        self._cites: dict[str, set] = defaultdict(set)
        self._topic_adj: dict[str, set] = defaultdict(set)
        self._layout = None
        self._rings = {}

    # -- construction -------------------------------------------------------------------------
    def add_edge(self, source, target, type_, weight=None):
        if source == target or source not in self.nodes or target not in self.nodes:
            return
        w = WEIGHTS[type_] if weight is None else weight
        self.edges.append({"source": source, "target": target, "type": type_, "weight": round(w, 3)})
        a = self._adj[source]
        b = self._adj[target]
        a[target] = a.get(target, 0.0) + w
        b[source] = b.get(source, 0.0) + w
        if type_ in STRONG:
            self._strong[source].add(target)
            self._strong[target].add(source)
        if type_ in DIRECT:
            self._direct[source].add(target)
            self._direct[target].add(source)
        elif type_ == "cites":
            self._cites[source].add(target)
            self._cites[target].add(source)
        else:
            self._topic_adj[source].add(target)
            self._topic_adj[target].add(source)

    def _edges_of(self, type_):
        return [e for e in self.edges if e["type"] == type_]

    # -- queries ------------------------------------------------------------------------------
    def _sort(self, ids):
        """Newest first, then title: the order lists use."""
        return sorted(set(ids), key=lambda i: (_neg_date(self.nodes[i]["date"]), self.nodes[i]["title"].lower(), i))

    def backlinks(self, id) -> list[str]:
        """Pages that link to ``id`` (builds_on or [[mention]])."""
        src = [e["source"] for e in self.edges if e["target"] == id and e["type"] in ("builds_on", "mentions")]
        return self._sort(src)

    def builds_on(self, id) -> list[str]:
        return [e["target"] for e in self.edges if e["source"] == id and e["type"] == "builds_on"]

    def read_next(self, id) -> list[str]:
        """Pages that build on ``id``."""
        return self._sort(e["source"] for e in self.edges if e["target"] == id and e["type"] == "builds_on")

    def related(self, id, k=5) -> list[str]:
        """Top ``k`` neighbours by summed edge weight, leaving out what builds_on / read_next already show."""
        if id not in self.nodes:
            return []
        skip = set(self.builds_on(id)) | set(self.read_next(id)) | {id}
        mine = set(self.nodes[id]["topics"])
        cand = [(w, n) for n, w in self._adj.get(id, {}).items() if n not in skip]

        def key(item):
            w, n = item
            node = self.nodes[n]
            return (-w, -len(mine & set(node["topics"])), _neg_date(node["date"]), n)

        return [n for _, n in sorted(cand, key=key)[:k]]

    def series(self) -> dict[str, list[str]]:
        groups = defaultdict(list)
        for n in self.nodes.values():
            s = n.get("series")
            if s and s.get("name"):
                groups[s["name"]].append(n)
        out = {}
        for name in sorted(groups):
            parts = sorted(groups[name], key=lambda n: (_num(n["series"].get("part")), n["date"], n["id"]))
            out[name] = [n["id"] for n in parts]
        return out

    def topic_pages(self, slug) -> list[str]:
        return self._sort(i for i, n in self.nodes.items() if slug in n["topics"])

    def degree(self, id) -> int:
        return len(self._adj.get(id, {}))

    def rings(self, id) -> dict[str, int]:
        """Nearest-first distance along direct links (builds_on, mentions, series), up to RING_DEPTH steps.

        A page with no direct links falls back to the pages it shares citations with, then to its topic peers.
        """
        if id in self._rings:
            return self._rings[id]
        dist = {id: 0}
        q = deque([id])
        while q:
            cur = q.popleft()
            if dist[cur] >= RING_DEPTH:
                continue
            for nb in sorted(self._direct.get(cur, ())):
                if nb not in dist:
                    dist[nb] = dist[cur] + 1
                    q.append(nb)
        if len(dist) == 1:
            for nb in sorted(self._cites.get(id, ()) or self._topic_adj.get(id, ())):
                dist[nb] = 1
        self._rings[id] = dist
        return dist

    # -- layout -------------------------------------------------------------------------------
    def layout(self) -> dict[str, tuple[float, float]]:
        if self._layout is None:
            self._layout = _force_layout(self)
        return self._layout

    def to_json(self) -> dict:
        pos = self.layout()
        nodes = []
        for i in sorted(self.nodes):
            n = dict(self.nodes[i])
            n["x"], n["y"] = pos[i]
            n["degree"] = self.degree(i)
            nodes.append(n)
        rings = {}
        for i in sorted(self.nodes):
            by = defaultdict(list)
            for other, d in self.rings(i).items():
                if d:
                    by[d].append(other)
            rings[i] = [sorted(by[d]) for d in sorted(by)]
        return {
            "nodes": nodes,
            "edges": sorted(self.edges, key=lambda e: (e["type"], e["source"], e["target"])),
            "rings": rings,
            "series": self.series(),
            "topics": {k: self.topics[k] for k in sorted(self.topics) if any(k in n["topics"] for n in nodes)},
        }


def _neg_date(s):
    # sort newest first with an ascending sort: invert the characters of an ISO date
    return "".join(chr(0x7F - ord(c)) if c.isdigit() else c for c in (s or "0000"))


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return 1e9


def build_graph(pages, rendered, site=None) -> Graph:
    """Build the graph from the public pages and their rendered output.

    ``rendered`` maps page id -> Rendered (``mentions``, ``cites``, ``figures``); a missing entry is fine.
    """
    g = Graph()
    rendered = rendered or {}
    topics = _attr(site, "topics", {}) or {}
    g.topics = {slug: (t.get("label") if isinstance(t, dict) else str(t)) or slug for slug, t in topics.items()}
    for p in sorted(pages, key=lambda p: p.id):
        r = rendered.get(p.id)
        series = _attr(p, "series")
        g.nodes[p.id] = {
            "id": p.id,
            "title": p.title,
            "url": p.url,
            "kind": p.kind,
            "summary": _attr(p, "summary", "") or "",
            "topics": list(_attr(p, "topics", []) or []),
            "date": _iso(_attr(p, "date")),
            "series": {"name": series.get("name"), "part": series.get("part")} if isinstance(series, dict) and series.get("name") else None,
            "figures": list(_attr(r, "figures", []) or []) if r is not None else [],
        }
    ids = set(g.nodes)

    # builds_on and mentions (directed)
    for p in sorted(pages, key=lambda p: p.id):
        seen = set()
        for t in _attr(p, "builds_on", []) or []:
            if t in ids and t not in seen:
                seen.add(t)
                g.add_edge(p.id, t, "builds_on")
        r = rendered.get(p.id)
        for t in (_attr(r, "mentions", []) or []) if r is not None else []:
            if t in ids and t not in seen:
                seen.add(t)
                g.add_edge(p.id, t, "mentions")

    # cites: pages that share reference keys, one edge per pair weighted by the count
    by_key = defaultdict(set)
    for p in pages:
        r = rendered.get(p.id)
        keys = set(_attr(p, "cites", []) or []) | set((_attr(r, "cites", []) or []) if r is not None else [])
        for k in keys:
            by_key[k].add(p.id)
    pair = defaultdict(int)
    for k in sorted(by_key):
        members = sorted(by_key[k])
        if len(members) > 40:          # a reference every page cites says nothing about closeness
            continue
        for i, a in enumerate(members):
            for b in members[i + 1:]:
                pair[(a, b)] += 1
    for (a, b), n in sorted(pair.items()):
        g.add_edge(a, b, "cites", WEIGHTS["cites"] * min(n, 3))

    # series: consecutive parts
    for name, order in g.series().items():
        for a, b in zip(order, order[1:]):
            g.add_edge(a, b, "series")

    # topic: shared topics, weak; each page tied to its nearest same-topic pages by date
    tpair = defaultdict(int)
    by_topic = defaultdict(list)
    for i in sorted(ids):
        for t in g.nodes[i]["topics"]:
            by_topic[t].append(i)
    for t in sorted(by_topic):
        members = sorted(by_topic[t], key=lambda i: (g.nodes[i]["date"], i))
        for idx, a in enumerate(members):
            for b in members[idx + 1: idx + 1 + TOPIC_NEIGHBOURS]:
                tpair[tuple(sorted((a, b)))] += 1
    for (a, b), n in sorted(tpair.items()):
        g.add_edge(a, b, "topic", WEIGHTS["topic"] * n)
    return g


# ------------------------------------------------------------------------------------------------
# Layout: clusters by main topic, then a force pass with local repulsion (spatial grid).
# ------------------------------------------------------------------------------------------------
def _force_layout(g: Graph) -> dict[str, tuple[float, float]]:
    ids = sorted(g.nodes)
    n = len(ids)
    if n == 0:
        return {}
    if n == 1:
        return {ids[0]: (0.5, 0.5)}
    rnd = random.Random(SEED)

    # Main topic per node: its first topic; clusters ordered by size then name.
    main = {i: (g.nodes[i]["topics"][0] if g.nodes[i]["topics"] else "") for i in ids}
    sizes = defaultdict(int)
    for i in ids:
        sizes[main[i]] += 1
    clusters = sorted(sizes, key=lambda t: (-sizes[t], t))
    centres = {}
    m = len(clusters)
    for k, t in enumerate(clusters):
        if m == 1:
            centres[t] = (0.0, 0.0)
        else:
            # sunflower spiral: big clusters near the middle, the rest spread evenly
            r = math.sqrt((k + 0.5) / m)
            a = k * 2.399963229728653
            centres[t] = (r * math.cos(a), r * math.sin(a))

    pos = {}
    for i in ids:
        cx, cy = centres[main[i]]
        pos[i] = [cx + rnd.uniform(-0.08, 0.08), cy + rnd.uniform(-0.08, 0.08)]

    ideal = 1.4 / math.sqrt(n)            # target spacing in the [-1, 1] box
    cell = ideal * 2.5
    edges = {}
    for e in g.edges:
        key = tuple(sorted((e["source"], e["target"])))
        edges[key] = edges.get(key, 0.0) + e["weight"]
    edge_list = sorted(edges.items())
    iters = 220
    temp = 0.12
    for it in range(iters):
        disp = {i: [0.0, 0.0] for i in ids}
        # local repulsion through a grid
        grid = defaultdict(list)
        for i in ids:
            grid[(int(math.floor(pos[i][0] / cell)), int(math.floor(pos[i][1] / cell)))].append(i)
        for (gx, gy), members in grid.items():
            near = []
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    near.extend(grid.get((gx + dx, gy + dy), ()))
            for a in members:
                pa = pos[a]
                for b in near:
                    if b <= a:
                        continue
                    pb = pos[b]
                    dx_, dy_ = pa[0] - pb[0], pa[1] - pb[1]
                    d2 = dx_ * dx_ + dy_ * dy_
                    if d2 > cell * cell:
                        continue
                    if d2 < 1e-12:
                        dx_, dy_, d2 = 1e-4 * (1 if a < b else -1), 1e-4, 2e-8
                    d = math.sqrt(d2)
                    f = ideal * ideal / d
                    ux, uy = dx_ / d, dy_ / d
                    disp[a][0] += ux * f
                    disp[a][1] += uy * f
                    disp[b][0] -= ux * f
                    disp[b][1] -= uy * f
        # attraction along edges
        for (a, b), w in edge_list:
            pa, pb = pos[a], pos[b]
            dx_, dy_ = pa[0] - pb[0], pa[1] - pb[1]
            d = math.sqrt(dx_ * dx_ + dy_ * dy_) or 1e-6
            f = (d * d / ideal) * min(w, 4.0) * 0.18
            ux, uy = dx_ / d, dy_ / d
            disp[a][0] -= ux * f
            disp[a][1] -= uy * f
            disp[b][0] += ux * f
            disp[b][1] += uy * f
        # pull to the cluster centre and gently to the middle
        for i in ids:
            cx, cy = centres[main[i]]
            disp[i][0] += (cx - pos[i][0]) * 0.9 * ideal * 4 - pos[i][0] * ideal * 0.5
            disp[i][1] += (cy - pos[i][1]) * 0.9 * ideal * 4 - pos[i][1] * ideal * 0.5
        for i in ids:
            dx_, dy_ = disp[i]
            d = math.sqrt(dx_ * dx_ + dy_ * dy_)
            if d > 0:
                step = min(d, temp)
                pos[i][0] += dx_ / d * step
                pos[i][1] += dy_ / d * step
        temp = max(0.002, temp * 0.975)

    _separate(pos, ids, ideal * 0.55)
    # normalise into [0.05, 0.95] keeping the aspect ratio
    xs = [pos[i][0] for i in ids]
    ys = [pos[i][1] for i in ids]
    span = max(max(xs) - min(xs), max(ys) - min(ys)) or 1.0
    ox = (min(xs) + max(xs)) / 2
    oy = (min(ys) + max(ys)) / 2
    out = {}
    for i in ids:
        x = 0.5 + (pos[i][0] - ox) / span * 0.9
        y = 0.5 + (pos[i][1] - oy) / span * 0.9
        out[i] = (round(x, 4), round(y, 4))
    return out


def _separate(pos, ids, min_d, rounds=40):
    """Push apart any two nodes closer than ``min_d`` (a few passes)."""
    for _ in range(rounds):
        moved = False
        grid = defaultdict(list)
        for i in ids:
            grid[(int(math.floor(pos[i][0] / min_d)), int(math.floor(pos[i][1] / min_d)))].append(i)
        for (gx, gy), members in sorted(grid.items()):
            for a in members:
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        for b in grid.get((gx + dx, gy + dy), ()):
                            if b <= a:
                                continue
                            pa, pb = pos[a], pos[b]
                            ddx, ddy = pb[0] - pa[0], pb[1] - pa[1]
                            d = math.sqrt(ddx * ddx + ddy * ddy)
                            if d >= min_d:
                                continue
                            if d < 1e-9:
                                ddx, ddy, d = 1.0, 0.0, 1.0
                                push = min_d / 2
                            else:
                                push = (min_d - d) / 2
                            ux, uy = ddx / d, ddy / d
                            pa[0] -= ux * push
                            pa[1] -= uy * push
                            pb[0] += ux * push
                            pb[1] += uy * push
                            moved = True
        if not moved:
            break
