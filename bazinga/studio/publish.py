"""The publish pipeline (docs/DESIGN.md, "The Editor", Publish). It runs on the author's machine only.

Steps, in order; the first failure stops the run and its output is shown:

1. checks: errors stop; warnings stop unless the author accepted them
2. status, date and updated in the page's front matter
3. the contract tests of the figures the page uses
4. build the site
5. the wiki files (the build writes wiki/index.md; this step appends ``publish | Title`` to wiki/log.md)
6. suggestions the author accepted from the model (applied in the editor before the run; reported here)
7. ``git add`` only the page, its figures, drawings and uploads, the references and topics, and the wiki files;
   ``git commit -m "Publish: <title>"`` limited to those paths
8. ``git push``, then the optional ``publish.command`` (split with shlex, never through a shell)
9. the live URL

``unpublish`` sets ``status: draft`` and runs 4-8; ``schedule`` sets a future date. ``dry_run`` does everything up to
the build in a temporary copy of the site and only *reports* what git and the command would do, so nothing in the
site folder changes.

Every external program runs from an argument list (``subprocess`` without a shell), with ``GIT_TERMINAL_PROMPT=0`` so
a missing credential fails instead of hanging.
"""
from __future__ import annotations

import datetime as _dt
import difflib
import json
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading

from dataclasses import dataclass, field
from pathlib import Path

from . import engine, pages
from .security import atomic_write

_running = threading.Lock()

STEPS = [
    ("checks", "Check the page"),
    ("status", "Set status and date"),
    ("figures", "Test its figures"),
    ("build", "Build the site"),
    ("wiki", "Update the wiki files"),
    ("suggest", "Suggested links and topics"),
    ("commit", "Commit"),
    ("push", "Push"),
    ("command", "Deploy command"),
    ("live", "Live address"),
]
UNPUBLISH_SKIP = {"checks", "figures", "suggest"}


class StepFailed(Exception):
    def __init__(self, message: str, output: str = ""):
        super().__init__(message)
        self.message, self.output = message, output


@dataclass
class Options:
    mode: str = "publish"                 # publish | unpublish | schedule
    date: str | None = None               # schedule: YYYY-MM-DD in the future
    dry_run: bool = False
    accept_warnings: bool = False
    accepted: list = field(default_factory=list)   # short notes on accepted suggestions (for the log)
    build_cmd: list | None = None         # tests may replace the build command
    timeout_build: float = 900
    timeout_git: float = 300
    timeout_command: float = 1800


def today() -> _dt.date:
    try:
        from bazinga import content
        return content.today()
    except Exception:  # noqa: BLE001
        return _dt.date.today()


# --- helpers ---------------------------------------------------------------------------------------------------------

def _env(root: Path) -> dict:
    env = engine.env_for(root)
    env["GIT_TERMINAL_PROMPT"] = "0"
    env.setdefault("GIT_ASKPASS", "")
    return env


def run_stream(cmd: list[str], cwd: Path, emit, timeout: float, env=None) -> tuple[int, str]:
    """Run ``cmd`` (a list, never a shell), streaming its output lines to the log. Returns (code, output)."""
    emit("log", {"text": "$ " + " ".join(shlex.quote(c) for c in cmd)})
    try:
        proc = subprocess.Popen(cmd, cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                env=env or _env(cwd), bufsize=1, stdin=subprocess.DEVNULL)
    except FileNotFoundError:
        msg = f"{cmd[0]}: program not found"
        emit("log", {"text": msg})
        return 127, msg
    timer = threading.Timer(timeout, proc.kill)
    timer.start()
    lines = []
    try:
        for line in proc.stdout:
            line = line.rstrip("\n")
            lines.append(line)
            emit("log", {"text": line})
        code = proc.wait()
    finally:
        timer.cancel()
        proc.stdout.close()
    if code < 0:
        lines.append(f"Stopped after {int(timeout)} seconds.")
        emit("log", {"text": lines[-1]})
    return code, "\n".join(lines[-400:])


def git(root: Path, *args, check=True, timeout=60) -> subprocess.CompletedProcess:
    proc = subprocess.run(["git", *args], cwd=str(root), capture_output=True, text=True, env=_env(root),
                          timeout=timeout, stdin=subprocess.DEVNULL)
    if check and proc.returncode != 0:
        raise StepFailed(f"git {args[0]} failed", (proc.stdout + proc.stderr).strip())
    return proc


