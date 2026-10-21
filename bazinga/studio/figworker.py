"""The figure panel's operations, run by :mod:`bazinga.studio.worker` in a fresh interpreter (cwd = a site root).

``figure-report``  the figure test in plain checks, plus the figure's HTML for the preview frame
``figure-gallery`` every figure drawn at its starting values (the panel's thumbnails)
"""
from __future__ import annotations

import time
import traceback
from pathlib import Path


def _cfg():
    from bazinga import config
    config.set_root(Path.cwd())
    return config.load(Path.cwd())


def op_figure_report(args):
    cfg = _cfg()
    from bazinga import figures
    name = args["name"]
    t0 = time.perf_counter()
    try:
        report = figures.test_report(name, cfg)
    except Exception:  # noqa: BLE001 - shown to the author as it is
        text = traceback.format_exc(limit=6)
        return {"ok": False, "report": {"ok": False, "problems": [text], "line": figures.line_of(text),
                                        "checks": [{"label": "The test ran", "ok": False, "detail": text}]}}
    out = {"ok": report["ok"], "report": report, "ms": round((time.perf_counter() - t0) * 1000)}
    path = Path(cfg.figures_dir) / f"{name}.py"
    if path.exists():
        out["made"] = figures.made_with(path.read_text(encoding="utf-8"))
    if args.get("html", True):
        try:
            out["html"] = figures.figure_html(name, start=args.get("start") or None, cfg=cfg)
        except Exception as exc:  # noqa: BLE001
            out["html_error"] = str(exc)
    return out


def op_figure_gallery(args):
    cfg = _cfg()
    from bazinga import figures
    items = []
    for name, path in figures.discover(cfg).items():
        item = {"name": name, "made": figures.made_with(path.read_text(encoding="utf-8"))}
        try:
            mod = figures.load(name, cfg)
            item.update(title=mod.TITLE, caption=getattr(mod, "CAPTION", ""),
                        controls=len(figures.controls(mod)),
                        presets=[p["label"] for p in figures.presets(mod)])
            r = figures.run(name, None, 0, cfg)
            item.update(ok=True, svg=r["svg"], ms=round(r["ms"], 1))
        except Exception as exc:  # noqa: BLE001
            item.update(ok=False, error=str(exc), title=item.get("title", name))
        items.append(item)
    return {"ok": True, "figures": items}


OPS = {"figure-report": op_figure_report, "figure-gallery": op_figure_gallery}
