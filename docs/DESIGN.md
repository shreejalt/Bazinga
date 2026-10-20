# Tessera — design spec

Tessera is an open-source template for technical blogs and personal sites. Its parts:
- **Posts** are Markdown, with real equations rendered at build time and interactive figures written as small Python files. The same Python runs at build time and again in the reader's browser.
- **The site is kept as an LLM wiki:** a catalog, a log, a knowledge-graph map, topic hubs and series, plus an **Ask** box on every page.
- **The Studio**, which runs on localhost only, is where authors write, check and **publish** like on Medium.

The name means one tile of a mosaic: every post is a tile and the map shows the mosaic. Change it in `site.yml`.

This file is the contract between the parts. Every builder reads it first. `docs/research.md` holds the sources.

## Principles

1. **One Python file, three places.** A figure's `compute()` runs at build time (static SVG in the HTML), in the browser on Pyodide (when the reader moves a control), and in the Studio (live preview). The SVG renderer (`tessera/plot.py`) is Python too, so the browser gets the *same* SVG the build made.
2. **Works without JavaScript.** Every page, equation, figure (at its defaults) and drawing is static HTML/SVG/MathML. JS only adds interaction, the map's hover, and Ask.
3. **Authors write Markdown, not HTML.** Everything has a short syntax and a Studio button. Errors are caught and explained with the line number, never silently rendered wrong.
4. **Models propose, people publish.** LLM features (optional, any OpenAI-compatible endpoint, a local Ollama included) write proposals; nothing a model writes reaches the site without the author accepting it.
5. **Publishing happens only on the author's machine.** The Studio is not part of the built site. No file of `tessera/studio/` is ever copied to `_site/`, and a test enforces this. The Studio:
   - binds to 127.0.0.1;
   - checks Host and Origin;
   - requires a per-launch token.

   The deployed site can only *answer* (Ask). It cannot write.
6. **Standard library first.** The runtime dependencies are Markdown, PyYAML, Jinja2, latex2mathml and Pygments. Python ≥ 3.11. No Node needed. CDN assets are pinned to exact versions in one place (`tessera/vendor.py`).
7. **Customisable without forking the engine.**
   - `site.yml` covers names, nav, colours, fonts, kinds, LLM provider and deploy command.
   - A `theme/` folder in the site root overrides any template or asset of `tessera/theme/` by the same path.

## Repository layout (the template repo)

