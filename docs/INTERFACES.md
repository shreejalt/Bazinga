# Interfaces between the builders (binding; change only by agreement through this file)

The root of the template is `/Users/shreejaltrivedi/Documents/Repos/shreejalt.github.io/.worktrees/template`.
- Python: `.venv/bin/python` in that folder (3.14, with Markdown, PyYAML, Jinja2, latex2mathml and Pygments).
- Run the engine as `.venv/bin/python -m bazinga …` with the template root as the working directory.

## bazinga/config.py (owner: core)
```python
ROOT: Path                      # Path.cwd() at import, overridable by bazinga.config.set_root(path) (tests use temp dirs)
def load(root=None) -> Config   # site.yml merged over DEFAULTS; raises ConfigError with a clear message
class Config(dict):             # attribute + key access: cfg.site.name, cfg["theme"]["accent"], cfg.kinds, cfg.llm …
    root: Path                  # site root; paths: cfg.content_dir, cfg.figures_dir, cfg.drawings_dir, cfg.static_dir, cfg.out_dir (_site)
```

## bazinga/content.py (owner: core)
```python
@dataclass
class Page:
    id: str            # "post:attention"
    kind: str          # "posts"
    slug: str
    path: Path         # content/posts/attention.md
    url: str           # "/posts/attention/"
    meta: dict         # front matter as written
    body: str          # Markdown after front matter
    body_line: int     # line number of the body's first line in the file (for error lines)
    title: str; date: date | None; updated: date | None; status: str  # "draft" | "published"
    summary: str; description: str; topics: list[str]; series: dict | None; builds_on: list[str]; cites: list[str]
    @property public -> bool     # published and date <= today
    @property scheduled -> bool  # published and date > today
def parse(text: str, path: Path, cfg) -> Page              # never touches other files
def load_pages(cfg, drafts=False) -> list[Page]            # public only unless drafts=True; sorted newest first
def load_topics(cfg) -> dict[str, dict]                    # slug -> {slug,label,blurb,group}
def load_references(cfg) -> dict[str, dict]
```

## bazinga/markdown.py (owner: core)
```python
@dataclass
class Rendered:
    html: str
    toc: list[dict]            # {"level": 2|3, "id": str, "text": str}
    mentions: list[str]        # page ids linked with [[...]] in order of first use
    cites: list[str]           # reference keys in order of first use (body [@KEY] then front-matter cites)
    figures: list[str]         # figure names used
    drawings: list[str]        # "module.fn"
    issues: list               # checks.Issue found while rendering (math errors, unknown ids/keys …)
    sections: list[dict]       # {"id","title","text"} plain text per h2/h3 section (for passages); first section "" = intro
def render(page: Page, site: "SiteIndex") -> Rendered
class SiteIndex:               # what rendering needs to know about the rest of the site
    pages: dict[str, Page]     # by id (includes drafts when previewing)
    references: dict[str, dict]
    topics: dict[str, dict]
```
`::figure name | start: Label` calls `bazinga.figures.figure_html(name, start=label)`.
`::drawing module.fn | caption` calls `bazinga.drawings.drawing_html("module.fn", caption)`.
Both raise `bazinga.figures.FigureError` / `bazinga.drawings.DrawingError`. markdown.py catches these and turns them into an issue plus a visible error box in preview builds; a production build fails on them.

## bazinga/mathml.py (owner: core)
```python
class MathError(Exception): message, hint, offset
def to_mathml(tex: str, display: bool) -> str   # raises MathError
```

## bazinga/checks.py (owner: core)
```python
@dataclass
class Issue: level: str ("error"|"warning"); line: int | None; message: str; hint: str = ""; code: str = ""
def check_page(page: Page, site: SiteIndex) -> list[Issue]   # front matter + render issues + style rules
```

## bazinga/figures.py, plot.py, draw.py, drawings.py (owner: figures)
```python
class FigureError(Exception)
def discover(cfg) -> dict[str, Path]                      # figures/*.py not starting with "_"
def load(name, cfg=None) -> module                        # validates the contract; FigureError explains what is wrong
def run(name, values=None, narrow=0) -> dict              # {"svg": str, "readouts_html": str, "ms": float}
def figure_html(name, start=None) -> str                  # the full <figure class="fig" …> block (static SVG, controls, caption)
def write_assets(cfg, used: set[str], out: Path)          # copies used figure modules + _plot.py into out/figures/
def test_figure(name) -> list[str]                        # problems found (empty = ok): defaults, presets, 20 random states, timing, NaN
# plot.py
def render(spec: dict, narrow=0) -> tuple[str, str]       # (svg, readouts_html); stdlib only; also runs in the browser
# drawings.py
class DrawingError(Exception)
def drawing_html(ref: str, caption: str = "") -> str
```
Browser side (owner: figures): `bazinga/theme/assets/js/figure.js`, `bazinga/theme/assets/js/pyworker.js`, `bazinga/theme/assets/css/figure.css`.
- `figure.js` exposes `window.Bazinga.py` for others (Ask uses it): `await Bazinga.py.call(moduleUrl, fnName, argsObject)` runs a function from a module URL in the same worker and returns JSON.
- The base template includes `figure.js` on every page (it is tiny and boots nothing until needed).

