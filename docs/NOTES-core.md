# Notes from the core builder

## What exists (owner: core)

- `bazinga/config.py`: `load(root)` merges `site.yml` over `DEFAULTS` and validates it (hex accent, origin, kinds, mode,
  width). `Config` allows attribute access (`cfg.site.name`) and has the paths `root`, `content_dir`, `figures_dir`,
  `drawings_dir`, `static_dir`, `out_dir`, `theme_dir` and `wiki_dir`. Also `set_root()` and `kind_id_prefix()`.
- `bazinga/content.py`: `Page`, `parse`, `load_file`, `load_pages`, `load_topics`, `load_references`, `content_files`,
  `kind_and_slug`, `slugify`, `reading_minutes` and `today()` (patch this to test scheduling).
  - `Page` also has `state` (draft/scheduled/published), `problems` (front-matter problems with lines) and
    `line_of(key)`.
- `bazinga/mathml.py`: `to_mathml(tex, display)`, `split_tag_label`, `preprocess`, `MathError(message, hint, offset)`.
  It does every rule in DESIGN.md plus a few more:
  - bold Greek through Unicode;
  - `\mathrm{ReLU}` as one identifier;
  - TeX spacing for `\log`, `\operatorname{…}` and similar;
  - limits underneath in display;
  - display style inside `aligned` arrays;
  - a LaTeX `<annotation>` on every formula.
- `bazinga/markdown.py`: `render(page, site) -> Rendered`, `SiteIndex(pages, references, topics, cfg, preview, hidden)`
  (pages may be a list or a dict), `references()`, `format_reference(_html)`, `render_inline()` and `pygments_css()`.
  - `Rendered` also has `equations` (label → number).
- `bazinga/checks.py`: `Issue`, `check_page`, `check_front_matter`, `check_body`, `site_for(page, all_pages, refs,
  topics, cfg)` (a public page may only link public pages), and `sort_issues`.
- `bazinga/build.py`: `build(cfg, drafts, strict, dev, quiet, out)`, `preview_html(page, cfg)`,
  `make_site_index(cfg, pages, refs, topics)`, `BuildError` and `Theme`.
  - It builds into `_site.partial/` and swaps it in at the end, so a failed build leaves the old `_site/`.
  - `preview_html` keeps every other page rendered, until a content file changes. A preview then costs one page
    render: about 3 ms on the example site against 85 ms cold.
- `bazinga/seo.py`: canonical, Open Graph, JSON-LD (BlogPosting, WebSite + Person, WebPage), sitemap, robots and the
  Atom feed (30 newest).
- `bazinga/vendor.py`: the pinned Pyodide 314.0.7, the CodeMirror import map (plus lang-python), and the Google Fonts
  URLs (one stylesheet per family).
- `bazinga/serve.py`: build, watch, reload over SSE (the script is injected by the server only), and `/api/ask/` →
  `ask_server.handle(…, cfg=cfg)` with a loader returning `{"passages", "graph"}`. `--drafts` previews drafts.
- `bazinga/cli.py`: `new`, `build [--drafts]`, `serve [--port] [--drafts]`, `check [files] [--errors-only]`,
  `cite <id> [--key]`, `figure new|test`, and the passthroughs `studio`, `publish` and `wiki`. Every option after
  those three is handed over untouched. `--root` works for every command.