```
README.md            quick start, screenshots, feature tour
LICENSE              MIT (code). content/LICENSE: CC BY 4.0 for the example posts (authors replace with their own)
THIRD_PARTY.md       Pyodide (MPL-2.0), CodeMirror (MIT), fonts (OFL), latex2mathml (MIT) …
AGENTS.md            the wiki schema for coding agents (Karpathy's LLM-wiki "schema" layer): how pages, index, log work
site.yml             all configuration (see below)
requirements.txt
tessera/             the engine (a Python package, run as `python -m tessera <command>`)
  __init__.py  __main__.py  cli.py
  config.py          load + validate site.yml, defaults, paths (ROOT = cwd)
  content.py         load pages from content/<kind>/*.md: front matter, ids, status, dates, series
  markdown.py        Markdown → HTML: math, [[links]], [@KEY] cites, ::figure, ::drawing, callouts, footnotes, code
  mathml.py          LaTeX → MathML with pre/post-processing and validation (MathError with line + hint)
  checks.py          all checks on a page (used by build, `tessera check`, the Studio)
  graph.py           the site graph: nodes, edges, backlinks, related, series order, topic hubs, map layout
  figures.py         discover figures/*.py, validate the contract, run compute at build, write data + static SVG
  plot.py            figure spec → SVG (runs at build AND in the browser; stdlib only)
  draw.py            diagram kit for drawings/*.py → SVG (stdlib only)
  drawings.py        run `::drawing module.fn` at build
  wiki.py            generated wiki files: wiki/index.md, wiki/log.md, passages, llms.txt, llms-full.txt, page .md copies
  retrieve.py        BM25 + graph answer (runs at build tests, in the browser on Pyodide, and in api/ask.py; stdlib only)
  llm.py             OpenAI-compatible client + the proposal operations (ingest, lint, highlights, describe, equation, figure)
  ask_server.py      the "written answer" handler, shared by api/ask.py (Vercel) and `tessera serve`
  seo.py             sitemap.xml, robots.txt, feed.xml, JSON-LD, Open Graph, canonical
  build.py           orchestrates a full build into _site/
  serve.py           dev server: build + watch + reload + /api/ask locally
  vendor.py          every pinned CDN URL (Pyodide, CodeMirror via esm.sh import map, fonts)
  theme/             default theme
    templates/       base.html, page.html, list.html, home.html, topic.html, topics.html, series.html, explore.html, ask.html, 404.html, partials/
    assets/css/      tokens.css (all colours/fonts/sizes as CSS variables, light + dark), site.css, math.css, figure.css
    assets/js/       site.js (theme toggle, nav, copy buttons), figure.js (controls → worker), pyworker.js (module worker running Pyodide),
                     explore.js (map), ask.js (Ask page + floating widget)
  studio/            LOCAL ONLY — never copied to _site
    server.py        http.server on 127.0.0.1, token + Host/Origin checks, JSON API, SSE for publish logs
    api.py           the handlers (pages, render, figures, cite lookup, checks, llm proposals, publish)
    publish.py       the publish pipeline
    static/          index.html, studio.css, studio.js, editor.js (CodeMirror 6 via import map), panels/*.js
  starters/          post.md, figures/{slider_plot,compare_bars,heatmap,geometry2d,animation}.py, drawings/{pipeline,blocks}.py
api/ask.py           Vercel Python function: thin wrapper over tessera.ask_server
content/
  posts/*.md         example posts (one showcase post that uses every feature)
  projects/*.md
  topics.yml         the allowed topics (grouped)
  references.yml     citation library
  series/            generated series highlights (proposals accepted by the author)
figures/*.py         the site's interactive figures (examples)
drawings/*.py        the site's diagrams (examples)
static/              images and files copied as-is (static/uploads/ for Studio uploads)
wiki/                GENERATED and committed: index.md (catalog), log.md (append-only log) — the agent-facing wiki
proposals/           LLM proposals waiting for the author (git-ignored by default)
tests/
vercel.json  netlify.toml  .github/workflows/pages.yml (GitHub Pages)
```

## site.yml (defaults shown; config.py fills anything missing)

```yaml
site:
  name: "Tessera"
  author: "Your Name"
  tagline: "Notes on things I am learning"
  description: "≤155 characters for search engines"
  origin: "https://example.com"        # canonical origin, no trailing slash
  language: en
  avatar: static/avatar.png             # optional
  links: {github: "", x: "", linkedin: "", email: "", scholar: ""}
nav: [{label: Writing, href: /posts/}, {label: Projects, href: /projects/}, {label: Map, href: /explore/}, {label: Ask, href: /ask/}]
kinds:                                  # each kind is a folder content/<kind>/ and a list page /<kind>/
  posts:    {label: Writing,  singular: Post}
  projects: {label: Projects, singular: Project}
home: {intro: "A paragraph about you (Markdown).", show: [latest, series, map]}
theme:
  accent: "#3b5bdb"                     # one colour; tokens.css derives the rest
  font_text: "Source Serif 4"           # Google Fonts names
  font_ui: "Inter"
  font_code: "JetBrains Mono"
  font_math: "STIX Two Math"
  width: 720                            # reading column in px
  mode: auto                            # auto | light | dark
features: {ask: true, explore: true, series: true, feed: true, llms_txt: true}
llm:                                    # optional; everything works without it except proposals + written answers
  base_url: "https://openrouter.ai/api/v1"   # any OpenAI-compatible /chat/completions (OpenAI, OpenRouter, Ollama http://localhost:11434/v1 …)
  model: ""                             # e.g. "openai/gpt-4o-mini" or "llama3.1"; comma-separated = fallbacks
  key_env: "LLM_API_KEY"                # name of the env var holding the key (.env.local is read too, never committed)
ask:
  written_answers: true                 # needs llm.model + key on the server
  per_visitor: 5                        # per IP per day
  daily_cap: 300
publish:                                # what Publish runs after building, on the author's machine
  commit: true                          # git add the post (+ its figures/drawings/uploads/references) and commit
  push: true                            # git push (Vercel/Netlify/GitHub Pages then deploy from the repo)
  command: ""                           # optional extra command, e.g. "vercel deploy --prod --yes"
  author: ""                            # optional "Name <email>" for commits; default is git's own config
```

