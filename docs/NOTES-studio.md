# Editor: build notes

The Editor is the local-only writing app: `python -m bazinga editor`. It is a library of pages, a Markdown editor
with a live preview of the real page, helpers (equations, figures, drawings, citations, links, images), checks,
versions, and the publish pipeline. Nothing under `bazinga/studio/` is ever copied to `_site/`, and a test enforces
that.

## Files

```
bazinga/studio/
  __init__.py, __main__.py   python -m bazinga.studio works too (same as python -m bazinga editor)
  server.py     ThreadingHTTPServer on 127.0.0.1 (random free port unless --port); main(argv); the guard on every
                request; the app page with the pinned import map and a strict CSP; the publish log streamed as
                server-sent events on the POST's own response
  security.py   Host allowlist, token cookie, Origin / Sec-Fetch-Site + JSON checks, path confinement (resolve()
                follows symlinks), atomic writes, image sniffing, upload limit
  api.py        the handlers (pages, preview, checks, maths, figures, drawings, citations, topics, uploads,
                suggestions, publish); preview assets (/assets, /static, /figures, generated pygments.css);
                /frame/figure/<name> and /frame/drawing/<ref> (one figure or drawing, styled like the site);
                draft_gate() for model-written figure code
  publish.py    the pipeline (publish / unpublish / schedule, dry run) + cli_main for `python -m bazinga publish`
  pages.py      front matter read/write: unchanged keys keep their text and comments byte for byte; changed keys are
                patched in place; new drafts from bazinga/starters/post.md; rename-safe link rewriting
  history.py    snapshots in .studio/history/<kind>/<slug>/ (explicit saves; autosaves at most once a minute; 60 kept)
  cite.py       arXiv / Crossref lookup (core's bazinga.cite when present), keys, append to references.yml
  engine.py     lazy imports of core/figures/wiki modules ("not available yet" instead of a crash); the worker runner
  worker.py     python -m bazinga.studio.worker <op>: figure tests/runs, drawings, wiki log, in a fresh interpreter
                (fresh imports, timeouts, and a temp copy of the site for dry runs)
  static/       index.html, studio.css, studio.js (routing, theme), lib.js (API, DOM, dialogs, icons), library.js,
                editor.js, cm.js (CodeMirror: Markdown + maths-aware marks, completion, "/" menu, code editor),
                preview.js (iframe + in-place DOM patching + scroll sync), panels/{equation,figures,cite,links,
                details,checks,publish,history}.js
tests/test_studio_security.py  test_studio_publish.py  test_studio_pages.py  test_studio_site.py  test_studio_js.py
```

## How to run

```
python -m bazinga editor                    # opens http://127.0.0.1:<port>/?token=...
python -m bazinga editor -- --port 9000 --no-browser
python -m bazinga publish -- content/posts/x.md [--dry-run] [--unpublish] [--schedule 2026-11-01] [--yes]
```

