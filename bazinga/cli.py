"""The command line: ``python -m bazinga <command>``.

    new "Title" [--kind posts]        a new draft from bazinga/starters/post.md
    build [--drafts]                  build _site/ (drafts only with --drafts, for private previews)
    serve [--port 8000]               build, watch, live-reload, /api/ask/ locally, and the Editor behind a
                                      "Write" button (local only; --no-editor leaves it out)
    editor                            the Editor, the local writing window (127.0.0.1 only; "studio" also works)
    check [file ...]                  run the checks; exit code 1 when there are errors
    figure new <name> --from <starter|builder[:type]> | figure starters | figure test [name] | figure preview <name> | figure list
    cite <arxiv-id|doi> [--key KEY]   add a reference to content/references.yml
    math "<latex>" [--display] [--html FILE]
                                      check one formula: the MathML, or what is wrong, where, and what to write
    wiki index|ingest|lint|highlights|describe|query [args]
    publish <file>                    the Editor's publish pipeline, from the terminal

Every command runs in the current folder (the site root) unless ``--root`` says otherwise.
"""
from __future__ import annotations

import argparse
import importlib
import json
import re
import sys
from datetime import date
from pathlib import Path

from . import config, content


def _module(name: str):
    """Import an optional part of Bazinga; None when it is not installed."""
    try:
        return importlib.import_module(f"bazinga.{name}")
    except ModuleNotFoundError as exc:
        if exc.name == f"bazinga.{name}" or exc.name == "bazinga.studio":
            return None
        raise


def _missing(what: str) -> int:
    print(f"{what} is not part of this copy of Bazinga.", file=sys.stderr)
    return 1


# ------------------------------------------------------------------------------------------------------ commands
def cmd_new(args, cfg) -> int:
    kind = args.kind
    if kind not in cfg["kinds"]:
        print(f"unknown kind {kind!r}; site.yml defines: {', '.join(cfg['kinds'])}", file=sys.stderr)
        return 2
    slug = args.slug or content.slugify(args.title)
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", slug or ""):
        print(f"{slug!r} is not a page name: use lowercase letters, digits and dashes (no / or ..), "
              "for example --slug my-first-post", file=sys.stderr)
        return 2
    folder = cfg.content_dir / kind
    path = folder / f"{slug}.md"
    if path.exists():
        print(f"{path.relative_to(cfg.root)} already exists; pick another title or pass --slug", file=sys.stderr)
        return 1
    starter = (cfg.root / "theme" / "starters" / "post.md")
    if not starter.exists():
        starter = Path(__file__).parent / "starters" / "post.md"
    text = starter.read_text(encoding="utf-8")
    title = " ".join(args.title.split())                 # one line
    # a JSON string is a valid YAML double-quoted string: quotes, backslashes and the rest are escaped properly
    text = text.replace('"{{title}}"', json.dumps(title, ensure_ascii=False)).replace("{{title}}", title)
    text = text.replace("{{date}}", date.today().isoformat())
    folder.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    print(f"Created {path.relative_to(cfg.root)} (a draft). Preview it with: python -m bazinga serve --drafts")
    return 0


def cmd_build(args, cfg) -> int:
    from .build import BuildError, build
    try:
        result = build(cfg, drafts=args.drafts, quiet=args.quiet)
    except BuildError as exc:
        print(f"\n{exc}\n", file=sys.stderr)
        print("Nothing was written. Fix the problems above (each has a hint) and build again.", file=sys.stderr)
        return 1
    warnings = sum(1 for issues in result.issues.values() for i in issues if i.level == "warning")
    rel = result.out.relative_to(cfg.root) if result.out.is_relative_to(cfg.root) else result.out
    print(f"Built {len(result.pages)} pages ({result.files} HTML files) into {rel}/ in {result.seconds:.2f}s"
          + (f"; {warnings} warning(s), see: python -m bazinga check" if warnings else "")
          + (" — drafts included, do not deploy this build" if args.drafts else ""))
    return 0


