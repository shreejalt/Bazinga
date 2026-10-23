"""The Editor's handlers. ``server.py`` does the transport and the security checks; this file does the work.

GET handlers only read. Every POST handler receives the parsed JSON body (already checked for Origin, cookie and
content type) and returns a dict that becomes the JSON response; :class:`~bazinga.studio.security.Refused` turns into
an error status with a plain message.
"""
from __future__ import annotations

import ast
import base64
import binascii
import hashlib
import json
import keyword
import mimetypes
import re
import shutil
import tempfile
import threading
import time
from pathlib import Path

import yaml

from . import cite, engine, history, pages, publish
from .security import (IMAGE_TYPES, UPLOAD_LIMIT, Refused, atomic_write, confine, image_type)

STUDIO_DIR = Path(__file__).resolve().parent
STATIC_DIR = STUDIO_DIR / "static"
ENGINE_DIR = STUDIO_DIR.parent
_NAME = re.compile(r"^[a-z][a-z0-9_]{0,40}$")


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


class Editor:
    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self._cfg = None
        self._cfg_mtime = None
        self.buffers: dict[str, str] = {}          # id -> unsaved text, for the preview
        self._checks_cache: dict = {}
        self._lock = threading.RLock()

    # --- configuration ---------------------------------------------------------------------------------------------
    def cfg(self):
        from bazinga import config
        p = self.root / "site.yml"
        mtime = p.stat().st_mtime if p.exists() else None
        if self._cfg is None or mtime != self._cfg_mtime:
            config.set_root(self.root)
            self._cfg = config.load(self.root, local=True)
            self._cfg_mtime = mtime
        return self._cfg

    # --- reading ---------------------------------------------------------------------------------------------------
    def state(self, _q=None) -> dict:
        cfg = self.cfg()
        llm_on = False
        try:
            llm_on = bool(engine.module("llm").configured(cfg))
        except engine.Unavailable:
            pass
        except Exception:  # noqa: BLE001
            llm_on = False
        topics = {}
        refs = {}
        try:
            from bazinga import content
            topics = content.load_topics(cfg)
            refs = content.load_references(cfg)
        except Exception:  # noqa: BLE001
            pass
        kinds = [{"name": k, "label": v.get("label", k), "singular": v.get("singular", k),
                  "prefix": pages.page_id(cfg, k, "x")[:-2]} for k, v in cfg["kinds"].items()]
        return {
            "site": {"name": cfg["site"]["name"], "origin": cfg.origin, "author": cfg["site"]["author"]},
            "accent": cfg["theme"]["accent"],
            "kinds": kinds, "llm": llm_on,
            "available": {m: engine.available(m) for m in ("markdown", "checks", "build", "figures", "drawings",
                                                           "mathml", "wiki")},
            "topics": [{"slug": t["slug"], "label": t["label"], "group": t.get("group", "")} for t in topics.values()],
            "references": [{"key": k, "title": str(v.get("title", "")), "year": v.get("year"),
                            "authors": v.get("authors") or []} for k, v in refs.items()],
            "figures": self._figure_list(),
            "drawings": self._drawing_list(),
            "series": sorted({(r.get("series") or {}).get("name") for r in pages.list_pages(cfg)
                              if r.get("series")} - {None}),
            "publish": {"commit": bool(cfg["publish"].get("commit", True)),
                        "push": bool(cfg["publish"].get("push", True)),
                        "command": cfg["publish"].get("command") or ""},
        }

    def list_pages(self, _q=None) -> dict:
        return {"pages": pages.list_pages(self.cfg())}

    def get_page(self, q) -> dict:
        cfg = self.cfg()
        pid = q.get("id", "")
        path = pages.page_path(cfg, pid)
        if not path.exists():
            raise Refused(404, "That page does not exist (it may have been renamed).")
        text = path.read_text(encoding="utf-8")
        fm, body = pages.split(text)
        try:
            meta = pages.load_meta(fm)
            meta_error = None
        except yaml.YAMLError as exc:
            meta, meta_error = {}, f"The front matter is not valid YAML: {exc}"
        row = pages.summary_row(cfg, path)
        return {"id": pid, "kind": row["kind"], "slug": row["slug"], "path": row["path"], "url": row["url"],
                "state": row["state"], "meta": pages.to_json(meta), "body": body.lstrip("\n"),
                "hash": _hash(text), "mtime": path.stat().st_mtime, "meta_error": meta_error,
                "live_url": cfg.origin + row["url"]}

    def checks_summary(self, _q=None) -> dict:
        """Errors and warnings per page for the Library's badges (cached until something in content/ changes)."""
        cfg = self.cfg()
        try:
            checks = engine.module("checks")
        except engine.Unavailable as exc:
            return {"available": False, "note": str(exc), "pages": {}}
        files = list(cfg.content_dir.rglob("*")) if cfg.content_dir.exists() else []
        sig = max((f.stat().st_mtime for f in files if f.is_file()), default=0) + len(files)
        if self._checks_cache.get("sig") == sig:
            return self._checks_cache["result"]
        out = {}
        with engine.lock():
            from bazinga import content
            try:
                site = engine.site_index(cfg)
            except engine.Unavailable as exc:
                return {"available": False, "note": str(exc), "pages": {}}
            for path in content.content_files(cfg):
                try:
                    page = content.load_file(path, cfg)
                    issues = checks.check_page(page, site)
                    out[page.id] = {"errors": sum(i.level == "error" for i in issues),
                                    "warnings": sum(i.level != "error" for i in issues)}
                except Exception as exc:  # noqa: BLE001
                    kind, slug = content.kind_and_slug(path, cfg)
                    out[pages.page_id(cfg, kind, slug)] = {"errors": 1, "warnings": 0, "note": str(exc)}
        result = {"available": True, "pages": out}
        self._checks_cache = {"sig": sig, "result": result}
        return result

    def history_list(self, q) -> dict:
        cfg = self.cfg()
        pid = q.get("id", "")
        pages.page_path(cfg, pid)
        kind, slug = pages.kind_of(cfg, pid), pid.split(":", 1)[1]
        return {"versions": history.list_versions(self.root, kind, slug)}

    def history_read(self, q) -> dict:
        cfg = self.cfg()
        pid = q.get("id", "")
        pages.page_path(cfg, pid)
        kind, slug = pages.kind_of(cfg, pid), pid.split(":", 1)[1]
        text = history.read_version(self.root, kind, slug, q.get("name", ""))
        fm, body = pages.split(text)
        return {"meta": pages.to_json(pages.load_meta(fm)), "body": body.lstrip("\n")}

    def read_code(self, q) -> dict:
        kind, name = q.get("kind"), q.get("name", "")
        folder = {"figure": "figures", "drawing": "drawings"}.get(kind)
        if not folder or not _NAME.match(name):
            raise Refused(400, "Unknown file.")
        path = confine(self.root, f"{folder}/{name}.py")
        if not path.exists():
            raise Refused(404, f"{folder}/{name}.py does not exist.")
        return {"source": path.read_text(encoding="utf-8"), "path": f"{folder}/{name}.py"}

    def starters(self, _q=None) -> dict:
        out = {}
        for kind in ("figures", "drawings"):
            d = ENGINE_DIR / "starters" / kind
            items = []
            if d.is_dir():
                for p in sorted(d.glob("*.py")):
                    if p.name.startswith("_"):
                        continue
                    meta = _module_constants(p)
                    items.append({"name": p.stem, "title": meta.get("TITLE") or p.stem.replace("_", " ").capitalize(),
                                  "caption": meta.get("CAPTION", "")})
            out[kind] = items
        return out

    def _figure_list(self) -> list[dict]:
        d = self.root / "figures"
        out = []
        if d.is_dir():
            for p in sorted(d.glob("*.py")):
                if p.name.startswith("_"):
                    continue
                meta = _module_constants(p)
                out.append({"name": p.stem, "title": meta.get("TITLE") or p.stem,
                            "caption": meta.get("CAPTION", ""), "presets": meta.get("PRESETS_LABELS", [])})
        return out

    def _drawing_list(self) -> list[dict]:
        from .worker import drawing_functions
        d = self.root / "drawings"
        out = []
        if d.is_dir():
            for p in sorted(d.glob("*.py")):
                if p.name.startswith("_"):
                    continue
                out.append({"module": p.stem, "functions": drawing_functions(p)})
        return out

    # --- pages -----------------------------------------------------------------------------------------------------
    def _text_for(self, cfg, pid, data, path):
        meta = pages.normalise(data.get("meta") or {})
        body = data.get("body")
        if not isinstance(body, str):
            raise Refused(400, "The page text is missing.")
        original = path.read_text(encoding="utf-8") if path.exists() else None
        return pages.compose(meta, body, original), original

    def save_page(self, data) -> dict:
        cfg = self.cfg()
        pid = data.get("id", "")
        path = pages.page_path(cfg, pid)
        if not path.exists():
            raise Refused(404, "That page does not exist (it may have been renamed).")
        text, original = self._text_for(cfg, pid, data, path)
        base = data.get("base")
        if base and original is not None and _hash(original) != base and not data.get("force"):
            raise Refused(409, "This page was changed outside the Editor since you opened it.")
        kind, slug = pages.kind_of(cfg, pid), pid.split(":", 1)[1]
        if original is not None and original != text:
            history.snapshot(self.root, kind, slug, original, explicit=bool(data.get("explicit")))
        if original != text:
            pages.write_page(path, text)
        if data.get("explicit"):
            history.snapshot(self.root, kind, slug, text, explicit=True)
        self.buffers.pop(pid, None)
        return {"ok": True, "hash": _hash(text), "mtime": path.stat().st_mtime,
                "state": pages.summary_row(cfg, path)["state"]}

    def new_page(self, data) -> dict:
        cfg = self.cfg()
        title = " ".join(str(data.get("title") or "").split()) or "Untitled"
        kind = data.get("kind") or next(iter(cfg["kinds"]))
        if kind not in cfg["kinds"]:
            raise Refused(400, "Unknown kind of page.")
        slug = pages.unique_slug(cfg, kind, title)
        path = confine(self.root, f"content/{kind}/{slug}.md")
        text = pages.starter_text(title)
        if path.exists():
            raise Refused(409, "A page with that name already exists.")
        pages.write_page(path, text)
        return {"id": pages.page_id(cfg, kind, slug)}

    def rename_page(self, data) -> dict:
        cfg = self.cfg()
        pid = data.get("id", "")
        path = pages.page_path(cfg, pid)
        from bazinga import content
        new_slug = content.slugify(str(data.get("slug") or ""))
        kind = pages.kind_of(cfg, pid)
        new_id = pages.page_id(cfg, kind, new_slug)
        if new_id == pid:
            return {"id": pid, "changed": []}
        new_path = confine(self.root, f"content/{kind}/{new_slug}.md")
        if new_path.exists():
            raise Refused(409, f"{new_path.name} already exists; pick another name.")
        if not path.exists():
            raise Refused(404, "That page does not exist.")
        was_public = pages.summary_row(cfg, path)["state"] == "published"
        path.rename(new_path)
        history.move(self.root, kind, pid.split(":", 1)[1], new_slug)
        changed = []
        for other in content.content_files(cfg):
            text = other.read_text(encoding="utf-8")
            new_text, n = pages.rewrite_references(text, pid, new_id)
            if n:
                atomic_write(other, new_text)
                changed.append(str(other.relative_to(self.root)))
        # remember the old file so the next publish stages its removal -- only when git knows it (an untracked
        # page has nothing to remove, and naming it to `git add` would stop the publish)
        old_rel = str(path.relative_to(self.root))
        try:
            tracked = publish.git(self.root, "ls-files", "--error-unmatch", "--", old_rel,
                                  check=False).returncode == 0
        except (OSError, Exception):  # noqa: BLE001 - no git, or not a repository
            tracked = False
        renames = self.root / ".studio" / "renames.json"
        renames.parent.mkdir(exist_ok=True)
        try:
            data_r = json.loads(renames.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data_r = {}
        olds = data_r.pop(pid, [])
        data_r[new_id] = [o for o in olds + ([old_rel] if tracked else []) if o != str(new_path.relative_to(self.root))]
        atomic_write(renames, json.dumps(data_r, indent=1))
        self.buffers.pop(pid, None)
        note = (f"The live address changes from {cfg.origin}/{kind}/{pid.split(':', 1)[1]}/ to "
                f"{cfg.origin}/{kind}/{new_slug}/ when you publish again.") if was_public else ""
        return {"id": new_id, "changed": changed, "note": note}

    # --- rendering -------------------------------------------------------------------------------------------------
    def _page_from(self, data):
        cfg = self.cfg()
        pid = data.get("id", "")
        path = pages.page_path(cfg, pid)
        text, _ = self._text_for(cfg, pid, data, path)
        return cfg, pid, path, text

    def preview(self, data) -> dict:
        cfg, pid, path, text = self._page_from(data)
        self.buffers[pid] = text
        return self._render(cfg, path, text)

    def preview_get(self, pid: str) -> tuple[int, str]:
        cfg = self.cfg()
        path = pages.page_path(cfg, pid)
        text = self.buffers.get(pid)
        if text is None:
            if not path.exists():
                return 404, _message_page("Not found", "This page does not exist.")
            text = path.read_text(encoding="utf-8")
        r = self._render(cfg, path, text)
        if "html" in r:
            return 200, r["html"]
        return 200, _message_page("Preview", r.get("error", "The preview is not available."), r.get("hint", ""))

    def _render(self, cfg, path, text) -> dict:
        t = time.perf_counter()
        try:
            build = engine.module("build")
        except engine.Unavailable as exc:
            return {"error": str(exc), "unavailable": True}
        try:
            with engine.lock():
                page = engine.parse(cfg, path, text)
                html = build.preview_html(page, cfg)
        except engine.Unavailable as exc:
            return {"error": str(exc), "unavailable": True}
        except Exception as exc:  # noqa: BLE001 - shown above the preview, the last good one stays
            line = getattr(exc, "line", None)
            return {"error": getattr(exc, "message", None) or str(exc), "hint": getattr(exc, "hint", ""),
                    "line": line, "body_line": _body_line(text), "trace": engine.format_exc()}
        return {"html": html, "ms": round((time.perf_counter() - t) * 1000, 1)}

    def check(self, data) -> dict:
        cfg, pid, path, text = self._page_from(data)
        try:
            checks = engine.module("checks")
        except engine.Unavailable as exc:
            return {"available": False, "note": str(exc), "issues": []}
        try:
            with engine.lock():
                page = engine.parse(cfg, path, text)
                site = engine.site_index(cfg, override=page)
                issues = checks.check_page(page, site)
            body_line = page.body_line
        except engine.Unavailable as exc:
            return {"available": False, "note": str(exc), "issues": []}
        except Exception as exc:  # noqa: BLE001
            return {"available": True, "body_line": _body_line(text),
                    "issues": [{"level": "error", "line": getattr(exc, "line", None),
                                "message": getattr(exc, "message", None) or str(exc),
                                "hint": getattr(exc, "hint", ""), "code": "parse"}]}
        meta_lines = getattr(page, "meta_lines", {}) or {}
        out = []
        for i in issues:
            field = None
            if i.line is not None and i.line < body_line:
                field = next((k for k, v in meta_lines.items() if v == i.line), None)
            out.append({"level": i.level, "line": i.line, "message": i.message, "hint": getattr(i, "hint", ""),
                        "code": getattr(i, "code", ""), "field": field})
        return {"available": True, "body_line": body_line, "issues": out}

    def math(self, data) -> dict:
        """One formula (``tex``, ``display``) or many (``items: [{tex, display}]``, for the editor's hover and lint).

        Each result is ``{mathml, tag, label}`` or ``{error, hint, line, column, index, length}``; display formulas
        may carry \\tag and \\label, as in a page."""
        items = data.get("items")
        if items is not None:
            if not isinstance(items, list) or len(items) > 400:
                raise Refused(413, "Too many equations at once.")
            if sum(len(str((i or {}).get("tex") or "")) for i in items) > 200000:
                raise Refused(413, "Those equations are too long.")
        elif len(str(data.get("tex") or "")) > 20000:
            raise Refused(413, "That equation is too long.")
        try:
            mathml = engine.module("mathml")
        except engine.Unavailable as exc:
            return {"available": False, "error": str(exc)}

        def one(tex, display) -> dict:
            try:
                if hasattr(mathml, "check"):
                    res = mathml.check(tex, display)
                    if res["ok"]:
                        return {"mathml": res["mathml"], "tag": res.get("tag"), "label": res.get("label")}
                    e = res["error"]
                    return {"error": e["message"], "hint": e["hint"], "offset": e["line"], "line": e["line"],
                            "column": e["column"], "index": e["index"], "length": e["length"]}
                return {"mathml": mathml.to_mathml(tex, display)}
            except Exception as exc:  # noqa: BLE001 - MathError or a converter bug: both are shown, not raised
                return {"error": getattr(exc, "message", None) or str(exc), "hint": getattr(exc, "hint", ""),
                        "offset": getattr(exc, "offset", None), "line": getattr(exc, "offset", None),
                        "column": getattr(exc, "column", None), "index": getattr(exc, "index", None),
                        "length": getattr(exc, "length", 1)}

        if items is not None:
            return {"available": True, "results": [one(str((i or {}).get("tex") or ""), bool((i or {}).get("display")))
                                                   for i in items]}
        return {"available": True, **one(str(data.get("tex") or ""), bool(data.get("display", True)))}

    # --- figures and drawings --------------------------------------------------------------------------------------
    def figures_run(self, data) -> dict:
        names = [n for n in (data.get("names") or [data.get("name")]) if n]
        for n in names:
            if not _NAME.match(n):
                raise Refused(400, "Unknown figure.")
        if not engine.available("figures"):
            return {"available": False, "figures": []}
        res = engine.worker(self.root, "figure-run", {"names": names, "values": data.get("values")}, timeout=60)
        res["available"] = not res.get("unavailable")
        return res

    def _check_name(self, name: str, what: str) -> str:
        name = str(name or "").strip()
        if not _NAME.match(name) or keyword.iskeyword(name):
            raise Refused(400, f"A {what} name is lowercase letters, digits and _ , starting with a letter "
                               "(e.g. softmax_temperature).")
        return name

    def _starter(self, kind: str, starter: str) -> str:
        if not re.fullmatch(r"[a-z0-9_]+", starter or ""):
            raise Refused(400, "Unknown starter.")
        p = ENGINE_DIR / "starters" / kind / f"{starter}.py"
        if not p.exists():
            raise Refused(404, "That starter is not available yet.")
        return p.read_text(encoding="utf-8")

    def figure_new(self, data) -> dict:
        name = self._check_name(data.get("name"), "figure")
        path = confine(self.root, f"figures/{name}.py")
        if path.exists():
            raise Refused(409, f"A figure called {name} already exists.")
        src = self._starter("figures", data.get("starter", ""))
        title = str(data.get("title") or "").strip()
        if title:
            src = re.sub(r'^TITLE\s*=\s*.*$', "TITLE = " + json.dumps(title), src, count=1, flags=re.M)
        atomic_write(path, src)
        return {"name": name, "source": src, "path": f"figures/{name}.py"}

    def figure_save(self, data) -> dict:
        name = self._check_name(data.get("name"), "figure")
        src = data.get("source")
        if not isinstance(src, str) or len(src) > 400_000:
            raise Refused(400, "The figure's code is missing or too long.")
        path = confine(self.root, f"figures/{name}.py")
        if data.get("create") and path.exists():
            raise Refused(409, f"A figure called {name} already exists.")
        atomic_write(path, src)
        if not engine.available("figures"):
            return {"saved": True, "available": False, "ok": False, "problems": ["Figure tests are not available yet."]}
        res = engine.worker(self.root, "figure-test", {"name": name}, timeout=120)
        res["saved"] = True
        return res

    def figure_draft(self, data) -> dict:
        cfg = self.cfg()
        name = self._check_name(data.get("name"), "figure")
        desc = str(data.get("description") or "").strip()
        if not desc:
            raise Refused(400, "Describe the figure first.")
        try:
            llm = engine.module("llm")
            if not llm.configured(cfg):
                raise Refused(400, "Suggestions are off: set llm.model in site.yml and the key in .env.local.")
            src = llm.figure_draft(cfg, desc)
        except engine.Unavailable as exc:
            raise Refused(503, str(exc)) from None
        except Refused:
            raise
        except Exception as exc:  # noqa: BLE001
            raise Refused(502, f"The draft could not be made: {exc}") from None
        # Model-written code is never run before the author has read it: it comes back as text, and runs only when
        # the author presses Run (the figure check) or saves it. The gate says what in it a figure does not need.
        unsafe = draft_gate(src)
        problems = ["Written from your description and not run yet. Read it, then run it to test it."]
        if unsafe:
            problems.append("It does things a figure does not need: it " + "; it ".join(unsafe)
                            + ". Remove them before you run it.")
        return {"ok": False, "ran": False, "source": src, "problems": problems, "unsafe": unsafe}

    def _test_in_temp(self, op, args, rel, src) -> dict:
        """Test unsaved code in a throwaway site folder, so nothing is written until the author saves."""
        tmp = Path(tempfile.mkdtemp(prefix="bazinga-studio-"))
        try:
            for f in ("site.yml",):
                if (self.root / f).exists():
                    shutil.copy2(self.root / f, tmp / f)
            for folder in ("figures", "drawings"):
                if (self.root / folder).is_dir():
                    shutil.copytree(self.root / folder, tmp / folder,
                                    ignore=shutil.ignore_patterns("__pycache__"))
            (tmp / rel).parent.mkdir(parents=True, exist_ok=True)
            (tmp / rel).write_text(src, encoding="utf-8")
            return engine.worker(tmp, op, args, timeout=120)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def drawing_new(self, data) -> dict:
        module = self._check_name(data.get("module"), "drawing")
        path = confine(self.root, f"drawings/{module}.py")
        if path.exists():
            raise Refused(409, f"drawings/{module}.py already exists.")
        src = self._starter("drawings", data.get("starter", ""))
        atomic_write(path, src)
        return {"module": module, "source": src, "path": f"drawings/{module}.py"}

    def drawing_save(self, data) -> dict:
        module = self._check_name(data.get("module"), "drawing")
        src = data.get("source")
        if not isinstance(src, str) or len(src) > 400_000:
            raise Refused(400, "The drawing's code is missing or too long.")
        path = confine(self.root, f"drawings/{module}.py")
        if data.get("save", True):
            atomic_write(path, src)
        if not engine.available("drawings"):
            return {"saved": True, "available": False, "ok": False, "error": "Drawings are not available yet."}
        res = engine.worker(self.root, "drawing-test", {"module": module}, timeout=120)
        res["saved"] = True
        return res

    def drawing_preview(self, data) -> dict:
        module = self._check_name(data.get("module"), "drawing")
        if not engine.available("drawings"):
            return {"available": False, "ok": False, "functions": []}
        return engine.worker(self.root, "drawing-test", {"module": module}, timeout=120)

    # --- citations, topics, uploads --------------------------------------------------------------------------------
    def cite_lookup(self, data) -> dict:
        rec = cite.lookup(str(data.get("q") or ""))
        existing = cite.load(self.root)
        dup = next((k for k, v in existing.items() if isinstance(v, dict) and (
            (rec.get("arxiv") and str(v.get("arxiv")) == str(rec.get("arxiv")))
            or (rec.get("doi") and str(v.get("doi", "")).lower() == str(rec.get("doi")).lower()))), None)
        return {"record": rec, "key": dup or cite.suggest_key(rec, existing), "existing": dup}

    def cite_save(self, data) -> dict:
        rec = cite.save(self.root, str(data.get("key") or ""), data.get("record") or {})
        return {"ok": True, "key": data.get("key"), "record": rec}

    def topic_add(self, data) -> dict:
        from bazinga import content
        label = " ".join(str(data.get("label") or "").split())
        if not label or len(label) > 60:
            raise Refused(400, "Give the topic a short name.")
        slug = content.slugify(label)
        path = confine(self.root, "content/topics.yml")
        old = path.read_text(encoding="utf-8") if path.exists() else ""
        parsed = yaml.safe_load(old) or {}
        groups = parsed.get("groups") or []
        if any(t.get("slug") == slug for g in groups for t in (g.get("topics") or [])):
            return {"slug": slug, "label": label, "existed": True}
        blurb = " ".join(str(data.get("blurb") or "").split())
        item = f"      - {{slug: {slug}, label: {json.dumps(label)}" + (
            f", blurb: {json.dumps(blurb)}" if blurb else "") + "}\n"
        if not old.strip():
            new = "groups:\n  - name: Topics\n    topics:\n" + item
        elif groups and groups[-1].get("name") == "New topics" and old.rstrip().endswith("}"):
            new = old.rstrip("\n") + "\n" + item
        else:
            new = old.rstrip("\n") + "\n  - name: New topics\n    topics:\n" + item
        check = yaml.safe_load(new) or {}
        if not any(t.get("slug") == slug for g in check.get("groups") or [] for t in g.get("topics") or []):
            raise Refused(500, "topics.yml could not be extended safely; add the topic by hand.")
        atomic_write(path, new)
        return {"slug": slug, "label": label}

    def upload(self, data) -> dict:
        cfg = self.cfg()
        raw = data.get("data") or ""
        if "," in raw[:100] and raw.startswith("data:"):
            raw = raw.split(",", 1)[1]
        if len(raw) > UPLOAD_LIMIT * 4 // 3 + 8:
            raise Refused(413, f"Images can be at most {UPLOAD_LIMIT // (1024 * 1024)} MB.")
        try:
            blob = base64.b64decode(raw, validate=True)
        except (binascii.Error, ValueError):
            raise Refused(400, "The image could not be read.") from None
        if len(blob) > UPLOAD_LIMIT:
            raise Refused(413, f"Images can be at most {UPLOAD_LIMIT // (1024 * 1024)} MB.")
        kind = image_type(blob)
        if kind is None:
            raise Refused(415, "Only PNG, JPEG, GIF, WebP and AVIF images can be uploaded.")
        from bazinga import content
        stem = content.slugify(Path(str(data.get("name") or "image")).stem)[:50] or "image"
        prefix = content.slugify(str(data.get("slug") or ""))[:40]
        base = f"{prefix}-{stem}" if prefix and not stem.startswith(prefix) else stem
        name, n = f"{base}.{kind}", 2
        while (self.root / "static" / "uploads" / name).exists():
            name, n = f"{base}-{n}.{kind}", n + 1
        path = confine(self.root, f"static/uploads/{name}")
        atomic_write(path, blob)
        return {"path": f"static/uploads/{name}", "bytes": len(blob), "type": kind}

    # --- suggestions -----------------------------------------------------------------------------------------------
    def _llm(self):
        cfg = self.cfg()
        try:
            llm = engine.module("llm")
        except engine.Unavailable as exc:
            raise Refused(503, str(exc)) from None
        if not llm.configured(cfg):
            raise Refused(400, "Suggestions are off: set llm.model in site.yml and the key in .env.local.")
        return cfg, llm

    def llm_describe(self, data) -> dict:
        cfg, llm = self._llm()
        _, pid, path, text = self._page_from(data)
        page = engine.parse(cfg, path, text)
        try:
            return {"description": str(llm.describe(cfg, page)).strip()}
        except Exception as exc:  # noqa: BLE001
            raise Refused(502, f"No suggestion this time: {exc}") from None

    def llm_equation(self, data) -> dict:
        cfg, llm = self._llm()
        words = str(data.get("words") or "").strip()
        if not words:
            raise Refused(400, "Describe the equation in words first.")
        try:
            return {"tex": str(llm.equation(cfg, words)).strip()}
        except Exception as exc:  # noqa: BLE001
            raise Refused(502, f"No suggestion this time: {exc}") from None

    def llm_ingest(self, data) -> dict:
        cfg, llm = self._llm()
        _, pid, path, text = self._page_from(data)
        page = engine.parse(cfg, path, text)
        try:
            proposals = llm.ingest(cfg, page)
        except Exception as exc:  # noqa: BLE001
            raise Refused(502, f"No suggestions this time: {exc}") from None
        return {"proposals": pages.to_json(proposals if isinstance(proposals, dict) else {})}

    # --- publish ---------------------------------------------------------------------------------------------------
    def publish_prepare(self, data) -> dict:
        return publish.prepare(self.cfg(), data.get("id", ""), data.get("mode", "publish"), data.get("date"))

    def publish_run(self, data, emit) -> dict:
        mode = data.get("mode", "publish")
        if mode not in ("publish", "unpublish", "schedule"):
            raise Refused(400, "Unknown publish mode.")
        accepted = [str(a)[:300] for a in (data.get("accepted") or [])][:50]
        opts = publish.Options(mode=mode, date=data.get("date"), dry_run=bool(data.get("dry_run")),
                               accept_warnings=bool(data.get("accept_warnings")), accepted=accepted)
        self._checks_cache = {}
        return publish.run(self.cfg(), data.get("id", ""), opts, emit)

    def frame(self, kind: str, ref: str, q: dict) -> tuple[int, str]:
        """A small page holding one figure (with working controls) or one drawing, styled like the site."""
        import html as _html
        if kind == "figure":
            if not _NAME.match(ref):
                raise Refused(404, "Unknown figure.")
            res = engine.worker(self.root, "figure-html", {"name": ref, "start": q.get("start")}, timeout=60)
        else:
            if not re.fullmatch(r"[a-z][a-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*", ref):
                raise Refused(404, "Unknown drawing.")
            res = engine.worker(self.root, "drawing-html", {"ref": ref, "caption": q.get("caption", "")}, timeout=60)
        theme = q.get("theme") if q.get("theme") in ("light", "dark") else ""
        if res.get("ok"):
            inner = res["html"]
        else:
            detail = res.get("traceback") or res.get("error") or "unknown problem"
            inner = ('<div class="frame-error"><strong>This could not be drawn.</strong><pre>'
                     + _html.escape(str(detail)[-3000:]) + "</pre></div>")
        css = "".join(f'<link rel="stylesheet" href="/assets/css/{n}">' for n in
                      ("tokens.css", "figure.css", "math.css", "site.css", "diagram.css") if (ENGINE_DIR / "theme/assets/css" / n).exists()
                      or (self.root / "theme/assets/css" / n).exists())
        js = '<script src="/assets/js/figure.js" defer></script>' if kind == "figure" else ""
        return 200, ("<!doctype html><html lang=en" + (f' data-theme="{theme}"' if theme else "") + "><head>"
                     "<meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
                     + css + "<style>body{margin:0;padding:12px 16px;background:var(--bg,transparent)}"
                     ".fig,figure{margin:0!important;max-width:none!important}"
                     ".frame-error{font:13px/1.5 ui-monospace,monospace;color:#b3261e}"
                     ".frame-error pre{white-space:pre-wrap}</style></head><body class=studio-frame>"
                     + inner + js + "</body></html>")

    # --- files for the preview -------------------------------------------------------------------------------------
    def generated_asset(self, path: str) -> tuple[str, str] | None:
        """Assets the build generates instead of copying (the code highlighting colours)."""
        if path == "/assets/css/pygments.css":
            try:
                return engine.module("markdown").pygments_css(), "text/css; charset=utf-8"
            except Exception:  # noqa: BLE001
                return "", "text/css; charset=utf-8"
        return None

    def preview_file(self, path: str) -> Path | None:
        """Files the preview page asks for: theme assets, static files, figure modules, generated data."""
        cfg = self.cfg()
        m = re.match(r"^/assets/(.+)$", path)
        if m:
            rel = m.group(1)
            for base in (self.root / "theme" / "assets", ENGINE_DIR / "theme" / "assets"):
                p = _inside(base, rel)
                if p:
                    return p
            return None
        m = re.match(r"^(?:/.*)?/static/(.+)$", path)
        if m:
            return _inside(cfg.static_dir, m.group(1))
        m = re.match(r"^/figures/_(plot|retrieve|scene3d)\.py$", path)
        if m:
            return _inside(ENGINE_DIR, f"{m.group(1)}.py")
        m = re.match(r"^/figures/([a-z][a-z0-9_]*)\.py$", path)
        if m:
            own = _inside(cfg.figures_dir, f"{m.group(1)}.py")
            if own or not m.group(1).startswith("starter_"):
                return own
            return _inside(ENGINE_DIR / "starters" / "figures", f"{m.group(1)[len('starter_'):]}.py")   # ::figure starter_x
        m = re.match(r"^/data/((?:view/)?[a-z0-9][a-z0-9_-]*\.(?:json|js))$", path)
        if m:   # what the last build generated: search passages, the map, hover cards (site.js), per-page views
            return _inside(cfg.out_dir / "data", m.group(1))
        return None

    def route_page(self, path: str) -> str | None:
        """``/posts/x/`` (a link inside the preview) -> the page id, when that page exists."""
        cfg = self.cfg()
        m = re.match(r"^/([a-z][a-z0-9-]*)/([a-z0-9][a-z0-9-]*)/?$", path)
        if m and m.group(1) in cfg["kinds"]:
            pid = pages.page_id(cfg, m.group(1), m.group(2))
            if (cfg.content_dir / m.group(1) / f"{m.group(2)}.md").exists():
                return pid
        return None


# What a model-written figure may use. Everything else is reported, and the draft is not run until it is gone.
DRAFT_IMPORTS = {"math", "random", "statistics", "__future__"}
DRAFT_KITS = {"bazinga.scene3d", "bazinga.plot"}
DRAFT_NUMPY = {"numpy"}                  # only when the figure declares REQUIRES = ["numpy"]
DRAFT_NAMES = {"open", "exec", "eval", "compile", "__import__", "globals", "locals", "vars", "input", "breakpoint",
               "memoryview", "getattr", "setattr", "delattr", "hasattr", "type", "object", "super", "classmethod",
               "staticmethod", "property", "help", "exit", "quit", "dir", "id", "__builtins__", "__loader__",
               "__spec__"}
# numpy functions that read or write files, run code or reach outside the figure
NUMPY_BLOCKED = {"load", "loads", "save", "savez", "savez_compressed", "savetxt", "loadtxt", "genfromtxt", "fromfile",
                 "tofile", "memmap", "fromregex", "DataSource", "lib", "ctypeslib", "testing", "f2py", "distutils",
                 "show_config", "get_include", "dump", "dumps", "frombuffer", "from_dlpack", "info", "source",
                 "who", "lookfor", "char", "rec", "ma", "polynomial", "emath", "typing", "core", "_core"}


def _declared_requires(tree) -> list[str]:
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "REQUIRES" for t in node.targets):
            try:
                value = ast.literal_eval(node.value)
            except ValueError:
                return []
            return [str(v) for v in value] if isinstance(value, (list, tuple)) else []
    return []