## Content model

A page is `content/<kind>/<slug>.md`. Its id is `<kind-singular-lowercase>:<slug>`, for example `post:attention` or `project:robot`. Its URL is `/<kind>/<slug>/`.

Front matter (YAML):

```yaml
title: "Attention, Step by Step"        # required
date: 2026-10-20                        # required for published pages
status: draft                           # draft | published   (default: published, so hand-written files just work)
updated: 2026-10-21                     # optional: when really revised
summary: "Two or three sentences shown in lists and the map."   # required for published
description: "≤155 chars for search"    # optional; else cut from summary
topics: [attention, transformers]       # 1–4, each must exist in content/topics.yml
series: {name: "Transformers", part: 2} # optional
builds_on: [post:query-key-value]       # optional: prerequisite pages (graph edges, "read first")
cites: [VASW17]                         # optional: keys in content/references.yml (also collected from [@KEY] in the body)
cover: static/uploads/x.png             # optional share image
```

Rules:
- **What is public:** a page is public when `status: published` and `date <= today`. A future date means scheduled: it appears on the first build after that date. Drafts and scheduled pages are never written to `_site`, the sitemap, the feed, the wiki files or the passages. The Studio previews them.
- **Topics:** `topics.yml` looks like `{groups: [{name: "Methods", topics: [{slug: attention, label: "Attention", blurb: "…"}]}]}`. An unknown topic is an error with a "did you mean".
- **References:** `references.yml` maps `KEY: {title, authors: [..], year, venue, arxiv?, doi?, url?}`.

## Markdown syntax (markdown.py) — all of it is in the showcase post and the Studio's "/" menu

| Write | Get |
|---|---|
| `$x^2$` inline, `$$ … $$` on its own lines (display) | MathML (`<math>`); display math is numbered with `\tag{n}` or `{#eq:name}` after the closing `$$` |
| `\begin{aligned}…\end{aligned}`, `align` | rewritten to an `array` that renders correctly |
| `[[post:attention]]`, `[[post:attention|this post]]` | a link plus a "mentions" graph edge; an unknown id is an error |
| `[@VASW17]`, `[@VASW17, p. 4]` | numbered citation linking to the reference list at the end of the page |
| `::figure name` / `::figure name \| start: Preset label` | the interactive figure (static SVG + controls) |
| `::drawing module.fn \| caption` | static SVG diagram |
| `> [!NOTE]`, `> [!TIP]`, `> [!WARNING]`, `> [!KEY]` (first line of a blockquote) | callout boxes |
| `[^1]` footnotes, tables, fenced code with language, `==highlight==`, `~~del~~` | the usual, code highlighted at build (Pygments classes, themed by CSS) |
| `![alt](static/uploads/x.png "caption")` | `<figure>` with caption; missing alt is a check warning |
| `## Heading {#id}` | stable anchors; every h2/h3 gets an id and a hover link |

**Math pipeline (mathml.py).** Pre-process, convert with latex2mathml, post-process, then validate.
- **Pre-processing:**
  - `aligned`/`align`/`align*`/`gather` become `\begin{array}{rl}`.
  - `\\[4pt]` becomes `\\`.
  - `\arg`, `\argmax`, `\argmin` and `\operatorname*` become `\operatorname{…}`.
  - `\boldsymbol` and `\bm` become `\mathbf` (Chromium ignores bold-italic).
  - `\big`/`\Big`/`\bigg` and their l/r forms are dropped (MathML stretches).
  - `\text{}` keeps its spaces.
  - `\tag{..}` and `\label{..}` are taken out into the equation number.