def _copy_site(root: Path) -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="bazinga-dry-run-"))
    skip_top = {".git", "_site", ".venv", "venv", "node_modules", ".studio", "proposals", "bazinga", ".vercel",
                ".netlify", ".worktrees"}

    def ignore(folder, names):
        if Path(folder).resolve() == root.resolve():
            return [n for n in names if n in skip_top]
        return [n for n in names if n in ("__pycache__", ".DS_Store")]

    dest = tmp / "site"
    shutil.copytree(root, dest, ignore=ignore, symlinks=True)
    return dest


def renamed_from(root: Path, page_id: str) -> list[str]:
    p = Path(root) / ".studio" / "renames.json"
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return list(data.get(page_id, []))
    except (OSError, ValueError):
        return []


def clear_renames(root: Path, page_id: str) -> None:
    p = Path(root) / ".studio" / "renames.json"
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    if data.pop(page_id, None) is not None:
        atomic_write(p, json.dumps(data, indent=1))


def files_to_commit(root: Path, page_rel: str, body: str, text: str, page_id: str) -> list[str]:
    """Only the files that belong to this page's publication."""
    out = [page_rel]
    out += [f"figures/{n}.py" for n in pages.figures_used(body)]
    out += [f"drawings/{ref.split('.')[0]}.py" for ref in pages.drawings_used(body)]
    out += pages.uploads_used(text)
    out += ["content/references.yml", "content/topics.yml", "wiki/index.md", "wiki/log.md"]
    seen, result = set(), []
    for rel in out:
        if rel in seen:
            continue
        seen.add(rel)
        if (Path(root) / rel).exists():
            result.append(rel)
    for old in renamed_from(root, page_id):
        if old not in seen:
            result.append(old)   # the old file of a renamed page: staging its removal
    return result


# --- prepare ---------------------------------------------------------------------------------------------------------

def run_checks(cfg, page) -> tuple[list, list, str | None]:
    """(errors, warnings, note). The note says when checks are not available."""
    try:
        checks = engine.module("checks")
        with engine.lock():
            site = engine.site_index(cfg, override=page)
            issues = checks.check_page(page, site)
    except engine.Unavailable as exc:
        return [], [], str(exc)
    as_dict = [{"level": i.level, "line": i.line, "message": i.message, "hint": getattr(i, "hint", ""),
                "code": getattr(i, "code", "")} for i in issues]
    return ([i for i in as_dict if i["level"] == "error"], [i for i in as_dict if i["level"] != "error"], None)


def plan_fields(page, mode: str, date: str | None) -> dict:
    """The front-matter changes a publish/unpublish/schedule makes."""
    t = today()
    if mode == "unpublish":
        return {"status": "draft"}
    if mode == "schedule":
        try:
            when = _dt.date.fromisoformat(str(date))
        except (TypeError, ValueError):
            raise StepFailed("Pick the day the page should go live.") from None
        if when <= t:
            raise StepFailed("A scheduled day must be in the future; use Publish to publish today.")
        return {"status": "published", "date": when}
    if page.public:  # republishing: keep the first date, mark the revision
        return {"status": "published", "date": page.date, "updated": t}
    return {"status": "published", "date": t}


def prepare(cfg, page_id: str, mode: str = "publish", date: str | None = None) -> dict:
    path = pages.page_path(cfg, page_id)
    page = engine.parse(cfg, path, path.read_text(encoding="utf-8"))
    errors, warnings, note = ([], [], None) if mode == "unpublish" else run_checks(cfg, page)
    pub = cfg.get("publish") or {}
    try:
        fields = plan_fields(page, mode, date)
        plan_error = None
    except StepFailed as exc:
        fields, plan_error = {}, exc.message
    return {"id": page_id, "title": page.title, "state": page.state, "errors": errors, "warnings": warnings,
            "checks_note": note, "fields": pages.to_json(fields), "plan_error": plan_error,
            "figures": pages.figures_used(page.body),
            "commit": bool(pub.get("commit", True)), "push": bool(pub.get("push", True)),
            "command": pub.get("command") or "", "url": cfg.origin + page.url,
            "steps": [{"key": k, "label": label} for k, label in STEPS
                      if not (mode == "unpublish" and k in UNPUBLISH_SKIP)]}


# --- run -------------------------------------------------------------------------------------------------------------

def run(cfg, page_id: str, opts: Options, emit) -> dict:
    """Run the pipeline, reporting through ``emit(event, data)``. Returns the final summary."""
    if not _running.acquire(blocking=False):
        emit("error", {"message": "Another publish is already running."})
        return {"ok": False, "error": "busy"}
    try:
        return _run(cfg, page_id, opts, emit)
    finally:
        _running.release()


