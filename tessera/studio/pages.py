"""Reading and writing page files for the Studio.

The editor works on two things: the front matter (as a dict, edited through the Details form) and the Markdown body.
:func:`compose` turns them back into a file. When the front matter did not change, the original YAML text is kept
byte for byte, so autosaving the body never reformats what the author wrote by hand.
"""
from __future__ import annotations

import datetime as _dt
import json
import re
from pathlib import Path

import yaml

from .. import content as _content
from ..config import kind_id_prefix
from .security import Refused, atomic_write, confine

DATE_KEYS = ("date", "updated")
# The order fields are written in when the Studio re-serialises the front matter; unknown keys follow in their order.
ORDER = ("title", "date", "updated", "status", "summary", "description", "topics", "series", "builds_on", "cites",
         "cover")
_PLAIN = re.compile(r"^[A-Za-z_][A-Za-z0-9 _.\-/:]*$")
_RESERVED = {"true", "false", "yes", "no", "on", "off", "null", "none", "~", ""}


# --- front matter --------------------------------------------------------------------------------------------------

def split(text: str) -> tuple[str, str]:
    """(front-matter YAML, body). Uses core's splitter so both agree on where the body starts."""
    fm, body, _line = _content.split_front_matter(text)
    return fm, body


def load_meta(fm: str) -> dict:
    meta = yaml.safe_load(fm) if fm.strip() else {}
    return meta if isinstance(meta, dict) else {}


def to_json(value):
    """Front-matter values as JSON (dates become YYYY-MM-DD)."""
    if isinstance(value, (_dt.date, _dt.datetime)):
        return value.isoformat()[:10]
    if isinstance(value, dict):
        return {str(k): to_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [to_json(v) for v in value]
    return value


def _scalar(value) -> str:
    if value is None:
        return '""'
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, (_dt.date, _dt.datetime)):
        return value.isoformat()[:10]
    text = str(value)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return text
    if _PLAIN.match(text) and text.lower() not in _RESERVED and not text.endswith((" ", ":")) and ": " not in text \
            and not re.fullmatch(r"[\d.eE+-]+", text):
        return text
    return json.dumps(text, ensure_ascii=False)


def _flow(value) -> str:
    if isinstance(value, list):
        return "[" + ", ".join(_flow(v) for v in value) + "]"
    if isinstance(value, dict):
        return "{" + ", ".join(f"{k}: {_flow(v)}" for k, v in value.items()) + "}"
    return _scalar(value)


def dump_meta(meta: dict) -> str:
    """Front matter in the style of the docs: one key per line, short lists and maps in flow style."""
    keys = [k for k in ORDER if k in meta] + [k for k in meta if k not in ORDER]
    lines = []
    for key in keys:
        value = meta[key]
        if key in DATE_KEYS and value in ("", None):
            continue
        if value in ("", None, [], {}) and key not in ("title",):
            continue
        lines.append(f"{key}: {_flow(value)}")
    return "\n".join(lines)


def normalise(meta: dict) -> dict:
    """Clean a front-matter dict that came from the browser: trim strings, parse dates, drop empty values."""
    out: dict = {}
    for key, value in (meta or {}).items():
        key = str(key).strip()
        if not re.fullmatch(r"[A-Za-z_][\w-]*", key):
            raise Refused(400, f"{key!r} is not a valid front-matter field name.")
        if isinstance(value, str):
            value = value.strip()
        if key in DATE_KEYS and isinstance(value, str) and value:
            try:
                value = _dt.date.fromisoformat(value)
            except ValueError:
                raise Refused(400, f"{key} must be a date written YYYY-MM-DD.") from None
        if key == "series" and isinstance(value, dict):
            name = str(value.get("name") or "").strip()
            if not name:
                continue
            try:
                part = int(value.get("part") or 1)
            except (TypeError, ValueError):
                part = 1
            value = {"name": name, "part": part}
        if isinstance(value, list):
            value = [v.strip() if isinstance(v, str) else v for v in value]
            value = [v for v in value if v not in ("", None)]
        out[key] = value
    return out


