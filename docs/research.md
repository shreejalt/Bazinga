# Prior-art research for the technical-blog template

Researched online on 2026-10-20. "Verified" means I ran it myself: headless Chrome over CDP, or the package in a
scratch venv. Everything else comes from the linked source.

## 1. Karpathy's LLM Wiki, and llms.txt

**LLM Wiki** (gist "llm-wiki.md", created 2026-04-04): https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f
- The gist is an "idea file" you paste into an agent. Its alternative to per-query RAG is a persistent, compounding wiki
  that the LLM maintains.
- Three layers:
  - **Raw sources**: immutable. The LLM reads them and never edits them.
  - **The wiki**: LLM-written Markdown (summaries, entity and concept pages, comparisons, an overview). The LLM owns
    it; the human reads it.
  - **The schema**: CLAUDE.md or AGENTS.md, holding the conventions and workflows. It "co-evolves" with the user.
- Two special files:
  - `index.md` is content-oriented: a categorised catalog of every page, each with a link, a one-line summary and
    optional metadata. The agent reads it first when answering and updates it on every ingest. The gist says this is
    enough at around 100 sources and hundreds of pages, without embeddings.
  - `log.md` is chronological and append-only. Entries use a fixed prefix, `## [2026-04-02] ingest | Title`, so that
    `grep` and `tail` work on it.
- Three operations:
  - **ingest**: read one source, discuss it, write a summary page, update the index, revise the 10–15 related pages,
    append to the log. Karpathy prefers one source at a time, supervised.
  - **query**: read the index, then the relevant pages, then answer with citations. Good answers can be filed back as
    new pages.
  - **lint**: look for contradictions, stale claims, orphan pages, missing concept pages, missing cross-references, and
    gaps that web search could fill.
- Tooling the gist names: Obsidian (graph view shows hubs and orphans), qmd (local hybrid BM25/vector search with CLI
  and MCP; simpler scripts work at small scale), Web Clipper, Dataview, Marp, git.

