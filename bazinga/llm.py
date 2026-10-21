"""Optional model help: an OpenAI-compatible client and the proposal operations.

Every operation writes a *proposal* (``proposals/<op>-<slug>.md`` + ``.json``) and a line in ``wiki/log.md``.
Nothing here edits ``content/``: the author reads the proposal and accepts what is good.

Works with any OpenAI-compatible ``/chat/completions`` endpoint (OpenAI, OpenRouter, a local Ollama at
``http://localhost:11434/v1`` …). ``llm.model`` may list fallbacks separated by commas. The key is read from the
environment variable named by ``llm.key_env`` or from ``.env.local`` in the site root; it is never printed.
"""
from __future__ import annotations

import ast
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from . import wiki as _wiki

TIMEOUT = 60
DESCRIPTION_MAX = 155


class LLMError(Exception):
    pass


# ------------------------------------------------------------------------------------------------
# Settings and client
# ------------------------------------------------------------------------------------------------
def _get(obj, *path, default=None):
    return _wiki._get(obj, *path, default=default)


def _root(cfg):
    r = _get(cfg, "root")
    return Path(r) if r else None


def read_env_file(path: Path) -> dict:
    out = {}
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        return out
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        if k.startswith("export "):
            k = k[7:].strip()
        v = v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
            v = v[1:-1]
        out[k] = v
    return out


def api_key(cfg) -> str:
    if _get(cfg, "_key"):
        return _get(cfg, "_key")
    name = _get(cfg, "llm", "key_env", default="LLM_API_KEY") or "LLM_API_KEY"
    if os.environ.get(name):
        return os.environ[name]
    root = _root(cfg)
    if root is not None:
        return read_env_file(root / ".env.local").get(name, "")
    return ""


def models(cfg) -> list[str]:
    raw = _get(cfg, "llm", "model", default="") or ""
    if isinstance(raw, (list, tuple)):
        raw = ",".join(raw)
    return [m.strip() for m in str(raw).split(",") if m.strip()]


def _base_url(cfg) -> str:
    return (_get(cfg, "llm", "base_url", default="") or "https://openrouter.ai/api/v1").rstrip("/")


def _local(url: str) -> bool:
    return bool(re.match(r"^https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?/", url + "/"))


def configured(cfg) -> bool:
    """A model is named and a key is available (a local endpoint such as Ollama needs no key)."""
    return bool(models(cfg)) and (bool(api_key(cfg)) or _local(_base_url(cfg)))