def _key_spans(lines: list[str]) -> dict[str, tuple[int, int]]:
    """Top-level key -> (first line, end line) in front-matter lines; continuation lines belong to their key."""
    spans: dict[str, tuple[int, int]] = {}
    current = None
    for i, line in enumerate(lines):
        m = re.match(r"^([A-Za-z_][\w-]*)\s*:", line)
        if m:
            if current:
                spans[current[0]] = (current[1], i)
            current = (m.group(1), i)
        elif current and line[:1] in (" ", "\t", "-") and line.strip():
            continue
        elif current:
            spans[current[0]] = (current[1], i)
            current = None
    if current:
        spans[current[0]] = (current[1], len(lines))
    return spans


def patch_front_matter(old_fm: str, new_meta: dict) -> str:
    """Change only the keys whose values differ, keeping comments, order and formatting of everything else."""
    old_meta = load_meta(old_fm)
    lines = old_fm.split("\n")
    spans = _key_spans(lines)
    if set(spans) != set(old_meta):          # something unusual: re-serialise
        return dump_meta(new_meta)
    edits = []                               # (start, end, replacement lines)
    for key, (a, b) in spans.items():
        if key not in new_meta or new_meta[key] in ("", None, [], {}):
            edits.append((a, b, []))
        elif to_json(new_meta[key]) != to_json(old_meta.get(key)):
            edits.append((a, b, [f"{key}: {_flow(new_meta[key])}"]))
    for a, b, rep in sorted(edits, reverse=True):
        lines[a:b] = rep
    added = [k for k in new_meta if k not in spans and new_meta[k] not in ("", None, [], {})]
    if added:
        last = max((b for k, (a, b) in spans.items() if k in new_meta), default=0)
        shift = sum(len(rep) - (b - a) for a, b, rep in edits if a < last)
        at = last + shift
        lines[at:at] = [f"{k}: {_flow(new_meta[k])}" for k in added]
    fm = "\n".join(lines)
    try:
        if to_json(load_meta(fm)) == to_json({k: v for k, v in new_meta.items() if v not in ("", None, [], {})}):
            return fm
    except yaml.YAMLError:
        pass
    return dump_meta(new_meta)


def compose(meta: dict, body: str, original: str | None = None) -> str:
    """The file text for ``meta`` + ``body``. Keeps the original YAML (comments included) for unchanged keys."""
    fm = None
    if original is not None:
        try:
            old_fm, _old_body = split(original)
            fm = old_fm if to_json(load_meta(old_fm)) == to_json(meta) else patch_front_matter(old_fm, meta)
        except Exception:  # noqa: BLE001
            fm = None
    if fm is None:
        fm = dump_meta(meta)
    body = body.replace("\r\n", "\n").lstrip("\n")
    if not body.endswith("\n"):
        body += "\n"
    return f"---\n{fm}\n---\n\n{body}"


def set_fields(text: str, **fields) -> str:
    """Change some front-matter fields of a file's text (None removes a field). Used by publish."""
    fm, body = split(text)
    meta = load_meta(fm)
    for key, value in fields.items():
        if value is None:
            meta.pop(key, None)
        else:
            meta[key] = value
    return f"---\n{patch_front_matter(fm, meta)}\n---\n" + body


# --- the site's pages ----------------------------------------------------------------------------------------------

def page_path(cfg, page_id: str) -> Path:
    """``post:attention`` -> content/posts/attention.md (confined)."""
    if not isinstance(page_id, str) or ":" not in page_id:
        raise Refused(400, "Unknown page.")
    prefix, slug = page_id.split(":", 1)
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", slug or ""):
        raise Refused(400, "That page name is not valid.")
    for kind in cfg["kinds"]:
        if kind_id_prefix(cfg, kind) == prefix:
            return confine(cfg.root, f"content/{kind}/{slug}.md")
    raise Refused(404, "Unknown kind of page.")


def page_id(cfg, kind: str, slug: str) -> str:
    return f"{kind_id_prefix(cfg, kind)}:{slug}"


def kind_of(cfg, page_id: str) -> str:
    prefix = page_id.split(":", 1)[0]
    for kind in cfg["kinds"]:
        if kind_id_prefix(cfg, kind) == prefix:
            return kind
    raise Refused(404, "Unknown kind of page.")


_FIG = re.compile(r"^::figure\s+([A-Za-z_][\w]*)", re.M)
_DRAW = re.compile(r"^::drawing\s+([A-Za-z_][\w]*)\.([A-Za-z_]\w*)", re.M)
_UPLOAD = re.compile(r"static/uploads/[A-Za-z0-9._/-]+")


def figures_used(body: str) -> list[str]:
    return list(dict.fromkeys(_FIG.findall(_strip_code(body))))