**llms.txt** (https://llmstxt.org/):
- Location is `/llms.txt`, or a sub-path such as `/docs/llms.txt`; the most specific file wins.
- Format is Markdown in this order: an H1 with the name (the only required part), a `>` summary, free body text, then
  H2 sections of link lists, each item `[name](url): notes`. An H2 named `Optional` holds links an agent may skip.
- Each page should also exist as clean Markdown at `page.html.md` or `page.md` (`index.html.md` for directory URLs).
- Discovery uses `<link rel="alternate" type="text/markdown">` for a page's Markdown and `rel="describedby"` for its
  llms.txt, as an element or an HTTP `Link:` header.

**llms-full.txt** is not in the spec. It is a de-facto convention: the whole corpus concatenated into one file. Mintlify
generates both files and caps the generated llms.txt at 100k characters; docs.claude.com publishes both.
https://mintlify.com/docs/ai/llmstxt

## 2. Prior art for interactive and computational blogs

| Tool | Does well | Pain points |
|---|---|---|
| **Distill template** (https://github.com/distillpub/template, Apache-2.0) | Article typography: margin notes, footnotes, BibTeX citations, hover previews, figure layout grid | Self-described "research code". The journal went on hiatus because interactive articles cost too much to make: "more than 50 hours of help" per early article, editor burnout (https://distill.pub/2021/distill-hiatus/). Lesson: keep the per-figure cost low. |
| **Quarto + quarto-live** (https://github.com/r-wasm/quarto-live, MIT) | `{python}` becomes `{pyodide}` with `format: live-html`, giving editable cells that run in the browser. OJS `viewof` sliders react without WASM. Exercises and grading | Needs the Quarto CLI plus Jupyter or knitr. No tagged releases. Two reactive systems (OJS and Pyodide) to learn. Readers get notebook-style cells, not authored figures. |
| **MyST / Jupyter Book 2** (mystmd 1.11.0, 2026-09-21; https://github.com/jupyter-book/mystmd/releases) | Best-in-class cross-references, labelled equations, citations and hover previews. Executable figures through Binder or JupyterLite. `{anywidget}` directive (experimental since 1.8.2) | Node toolchain plus a themed React site. Heavy for a personal blog. Interactivity leans on kernels and widgets. |
| **Observable Framework** (v1.13.4; https://github.com/observablehq/framework) | Data loaders in any language (a `.py` file's stdout becomes static data), live preview that re-runs loaders, Plot/D3 front end | The browser never runs Python, so every interactive part is JS. The `deploy` command is deprecated. Release activity has slowed. |
| **marimo WASM** (https://docs.marimo.io/guides/exporting/webassembly_html/) | `marimo export html-wasm --mode run` gives a self-contained page on Pyodide; local modules ship as wheels. "Islands" embed reactive cells in any HTML via `@marimo-team/islands` | Notebook-shaped. Islands are a low-level API with no SSG integration guide. Not every package runs in Pyodide. |
| **Idyll** (https://github.com/idyll-lang/idyll) | Markup language for explorable essays with reactive variables bound to components | Stalled: no releases listed. Its JS component model is a dead end for Python authors. |

Takeaway: none of these combines "Python file per figure, computed at build time, with a static fallback" and "same
code re-run in the browser on interaction". Quarto-live and marimo come closest, but both are notebook-centric.

## 3. Local editing and publishing

- **Decap CMS local backend** (https://decapcms.org/docs/decap-proxy/):
  - Set `local_backend: true` and run `npx decap-server` (port 8081); the admin UI lives at `/admin`.
  - It writes files and does not commit them. `editorial_workflow` (draft → review → publish) is unavailable locally.
  - Security history: CORS was `*` before 3.8.0. It now allows only localhost origins and offers `BIND_HOST` and
    `ORIGIN` settings.
- **Keystatic** (https://keystatic.com/docs/local-mode): `storage: {kind: 'local'}` writes straight to the filesystem
  from a typed schema of collections and singletons. GitHub mode is the team option.
- **TinaCMS** (https://tina.io/docs/faq): local mode needs no login and talks to `localhost:4001`. A database or index
  layer caches the Markdown. Self-hosting needs a GraphQL backend and loses search and git-backed media. Too heavy for
  a stdlib-leaning template.
- **Front Matter CMS** (VS Code extension; https://docs.astro.build/en/guides/cms/frontmatter-cms/): content dashboard,
  content types that map front-matter fields, a "start server" button and preview, all inside the editor. Works with
  any SSG.
- **Ghost Koenig** (https://ghost.org/help/publishing-content):
  - `/` at the start of an empty line opens a card menu (image, code, Markdown, HTML).
  - Markdown shortcuts work inline (`---`, three backticks); images can be dragged in.
  - Preview is Cmd/Ctrl+P, with desktop/mobile and web/email views.
  - Publishing offers "Schedule for later", which is status `scheduled` plus a future `published_at`.
- **Best pattern for us**:
  - Files on disk are the single source of truth, edited directly.
  - Front matter carries `status: draft|published`; scheduling, if added, is a future `date` that the build skips.
  - The UI is a split view (CodeMirror plus live preview), with a `/` menu for equation, figure, citation and drawing.
  - Publish is explicit: run the checks, flip the status, build, then `git commit` + `push` or the deploy CLI. Show the
    diff before committing.
  - No database or index layer, matching Decap/Keystatic local mode.
- **Localhost server security**:
  - Precedent: Vite CVE-2025-24010 (https://github.com/advisories/GHSA-vg6x-rcgg-rjx6). Three bugs combined: CORS `*`,
    no Origin check on the WebSocket, and no Host check, which allowed DNS rebinding. The fix was an `allowedHosts`
    allowlist and an Origin check (https://vite.dev/config/server-options#server-allowedhosts).
  - Do this:
    1. Bind to `127.0.0.1` only.
    2. Reject any request whose `Host` is not `127.0.0.1:<port>` or `localhost:<port>`.
    3. On state-changing requests, require an `Origin` (or `Sec-Fetch-Site: same-origin`) that matches.
    4. Send no CORS headers at all.
    5. Require a random per-launch token (`secrets.token_urlsafe(32)`), passed once in the URL as Jupyter does, then
       stored in a `SameSite=Strict` HttpOnly cookie or sent in a custom header (a custom header forces a CORS
       preflight).
    6. Resolve every path to the absolute path and check that it stays inside `content/`.
    7. Write files atomically (temp file, then `os.replace`).
    8. Never `shell=True`; pass git arguments as a list.
  - Chrome's Local Network Access prompt is extra protection; do not rely on it.

## 4. Pyodide (verified 2026-10-20)

- **Latest stable is 314.0.7**: https://github.com/pyodide/pyodide/releases and https://pyodide.org/en/stable/.
  - Versioning now follows CPython: 314.x means Python 3.14. 314.0.0 shipped 2026-06-09, after 0.29.x.
  - Since PEP 783, wheels can be published to PyPI with `pyemscripten_2026_0` tags.
  - https://blog.pyodide.org/posts/314-release
- **CDN**:
  - `https://cdn.jsdelivr.net/pyodide/v314.0.7/full/pyodide.mjs`; `indexURL` is
    `https://cdn.jsdelivr.net/pyodide/v314.0.7/full/`.
  - Breaking change in 314: classic workers (`importScripts`) are no longer supported. Use `new Worker(url,
    {type: "module"})`. Also, `pyodide.asm.js` became `.mjs` and `fullstdlib` does nothing.
- **Packages**:
  - `await pyodide.loadPackage("numpy")` loads from the distribution; I verified it gives numpy 2.4.6 on Python 3.14.2.
  - `loadPackagesFromImports(code)` resolves distribution packages only.
  - `micropip.install()` handles pure-Python wheels from PyPI.
  - https://pyodide.org/en/stable/usage/loading-packages.html
- **Worker pattern** (https://pyodide.org/en/stable/usage/webworker.html):
  - Start `loadPyodide()` once at worker start.
  - Messages carry `{id, python, context}`; replies carry `{id, result|error}`.
  - Load each figure's packages in the worker, not on the main thread.
- **Measured startup**, headless Chrome on a fast connection, module worker:
  - Cold: core 1.16 s plus numpy 0.32 s.
  - Warm cache: 0.85 s plus 0.16 s.
  - So: start the worker on the first interaction or when a figure scrolls into view, and keep the build-time SVG
    visible until the worker is ready.

## 5. MathML in 2026

- **Browser support**:
  - Chrome and Edge 109+ (Jan 2023), Firefox (all versions) and Safari 10+ (including iOS and iPadOS): about 96% of
    global usage (https://caniuse.com/mathml).
  - MathML Core is a Candidate Recommendation, expected to finish Q4 2026
    (https://www.w3.org/groups/wg/math/charters/active).
- **Known rendering gaps** (Temml's browser notes, https://temml.org/docs/en/administration):
  - Chromium: radical degree placed too far left, poor extensible arrows and flat accents, tall radicals not matching
    the vinculum. Combining accents are still being fixed (MathML Core issue 311).
  - WebKit: misaligns short `\left( \right)`, has no automatic line breaking, and draws poor extensible arrows.
  - Firefox renders best.
- **MathML Core restrictions that matter for converters** (https://w3c.github.io/mathml-core/):
  - `mathvariant` may only be `normal`, so bold and blackboard letters must be Unicode Math Alphanumerics.
  - `menclose` and `mfenced` are unknown elements.
  - `<mspace linebreak=…>` is not supported.
- **latex2mathml 3.81.1** (2026-09-07, Python ≥3.10, MIT; https://pypi.org/project/latex2mathml/), probed in a scratch
  venv:
  - Good: `\mathbf`, `\mathbb`, `\mathcal` and `\mathfrak` map to Unicode; `array`, `pmatrix`, `cases`, `\big`,
    `\operatorname`, `\binom`, `\sqrt[n]`, `\underbrace`, `\text`, `\color` and `\newcommand` all work.
  - Broken:
    - `aligned` emits a literal `&` as `<mi>&</mi>` plus `mspace linebreak`; use `array`.
    - `\\[4pt]` renders "[4pt]" as text.
    - `\arg`, `\eqref` and `\label` leak through as `<mi>\arg</mi>`.
    - **Unknown commands fail silently as `<mi>\foo</mi>`.** The build should fail on any `<mi>\` in the output.
    - `\cancel` and `\boxed` emit non-Core `menclose`.
    - `\boldsymbol` and `\bm` emit `mathvariant="bold-italic"`, which Chromium ignores.
    - `\tag{1}` becomes inline "(1)" text.
- **Alternatives**:
  - Temml 0.14.0 (npm, MIT, 2026-10-08) is the most MathML-Core-faithful converter. It runs server-side via
    `temml.mjs`/`temml.cjs` (mhchem and physics included), but needs Node.
  - KaTeX 0.19.0 can output MathML-only, also via Node.
  - ziamath 0.13 (PyPI, MIT) renders LaTeX to SVG in pure Python. Useful as a fallback for single hard equations, not
    for body text.
- **Fonts: yes, ship one.**
  - Many systems lack a math font with a MATH table: Windows has only Cambria Math, Android has none, and Linux depends
    on the distro (https://developer.mozilla.org/en-US/docs/Web/MathML/Guides/Fonts).
  - Google Fonts serves STIX Two Math (OFL) as one 285 KB woff2. **I checked that the MATH table is kept.** URL:
    `https://fonts.googleapis.com/css2?family=STIX+Two+Math&display=swap`.
  - Avoid Fontsource's copy: its `@font-face` declares a Latin-only `unicode-range`, so math symbols never use it.
  - Latin Modern Math (GUST licence) has no CDN copy. Self-host a woff2 if the Computer Modern look is wanted; Temml
    rates it best in Chromium.
  - CSS: `math { font-family: "STIX Two Math", "Latin Modern Math", "Cambria Math", math; }` plus about 10 lines of
    fixes: `math[display=block]{overflow-x:auto}` for mobile, and `mtable` padding.

## 6. CodeMirror 6 from a CDN without a bundler (verified in headless Chrome)

- **Duplicate-state problem**: plain per-package URLs load two copies of `@codemirror/state`, which throws
  "Unrecognized extension value … multiple instances of @codemirror/state"
  (https://discuss.codemirror.net/t/esm-compatible-codemirror-build-directly-importable-in-browser/5933/13).
- **Fix**: an import map using esm.sh's `*` prefix, which leaves all dependencies external and resolves them through
  the map (https://esm.sh/).
- **Versions** are the newest at least two weeks old. The tested map below rendered a Markdown editor with
  highlighting.
```html
<script type="importmap">{"imports":{
"codemirror":"https://esm.sh/*codemirror@6.0.2",
"@codemirror/state":"https://esm.sh/*@codemirror/state@6.7.6",
"@codemirror/view":"https://esm.sh/*@codemirror/view@6.43.13",
"@codemirror/commands":"https://esm.sh/*@codemirror/commands@6.11.1",
"@codemirror/language":"https://esm.sh/*@codemirror/language@6.12.4",
"@codemirror/autocomplete":"https://esm.sh/*@codemirror/autocomplete@6.20.3",
"@codemirror/search":"https://esm.sh/*@codemirror/search@6.7.2",
"@codemirror/lint":"https://esm.sh/*@codemirror/lint@6.9.7",
"@codemirror/lang-markdown":"https://esm.sh/*@codemirror/lang-markdown@6.5.2",
"@codemirror/lang-html":"https://esm.sh/*@codemirror/lang-html@6.4.12",
"@codemirror/lang-css":"https://esm.sh/*@codemirror/lang-css@6.3.1",
"@codemirror/lang-javascript":"https://esm.sh/*@codemirror/lang-javascript@6.2.5",
"@lezer/common":"https://esm.sh/*@lezer/common@1.5.3",
"@lezer/highlight":"https://esm.sh/*@lezer/highlight@1.2.5",
"@lezer/lr":"https://esm.sh/*@lezer/lr@1.4.10",
"@lezer/markdown":"https://esm.sh/*@lezer/markdown@1.7.2",
"@lezer/html":"https://esm.sh/*@lezer/html@1.3.13",
"@lezer/css":"https://esm.sh/*@lezer/css@1.3.8",
"@lezer/javascript":"https://esm.sh/*@lezer/javascript@1.5.6",
"style-mod":"https://esm.sh/style-mod@4.1.4",
"w3c-keyname":"https://esm.sh/w3c-keyname@2.2.8",
"crelt":"https://esm.sh/crelt@1.0.7",
"@marijn/find-cluster-break":"https://esm.sh/@marijn/find-cluster-break@1.0.4"}}</script>
<script type="module">
import {EditorView, basicSetup} from "codemirror";
import {markdown, markdownLanguage} from "@codemirror/lang-markdown";
new EditorView({doc: "# Hi", extensions: [basicSetup, markdown({base: markdownLanguage})], parent: el});
</script>
```
- **Caveats**:
  - `@codemirror/language` 6.13+ adds a dependency on `@codemirror/streamparser`. Add it to the map if you upgrade.
  - lang-markdown pulls in lang-html, lang-css and lang-javascript, which is why they are in the map.
  - The Editor is local-only, so an alternative is to vendor these files once into `studio/vendor/`, so it works
    offline and does not depend on esm.sh staying up.

## 7. Licensing

- What existing templates do:
  - al-folio: MIT (https://github.com/alshedivat/al-folio/blob/main/LICENSE).
  - AstroPaper: MIT (https://github.com/satnaing/astro-paper).
  - Distill template: Apache-2.0.
  - Hugo's theme site only requires "an Open Source license"; most themes there are MIT
    (https://github.com/gohugoio/hugoThemesSiteBuilder).
  - None of the ones I checked license the example content separately.
- MIT vs Apache-2.0 (https://choosealicense.com/licenses/): Apache adds an express patent grant and a
  "state changes" condition. That is more friction for people forking a template, and there is little patent risk in
  a static-site template.
- Creative Commons advises against CC for software (https://creativecommons.org/faq/), so CC BY 4.0 belongs on prose
  only.
- Fonts and vendored libraries keep their own licences: STIX Two Math is OFL, CodeMirror is MIT, Pyodide is MPL-2.0.
  List them in a `THIRD_PARTY.md`.

## Recommendations for our template

1. Copy Karpathy's layout literally:
   - `content/` is the wiki.
   - `sources/` (optional, git-ignored) holds raw material.
   - `AGENTS.md` is the schema.
   - `wiki/index.md` and `wiki/log.md` are generated, with log lines `## [YYYY-MM-DD] op | subject`.
2. Make ingest, lint and query CLI subcommands that write proposals only. Keep the human-approval step; it is what
   separates the template from "LLM rewrites your blog".
3. Lint deterministically first (orphans, dangling `[[id]]`, unknown tags, missing cross-links), then run an optional
   LLM pass for contradictions and stale claims.
4. Emit `/llms.txt` (spec order, with an `Optional` section for tags and series), `/llms-full.txt`, and a `.md` twin
   for every page, plus `<link rel="alternate" type="text/markdown">`.
5. The Ask widget uses BM25 over per-section passages in a static JSON file. The written answer goes through one
   OpenAI-compatible function using `base_url`, `model` and key from env. Answer only from retrieved passages, cite
   their ids, and apply per-IP and daily caps. Store no answers by default.
6. Pin Pyodide `v314.0.7` in one config value. Load it from `cdn.jsdelivr.net/pyodide/v314.0.7/full/pyodide.mjs` in a
   **module** worker.
7. Every figure ships its build-time SVG. The worker starts on first interaction or when the figure scrolls into view;
   expect about 1–1.5 s to first recompute.
8. The figure contract is `controls` plus a pure `compute(**values) -> spec`, using only numpy and the stdlib. Declare
   extra packages per figure; the worker calls `loadPackage` for those and nothing else.
9. Keep one tiny JS renderer for the declarative spec (SVG). This is what Quarto-live and marimo lack: authored
   figures, not notebook cells.
10. Use latex2mathml 3.81.x behind a pre- and post-processor:
    - Rewrite `aligned`/`align` to `array{rl}`.
    - Strip `\\[..]` spacing.
    - Map `\arg`, `\argmax` and `\argmin` to `\operatorname`.
    - Map `\boldsymbol` and `\bm` to Unicode bold-italic.
    - Implement `\tag`, `\label` and `\eqref` in Markdown, outside the maths.
11. Fail the build when the MathML output contains `<mi>\`, `menclose`, `mfenced`, or `linebreak=`, and print the
    offending source line. Silent failure is the biggest latex2mathml risk.
12. Offer Temml as an optional backend via `npx temml` for authors who need more coverage. Do not make Node a
    requirement.
13. Ship STIX Two Math from Google Fonts (`css2?family=STIX+Two+Math`), not Fontsource. Add a small `math.css` with a
    font stack, `overflow-x:auto` on display maths, and a scaled `math{font-size}`.
14. Editor: a stdlib `http.server` (or a minimal ASGI server) bound to `127.0.0.1` on a random free port. It opens the
    browser at `/?token=…` and exchanges the token for a `SameSite=Strict` cookie.
15. Editor checks on every request:
    - Host allowlist.
    - Origin or `Sec-Fetch-Site` check on writes.
    - No CORS headers.
    - JSON content-type only.
    - Path containment under `content/`.
    - Atomic writes.
    - git called with argument lists, never a shell.
16. Editor text area: CodeMirror 6 through the esm.sh import map in §6, vendored for offline use. Split view with a live
    preview that the real build pipeline renders for a single page (the same Markdown and maths code).
17. Editor UX borrowed from Ghost:
    - `/` menu: equation, figure from a starter, drawing, citation, callout, series link.
    - Cmd/Ctrl+P for preview.
    - Autosave to the file.
    - A "draft / published / scheduled" pill.
18. Status lives in front matter (`status: draft|published`). Drafts build only in the Editor preview, never in the
    public build or the sitemap. A future `date` means scheduled.
19. Publish is one button with a visible pipeline: checks, then the status flip, then build, then a diff preview, then
    commit, then deploy (`git push` or a configured CLI command). Stop on the first failure and show its output.
20. Citation lookup: arXiv API and Crossref (DOI) only, writing to `references.yml`. Show the fetched metadata for
    confirmation before saving.
21. Figure starters are a `figures/_starters/` folder of three or four tested examples (slider plot, 2-D geometry,
    matrix heatmap, 3-D scene), copied and renamed by the Editor. Every new figure also gets a generated test.
22. Licence: MIT for the code, with a `LICENSE`. Put CC BY 4.0 on the example posts in `content/LICENSE`, and say in
    the README that authors should replace the content licence with their own. List third-party items (fonts, CDN libs,
    Pyodide MPL-2.0) in `THIRD_PARTY.md`.
23. Pin every CDN dependency to an exact version at least two weeks old, kept in one `vendor.yml`. Add a test that
    fails on unpinned URLs.
24. Floor is Python ≥3.11: Markdown 3.11.2 requires it, and latex2mathml requires ≥3.10. Dependencies are Markdown,
    PyYAML 6.0.3, Jinja2 3.1.6 and latex2mathml 3.81.1, with nothing else required.
