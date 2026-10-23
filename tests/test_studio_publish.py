"""The publish pipeline, in a temporary git repository with a bare remote: it commits only the page's files and
pushes; a dry run changes nothing; a failure stops the run and leaves the page as it was; errors block; unpublish and
schedule; the server streams the steps."""

import datetime
import hashlib
import http.client
import json
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

from bazinga.studio import publish
from bazinga.studio.server import StudioServer
import os as _os
import sys as _sys

_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from perf_support import PERF, perf_only  # noqa: E402,F401

HAS_GIT = shutil.which("git") is not None
FAKE_BUILD = [sys.executable, "-c", "import pathlib; pathlib.Path('_site').mkdir(exist_ok=True); "
              "pathlib.Path('_site/index.html').write_text('ok'); print('built')"]


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


def make_repo(tmp: Path, extra_site_yml: str = "") -> tuple[Path, Path]:
    root, remote = tmp / "site", tmp / "remote.git"
    (root / "content" / "posts").mkdir(parents=True)
    (root / "site.yml").write_text('site:\n  name: "Test"\n  origin: "https://example.org"\n' + extra_site_yml,
                                   encoding="utf-8")
    (root / ".gitignore").write_text("_site/\n.studio/\n", encoding="utf-8")
    (root / "content" / "topics.yml").write_text(
        "groups:\n  - name: Main\n    topics:\n      - {slug: writing, label: Writing}\n", encoding="utf-8")
    (root / "content" / "posts" / "hello.md").write_text(
        '---\ntitle: "Hello"\nstatus: draft\nsummary: "A first test page with a short summary."\n'
        "topics: [writing]\n---\n\nHello there. This is the body of the page.\n", encoding="utf-8")
    (root / "content" / "posts" / "other.md").write_text(
        '---\ntitle: "Other"\nstatus: draft\nsummary: "Another page."\ntopics: [writing]\n---\n\nOther.\n',
        encoding="utf-8")
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.email", "test@example.org")
    git(root, "config", "user.name", "Editor Test")
    git(root, "config", "commit.gpgsign", "false")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "init")
    git(root, "remote", "add", "origin", str(remote))
    git(root, "push", "-q", "-u", "origin", "main")
    return root, remote