def _post(url, payload, key, timeout):
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json", "Accept": "application/json", "User-Agent": "bazinga"}
    if key:
        headers["Authorization"] = "Bearer " + key
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def chat(cfg, system, user, json_mode=False, max_tokens=1200, timeout=None) -> str:
    """Send one chat; try each model in turn. Returns the reply text; raises LLMError if every model fails."""
    ms = models(cfg)
    if not ms:
        raise LLMError("no model is set: add llm.model to site.yml")
    key = api_key(cfg)
    url = _base_url(cfg) + "/chat/completions"
    if not key and not _local(url):
        raise LLMError(f"no API key: set {_get(cfg, 'llm', 'key_env', default='LLM_API_KEY')} in the environment or .env.local")
    errors = []
    for model in ms:
        payload = {
            "model": model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "max_tokens": int(max_tokens),
            "temperature": 0.2,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        tries = [payload]
        if json_mode:
            plain = dict(payload)
            plain.pop("response_format")
            tries.append(plain)          # some endpoints reject response_format: retry without it
        for p in tries:
            try:
                data = _post(url, p, key, timeout or TIMEOUT)
                msg = ((data.get("choices") or [{}])[0].get("message") or {})
                text = msg.get("content")
                if isinstance(text, list):
                    text = "".join(part.get("text", "") for part in text if isinstance(part, dict))
                if text and text.strip():
                    return text.strip()
                errors.append(f"{model}: empty reply")
                break
            except urllib.error.HTTPError as exc:
                exc.close()
                errors.append(f"{model}: HTTP {exc.code}")
                if exc.code == 400 and p is tries[0] and len(tries) > 1:
                    continue
                break
            except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
                errors.append(f"{model}: {type(exc).__name__}")
                break
    raise LLMError("every model failed (" + "; ".join(errors) + ")")


def parse_json(text: str):
    """Parse a JSON reply, tolerating ```json fences and text around the object."""
    t = (text or "").strip()
    m = re.search(r"```(?:json|JSON)?\s*\n?(.*?)```", t, re.S)
    if m:
        t = m.group(1).strip()
    try:
        return json.loads(t)
    except ValueError:
        pass
    for open_, close in (("{", "}"), ("[", "]")):
        i, j = t.find(open_), t.rfind(close)
        if i != -1 and j > i:
            try:
                return json.loads(t[i:j + 1])
            except ValueError:
                continue
    raise LLMError("the reply was not JSON")


def chat_json(cfg, system, user, max_tokens=1500):
    return parse_json(chat(cfg, system, user, json_mode=True, max_tokens=max_tokens))


# ------------------------------------------------------------------------------------------------
# Site state (pages, rendered, graph) for the operations. Tests replace ``load_state``.
# ------------------------------------------------------------------------------------------------
class State:
    def __init__(self, pages, rendered, graph, topics, site=None):
        self.pages = pages
        self.rendered = rendered
        self.graph = graph
        self.topics = topics
        self.site = site
        self.by_id = {p.id: p for p in pages}


def load_state(cfg) -> State:
    from . import content, graph as g, markdown
    pages = content.load_pages(cfg)
    topics = content.load_topics(cfg)
    site = markdown.SiteIndex(pages=pages, references=content.load_references(cfg), topics=topics, cfg=cfg)
    rendered = {}
    for p in pages:
        try:
            rendered[p.id] = markdown.render(p, site)
        except Exception:      # a page that fails to render still counts as a page
            rendered[p.id] = None
    return State(pages, rendered, g.build_graph(pages, rendered, site), topics, site)


def find_page(state: State, ref):
    """A page by id (``post:x``), slug, or file path."""
    if hasattr(ref, "id"):
        return ref
    ref = str(ref)
    if ref in state.by_id:
        return state.by_id[ref]
    stem = Path(ref).stem
    for p in state.pages:
        if p.slug == ref or p.slug == stem or str(p.path).endswith(ref):
            return p
    raise LLMError(f"no public page {ref!r} (use an id such as post:attention, a slug, or a file path)")


def page_text(state: State, page, limit=12000) -> str:
    r = state.rendered.get(page.id)
    secs = _get(r, "sections", default=None)
    if secs:
        parts = []
        for s in secs:
            if s.get("title"):
                parts.append("## " + s["title"])
            parts.append(s.get("text") or "")
        text = "\n".join(parts)
    else:
        text = page.body or ""
    return text[:limit]


# ------------------------------------------------------------------------------------------------
# Proposals
# ------------------------------------------------------------------------------------------------
def _slug(s):
    s = re.sub(r"[^a-z0-9]+", "-", str(s).lower()).strip("-")
    return s[:60] or "site"


def save_proposal(cfg, op, subject_slug, data, markdown_text, log_subject=None, extra_files=None):
    root = _root(cfg) or Path.cwd()
    folder = root / "proposals"
    folder.mkdir(parents=True, exist_ok=True)
    base = folder / f"{op}-{_slug(subject_slug)}"
    base.with_suffix(".json").write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    base.with_suffix(".md").write_text(markdown_text.rstrip() + "\n", encoding="utf-8")
    for suffix, text in (extra_files or {}).items():
        Path(str(base) + suffix).write_text(text, encoding="utf-8")
    _wiki.append_log(cfg, op, log_subject or subject_slug, f"Proposal: proposals/{base.name}.md")
    return base.with_suffix(".md")


# ------------------------------------------------------------------------------------------------
# ingest
# ------------------------------------------------------------------------------------------------
INGEST_SYSTEM = """You help the author of a technical blog keep it connected, like a wiki.
You read one page and the site's catalog and PROPOSE metadata. Use only ids and topics that appear in the lists given.
For links, quote one sentence that is copied word for word from the page, and the words in it to turn into the link.
Answer with one JSON object and nothing else:
{"topics": [slug, ...1-4], "builds_on": [page id, ...], "links": [{"target": id, "sentence": "...", "anchor_text": "..."}],
 "summary": "two or three sentences in the page's own words", "description": "at most 155 characters",
 "questions": ["three questions the page answers"], "series": {"name": "...", "part": n} or null}"""


def _catalog(state: State, skip=None, limit=200):
    lines = []
    for p in state.pages[:limit]:
        if p.id == skip:
            continue
        lines.append(f"- {p.id} | {p.title} | {', '.join(p.topics)} | {_wiki._one_line(p.summary)[:160]}")
    return "\n".join(lines)


def _norm(s):
    return re.sub(r"\s+", " ", s or "").strip()


def validate_ingest(raw: dict, page, state: State) -> dict:
    """Keep only what refers to real ids/topics and quotes the page; record what was dropped."""
    dropped = []
    raw = raw if isinstance(raw, dict) else {}
    topics = []
    for t in raw.get("topics") or []:
        t = str(t).strip()
        if t in state.topics and t not in topics:
            topics.append(t)
        else:
            dropped.append(f"topic {t!r}: not in topics.yml")
    if len(topics) > 4:
        dropped += [f"topic {t!r}: more than 4" for t in topics[4:]]
        topics = topics[:4]
    builds = []
    for b in raw.get("builds_on") or []:
        b = str(b).strip()
        if b in state.by_id and b != page.id and b not in builds:
            builds.append(b)
        else:
            dropped.append(f"builds_on {b!r}: no such page")
    text = _norm(page.body)
    links = []
    for ln in raw.get("links") or []:
        if not isinstance(ln, dict):
            continue
        tgt = str(ln.get("target") or "").strip()
        sent = _norm(str(ln.get("sentence") or ""))
        anchor = _norm(str(ln.get("anchor_text") or ""))
        if tgt not in state.by_id or tgt == page.id:
            dropped.append(f"link to {tgt!r}: no such page")
        elif not sent or sent not in text:
            dropped.append(f"link to {tgt!r}: the sentence is not in the page")
        elif not anchor or anchor not in sent:
            dropped.append(f"link to {tgt!r}: the anchor text is not in the sentence")
        elif f"[[{tgt}" in (page.body or ""):
            dropped.append(f"link to {tgt!r}: already linked")
        else:
            links.append({"target": tgt, "sentence": sent, "anchor_text": anchor,
                          "replace_with": sent.replace(anchor, f"[[{tgt}|{anchor}]]", 1)})
    summary = _norm(str(raw.get("summary") or ""))
    desc = _norm(str(raw.get("description") or ""))
    if len(desc) > DESCRIPTION_MAX:
        dropped.append(f"description: {len(desc)} characters, cut to {DESCRIPTION_MAX}")
        desc = cut(desc, DESCRIPTION_MAX)
    questions = [_norm(str(q)) for q in (raw.get("questions") or []) if _norm(str(q))][:3]
    series = raw.get("series")
    if isinstance(series, dict) and series.get("name"):
        try:
            series = {"name": _norm(str(series["name"])), "part": int(series.get("part") or 0)}
        except (TypeError, ValueError):
            dropped.append("series: part is not a number")
            series = None
    else:
        series = None
    return {"page": page.id, "topics": topics, "builds_on": builds, "links": links, "summary": summary,
            "description": desc, "questions": questions, "series": series, "dropped": dropped}


def ingest(cfg, page, state: State | None = None) -> dict:
    state = state or load_state(cfg)
    page = find_page(state, page)
    user = (f"Topics allowed (slug: label):\n" + "\n".join(f"- {k}: {v.get('label', k) if isinstance(v, dict) else v}" for k, v in state.topics.items())
            + f"\n\nOther pages (id | title | topics | summary):\n{_catalog(state, skip=page.id)}"
            + f"\n\nSeries in use: {', '.join(state.graph.series()) or 'none'}"
            + f"\n\nTHE PAGE {page.id}: {page.title}\nCurrent topics: {page.topics}; builds_on: {page.builds_on}\n\n{page.body[:14000]}")
    raw = chat_json(cfg, INGEST_SYSTEM, user)
    out = validate_ingest(raw, page, state)
    md = [f"# Ingest proposal: {page.title}", "", f"Page `{page.id}` ({page.path}). Nothing was changed; copy what you accept.", ""]
    md += ["## Front matter", "", "```yaml"]
    md.append(f"topics: [{', '.join(out['topics'])}]")
    if out["builds_on"]:
        md.append(f"builds_on: [{', '.join(out['builds_on'])}]")
    if out["summary"]:
        md.append(f"summary: {json.dumps(out['summary'], ensure_ascii=False)}")
    if out["description"]:
        md.append(f"description: {json.dumps(out['description'], ensure_ascii=False)}")
    if out["series"]:
        md.append(f"series: {{name: {json.dumps(out['series']['name'])}, part: {out['series']['part']}}}")
    md += ["```", ""]
    if out["links"]:
        md += ["## Links to add", ""]
        for ln in out["links"]:
            md += [f"- to `{ln['target']}` ({state.by_id[ln['target']].title})", f"  - now: {ln['sentence']}",
                   f"  - with link: {ln['replace_with']}"]
        md.append("")
    if out["questions"]:
        md += ["## Questions the page answers", ""] + [f"- {q}" for q in out["questions"]] + [""]
    if out["dropped"]:
        md += ["## Dropped (did not check out)", ""] + [f"- {d}" for d in out["dropped"]] + [""]
    out["proposal"] = str(save_proposal(cfg, "ingest", page.slug, out, "\n".join(md), page.title))
    return out


# ------------------------------------------------------------------------------------------------
# lint
# ------------------------------------------------------------------------------------------------
_MENTION_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]")