def drawings_used(body: str) -> list[str]:
    return list(dict.fromkeys(f"{m}.{f}" for m, f in _DRAW.findall(_strip_code(body))))


def uploads_used(text: str) -> list[str]:
    return list(dict.fromkeys(_UPLOAD.findall(text)))


def _strip_code(body: str) -> str:
    return re.sub(r"^(```|~~~).*?^\1", "", body, flags=re.S | re.M)


def summary_row(cfg, path: Path) -> dict:
    """What the Library shows for one file. Never raises: a broken file is listed with its problem."""
    kind, slug = _content.kind_and_slug(path, cfg)
    stat = path.stat()
    row = {"id": page_id(cfg, kind, slug), "kind": kind, "slug": slug, "path": str(path.relative_to(cfg.root)),
           "url": f"/{kind}/{slug}/", "mtime": stat.st_mtime, "title": slug, "summary": "", "state": "draft",
           "date": None, "words": 0, "figures": 0, "topics": [], "error": None}
    try:
        page = _content.load_file(path, cfg)
    except Exception as exc:  # noqa: BLE001 - shown in the Library, never fatal
        row["error"] = str(exc)
        return row
    row.update(title=page.title or slug, summary=page.summary, state=page.state,
               date=page.date.isoformat() if page.date else None, topics=page.topics,
               words=_content.word_count(page.body), figures=len(figures_used(page.body)),
               series=page.series)
    return row


def list_pages(cfg) -> list[dict]:
    rows = [summary_row(cfg, p) for p in _content.content_files(cfg)]
    rows.sort(key=lambda r: r["mtime"], reverse=True)
    return rows


def unique_slug(cfg, kind: str, title: str) -> str:
    base = _content.slugify(title)[:60].strip("-") or "untitled"
    slug, n = base, 2
    while (cfg.content_dir / kind / f"{slug}.md").exists():
        slug, n = f"{base}-{n}", n + 1
    return slug


def starter_text(title: str) -> str:
    """A new draft from tessera/starters/post.md (core), with the title filled in and no date yet.

    The starter's text is kept (its commented-out optional fields are useful), with ``{{title}}`` replaced and the
    ``date:`` line dropped: a draft gets its date when it is published.
    """
    starter = Path(__file__).resolve().parent.parent / "starters" / "post.md"
    text = starter.read_text(encoding="utf-8") if starter.exists() else (
        '---\ntitle: "{{title}}"\nstatus: draft\n---\n\nStart writing here.\n')
    quoted = json.dumps(title, ensure_ascii=False)
    text = text.replace('"{{title}}"', quoted).replace("'{{title}}'", quoted).replace("{{title}}", title)
    text = re.sub(r"^date:\s*\{\{date\}\}\s*\n", "", text, flags=re.M)
    text = text.replace("{{date}}", "")
    try:
        fm, body = split(text)
        meta = load_meta(fm)
        ok = meta.get("title") == title
    except Exception:  # noqa: BLE001 - an unusual starter: fall back to writing the fields ourselves
        ok, body, meta = False, text, {}
    if not ok or str(meta.get("status", "")).lower() != "draft":
        meta = {k: v for k, v in meta.items() if k not in ("date", "updated")}
        meta.update(title=title, status="draft")
        return compose(normalise(to_json(meta)), body)
    return text


def rewrite_references(text: str, old_id: str, new_id: str) -> tuple[str, int]:
    """Point ``[[old]]``, ``[[old|...]]`` and ``builds_on: [old]`` at the new id. Returns (text, changes)."""
    count = 0

    def link(m):
        nonlocal count
        count += 1
        return f"[[{new_id}{m.group(1)}]]"

    text = re.sub(r"\[\[" + re.escape(old_id) + r"((?:\|[^\]]*)?)\]\]", link, text)
    fm, body = split(text) if text.startswith("---") else ("", text)
    if fm and re.search(r"(?<![\w:-])" + re.escape(old_id) + r"(?![\w-])", fm):
        meta = load_meta(fm)
        bo = meta.get("builds_on")
        if isinstance(bo, list) and old_id in bo:
            meta["builds_on"] = [new_id if b == old_id else b for b in bo]
            count += 1
            text = f"---\n{patch_front_matter(fm, meta)}\n---\n" + body
    return text, count


def write_page(path: Path, text: str) -> None:
    atomic_write(path, text)
