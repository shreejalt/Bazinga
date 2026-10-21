"""Quick answers from the site's own passages.

Standard library only: this file runs at build time, in tests, in ``api/ask.py`` and in the reader's
browser (it is copied to ``_site/figures/_retrieve.py``). Keep it import-free beyond the stdlib.

``answer(question, passages, graph=None, page=None, k=6)`` ranks the passages with BM25, boosts the
current page and its neighbours on the map, adds a little for title and section matches, and returns
an extractive answer (the best two or three sentences) plus the pages it came from.
"""
import math
import re
import unicodedata

K1 = 1.2
B = 0.75
PAGE_BOOST = 1.6          # passages of the page the reader is on
NEIGHBOUR_BOOST = 1.25    # passages of pages one step away on the map
TITLE_BONUS = 0.35        # per query term found in the page title (scaled by idf share)
SECTION_BONUS = 0.25      # per query term found in the section heading
MAX_SENTENCES = 3

STOPWORDS = frozenset("""
a about above after again against all also am an and any are as at be because been before being below between both
but by can could did do does doing down during each few for from further had has have having he her here hers herself
him himself his how i if in into is it its itself just let me more most my myself no nor not now of off on once only
or other our ours ourselves out over own same she should so some such than that the their theirs them themselves then
there these they this those through to too under until up very was we were what when where which while who whom why
will with would you your yours yourself yourselves s t can't don't isn't it's i'm i've you're what's how's let's
there's here's does doesn't did didn't was wasn't were weren't via per vs etc eg ie e.g i.e
tell explain describe show give please mean means meaning work works
""".split())

_WORD = re.compile(r"[^\W_]+(?:['’][^\W_]+)?", re.UNICODE)
_SENT = re.compile(r"(?<=[.!?])[\"')\]]*\s+(?=[\"'(\[]?[A-Z0-9À-ɏ])")


def _fold(text):
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c)).lower()


def stem(w):
    """A light suffix stripper: plurals, -ing, -ed, -ly, -ies, and a final -e, so that "divide", "divides" and
    "divided" meet. Short words and numbers are left alone. Consistent rather than linguistically right."""
    if len(w) <= 3 or w.isdigit():
        return w
    if w.endswith("ies") and len(w) > 4:
        w = w[:-3] + "y"
    elif w.endswith("sses"):
        w = w[:-2]
    elif w.endswith("ing") and len(w) > 5:
        w = w[:-3]
        if len(w) > 3 and w[-1] == w[-2] and w[-1] not in "lsz":
            w = w[:-1]
    elif w.endswith("ed") and len(w) > 4 and not w.endswith("eed"):
        w = w[:-2]
        if len(w) > 3 and w[-1] == w[-2] and w[-1] not in "lsz":
            w = w[:-1]
    elif w.endswith("ly") and len(w) > 5:
        w = w[:-2]
    elif w.endswith("s") and not w.endswith(("ss", "us", "is")):
        w = w[:-1]
    if len(w) > 4 and w.endswith("e") and not w.endswith("ee"):
        w = w[:-1]
    return w


def tokenize(text, keep_stopwords=False):
    out = []
    for m in _WORD.finditer(_fold(text or "")):
        w = m.group(0).replace("’", "'")
        if w.endswith("'s"):
            w = w[:-2]
        if not keep_stopwords and (w in STOPWORDS or len(w) < 2 and not w.isdigit()):
            continue
        out.append(stem(w))
    return out


def sentences(text):
    parts = _SENT.split((text or "").strip())
    return [p.strip() for p in parts if p and p.strip()]


class Index:
    """BM25 statistics over a list of passages."""

    def __init__(self, passages):
        self.passages = passages
        self.docs = []
        self.df = {}
        self.titles = []
        self.sections = []
        total = 0
        for p in passages:
            body = (p.get("text") or "")
            toks = tokenize(body) + tokenize(p.get("section") or "")
            tf = {}
            for t in toks:
                tf[t] = tf.get(t, 0) + 1
            self.docs.append((tf, len(toks)))
            total += len(toks)
            for t in tf:
                self.df[t] = self.df.get(t, 0) + 1
            self.titles.append(set(tokenize(p.get("title") or "")))
            self.sections.append(set(tokenize(p.get("section") or "")))
        self.n = len(passages)
        self.avgdl = (total / self.n) if self.n else 1.0

    def idf(self, t):
        df = self.df.get(t, 0)
        return math.log(1 + (self.n - df + 0.5) / (df + 0.5))

    def scores(self, terms):
        out = []
        idf = {t: self.idf(t) for t in terms}
        idf_sum = sum(idf.values()) or 1.0
        for i, (tf, dl) in enumerate(self.docs):
            s = 0.0
            for t in terms:
                f = tf.get(t)
                if f:
                    s += idf[t] * f * (K1 + 1) / (f + K1 * (1 - B + B * dl / self.avgdl))
            if s > 0:
                # coordination: passages that contain more of the question's (weighted) words rank higher
                cover = sum(idf[t] for t in terms if t in tf) / idf_sum
                s *= 0.4 + 0.6 * cover
                tb = sum(idf[t] for t in terms if t in self.titles[i]) / idf_sum
                sb = sum(idf[t] for t in terms if t in self.sections[i]) / idf_sum
                s *= 1 + TITLE_BONUS * tb + SECTION_BONUS * sb
            out.append(s)
        return out