def lint_rules(state: State, today=None) -> dict:
    import datetime as dt
    today = today or dt.date.today()
    g = state.graph
    strong = {}
    for e in g.edges:
        if e["type"] != "topic":
            strong.setdefault(e["source"], set()).add(e["target"])
            strong.setdefault(e["target"], set()).add(e["source"])
    orphans = [p.id for p in state.pages if not strong.get(p.id)]
    mentions = {(e["source"], e["target"]) for e in g.edges if e["type"] in ("mentions", "builds_on")}
    one_way = []
    for a, b in sorted(mentions):
        if (b, a) not in mentions and set(g.nodes[a]["topics"]) & set(g.nodes[b]["topics"]):
            one_way.append({"from": a, "to": b})
    counts = {t: 0 for t in state.topics}
    for p in state.pages:
        for t in p.topics:
            counts[t] = counts.get(t, 0) + 1
    thin = sorted(t for t, n in counts.items() if n < 2)
    no_fig = []
    for p in state.pages:
        r = state.rendered.get(p.id)
        if r is not None and not (_get(r, "figures", default=[]) or _get(r, "drawings", default=[])):
            no_fig.append(p.id)
    stale = []
    for p in state.pages:
        if p.updated and p.date and p.updated < p.date:
            stale.append({"page": p.id, "problem": f"updated {p.updated} is before date {p.date}"})
        elif p.updated and p.updated > today:
            stale.append({"page": p.id, "problem": f"updated {p.updated} is in the future"})
    broken = []
    for p in state.pages:
        for m in _MENTION_RE.finditer(p.body or ""):
            t = m.group(1).strip()
            if t not in state.by_id:
                broken.append({"page": p.id, "link": t})
    return {"orphans": orphans, "one_way_links": one_way, "thin_topics": thin, "pages_without_figures": no_fig,
            "stale_updated": stale, "broken_links": broken}