def draft_gate(src: str) -> list[str]:
    """What in model-written figure code a figure does not need (empty: plain computation with the allowed modules).

    An allowlist: imports of math, random, statistics and the figure kits (bazinga.scene3d, bazinga.plot) only, numpy
    only when the figure declares ``REQUIRES = ["numpy"]`` and then without its file and code functions; no
    getattr/eval/exec/open and friends, and no double-underscore names or attributes."""
    try:
        tree = ast.parse(src)
    except SyntaxError as exc:
        return [f"has a syntax error on line {exc.lineno}"]
    allowed = set(DRAFT_IMPORTS)
    if "numpy" in _declared_requires(tree):
        allowed |= DRAFT_NUMPY
    numpy_names = set()
    out = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                if a.name in allowed or a.name in DRAFT_KITS:
                    if a.name == "numpy":
                        numpy_names.add(a.asname or "numpy")
                else:
                    out.append(f"imports {a.name}")
        elif isinstance(n, ast.ImportFrom):
            mod = n.module or ""
            if n.level:
                out.append("uses a relative import")
            elif mod == "bazinga":
                for a in n.names:
                    if f"bazinga.{a.name}" not in DRAFT_KITS:
                        out.append(f"imports bazinga.{a.name}")
            elif mod in DRAFT_KITS or mod in allowed:
                for a in n.names:
                    if a.name == "*" or a.name.startswith("_"):
                        out.append(f"imports {a.name} from {mod}")
                    elif mod == "numpy" and a.name in NUMPY_BLOCKED:
                        out.append(f"imports numpy.{a.name}")
            else:
                out.append(f"imports {mod}")
        elif isinstance(n, ast.Name):
            if n.id in DRAFT_NAMES:
                out.append(f"uses {n.id}")
            elif n.id.startswith("__") and n.id != "__name__":
                out.append(f"uses {n.id}")
        elif isinstance(n, ast.Attribute):
            if n.attr.startswith("_"):
                out.append(f"reaches into .{n.attr}")
            elif n.attr in NUMPY_BLOCKED and isinstance(n.value, ast.Name) and n.value.id in numpy_names:
                out.append(f"uses {n.value.id}.{n.attr}")
            elif n.attr in ("tofile", "dump", "dumps"):
                out.append(f"uses .{n.attr}")
        elif isinstance(n, (ast.Global, ast.Nonlocal)):
            pass
    return list(dict.fromkeys(out))