def snapshot(root: Path) -> dict:
    out = {}
    for p in sorted(root.rglob("*")):
        if p.is_file() and ".git" not in p.relative_to(root).parts:
            out[str(p.relative_to(root))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


@unittest.skipUnless(HAS_GIT, "git is not installed")
class Pipeline(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="studio-publish-"))
        self.root, self.remote = make_repo(self.tmp)
        self.events = []

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def cfg(self):
        from bazinga import config
        config.set_root(self.root)
        return config.load(self.root)

    def emit(self, event, data):
        self.events.append((event, data))

    def run_pipeline(self, **kw):
        kw.setdefault("build_cmd", FAKE_BUILD)
        return publish.run(self.cfg(), "post:hello", publish.Options(**kw), self.emit)

    def steps(self):
        return {d["key"]: d["state"] for e, d in self.events if e == "step" and d["state"] != "running"}

    def test_publish_commits_only_the_page_files_and_pushes(self):
        # an unrelated change in the working tree must not be committed
        other = self.root / "content/posts/other.md"
        other.write_text(other.read_text() + "\nUnsaved thoughts.\n", encoding="utf-8")
        res = self.run_pipeline()
        self.assertTrue(res["ok"], res)
        text = (self.root / "content/posts/hello.md").read_text()
        self.assertIn("status: published", text)
        self.assertIn(f"date: {datetime.date.today().isoformat()}", text)
        self.assertEqual(git(self.root, "log", "-1", "--format=%s"), "Publish: Hello")
        changed = git(self.root, "show", "--name-only", "--format=", "HEAD").split()
        self.assertIn("content/posts/hello.md", changed)
        self.assertNotIn("content/posts/other.md", changed)
        self.assertTrue(set(changed) <= {"content/posts/hello.md", "wiki/log.md", "wiki/index.md",
                                         "content/topics.yml", "content/references.yml"}, changed)
        self.assertIn("Unsaved thoughts.", other.read_text())
        self.assertIn("content/posts/other.md", git(self.root, "status", "--porcelain"))
        self.assertEqual(git(self.root, "rev-parse", "HEAD"), git(self.remote, "rev-parse", "main"))
        self.assertEqual(res["url"], "https://example.org/posts/hello/")
        self.assertEqual(self.steps()["push"], "done")
        log = (self.root / "wiki/log.md").read_text()
        self.assertIn("publish | Hello", log)

    def test_dry_run_changes_nothing(self):
        before, head = snapshot(self.root), git(self.root, "rev-parse", "HEAD")
        status = git(self.root, "status", "--porcelain")
        res = self.run_pipeline(dry_run=True)
        self.assertTrue(res["ok"], res)
        self.assertTrue(res["dry_run"])
        self.assertEqual(snapshot(self.root), before)
        self.assertEqual(git(self.root, "rev-parse", "HEAD"), head)
        self.assertEqual(git(self.root, "status", "--porcelain"), status)
        self.assertEqual(git(self.remote, "rev-parse", "main"), head)
        logs = "\n".join(d["text"] for e, d in self.events if e == "log")
        self.assertIn("Would run: git commit", logs)
        self.assertIn("Would run: git push", logs)

    def test_failure_stops_and_restores_the_page(self):
        original = (self.root / "content/posts/hello.md").read_text()
        head = git(self.root, "rev-parse", "HEAD")
        res = self.run_pipeline(build_cmd=[sys.executable, "-c", "import sys; print('boom'); sys.exit(3)"])
        self.assertFalse(res["ok"])
        self.assertEqual(res["step"], "build")
        self.assertIn("boom", res["output"])
        steps = self.steps()
        self.assertEqual(steps["build"], "failed")
        self.assertNotIn("commit", steps)
        self.assertNotIn("push", steps)
        self.assertEqual((self.root / "content/posts/hello.md").read_text(), original)
        self.assertEqual(git(self.root, "rev-parse", "HEAD"), head)
        self.assertFalse((self.root / "wiki/log.md").exists())

    def test_errors_block_before_anything_changes(self):
        p = self.root / "content/posts/hello.md"
        p.write_text(p.read_text().replace("topics: [writing]", "topics: [no-such-topic]"), encoding="utf-8")
        before = snapshot(self.root)
        res = self.run_pipeline()
        self.assertFalse(res["ok"])
        self.assertEqual(res["step"], "checks")
        self.assertEqual(snapshot(self.root), before)

    def test_push_failure_is_reported_after_commit(self):
        git(self.root, "remote", "set-url", "origin", str(self.tmp / "missing.git"))
        res = self.run_pipeline()
        self.assertFalse(res["ok"])
        self.assertEqual(res["step"], "push")
        self.assertEqual(git(self.root, "log", "-1", "--format=%s"), "Publish: Hello")  # kept locally

    def test_unpublish(self):
        self.assertTrue(self.run_pipeline()["ok"])
        self.events.clear()
        res = self.run_pipeline(mode="unpublish")
        self.assertTrue(res["ok"], res)
        self.assertIn("status: draft", (self.root / "content/posts/hello.md").read_text())
        self.assertEqual(git(self.root, "log", "-1", "--format=%s"), "Unpublish: Hello")
        self.assertEqual(git(self.root, "rev-parse", "HEAD"), git(self.remote, "rev-parse", "main"))
        self.assertNotIn("checks", self.steps())

    def test_schedule(self):
        when = (datetime.date.today() + datetime.timedelta(days=10)).isoformat()
        res = self.run_pipeline(mode="schedule", date=when)
        self.assertTrue(res["ok"], res)
        text = (self.root / "content/posts/hello.md").read_text()
        self.assertIn("status: published", text)
        self.assertIn(f"date: {when}", text)
        self.assertEqual(git(self.root, "log", "-1", "--format=%s"), f"Schedule: Hello ({when})")
        bad = self.run_pipeline(mode="schedule", date=datetime.date.today().isoformat())
        self.assertFalse(bad["ok"])

    def test_republish_sets_updated_and_keeps_date(self):
        p = self.root / "content/posts/hello.md"
        p.write_text(p.read_text().replace("status: draft", "status: published\ndate: 2025-01-02"), encoding="utf-8")
        git(self.root, "commit", "-qam", "published earlier")
        p.write_text(p.read_text() + "\nA new paragraph.\n", encoding="utf-8")
        res = self.run_pipeline()
        self.assertTrue(res["ok"], res)
        text = p.read_text()
        self.assertIn("date: 2025-01-02", text)
        self.assertIn(f"updated: {datetime.date.today().isoformat()}", text)

    def test_nothing_to_commit_is_not_an_error(self):
        self.assertTrue(self.run_pipeline()["ok"])
        self.events.clear()
        # the same day, nothing changed: status/date are identical, so only the log line differs
        res = self.run_pipeline()
        self.assertTrue(res["ok"], res)

    def test_commit_author_from_site_yml(self):
        shutil.rmtree(self.tmp)
        self.tmp.mkdir()
        self.root, self.remote = make_repo(self.tmp, 'publish:\n  author: "Ada Writer <ada@example.org>"\n')
        res = self.run_pipeline()
        self.assertTrue(res["ok"], res)
        self.assertEqual(git(self.root, "log", "-1", "--format=%an <%ae>"), "Ada Writer <ada@example.org>")

    def test_publish_command_runs_without_a_shell(self):
        marker = self.tmp / "deployed;touch pwned"
        cmd = f'{sys.executable} -c "import sys, pathlib; pathlib.Path(sys.argv[1]).write_text(\'ok\')" "{marker}"'
        shutil.rmtree(self.tmp)
        self.tmp.mkdir()
        self.root, self.remote = make_repo(self.tmp, "publish:\n  command: " + json.dumps(cmd) + "\n")
        res = self.run_pipeline()
        self.assertTrue(res["ok"], res)
        self.assertTrue(marker.exists())           # the whole name, semicolon included, is one argument
        self.assertFalse((self.root / "pwned").exists())

    def test_rename_stages_the_old_file_removal(self):
        from bazinga.studio.api import Editor
        studio = Editor(self.root)
        res = studio.rename_page({"id": "post:hello", "slug": "hello-world"})
        self.assertEqual(res["id"], "post:hello-world")
        out = publish.run(self.cfg(), "post:hello-world", publish.Options(build_cmd=FAKE_BUILD), self.emit)
        self.assertTrue(out["ok"], out)
        changed = git(self.root, "show", "--name-status", "--format=", "HEAD")
        self.assertIn("content/posts/hello-world.md", changed)
        self.assertIn("content/posts/hello.md", changed)    # deleted in the same commit
        self.assertFalse((self.root / "content/posts/hello.md").exists())

    def test_rename_of_an_untracked_page_publishes(self):
        """A3: a page made and renamed before its first commit has no old file for git to remove."""
        from bazinga.studio.api import Editor
        studio = Editor(self.root)
        pid = studio.new_page({"title": "Fresh page", "kind": "posts"})["id"]
        path = self.root / "content/posts" / (pid.split(":", 1)[1] + ".md")
        path.write_text('---\ntitle: "Fresh page"\nstatus: draft\nsummary: "A fresh page."\ntopics: [writing]\n---\n\n'
                        "Fresh.\n", encoding="utf-8")
        res = studio.rename_page({"id": pid, "slug": "fresh-renamed"})
        renames = json.loads((self.root / ".studio/renames.json").read_text(encoding="utf-8"))
        self.assertEqual(renames.get(res["id"]), [])
        out = publish.run(self.cfg(), res["id"], publish.Options(build_cmd=FAKE_BUILD), self.emit)
        self.assertTrue(out["ok"], out)
        self.assertIn("content/posts/fresh-renamed.md", git(self.root, "show", "--name-only", "--format=", "HEAD"))

    def assert_untouched_after_failure(self, res, step):
        self.assertFalse(res["ok"])
        self.assertEqual(res["step"], step)
        self.assertIn("status: draft", (self.root / "content/posts/hello.md").read_text(encoding="utf-8"))
        self.assertEqual(git(self.root, "diff", "--cached", "--name-only"), "")      # nothing left staged
        self.assertEqual(git(self.root, "status", "--porcelain", "--untracked-files=all"), "")
        self.assertFalse((self.root / "wiki/log.md").exists())                      # no false log entry
        self.assertEqual(git(self.root, "log", "--oneline").count("\n"), 0)        # still only "init"

    def test_commit_rejected_by_a_hook_leaves_nothing_staged(self):
        """A2/D1: a failing pre-commit hook used to leave the published page and the log entry staged."""
        hook = self.root / ".git/hooks/pre-commit"
        hook.write_text("#!/bin/sh\necho 'hook says no'; exit 1\n", encoding="utf-8")
        hook.chmod(0o755)
        (self.root / "wiki").mkdir(exist_ok=True)
        res = self.run_pipeline()
        self.assertIn("git commit failed", res["error"])
        self.assert_untouched_after_failure(res, "commit")

    def test_no_identity_stops_before_staging(self):
        import os
        from unittest import mock
        git(self.root, "config", "--unset", "user.email")
        git(self.root, "config", "--unset", "user.name")
        home = self.tmp / "home"
        home.mkdir()
        with mock.patch.dict(os.environ, {"HOME": str(home), "XDG_CONFIG_HOME": str(home), "GIT_CONFIG_NOSYSTEM": "1",
                                          "GIT_CONFIG_GLOBAL": str(home / "none")}):
            for k in ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL", "EMAIL"):
                os.environ.pop(k, None)
            res = self.run_pipeline()
        self.assertIn("does not know your name and email", res["error"])
        self.assertNotIn(("log", {"text": "staged content/posts/hello.md"}), self.events)
        self.assert_untouched_after_failure(res, "commit")

    def test_a_malformed_publish_author_stops_before_staging(self):
        shutil.rmtree(self.tmp)
        self.tmp.mkdir()
        self.root, self.remote = make_repo(self.tmp, 'publish:\n  author: "Ada Writer"\n')
        res = self.run_pipeline()
        self.assertIn("publish.author", res["error"])
        self.assert_untouched_after_failure(res, "commit")

    @unittest.skipUnless(shutil.which("git"), "git")
    def test_real_build(self):
        """The real `python -m bazinga build` in the temporary site (when the core build is present)."""
        try:
            import bazinga.build  # noqa: F401
            import bazinga.cli  # noqa: F401
        except ImportError:
            self.skipTest("the core build is not available yet")
        res = publish.run(self.cfg(), "post:hello", publish.Options(dry_run=True), self.emit)
        self.assertTrue(res["ok"], "\n".join(d.get("text", "") for e, d in self.events if e == "log")[-3000:])