def _run(cfg, page_id: str, opts: Options, emit) -> dict:
    root = Path(cfg.root).resolve()
    real_path = pages.page_path(cfg, page_id)
    page_rel = str(real_path.relative_to(root))
    original = real_path.read_text(encoding="utf-8")
    page = engine.parse(cfg, real_path, original)
    title = page.title or page.slug
    mode = opts.mode
    pub = cfg.get("publish") or {}
    work = root
    tmp_root = None
    wrote = False
    staged = []            # paths this run staged (unstaged again if it fails before the commit)
    # the wiki files as they were, so a failed publish leaves no log entry for something that never went out
    wiki_before = {rel: ((root / rel).read_bytes() if (root / rel).is_file() else None)
                   for rel in ("wiki/index.md", "wiki/log.md")}
    summary = {"ok": False, "dry_run": opts.dry_run, "mode": mode, "title": title, "url": None, "commit": None}
    keys = [k for k, _ in STEPS if not (mode == "unpublish" and k in UNPUBLISH_SKIP)]
    current = {"key": None}

    def step(key, state, note=""):
        if key not in keys:
            return
        current["key"] = key if state == "running" else current["key"]
        emit("step", {"key": key, "state": state, "note": note})

    def log(text):
        emit("log", {"text": text})

    try:
        if opts.dry_run:
            log("Dry run: working on a temporary copy of the site; nothing in your folder will change.")
            work = _copy_site(root)
            tmp_root = work.parent
        work_path = work / page_rel

        # 1. checks
        if "checks" in keys:
            step("checks", "running")
            errors, warnings, note = run_checks(cfg, page)
            for i in errors + warnings:
                where = f"line {i['line']}: " if i.get("line") else ""
                log(f"{i['level']}: {where}{i['message']}" + (f" ({i['hint']})" if i.get("hint") else ""))
            if errors:
                raise StepFailed(f"{len(errors)} error{'s' if len(errors) != 1 else ''} to fix first.")
            if warnings and not opts.accept_warnings:
                raise StepFailed(f"{len(warnings)} warning{'s' if len(warnings) != 1 else ''} to look at first.")
            step("checks", "done", note or (f"{len(warnings)} warning(s) accepted" if warnings else "No problems"))

        # 2. status, date, updated
        step("status", "running")
        fields = plan_fields(page, mode, opts.date)
        new_text = pages.set_fields(original, **fields)
        if not opts.dry_run:
            wrote = True
        atomic_write(work_path, new_text)
        diff = "\n".join(difflib.unified_diff(original.split("\n")[:20], new_text.split("\n")[:20], page_rel,
                                              page_rel, lineterm="", n=0))
        for line in diff.splitlines()[2:]:
            log(line)
        step("status", "done", ", ".join(f"{k}: {pages.to_json(v)}" for k, v in fields.items()))

        # 3. figure tests
        if "figures" in keys:
            names = pages.figures_used(page.body)
            if not names:
                step("figures", "skipped", "This page has no figures")
            else:
                step("figures", "running")
                res = engine.worker(work, "figure-tests", {"names": names}, timeout=300)
                if res.get("unavailable"):
                    step("figures", "skipped", "Figure tests are not available yet")
                else:
                    for r in res.get("results", []):
                        log(f"{r['name']}: " + ("ok" if not r["problems"] else "; ".join(r["problems"])))
                    if not res.get("ok"):
                        raise StepFailed("A figure did not pass its test.",
                                         res.get("error") or "\n".join(
                                             p for r in res.get("results", []) for p in r["problems"]))
                    step("figures", "done", f"{len(names)} figure{'s' if len(names) != 1 else ''} passed")

        # 4. build
        step("build", "running")
        cmd = opts.build_cmd or [sys.executable, "-m", "bazinga", "build"]
        code, output = run_stream(cmd, work, emit, opts.timeout_build)
        if code != 0:
            raise StepFailed("The build failed.", output)
        step("build", "done")

        # 5. wiki
        step("wiki", "running")
        op = {"publish": "publish", "unpublish": "unpublish", "schedule": "schedule"}[mode]
        subject = title if mode != "schedule" else f"{title} (live {fields['date']})"
        res = engine.worker(work, "log", {"op": op, "subject": subject}, timeout=60)
        if res.get("unavailable"):
            step("wiki", "skipped", "The wiki files are not available yet")
        elif not res.get("ok"):
            raise StepFailed("Could not update wiki/log.md.", res.get("error", ""))
        else:
            step("wiki", "done", f"log: {op} | {subject}")

        # 6. accepted suggestions
        if "suggest" in keys:
            if opts.accepted:
                for note in opts.accepted:
                    log(f"accepted: {note}")
                step("suggest", "done", f"{len(opts.accepted)} accepted")
            else:
                step("suggest", "skipped", "None asked for")

        # 7. commit
        verb = {"publish": "Publish", "unpublish": "Unpublish", "schedule": "Schedule"}[mode]
        message = f"{verb}: {title}" + (f" ({fields['date']})" if mode == "schedule" else "")
        committed = False
        if not pub.get("commit", True):
            step("commit", "skipped", "publish.commit is off in site.yml")
        else:
            step("commit", "running")
            top = git(root, "rev-parse", "--show-toplevel", check=False)
            if top.returncode != 0:
                raise StepFailed("This folder is not a git repository.",
                                 "Run `git init` and add a remote, or set publish.commit: false in site.yml.")
            paths = files_to_commit(work, page_rel, page.body, new_text, page_id)
            if opts.dry_run:
                paths = [p for p in paths if (root / p).exists() or (work / p).exists()] or paths
                log("Would stage: " + ", ".join(paths))
                log("Would run: git commit -m " + shlex.quote(message) + " -- " + " ".join(paths))
                step("commit", "done", "Dry run: not committed")
            else:
                # who commits is settled before anything is staged, so a missing name leaves the index alone
                author = (pub.get("author") or "").strip()
                if author and not re.fullmatch(r"[^<>]+<[^<>@\s]+@[^<>\s]+>", author):
                    raise StepFailed("Not committed: publish.author in site.yml is not \"Your Name <you@example.com>\".",
                                     f"It is {author!r}. Fix it, or remove it to commit under your git name and email.")
                if not author and not (git(root, "config", "user.name", check=False).stdout.strip()
                                       and git(root, "config", "user.email", check=False).stdout.strip()):
                    raise StepFailed("Not committed: git does not know your name and email.",
                                     "Set publish.author in site.yml (\"Your Name <you@example.com>\") or run "
                                     "`git config user.name \"Your Name\"` and `git config user.email you@example.com`.")
                args = []
                if author:
                    name, email = author.split("<", 1)
                    args = ["-c", f"user.name={name.strip()}", "-c", f"user.email={email.strip(' >')}"]
                staged = list(paths)
                git(root, "add", "-A", "--", *paths)
                staged_names = git(root, "diff", "--cached", "--name-only", "--", *paths)
                if not staged_names.stdout.strip():
                    staged = []
                    step("commit", "skipped", "Nothing changed since the last commit")
                else:
                    for line in staged_names.stdout.split():
                        log(f"staged {line}")
                    commit_args = [*args, "commit", "-m", message]
                    if author:
                        commit_args += ["--author", author]
                    code, out = run_stream(["git", *commit_args, "--", *paths], root, emit, opts.timeout_git)
                    if code != 0:
                        raise StepFailed("git commit failed.", out)
                    staged = []
                    sha = git(root, "rev-parse", "--short", "HEAD").stdout.strip()
                    summary["commit"] = sha
                    committed = True
                    clear_renames(root, page_id)
                    step("commit", "done", f"{sha} {message}")
        wrote = False  # from here on the change is committed (or deliberately left in place)

        # 8. push + command
        if not pub.get("push", True) or not pub.get("commit", True):
            step("push", "skipped", "publish.push is off in site.yml" if pub.get("commit", True)
                 else "Nothing committed")
        elif opts.dry_run:
            log("Would run: git push")
            step("push", "done", "Dry run: not pushed")
        elif not committed:
            step("push", "skipped", "No new commit")
        else:
            step("push", "running")
            upstream = git(root, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}", check=False)
            if upstream.returncode == 0 and "/" in upstream.stdout.strip():
                # push to the branch this one tracks, even when the names differ (local "work" tracking origin/main)
                remote, _, branch = upstream.stdout.strip().partition("/")
                cmd = ["git", "push", remote, "HEAD:" + branch]
            elif "origin" in git(root, "remote", check=False).stdout.split():
                cmd = ["git", "push", "-u", "origin", "HEAD"]
            else:
                raise StepFailed("Committed, but there is no remote to push to.",
                                 "Add one with `git remote add origin <url>`, then publish again.")
            code, out = run_stream(cmd, root, emit, opts.timeout_git)
            if code != 0:
                raise StepFailed("Committed locally, but git push failed.", out)
            step("push", "done")

        command = (pub.get("command") or "").strip()
        if not command:
            step("command", "skipped", "No deploy command in site.yml")
        else:
            argv = shlex.split(command)
            if opts.dry_run:
                log("Would run: " + " ".join(shlex.quote(a) for a in argv))
                step("command", "done", "Dry run: not run")
            else:
                step("command", "running")
                code, out = run_stream(argv, root, emit, opts.timeout_command)
                if code != 0:
                    raise StepFailed("The deploy command failed.", out)
                step("command", "done")

        # 9. live URL
        if mode == "unpublish":
            url = cfg.origin + f"/{page.kind}/"
            note = "The page is a draft again; it leaves the site on the next deploy"
        elif mode == "schedule":
            url = cfg.origin + page.url
            note = (f"Goes live on {fields['date']}, on the first build that day or later (GitHub Pages builds daily; "
                    "on Vercel or Netlify add a daily build hook, see the README)")
        else:
            url = cfg.origin + page.url
            note = "Live after your host finishes deploying" if pub.get("push", True) or command else ""
        step("live", "done", note)
        summary.update(ok=True, url=url, note=note)
        emit("done", summary)
        return summary
    except StepFailed as exc:
        if current["key"]:
            emit("step", {"key": current["key"], "state": "failed", "note": exc.message})
        if exc.output:
            emit("log", {"text": exc.output, "error": True})
        summary.update(error=exc.message, output=exc.output, step=current["key"])
        emit("done", summary)
        return summary
    except Exception as exc:  # noqa: BLE001 - shown in the dialog, never a dead stream
        if current["key"]:
            emit("step", {"key": current["key"], "state": "failed", "note": str(exc)})
        out = engine.format_exc()
        emit("log", {"text": out, "error": True})
        summary.update(error=f"{type(exc).__name__}: {exc}", output=out, step=current["key"])
        emit("done", summary)
        return summary
    finally:
        if wrote and not opts.dry_run:   # failed before committing: put the page and the wiki back as they were
            if staged:
                git(root, "reset", "-q", "--", *staged, check=False)
                emit("log", {"text": "Unstaged: " + ", ".join(staged) + "."})
            try:
                atomic_write(real_path, original)
                for rel, data in wiki_before.items():
                    if data is None:
                        (root / rel).unlink(missing_ok=True)
                    elif not (root / rel).is_file() or (root / rel).read_bytes() != data:
                        atomic_write(root / rel, data)
                emit("log", {"text": f"Restored {page_rel} and the wiki files to how they were before publishing."})
            except OSError:
                pass
        if tmp_root is not None:
            shutil.rmtree(tmp_root, ignore_errors=True)