LINT_SYSTEM = """You check a technical blog for contradictions between pages that share a topic.
Report only real contradictions: two pages that state incompatible facts, numbers or definitions.
Quote both claims word for word. Answer with JSON: {"contradictions": [{"pages": [id, id], "claim_a": "...", "claim_b": "...", "note": "..."}]}
Use only the page ids given. An empty list is a good answer."""


def lint(cfg, use_model=False, state: State | None = None) -> dict:
    state = state or load_state(cfg)
    out = {"rules": lint_rules(state), "contradictions": [], "dropped": []}
    if use_model:
        for t in sorted(state.topics):
            ids = state.graph.topic_pages(t)
            if len(ids) < 2:
                continue
            ids = ids[:6]
            blocks = [f"=== {i}: {state.by_id[i].title}\n{page_text(state, state.by_id[i], 4000)}" for i in ids]
            try:
                raw = chat_json(cfg, LINT_SYSTEM, f"Topic: {t}\n\n" + "\n\n".join(blocks))
            except Exception as exc:
                out["dropped"].append(f"topic {t}: {exc}")
                continue
            for c in (raw.get("contradictions") or []) if isinstance(raw, dict) else []:
                ps = [str(x) for x in (c.get("pages") or [])][:2]
                if len(ps) == 2 and all(x in ids for x in ps):
                    ok = all(_norm(str(c.get(k) or ""))[:40] in _norm(state.by_id[p].body)
                             for k, p in (("claim_a", ps[0]), ("claim_b", ps[1])))
                    if ok:
                        out["contradictions"].append({"topic": t, "pages": ps, "claim_a": c.get("claim_a"),
                                                      "claim_b": c.get("claim_b"), "note": c.get("note", "")})
                        continue
                out["dropped"].append(f"topic {t}: a claim that is not quoted from the pages")
    r = out["rules"]
    md = ["# Lint", "", "Fixed rules over the public pages" + (" and a model check for contradictions." if use_model else "."), ""]
    sections = [
        ("Orphans (no links, no shared citations, no series)", [f"- `{x}`" for x in r["orphans"]]),
        ("One-way links between pages on the same topic", [f"- `{x['from']}` links to `{x['to']}`, not back" for x in r["one_way_links"]]),
        ("Thin topics (fewer than two pages)", [f"- `{x}`" for x in r["thin_topics"]]),
        ("Pages without figures or drawings", [f"- `{x}`" for x in r["pages_without_figures"]]),
        ("Dates to check", [f"- `{x['page']}`: {x['problem']}" for x in r["stale_updated"]]),
        ("Broken [[links]]", [f"- `{x['page']}` links to `{x['link']}`" for x in r["broken_links"]]),
    ]
    if use_model:
        sections.append(("Possible contradictions", [f"- {c['pages'][0]} says “{c['claim_a']}”; {c['pages'][1]} says “{c['claim_b']}”. {c['note']}" for c in out["contradictions"]]))
    for title, items in sections:
        md += [f"## {title}", ""] + (items or ["- none"]) + [""]
    n = sum(len(v) for v in r.values()) + len(out["contradictions"])
    out["proposal"] = str(save_proposal(cfg, "lint", "site", out, "\n".join(md), f"{n} findings"))
    return out


