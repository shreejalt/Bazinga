"""One engine operation in a fresh interpreter: ``python -m bazinga.studio.worker <op> '<json args>'``.

The current directory is the site root. Running figures and drawings here means an edited module is always imported
fresh, an endless loop can be stopped with a timeout, and a publish dry run can use a temporary copy of the site.
The result is printed as one JSON line after a marker (anything the author's code prints comes before it).
"""
from __future__ import annotations

import ast
import json
import sys
import time
import traceback
from pathlib import Path

MARK = "\x1eBAZINGA-RESULT "


def _cfg():
    from bazinga import config
    config.set_root(Path.cwd())
    return config.load(Path.cwd())


def op_figure_test(args):
    cfg = _cfg()
    from bazinga import figures
    name = args["name"]
    try:
        problems = figures.test_figure(name)
    except Exception:  # noqa: BLE001
        return {"ok": False, "problems": [traceback.format_exc(limit=6)]}
    result = {"ok": not problems, "problems": list(problems)}
    if not problems and args.get("preview", True):
        try:
            result.update(figures.run(name))
            mod = figures.load(name, cfg)
            result["title"] = getattr(mod, "TITLE", name)
            result["caption"] = getattr(mod, "CAPTION", "")
        except Exception:  # noqa: BLE001
            result.update(ok=False, problems=[traceback.format_exc(limit=6)])
    return result


def op_figure_run(args):
    cfg = _cfg()
    from bazinga import figures
    out = []
    for name in args.get("names") or [args.get("name")]:
        try:
            r = figures.run(name, args.get("values"), int(args.get("narrow") or 0))
            mod = figures.load(name, cfg)
            r.update(name=name, ok=True, title=getattr(mod, "TITLE", name), caption=getattr(mod, "CAPTION", ""))
        except Exception as exc:  # noqa: BLE001
            r = {"name": name, "ok": False, "error": f"{type(exc).__name__}: {exc}",
                 "traceback": traceback.format_exc(limit=6)}
        out.append(r)
    return {"ok": all(r["ok"] for r in out), "figures": out}


def op_figure_html(args):
    cfg = _cfg()
    from bazinga import figures
    try:
        return {"ok": True, "html": figures.figure_html(args["name"], start=args.get("start") or None, cfg=cfg)}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"{exc}", "traceback": traceback.format_exc(limit=6)}


def op_drawing_html(args):
    _cfg()
    from bazinga import drawings
    try:
        return {"ok": True, "html": drawings.drawing_html(args["ref"], args.get("caption", ""))}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"{exc}", "traceback": traceback.format_exc(limit=6)}


def drawing_functions(path: Path) -> list[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return []
    return [n.name for n in tree.body if isinstance(n, ast.FunctionDef) and not n.name.startswith("_")]


def op_drawing_test(args):
    _cfg()
    from bazinga import drawings
    module = args["module"]
    path = Path.cwd() / "drawings" / f"{module}.py"
    if not path.exists():
        return {"ok": False, "error": f"drawings/{module}.py does not exist"}
    try:
        compile(path.read_text(encoding="utf-8"), str(path), "exec")
    except SyntaxError:
        return {"ok": False, "error": traceback.format_exc(limit=2), "functions": []}
    fns = []
    for fn in drawing_functions(path):
        t = time.perf_counter()
        try:
            html = drawings.drawing_html(f"{module}.{fn}", args.get("caption", ""))
            fns.append({"fn": fn, "ok": True, "html": html, "ms": round((time.perf_counter() - t) * 1000, 1)})
        except Exception:  # noqa: BLE001
            fns.append({"fn": fn, "ok": False, "error": traceback.format_exc(limit=6)})
    if not fns:
        return {"ok": False, "error": "This file has no drawing functions (def name(): return an SVG).",
                "functions": []}
    return {"ok": all(f["ok"] for f in fns), "functions": fns}


def op_log(args):
    cfg = _cfg()
    from bazinga import wiki
    wiki.append_log(cfg, args["op"], args["subject"])
    return {"ok": True}


def op_used_figure_tests(args):
    """Run the contract tests of several figures (publish step 3)."""
    _cfg()
    from bazinga import figures
    results = []
    for name in args.get("names", []):
        try:
            problems = list(figures.test_figure(name))
        except Exception:  # noqa: BLE001
            problems = [traceback.format_exc(limit=6)]
        results.append({"name": name, "problems": problems})
    return {"ok": all(not r["problems"] for r in results), "results": results}


OPS = {"figure-test": op_figure_test, "figure-run": op_figure_run, "drawing-test": op_drawing_test,
       "log": op_log, "figure-tests": op_used_figure_tests, "figure-html": op_figure_html,
       "drawing-html": op_drawing_html}

from .figworker import OPS as _FIGURE_PANEL_OPS  # noqa: E402  (the figure panel's operations)
OPS.update(_FIGURE_PANEL_OPS)


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    op = argv[0] if argv else ""
    args = json.loads(argv[1]) if len(argv) > 1 else {}
    fn = OPS.get(op)
    if fn is None:
        result = {"ok": False, "error": f"unknown operation {op!r}"}
    else:
        try:
            result = fn(args)
        except ModuleNotFoundError as exc:
            result = {"ok": False, "unavailable": True, "error": f"not available yet ({exc.name})"}
        except Exception:  # noqa: BLE001
            result = {"ok": False, "error": traceback.format_exc(limit=8)}
    sys.stdout.write("\n" + MARK + json.dumps(result, default=str) + "\n")
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