- **Validation:** after conversion it rejects any `<mi>\`-leaked command, `menclose`, `mfenced` or `linebreak=`. It raises `MathError(message, line, hint)` with a plain-English hint, for example "\\cancel is not supported in browsers' math; try \\not or colour".
- **Mobile:** display math sits in `<div class="math-display">`, which scrolls horizontally on phones.

## Interactive figures (figures/<name>.py)

The contract. `figures.py` validates it; the Studio's starters follow it.

```python
TITLE = "Softmax temperature"                 # shown above the figure
CAPTION = "What the slider does, in one or two sentences."
REQUIRES = []                                 # optional Pyodide packages, e.g. ["numpy"] (build env must have them too)
CONTROLS = [                                  # rendered as HTML controls in this order
  {"name": "t", "kind": "slider", "label": "temperature", "min": 0.1, "max": 5, "step": 0.1, "value": 1, "play": False},
  {"name": "k", "kind": "steps",  "label": "classes", "options": ["3", "5", "10"], "value": 0},
  {"name": "log", "kind": "toggle", "label": "scale", "options": ["linear", "log"], "value": 0},
]
PRESETS = [{"label": "sharp", "values": {"t": 0.2}}]   # optional buttons; "Reset" is always added
def compute(t=1.0, k=0, log=0, _narrow=0):    # pure: same inputs → same spec; _narrow=1 for a phone layout
    return {...spec...}
```

**The spec** (plot.py renders it to SVG; every field optional unless stated):

```python
{"panels": [ {                                   # 1–4 panels, laid out in a row (column when _narrow)
    "kind": "xy",                                # xy | bars | heatmap | scene (free 2-D shapes in data units)
    "title": "…", "x_label": "…", "y_label": "…",
    "x": [..] , "x_min": .., "x_max": .., "y_min": .., "y_max": .., "x_log": False, "y_log": False,
    "series": [ {"name": "…", "y": [..], "x": [..optional..], "style": "main|second|third|muted|dashed|area|points",
                 "label_at": "end|none"} ],
    "bars": [ {"label": "…", "value": .., "style": "main|muted|…", "note": "…"} ],        # kind=bars
    "matrix": [[..]], "row_labels": [..], "col_labels": [..], "range": [lo, hi], "show_values": False,   # kind=heatmap
    "shapes": [ {"type": "point|line|arrow|polygon|circle|rect|text", ...data-unit coords..., "style": "…", "label": "…"} ],
    "marks": [ {"x": .., "label": "…"} , {"y": .., "label": "…"} ],                # reference lines
    "annotations": [ {"x": .., "y": .., "text": "…"} ] } ],
  "readouts": [ {"label": "…", "value": "…", "note": "…"} ],   # number tiles under the plot (HTML)
  "note": "one line of plain text under the readouts" }
