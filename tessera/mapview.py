"""How the work connects, as the map and the Connections block draw it.

Every page (of every kind), the references they cite and the topics they share form one graph. This module answers
the questions the theme asks about it:

    layout()        the whole map: every page in one forest of boxes, each below what it builds on
    view()          what sits around one page
      related       what else is most like it      (nearest first)
      path          what to read before and after  (along "builds on", nothing before what it rests on)
    view_on_map()   view() plus the motion the map plays on hover: rings nearest first, then the reading order walk
    neighbors()     what one page builds on, cites or links to, and what points back at it (the Connections figure)
    links_figure()  that, drawn as SVG (a wide and a phone version)
    trail()         the chain from the root of a page's tree down to it
    suggest()       the pages most like one by topic, rarest shared topic first
    find_series(), series_between(), series_for_tag()   reading orders found in the map

Standard library only: it runs at build time and is also shipped to the browser (``/figures/_mapview.py``), where the
Explore page calls the series functions.

Input shape (``graph_data`` in build.py makes it):
    {"items":  [{"id": "read:attention", "type": "read" | "paper" | "proj" | "ext", "title": …, "short": …,
                 "topics": [slug], "cites": ["ref:KEY" or a page id], "links": [ids it builds on],
                 "mentions": [ids linked in the text], "series": name or None, "part": n or None}],
     "refs":   {"KEY": {"title": …}},            cited papers with no write-up on the site
     "topics": {"slug": {"title": …, "group": …}}}
"""
import html as _html
import math
from collections import deque

TYPES = ("read", "paper", "proj", "ext")          # the content types, in the order the site lists them
RANK = {"read": 0, "paper": 1, "proj": 2, "ext": 3, "topic": 4, "ref": 5}
CONTENT = TYPES


def build(data):
    nodes, adj, pre = {}, {}, {}

    def add(i, **kw):
        if i not in nodes:
            nodes[i] = dict(id=i, order=len(nodes), **kw)
            adj[i] = set()
            pre[i] = []

    def link(a, b):
        if a in nodes and b in nodes and a != b:
            adj[a].add(b)
            adj[b].add(a)

    for item in items(data):
        add(item["id"], type=item.get("type", "read"), title=item["title"], series=item.get("series"),
            part=item.get("part"))
    for key, ref in (data.get("refs") or {}).items():
        add("ref:" + key, type="ref", title=ref["title"])
    for slug, t in (data.get("topics") or {}).items():
        add("topic:" + slug, type="topic", title=t["title"], group=t.get("group", ""))

    for item in items(data):
        a = item["id"]
        for t in item.get("topics", []):
            add("topic:" + t, type="topic", title=t, group="")
            link(a, "topic:" + t)
        for c in item.get("cites", []):
            link(a, c)
        for m in item.get("mentions", []):      # a [[link]] in the body
            link(a, m)
        for b in item.get("links", []):         # "a builds on b"
            link(a, b)
            if b in nodes and b != a and b not in pre[a]:
                pre[a].append(b)
    for i in list(nodes):                        # a topic nothing uses is not on the map
        if nodes[i]["type"] == "topic" and not adj[i]:
            del nodes[i], adj[i], pre[i]
    return nodes, adj, pre


def items(data):
    return list(data.get("items") or [])


def order_key(nodes):
    """One ordering used everywhere: by kind, then in the order the site lists things."""
    def key(i):
        return (RANK.get(nodes[i]["type"], 9), nodes[i]["order"], i)
    return key


def distances(adj, start, key):
    """Breadth-first: how many links away everything is."""
    dist, q = {start: 0}, deque([start])
    while q:
        u = q.popleft()
        for v in sorted(adj[u], key=key):
            if v not in dist:
                dist[v] = dist[u] + 1
                q.append(v)
    return dist