def cmd_serve(args, cfg) -> int:
    from .serve import serve
    return serve(cfg, port=args.port, open_browser=args.open, drafts=args.drafts, studio=not args.no_studio,
                 studio_port=args.studio_port)


def cmd_check(args, cfg) -> int:
    from . import checks
    from .build import make_site_index  # noqa: F401 - the core build must be importable
    root = cfg.root.resolve()

    def rel(path):
        path = Path(path).resolve()
        return path.relative_to(root) if path.is_relative_to(root) else path

    wanted = None
    if args.files:
        wanted = {Path(f).resolve() for f in args.files}
        for f in wanted:
            if not f.exists():
                print(f"{f}: no such file", file=sys.stderr)
                return 2
    everything, broken = [], []          # broken: (path, ContentError) for files that cannot be read at all
    files = content.content_files(cfg)
    for path in files + sorted((wanted or set()) - {Path(f).resolve() for f in files}):
        try:
            everything.append(content.load_file(path, cfg))
        except content.ContentError as exc:
            broken.append((Path(path).resolve(), exc))
    try:
        refs, topics = content.load_references(cfg), content.load_topics(cfg)
    except content.ContentError as exc:
        print(f"{rel(exc.path) if exc.path else ''}:{exc.line or ''}: error: {exc.message}"
              + (f"\n    hint: {exc.hint}" if exc.hint else ""))
        print("\nChecked 0 page(s): 1 error(s), 0 warning(s).")
        return 1
    pages = [p for p in everything if wanted is None or Path(p.path).resolve() in wanted]
    errors = warnings = 0
    for path, exc in broken:
        if wanted is not None and path not in wanted:
            continue
        print(checks.Issue("error", exc.line, exc.message, exc.hint, "parse").format(rel(path)))
        errors += 1
    for page in pages:
        site = checks.site_for(page, everything, refs, topics, cfg)
        issues = checks.check_page(page, site)
        for issue in issues:
            if args.errors_only and issue.level != "error":
                continue
            print(issue.format(rel(page.path)))
        errors += sum(1 for i in issues if i.level == "error")
        warnings += sum(1 for i in issues if i.level == "warning")
    count = len(pages) + sum(1 for path, _ in broken if wanted is None or path in wanted)
    print(f"\nChecked {count} page(s): {errors} error(s), {warnings} warning(s).")
    return 1 if errors else 0


def cmd_cite(args, cfg) -> int:
    from . import cite
    try:
        record = cite.lookup(args.id)
        key = cite.add_reference(cfg, record, args.key)
    except cite.CiteError as exc:
        print(f"Could not add the reference: {exc}", file=sys.stderr)
        return 1
    authors = record.get("authors") or []
    who = authors[0] + (" et al." if len(authors) > 1 else "") if authors else "Unknown"
    print(f"{key}: {who} ({record.get('year')}). {record.get('title')}")
    print(f"Cite it with [@{key}] (or [@{key}, p. 4]).")
    return 0


def cmd_figure(args, cfg) -> int:
    figs = _module("figures")
    if figs is None:
        return _missing("The figure engine (bazinga/figures.py)")
    if args.action == "new":
        if not args.name:
            print("usage: python -m bazinga figure new <name> --from <starter|builder[:type]>", file=sys.stderr)
            return 2
        try:
            path = figs.cli_new(args.name, args.starter, cfg)
        except figs.FigureError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        print(f"Created {Path(path).relative_to(cfg.root)}. Use it in a post with ::figure {args.name}")
        return 0
    if args.action == "list":
        return figs.cli_list(cfg)
    if args.action == "starters":
        return figs.cli_starters()
    if args.action == "preview":
        if not args.name:
            print("usage: python -m bazinga figure preview <name>", file=sys.stderr)
            return 2
        try:
            figs.cli_preview(args.name, cfg)
        except figs.FigureError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        return 0
    return figs.cli_test(args.name, cfg)


