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

| Item | Documented in | Status |
|---|---|---|
| `python -m bazinga --root` | [reference/commands › the-whole-program](../reference/commands.md#the-whole-program) | documented |
| `new` with `--kind`, `--slug` | [reference/commands › new](../reference/commands.md#new) | documented |
| `build` with `--drafts`, `--quiet` | [reference/commands › build](../reference/commands.md#build) | documented |
| `serve` with `--port`, `--open`, `--drafts`, `--no-editor` (`--no-studio`), `--studio-port` | [reference/commands › serve](../reference/commands.md#serve) | documented |
| `check` with files and `--errors-only` | [reference/commands › check](../reference/commands.md#check) | documented |
| `cite` with `--key` | [reference/commands › cite](../reference/commands.md#cite) | documented |
| `math` with `--display`, `--html`, and `-` for input | [reference/commands › math](../reference/commands.md#math) | documented |
| `figure new --from` (starter, `builder`, `builder:<kind>`) | [reference/commands › figure](../reference/commands.md#figure) | documented |
| `figure test`, `figure preview`, `figure list`, `figure starters` | [reference/commands › figure](../reference/commands.md#figure) | documented |
| `editor` (and `studio`) with `--port`, `--no-browser`, `--root` | [reference/commands › editor](../reference/commands.md#editor) | documented |
| `publish` with `--dry-run`, `--unpublish`, `--schedule`, `--yes` | [reference/commands › publish](../reference/commands.md#publish) | documented |
| `wiki index`, `query`, `lint`, `log` (no model) | [ask-and-wiki › without-a-model](../ask-and-wiki.md#without-a-model) | documented |
| `wiki ingest` | [ask-and-wiki › suggestions-for-one-page](../ask-and-wiki.md#suggestions-for-one-page) | documented |
| `wiki describe` | [ask-and-wiki › a-description-for-search-engines](../ask-and-wiki.md#a-description-for-search-engines) | documented |
| `wiki highlights` | [ask-and-wiki › highlights-for-a-series](../ask-and-wiki.md#highlights-for-a-series) | documented |
| `wiki lint --model` | [ask-and-wiki › check-for-contradictions](../ask-and-wiki.md#check-for-contradictions) | documented |
| `wiki equation`, `wiki figure` | [ask-and-wiki › an-equation-or-a-figure-from-words](../ask-and-wiki.md#an-equation-or-a-figure-from-words) | documented |
| Options after `editor`, `publish`, `wiki`, and the `--` form | [reference/commands › passing-options-to-editor-publish-and-wiki](../reference/commands.md#passing-options-to-editor-publish-and-wiki) | documented |

## `site.yml`

| Item | Documented in | Status |
|---|---|---|
| `site.name`, `author`, `tagline`, `description`, `origin`, `language`, `avatar` | [reference/configuration › site](../reference/configuration.md#site) | documented |
| `site.links` (github, linkedin, medium, scholar, x, email, and others) | [home-and-cv › your-name-and-links](../home-and-cv.md#your-name-and-links) | documented |
| `nav` (adding pages to the menu) | [theme › the-menu](../theme.md#the-menu) | documented |
| `kinds` with `label`, `singular`, `blurb`, `placeholder`, `word`, `external`, `role` | [theme › kinds-of-pages](../theme.md#kinds-of-pages) | documented |
| `home.title`, `photo`, `role`, `employer`, `working_at`, `tagline`, `statement`, `lead`, `intro` | [home-and-cv › the-top](../home-and-cv.md#the-top) | documented |
| `home.about`, `starters`, `starters_label` | [home-and-cv › about-and-the-pick-one-buttons](../home-and-cv.md#about-and-the-pick-one-buttons) | documented |
| `home.map_text` | [home-and-cv › explore](../home-and-cv.md#explore) | documented |
| `home.experience`, `education`, `courses` | [home-and-cv › experience-and-education](../home-and-cv.md#experience-and-education) | documented |
| `home.contact` (`lead`, `areas`, `stack`, `close`, `email_button`, `links_text`, `elsewhere`) | [home-and-cv › contact](../home-and-cv.md#contact) | documented |
| `home.ask_examples`, `home.show` | [reference/configuration › home](../reference/configuration.md#home) | documented |
| `cv.pdf` | [home-and-cv › a-pdf-copy](../home-and-cv.md#a-pdf-copy) | documented |
| `theme.accent` and the optional colours | [theme › colours](../theme.md#colours) | documented |
| `theme.font_text`, `font_ui`, `font_code`, `font_math` | [theme › fonts](../theme.md#fonts) | documented |
| `theme.width`, `theme.mode` (checked, not used by the default theme) | [reference/configuration › theme](../reference/configuration.md#theme) | documented |
| `features.ask`, `explore`, `series`, `feed`, `llms_txt`, `credit` | [reference/configuration › features](../reference/configuration.md#features) | documented |
| `llm.base_url`, `model` (with fallbacks), `key_env` | [reference/configuration › llm](../reference/configuration.md#llm) | documented |
| `ask.written_answers`, `per_visitor`, `daily_cap` | [reference/configuration › ask](../reference/configuration.md#ask) | documented |
| `publish.commit`, `push`, `command`, `author` | [reference/configuration › publish](../reference/configuration.md#publish) | documented |
| Publish needs a git name and email (`publish.author` or `git config`), and pushes to the tracked branch | [writing/publishing › step-2-publish](../writing/publishing.md#step-2-publish) | documented |
| Environment variables: `LLM_MODEL`, `LLM_BASE_URL`, `LLM_KEY_ENV`, `ASK_MODEL`, `ASK_WRITTEN`, `ASK_PER_VISITOR`, `ASK_DAILY_CAP`, `SITE_URL`, `BAZINGA_STUDIO_DEV`, and where each applies | [reference/configuration › environment-variables](../reference/configuration.md#environment-variables) | documented |
| `.env.local`: who reads it, and which value wins | [reference/configuration › envlocal](../reference/configuration.md#envlocal) | documented |
| Every page header field, in one table | [reference/configuration › page-header-fields](../reference/configuration.md#page-header-fields) | documented |
| Figure control kinds and their fields, in one table | [reference/configuration › figure-controls](../reference/configuration.md#figure-controls) | documented |
| Host files (`vercel.json`, `netlify.toml`, `pages.yml`) | [reference/configuration › host-files](../reference/configuration.md#host-files) | documented |
| A minimal `site.yml` | [reference/configuration › a-minimal-siteyml](../reference/configuration.md#a-minimal-siteyml) | documented |

## Content

| Item | Documented in | Status |
|---|---|---|
| Kinds: reads, papers, projects | [writing/first-post › other-kinds-of-page](../writing/first-post.md#other-kinds-of-page) | documented |
| External entries: `external`, `author`, `publication` | [writing/first-post › other-kinds-of-page](../writing/first-post.md#other-kinds-of-page) | documented |
| Header: `title`, `date`, `status`, `summary`, `topics`, `description`, `builds_on`, `cites`, `series`, `updated`, `cover`, `seo_title` | [writing/first-post › the-header-fields](../writing/first-post.md#the-header-fields) | documented |
| Header: `short`, `first_published` | [writing/first-post › the-header-fields](../writing/first-post.md#the-header-fields) | documented |
| Header: `explains` (papers) | [writing/citations › step-3-cite-it-in-a-post](../writing/citations.md#step-3-cite-it-in-a-post) | documented |
| Project fields: `type`, `stack`, `tagline`, `lead`, `from`, `github`, `usage`, `limitations`, `credit`, `order`, `launch` | [writing/first-post › project-pages](../writing/first-post.md#project-pages) | documented |
| Drafts and scheduled pages | [writing/publishing › schedule-a-post-for-later](../writing/publishing.md#schedule-a-post-for-later) | documented |
| `content/topics.yml` | [writing/links-and-topics › adding-a-topic](../writing/links-and-topics.md#adding-a-topic) | documented |
| `content/references.yml` | [writing/citations › step-2-or-write-the-entry-by-hand](../writing/citations.md#step-2-or-write-the-entry-by-hand) | documented |
| `content/cv.yml` | [home-and-cv › the-cv-page](../home-and-cv.md#the-cv-page) | documented |
| `content/series/<slug>.yml` | [writing/series › step-3-write-your-own-highlights](../writing/series.md#step-3-write-your-own-highlights) | documented |
| `content/LICENSE.md` | [whats-in-bazinga › licences](../whats-in-bazinga.md#licences) | documented |
| Starter for new posts (`theme/starters/post.md`) | [theme › your-own-copy-of-a-theme-file](../theme.md#your-own-copy-of-a-theme-file) | documented |

## Markdown

| Item | Documented in | Status |
|---|---|---|
| `##` headings, numbering, table of contents | [writing/sections › step-1-write-your-sections-with](../writing/sections.md#step-1-write-your-sections-with) | documented |
| `::pagebreak` | [writing/sections › step-2-split-a-long-post-with-pagebreak](../writing/sections.md#step-2-split-a-long-post-with-pagebreak) | documented |
| Heading anchors and `{#id}` | [writing/sections › how-the-anchors-are-made](../writing/sections.md#how-the-anchors-are-made) | documented |
| Inline and display maths | [writing/equations › step-2-an-equation-on-its-own-line](../writing/equations.md#step-2-an-equation-on-its-own-line) | documented |
| `{#eq:name}`, `\tag`, `\label`, `[eq:name]` | [writing/equations › step-3-number-it-and-refer-to-it](../writing/equations.md#step-3-number-it-and-refer-to-it) | documented |
| `aligned`, `align`, matrices, cases | [writing/equations › step-4-several-rows-lined-up](../writing/equations.md#step-4-several-rows-lined-up) | documented |
| `[@Key]` and `[@Key, p. 4]` citations | [writing/citations › step-3-cite-it-in-a-post](../writing/citations.md#step-3-cite-it-in-a-post) | documented |
| `[[id]]` and `[[id|text]]` links | [writing/links-and-topics › step-1-link-to-another-page-from-the-text](../writing/links-and-topics.md#step-1-link-to-another-page-from-the-text) | documented |
| `::figure name` and `| start: preset` | [writing/figures-in-posts › step-2-open-it-at-a-preset](../writing/figures-in-posts.md#step-2-open-it-at-a-preset) | documented |
| `::drawing module.fn | caption` | [writing/figures-in-posts › step-4-place-a-drawing-made-by-code](../writing/figures-in-posts.md#step-4-place-a-drawing-made-by-code) | documented |
| ```` ```diagram ```` blocks | [writing/figures-in-posts › step-3-write-a-diagram-as-text](../writing/figures-in-posts.md#step-3-write-a-diagram-as-text) | documented |
| Callouts: NOTE, TIP, WARNING, KEY, IMPORTANT, CAUTION, custom titles | [writing/first-post › markdown](../writing/first-post.md#markdown) | documented |
| `==highlight==`, `~~strike~~`, footnotes, smart quotes | [writing/first-post › markdown](../writing/first-post.md#markdown) | documented |
| Images with captions and alt text; tables; highlighted code | [writing/first-post › markdown](../writing/first-post.md#markdown) | documented |

## Figures

| Item | Documented in | Status |
|---|---|---|
| How a figure is drawn at build time and in the browser | [figures › how-a-figure-works](../figures.md#how-a-figure-works) | documented |
| The form: function plot, shapes and curves, bars, heatmap, distribution, data table, 3-D scene | [figures › make-one-with-the-form-no-code](../figures.md#make-one-with-the-form-no-code) | documented |
| The starters (17, from `figure starters`) | [figures › start-from-an-example](../figures.md#start-from-an-example) | documented |
| `TITLE`, `CAPTION`, `REQUIRES`, `CONTROLS`, `PRESETS`, `compute()`, `_narrow` | [figures › write-one-by-hand](../figures.md#write-one-by-hand) | documented |
| Controls: `slider` (with `play`), `toggle`, `steps`, `group` | [figures › write-one-by-hand](../figures.md#write-one-by-hand) | documented |
| Panels: `xy`, `bars`, `heatmap`, `scene`, and styles | [figures › write-one-by-hand](../figures.md#write-one-by-hand) | documented |
| `readouts`, `note`, `legend`, `height`, `widths`, ticks, `marks`, `annotations`, `shapes`, series options | [figures › spec-fields](../figures.md#spec-fields) | documented |
| Presets and Reset | [writing/figures-in-posts › step-2-open-it-at-a-preset](../writing/figures-in-posts.md#step-2-open-it-at-a-preset) | documented |
| The figure test (defaults, presets, random states, 30 ms) | [figures › test-it](../figures.md#test-it) | documented |
| Speed | [figures › keep-it-fast](../figures.md#keep-it-fast) | documented |
| Common mistakes | [figures › common-mistakes](../figures.md#common-mistakes) | documented |

## Diagrams

| Item | Documented in | Status |
|---|---|---|
| Text diagrams: arrows, shapes, styles, labels, groups, direction, timelines, trees | [diagrams › diagrams-written-as-text](../diagrams.md#diagrams-written-as-text) | documented |
| `drawings/` starters: pipeline, blocks, architecture, flowchart, timeline, tree | [diagrams › start-from-a-starter](../diagrams.md#start-from-a-starter) | documented |
| `draw.flow`, `draw.timeline`, `draw.tree` | [diagrams › lay-it-out-for-you-flow-timeline-tree](../diagrams.md#lay-it-out-for-you-flow-timeline-tree) | documented |
| `Diagram` (`box`, `node`, `row`, `column`, `grid`, `arrow`, `chain`, `route`, `group`, `frame`, `label`, `note`, `anno`) | [diagrams › diagram-class](../diagrams.md#diagram-class) | documented |

## 3-D figures

| Item | Documented in | Status |
|---|---|---|
| The 3-D form | [figures-3d › make-one-with-the-form](../figures-3d.md#make-one-with-the-form) | documented |
| Starters: scene_basic, surface_plot, vectors_planes, camera_rig | [figures-3d › start-from-an-example](../figures-3d.md#start-from-an-example) | documented |
| `Scene(up=…)` and its items (points, lines, vectors, paths, polygons, boxes, planes, surfaces, curves, axes, grid, text, callout, dim, arc, camera, ray, image_view) | [figures-3d › what-a-scene-can-hold](../figures-3d.md#what-a-scene-can-hold) | documented |
| Controls `orbit`, `pad`, `hidden`, and groups | [figures-3d › controls-for-a-scene](../figures-3d.md#controls-for-a-scene) | documented |
| Dragging points: `_drag`, `apply_drag`, `layout`, handles, `state` | [figures-3d › points-the-reader-drags](../figures-3d.md#points-the-reader-drags) | documented |
| `plot_inset`, `as_inset`, `panel`, `on_image`, `Flat`, `viewer`, `screen_of`, camera rig helpers, `declutter`, `label_report` | [figures-3d › more-of-the-kit](../figures-3d.md#more-of-the-kit) | documented |
| Limits | [figures-3d › limits](../figures-3d.md#limits) | documented |

## The Editor

| Item | Documented in | Status |
|---|---|---|
| Opening it (Write button, `editor`) | [editor › open-it](../editor.md#open-it) | documented |
| Library: tabs, kinds, search, New post | [editor › your-pages](../editor.md#your-pages) | documented |
| Writing pane, live preview, wide and phone width, light and dark | [editor › the-writing-screen](../editor.md#the-writing-screen) | documented |
| Toolbar and the "/" menu | [editor › the-toolbar-and-the-menu](../editor.md#the-toolbar-and-the-menu) | documented |
| Keyboard shortcuts | [editor › keyboard-shortcuts](../editor.md#keyboard-shortcuts) | documented |
| Equation helper | [editor › equation](../editor.md#equation) | documented |
| Figure gallery and form | [editor › figure](../editor.md#figure) | documented |
| Diagram and drawing panels | [editor › diagram](../editor.md#diagram) | documented |
| Citation lookup | [editor › citation](../editor.md#citation) | documented |
| Link picker | [editor › link-to-page](../editor.md#link-to-page) | documented |
| Image upload | [editor › image-upload](../editor.md#image-upload) | documented |
| Details drawer | [editor › details](../editor.md#details) | documented |
| Checks drawer | [editor › checks](../editor.md#checks) | documented |
| Versions (history) | [editor › versions](../editor.md#versions) | documented |
| Publish, schedule, unpublish, dry run | [editor › publish](../editor.md#publish) | documented |
| Security: 127.0.0.1, key, Host and Origin checks | [editor › why-it-is-safe](../editor.md#why-it-is-safe) | documented |

## Ask and the wiki

| Item | Documented in | Status |
|---|---|---|
| Ask in the browser (page and floating button) | [ask-and-wiki › what-ask-does-with-no-setup](../ask-and-wiki.md#what-ask-does-with-no-setup) | documented |
| `wiki/index.md`, `wiki/log.md`, `passages.json`, `graph.json` | [ask-and-wiki › what-the-build-writes-for-the-wiki](../ask-and-wiki.md#what-the-build-writes-for-the-wiki) | documented |
| Connecting a model: OpenRouter, OpenAI, Ollama, LM Studio | [ask-and-wiki › 1-name-the-service-and-the-model-in-siteyml](../ask-and-wiki.md#1-name-the-service-and-the-model-in-siteyml) | documented |
| `.env.local` (never committed) | [ask-and-wiki › 2-put-the-key-in-envlocal](../ask-and-wiki.md#2-put-the-key-in-envlocal) | documented |
| `proposals/`: review and accept | [ask-and-wiki › suggestions-the-model-proposes-you-decide](../ask-and-wiki.md#suggestions-the-model-proposes-you-decide) | documented |
| Written answers (`api/ask.py`, the local `/api/ask/`) | [ask-and-wiki › written-answers-for-your-readers](../ask-and-wiki.md#written-answers-for-your-readers) | documented |
| Limits per visitor and per day | [ask-and-wiki › limits](../ask-and-wiki.md#limits) | documented |
| A laptop model cannot answer visitors of the deployed site | [ask-and-wiki › on-the-deployed-site](../ask-and-wiki.md#on-the-deployed-site) | documented |
| `sources/` | [updating › working-with-ai-coding-agents](../updating.md#working-with-ai-coding-agents) | documented |
| `AGENTS.md` | [updating › working-with-ai-coding-agents](../updating.md#working-with-ai-coding-agents) | documented |

## Map, topics and series

| Item | Documented in | Status |
|---|---|---|
| The map (`/explore/`): rings, reading order, filters, search | [map-and-topics › the-map-explore](../map-and-topics.md#the-map-explore) | documented |
| Series found on the map (chain between, by tag) | [map-and-topics › series-found-on-the-map](../map-and-topics.md#series-found-on-the-map) | documented |
| Connections on every post (Related, Go deeper, Go broader) | [map-and-topics › connections-on-every-post](../map-and-topics.md#connections-on-every-post) | documented |
| Topic pages (`/topics/`) | [map-and-topics › the-topic-pages](../map-and-topics.md#the-topic-pages) | documented |
| Series pages and highlights | [writing/series › step-2-see-the-highlights](../writing/series.md#step-2-see-the-highlights) | documented |
| Turning series off | [writing/series › turning-series-off](../writing/series.md#turning-series-off) | documented |

## Search engines and feeds

| Item | Documented in | Status |
|---|---|---|
| Canonical link, Open Graph, JSON-LD, share image | [seo-and-feeds › what-each-page-carries](../seo-and-feeds.md#what-each-page-carries) | documented |
| `description`, `seo_title`, `updated`, `cover` | [seo-and-feeds › header-fields-that-matter](../seo-and-feeds.md#header-fields-that-matter) | documented |
| `sitemap.xml`, `robots.txt`, `404.html` | [seo-and-feeds › files-at-the-root-of-the-site](../seo-and-feeds.md#files-at-the-root-of-the-site) | documented |
| `feed.xml` | [seo-and-feeds › the-feed](../seo-and-feeds.md#the-feed) | documented |
| `llms.txt`, `llms-full.txt`, Markdown copies | [seo-and-feeds › llmstxt-and-the-markdown-copies](../seo-and-feeds.md#llmstxt-and-the-markdown-copies) | documented |

## Theme

| Item | Documented in | Status |
|---|---|---|
| Colours (tokens) and fonts | [theme › colours](../theme.md#colours) | documented |
| The menu | [theme › the-menu](../theme.md#the-menu) | documented |
| Turning parts on and off | [theme › turning-parts-on-and-off](../theme.md#turning-parts-on-and-off) | documented |
| `theme/` overrides: templates, partials, CSS, scripts | [theme › your-own-copy-of-a-theme-file](../theme.md#your-own-copy-of-a-theme-file) | documented |

## Deploying and keeping up to date

| Item | Documented in | Status |
|---|---|---|
| Before you deploy (`site.origin`, tests) | [deploying › before-you-deploy](../deploying.md#before-you-deploy) | documented |
| Vercel (`vercel.json`) and written answers there | [deploying › written-answers-on-vercel](../deploying.md#written-answers-on-vercel) | documented |
| Netlify (`netlify.toml`) | [deploying › netlify](../deploying.md#netlify) | documented |
| GitHub Pages (`pages.yml`; skipped in the Bazinga repository itself) | [deploying › github-pages](../deploying.md#github-pages) | documented |
| Any static host (`_site/`) | [deploying › anywhere-else](../deploying.md#anywhere-else) | documented |
| Scheduled posts and the daily build | [deploying › scheduled-posts](../deploying.md#scheduled-posts) | documented |
| `publish.command` | [deploying › publishing-from-the-editor](../deploying.md#publishing-from-the-editor) | documented |
| Pulling a newer Bazinga into your site | [updating › step-2-bring-the-update-in](../updating.md#step-2-bring-the-update-in) | documented |

## The project

| Item | Documented in | Status |
|---|---|---|
| Install, build, serve | [getting-started › 2-install](../getting-started.md#2-install) | documented |
| Folder structure | [getting-started › 5-a-tour-of-the-folders](../getting-started.md#5-a-tour-of-the-folders) | documented |
| Tests | [getting-started › 6-run-the-tests-optional](../getting-started.md#6-run-the-tests-optional) | documented |
| Licences (`LICENSE`, `content/LICENSE.md`) and `THIRD_PARTY.md` | [whats-in-bazinga › licences](../whats-in-bazinga.md#licences) | documented |
| Everything in one place | [whats-in-bazinga › writing](../whats-in-bazinga.md#writing) | documented |
| Troubleshooting and FAQ | [troubleshooting › installing](../troubleshooting.md#installing) | documented |
| Contributing, the docs and their clips | [contributing/index › work-on-these-docs](../contributing/index.md#work-on-these-docs) | documented |
| How the clips are recorded | [contributing/recording-clips](../contributing/recording-clips.md) | documented |

**149 items: 149 documented, 0 gaps.**

## What's next

Back to [Contributing](index.md).