```

- **Styles are names, not colours.** CSS gives every style its colour from `tokens.css`, so figures follow the theme and dark mode automatically.
- **Labels never overlap.** plot.py places series end labels and annotations with a small collision-avoidance pass.
- **The build** (`figures.py`):
  - imports each used figure;
  - checks the contract;
  - runs `compute()` at the defaults and at `_narrow=1`;
  - renders it to SVG with `plot.py`;
  - embeds the SVG in the page;
  - writes the module source to `_site/figures/<name>.py` and `plot.py` to `_site/figures/_plot.py`.
- **The browser** (`figure.js` + `pyworker.js`):
  - The figure is a `<figure class="fig" data-figure="name" data-controls='json'>` holding the static SVG and controls.
  - On the first interaction, or when the figure is near the viewport and idle, a **module worker** boots Pyodide from `vendor.py`'s pinned URL, loads `REQUIRES`, and fetches the module and `_plot.py`.
  - Each control change then posts `{name, values, narrow}` to the worker; requests are coalesced so only the latest is kept. The worker returns `{svg, readouts_html}`, which replaces the old one.
  - While the worker boots, the controls already move and a small "Loading…" shows. If Pyodide fails, a plain message appears and the static figure stays.
  - Slider "play" animates the value with requestAnimationFrame, throttled to the worker's speed.
  - Reset and presets set values and recompute.
- **Performance budget:** `compute()` plus render under 30 ms (a test runs every figure at defaults, presets and 20 random control states; it fails on an exception, NaN or a slow state).

## Drawings (drawings/<module>.py)

Each function returns an SVG string built with `tessera.draw`. The kit has:
- `Diagram(width, height)`;
- `box(x, y, w, h, text, style)`, `arrow(a, b, label)`, `row(...)` / `column(...)` / `grid(...)` layouts, `group(label, items)`, `note(text)`;
- `.svg()`.

Styles are named and themed by CSS, as in figures. Diagrams are drawn at build time only, so no JS is needed.

## The graph and the wiki

- **graph.py** builds one graph from the public pages.
  - **Edges:** `builds_on` (directed), `mentions` (from `[[id]]`), `cites` (shared reference keys), `topic` (shared topics, weak) and `series` (consecutive parts).
  - **It gives:**
    - backlinks per page;
    - "related" (top 5 by weighted edges);
    - a reading order per series;
    - topic hubs (pages and their figures per topic);
    - a deterministic 2-D layout for the map (a force layout with a fixed seed, run at build time);
    - rings per node (nearest-first BFS distance) for the map's hover.
- **Generated wiki files** (`wiki.py`, every build, no model needed). These *are* Karpathy's index + log:
  - `wiki/index.md`, committed: a catalog with one line per public page (`- [Title](/posts/x/) — summary · topics · builds on …`), grouped by kind and topic. An agent reads it first.
  - `wiki/log.md`, append-only: `## [YYYY-MM-DD] publish | Title`, `ingest | …` and `lint | …`. Publish, ingest and lint append to it.
  - `_site/llms.txt` follows the llmstxt.org layout: H1 site name, `>` description, `## Writing` / `## Projects` link lists with summaries, `## Optional` for topics and series.
  - `_site/llms-full.txt` is every public page as Markdown, joined.
  - `_site/<kind>/<slug>/index.md` is a Markdown copy of each page, with `<link rel="alternate" type="text/markdown">`.
  - `_site/data/passages.json` holds one passage per section (h2/h3) of every page, as plain text: `{id, title, url, section, anchor, text}`.
  - `_site/data/graph.json` holds the nodes (id, title, url, kind, summary, topics, x, y), the edges and the rings.
- **LLM operations** (`llm.py`, CLI `tessera wiki <op>`, and Studio buttons). They write `proposals/<op>-<slug>.md` (or JSON for the Studio) and never edit content:
  - `ingest <page>` proposes topics, builds_on, `[[links]]` to add (with the sentence they fit in), a summary, a description, three questions the page answers, and series membership.
  - `lint` runs fixed rules (orphans, one-way links, thin topics, pages without figures, stale `updated`) and, with a model, flags contradictions between pages that share a topic.
  - `highlights <series>` writes 3–4 highlights per part from the part's own text; numbers must appear in the page or the line is rejected.
  - `describe <page>` writes a ≤155-character description from the page's own words.
  - `equation "<words>"` turns words into LaTeX (Studio equation helper).
  - `figure "<description>"` drafts a figure module from the closest starter. The Studio runs it through the contract test before showing it.
- **Ask** (`retrieve.py`, the same code everywhere):
  - **The browser box:** the `/ask/` page and the floating "Ask" button on every page (which takes the current page as context). It runs `retrieve.answer(question, passages, graph, page=None)` on Pyodide. That does BM25 over the passages, boosted for the current page and its graph neighbours, and returns the top passages, the pages they come from, and a short extractive answer. The quick answer needs no server.
  - **A "Written answer" button** appears when `/api/ask/` says it is on. It POSTs `{q, page}` to `api/ask.py`, which picks passages with the same `retrieve` code and asks the configured model to answer **only** from them with numbered citations. It has per-IP and daily limits and stores nothing. Locally, `tessera serve` serves the same endpoint.

## The Studio (local only)

`tessera studio` (or `python -m tessera studio`):
- picks a free port on **127.0.0.1**;
- prints `http://127.0.0.1:<port>/?token=<random>` and opens the browser;
- swaps the token for a `SameSite=Strict`, HttpOnly cookie.