def related(nodes, adj, pre, start, dist, key, limit=6, nodes_mentions=None):
    """Nearest pages first; ties broken by how specific the shared topics and papers are."""
    nodes_mentions = nodes_mentions or {}
    out = []
    for v, d in dist.items():
        if v == start or nodes[v]["type"] not in CONTENT:
            continue
        shared = sorted(adj[start] & adj[v], key=key)
        same_series = nodes[v].get("series") and nodes[v].get("series") == nodes[start].get("series")
        if v in pre[start]:
            why = "this builds on it" + (" (earlier in the series)" if same_series else "")
        elif start in pre[v]:
            why = "builds on this" + (" (next in the series)" if same_series else "")
        elif same_series:
            why = "same series: " + nodes[v]["series"]
        elif v in adj[start] and nodes[start]["type"] == "topic":
            why = "tagged with this"
        elif v in adj[start] and nodes[start]["type"] == "ref":
            why = "cites this paper"
        elif v in (nodes_mentions.get(start) or ()):
            why = "linked from the text"
        elif start in (nodes_mentions.get(v) or ()):
            why = "links to this"
        elif v in adj[start] and nodes[v]["type"] == "paper" and nodes[start]["type"] in CONTENT:
            why = "explains a paper this cites"
        elif v in adj[start] and nodes[start]["type"] == "paper" and nodes[v]["type"] in CONTENT:
            why = "cites the paper explained here"
        elif shared:
            rare_first = sorted(shared, key=lambda x: (len(adj[x]), key(x)))
            topics = [nodes[x]["title"] for x in rare_first if nodes[x]["type"] == "topic"]
            papers = [x for x in rare_first if nodes[x]["type"] in ("ref", "paper")]
            bits = []
            if topics:
                bits.append("same tag: " + ", ".join(topics[:2]))
            if papers:
                bits.append("cites the same paper")
            why = "; ".join(bits) or "closely linked"
        elif nodes[start]["type"] in CONTENT:
            why = "one step further out"
        else:
            continue                  # for a topic or a reference, list only what is actually on it
        direct = 0 if (v in adj[start]) else 1
        # a shared niche topic says more than a shared broad one: each shared thing counts 1 / (how many items have it)
        closeness = sum(1.0 / len(adj[x]) for x in shared)
        out.append((direct, d, -closeness, key(v), dict(nodes[v], why=why)))
    out.sort(key=lambda t: t[:4])
    strong = [t for t in out if t[4]["why"] != "one step further out"]
    if len(strong) >= 3:              # enough real connections: leave the distant ones out
        out = strong
    return [t[4] for t in out[:limit]]


def reading_walk(nodes, pre, start, key):
    """Depth-first along "builds on", as one continuous walk over the lines of the map.

    Up first: from the page to each thing it builds on, recursively, so the deepest foundation is numbered first and
    everything is numbered on the way back down. Then down: into everything that builds on the page, child by child;
    before a child is numbered, the walk detours up to any prerequisite of it that is still unnumbered, so nothing is
    listed before something it builds on.

    Returns the order (ids) and the moves: (parent, child, down) for every line travelled, with a "stamp" move
    (id, None, None) each time a page is numbered."""
    nxt = {i: [] for i in nodes}
    for a, bs in pre.items():
        for b in bs:
            nxt[b].append(a)
    order, moves, seen = [], [], {start}

    def stamp(i):
        order.append(i)
        moves.append((i, None, None))

    def up(u):
        for v in sorted(pre[u], key=key):
            if v not in seen:
                seen.add(v)
                moves.append((v, u, False))
                up(v)
                stamp(v)
                moves.append((v, u, True))

    up(start)
    stamp(start)

    later, stack = set(), [start]
    while stack:
        u = stack.pop()
        for v in nxt[u]:
            if v not in seen and v not in later:
                later.add(v)
                stack.append(v)
    placed, visited = set(), set()

    def need(u):
        for v in sorted(pre[u], key=key):
            if v in later and v not in placed:
                placed.add(v)
                moves.append((v, u, False))
                need(v)
                stamp(v)
                moves.append((v, u, True))

    def down(u):
        for c in sorted(nxt[u], key=key):
            if c in later and c not in visited:
                visited.add(c)
                moves.append((u, c, True))
                if c not in placed:
                    placed.add(c)
                    need(c)
                    stamp(c)
                down(c)
                moves.append((u, c, False))

    down(start)
    return order, moves


def reading_path(nodes, pre, start, fallback, key):
    """The reading order through a page: before it, everything it rests on, deepest foundation first; after it,
    everything that rests on it."""
    order, _ = reading_walk(nodes, pre, start, key)
    here = order.index(start)
    path = [dict(nodes[i], role="before") for i in order[:here]] + [dict(nodes[start], role="here")] + \
           [dict(nodes[i], role="after") for i in order[here + 1:]]
    if len(path) == 1:                # nothing builds on anything here: suggest the nearest work
        path += [dict({k: r[k] for k in ("id", "type", "title")}, role="also") for r in fallback[:3]]
    return path


