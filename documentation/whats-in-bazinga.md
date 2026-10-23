# What's in Bazinga

This page lists every part of Bazinga in one place, with a link to the page that explains it. Read it once to see
what you have, then come back when you wonder whether Bazinga can do something.

Bazinga is a Python template for a personal website: a portfolio with your CV and projects, and a technical blog
if you want one. You write YAML and Markdown files; one command turns them into a plain static site that any host
can serve. There is no Node and no bundler, and the built pages work
without JavaScript: scripts only add the moving parts.

## Your portfolio

All explained in [Your portfolio: home page, CV and projects](home-and-cv.md), except your own address.

| Part | What it gives you |
|---|---|
| [Name, links and email](home-and-cv.md#your-name-and-links) | the name on every page, your profile links and the Contact buttons |
| [Photo and tab icon](home-and-cv.md#the-top) | a round photo on the home page; `avatar` for the browser tab and share picture |
| [Home page sections](home-and-cv.md#the-home-page-section-by-section) | headline, About, Experience (each role opens), Education, Contact |
| [Contact](home-and-cv.md#contact) | what you work on, your tools, an email button and where else to find you |
| [CV page](home-and-cv.md#the-cv-page) | your full record at `/cv/`, from `content/cv.yml`, checked when the site is built |
| [CV as a PDF](home-and-cv.md#a-pdf-copy) | a **Download CV** button that opens your PDF |
| [Projects](home-and-cv.md#your-projects) | one page per project, with its stack, a GitHub link and usage |
| [A portfolio without the blog](home-and-cv.md#a-portfolio-without-the-blog) | only Home, Projects and CV |
| [Your own address](deploying.md) | a custom domain on Vercel, Netlify or GitHub Pages |

## Writing

| Part | What it gives you | Where it is explained |
|---|---|---|
| Pages | one Markdown file per page, in `content/reads/`, `papers/`, `projects/` and `elsewhere/` | [Your first post](writing/first-post.md) |
| Header fields | title, date, status, summary, topics, series, builds-on, citations, description and more | [Your first post](writing/first-post.md#the-header-fields) |
| Project pages | tagline, usage, limitations, a GitHub link and other project fields | [Your portfolio](home-and-cv.md#project-pages) |
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

All explained in [The Editor](editor.md).

| Part | What it gives you |
|---|---|
| [The writing window](editor.md) | a library of your pages, a writing pane, and a live preview of the real page |
| [Helpers](editor.md#the-helpers) | equation, figure, diagram, drawing, citation, link and image helpers |
| [Details, checks, versions](editor.md#details) | the header as a form, live checks, earlier versions to restore |
| [Publish](editor.md#publish) | publish, schedule, unpublish, and a dry run |
| [Safety](editor.md#why-it-is-safe) | it runs on your computer only, behind a key made each time it starts |

## The site your readers see

| Part | What it gives you | Where it is explained |
|---|---|---|
| The map | every page on one map; a hover lights what is nearest and the reading order | [The map and topics](map-and-topics.md) |
| Topic pages | one page per topic, with its pages and their live figures | [The map and topics](map-and-topics.md#topics) |
| Ask | readers ask a question and get an answer from your own pages | [Ask and the wiki](ask-and-wiki.md#what-ask-does-with-no-setup) |
| Written answers | optional answers written by a language model from your pages only | [Ask and the wiki](ask-and-wiki.md#written-answers-for-your-readers) |
| Search engines and feeds | sitemap, robots, canonical links, previews, structured data, an Atom feed | [SEO and feeds](seo-and-feeds.md) |
| `llms.txt` | your site laid out for language models, plus a Markdown copy of every page | [SEO and feeds](seo-and-feeds.md#llmstxt-and-the-markdown-copies) |
| The look | colours, fonts, the menu, kinds of pages, your own theme files | [Theme and customising](theme.md) |

## The wiki and models

All explained in [Ask and the wiki](ask-and-wiki.md).

| Part | What it gives you |
|---|---|
| [Wiki files](ask-and-wiki.md#what-the-build-writes-for-the-wiki) | `wiki/index.md` (the catalog) and `wiki/log.md` (the log), written for you |
| [Wiki commands](ask-and-wiki.md#the-wiki-commands) | `index`, `query`, `lint` and `log` without a model; `ingest`, `highlights`, `describe`, `equation`, `figure` with one |
| [Any model](ask-and-wiki.md#connect-a-model) | OpenRouter, OpenAI, or a model on your own computer |
| [Proposals](ask-and-wiki.md#suggestions-the-model-proposes-you-decide) | a model only suggests; you accept or reject in `proposals/` |
| [AI coding agents](ask-and-wiki.md#working-with-ai-coding-agents) | `AGENTS.md` tells an agent how the site works |

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

Every folder and file, and whether you edit it, is in [Getting started: a tour of the folders](getting-started.md#5-a-tour-of-the-folders).

## Licences {#licences}

- **The code** (`bazinga/`, `api/`, `tests/`) is under the MIT licence, in the file `LICENSE`.
- **The example content** (`content/`, `figures/`, `drawings/`) is under CC BY 4.0, in `content/LICENSE.md`. When
  you make the site yours, replace `content/LICENSE.md` with the licence you want for your own writing.
- **What Bazinga uses** is listed in `THIRD_PARTY.md`, each part under its own licence: Python-Markdown, PyYAML,
  Jinja2, latex2mathml and Pygments when the site is built; NumPy for figures that ask for it; Pyodide in the
  reader's browser (to redraw figures and answer Ask); CodeMirror in the Editor; and fonts from Google Fonts. None of
  them is copied into the repository: their versions are pinned in `requirements.txt` and `bazinga/vendor.py`.

## What's next

Next, make it yours: [Your portfolio: home page, CV and projects](home-and-cv.md). Ready to write instead? Go to
[Writing](writing/index.md). Later, [Updating Bazinga](updating.md) shows how to bring a newer Bazinga into your site.