**Every request is checked:**
- The Host must be `127.0.0.1:<port>` or `localhost:<port>`.
- Writes must be POST with JSON, a matching Origin (or `Sec-Fetch-Site: same-origin`) and the cookie.
- No CORS headers are sent.
- Paths must resolve inside `content/`, `figures/`, `drawings/`, `static/uploads/` or `content/references.yml`.
- Writes are atomic (temp file then rename).
- git and the publish command run with argument lists, never a shell string. The optional `publish.command` is split with `shlex.split`.

**Screens:**
1. **Library.** All pages with their status pill (Draft / Scheduled / Published), word count, figures, last edited and check badges. Search, filter by kind/status, and a **New post** button (title + kind → slug → file from `starters/post.md`, status draft).
2. **Editor.** Two panes, resizable:
   - **Left:** CodeMirror 6 Markdown with LaTeX-aware highlighting. It has autocomplete for `[[ids`, `[@keys`, `::figure names` and topics.
   - **Right:** the live preview, rendered by the *real* `markdown.py` + theme (an iframe of `/preview/<id>`, updated within ~300 ms of typing, scroll-synced). Its interactive figures work through the same worker.
   - **Top bar:** title, status pill, Save state ("Saved" / "Saving…"; autosave every 2 s after typing stops, plus a version snapshot in `.studio/history/`), **Checks** (count), **Publish**.
   - **The "/" menu** (and toolbar): Heading, Equation…, Inline math, Figure…, Drawing…, Citation…, Link to page…, Callout, Table, Image upload, Code block, Footnote, Divider.
   - **Equation helper:** a LaTeX field with live MathML, a palette (Greek, operators, fractions, sums/integrals, matrices, cases, arrows, accents), validation messages from `mathml.py` with the hint, "Describe in words" (llm, optional), and display/inline plus a name for references.
   - **Figure panel:**
     - Pick an existing figure (live preview), or **New figure** from a starter (slider plot, compare bars, heatmap, 2-D geometry, animation) or from a description (llm).
     - The figure's Python opens in an editor; Save runs the contract test and shows the preview or the traceback.
     - The figure is inserted as `::figure name`.
   - **Drawing panel:** the same, from the drawing starters.
   - **Citation panel:** paste an arXiv id/URL or DOI. It fetches from the arXiv API or Crossref, shows the record, lets the author edit the key, saves it to `references.yml` and inserts `[@KEY]`.
   - **Details drawer** (front matter as a form): title, slug (rename-safe), summary, description with a 155 counter and "Suggest" (llm), topics (chips from `topics.yml`, "add topic"), series, builds_on (page picker), cover image, date, and schedule.
   - **Checks drawer:** live results from `checks.py`, such as math errors, unknown ids/keys/topics, images without alt, a missing summary, a description that is too long, headings that skip a level, very long display equations, broken links and figure errors. Each result shows its line; clicking it jumps there.
3. **Publish** (a dialog with a step list and live log over SSE):
   1. Checks. Errors block; warnings ask.
   2. Set `status: published`, `date` (today unless scheduled) and `updated` when republishing.
   3. Run the tests for the figures this page uses.
   4. Build the site.
   5. Update the wiki files (index, log entry `publish | Title`, passages).
   6. Optional: "Ask the model for links and topics" shows the ingest proposals as accept/reject cards before committing.
   7. `git add` the page, its figures/drawings/uploads and references, wiki/index.md and wiki/log.md, then `git commit -m "Publish: <title>"`.
   8. `git push`, then the optional `publish.command`.
   9. Show the live URL.
   - **Unpublish** sets status back to draft and runs steps 4–8.
   - **Schedule** sets a future date: the page goes live on the first build after it. The README explains a daily cron build on Vercel or Netlify, and the GitHub Pages workflow has a daily schedule.

## Theme and look

