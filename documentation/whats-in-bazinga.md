# What's in Bazinga

This page lists every part of Bazinga in one place, with a link to the page that explains it. Read it once to see
what you have, then come back when you wonder whether Bazinga can do something.

Bazinga is a Python template for a personal site and technical blog. You write Markdown files; one command turns
them into a plain static site that any host can serve. There is no Node and no bundler, and the built pages work
without JavaScript: scripts only add the moving parts.

::clip site-tour | The example site: the home page, a list of posts, and a post with its contents.

## Writing

| Part | What it gives you | Where it is explained |
|---|---|---|
| Pages | one Markdown file per page, in `content/reads/`, `papers/`, `projects/` and `elsewhere/` | [Your first post](writing/first-post.md) |
| Header fields | title, date, status, summary, topics, series, builds-on, citations, description and more | [Your first post](writing/first-post.md#the-header-fields) |
| Project pages | tagline, usage, limitations, a GitHub link and other project fields | [Your first post](writing/first-post.md#project-pages) |
| Articles elsewhere | entries that open where they were published, with author and publication | [Your first post](writing/first-post.md#other-kinds-of-page) |
| Sections and contents | numbered headings, a table of contents with page numbers, `::pagebreak` | [Sections and contents](writing/sections.md) |
| Equations | LaTeX turned into MathML when the site is built; numbering and `[eq:name]` references | [Equations](writing/equations.md) |
| Citations | `[@Key]`, a numbered reference list, and `python -m bazinga cite` | [Citations](writing/citations.md) |
| Boxes and the rest | callouts, footnotes, highlights, images with captions, tables, code | [Your first post](writing/first-post.md#markdown) |
| Links and topics | `[[read:slug]]` links, `builds_on`, and the topics in `content/topics.yml` | [Links and topics](writing/links-and-topics.md) |
| Series | parts in order, series pages, highlights per part | [Series](writing/series.md) |
| Checks | every page checked, with the line and the fix | [Checking](writing/checking.md) |
| Publishing | check, build, commit and push in one step, or schedule a post | [Publishing](writing/publishing.md) |

## Figures and diagrams

| Part | What it gives you | Where it is explained |
|---|---|---|
| Interactive figures | a picture with sliders, toggles and presets, redrawn in the reader's browser | [Interactive figures](figures.md) |
| The figure form | seven kinds of figure made without code | [Interactive figures](figures.md#make-one-with-the-form-no-code) |
| Starters | seventeen working figures to copy and change | [Interactive figures](figures.md#start-from-an-example) |
| Every figure field | panels, series, shapes, marks, readouts and more | [Interactive figures](figures.md#spec-fields) |
| 3-D figures | scenes the reader turns, points they drag, cameras | [3-D figures](figures-3d.md) |
| Diagrams as text | boxes and arrows, flowcharts, timelines and trees written in the post | [Diagrams](diagrams.md#diagrams-written-as-text) |
| Diagrams from code | `drawings/` with `draw.flow`, `draw.timeline`, `draw.tree` and `Diagram` | [Diagrams](diagrams.md#diagrams-from-code) |

## The Editor

| Part | What it gives you | Where it is explained |
|---|---|---|
| The writing window | a library of your pages, a writing pane, and a live preview of the real page | [The Editor](editor.md) |
| Helpers | equation, figure, diagram, drawing, citation, link and image helpers | [The Editor](editor.md#the-helpers) |
| Details, checks, versions | the header as a form, live checks, earlier versions to restore | [The Editor](editor.md#details) |
| Publish | publish, schedule, unpublish, and a dry run | [The Editor](editor.md#publish) |
| Safety | it runs on your computer only, behind a key made each time it starts | [The Editor](editor.md#why-it-is-safe) |

## The site your readers see

| Part | What it gives you | Where it is explained |
|---|---|---|
| Home page and CV | about, experience, education, contact, and a full CV page | [Your home page and CV](home-and-cv.md) |
| The map | every page on one map; a hover lights what is nearest and the reading order | [The map and topics](map-and-topics.md) |
| Topic pages | one page per topic, with its pages and their live figures | [The map and topics](map-and-topics.md#topics) |
| Ask | readers ask a question and get an answer from your own pages | [Ask and the wiki](ask-and-wiki.md#what-ask-does-with-no-setup) |
| Written answers | optional answers written by a language model from your pages only | [Ask and the wiki](ask-and-wiki.md#written-answers-for-your-readers) |
| Search engines and feeds | sitemap, robots, canonical links, previews, structured data, an Atom feed | [SEO and feeds](seo-and-feeds.md) |
| `llms.txt` | your site laid out for language models, plus a Markdown copy of every page | [SEO and feeds](seo-and-feeds.md#llmstxt-and-the-markdown-copies) |
| The look | colours, fonts, the menu, kinds of pages, your own theme files | [Theme and customising](theme.md) |

## The wiki and models

| Part | What it gives you | Where it is explained |
|---|---|---|
| Wiki files | `wiki/index.md` (the catalog) and `wiki/log.md` (the log), written for you | [Ask and the wiki](ask-and-wiki.md#what-the-build-writes-for-the-wiki) |
| Wiki commands | `index`, `query`, `lint` and `log` without a model; `ingest`, `highlights`, `describe`, `equation`, `figure` with one | [Ask and the wiki](ask-and-wiki.md#the-wiki-commands) |
| Any model | OpenRouter, OpenAI, or a model on your own computer | [Ask and the wiki](ask-and-wiki.md#connect-a-model) |
| Proposals | a model only suggests; you accept or reject in `proposals/` | [Ask and the wiki](ask-and-wiki.md#suggestions-the-model-proposes-you-decide) |
| AI coding agents | `AGENTS.md` tells an agent how the site works | [Updating Bazinga](updating.md#working-with-ai-coding-agents) |

## Running it

| Part | What it gives you | Where it is explained |
|---|---|---|
| Install and serve | a preview that rebuilds when you save | [Getting started](getting-started.md) |
| Commands | every `python -m bazinga` command and option | [Commands](reference/commands.md) |
| Settings | every key of `site.yml`, and the environment variables | [Configuration](reference/configuration.md) |
| Deploying | Vercel, Netlify, GitHub Pages, or any static host | [Deploying](deploying.md) |
| Updating | bringing a newer Bazinga into your site | [Updating Bazinga](updating.md) |
| Problems | the messages you may see and what to do | [Troubleshooting and FAQ](troubleshooting.md) |

## The folders

```text
site.yml      settings and home page        content/   your posts, cv.yml, topics.yml, references.yml
figures/      interactive figures           drawings/  diagrams made with code (optional)
static/       images and files              wiki/      generated wiki files
bazinga/      the engine, theme and Editor  tests/     run before every deploy
api/          written answers on Vercel     docs/      notes on Bazinga's design
```

Every folder and file, and whether you edit it, is in the table in
[Getting started](getting-started.md#5-a-tour-of-the-folders).

## Licences {#licences}

- **The code** (`bazinga/`, `api/`, `tests/`) is under the MIT licence, in the file `LICENSE`.
- **The example content** (`content/`, `figures/`, `drawings/`) is under CC BY 4.0, in `content/LICENSE.md`. When
  you make the site yours, replace `content/LICENSE.md` with the licence you want for your own writing.
- **What Bazinga uses** is listed in `THIRD_PARTY.md`, each part under its own licence: Python-Markdown, PyYAML,
  Jinja2, latex2mathml and Pygments when the site is built; NumPy for figures that ask for it; Pyodide in the
  reader's browser (to redraw figures and answer Ask); CodeMirror in the Editor; and fonts from Google Fonts. None of
  them is copied into the repository: their versions are pinned in `requirements.txt` and `bazinga/vendor.py`.

## What's next

Start at [Getting started](getting-started.md) if you have not installed it yet, or go straight to
[Writing](writing/index.md).
