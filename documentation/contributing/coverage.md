# Coverage

This page checks that every part of Bazinga has a home in these docs. The list was made from the code, not from
memory: every command's `--help`, every key of `config.DEFAULTS` and the example `site.yml`, the header fields read
by `bazinga/content.py` and the templates, the Markdown handled by `bazinga/markdown.py`, the figure fields read by
`bazinga/plot.py` and `bazinga/figures.py`, the drawing kit (`bazinga/draw.py`), the 3-D kit (`bazinga/scene3d.py`),
the Editor (`bazinga/studio/`), Ask (`bazinga/ask_server.py`, `api/ask.py`), the wiki (`bazinga/llm.py`,
`bazinga/wiki.py`), the theme, the deploy files and the top-level files of the repository.

Each link was checked against the built docs: the page exists and the section is there. When you add a feature to
Bazinga, add a row here and a section where it belongs.

## Commands and options (from each `--help`)

| Item | Documented in |
|---|---|
| `python -m bazinga --root` | [reference/commands › the-whole-program](../reference/commands.md#the-whole-program) |
| `new` with `--kind`, `--slug` | [reference/commands › new](../reference/commands.md#new) |
| `build` with `--drafts`, `--quiet` | [reference/commands › build](../reference/commands.md#build) |
| `serve` with `--port`, `--open`, `--drafts`, `--no-editor` (`--no-studio`), `--editor-port` (`--studio-port`) | [reference/commands › serve](../reference/commands.md#serve) |
| `check` with files and `--errors-only` | [reference/commands › check](../reference/commands.md#check) |
| `cite` with `--key` | [reference/commands › cite](../reference/commands.md#cite) |
| `math` with `--display`, `--html`, and `-` for input | [reference/commands › math](../reference/commands.md#math) |
| `figure new --from` (starter, `builder`, `builder:<kind>`) | [reference/commands › figure](../reference/commands.md#figure) |
| `figure test`, `figure preview`, `figure list`, `figure starters` | [reference/commands › figure](../reference/commands.md#figure) |
| `editor` (and `studio`) with `--port`, `--no-browser`, `--root` | [reference/commands › editor](../reference/commands.md#editor) |
| `publish` with `--dry-run`, `--unpublish`, `--schedule`, `--yes` | [reference/commands › publish](../reference/commands.md#publish) |
| `wiki index`, `query`, `lint`, `log` (no model) | [ask-and-wiki › without-a-model](../ask-and-wiki.md#without-a-model) |
| `wiki ingest` | [ask-and-wiki › suggestions-for-one-page](../ask-and-wiki.md#suggestions-for-one-page) |
| `wiki describe` | [ask-and-wiki › a-description-for-search-engines](../ask-and-wiki.md#a-description-for-search-engines) |
| `wiki highlights` | [ask-and-wiki › highlights-for-a-series](../ask-and-wiki.md#highlights-for-a-series) |
| `wiki lint --model` | [ask-and-wiki › check-for-contradictions](../ask-and-wiki.md#check-for-contradictions) |
| `wiki equation`, `wiki figure` | [ask-and-wiki › an-equation-or-a-figure-from-words](../ask-and-wiki.md#an-equation-or-a-figure-from-words) |
| Options after `editor`, `publish`, `wiki`, and the `--` form | [reference/commands › passing-options-to-editor-publish-and-wiki](../reference/commands.md#passing-options-to-editor-publish-and-wiki) |

## `site.yml`

| Item | Documented in |
|---|---|
| `site.name`, `author`, `tagline`, `description`, `origin`, `language`, `avatar` | [reference/configuration › site](../reference/configuration.md#site) |
| `site.links` (github, linkedin, medium, scholar, x, email, and others) | [home-and-cv › your-name-and-links](../home-and-cv.md#your-name-and-links) |
| `nav` (adding pages to the menu) | [theme › the-menu](../theme.md#the-menu) |
| `kinds` with `label`, `singular`, `blurb`, `placeholder`, `word`, `external`, `role` | [theme › kinds-of-pages](../theme.md#kinds-of-pages) |
| `home.title`, `photo`, `role`, `employer`, `working_at`, `tagline`, `statement`, `lead`, `intro` | [home-and-cv › the-top](../home-and-cv.md#the-top) |
| `home.about`, `starters`, `starters_label` | [home-and-cv › about-and-the-pick-one-buttons](../home-and-cv.md#about-and-the-pick-one-buttons) |
| `home.map_text` | [home-and-cv › explore](../home-and-cv.md#explore) |
| `home.experience`, `education`, `courses` | [home-and-cv › experience-and-education](../home-and-cv.md#experience-and-education) |
| `home.contact` (`lead`, `areas`, `stack`, `close`, `email_button`, `links_text`, `elsewhere`) | [home-and-cv › contact](../home-and-cv.md#contact) |
| `home.ask_examples` | [reference/configuration › home](../reference/configuration.md#home) |
| `cv.pdf` | [home-and-cv › a-pdf-copy](../home-and-cv.md#a-pdf-copy) |
| `theme.accent` and the optional colours | [theme › colours](../theme.md#colours) |
| `theme.font_text`, `font_ui`, `font_code`, `font_math` | [theme › fonts](../theme.md#fonts) |
| `theme.width`; no dark mode | [theme › the-width-of-the-text](../theme.md#the-width-of-the-text), [theme › light-only](../theme.md#light-only) |
| `features.ask`, `explore`, `series`, `feed`, `llms_txt`, `credit` | [reference/configuration › features](../reference/configuration.md#features) |
| `llm.base_url`, `model` (with fallbacks), `key_env` | [reference/configuration › llm](../reference/configuration.md#llm) |
| `ask.written_answers`, `per_visitor`, `daily_cap` | [reference/configuration › ask](../reference/configuration.md#ask) |
| `publish.commit`, `push`, `command`, `author` | [reference/configuration › publish](../reference/configuration.md#publish) |
| Publish needs a git name and email (`publish.author` or `git config`), and pushes to the tracked branch | [writing/publishing › step-2-publish](../writing/publishing.md#step-2-publish) |
| Environment variables: `LLM_MODEL`, `LLM_BASE_URL`, `LLM_KEY_ENV`, `ASK_MODEL`, `ASK_WRITTEN`, `ASK_PER_VISITOR`, `ASK_DAILY_CAP`, `SITE_URL`, `BAZINGA_STUDIO_DEV`, and where each applies | [reference/configuration › environment-variables](../reference/configuration.md#environment-variables) |
| `.env.local`: who reads it, and which value wins | [reference/configuration › envlocal](../reference/configuration.md#envlocal) |
| Every page header field, in one table | [reference/configuration › page-header-fields](../reference/configuration.md#page-header-fields) |
| Figure control kinds and their fields, in one table | [reference/configuration › figure-controls](../reference/configuration.md#figure-controls) |
| Host files (`vercel.json`, `netlify.toml`, `pages.yml`) | [reference/configuration › host-files](../reference/configuration.md#host-files) |
| A minimal `site.yml` | [reference/configuration › a-minimal-siteyml](../reference/configuration.md#a-minimal-siteyml) |
| A portfolio without the blog (kinds, nav, features, removing links) | [home-and-cv › a-portfolio-without-the-blog](../home-and-cv.md#a-portfolio-without-the-blog) |
| Project pages for a portfolio | [home-and-cv › your-projects](../home-and-cv.md#your-projects) |
| Portfolio questions (photo, hide the blog, CV PDF, starters, credit) | [troubleshooting › your-portfolio](../troubleshooting.md#your-portfolio) |

## Content

| Item | Documented in |
|---|---|
| Kinds: reads, papers, projects | [writing/first-post › other-kinds-of-page](../writing/first-post.md#other-kinds-of-page) |
| External entries: `external`, `author`, `publication` | [writing/first-post › other-kinds-of-page](../writing/first-post.md#other-kinds-of-page) |
| Header: `title`, `date`, `status`, `summary`, `topics`, `description`, `builds_on`, `cites`, `series`, `updated`, `cover`, `seo_title` | [writing/first-post › the-header-fields](../writing/first-post.md#the-header-fields) |
| Header: `short`, `first_published` | [writing/first-post › the-header-fields](../writing/first-post.md#the-header-fields) |
| Header: `explains` (papers) | [writing/citations › step-3-cite-it-in-a-post](../writing/citations.md#step-3-cite-it-in-a-post) |
| Project fields: `type`, `stack`, `tagline`, `lead`, `from`, `github`, `usage`, `limitations`, `credit`, `order`, `launch` | [home-and-cv › project-pages](../home-and-cv.md#project-pages) |
| Drafts and scheduled pages | [writing/publishing › schedule-a-post-for-later](../writing/publishing.md#schedule-a-post-for-later) |
| `content/topics.yml` | [writing/links-and-topics › adding-a-topic](../writing/links-and-topics.md#adding-a-topic) |
| `content/references.yml` | [writing/citations › step-2-or-write-the-entry-by-hand](../writing/citations.md#step-2-or-write-the-entry-by-hand) |
| `content/cv.yml` | [home-and-cv › the-cv-page](../home-and-cv.md#the-cv-page) |
| `content/series/<slug>.yml` | [writing/series › step-3-write-your-own-highlights](../writing/series.md#step-3-write-your-own-highlights) |
| `content/LICENSE.md` | [whats-in-bazinga › licences](../whats-in-bazinga.md#licences) |
| Starter for new posts (`theme/starters/post.md`) | [theme › your-own-copy-of-a-theme-file](../theme.md#your-own-copy-of-a-theme-file) |

## Markdown

| Item | Documented in |
|---|---|
| `##` headings, numbering, table of contents | [writing/sections › step-1-write-your-sections-with](../writing/sections.md#step-1-write-your-sections-with) |
| `::pagebreak` | [writing/sections › step-2-split-a-long-post-with-pagebreak](../writing/sections.md#step-2-split-a-long-post-with-pagebreak) |
| Heading anchors and `{#id}` | [writing/sections › how-the-anchors-are-made](../writing/sections.md#how-the-anchors-are-made) |
| Inline and display maths | [writing/equations › step-2-an-equation-on-its-own-line](../writing/equations.md#step-2-an-equation-on-its-own-line) |
| `{#eq:name}`, `\tag`, `\label`, `[eq:name]` | [writing/equations › step-3-number-it-and-refer-to-it](../writing/equations.md#step-3-number-it-and-refer-to-it) |
| `aligned`, `align`, matrices, cases | [writing/equations › step-4-several-rows-lined-up](../writing/equations.md#step-4-several-rows-lined-up) |
| `[@Key]` and `[@Key, p. 4]` citations | [writing/citations › step-3-cite-it-in-a-post](../writing/citations.md#step-3-cite-it-in-a-post) |
| `[[id]]` and `[[id|text]]` links | [writing/links-and-topics › step-1-link-to-another-page-from-the-text](../writing/links-and-topics.md#step-1-link-to-another-page-from-the-text) |
| `::figure name` and `| start: preset` | [writing/figures-in-posts › step-2-open-it-at-a-preset](../writing/figures-in-posts.md#step-2-open-it-at-a-preset) |
| `::drawing module.fn | caption` | [writing/figures-in-posts › step-4-place-a-drawing-made-by-code](../writing/figures-in-posts.md#step-4-place-a-drawing-made-by-code) |
| ```` ```diagram ```` blocks | [writing/figures-in-posts › step-3-write-a-diagram-as-text](../writing/figures-in-posts.md#step-3-write-a-diagram-as-text) |
| Callouts: NOTE, TIP, WARNING, KEY, IMPORTANT, CAUTION, custom titles | [writing/first-post › markdown](../writing/first-post.md#markdown) |
| `==highlight==`, `~~strike~~`, footnotes, smart quotes | [writing/first-post › markdown](../writing/first-post.md#markdown) |
| Images with captions and alt text; tables; highlighted code | [writing/first-post › markdown](../writing/first-post.md#markdown) |

## Figures

| Item | Documented in |
|---|---|
| How a figure is drawn at build time and in the browser | [figures › how-a-figure-works](../figures.md#how-a-figure-works) |
| The form: function plot, shapes and curves, bars, heatmap, distribution, data table, 3-D scene | [figures › make-one-with-the-form-no-code](../figures.md#make-one-with-the-form-no-code) |
| The starters (17, from `figure starters`) | [figures › start-from-an-example](../figures.md#start-from-an-example) |
| `TITLE`, `CAPTION`, `REQUIRES`, `CONTROLS`, `PRESETS`, `compute()`, `_narrow` | [figures › write-one-by-hand](../figures.md#write-one-by-hand) |
| Controls: `slider` (with `play`), `toggle`, `steps`, `group` | [figures › write-one-by-hand](../figures.md#write-one-by-hand) |
| Panels: `xy`, `bars`, `heatmap`, `scene`, and styles | [figures › write-one-by-hand](../figures.md#write-one-by-hand) |
| `readouts`, `note`, `legend`, `height`, `widths`, ticks, `marks`, `annotations`, `shapes`, series options | [figures › spec-fields](../figures.md#spec-fields) |
| Presets and Reset | [writing/figures-in-posts › step-2-open-it-at-a-preset](../writing/figures-in-posts.md#step-2-open-it-at-a-preset) |
| The figure test (defaults, presets, random states, 30 ms) | [figures › test-it](../figures.md#test-it) |
| Speed | [figures › keep-it-fast](../figures.md#keep-it-fast) |
| Common mistakes | [figures › common-mistakes](../figures.md#common-mistakes) |

## Diagrams

| Item | Documented in |
|---|---|
| Text diagrams: arrows, shapes, styles, labels, groups, direction, timelines, trees | [diagrams › diagrams-written-as-text](../diagrams.md#diagrams-written-as-text) |
| `drawings/` starters: pipeline, blocks, architecture, flowchart, timeline, tree | [diagrams › start-from-a-starter](../diagrams.md#start-from-a-starter) |
| `draw.flow`, `draw.timeline`, `draw.tree` | [diagrams › lay-it-out-for-you-flow-timeline-tree](../diagrams.md#lay-it-out-for-you-flow-timeline-tree) |
| `Diagram` (`box`, `node`, `row`, `column`, `grid`, `arrow`, `chain`, `route`, `group`, `frame`, `label`, `note`, `anno`) | [diagrams › diagram-class](../diagrams.md#diagram-class) |

## 3-D figures

| Item | Documented in |
|---|---|
| The 3-D form | [figures-3d › make-one-with-the-form](../figures-3d.md#make-one-with-the-form) |
| Starters: scene_basic, surface_plot, vectors_planes, camera_rig | [figures-3d › start-from-an-example](../figures-3d.md#start-from-an-example) |
| `Scene(up=…)` and its items (points, lines, vectors, paths, polygons, boxes, planes, surfaces, curves, axes, grid, text, callout, dim, arc, camera, ray, image_view) | [figures-3d › what-a-scene-can-hold](../figures-3d.md#what-a-scene-can-hold) |
| Controls `orbit`, `pad`, `hidden`, and groups | [figures-3d › controls-for-a-scene](../figures-3d.md#controls-for-a-scene) |
| Dragging points: `_drag`, `apply_drag`, `layout`, handles, `state` | [figures-3d › points-the-reader-drags](../figures-3d.md#points-the-reader-drags) |
| `plot_inset`, `as_inset`, `panel`, `on_image`, `Flat`, `viewer`, `screen_of`, camera rig helpers, `declutter`, `label_report` | [figures-3d › more-of-the-kit](../figures-3d.md#more-of-the-kit) |
| Limits | [figures-3d › limits](../figures-3d.md#limits) |

## The Editor

| Item | Documented in |
|---|---|
| Opening it (Write button, `editor`) | [editor › open-it](../editor.md#open-it) |
| Library: tabs, kinds, search, New post | [editor › your-pages](../editor.md#your-pages) |
| Writing pane, live preview, wide and phone width, light and dark | [editor › the-writing-screen](../editor.md#the-writing-screen) |
| Toolbar and the "/" menu | [editor › the-toolbar-and-the-menu](../editor.md#the-toolbar-and-the-menu) |
| Keyboard shortcuts | [editor › keyboard-shortcuts](../editor.md#keyboard-shortcuts) |
| Equation helper | [editor › equation](../editor.md#equation) |
| Figure gallery and form | [editor › figure](../editor.md#figure) |
| Diagram and drawing panels | [editor › diagram](../editor.md#diagram) |
| Citation lookup | [editor › citation](../editor.md#citation) |
| Link picker | [editor › link-to-page](../editor.md#link-to-page) |
| Image upload | [editor › image-upload](../editor.md#image-upload) |
| Details drawer | [editor › details](../editor.md#details) |
| Checks drawer | [editor › checks](../editor.md#checks) |
| Versions (history) | [editor › versions](../editor.md#versions) |
| Publish, schedule, unpublish, dry run | [editor › publish](../editor.md#publish) |
| Security: 127.0.0.1, key, Host and Origin checks | [editor › why-it-is-safe](../editor.md#why-it-is-safe) |

## Ask and the wiki

| Item | Documented in |
|---|---|
| Ask in the browser (page and floating button) | [ask-and-wiki › what-ask-does-with-no-setup](../ask-and-wiki.md#what-ask-does-with-no-setup) |
| `wiki/index.md`, `wiki/log.md`, `passages.json`, `graph.json` | [ask-and-wiki › what-the-build-writes-for-the-wiki](../ask-and-wiki.md#what-the-build-writes-for-the-wiki) |
| Connecting a model: OpenRouter, OpenAI, Ollama, LM Studio | [ask-and-wiki › 1-name-the-service-and-the-model-in-siteyml](../ask-and-wiki.md#1-name-the-service-and-the-model-in-siteyml) |
| `.env.local` (never committed) | [ask-and-wiki › 2-put-the-key-in-envlocal](../ask-and-wiki.md#2-put-the-key-in-envlocal) |
| `proposals/`: review and accept | [ask-and-wiki › suggestions-the-model-proposes-you-decide](../ask-and-wiki.md#suggestions-the-model-proposes-you-decide) |
| Written answers (`api/ask.py`, the local `/api/ask/`) | [ask-and-wiki › written-answers-for-your-readers](../ask-and-wiki.md#written-answers-for-your-readers) |
| Limits per visitor and per day | [ask-and-wiki › limits](../ask-and-wiki.md#limits) |
| A laptop model cannot answer visitors of the deployed site | [ask-and-wiki › on-the-deployed-site](../ask-and-wiki.md#on-the-deployed-site) |
| `sources/` | [ask-and-wiki › working-with-ai-coding-agents](../ask-and-wiki.md#working-with-ai-coding-agents) |
| `AGENTS.md` | [ask-and-wiki › working-with-ai-coding-agents](../ask-and-wiki.md#working-with-ai-coding-agents) |

## Map, topics and series

| Item | Documented in |
|---|---|
| The map (`/explore/`): rings, reading order, filters, search | [map-and-topics › the-map-explore](../map-and-topics.md#the-map-explore) |
| Series found on the map (chain between, by tag) | [map-and-topics › series-found-on-the-map](../map-and-topics.md#series-found-on-the-map) |
| Connections on every post (Related, Go deeper, Go broader) | [map-and-topics › connections-on-every-post](../map-and-topics.md#connections-on-every-post) |
| Topic pages (`/topics/`) | [map-and-topics › the-topic-pages](../map-and-topics.md#the-topic-pages) |
| Series pages and highlights | [writing/series › step-2-see-the-highlights](../writing/series.md#step-2-see-the-highlights) |
| Turning series off | [writing/series › turning-series-off](../writing/series.md#turning-series-off) |

## Search engines and feeds

| Item | Documented in |
|---|---|
| Canonical link, Open Graph, JSON-LD, share image | [seo-and-feeds › what-each-page-carries](../seo-and-feeds.md#what-each-page-carries) |
| `description`, `seo_title`, `updated`, `cover` | [seo-and-feeds › header-fields-that-matter](../seo-and-feeds.md#header-fields-that-matter) |
| `sitemap.xml`, `robots.txt`, `404.html` | [seo-and-feeds › files-at-the-root-of-the-site](../seo-and-feeds.md#files-at-the-root-of-the-site) |
| `feed.xml` | [seo-and-feeds › the-feed](../seo-and-feeds.md#the-feed) |
| `llms.txt`, `llms-full.txt`, Markdown copies | [seo-and-feeds › llmstxt-and-the-markdown-copies](../seo-and-feeds.md#llmstxt-and-the-markdown-copies) |

## Theme

| Item | Documented in |
|---|---|
| Colours (tokens) and fonts | [theme › colours](../theme.md#colours) |
| The menu | [theme › the-menu](../theme.md#the-menu) |
| Turning parts on and off | [reference/configuration › features](../reference/configuration.md#features) |
| `theme/` overrides: templates, partials, CSS, scripts | [theme › your-own-copy-of-a-theme-file](../theme.md#your-own-copy-of-a-theme-file) |

## Deploying and keeping up to date

| Item | Documented in |
|---|---|
| Before you deploy (`site.origin`, tests) | [deploying › before-you-deploy](../deploying.md#before-you-deploy) |
| Vercel (`vercel.json`) and written answers there | [deploying › written-answers-on-vercel](../deploying.md#written-answers-on-vercel) |
| Netlify (`netlify.toml`) | [deploying › netlify](../deploying.md#netlify) |
| GitHub Pages (`pages.yml`; skipped in the Bazinga repository itself) | [deploying › github-pages](../deploying.md#github-pages) |
| Any static host (`_site/`) | [deploying › anywhere-else](../deploying.md#anywhere-else) |
| Scheduled posts and the daily build | [deploying › scheduled-posts](../deploying.md#scheduled-posts) |
| `publish.command` | [writing/publishing › choose-what-publish-does](../writing/publishing.md#choose-what-publish-does) |
| Pulling a newer Bazinga into your site | [updating › step-3-bring-the-update-in](../updating.md#step-3-bring-the-update-in) |
| A site under a path (`site.origin` with a folder, GitHub Pages project sites) | [reference/configuration › a-site-under-a-path](../reference/configuration.md#a-site-under-a-path) |
| `build --origin`, `BAZINGA_ORIGIN`, `SITE_URL` at build time | [reference/commands › build](../reference/commands.md#build) |
| Custom domains (Vercel, Netlify, GitHub Pages) | [deploying › netlify-domain](../deploying.md#netlify-domain), [vercel-domain](../deploying.md#vercel-domain), [github-pages-domain](../deploying.md#github-pages-domain) |
| Where Publish pushes, and push failures | [writing/publishing › when-the-push-fails](../writing/publishing.md#when-the-push-fails) |
| Reading the changelog before an update | [updating › step-1-read-what-changed](../updating.md#step-1-read-what-changed) |

## The project

| Item | Documented in |
|---|---|
| Install, build, serve | [getting-started › 2-install](../getting-started.md#2-install) |
| Folder structure | [getting-started › 5-a-tour-of-the-folders](../getting-started.md#5-a-tour-of-the-folders) |
| Tests | [getting-started › 6-run-the-tests-optional](../getting-started.md#6-run-the-tests-optional) |
| Licences (`LICENSE`, `content/LICENSE.md`) and `THIRD_PARTY.md` | [whats-in-bazinga › licences](../whats-in-bazinga.md#licences) |
| Everything in one place | [whats-in-bazinga › writing](../whats-in-bazinga.md#writing) |
| Troubleshooting and FAQ | [troubleshooting › installing](../troubleshooting.md#installing) |
| Contributing, the docs and their clips | [contributing/index › work-on-these-docs](../contributing/index.md#work-on-these-docs) |
| How the clips are recorded | [contributing/recording-clips](../contributing/recording-clips.md) |

## Contributing

| Item | Documented in |
|---|---|
| Sending a change: fork, branch, pull request, changelog line | [contributing › send-your-change](index.md#send-your-change) |
| Node.js for the clips and the script tests | [contributing › set-up](index.md#set-up), [recording-clips › what-you-need](recording-clips.md#what-you-need) |
| Where terminal clips run (`/tmp/bazinga-clips`) | [recording-clips › how-it-works](recording-clips.md#how-it-works) |
| Demo sites for a clip (`site:`, `REMOVE`) | [recording-clips › adding-a-browser-clip](recording-clips.md#adding-a-browser-clip) |
| A placeholder for unrecorded clips (`BAZINGA_DOCS_DRAFT`) | [recording-clips › how-a-clip-gets-into-a-page](recording-clips.md#how-a-clip-gets-into-a-page) |

**162 items, each with a home in these docs.**

## What's next

Back to [Contributing](index.md).