# ------------------------------------------------------------------------------------------------
# highlights
# ------------------------------------------------------------------------------------------------
_NUM = re.compile(r"(?<![\w.])-?\d+(?:[.,]\d+)*(?:\.\d+)?%?")

HIGHLIGHT_SYSTEM = """You write highlights for one part of a blog series: 3 or 4 short lines (under 160 characters each),
each one a concrete thing the reader learns in THIS part, in the page's own words. Do not add facts or numbers that are
not in the page. Answer with JSON: {"highlights": ["...", "..."]}"""


def _numbers(s):
    return [m.group(0).rstrip("%").replace(",", "") for m in _NUM.finditer(s)]


def check_highlights(lines, text) -> tuple[list, list]:
    """Keep a line only if every number in it appears in the page text."""
    page_nums = set(_numbers(text))
    keep, drop = [], []
    for ln in lines:
        ln = _norm(str(ln))
        if not ln:
            continue
        missing = [n for n in _numbers(ln) if n not in page_nums]
        if missing:
            drop.append({"line": ln, "why": "numbers not in the page: " + ", ".join(missing)})
        elif len(ln) > 200:
            drop.append({"line": ln, "why": "too long"})
        else:
            keep.append(ln)
    return keep[:4], drop


def highlights(cfg, series, state: State | None = None) -> dict:
    state = state or load_state(cfg)
    from .graph import series_slug
    all_series = state.graph.series()
    name = next((n for n in all_series if n == series or series_slug(n) == series_slug(str(series))), None)
    if name is None:
        raise LLMError(f"no series {series!r}; known: {', '.join(all_series) or 'none'}")
    parts = []
    for i in all_series[name]:
        p = state.by_id[i]
        text = page_text(state, p)
        try:
            raw = chat_json(cfg, HIGHLIGHT_SYSTEM, f"Series: {name}\nPart: {p.title}\n\n{text}")
            lines = raw.get("highlights") if isinstance(raw, dict) else raw
        except LLMError as exc:
            parts.append({"id": i, "title": p.title, "highlights": [], "dropped": [{"line": "", "why": str(exc)}]})
            continue
        keep, drop = check_highlights(lines or [], (p.body or "") + "\n" + text)
        parts.append({"id": i, "title": p.title, "highlights": keep, "dropped": drop})
    out = {"series": name, "slug": series_slug(name), "parts": parts}
    yml = [f"# content/series/{out['slug']}.yml (proposal; copy it there when you accept it)", f"series: {json.dumps(name)}", "parts:"]
    for pt in parts:
        yml.append(f"  {pt['id']}:")
        yml += [f"    - {json.dumps(h, ensure_ascii=False)}" for h in pt["highlights"]] or ["    []"]
    md = [f"# Highlights: {name}", "", "Every number in a kept line appears in its page.", "", "```yaml", *yml, "```", ""]
    dropped = [f"- {pt['id']}: {d['line']} ({d['why']})" for pt in parts for d in pt["dropped"]]
    if dropped:
        md += ["## Dropped", ""] + dropped + [""]
    out["proposal"] = str(save_proposal(cfg, "highlights", out["slug"], out, "\n".join(md), name,
                                        extra_files={".yml": "\n".join(yml) + "\n"}))
    return out


