# Tessera

**A template for technical blogs and personal sites where equations render properly, figures move, and the whole
site is a wiki you can ask questions.**

- **Write in Markdown.** Equations in LaTeX become real math (MathML) at build time. Mistakes are caught with the line
  number and a plain-English fix, instead of rendering wrong.
- **Interactive figures from one small Python file.** The same file draws the figure when the site is built (so it
  shows instantly and works without JavaScript) and again in the reader's browser when they move a slider (through
  [Pyodide](https://pyodide.org)).
- **Your site is an LLM wiki** (after [Karpathy's LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)).
  Every build writes the catalog (`wiki/index.md`) and log (`wiki/log.md`), a knowledge-graph **map** of how the
  posts connect, topic hubs, series pages, backlinks, [`llms.txt`](https://llmstxt.org) and a Markdown copy of every
  page.
- **Ask, on every page.** Readers ask a question and get an answer drawn from your own pages, computed in their browser.
  An optional "written answer" uses any OpenAI-compatible model and answers only from your pages, with sources.
- **The Studio: write and publish like Medium, from your own machine.** It has:
  - a live preview of the real page;
  - an equation helper;
  - a figure maker with starters;
  - citation lookup by arXiv id or DOI;
  - checks;
  - a **Publish** button that checks, builds, commits and pushes.

  It runs on `127.0.0.1` only; the published site cannot write anything.
- **Models propose, you publish.** With an LLM configured, Tessera suggests links, topics, summaries, descriptions,
  series highlights, equations from words and figure drafts. These are always proposals you accept or reject.

No Node, no bundler: Python 3.11+, with five small dependencies.

## Quick start

```bash
# 1. Get the template (GitHub: "Use this template"), then:
git clone https://github.com/<you>/<your-site>.git && cd <your-site>
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

# 2. See the example site, rebuilt live as you edit
.venv/bin/python -m tessera serve            # http://127.0.0.1:8000

# 3. Write
.venv/bin/python -m tessera studio           # opens the Studio in your browser
```

Then make it yours:
1. Edit `site.yml`: your name, origin, links, colours and fonts.
2. Replace the example posts in `content/posts/`.
3. Replace `content/LICENSE.md` with the licence you want for your writing.

## Writing a post

Use the Studio (`python -m tessera studio`), or any editor plus `python -m tessera serve`. A post is one file,
`content/posts/<slug>.md`:

```markdown
---
title: "Attention, Step by Step"
date: 2026-10-20
status: draft                 # draft | published; a future date schedules it
summary: "Two or three sentences for lists, the map and search."
topics: [attention, transformers]
series: {name: "Learning, Visually", part: 3}
builds_on: [post:softmax-and-temperature]
---

Attention turns similarities into weights with a softmax [@Vaswani17]:

$$
\operatorname{Attention}(Q, K, V) = \operatorname{softmax}\!\left(\frac{QK^\top}{\sqrt{d_k}}\right) V
$$ {#eq:attention}

::figure attention_weights | start: unscaled

> [!TIP]
> Equation [eq:attention] is the whole idea; the rest is bookkeeping. See [[post:gradient-descent]].
```

| You write | You get |
|---|---|
| `$x^2$`, `$$ … $$` | real math; `aligned`, `\tag`, `{#eq:name}` with `[eq:name]` references |
| `[[post:slug]]`, `[[post:slug\|text]]` | a link, plus an edge on the map |
| `[@Key]`, `[@Key, p. 4]` | a numbered citation and reference list (`python -m tessera cite 1706.03762` adds a paper) |
| `::figure name` | an interactive figure from `figures/name.py` |
| `::drawing module.fn \| caption` | a diagram from `drawings/module.py` |
| `> [!NOTE]` `> [!TIP]` `> [!WARNING]` `> [!KEY]` | callouts |
| footnotes, tables, fenced code, `==mark==`, images with captions | as you expect |

The example posts are the documentation:
- `content/posts/welcome.md` shows every feature next to its syntax.
- `content/posts/writing-math.md` is a guide to writing equations that render everywhere, and to the errors you might see.

`python -m tessera check` runs the same checks as the Studio. They cover:
- math that won't render;
- unknown links, citations and topics;
- images without alt text;
- missing summaries;
- descriptions that are too long;
- headings that skip a level.

## Interactive figures

A figure is a Python file in `figures/` with controls and a pure `compute()` that returns a small description of the
plot:

```python
TITLE = "Softmax temperature"
CAPTION = "Lower temperature sharpens the distribution; higher flattens it."
CONTROLS = [{"name": "t", "kind": "slider", "label": "temperature", "min": 0.1, "max": 5, "step": 0.1, "value": 1}]

def compute(t=1.0, _narrow=0):
    import math
    z = [3.0, 2.2, 1.6, 1.1, 0.4]
    e = [math.exp(v / t) for v in z]
    p = [v / sum(e) for v in e]
    return {"panels": [{"kind": "bars", "bars": [{"label": f"class {i+1}", "value": v} for i, v in enumerate(p)]}]}
```

To make one:
- **From a starter:** `python -m tessera figure new my_figure --from slider_plot`. The starters are `slider_plot`,
  `compare_bars`, `heatmap`, `geometry2d` and `animation`.
- **From the Studio's figure panel.**

`python -m tessera figure test` runs every figure at its defaults, presets and random states, and fails on errors,
NaN or anything slower than 30 ms. Panels can be line plots, bars, heatmaps or free 2-D shapes. Colours come from
the theme, so figures follow light and dark mode. A figure may use numpy (`REQUIRES = ["numpy"]`). Diagrams that don't
move go in `drawings/` (see `tessera/starters/drawings/`).

## The wiki, the map and Ask

Every build writes:
- `wiki/index.md`, the catalog of every page that an agent (or you) reads first;
- `wiki/log.md`, the append-only log of publishes, ingests and lints;
- `/llms.txt`, `/llms-full.txt` and a `.md` copy of each page;
- the map's graph and the passages Ask searches.

`AGENTS.md` explains the wiki to coding agents.

With an LLM configured (in `site.yml`, under `llm:`; the key goes in `.env.local`, never committed), these commands write proposals into `proposals/` for you to review:

```bash
python -m tessera wiki ingest content/posts/x.md   # topics, links to add, summary, description, questions
python -m tessera wiki lint                        # orphans, one-way links, thin topics (+ contradictions with --model)
python -m tessera wiki highlights "Series name"    # 3–4 highlights per part, numbers checked against the page
```

Any OpenAI-compatible endpoint works: OpenAI, OpenRouter, or a local model through Ollama
(`base_url: http://localhost:11434/v1`).

**Written answers on Ask** run as a serverless function (`api/ask.py`, on Vercel). Set the key's environment
variable (named by `llm.key_env`) in your Vercel project. Set `SITE_URL` too if the deployed address differs from
`site.origin`. Without a key, Ask still gives quick answers in the reader's browser.

## Publishing

In the Studio, **Publish** runs each step in a dialog with a live log:
1. Checks.
2. Sets the status and date.
3. Tests the post's figures.
4. Builds.
5. Updates the wiki files.
6. Optionally shows the model's suggested links and topics to accept or reject.
7. Commits only that post and its files.
8. Pushes, then runs your optional deploy command.

**Schedule** sets a future date; the post appears on the first build after that date. **Unpublish** turns it back
into a draft. From a terminal it's `python -m tessera publish -- content/posts/x.md [--dry-run]`.

The Studio is local by design:
- It listens on 127.0.0.1 only.
- It checks the Host and Origin of every request.
- It needs a fresh token each launch.
- It never sends CORS headers.
- It writes only inside your content folders.

None of its files are copied into the built site.

## Deploying

| Host | How | Ask's written answers |
|---|---|---|
| **Vercel** | Import the repo. `vercel.json` runs the tests and builds; `api/ask.py` is the function | yes (set the key) |
| **Netlify** | Import the repo. `netlify.toml` is included | quick answers only |
| **GitHub Pages** | Settings → Pages → Source: GitHub Actions. `.github/workflows/pages.yml` builds on push and daily (for scheduled posts) | quick answers only |
| **Anywhere** | `python -m tessera build` and upload `_site/` | quick answers only |

## Customising

- **`site.yml`:**
  - names, menu, content kinds, home page sections;
  - one accent colour (everything else is derived from it, in light and dark);
  - fonts from Google Fonts;
  - reading width;
  - features on and off.
- **Theme overrides:** put a file at the same path under `theme/` in your site to override the built-in one. For example, `theme/templates/page.html` or `theme/assets/css/site.css`.
- **New content kinds:** add one under `kinds:` and a folder `content/<kind>/`.

## Project layout

```
site.yml              configuration
content/              your pages (the wiki), topics.yml, references.yml
figures/  drawings/   interactive figures and diagrams
static/               images and files, copied as-is
wiki/                 generated catalog and log (committed)
tessera/              the engine; theme/ and studio/ inside it
api/ask.py            the written-answer function (Vercel)
tests/                run before every deploy
```

`docs/DESIGN.md` is the full design.

## Licence

- **Code:** [MIT](LICENSE).
- **Example content** in `content/`, `figures/` and `drawings/`: [CC BY 4.0](content/LICENSE.md). Replace it with your own.
- **Third-party components:** listed in [THIRD_PARTY.md](THIRD_PARTY.md).