def cmd_passthrough(module: str, fn: str, what: str):
    def run(args, cfg) -> int:
        mod = _module(module)
        if mod is None or not hasattr(mod, fn):
            return _missing(what)
        call = getattr(mod, fn)
        rest = list(args.rest)
        if module == "llm":
            return call(rest, cfg)
        if module == "studio.server" and "--root" not in rest:
            rest += ["--root", str(cfg.root)]
        return call(rest)
    return run


def cmd_math(args, cfg=None) -> int:
    """Check one formula; print the MathML, or the error with a caret under the place and what to write instead."""
    import html as htmllib

    from . import mathml
    tex = sys.stdin.read() if args.tex == "-" else args.tex
    res = mathml.check(tex, args.display)
    if res["ok"]:
        if args.html:
            out = Path(args.html)
            css = (Path(__file__).parent / "theme" / "assets" / "css" / "math.css").read_text(encoding="utf-8")
            body = res["mathml"]
            if args.display:
                num = f'<span class="eq-number">({htmllib.escape(res["tag"])})</span>' if res.get("tag") else ""
                body = f'<div class="math-display">{body}{num}</div>'
            else:
                body = f"<p>Inside a sentence: {body} and after it.</p>"
            out.write_text(
                '<!doctype html><html><head><meta charset="utf-8"><title>Formula preview</title>'
                '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=STIX+Two+Math&display=swap">'
                f'<style>:root{{--font-math:"STIX Two Math",math;--text-muted:#666;--accent-soft:#eef}}'
                f'body{{font:20px Georgia,serif;max-width:46rem;margin:3rem auto;padding:0 1rem;color:#1a1a1a;'
                f'background:#fff}}pre{{font-size:13px;color:#555;white-space:pre-wrap}}{css}</style></head><body>'
                f"<pre>{htmllib.escape(tex)}</pre>{body}</body></html>", encoding="utf-8")
            print(f"Wrote {out}")
        else:
            print(res["mathml"])
        return 0
    e = res["error"]
    lines = tex.split("\n")
    line = e["line"] or 0
    col = e["column"] or 0
    print(f"line {line + 1}, column {col + 1}: {e['message']}", file=sys.stderr)
    if 0 <= line < len(lines):
        print("    " + lines[line], file=sys.stderr)
        print("    " + " " * col + "^" * max(1, min(e.get("length") or 1, len(lines[line]) - col or 1)),
              file=sys.stderr)
    if e["hint"]:
        print(f"Instead: {e['hint']}", file=sys.stderr)
    return 1