# --- terminal --------------------------------------------------------------------------------------------------------

def cli_main(argv=None) -> int:
    """``python -m bazinga publish <file> [--dry-run] [--unpublish] [--schedule YYYY-MM-DD] [--yes]``."""
    import argparse

    from bazinga import config, content

    ap = argparse.ArgumentParser(prog="bazinga publish")
    ap.add_argument("file")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--unpublish", action="store_true")
    ap.add_argument("--schedule", metavar="YYYY-MM-DD")
    ap.add_argument("--yes", action="store_true", help="accept warnings")
    a = ap.parse_args([x for x in (sys.argv[1:] if argv is None else argv) if x != "--"])
    cfg = config.load()
    path = Path(a.file)
    if not path.is_absolute() and not path.exists():
        path = cfg.root / path
    path = path.resolve()
    if not path.exists():
        print(f"No such page: {a.file}")
        return 2
    kind, slug = content.kind_and_slug(path, cfg)
    mode = "unpublish" if a.unpublish else ("schedule" if a.schedule else "publish")
    opts = Options(mode=mode, date=a.schedule, dry_run=a.dry_run, accept_warnings=a.yes)

    def emit(event, data):
        if event == "step" and data["state"] != "running":
            print(f"[{data['state']:>7}] {dict(STEPS)[data['key']]}" + (f" - {data['note']}" if data.get("note")
                                                                        else ""))
        elif event == "log":
            print("          " + data["text"].replace("\n", "\n          "))

    res = run(cfg, pages.page_id(cfg, kind, slug), opts, emit)
    if res.get("ok"):
        print(f"\n{res.get('url')}")
        return 0
    print(f"\nStopped: {res.get('error')}")
    return 1