The look is calm and editorial: a reading column of about 720 px, a generous serif for text and a clean sans for the UI. Figures may break out to about 1000 px.
- **Colour:** `tokens.css` derives everything from one `--accent`, with light and dark palettes (`prefers-color-scheme` plus a toggle stored in localStorage).
- **Pages:**
  - **Home:** intro, latest posts, series, a small map teaser.
  - **Lists:** cards with summary, topics and reading time.
  - **Post:**
    - title, summary, meta (date, reading time, series position);
    - a table of contents at the side on wide screens;
    - the body, then a "Connections" block (builds on, read next, backlinks, related) and the references.
  - **Topic hub:** intro, pages, and the live figures from those pages.
  - **Series:** parts in order with highlights.
  - **Explore:** the map.
  - **Ask:** the Ask page.
  - **404.**
- **Mobile:** no horizontal overflow at 360–1440 px; verify in a browser.
- **Accessibility:** controls are real `<input>`s with labels, focus rings show, the SVGs have titles, and colour is never the only cue.
- **Wording:** plain everywhere. Never name the machinery on the page: no "Pyodide", "Python" or "BM25" in visible text. Status text is plain, such as "Loading…" or "Answered from 214 passages of this site".

## CLI (cli.py)

```
python -m tessera new "Title" [--kind posts]       new draft from the starter
python -m tessera build [--drafts]                 build _site/ (drafts only with --drafts, for previews)
python -m tessera serve [--port 8000]              build, watch, live-reload, /api/ask locally
python -m tessera studio                           the local editor (127.0.0.1 only)
python -m tessera check [file ...]                 run the checks; exit 1 on errors
python -m tessera figure new <name> --from slider_plot | figure test [name]
python -m tessera cite <arxiv-id|doi> [--key KEY]  add a reference
python -m tessera wiki index|ingest|lint|highlights|describe [args]
python -m tessera publish <file>                   the Studio's publish pipeline, from the terminal
```

## Tests (tests/, unittest, must pass before a deploy)

The tests cover:
- the math cases (every pre-processing rule, the rejection list, error messages with line numbers);
- the Markdown extensions;
- content rules (drafts and scheduled pages never public);
- graph edges and backlinks;
- the wiki files (index, llms.txt layout, passages);
- `retrieve` ranking on a fixture;
- the figure contract plus every figure in `figures/` at defaults, presets and random states (< 30 ms, no NaN, valid SVG);
- drawings;
- the Studio security (Host, Origin, token, path traversal, no Studio files in `_site`);
- the publish pipeline in a temporary git repo (a dry run with no push);
- the example site building end to end;
- `node --check` on every JS file when node is available.

## Deploy

- **Vercel:** `vercel.json` runs `pip install -r requirements.txt && python -m unittest discover tests && python -m tessera build`. `api/ask.py` is the function.
- **Netlify:** `netlify.toml` gives the same build; Ask's written answers are off (static only), unless the author adds a Netlify function.
- **GitHub Pages:** `.github/workflows/pages.yml` builds on push and daily (for scheduled posts) and deploys `_site`. Written answers are off.
- **Any static host:** upload `_site/`.

## The default theme (rail and paper sheet)

The default theme follows the owner's own site: a rail (brand, sections, buttons, date) on a recycled-paper ground and
each page as a paper sheet; STIX Two Text and Courier Prime; reads and papers in a memo layout (header block, title,
series strip, Summary, contents with page numbers, numbered sections, Connections with the links figure, Related / Go
deeper / Go broader, Papers, older/newer). Kinds carry a `role` (read, paper, project, external). The home page, the CV
(`content/cv.yml`), lists (ten rows a page, filter), series, topics with live figures, Explore and Ask follow it too.
`tessera/mapview.py` (standard library) computes the map layout, every page's view (related, reading order, the hover
motion), the links figure and the series finder; the build writes `/data/site.js`, `/data/map.json`,
`/data/mapdata.json`, `/data/series.json` and `/data/view/<id>.json`, and ships the module as `/figures/_mapview.py`
for the Explore page's "chain between" and "in reading order". There is no dark mode. `tessera serve` starts the Studio
and adds a Write button (and Edit this page) at the theme's `<!-- local-tools -->` mark as it serves; builds never
contain them.