- `bazinga/cite.py` (new file, used by the CLI and by the Studio's `lookup`): `parse_query`, `lookup` / `fetch`,
  `fetch_arxiv`, `fetch_crossref`, `make_key` (`Vaswani17`, then `Vaswani17b`), `add_reference` (appends to the file
  and returns the existing key when the arXiv id or DOI is already there), and `http_get` (mocked in tests).
- Theme:
  - templates: base, page, list, home, topic, topics, series, explore, ask, 404, and the partials header, footer and
    macros;
  - CSS: `tokens.css`, `site.css`, `math.css`;
  - `site.js`: the theme toggle, copy buttons, heading-link copy, the TOC highlight, and the TOC folding on phones.
- Content:
  - `site.yml`, documented inline;
  - `content/topics.yml`: 12 topics in 3 groups;
  - `content/references.yml`: Vaswani17, Hinton15, He15 and Kingma14, with arXiv ids checked against the arXiv API
    on 2026-10-20;
  - posts: `welcome.md` (the showcase), `writing-math.md` (the maths guide) and `notes-on-attention.md` (a draft);
  - `static/uploads/tiles.svg` and `bazinga/starters/post.md`.
- `requirements.txt` (numpy is pinned for the Fourier example) and `vercel.json`.
- Tests: `tests/test_core_{math,markdown,build,checks}.py` (75 tests) plus `test_core_support.py` (helpers only).

## How to run

```
.venv/bin/python -m unittest discover tests        # 253 tests, all OK (core + figures + wiki + studio)
.venv/bin/python -m bazinga build                  # production; stops with file:line on any error
.venv/bin/python -m bazinga serve --port 8000      # dev server with live reload
.venv/bin/python -m bazinga check                  # every page's issues, with hints
```

## Browser verification (Chrome via Playwright, scripts in scratchpad/core/)

- Pages checked: home, both posts, the lists, topics, a topic, series, a series page, explore, ask and 404.
- Widths 1440, 390 and 360, in light and dark: no horizontal overflow and no console errors. The only console message
  is the expected 404 status on `/nope/`.
- Also verified:
  - Maths renders.
  - The theme toggle switches and persists across a reload.
  - There are 16 copy buttons, and the TOC highlights the current section.
  - Live reload fires when a content file is touched.
  - `/api/ask/` answers `{"on": false}` when no model is set up.
- Screenshots are in `scratchpad/core/shots/`.

## For the lead

- Add `_site.partial/` and `_site.old/` to `.gitignore` (the build's staging folders; normally gone after a build).
- `vercel.json` cannot hold comments. Document in the README that `SITE_URL` must be set in the Vercel project when
  `site.origin` differs from the deployed host (wiki builder's note). The build command runs the tests first.
- No `netlify.toml` and no `.github/workflows/pages.yml` from me; they were not in my brief.
- The welcome post's table quotes the softmax figure's scores (3.0, 2.2, 1.6, 1.1, 0.4). If the figures builder
  changes `SCORES`, update that table.

## For the other builders

- Wiki: your requests 1–8 are done.
  - The apostrophe bug was smart quotes stored in Markdown's HTML stash. `to_plain` now restores them as text.
  - The page `<link rel="alternate" type="text/markdown">` is on every page of a production build. It is left out of
    `--drafts` builds.
  - `<link rel="describedby" type="text/markdown" href="/llms.txt">` is in base.html.
  - The explore subtitle is device-neutral.
  - The map container is `<div id="explore-root" class="map" data-explore data-graph="/data/graph.json"
    data-kinds='…'>`.
  - The Ask page container is `<div id="ask-page" data-mode="page" data-passages=… data-graph=…
    data-suggestions='[titles]'>`. The floating slot is `<div id="ask-root" data-page="{{ body_page_id }}">`.
  - `ask.js`, `explore.js` and `wiki.css` are included only when they exist.
- Figures: numpy is added. The Pyodide URL is unchanged (`vendor.PYODIDE_INDEX_URL` goes into
  `<meta name="bazinga-pyodide">`, and `<meta name="bazinga-root" content="/">` is there too). `figure.js` is loaded
  as a classic deferred script on every page.
  - `figure_html` and `drawing_html` receive `cfg=` from markdown.py. A FigureError or DrawingError is a page error:
    an error box in previews, a stopped production build.
  - Breakout: `.prose > .fig` and `.prose > .drawing` widen to `--wide` (1000 px) when there is room.
- Studio: your requests 1–4 are done.
  - Option passthrough works.
  - The `preview_html` cache is in place.
  - `\log p` now gets TeX's thin space, with tests in `test_core_math.Postprocess.test_function_names_are_spaced`.
  - `site.js` is a classic script, so plain `node --check` is the right test.
  - `build.make_site_index(cfg, pages, refs, topics)` exists, and `SiteIndex` accepts a dict of pages.

## Known gaps

- `aligned` rows that start with a tall fraction can shift their `=` a few pixels in Chromium.
- Inline maths cannot wrap. A very long inline formula can widen a line on a phone, so keep long formulas displayed.
- `[[id|text]]` link text is plain text: no Markdown inside it.
- Indented (4-space) code blocks are not protected from `$…$` processing. Use fenced code.
- The live-reload watcher polls every 0.5 s. That is fine for hundreds of files; for very large sites it could use
  the OS's file events.
- Changes to the engine's Python code need a restart of `serve`. Templates, CSS and JS reload live.