def choreograph(data, start, layout, step=700, speed=380, pause=320, rest=600, reach=2):
    """The two searches as motion on the map, timed in milliseconds, for the page to play on hover.

    wave  - nearest first: every page within two links (a curve, a citation or a link in the text) is reached at
            (links away) x step; a curve that joins distance d to d+1 is drawn from its nearer end in that interval.
    walk  - after the wave has settled, one dot walks the curves in the reading order, at a steady speed (faster
            when the walk is long, so the travel takes about six seconds at most), pausing where it numbers a page."""
    nodes, adj, pre = build(data)
    key = order_key(nodes)
    if start not in nodes:
        return None
    firm = {i: {v for v in adj[i] if nodes[v]["type"] != "topic"} for i in adj}
    dist = distances(firm, start, key)
    pos = {n["id"]: n for n in layout["nodes"]}
    route = {(e["a"], e["b"]): e["pts"] for e in layout["edges"]}

    wave = dict(step=step, reach=reach, nodes=[], edges=[])
    for i, d in dist.items():
        if i in pos and d <= reach:
            wave["nodes"].append(dict(id=i, d=d, t=d * step))
    for e in layout["edges"]:
        da, db = dist.get(e["a"]), dist.get(e["b"])
        if da is None or db is None or max(da, db) > reach or abs(da - db) != 1:
            continue
        near = e["a"] if da < db else e["b"]
        wave["edges"].append(dict(a=e["a"], b=e["b"], src=near, t0=min(da, db) * step,
                                  t1=min(da, db) * step + step))

    def length(pts):
        return sum(math.hypot(x1 - x0, y1 - y0) for (x0, y0), (x1, y1) in zip(pts, pts[1:]))

    order, moves = reading_walk(nodes, pre, start, key)
    total = sum(length(route[(a, b)]) for a, b, down in moves if b is not None and (a, b) in route)
    speed = max(speed, total / 6.0)
    pause = min(pause, 2400.0 / max(1, len(order)))
    floor = min(260.0, 5000.0 / max(1, sum(1 for m in moves if m[1] is not None)))
    begin = (max(w["d"] for w in wave["nodes"]) + 1) * step + rest if wave["nodes"] else 0
    t, steps, stamps, drawn, path, travelled = float(begin), [], [], set(), [], 0.0
    for a, b, down in moves:
        if b is None:
            stamps.append(dict(id=a, n=order.index(a) + 1, t=round(t)))
            t += pause
            continue
        pts = route.get((a, b))
        if not pts:
            continue
        pts = pts if down else pts[::-1]
        if path:
            travelled += math.hypot(pts[0][0] - path[-1][0], pts[0][1] - path[-1][1])
        L = length(pts)
        dur = max(floor, L / speed * 1000)
        steps.append(dict(a=a, b=b, down=down, t0=round(t), t1=round(t + dur), s0=round(travelled, 1),
                          s1=round(travelled + L, 1), first=(a, b) not in drawn))
        drawn.add((a, b))
        path.extend(pts if not path or tuple(pts[0]) != tuple(path[-1]) else pts[1:])
        travelled += L
        t += dur
    return dict(wave=wave, walk=dict(start=begin, steps=steps, stamps=stamps, path=path, length=round(travelled, 1),
                                     duration=round(t)), order=order)


def view_on_map(data, start, layout):
    """What a hover needs: the view (related, reading order, rings) plus the motion that explains it on the map."""
    v = view(data, start)
    v["motion"] = choreograph(data, v["start"], layout)
    return v


def view(data, start, cap=8):
    nodes, adj, pre = build(data)
    key = order_key(nodes)
    if not nodes:
        return {"start": start, "item": None, "related": [], "path": [], "rings": {}}
    if start not in nodes:
        start = sorted(nodes, key=key)[0]
    dist = distances(adj, start, key)
    mentions = {item["id"]: set(item.get("mentions", [])) for item in items(data)}
    rel = related(nodes, adj, pre, start, dist, key, limit=6 if nodes[start]["type"] in CONTENT else 12,
                  nodes_mentions=mentions)
    return {
        "start": start,
        "item": nodes[start],
        "related": rel,
        "path": reading_path(nodes, pre, start, rel, key),
        "rings": {i: d for i, d in dist.items() if nodes[i]["type"] in CONTENT and 0 < d <= 4},
    }


BOX_W, BOX_H = 136, 50      # one box: a kind label and a title of up to two lines
GX, GY, GH, SP, GT = 10, 46, 12, 26, 48   # between siblings, between rows, between hung leaves, across a spine, trees
CHARS = 18                   # characters of title per line at the box's font


def wrap_label(text, chars=CHARS, lines=2):
    """A title broken into at most `lines` lines of about `chars` characters; the last is cut with an ellipsis."""
    out = [""]
    for w in text.split():
        if out[-1] and len(out[-1]) + 1 + len(w) > chars:
            out.append(w)
        else:
            out[-1] = (out[-1] + " " + w).strip()
    if len(out) > lines:
        out = out[:lines]
        out[-1] = out[-1][:chars - 1].rstrip() + "…"
    return out


