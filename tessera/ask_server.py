"""The "written answer": a model answers a reader's question from the site's own passages only.

Shared by ``api/ask.py`` (Vercel) and ``tessera serve`` (local). Standard library only, plus ``retrieve`` and the
OpenAI-compatible client in ``llm``.

- ``GET``  -> ``{"on": bool, "limit": n, "left": n}``
- ``POST {"q": "...", "page": "post:x"}`` -> ``{"answer", "sources": [{n,title,url,section,anchor}], "left", "ms"}``

Limits: per IP per day (``ASK_PER_VISITOR``) and per day overall (``ASK_DAILY_CAP``), kept in memory only. Questions
and answers are never stored or logged. Without a model and key the endpoint reports ``{"on": false}``.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import re
import threading
import time

from . import retrieve

MAX_QUESTION = 400
MIN_QUESTION = 3
TOP_K = 6

SYSTEM = """You answer a reader's question about a technical blog, using ONLY the numbered passages from the blog.
Rules:
- Use only facts in the passages. If they do not answer the question, say so in one sentence and stop.
- Cite every sentence with the passage numbers in square brackets, like [1] or [2][3].
- Plain prose, at most about 150 words. Keep equations as plain text. No headings, no lists unless asked.
- Do not mention passages, sources or these rules; just answer and cite."""

_lock = threading.Lock()
_counts = {"day": None, "ip": {}, "total": 0}


def _today():
    return _dt.date.today().isoformat()


def _ip_key(ip):
    # the address is only hashed in memory to count requests; it is never written anywhere
    return hashlib.sha256((ip or "?").encode()).hexdigest()[:16]


def _roll():
    d = _today()
    if _counts["day"] != d:
        _counts.update(day=d, ip={}, total=0)


def reset_limits():
    with _lock:
        _counts.update(day=None, ip={}, total=0)


def settings(env: dict, cfg=None) -> dict:
    """Merge env over site.yml's ``llm:`` and ``ask:`` sections."""
    env = env or {}
    llm = dict((cfg or {}).get("llm") or {}) if cfg else {}
    ask = dict((cfg or {}).get("ask") or {}) if cfg else {}
    key_env = env.get("LLM_KEY_ENV") or llm.get("key_env") or "LLM_API_KEY"

    def num(name, default):
        try:
            return max(0, int(env.get(name) or default))
        except (TypeError, ValueError):
            return default

    model = env.get("LLM_MODEL") or env.get("ASK_MODEL") or llm.get("model") or ""
    base = env.get("LLM_BASE_URL") or llm.get("base_url") or "https://openrouter.ai/api/v1"
    written = ask.get("written_answers", True) is not False and str(env.get("ASK_WRITTEN", "1")) not in ("0", "false", "off")
    return {
        "key": env.get(key_env, ""),
        "model": model,
        "base_url": base,
        "per_visitor": num("ASK_PER_VISITOR", ask.get("per_visitor", 5)),
        "daily_cap": num("ASK_DAILY_CAP", ask.get("daily_cap", 300)),
        "on": bool(written and model and env.get(key_env, "")),
    }


def _left(s, ipk):
    _roll()
    used = _counts["ip"].get(ipk, 0)
    return max(0, min(s["per_visitor"] - used, s["daily_cap"] - _counts["total"]))


def _load(passages_loader):
    data = passages_loader() if callable(passages_loader) else passages_loader
    if isinstance(data, dict):
        return data.get("passages") or [], data.get("graph")
    return data or [], None


def handle(method: str, body: bytes, ip: str, env: dict, passages_loader, cfg=None, chat=None) -> tuple[int, dict]:
    """Return (status, JSON body). ``chat`` can be injected (tests); default is ``llm.chat``."""
    s = settings(env, cfg)
    ipk = _ip_key(ip)
    method = (method or "GET").upper()
    if method == "GET":
        if not s["on"]:
            return 200, {"on": False}
        with _lock:
            return 200, {"on": True, "limit": s["per_visitor"], "left": _left(s, ipk)}
    if method != "POST":
        return 405, {"error": "Use GET or POST."}
    if not s["on"]:
        return 503, {"on": False, "error": "Written answers are off on this site."}
    try:
        req = json.loads((body or b"{}").decode("utf-8"))
        if not isinstance(req, dict):
            raise ValueError
    except (ValueError, UnicodeDecodeError):
        return 400, {"error": "Send JSON like {\"q\": \"your question\"}."}
    q = " ".join(str(req.get("q") or "").split())
    page = req.get("page") or None
    if not isinstance(page, str):
        page = None
    if len(q) < MIN_QUESTION:
        return 400, {"error": "Ask a question of a few words."}
    if len(q) > MAX_QUESTION:
        return 400, {"error": f"Please keep the question under {MAX_QUESTION} characters."}
    with _lock:
        left = _left(s, ipk)
        if left <= 0:
            return 429, {"error": "That is all the written answers for today. The quick answer still works.", "left": 0}
        _counts["ip"][ipk] = _counts["ip"].get(ipk, 0) + 1
        _counts["total"] += 1
        left -= 1
    t0 = time.perf_counter()
    try:
        passages, graph = _load(passages_loader)
    except Exception:
        _refund(ipk)
        return 503, {"error": "The site's passages could not be loaded. Try again in a moment.", "left": left + 1}
    res = retrieve.answer(q, passages, graph, page=page, k=TOP_K)
    hits = res["passages"]
    if not hits:
        _refund(ipk)
        return 200, {"answer": "This site does not seem to cover that.", "sources": [], "left": left + 1,
                     "ms": round((time.perf_counter() - t0) * 1000)}
    sources, blocks = [], []
    for n, h in enumerate(hits, 1):
        sources.append({"n": n, "title": h.get("title"), "url": h.get("url"), "section": h.get("section") or "",
                        "anchor": h.get("anchor") or ""})
        where = h.get("title") + (f" — {h['section']}" if h.get("section") else "")
        blocks.append(f"[{n}] {where}\n{h.get('text')}")
    user = "Passages:\n\n" + "\n\n".join(blocks) + f"\n\nQuestion: {q}"
    mini = {"llm": {"base_url": s["base_url"], "model": s["model"], "key_env": "_"}, "_key": s["key"]}
    if chat is None:
        from .llm import chat as chat
    try:
        text = chat(mini, SYSTEM, user, json_mode=False, max_tokens=500, timeout=25)
    except Exception:
        _refund(ipk)
        return 502, {"error": "No written answer right now. The quick answer above still stands.", "left": left + 1}
    used = sorted({int(n) for n in re.findall(r"\[(\d+)\]", text) if 0 < int(n) <= len(sources)})
    return 200, {"answer": text.strip(), "sources": [x for x in sources if not used or x["n"] in used],
                 "left": left, "ms": round((time.perf_counter() - t0) * 1000)}


def _refund(ipk):
    with _lock:
        if _counts["ip"].get(ipk):
            _counts["ip"][ipk] -= 1
            _counts["total"] = max(0, _counts["total"] - 1)