def _inside(base: Path, rel: str) -> Path | None:
    base = Path(base).resolve()
    if "\x00" in rel or rel.startswith("/"):
        return None
    p = (base / rel).resolve()
    try:
        p.relative_to(base)
    except ValueError:
        return None
    return p if p.is_file() else None


def _module_constants(path: Path) -> dict:
    """TITLE, CAPTION (and preset labels) read without running the module."""
    out = {}
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, OSError, UnicodeDecodeError):
        return out
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            if name in ("TITLE", "CAPTION", "PRESETS"):
                try:
                    value = ast.literal_eval(node.value)
                except ValueError:
                    continue
                if name == "PRESETS" and isinstance(value, list):
                    out["PRESETS_LABELS"] = [p.get("label") for p in value if isinstance(p, dict)]
                elif isinstance(value, str):
                    out[name] = value
    return out


def _body_line(text: str) -> int:
    try:
        from bazinga import content
        return content.split_front_matter(text)[2]
    except Exception:  # noqa: BLE001
        return 1


def _message_page(title: str, message: str, hint: str = "") -> str:
    import html
    return ("<!doctype html><meta charset=utf-8><title>" + html.escape(title) + "</title>"
            "<style>body{font:16px/1.6 system-ui,sans-serif;color:#555;margin:0;display:grid;place-items:center;"
            "min-height:100vh;background:#fbfaf8}@media(prefers-color-scheme:dark){body{background:#161514;"
            "color:#aaa}}div{max-width:30em;padding:2em;text-align:center}</style><div><p>"
            + html.escape(message) + "</p>" + (f"<p><small>{html.escape(hint)}</small></p>" if hint else "")
            + "</div>")


def guess_type(path: Path) -> str:
    t = mimetypes.guess_type(str(path))[0]
    if path.suffix in (".js", ".mjs"):
        return "text/javascript; charset=utf-8"
    if path.suffix == ".py":
        return "text/plain; charset=utf-8"
    if path.suffix in (".css",):
        return "text/css; charset=utf-8"
    if path.suffix in (".html",):
        return "text/html; charset=utf-8"
    if path.suffix in (".svg",):
        return "image/svg+xml"
    return t or "application/octet-stream"


_ = IMAGE_TYPES  # imported for callers that list the allowed types

# The figure panel (gallery, figure builder, checking unsaved code) lives in figpanel.py.
from . import figpanel as _figpanel  # noqa: E402
_figpanel.install(Editor)

# The diagram panel (text diagrams drawn as you type) lives in diagrampanel.py.
from . import diagrampanel as _diagrampanel  # noqa: E402
_diagrampanel.install(Editor)