@unittest.skipUnless(HAS_GIT, "git is not installed")
class Streamed(unittest.TestCase):
    def test_publish_streams_events_over_the_post(self):
        tmp = Path(tempfile.mkdtemp(prefix="studio-sse-"))
        try:
            root, _ = make_repo(tmp)
            server = StudioServer(root, 0)
            server.quiet = True
            t = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
            t.start()
            orig = publish.Options.__init__

            def fake_build(self, *a, **kw):    # keep this test independent of the core build
                orig(self, *a, **kw)
                self.build_cmd = FAKE_BUILD
            publish.Options.__init__ = fake_build
            try:
                conn = http.client.HTTPConnection("127.0.0.1", server.port, timeout=60)
                body = json.dumps({"id": "post:hello", "mode": "publish", "dry_run": True}).encode()
                conn.request("POST", "/api/publish/run", body, {
                    "Host": f"127.0.0.1:{server.port}", "Cookie": f"{server.cookie}={server.token}",
                    "Origin": f"http://127.0.0.1:{server.port}", "Content-Type": "application/json",
                    "X-Bazinga-Write": server.write_key})
                res = conn.getresponse()
                self.assertEqual(res.status, 200)
                self.assertTrue(res.getheader("Content-Type").startswith("text/event-stream"))
                text = res.read().decode()
                self.assertIn("event: step", text)
                self.assertIn("event: log", text)
                done = [json.loads(chunk.split("data: ", 1)[1]) for chunk in text.split("\n\n")
                        if chunk.startswith("event: done")]
                self.assertTrue(done and done[0]["ok"], text[-2000:])
            finally:
                publish.Options.__init__ = orig
                server.shutdown()
                server.server_close()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