# ------------------------------------------------------------------------------------------------
# describe, equation, figure
# ------------------------------------------------------------------------------------------------
def cut(text, limit=DESCRIPTION_MAX) -> str:
    """Shorten to ``limit`` characters at a sentence, clause or word boundary."""
    text = _norm(text)
    if len(text) <= limit:
        return text
    head = text[:limit + 1]
    for sep in (". ", "; ", ", ", " — ", " "):
        i = head.rfind(sep, 0, limit)
        if i > limit * 0.5:
            out = head[:i + (1 if sep == ". " else 0)].rstrip(" ,;—")
            return out if out.endswith(".") else out
    return text[:limit].rstrip()


DESCRIBE_SYSTEM = """Write a search-engine description for this page: one sentence, at most 155 characters, using the
page's own words and terms. No marketing words, no "In this post". Answer with the sentence only."""


def own_words(sentence, text, share=0.7) -> bool:
    from .retrieve import tokenize
    toks = tokenize(sentence)
    if not toks:
        return False
    have = set(tokenize(text))
    return sum(1 for t in toks if t in have) / len(toks) >= share


def describe(cfg, page, state: State | None = None) -> str:
    state = state or load_state(cfg)
    page = find_page(state, page)
    text = page_text(state, page, 8000)
    desc = ""
    try:
        desc = _norm(chat(cfg, DESCRIBE_SYSTEM, f"{page.title}\n\n{page.summary}\n\n{text}", max_tokens=200)).strip('"')
    except LLMError:
        pass
    source = "model"
    if not desc or not own_words(desc, page.title + " " + page.summary + " " + page.body):
        desc, source = page.summary or text, "summary"
    desc = cut(desc)
    data = {"page": page.id, "description": desc, "chars": len(desc), "from": source}
    md = [f"# Description: {page.title}", "", "```yaml", f"description: {json.dumps(desc, ensure_ascii=False)}", "```",
          "", f"{len(desc)} characters." + (" Taken from the summary (the model's line was not in the page's words)." if source == "summary" else "")]
    save_proposal(cfg, "describe", page.slug, data, "\n".join(md), page.title)
    return desc


EQUATION_SYSTEM = """Turn the description into one LaTeX equation for MathML conversion. Use plain LaTeX: \\frac, \\sum,
\\mathbf, \\operatorname, \\begin{array}{rl} for several rows (not aligned). Answer with the LaTeX only: no $$, no prose."""


def clean_latex(text) -> str:
    t = (text or "").strip()
    m = re.search(r"```(?:latex|tex)?\s*\n?(.*?)```", t, re.S)
    if m:
        t = m.group(1).strip()
    for a, b in (("$$", "$$"), ("\\[", "\\]"), ("$", "$")):
        if t.startswith(a) and t.endswith(b) and len(t) > len(a) + len(b):
            t = t[len(a):-len(b)].strip()
            break
    return t


