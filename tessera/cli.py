"""The command line: ``python -m tessera <command>``.

    new "Title" [--kind posts]        a new draft from tessera/starters/post.md
    build [--drafts]                  build _site/ (drafts only with --drafts, for private previews)
    serve [--port 8000]               build, watch, live-reload, /api/ask/ locally
    studio                            the local editor (127.0.0.1 only)
    check [file ...]                  run the checks; exit code 1 when there are errors
    figure new <name> --from slider_plot | figure test [name]
    cite <arxiv-id|doi> [--key KEY]   add a reference to content/references.yml
    wiki index|ingest|lint|highlights|describe|query [args]
    publish <file>                    the Studio's publish pipeline, from the terminal

Every command runs in the current folder (the site root) unless ``--root`` says otherwise.
"""
from __future__ import annotations

import argparse
import importlib
import sys
from datetime import date
from pathlib import Path

from . import config, content


def _module(name: str):
    """Import an optional part of Tessera; None when it is not installed."""
    try:
        return importlib.import_module(f"tessera.{name}")
    except ModuleNotFoundError as exc:
        if exc.name == f"tessera.{name}" or exc.name == "tessera.studio":
            return None
        raise


def _missing(what: str) -> int:
    print(f"{what} is not part of this copy of Tessera.", file=sys.stderr)
    return 1


# ------------------------------------------------------------------------------------------------------ commands
def cmd_new(args, cfg) -> int:
    kind = args.kind
    if kind not in cfg["kinds"]:
        print(f"unknown kind {kind!r}; site.yml defines: {', '.join(cfg['kinds'])}", file=sys.stderr)
        return 2
    slug = args.slug or content.slugify(args.title)
    folder = cfg.content_dir / kind
    path = folder / f"{slug}.md"
    if path.exists():
        print(f"{path.relative_to(cfg.root)} already exists; pick another title or pass --slug", file=sys.stderr)
        return 1
    starter = (cfg.root / "theme" / "starters" / "post.md")
    if not starter.exists():
        starter = Path(__file__).parent / "starters" / "post.md"
    text = starter.read_text(encoding="utf-8")
    title = args.title.replace('"', '\\"')
    text = text.replace("{{title}}", title).replace("{{date}}", date.today().isoformat())
    folder.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    print(f"Created {path.relative_to(cfg.root)} (a draft). Preview it with: python -m tessera serve --drafts")
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
          + (f"; {warnings} warning(s), see: python -m tessera check" if warnings else "")
          + (" — drafts included, do not deploy this build" if args.drafts else ""))
    return 0


def cmd_serve(args, cfg) -> int:
    from .serve import serve
    return serve(cfg, port=args.port, open_browser=args.open, drafts=args.drafts)


def cmd_check(args, cfg) -> int:
    from . import checks
    from .build import make_site_index
    everything = []
    for path in content.content_files(cfg):
        try:
            everything.append(content.load_file(path, cfg))
        except content.ContentError as exc:
            print(str(exc))
    refs, topics = content.load_references(cfg), content.load_topics(cfg)
    if args.files:
        wanted = {Path(f).resolve() for f in args.files}
        pages = []
        for f in wanted:
            if not f.exists():
                print(f"{f}: no such file", file=sys.stderr)
                return 2
            match = [p for p in everything if Path(p.path).resolve() == f]
            pages += match or [content.load_file(f, cfg)]
    else:
        pages = everything
    errors = warnings = 0
    for page in pages:
        site = checks.site_for(page, everything, refs, topics, cfg)
        issues = checks.check_page(page, site)
        rel = Path(page.path).resolve()
        rel = rel.relative_to(cfg.root.resolve()) if rel.is_relative_to(cfg.root.resolve()) else rel
        for issue in issues:
            if args.errors_only and issue.level != "error":
                continue
            print(issue.format(rel))
        errors += sum(1 for i in issues if i.level == "error")
        warnings += sum(1 for i in issues if i.level == "warning")
    print(f"\nChecked {len(pages)} page(s): {errors} error(s), {warnings} warning(s).")
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
        return _missing("The figure engine (tessera/figures.py)")
    if args.action == "new":
        if not args.name:
            print("usage: python -m tessera figure new <name> --from slider_plot", file=sys.stderr)
            return 2
        try:
            path = figs.cli_new(args.name, args.starter, cfg)
        except figs.FigureError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        print(f"Created {Path(path).relative_to(cfg.root)}. Use it in a post with ::figure {args.name}")
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


# ---------------------------------------------------------------------------------------------------- argparse
def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="python -m tessera", description="Build and write a Tessera site.",
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
    p.set_defaults(fn=cmd_build)

    p = sub.add_parser("serve", help="build, serve on 127.0.0.1 and rebuild on changes")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--open", action="store_true", help="open the browser")
    p.add_argument("--drafts", action="store_true", help="also show drafts and scheduled pages (local preview)")
    p.set_defaults(fn=cmd_serve)

    p = sub.add_parser("check", help="check pages; exit code 1 on errors")
    p.add_argument("files", nargs="*")
    p.add_argument("--errors-only", action="store_true")
    p.set_defaults(fn=cmd_check)

    p = sub.add_parser("cite", help="add a paper to content/references.yml")
    p.add_argument("id", help="an arXiv id or URL, or a DOI")
    p.add_argument("--key", default=None, help="the citation key (default: FirstAuthorYY)")
    p.set_defaults(fn=cmd_cite)

    p = sub.add_parser("figure", help="new figure from a starter, or test figures")
    p.add_argument("action", choices=["new", "test"])
    p.add_argument("name", nargs="?")
    p.add_argument("--from", dest="starter", default="slider_plot")
    p.set_defaults(fn=cmd_figure)

    for name, module, fn, what, help_text in [
        ("studio", "studio.server", "main", "The Studio (tessera/studio/)", "the local editor"),
        ("publish", "studio.publish", "cli_main", "Publishing (tessera/studio/publish.py)", "publish one page"),
        ("wiki", "llm", "cli", "The wiki tools (tessera/llm.py)", "index, ingest, lint, highlights, describe"),
    ]:
        p = sub.add_parser(name, help=help_text, add_help=False)
        p.add_argument("rest", nargs=argparse.REMAINDER)
        p.set_defaults(fn=cmd_passthrough(module, fn, what))
    return ap


PASSTHROUGH = {"studio", "publish", "wiki"}


def _split_passthrough(argv: list) -> tuple[list, list] | None:
    """``[--root R] studio --port 9 …`` -> (``[--root R, studio]``, ``[--port 9 …]``): options after these commands
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
    root = Path(args.root).resolve() if args.root else Path.cwd()
    config.set_root(root)
    try:
        cfg = config.load(root)
    except config.ConfigError as exc:
        print(f"site.yml: {exc}", file=sys.stderr)
        return 2
    if getattr(args, "kind", "x") is None:
        args.kind = next(iter(cfg["kinds"]))
    try:
        return int(args.fn(args, cfg) or 0)
    except content.ContentError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