# ---------------------------------------------------------------------------------------------------- argparse
def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="python -m bazinga", description="Build and write a Bazinga site.",
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=None, help="the site folder (default: the current folder)")
    sub = ap.add_subparsers(dest="command", metavar="<command>")

    p = sub.add_parser("new", help="start a new draft")
    p.add_argument("title")
    p.add_argument("--kind", default=None, help="content folder, e.g. posts or projects (default: the first kind)")
    p.add_argument("--slug", default=None, help="the file name / URL part (default: from the title)")
    p.set_defaults(fn=cmd_new)

    p = sub.add_parser("build", help="build the site into _site/")
    p.add_argument("--drafts", action="store_true", help="include drafts and scheduled pages (private previews only)")
    p.add_argument("--quiet", action="store_true")
    p.add_argument("--origin", default=None, metavar="URL",
                   help="the address the site is deployed at, instead of site.origin (also BAZINGA_ORIGIN or SITE_URL "
                        "in the environment); a path such as https://you.github.io/repo puts every link under /repo")
    p.set_defaults(fn=cmd_build)

    p = sub.add_parser("serve", help="build, serve on 127.0.0.1 and rebuild on changes")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--open", action="store_true", help="open the browser")
    p.add_argument("--drafts", action="store_true", help="also show drafts and scheduled pages (local preview)")
    p.add_argument("--no-editor", "--no-studio", dest="no_studio", action="store_true",
                   help="do not start the Editor (no Write button)")
    p.add_argument("--editor-port", "--studio-port", dest="studio_port", type=int, default=None,
                   help="port of the Editor on 127.0.0.1 (default: the serve port + 1, or a free one)")
    p.set_defaults(fn=cmd_serve)

    p = sub.add_parser("check", help="check pages; exit code 1 on errors")
    p.add_argument("files", nargs="*")
    p.add_argument("--errors-only", action="store_true")
    p.set_defaults(fn=cmd_check)

    p = sub.add_parser("cite", help="add a paper to content/references.yml")
    p.add_argument("id", help="an arXiv id or URL, or a DOI")
    p.add_argument("--key", default=None, help="the citation key (default: FirstAuthorYY)")
    p.set_defaults(fn=cmd_cite)

    p = sub.add_parser("math", help="check one formula (MathML, or what is wrong and what to write instead)")
    p.add_argument("tex", help='the LaTeX, in quotes; "-" reads it from the input')
    p.add_argument("--display", action="store_true", help="as a displayed equation ($$ … $$), not inside a sentence")
    p.add_argument("--html", default=None, metavar="FILE", help="write a preview page to FILE instead of printing")
    p.set_defaults(fn=cmd_math)

    p = sub.add_parser("figure", help="new figure (from a starter or the builder), test, preview or list figures")
    p.add_argument("action", choices=["new", "test", "preview", "list", "starters"])
    p.add_argument("name", nargs="?")
    p.add_argument("--from", dest="starter", default="slider_plot",
                   help="a starter (slider_plot, scatter_fit, distribution, …) or builder / builder:<type> for the form")
    p.set_defaults(fn=cmd_figure)

    for name, module, fn, what, help_text in [
        ("editor", "studio.server", "main", "The Editor (bazinga/studio/)", "the Editor, the local writing window"),
        ("studio", "studio.server", "main", "The Editor (bazinga/studio/)", "the same as editor"),
        ("publish", "studio.publish", "cli_main", "Publishing (bazinga/studio/publish.py)", "publish one page"),
        ("wiki", "llm", "cli", "The wiki tools (bazinga/llm.py)", "index, ingest, lint, highlights, describe"),
    ]:
        p = sub.add_parser(name, help=help_text, add_help=False)
        p.add_argument("rest", nargs=argparse.REMAINDER)
        p.set_defaults(fn=cmd_passthrough(module, fn, what))
    return ap


PASSTHROUGH = {"editor", "studio", "publish", "wiki"}


def _split_passthrough(argv: list) -> tuple[list, list] | None:
    """``[--root R] editor --port 9 …`` -> (``[--root R, editor]``, ``[--port 9 …]``): options after these commands
    belong to them, so they are handed over untouched."""
    i = 0
    while i < len(argv):
        if argv[i] == "--root":
            i += 2
            continue
        if argv[i].startswith("--root="):
            i += 1
            continue
        if argv[i] in PASSTHROUGH:
            return argv[: i + 1], argv[i + 1:]
        return None
    return None


def main(argv=None) -> int:
    ap = parser()
    argv = list(sys.argv[1:] if argv is None else argv)
    split = _split_passthrough(argv)
    if split:
        args = ap.parse_args(split[0])
        args.rest = split[1]
    else:
        args = ap.parse_args(argv)
    if not getattr(args, "fn", None):
        ap.print_help()
        return 0
    if args.fn is cmd_math:                     # needs no site
        return cmd_math(args)
    root = Path(args.root).resolve() if args.root else Path.cwd()
    config.set_root(root)
    try:
        # a build takes the site's address from --origin or the environment when a deploy sets it (GitHub Pages)
        origin = (getattr(args, "origin", None) or config.origin_from_env()) if args.fn is cmd_build else None
        cfg = config.load(root, origin=origin)
    except config.ConfigError as exc:
        print(str(exc) if str(exc).startswith("site.yml") else f"site.yml: {exc}", file=sys.stderr)
        return 2
    if getattr(args, "kind", "x") is None:
        args.kind = next(iter(cfg["kinds"]))
    try:
        return int(args.fn(args, cfg) or 0)
    except content.ContentError as exc:
        if exc.path and Path(exc.path).resolve().is_relative_to(root):
            exc.path = Path(exc.path).resolve().relative_to(root)
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