(The `--` is needed until core's subcommand pass-through forwards options; see "Requests" below.)

What you can do:
- **Library.** Status pills, words, figures, last edit and check badges, with search, filters and New post.
- **Editor.**
  - Title and summary fields, then the body in CodeMirror.
  - Equations, `[[links]]`, `[@cites]` and `::figure` lines are marked up as you type.
  - Completion for `[[`, `[@`, `::figure`, `::drawing`, callout kinds and LaTeX commands inside maths.
  - A "/" menu on an empty line, or Cmd/Ctrl+/. It also appears in the toolbar.
- **Saving and preview.**
  - Autosave after 2 s idle; Cmd/Ctrl+S saves with a version.
  - The live preview updates about 300 ms after typing. It is patched in place, so figures keep their state and the
    scroll position survives.
  - Scroll sync matches headings, figures and equations. Cmd/Ctrl+P toggles the preview, with wide and phone widths.
  - Paste or drop an image to upload it.
- **Helpers.**
  - Equation helper: live MathML, a palette, the converter's hint, display or inline, a name, and "describe in words".
  - Figures and drawings: live previews with working controls, new from a starter, edit the code, Save runs the test.
    Figures can also be drafted from a description.
  - Citation lookup by arXiv id/URL or DOI.
  - Link picker (Cmd/Ctrl+K).
  - Details drawer: rename-safe address, description counter with Suggest, topic chips with "add topic", series,
    builds-on, cover, dates.
  - Checks drawer: click an issue to jump to its line or field.
  - Versions, with restore.
- **Publish dialog.**
  - Publish now, Schedule or Unpublish.
  - Errors block publishing; warnings need an explicit "Publish anyway".
  - Optional suggestion cards to accept or reject.
  - A dry run, a live step list, the log, the result and the live URL.

The suggestion buttons appear only when `llm.configured(cfg)` is true. The UI never names the machinery.

## Security measures (owner's hard requirement: publishing works only on localhost)

1. Binds `127.0.0.1` only (asserted by a test).
2. **Host** must be exactly `127.0.0.1:<port>` or `localhost:<port>`. Everything else is refused with 403, which
   stops DNS rebinding. Tested: `evil.com`, `127.0.0.1.nip.io`, `localhost.evil.com`, a wrong port, `[::1]`,
   `0.0.0.0` and a missing Host.
3. **Token.** `secrets.token_urlsafe(32)` per launch, passed once in the URL.
   - The server swaps it for `bazinga_studio_<port>=…; HttpOnly; SameSite=Strict; Path=/` and 303-redirects to
     `/`, so the token leaves the address bar.
   - The cookie name carries the port, because cookies are shared across ports.
   - Every route except the token exchange needs the cookie: the app, the API, previews and assets. Comparison is
     constant-time.
4. **Writes** must be POST with `Content-Type: application/json`, plus one of:
   - an `Origin` equal to the Editor's own origin;
   - no Origin, but `Sec-Fetch-Site: same-origin`.

   `Sec-Fetch-Site: cross-site` or `same-site` is refused even when an Origin is present. Bodies are capped at
   2 MB (uploads 8 MB) and refused before they are read. PUT, DELETE, PATCH and OPTIONS get 405.
5. **No CORS headers**, ever (tested on every kind of response). Every response also sends:
   - `X-Content-Type-Options: nosniff`, `Cross-Origin-Resource-Policy: same-origin`, `Referrer-Policy: no-referrer`
     and `Cache-Control: no-store`.
   - On the app page: a CSP (`default-src 'none'`; scripts only from self, the import map's hash and esm.sh;
     `frame-ancestors 'none'`) and `X-Frame-Options: DENY`.
   - On preview pages: `frame-ancestors 'self'` and `X-Frame-Options: SAMEORIGIN`.
6. **Paths.**
   - Ids and names are validated by regex, then `confine()` resolves them (following symlinks) inside `content/`,
     `figures/`, `drawings/`, `static/uploads/`, `content/references.yml` or `content/topics.yml`.
   - Symlinks pointing out are refused (tested for a file link, a directory link and a linked `figures/`).
   - Read-only asset routes are confined to their folders the same way.
7. **Atomic writes.** A temp file in the same folder, then fsync, then `os.replace`. A failed write leaves the old
   file and no temp file (tested).
8. **Uploads.** At most 8 MB. Only PNG, JPEG, GIF, WebP and AVIF, sniffed from the bytes; SVG and HTML are refused.
   The file name is re-slugged, so `../../evil.png` becomes `static/uploads/hello-evil.png`.
9. **Subprocesses.**
   - git, the build and `publish.command` (split with `shlex.split`) run as argument lists, never `shell=True`.
     A test shows a `;` in the command stays inside one argument.
   - `GIT_TERMINAL_PROMPT=0`, so a missing credential fails instead of hanging.
   - Timeouts on everything.
10. **Model-written figure code** is run for its test only when `draft_gate()` finds plain computation:
    - imports limited to math, numpy, random, statistics and similar;
    - no `open`, `exec`, `eval` or `__import__`, and no dunder attributes.

    Otherwise the author reads the draft first, and saving it, an explicit act, runs the test.
11. **Not part of the site.** `test_studio_site.py` builds the example site, with and without drafts, and checks:
    - no file under `_site/` comes from `bazinga/studio/`, by path or by content hash;
    - no page refers to `/_studio/`, the cookie name or the write endpoints.

Known trade-off: the preview iframe is same-origin with the Editor, which the in-place patching and live figure
state need. So the site's own scripts and its pinned CDN scripts (Pyodide, fonts) run with the Editor's cookie. They
are the author's own site code, pinned in `vendor.py`.

## Publish pipeline (publish.py)

The steps, in order:
1. Checks: errors stop the run; warnings stop it unless accepted.
2. status, date and updated. A republish keeps `date` and sets `updated`.
3. Tests of the page's figures, run in the worker.
4. Build: `python -m bazinga build`, streamed.
5. Wiki: the build writes `wiki/index.md`; `wiki.append_log` adds `publish | Title`.
6. Accepted suggestions are reported. They are applied in the editor before the run and saved.
7. Commit:
   - `git add -A -- <only: the page, its figures/drawings/uploads, references.yml, topics.yml, wiki/index.md,
     wiki/log.md, and the old file of a renamed page>`;
   - then `git commit -m "Publish: <title>" [--author] -- <same paths>`. Other dirty files are never committed
     (tested).
   - `publish.author` sets the author.
8. Push: `git push`, or `git push -u origin HEAD` when there is no upstream yet. Then `publish.command`.
9. The live URL.

Failure handling:
- The first failure stops the run and shows its output.
- A failure before the commit restores the page file to how it was.
- A push failure keeps the local commit and says so.

Modes:
- **Dry run:** steps 1–6 run in a temporary copy of the site. git and the command are only reported ("Would run: …").
  The site folder, HEAD and the remote are unchanged (tested byte for byte).
- **Unpublish** sets `status: draft` and runs steps 4–9 with "Unpublish: <title>".
- **Schedule** needs a future date and commits "Schedule: <title> (<date>)".

## Tests

`python -m unittest discover tests -p "test_studio_*.py"`: 73 tests, about 5 s. The full suite passes as well (178 tests).

| File | What it covers |
|---|---|
| `test_studio_security.py` (33) | Binding; the Host allowlist; token/cookie exchange and attributes; Origin and Sec-Fetch-Site; JSON-only writes; 405 without CORS; no CORS anywhere; CSP; body limit; traversal on ids, code and asset routes; symlink escapes; upload limits and types; atomic write; image sniffing; the draft gate |
| `test_studio_publish.py` (14) | A temp git repo with a bare remote: commit and push; only the page's files committed; dry run changes nothing; a failing build stops the run and restores the page; errors block; a push failure keeps the commit; unpublish; schedule; republish sets `updated`; nothing to commit is not an error; author from site.yml; the deploy command runs without a shell; a rename stages the old file's removal; a real `python -m bazinga build` in a dry run; the SSE stream over HTTP |
| `test_studio_pages.py` (17) | Front matter kept byte for byte, comments kept on patch, tricky values round-trip; starter drafts; save conflict (409); rename rewrites `[[links]]` and `builds_on` and moves the history; snapshots and dedupe; topic add; citation parsing, keys, append without reformatting |
| `test_studio_site.py` (3) | No Editor file in `_site` (production and `--drafts` builds), and no Editor addresses in the built site |
| `test_studio_js.py` (6) | `node --check` on every Editor script *as a .mjs copy*; imports are relative or in the pinned import map; the map is pinned; no machinery named in visible strings; writes send JSON, no FormData or EventSource |

## Verified in a real browser

Chrome via Playwright. The scripts are in the scratchpad (`scratchpad/studio/s1–s6.mjs`); they ran against a temp
git copy of the site with a bare remote.

- **Writing.**
  - Created a post, then typed Markdown with a numbered equation, an `[eq:…]` reference and `::figure
    softmax_temperature`. The preview updated with the rendered MathML and the working figure.
  - The "/" menu and the callout from it.
  - The equation helper, with a valid formula and with `\cancel`, which shows the converter's hint.
- **Panels.**
  - The Checks and Details drawers.
  - The Figures panel: a live, interactive frame; new from a starter, then edit and Save and test. Invalid code
    shows the traceback.
  - Citation lookup for a real arXiv id, online.
  - The link picker, `[[` completion, versions, and image paste-upload.
- **Publish.**
  - A dry run went through all steps, and `git status` of the site copy was unchanged afterwards.
  - The Schedule tab, blocked by a real check error.
- **Suggestion features,** against a fake OpenAI-compatible endpoint on localhost: equation from words, description
  Suggest, link and topic cards (accept and reject), and a figure draft tested before saving.
- **Forged requests.**
  - Host `evil.com` and `127.0.0.1.nip.io`: 403.
  - Foreign Origin: 403. `Sec-Fetch-Site: cross-site`: 403. text/plain body: 415.
  - The same-origin request: 200, with no CORS headers.
  - A fetch from another page could not read the API.
- **Layout and errors.**
  - No horizontal overflow at 1440, 1280, 1024 and 820 px. Below 980 px the preview and the writing pane toggle,
    and drawers overlay. Dark mode works.
  - No console errors (the last one was the missing favicon, now inline).

Screenshots are in the scratchpad: `scratchpad/studio/*.png`. Among them: 01-library(-dark), 04-editor-typed(-dark),
05-slash-menu, 06-equation, 06b-equation-error, 07-checks, 08-details, 09-figures, 10-publish, 11-publish-dry-run,
13-citation, 16/17/18 figures, 19-versions, 20-schedule, 22–26 suggestions, and r-1280/1024/820-*.

## Gaps

- **CodeMirror loads from esm.sh, so the editor needs a network connection.** research.md §6 suggests vendoring the
  modules into `studio/vendor/` for offline use; that is not done. The map comes from `vendor.CODEMIRROR_IMPORT_MAP`
  (with a pinned fallback in server.py), and `@codemirror/lang-python` is used for figure code when the map has it.
- Scroll sync is one way, from the editor to the preview.
- Link suggestions apply only while their sentence still appears word for word in the page.
- Renaming or unpublishing a published page adds no redirect. The Editor says the address changes.
- Scheduling relies on the host's daily build (core's README and the workflows).
- Only Chrome was checked; Safari and Firefox were not.