_CACHE = {"key": None, "index": None, "graph": None}


def _key(passages):
    if not passages:
        return (0,)
    return (len(passages), passages[0].get("id"), passages[0].get("anchor"), passages[-1].get("id"),
            passages[-1].get("anchor"), len(passages[-1].get("text") or ""))


def load(passages, graph=None):
    """Build and keep the index (the browser calls this once, then ``answer`` with ``passages=None``)."""
    _CACHE["key"] = _key(passages)
    _CACHE["index"] = Index(passages)
    _CACHE["graph"] = graph
    return {"count": len(passages)}


def _index_for(passages):
    if passages is None:
        if _CACHE["index"] is None:
            raise ValueError("no passages loaded")
        return _CACHE["index"]
    key = _key(passages)
    if _CACHE["key"] != key or _CACHE["index"] is None:
        _CACHE["key"] = key
        _CACHE["index"] = Index(passages)
    return _CACHE["index"]


def neighbours(graph, page):
    """Pages one step from ``page`` on the map (any edge type)."""
    out = set()
    if not graph or not page:
        return out
    rings = graph.get("rings") or {}
    r = rings.get(page)
    if isinstance(r, list) and r:
        out.update(r[0])
    elif isinstance(r, dict):
        out.update(k for k, d in r.items() if d == 1)
    for e in graph.get("edges") or ():
        if e.get("type") == "topic":
            continue
        if e.get("source") == page:
            out.add(e.get("target"))
        elif e.get("target") == page:
            out.add(e.get("source"))
    out.discard(page)
    return out


def _overlap(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / float(min(len(a), len(b)))


def answer(question, passages=None, graph=None, page=None, k=6):
    """Rank passages for ``question`` and pull out a short extractive answer.

    Returns ``{"answer", "passages" (top k, each with "score"), "pages" [{id,title,url}], "count"}``.
    """
    index = _index_for(passages)
    if graph is None and passages is None:
        graph = _CACHE.get("graph")
    count = index.n
    terms = []
    for t in tokenize(question or ""):
        if t not in terms:
            terms.append(t)
    if not terms:
        return {"answer": "", "passages": [], "pages": [], "count": count, "terms": []}
    raw = index.scores(terms)
    near = neighbours(graph, page)
    scored = []
    for i, s in enumerate(raw):
        if s <= 0:
            continue
        pid = index.passages[i].get("id")
        if page and pid == page:
            s *= PAGE_BOOST
        elif pid in near:
            s *= NEIGHBOUR_BOOST
        scored.append((s, i))
    scored.sort(key=lambda x: (-x[0], x[1]))
    top = scored[:max(1, int(k))]
    hits = []
    for s, i in top:
        p = dict(index.passages[i])
        p["score"] = round(s, 4)
        hits.append(p)

    # extractive answer: the best sentences from the top passages
    tset = set(terms)
    idf = {t: index.idf(t) for t in terms}
    idf_sum = sum(idf.values()) or 1.0
    cands = []
    best = top[0][0] if top else 1.0
    for rank, (s, i) in enumerate(top[:4]):
        if s < best * 0.45:
            break
        if rank and index.passages[i].get("id") != index.passages[top[0][1]].get("id") and s < best * 0.75:
            continue          # another page has to be nearly as good to speak in the answer
        sents = sentences(index.passages[i].get("text") or "")
        for j, sent in enumerate(sents):
            toks = set(tokenize(sent))
            if not toks or len(sent) < 25:
                continue
            cover = sum(idf[t] for t in tset & toks) / idf_sum
            if cover <= 0:
                continue
            score = cover * 2.0 + (s / best) - 0.04 * j - 0.15 * rank
            if len(sent) > 400:
                score -= 0.3
            cands.append((score, rank, j, sent, toks))
    cands.sort(key=lambda c: (-c[0], c[1], c[2]))
    if cands:
        # keep only sentences close to the best one: a stray shared word is not an answer
        top_score = cands[0][0]
        cands = [c for c in cands if c[0] >= top_score * 0.6]
    chosen = []
    for c in cands:
        if any(_overlap(c[4], o[4]) > 0.6 for o in chosen):
            continue
        chosen.append(c)
        if len(chosen) >= MAX_SENTENCES:
            break
    # if the best sentence already says a lot, two are enough
    if len(chosen) == 3 and sum(len(c[3]) for c in chosen) > 700:
        chosen = chosen[:2]
    chosen.sort(key=lambda c: (c[1], c[2]))
    text = " ".join(c[3] for c in chosen)

    pages, seen = [], set()
    for h in hits:
        if h.get("id") in seen:
            continue
        seen.add(h.get("id"))
        pages.append({"id": h.get("id"), "title": h.get("title"), "url": h.get("url")})
    return {"answer": text, "passages": hits, "pages": pages, "count": count, "terms": terms}