def equation(cfg, words) -> str:
    tex = clean_latex(chat(cfg, EQUATION_SYSTEM, words, max_tokens=400))
    try:
        from . import mathml
        try:
            mathml.to_mathml(tex, True)
        except mathml.MathError as exc:
            hint = getattr(exc, "hint", "") or str(exc)
            tex = clean_latex(chat(cfg, EQUATION_SYSTEM, f"{words}\n\nYour last answer {tex!r} failed: {hint}", max_tokens=400))
    except ImportError:
        pass
    root = _root(cfg)
    if root is not None:
        _wiki.append_log(cfg, "equation", _norm(words)[:80])
    return tex


FIGURE_SYSTEM = """You write an interactive figure module for a technical blog. Follow the contract exactly:
module-level TITLE, CAPTION, CONTROLS (list of dicts: name, kind slider|steps|toggle, label, and min/max/step/value or
options/value), optional PRESETS, and a pure function compute(<one keyword per control with its default>, _narrow=0)
that returns a spec dict {"panels": [...], "readouts": [...], "note": "..."} as described. Standard library only.
Styles are names (main, second, third, muted, dashed, area, points), never colours. Answer with the Python source only."""

FIGURE_CONTRACT = """Spec: {"panels": [{"kind": "xy|bars|heatmap|scene", "title", "x_label", "y_label", "x", "x_min",
"x_max", "y_min", "y_max", "series": [{"name", "y", "x", "style", "label_at": "end|none"}], "bars": [{"label", "value",
"style", "note"}], "matrix", "row_labels", "col_labels", "range", "shapes": [{"type": "point|line|arrow|polygon|circle|
rect|text", "style", "label", ...}], "marks": [{"x"|"y", "label"}], "annotations": [{"x", "y", "text"}]}],
"readouts": [{"label", "value", "note"}], "note": "..."}. compute() must run in under 30 ms and never return NaN."""


def closest_starter(description) -> tuple[str, str]:
    from .retrieve import tokenize
    folder = Path(__file__).with_name("starters") / "figures"
    best = ("", "", -1.0)
    want = set(tokenize(description))
    for f in sorted(folder.glob("*.py")) if folder.is_dir() else []:
        src = f.read_text(encoding="utf-8")
        head = f.stem.replace("_", " ") + " " + " ".join(re.findall(r'^(?:TITLE|CAPTION)\s*=\s*["\'](.*)["\']', src, re.M))
        score = len(want & set(tokenize(head))) + 0.01 * len(want & set(tokenize(src)))
        if score > best[2]:
            best = (f.stem, src, score)
    return best[0], best[1]


def check_figure_source(src) -> list[str]:
    problems = []
    try:
        tree = ast.parse(src)
    except SyntaxError as exc:
        return [f"syntax error on line {exc.lineno}: {exc.msg}"]
    names = {t.id for n in tree.body if isinstance(n, ast.Assign) for t in n.targets if isinstance(t, ast.Name)}
    funcs = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
    for need in ("TITLE", "CAPTION", "CONTROLS"):
        if need not in names:
            problems.append(f"{need} is missing")
    if "compute" not in funcs:
        problems.append("compute() is missing")
    std = set(getattr(sys, "stdlib_module_names", ())) | {"bazinga"}
    for n in ast.walk(tree):
        mods = []
        if isinstance(n, ast.Import):
            mods = [a.name.split(".")[0] for a in n.names]
        elif isinstance(n, ast.ImportFrom) and n.module:
            mods = [n.module.split(".")[0]]
        for m in mods:
            if std and m not in std:
                problems.append(f"imports {m}, which is not in the standard library (add it to REQUIRES if you mean it)")
    return problems


def figure_draft(cfg, description) -> str:
    name, starter = closest_starter(description)
    user = f"{FIGURE_CONTRACT}\n\nDescription of the figure:\n{description}\n"
    if starter:
        user += f"\nStart from this working starter ({name}.py) and change it:\n```python\n{starter}\n```\n"
    src = chat(cfg, FIGURE_SYSTEM, user, max_tokens=3000)
    m = re.search(r"```(?:python|py)?\s*\n(.*?)```", src, re.S)
    if m:
        src = m.group(1)
    src = src.strip() + "\n"
    problems = check_figure_source(src)
    if problems:
        retry = chat(cfg, FIGURE_SYSTEM, user + "\nYour previous answer had these problems: " + "; ".join(problems)
                     + f"\n```python\n{src}```", max_tokens=3000)
        m = re.search(r"```(?:python|py)?\s*\n(.*?)```", retry, re.S)
        src = (m.group(1) if m else retry).strip() + "\n"
        problems = check_figure_source(src)
    slug = _slug(description)[:40]
    md = [f"# Figure draft: {description}", "", f"Started from `{name or 'nothing'}`. Saved as proposals/figure-{slug}.py.",
          "Copy it to figures/<name>.py and run `python -m bazinga figure test <name>`.", ""]
    if problems:
        md += ["## Problems still in the draft", ""] + [f"- {p}" for p in problems] + [""]
    if _root(cfg) is not None:
        save_proposal(cfg, "figure", slug, {"description": description, "starter": name, "problems": problems},
                      "\n".join(md), _norm(description)[:80], extra_files={".py": src})
    return src


