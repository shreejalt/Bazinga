"""Geometry checks for laid-out diagrams (used by tests/test_diagram_layout.py)."""
from tessera import draw


def _hit(a, b, pad=0.0):
    return a[0] < b[2] - pad and b[0] < a[2] - pad and a[1] < b[3] - pad and b[1] < a[3] - pad


def _rect(box):
    x, y, w, h = box
    return (x, y, x + w, y + h)


def _seg_rect(p, q, r, shrink):
    x0, y0, x1, y1 = r[0] + shrink, r[1] + shrink, r[2] - shrink, r[3] - shrink
    if x0 >= x1 or y0 >= y1:
        return False
    sx0, sx1 = min(p[0], q[0]), max(p[0], q[0])
    sy0, sy1 = min(p[1], q[1]), max(p[1], q[1])
    return sx0 < x1 and x0 < sx1 + 1e-9 and sy0 < y1 and y0 < sy1 + 1e-9 and not (sx1 <= x0 or sx0 >= x1 or sy1 <= y0 or sy0 >= y1)


def problems(d):
    """Plain-English list of what is wrong with a laid-out flow diagram (empty when it is clean)."""
    info = d.layout_info
    out = []
    boxes = {k: _rect(v) for k, v in info["boxes"].items()}
    groups = {k: _rect(v) for k, v in info["groups"].items()}
    names = list(boxes)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if _hit(boxes[a], boxes[b]):
                out.append("boxes %r and %r overlap" % (a, b))

    def subtree(gname):
        res = set()
        for m in info["members"].get(gname, []):
            res.add(m)
            res |= subtree(m)
        return res

    for gname, gr in groups.items():
        inside = subtree(gname)
        for m in inside:
            r = boxes.get(m) or groups.get(m)
            if r and not (r[0] >= gr[0] - 0.5 and r[1] >= gr[1] - 0.5 and r[2] <= gr[2] + 0.5 and r[3] <= gr[3] + 0.5):
                out.append("%r sticks out of its group %r" % (m, gname))
        for other, r in list(boxes.items()) + list(groups.items()):
            if other == gname or other in inside:
                continue
            if gname in subtree(other):
                continue                                   # an enclosing group
            if _hit(r, gr):
                out.append("%r overlaps the group %r it is not in" % (other, gname))
    for a, b, pts in info["routes"]:
        for p, q in zip(pts, pts[1:]):
            if abs(p[0] - q[0]) > 0.05 and abs(p[1] - q[1]) > 0.05 and a != b:
                out.append("arrow %s -> %s has a slanted piece %r-%r" % (a, b, p, q))
        for k, (p, q) in enumerate(zip(pts, pts[1:])):
            for name, r in boxes.items():
                ends = name in (a, b)
                if ends and (k == 0 or k == len(pts) - 2):
                    if info["shapes"][name] in ("circle", "diamond"):
                        continue
                if _seg_rect(p, q, r, 1.5 if not ends else 2.5):
                    out.append("arrow %s -> %s runs through %r" % (a, b, name))
    segs = []
    for a, b, pts in info["routes"]:
        for p, q in zip(pts, pts[1:]):
            segs.append((a, b, p, q))
    for i, (a1, b1, p1, q1) in enumerate(segs):
        for a2, b2, p2, q2 in segs[i + 1:]:
            if a1 == a2 or b1 == b2 or (a1, b1) == (b2, a2):
                continue
            if abs(p1[1] - q1[1]) < 0.05 and abs(p2[1] - q2[1]) < 0.05 and abs(p1[1] - p2[1]) < 0.05:
                lo, hi = max(min(p1[0], q1[0]), min(p2[0], q2[0])), min(max(p1[0], q1[0]), max(p2[0], q2[0]))
            elif abs(p1[0] - q1[0]) < 0.05 and abs(p2[0] - q2[0]) < 0.05 and abs(p1[0] - p2[0]) < 0.05:
                lo, hi = max(min(p1[1], q1[1]), min(p2[1], q2[1])), min(max(p1[1], q1[1]), max(p2[1], q2[1]))
            else:
                continue
            if hi - lo > 1:
                out.append("arrows %s -> %s and %s -> %s run on top of each other" % (a1, b1, a2, b2))
    placed = []
    for text, at in info["labels"]:
        w, h = draw.mono_width(text, 12) + 10, 18
        lr = (at[0] - w / 2, at[1] - h / 2, at[0] + w / 2, at[1] + h / 2)
        for name, r in boxes.items():
            if _hit(lr, r, 0.5):
                out.append("the label %r covers %r" % (text, name))
        for other, orect in placed:
            if _hit(lr, orect, 0.5):
                out.append("the labels %r and %r overlap" % (text, other))
        placed.append((text, lr))
    return out