## bazinga/graph.py, wiki.py, retrieve.py, llm.py, ask_server.py, api/ask.py (owner: wiki)
```python
# graph.py
class Graph:
    nodes: dict[str, dict]            # id -> {id,title,url,kind,summary,topics,date,series}
    edges: list[dict]                 # {"source","target","type": builds_on|mentions|cites|topic|series, "weight"}
    def backlinks(self, id) -> list[str]
    def builds_on(self, id) -> list[str]; def read_next(self, id) -> list[str]   # pages that build on id
    def related(self, id, k=5) -> list[str]
    def series(self) -> dict[str, list[str]]          # name -> ids in part order
    def topic_pages(self, slug) -> list[str]
    def layout(self) -> dict[str, tuple[float, float]] # deterministic, unit square
    def rings(self, id) -> dict[str, int]             # BFS distance
    def to_json(self) -> dict
def build_graph(pages: list[Page], rendered: dict[str, Rendered], site: SiteIndex) -> Graph
# wiki.py
def passages(pages, rendered) -> list[dict]           # {id,title,url,section,anchor,text}
def write_site_files(cfg, pages, rendered, graph, out: Path)   # llms.txt, llms-full.txt, <url>/index.md, data/passages.json, data/graph.json
def write_repo_wiki(cfg, pages, graph)                # wiki/index.md (deterministic; only rewritten when content changes)
def append_log(cfg, op: str, subject: str)            # wiki/log.md "## [YYYY-MM-DD] op | subject"
# retrieve.py  (stdlib only; shipped to _site/figures/_retrieve.py and run in the browser via Bazinga.py.call)
def answer(question: str, passages: list, graph: dict | None = None, page: str | None = None, k: int = 6) -> dict
#   -> {"answer": str (extractive, plain), "passages": [...top k with "score"], "pages": [{id,title,url}], "count": n}
# llm.py
def configured(cfg) -> bool
def chat(cfg, system, user, json_mode=False, max_tokens=1200) -> str     # OpenAI-compatible; fallbacks over comma-separated models
def ingest(cfg, page) -> dict; def lint(cfg, use_model=False) -> dict; def highlights(cfg, series) -> dict
def describe(cfg, page) -> str; def equation(cfg, words) -> str; def figure_draft(cfg, description) -> str (module source)
# ask_server.py
def handle(method: str, body: bytes, ip: str, env: dict, passages_loader) -> tuple[int, dict]
```
Browser side (owner: wiki): `bazinga/theme/assets/js/explore.js`, `bazinga/theme/assets/js/ask.js`, `bazinga/theme/assets/css/` additions in `wiki.css`.

## build.py (owner: core). The order of a build:
1. Config.
2. Pages: public, or all with drafts.
3. SiteIndex.
4. Render every page.
5. `graph.build_graph`.
6. Templates for every page (context below).
7. Lists, home, topics, series, explore, ask, 404.
8. `figures.write_assets`.
9. `wiki.write_site_files` + `wiki.write_repo_wiki` (production only).
10. seo (sitemap, robots, feed).
11. Static copy: `bazinga/theme/assets/` → `_site/assets/`, overridden by `<root>/theme/assets/`; `<root>/static/` → `_site/static/`.

The core may import graph/wiki lazily and skip them with a printed note if they don't exist yet, so builders can work in parallel.

Also `def preview_html(page: Page, cfg) -> str` gives a full HTML page for the Editor preview, with drafts visible.

**Template context:**
- Every template gets:
  - `site` (cfg.site), `cfg`, `nav`;
  - `asset(path)` → `/assets/<path>?v=<hash>`;
  - `vendor` (bazinga.vendor URLs);
  - `page_title`, `canonical`, `og` (dict), `jsonld` (str);
  - `body_page_id` (or "") and `features`.
- `page.html` also gets:
  - `page` (Page), `html`, `toc`;
  - `connections` = `{builds_on: [node], read_next: [node], backlinks: [node], related: [node]}`;
  - `references` = `[{key, n, text, url}]`;
  - `series_nav` = `{name, url, parts: [node], index}` or None;
  - `reading_minutes`.

## Ownership (do not edit files you do not own; leave a note in docs/NOTES-<you>.md for the owner instead)
- **core:**
  - bazinga/{__init__,__main__,cli,config,content,markdown,mathml,checks,build,serve,seo,vendor}.py;
  - bazinga/theme/templates/**;
  - bazinga/theme/assets/css/{tokens,site,math}.css;
  - bazinga/theme/assets/js/site.js;
  - bazinga/starters/post.md;
  - site.yml, requirements.txt;
  - content/topics.yml, content/references.yml, content/posts/*;
  - tests/test_core_*.py.
- **figures:**
  - bazinga/{figures,plot,draw,drawings}.py;
  - bazinga/theme/assets/js/{figure,pyworker}.js;
  - bazinga/theme/assets/css/figure.css;
  - bazinga/starters/{figures,drawings}/**;
  - figures/**, drawings/**;
  - tests/test_fig_*.py.
- **wiki:**
  - bazinga/{graph,wiki,retrieve,llm,ask_server}.py, api/ask.py;
  - bazinga/theme/assets/js/{explore,ask}.js;
  - bazinga/theme/assets/css/wiki.css;
  - tests/test_wiki_*.py.
- **studio** (later): bazinga/studio/**, tests/test_studio_*.py.