# ------------------------------------------------------------------------------------------------
# CLI: python -m bazinga wiki <op>
# ------------------------------------------------------------------------------------------------
USAGE = """usage: python -m bazinga wiki <command>

  index                      rewrite wiki/index.md from the public pages (no model)
  query "<question>"         answer from the site's passages (no model)
  ingest <page>              propose topics, links, summary, description, questions for one page
  lint [--model]             fixed checks; with --model also look for contradictions
  highlights <series>        propose 3-4 highlights per part of a series
  describe <page>            propose a description of at most 155 characters
  equation "<words>"         LaTeX for an equation described in words
  figure "<description>"     draft a figure module from the closest starter
  log <op> "<subject>"       append an entry to wiki/log.md

<page> is an id (post:attention), a slug or a file path. Proposals go to proposals/; nothing in content/ changes."""


def cli(argv, cfg=None) -> int:
    argv = list(argv)
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(USAGE)
        return 0
    op, args = argv[0], argv[1:]
    if cfg is None:
        from . import config
        cfg = config.load()
    try:
        if op == "index":
            state = load_state(cfg)
            changed = _wiki.write_repo_wiki(cfg, state.pages, state.graph)
            print(f"wiki/index.md: {len(state.pages)} pages, {'updated' if changed else 'unchanged'}")
            if changed:
                _wiki.append_log(cfg, "index", f"{len(state.pages)} pages")
            return 0
        if op == "log":
            if len(args) < 2:
                print("usage: python -m bazinga wiki log <op> \"<subject>\"")
                return 2
            _wiki.append_log(cfg, args[0], " ".join(args[1:]))
            return 0
        if op == "query":
            from . import retrieve
            state = load_state(cfg)
            ps = _wiki.passages(state.pages, state.rendered)
            res = retrieve.answer(" ".join(args), ps, state.graph.to_json())
            print(res["answer"] or "Nothing on this site matches that question.")
            print()
            for p in res["passages"][:6]:
                print(f"- {p['title']} — {p['section'] or 'introduction'}: {p['url']}{'#' + p['anchor'] if p['anchor'] else ''}")
            return 0
        needs_model = {"ingest", "highlights", "describe", "equation", "figure"}
        if op == "lint":
            use = "--model" in args
            if use and not configured(cfg):
                print("No model configured (llm.model and a key); running the fixed rules only.")
                use = False
            out = lint(cfg, use_model=use)
            print(f"Lint: {sum(len(v) for v in out['rules'].values())} findings. Proposal: {out['proposal']}")
            return 0
        if op not in needs_model:
            print(f"unknown wiki command {op!r}\n\n{USAGE}")
            return 2
        if not args:
            print(f"missing argument for {op}\n\n{USAGE}")
            return 2
        if not configured(cfg):
            print("No model configured: set llm.model in site.yml and the key in the environment variable named by "
                  "llm.key_env (or .env.local).")
            return 1
        arg = " ".join(args)
        if op == "ingest":
            out = ingest(cfg, arg)
            print(f"Proposal: {out['proposal']} ({len(out['links'])} links, {len(out['dropped'])} dropped)")
        elif op == "highlights":
            out = highlights(cfg, arg)
            print(f"Proposal: {out['proposal']}")
        elif op == "describe":
            print(describe(cfg, arg))
        elif op == "equation":
            print(equation(cfg, arg))
        elif op == "figure":
            print(figure_draft(cfg, arg))
        return 0
    except LLMError as exc:
        print(f"error: {exc}")
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(cli(sys.argv[1:]))