## Requests to the other builders

- **core, `cli.py`:** `studio` and `publish` use `nargs=argparse.REMAINDER`, which does not capture options that
  come first. `python -m bazinga editor --no-browser` fails with "unrecognized arguments"; it works with `--`.
  Suggested fix: parse with `parse_known_args()` and forward the extras, or add the options explicitly.
- **core, `build.preview_html`:** it renders every page on each call. That is fine for the example site; on a large
  site the Editor's preview, which runs about 300 ms after typing stops, would benefit from caching the other pages'
  renders by mtime.
- **core, `mathml.py`:** `\log p_i` renders as "logp" in Chrome (no space between the operator and its argument).
  Consider emitting `\log` and similar as `<mi>log</mi><mo>&#x2061;</mo>` (function application).
- **core and figures:** `node --check file.js` exits 0 on an ES module with a syntax error (Node's module detection
  hides it). Checking a `.mjs` copy catches it. This affects any test that runs `node --check` on module workers
  (`pyworker.js`, `test_fig_js.py`).
- **wiki, `llm.check_figure_source`:** it allows any standard-library import (`os`, `subprocess` …). The Editor adds
  its own stricter gate before running a draft, but `python -m bazinga wiki figure` users may want the same.
- **content:** the example posts are hard-wrapped at about 120 columns. In the Editor's proportional font, one line
  per paragraph reads more naturally. This is optional.