def layout(data, width=1100):
    """The map: every page in one forest of boxes, each below what it builds on.

    Levels come from the longest "builds on" chain above each page. A page hangs from its deepest parent; its other
    parents reach it with a lighter curve. Pages with no "builds on" link at all hang from the page they share the
    most specific topics with, on a dotted curve, so nothing floats. Under each page, children that have children of
    their own stand in a row; two or more childless ones hang from one spine. Each tree is laid out as a block (a
    parent centred over its children), and the trees are set on shelves across the width, tallest first."""
    nodes, adj, pre = build(data)
    key = order_key(nodes)
    content = sorted((i for i in nodes if nodes[i]["type"] in CONTENT), key=key)
    cset = set(content)
    level, state = {}, {}

    def depth(i):
        if i in level:
            return level[i]
        if state.get(i) == 1:                  # a cycle in the content: break it here
            return 0
        state[i] = 1
        level[i] = 1 + max((depth(b) for b in pre[i] if b in cset), default=-1)
        state[i] = 2
        return level[i]

    for i in content:
        depth(i)

    parent, how = {}, {}
    for i in content:
        ups = [b for b in pre[i] if b in cset and level[b] < level[i]]
        if ups:
            parent[i] = max(ups, key=lambda b: (level[b], -content.index(b)))
            how[i] = "builds"
    linked = {i for i in content if any(b in cset for b in pre[i])} | {b for i in content for b in pre[i] if b in cset}
    for i in content:
        if i in linked:
            continue
        best, score = None, 0.0
        for j in sorted(linked, key=key):
            shared = sum(1.0 / len(adj[t]) for t in adj[i] & adj[j] if nodes[t]["type"] in ("topic", "ref", "paper"))
            if shared > score:
                best, score = j, shared
        if best:
            parent[i], how[i] = best, "tag"
            level[i] = level[best] + 1
    kids = {i: [] for i in content}
    for i, p in parent.items():
        kids[p].append(i)
    out, edges = [], []

    def put(i, x, y):
        short = data_short(data, i)
        out.append(dict(id=i, type=nodes[i]["type"], label=short, lines=wrap_label(short),
                        level=level[i], x=round(x, 1), y=round(y, 1), w=BOX_W, h=BOX_H))

    def pack(A, B):
        shift = 0.0
        for (i, ax, ay, aw, ah) in A:
            for (j, bx, by, bw, bh) in B:
                if ay < by + bh + GY and by < ay + ah + GY:
                    shift = max(shift, ax + aw + GX - bx)
        return shift

    def move(segs, dx, dy):
        return [tuple(s if n == 0 or not isinstance(s, tuple) else (s[0] + dx, s[1] + dy) for n, s in enumerate(seg))
                for seg in segs]

    def hung(u, leaves):
        cols = 2 if len(leaves) > 4 else 1
        bx, cv = [], []
        for k, i in enumerate(leaves):
            left = cols == 2 and k % 2 == 0
            lx = -BOX_W - SP / 2 if left else SP / 2
            ly = (k // cols) * (BOX_H + GH)
            mid = ly + BOX_H / 2
            bx.append((i, lx, ly, BOX_W, BOX_H))
            cv.append((u, i, [("L", (0, mid - SP / 2)), ("A", SP / 2, 1 if left else 0, (-SP / 2 if left else SP / 2, mid))]))
        if cols == 1:
            bx.append((None, -1.0, 0.0, 1.0, bx[-1][2] + BOX_H / 2))
        return bx, cv, (BOX_W + SP / 2) / 2 if cols == 1 else 0.0

    def subtree(u):
        br = [c for c in kids[u] if kids[c]]
        lf = [c for c in kids[u] if not kids[c]]
        hang = lf if len(lf) >= 2 else []
        row = [subtree(c) + (0.0,) for c in br + ([] if hang else lf)]
        if hang:
            row.append(hung(u, hang))
        boxes, curves, placed, roots = [(u, -BOX_W / 2, 0.0, BOX_W, BOX_H)], [], [], []
        for bx, cv, off in row:
            dy = BOX_H + GY
            dx = pack(placed, [(i, x, y + dy, w, h) for i, x, y, w, h in bx]) if placed else 0.0
            placed += [(i, x + dx, y + dy, w, h) for i, x, y, w, h in bx]
            down = [("M", (0, BOX_H)), ("C", (0, BOX_H + GY / 2), (dx, BOX_H + GY / 2), (dx, dy))]
            if cv and cv[0][0] == u:
                curves += [(a, b, down + move(segs, dx, dy)) for a, b, segs in cv]
            else:
                curves += [(u, bx[0][0], down)] + [(a, b, move(segs, dx, dy)) for a, b, segs in cv]
            roots.append(dx + off)
        if roots:
            mid = (roots[0] + roots[-1]) / 2
            placed = [(i, x - mid, y, w, h) for i, x, y, w, h in placed]
            curves = [(a, b, ([("M", (0, BOX_H))] + move(segs, -mid, 0)[1:]) if a == u else move(segs, -mid, 0))
                      for a, b, segs in curves]
        return boxes + placed, curves

    comp = {i: i for i in content}

    def find(i):
        while comp[i] != i:
            comp[i] = comp[comp[i]]
            i = comp[i]
        return i

    for i in content:
        for b in pre[i]:
            if b in cset:
                comp[find(i)] = find(b)
    groups, alone = {}, []
    for i in content:
        if i in parent:
            continue
        if not kids[i] and i not in linked:
            alone.append((i, len(alone) * (BOX_W + GX) - BOX_W / 2, 0.0, BOX_W, BOX_H))
            continue
        groups.setdefault(find(i), []).append(subtree(i))
    trees = []
    for roots in groups.values():
        bx, cv = [], []
        for tb, tc in roots:
            dx = pack(bx, tb) if bx else 0.0
            bx += [(i, x + dx, y, w, h) for i, x, y, w, h in tb]
            cv += [(a, b, move(segs, dx, 0)) for a, b, segs in tc]
        lo, hi = min(x for _, x, _, _, _ in bx), max(x + w for _, x, _, w, _ in bx)
        trees.append((bx, cv, lo, hi, max(y + h for _, _, y, _, h in bx)))
    trees.sort(key=lambda t: (-t[4], -(t[3] - t[2]), content.index(t[0][0][0])))
    if alone:
        trees.append((alone, [], -BOX_W / 2, alone[-1][1] + BOX_W, BOX_H))
    pitch = BOX_H + GY
    for bx, cv, lo, hi, h in trees:
        w = hi - lo
        x = None
        for y in range(12, 12 + pitch * (len(content) + 1), pitch):
            near = [n for n in out if n["y"] < y + h + GT and y < n["y"] + n["h"] + GT]
            x = None
            for cand in sorted([6] + [n["x"] + n["w"] + GT for n in near]):
                if cand + w <= width - 6 and not any(n["x"] < cand + w + GT and cand < n["x"] + n["w"] + GT for n in near):
                    x = cand
                    break
            if x is not None:
                break
        if x is None:
            x, y = 6, (max(n["y"] + n["h"] for n in out) + GT) if out else 12
        x0 = x - lo
        for i, bx_, by_, w_, h_ in bx:
            if i is not None:
                put(i, x0 + bx_, y + by_)
        for a, b, segs in cv:
            edges.append(_edge(a, b, how[b], move(segs, x0, y)))
    pos = {n["id"]: n for n in out}
    for i in content:
        for b in pre[i]:
            if b in cset and parent.get(i) != b:
                A, B = pos[b], pos[i]
                x0, y0, x1, y1 = A["x"] + BOX_W / 2, A["y"] + BOX_H, B["x"] + BOX_W / 2, B["y"]
                dy = max(40.0, abs(y1 - y0) / 2)
                edges.append(_edge(b, i, "also", [("M", (x0, y0)), ("C", (x0, y0 + dy), (x1, y1 - dy), (x1, y1))]))
    return {"nodes": out, "edges": edges, "width": max(width, max(n["x"] + BOX_W for n in out) + 6) if out else width,
            "height": (max(n["y"] + BOX_H for n in out) + 14) if out else 0,
            "levels": max(level.values()) + 1 if level else 0}


def _edge(a, b, kind, segs):
    pts = _sample(segs)
    return dict(a=a, b=b, kind=kind, d=_path(segs), rd=_path(_reverse(segs)),
                pts=[[round(x, 1), round(y, 1)] for x, y in pts])


def _path(segs):
    s = []
    for seg in segs:
        if seg[0] == "A":
            s.append("A%g %g 0 0 %d %g %g" % (seg[1], seg[1], seg[2], seg[3][0], seg[3][1]))
        else:
            s.append(seg[0] + " ".join("%g %g" % p for p in seg[1:]))
    return "".join(s)


def _reverse(segs):
    ends = [seg[-1] for seg in segs]
    out = [("M", ends[-1])]
    for k in range(len(segs) - 1, 0, -1):
        seg, p = segs[k], ends[k - 1]
        if seg[0] == "C":
            out.append(("C", seg[2], seg[1], p))
        elif seg[0] == "A":
            out.append(("A", seg[1], 1 - seg[2], p))
        else:
            out.append(("L", p))
    return out


def _sample(segs, n=14):
    pts, cur = [], None
    for seg in segs:
        if seg[0] in ("M", "L"):
            cur = seg[1]
            pts.append(cur)
        elif seg[0] == "C":
            (x0, y0), (x1, y1), (x2, y2), (x3, y3) = cur, seg[1], seg[2], seg[3]
            for k in range(1, n + 1):
                t = k / n
                u = 1 - t
                pts.append((u ** 3 * x0 + 3 * u * u * t * x1 + 3 * u * t * t * x2 + t ** 3 * x3,
                            u ** 3 * y0 + 3 * u * u * t * y1 + 3 * u * t * t * y2 + t ** 3 * y3))
            cur = (x3, y3)
        else:
            (x0, y0), r, sweep, (x3, y3) = cur, seg[1], seg[2], seg[3]
            cx, cy = x3, y0
            a0, a1 = math.atan2(y0 - cy, x0 - cx), math.atan2(y3 - cy, x3 - cx)
            if sweep and a1 < a0:
                a1 += 2 * math.pi
            if not sweep and a1 > a0:
                a1 -= 2 * math.pi
            for k in range(1, 7):
                a = a0 + (a1 - a0) * k / 6
                pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
            cur = (x3, y3)
    return pts


def data_short(data, i):
    for item in items(data):
        if item["id"] == i:
            return item.get("short") or item["title"]
    return i


def neighbors(data, node):
    """What one page builds on, cites or links to, and what builds on, cites or links to it.

    Each entry carries `how`: "builds", "cites" or "mentions"; a page reached several ways keeps the strongest."""
    nodes, _, _ = build(data)
    rank = {"builds": 0, "cites": 1, "mentions": 2}
    out, inn = {}, {}

    def add(bucket, i, how):
        if i in nodes and (i not in bucket or rank[how] < rank[bucket[i]]):
            bucket[i] = how

    for item in items(data):
        ways = [(b, "builds") for b in item.get("links", [])] + [(c, "cites") for c in item.get("cites", [])] + \
               [(m, "mentions") for m in item.get("mentions", [])]
        if item["id"] == node:
            for i, how in ways:
                add(out, i, how)
        else:
            for i, how in ways:
                if i == node:
                    add(inn, item["id"], how)
    key = order_key(nodes)

    def pack(bucket):
        return [dict(nodes[i], how=bucket[i]) for i in sorted(bucket, key=lambda i: (rank[bucket[i]], key(i)))]
    return {"node": node, "out": pack(out), "in": pack(inn)}


def trail(data, start):
    """Where a page sits: the chain from the root of its tree down to its parent, following the deepest parent at
    each step (the same choice layout() makes when it hangs the page)."""
    nodes, adj, pre = build(data)
    if start not in nodes:
        return []
    memo = {}

    def depth(i, seen=()):
        if i in memo:
            return memo[i]
        memo[i] = 1 + max([depth(b, seen + (i,)) for b in pre[i] if b not in seen] or [-1])
        return memo[i]

    out, i = [], start
    while pre[i]:
        i = max(pre[i], key=lambda b: (depth(b), -nodes[b]["order"]))
        if i in out or i == start:
            break
        out.append(i)
    out.reverse()
    return out


def suggest(data, start, limit=5):
    """The pages most like one by topic, rarest shared topic counting most."""
    nodes, adj, _ = build(data)
    if start not in nodes:
        return []
    key = order_key(nodes)
    scored = []
    for v in nodes:
        if v == start or nodes[v]["type"] not in CONTENT:
            continue
        shared = [t for t in adj[start] & adj[v] if nodes[t]["type"] == "topic"]
        if shared:
            score = sum(1.0 / len(adj[t]) for t in shared)
            scored.append((-score, key(v), dict(nodes[v], score=round(score, 3),
                                                shared=sorted(nodes[t]["title"] for t in shared))))
    scored.sort(key=lambda t: t[:2])
    return [t[2] for t in scored[:limit]]


def _chain_graph(data):
    nodes, adj, pre = build(data)
    content = [i for i in nodes if nodes[i]["type"] in CONTENT]
    kids = {i: [] for i in content}
    for a in content:
        for b in pre[a]:
            if b in kids:
                kids[b].append(a)
    order, seen = [], set()

    def visit(u):
        if u in seen:
            return
        seen.add(u)
        for b in pre[u]:
            if b in kids:
                visit(b)
        order.append(u)

    key = order_key(nodes)
    for i in sorted(content, key=key):
        visit(i)
    return nodes, pre, kids, order, key


def _name_for(nodes, adj, ids, data):
    names = {nodes[i].get("series") for i in ids}
    if len(names) == 1 and None not in names:
        return names.pop()
    count = {}
    for i in ids:
        for t in adj[i]:
            if nodes[t]["type"] == "topic":
                count[t] = count.get(t, 0) + 1
    if not count:
        return "%s to %s" % (nodes[ids[0]]["title"], nodes[ids[-1]]["title"])
    best = max(count, key=lambda t: (count[t], -len(adj[t])))
    return nodes[best]["title"]


def find_series(data, minimum=3):
    """Series on the map: the declared ones first, then chains the map contains but nobody has declared."""
    nodes, pre, kids, order, key = _chain_graph(data)
    _, adj, _ = build(data)
    found, covered = [], set()
    declared = {}
    for u in order:
        if nodes[u].get("series"):
            declared.setdefault(nodes[u]["series"], []).append(u)
    for name in sorted(declared, key=lambda n: -len(declared[n])):
        ids = sorted(declared[name], key=lambda u: (nodes[u].get("part") or 0, key(u)))
        if len(ids) >= 2:
            s = _as_series(nodes, adj, ids, data)
            s["name"], s["declared"] = name, True
            found.append(s)
            covered |= set(ids)
    best, back = {}, {}
    for u in order:
        parents = [b for b in pre[u] if b in kids]
        if parents:
            p = max(parents, key=lambda b: (best[b], key(b)))
            best[u], back[u] = best[p] + 1, p
        else:
            best[u], back[u] = 1, None
    for end in sorted(order, key=lambda u: (-best[u], key(u))):
        if best[end] < minimum:
            break
        chain, u = [], end
        while u is not None:
            chain.append(u)
            u = back[u]
        chain.reverse()
        fresh = [i for i in chain if i not in covered]
        if len(fresh) < minimum or len(fresh) * 2 <= len(chain):
            continue
        covered |= set(chain)
        s = _as_series(nodes, adj, chain, data)
        s["declared"] = False
        found.append(s)
    return found


def series_between(data, start, end):
    """The longest "builds on" chain from `start` to `end`, so nothing on the way is skipped."""
    nodes, pre, kids, order, key = _chain_graph(data)
    _, adj, _ = build(data)
    if start not in kids or end not in kids:
        return None
    longest = []

    def walk(u, path):
        nonlocal longest
        if u == end:
            if len(path) > len(longest):
                longest = list(path)
            return
        for v in sorted(kids[u], key=key):
            if v not in path:
                path.append(v)
                walk(v, path)
                path.pop()

    walk(start, [start])
    return _as_series(nodes, adj, longest, data) if longest else None


def series_for_tag(data, tag):
    """Every page carrying a topic, in an order a reader can follow: parents before children along "builds on"."""
    nodes, pre, kids, order, key = _chain_graph(data)
    _, adj, _ = build(data)
    if "topic:" + tag not in nodes:
        return None
    tagged = [u for u in order if "topic:" + tag in adj[u]]
    if not tagged:
        return None
    s = _as_series(nodes, adj, tagged, data)
    s["name"] = nodes["topic:" + tag]["title"]
    for part in s["parts"]:
        needs = [b for b in pre[part["id"]] if b in kids and b not in tagged]
        part["read_first"] = [dict(id=b, title=nodes[b]["title"]) for b in sorted(needs, key=key)]
    return s


def _as_series(nodes, adj, ids, data):
    name = _name_for(nodes, adj, ids, data)
    parts = [dict(id=i, title=nodes[i]["title"], type=nodes[i]["type"], part=k + 1) for k, i in enumerate(ids)]
    slug = "".join(ch if ch.isalnum() else "-" for ch in name.lower()).strip("-")
    yaml = "\n".join('%s:  series: {name: "%s", part: %d}' % (i.ljust(34), name, k + 1) for k, i in enumerate(ids))
    return dict(name=name, slug=slug, ids=ids, parts=parts, length=len(ids), yaml=yaml)


# ------------------------------------------------------------------------------------- the Connections figure

def links_figure(neigh, labels):
    """What a page builds on, cites or links to, and what points back at it, as SVG: three columns the full width
    of the page (what points at this page, this page, what it points at), and the same stacked for phones.
    `labels` maps a type ("read", "paper", "proj", "ext", "ref") to its kind label. Colours come from the theme's
    CSS (classes t-<type>)."""
    W, BW, BH, STEP, TOP = 740, 214, 58, 72, 34
    left_x, right_x, mid_x = 0, W - BW, (W - 170) // 2
    esc = _html.escape

    def wrap(title, width=26):
        words, lines = title.split(), [""]
        for w in words:
            if len(lines[-1]) + len(w) + 1 > width and lines[-1]:
                lines.append(w)
            else:
                lines[-1] = (lines[-1] + " " + w).strip()
        if len(lines) > 3:
            lines = lines[:3]
            lines[2] = lines[2][:width - 1].rstrip() + "…"
        return [esc(x) for x in lines]

    def kind_line(o):
        how = {"builds": "", "cites": " · cited", "mentions": " · linked in the text"}[o.get("how", "builds")]
        return esc((labels.get(o["type"], o["type"]) + how).upper())

    rows = max(len(neigh["in"]), len(neigh["out"]), 1)
    H = TOP + rows * STEP
    mid_y = TOP + (rows * STEP - BH) / 2

    def ys(group):
        total = len(group) * STEP
        start = TOP + (rows * STEP - total) / 2
        return [start + k * STEP for k in range(len(group))]

    s, i = [], 0
    for y in ys(neigh["in"]):
        s.append('<path class="draw ln" style="--d:%dms" d="M%d %.0fC%d %.0f,%d %.0f,%d %.0f" fill="none"/>'
                 % (i * 120, BW, y + BH / 2, BW + 40, y + BH / 2, mid_x - 40, mid_y + BH / 2, mid_x, mid_y + BH / 2))
        i += 1
    for y in ys(neigh["out"]):
        s.append('<path class="draw ln" style="--d:%dms" d="M%d %.0fC%d %.0f,%d %.0f,%d %.0f" fill="none"/>'
                 % (i * 120, mid_x + 170, mid_y + BH / 2, mid_x + 210, mid_y + BH / 2, right_x - 40, y + BH / 2,
                    right_x, y + BH / 2))
        i += 1
    s.append('<rect class="me" x="%d" y="%.0f" width="170" height="%d"/><text class="me-t" x="%d" y="%.0f" '
             'text-anchor="middle" font-size="13" font-weight="700">This page</text>'
             % (mid_x, mid_y, BH, mid_x + 85, mid_y + BH / 2 + 4))
    s.append('<text class="hd" x="%d" y="14" font-size="10.5" text-anchor="start">POINTS AT THIS PAGE</text>' % left_x)
    s.append('<text class="hd" x="%d" y="14" font-size="10.5" text-anchor="end">THIS PAGE POINTS AT</text>'
             % (right_x + BW))
    for group, x in ((neigh["in"], left_x), (neigh["out"], right_x)):
        if not group:
            s.append('<text class="none" x="%d" y="%.0f" text-anchor="middle" font-size="12" font-style="italic">'
                     'nothing yet</text>' % (x + BW / 2, mid_y + BH / 2 + 4))
    k = 0
    for group, x in ((neigh["in"], left_x), (neigh["out"], right_x)):
        for o, y in zip(group, ys(group)):
            lines = wrap(o["title"])
            ty = y + 34 if len(lines) == 1 else (y + 29 if len(lines) == 2 else y + 25)
            dash = ' stroke-dasharray="4 3"' if o.get("how") == "mentions" else ""
            s.append('<a href="%s" data-x="%s" class="fadein bx t-%s%s" style="--d:%dms"><rect x="%d" y="%.0f" '
                     'width="%d" height="%d"%s/><text class="kd" x="%d" y="%.0f" text-anchor="middle" font-size="10" '
                     'letter-spacing=".08em">%s</text>%s</a>'
                     % (esc(o["url"]), esc(o["id"]), o["type"], " soft" if o.get("how") == "mentions" else "",
                        600 + k * 140, x, y, BW, BH, dash, x + BW / 2, y + 14, kind_line(o),
                        "".join('<text class="tt" x="%d" y="%.0f" text-anchor="middle" font-size="11.5" '
                                'font-weight="700">%s</text>' % (x + BW / 2, ty + n * 13, ln)
                                for n, ln in enumerate(lines))))
            k += 1
    m, y = [], 6

    def mbox(o, y):
        lines = wrap(o["title"], 40)
        ty = y + 34 if len(lines) == 1 else (y + 29 if len(lines) == 2 else y + 25)
        dash = ' stroke-dasharray="4 3"' if o.get("how") == "mentions" else ""
        return ('<a href="%s" data-x="%s" class="bx t-%s%s"><rect x="40" y="%d" width="280" height="%d"%s/>'
                '<text class="kd" x="180" y="%d" text-anchor="middle" font-size="10" letter-spacing=".08em">%s</text>'
                '%s</a>' % (esc(o["url"]), esc(o["id"]), o["type"], " soft" if o.get("how") == "mentions" else "",
                            y, BH, dash, y + 14, kind_line(o),
                            "".join('<text class="tt" x="180" y="%d" text-anchor="middle" font-size="11.5" '
                                    'font-weight="700">%s</text>' % (ty + n * 13, ln) for n, ln in enumerate(lines))))
    for label, group in (("POINTS AT THIS PAGE", neigh["in"]), ("THIS PAGE", None), ("THIS PAGE POINTS AT", neigh["out"])):
        if group is None:
            m.append('<rect class="me" x="95" y="%d" width="170" height="50"/><text class="me-t" x="180" y="%d" '
                     'text-anchor="middle" font-size="13" font-weight="700">This page</text>' % (y, y + 29))
            y += 50 + 22
            continue
        m.append('<text class="hd" x="180" y="%d" font-size="11" text-anchor="middle">%s</text>' % (y + 10, label))
        y += 22
        if not group:
            m.append('<text class="none" x="180" y="%d" text-anchor="middle" font-size="12" font-style="italic">'
                     'nothing yet</text>' % (y + 14))
            y += 30
        for o in group:
            m.append(mbox(o, y))
            m.append('<path class="ln" d="M180 %d v10"/>' % (y + BH))
            y += BH + 10
        y += 12
    aria = "What this page builds on and what builds on it"
    narrow = ('<svg class="links narrow" viewBox="0 0 360 %d" width="360" height="%d" role="img" aria-label="%s">%s'
              '</svg>' % (y, y, aria, "".join(m)))
    return (narrow + '<div class="tblwrap"><svg class="links wide" viewBox="0 0 %d %d" width="%d" height="%d" '
            'role="img" aria-label="%s">%s</svg></div>' % (W, H, W, H, aria, "".join(s)))
