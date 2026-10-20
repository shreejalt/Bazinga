"""The Studio's figure panel: the gallery, the figure builder (a form that writes the figure file), and checking code
before it is saved. Installed onto :class:`tessera.studio.api.Studio` by :func:`install`.

Unsaved work (the builder's current form, code typed but not saved) is written to ``.studio/drafts/figures/`` and
tested there by the worker, so nothing reaches ``figures/`` until the author saves. The preview frame of a draft is
``/frame/draft/<name>``; its figure loads its code from ``/_draft/figures/<name>.py``.
"""
from __future__ import annotations

import html as _html
import re
import shutil
import threading
from pathlib import Path

from . import engine
from .security import Refused, atomic_write, confine

_NAME = re.compile(r"^[a-z][a-z0-9_]{0,40}$")
ENGINE_DIR = Path(__file__).resolve().parent.parent
MAX_SOURCE = 400_000


class FigurePanel:
    """Mixed into Studio. Every public method is a route (see server.py)."""

    # --- places ------------------------------------------------------------------------------------------------
    def _drafts_root(self) -> Path:
        d = self.root / ".studio" / "drafts"
        (d / "figures").mkdir(parents=True, exist_ok=True)
        site = self.root / "site.yml"
        if site.exists():
            try:
                if not (d / "site.yml").exists() or (d / "site.yml").read_bytes() != site.read_bytes():
                    shutil.copyfile(site, d / "site.yml")
            except OSError:
                pass
        return d

    def _fig_name(self, name) -> str:
        name = str(name or "").strip()
        if not _NAME.match(name):
            raise Refused(400, "A figure name is lowercase letters, digits and _ , starting with a letter "
                               "(e.g. damped_wave).")
        return self._check_name(name, "figure")

    def _draft_state(self):
        if not hasattr(self, "_drafts"):
            self._drafts = {}            # name -> {"html", "n"}
            self._drafts_lock = threading.Lock()
        return self._drafts

    def _remember_draft(self, name, res) -> str:
        drafts = self._draft_state()
        with self._drafts_lock:
            n = drafts.get(name, {}).get("n", 0) + 1
            drafts[name] = {"html": res.get("html"), "error": res.get("html_error"), "n": n}
        return f"/frame/draft/{name}?v={n}"

    # --- reading -----------------------------------------------------------------------------------------------
    def builder_info(self, _q=None) -> dict:
        try:
            fb = engine.module("figbuilder")
        except engine.Unavailable as exc:
            return {"available": False, "error": str(exc)}
        out = fb.describe()
        out["available"] = True
        return out

    def figures_gallery(self, _q=None) -> dict:
        if not engine.available("figures"):
            return {"available": False, "figures": []}
        res = engine.worker(self.root, "figure-gallery", {}, timeout=90)
        uses = self._figure_uses()
        for f in res.get("figures", []):
            f["used_in"] = uses.get(f["name"], [])
        res["available"] = True
        return res

    def _figure_uses(self) -> dict:
        cfg = self.cfg()
        out: dict = {}
        content = Path(cfg.content_dir)
        if not content.is_dir():
            return out
        for p in sorted(content.rglob("*.md")):
            try:
                text = p.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            title = None
            for m in re.finditer(r"^\s*::figure\s+([a-z][a-z0-9_]*)", text, re.M):
                if title is None:
                    t = re.search(r'^title:\s*"?(.*?)"?\s*$', text, re.M)
                    title = t.group(1) if t else p.stem
                lst = out.setdefault(m.group(1), [])
                if title not in lst:
                    lst.append(title)
        return out

    def figure_open(self, q) -> dict:
        name = self._fig_name(q.get("name"))
        path = confine(self.root, f"figures/{name}.py", write=False)
        if not path.exists():
            raise Refused(404, f"figures/{name}.py does not exist.")
        src = path.read_text(encoding="utf-8")
        out = {"name": name, "source": src, "path": f"figures/{name}.py", "made": "code"}
        try:
            fb = engine.module("figbuilder")
            info = fb.read_spec(src)
            if info:
                out["made"] = "edited" if info["edited"] else "builder"
                out["spec"] = info["spec"]
        except engine.Unavailable:
            pass
        return out

    # --- the builder -------------------------------------------------------------------------------------------
    def _generate(self, spec):
        try:
            fb = engine.module("figbuilder")
        except engine.Unavailable as exc:
            raise Refused(503, str(exc)) from None
        if not isinstance(spec, dict):
            raise Refused(400, "The form is missing.")
        problems = fb.validate(spec)
        if problems:
            return None, problems
        return fb.generate(spec), []

    def builder_preview(self, data) -> dict:
        """Check the form; when it is fine, write the draft, test it and give the preview frame."""
        name = self._fig_name(data.get("name") or "draft")
        src, problems = self._generate(data.get("spec"))
        if problems:
            return {"ok": False, "problems": problems}
        return self._test_draft(name, src)

    def builder_save(self, data) -> dict:
        name = self._fig_name(data.get("name"))
        src, problems = self._generate(data.get("spec"))
        if problems:
            return {"ok": False, "saved": False, "problems": problems}
        path = confine(self.root, f"figures/{name}.py")
        if path.exists():
            if data.get("create"):
                raise Refused(409, f"A figure called {name} already exists. Pick another name.")
            fb = engine.module("figbuilder")
            info = fb.read_spec(path.read_text(encoding="utf-8"))
            if (info is None or info["edited"]) and not data.get("replace"):
                raise Refused(409, "This figure's code was written or changed by hand. Saving the form would "
                                   "replace that code.")
        atomic_write(path, src)
        res = engine.worker(self.root, "figure-report", {"name": name, "html": False}, timeout=120)
        return {"ok": bool(res.get("ok")), "saved": True, "name": name, "source": src,
                "report": res.get("report") or _plain_failure(res), "frame": f"/frame/figure/{name}"}

    # --- code --------------------------------------------------------------------------------------------------
    def figure_check(self, data) -> dict:
        """Test code that is not saved yet (the editor's live preview)."""
        name = self._fig_name(data.get("name"))
        src = data.get("source")
        if not isinstance(src, str) or len(src) > MAX_SOURCE:
            raise Refused(400, "The figure's code is missing or too long.")
        return self._test_draft(name, src)

    def figure_save_code(self, data) -> dict:
        name = self._fig_name(data.get("name"))
        src = data.get("source")
        if not isinstance(src, str) or len(src) > MAX_SOURCE:
            raise Refused(400, "The figure's code is missing or too long.")
        path = confine(self.root, f"figures/{name}.py")
        if data.get("create") and path.exists():
            raise Refused(409, f"A figure called {name} already exists. Pick another name.")
        atomic_write(path, src)
        if not engine.available("figures"):
            return {"saved": True, "ok": False, "report": {"ok": False, "checks": [], "problems": [
                "Figure tests are not available yet."]}}
        res = engine.worker(self.root, "figure-report", {"name": name, "html": False}, timeout=120)
        made = "code"
        try:
            made = engine.module("figures").made_with(src)
        except engine.Unavailable:
            pass
        return {"saved": True, "ok": bool(res.get("ok")), "name": name, "made": made,
                "report": res.get("report") or _plain_failure(res), "frame": f"/frame/figure/{name}"}

    def _test_draft(self, name, src) -> dict:
        root = self._drafts_root()
        atomic_write(root / "figures" / f"{name}.py", src)
        res = engine.worker(root, "figure-report", {"name": name}, timeout=60)
        report = res.get("report") or _plain_failure(res)
        out = {"ok": bool(res.get("ok")), "problems": [], "source": src, "report": report}
        if res.get("html"):
            out["frame"] = self._remember_draft(name, res)
        return out

    # --- the draft frame and its files -------------------------------------------------------------------------
    def draft_frame(self, name: str, q: dict) -> tuple[int, str]:
        if not _NAME.match(name):
            raise Refused(404, "Unknown figure.")
        d = self._draft_state().get(name)
        if not d or not d.get("html"):
            inner = ('<div class="frame-error"><strong>Nothing to show yet.</strong><pre>'
                     + _html.escape(str((d or {}).get("error") or "The figure has not been checked yet.")) + "</pre></div>")
        else:
            inner = d["html"]
        theme = q.get("theme") if q.get("theme") in ("light", "dark") else ""
        css = "".join(f'<link rel="stylesheet" href="/assets/css/{n}">' for n in
                      ("tokens.css", "site.css", "math.css", "figure.css")
                      if (ENGINE_DIR / "theme/assets/css" / n).exists() or (self.root / "theme/assets/css" / n).exists())
        return 200, ("<!doctype html><html lang=en" + (f' data-theme="{theme}"' if theme else "") + "><head>"
                     "<meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
                     '<meta name="tessera-root" content="/_draft/">'
                     + css + "<style>body{margin:0;padding:12px 16px;background:var(--bg,transparent)}"
                     ".fig,figure{margin:0!important;max-width:none!important}"
                     ".frame-error{font:13px/1.5 ui-monospace,monospace;color:#b3261e}"
                     ".frame-error pre{white-space:pre-wrap}</style></head><body class=studio-frame>"
                     + inner + '<script src="/assets/js/figure.js" defer></script></body></html>')

    def draft_file(self, path: str) -> Path | None:
        """/_draft/figures/<name>.py (a draft's code) and /_draft/figures/_plot.py (the renderer)."""
        m = re.fullmatch(r"/_draft/figures/(_plot|[a-z][a-z0-9_]*)\.py", path)
        if not m:
            return None
        if m.group(1) == "_plot":
            p = ENGINE_DIR / "plot.py"
        else:
            p = self.root / ".studio" / "drafts" / "figures" / f"{m.group(1)}.py"
        return p if p.is_file() else None


def _plain_failure(res) -> dict:
    text = res.get("error") or res.get("stderr") or "The test could not run."
    return {"ok": False, "problems": [text], "checks": [{"label": "The test ran", "ok": False, "detail": text}],
            "line": None}


def install(cls):
    """Add the figure panel's routes to the Studio class."""
    for key, value in vars(FigurePanel).items():
        if not key.startswith("__") and not hasattr(cls, key):
            setattr(cls, key, value)
    return cls
