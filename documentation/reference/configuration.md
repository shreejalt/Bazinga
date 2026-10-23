# Configuration

This page lists everything you can set in Bazinga, in one place: every key of `site.yml`, the environment
variables, the page header fields, the small YAML files in `content/`, the figure controls and the host files. Each
entry has what it does, its default, the values it accepts and a short example.

## How to read this page

- **Default** is what Bazinga uses when you leave the key out (from `bazinga/config.py`).
- **Example site** is what the template's own `site.yml` sets. The two differ in places, because the example is set
  up to look like a finished personal site. For example, the default accent is `#3b5bdb`, and the example sets
  `#0F52BA`.
- Everything in `site.yml` is optional. Bazinga lays your file over its defaults, so a nearly empty file still
  builds. `python -m bazinga serve` rebuilds after you save it.

When a value is wrong, every command stops before building and says what to write instead:

```text
site.yml: site.origin must start with http:// or https:// (got 'example.com')
```

(`site.yml:` is in front of every such message, even when the address came from `--origin` or the environment.)

## site

Who you are and where the site lives.

| Key | What it does | Default | Example site | Accepts |
|---|---|---|---|---|
| `site.name` | The name at the top of the side rail, in the browser tab, in search results and as the feed title. | `"Bazinga"` | `"Your Name"` | text |
| `site.author` | Your name on every page's header block, in the feed and for search engines. | `"Your Name"` | `"Your Name"` | text |
| `site.tagline` | The feed's subtitle, and the home page's search description when `description` is empty. | `"Notes on things I am learning"` | `"Notes on the things I build and learn"` | text |
| `site.description` | What search engines show for the home page. | `""` | a sentence | text, up to 155 characters |
| `site.origin` | The address the site will have. Used for canonical links, the sitemap, the feed and share cards. If it has a path (`https://you.github.io/notes`), every link the build writes starts with that path. | `"https://example.com"` | `"https://example.com"` | must start with `http://` or `https://`; may have a path; no `?` or `#`; a trailing `/` is removed |
| `site.language` | The language of the pages (`<html lang>`, share previews). | `"en"` | `en` | a language code |
| `site.avatar` | A picture used as the browser-tab icon and the share image. Without it the tab shows the Bazinga mark. | `""` | `""` | a path such as `static/avatar.png` |
| `site.links` | Buttons on the home page, in the order you write them. Empty ones are hidden. | `github`, `x`, `linkedin`, `email`, `scholar` (all empty) | `github`, `linkedin`, `medium`, `scholar`, `x`, `email` | a mapping of name → address |

```yaml
site:
  name: "Ada Example"
  origin: "https://ada.example"
  links:
    github: "https://github.com/ada"
    email: "ada@example.com"
```

### A site under a path {#a-site-under-a-path}

Most sites live at the root of their address (`https://ada.example/`). A GitHub Pages project site lives under a
folder instead: `https://ada.github.io/notes/`. Put that folder in `site.origin` and the build does the rest:

```yaml
site:
  origin: "https://ada.github.io/notes"
```

**What you should see** after `python -m bazinga build`: links, styles, data files and figure code all start with
`/notes/` (for example `href="/notes/assets/css/tokens.css?…"`), the canonical address is
`https://ada.github.io/notes/reads/welcome/`, and each page carries `<meta name="bazinga-base" content="/notes">`.

Three other ways set the address **for one build only**, without editing `site.yml`. The first one found wins:

1. `python -m bazinga build --origin https://ada.github.io/notes`
2. the environment variable `BAZINGA_ORIGIN`
3. the environment variable `SITE_URL`

The GitHub Pages workflow sets `BAZINGA_ORIGIN` for you (see [Deploying](../deploying.md#github-pages)).

`python -m bazinga serve` and the Editor always serve the site at the root of `http://127.0.0.1:8000/`, whatever
`site.origin` says, and they ignore `BAZINGA_ORIGIN` and `SITE_URL`.

`site.links.email` is not shown as a link: it powers the Contact section's email button. These names get a proper
label: `github`, `x`, `twitter`, `linkedin`, `email`, `scholar`, `medium`, `mastodon`, `bluesky`, `youtube`,
`website`, `orcid`, `substack`. Any other name is shown capitalised.

## nav

The side rail's menu, in order.

| Default | Example site | Accepts |
|---|---|---|
| Writing `/posts/`, Projects `/projects/`, Map `/explore/`, Ask `/ask/` | Home, Reads, Papers, Projects, Series, Elsewhere, Explore, Ask, CV | a list of `{label, href}`; both are required |

```yaml
nav:
  - {label: Home, href: /}
  - {label: Notes, href: /notes/}
  - {label: GitHub, href: "https://github.com/ada"}
```

`href` is a path on your site or a full address. More in [Theme and customising](../theme.md#the-menu).

For a portfolio with no blog, keep only Home, Projects and CV in the menu; see
[A portfolio without the blog](../home-and-cv.md#a-portfolio-without-the-blog).

## kinds

The kinds of page. Each kind is a folder `content/<kind>/` and a list page `/<kind>/`.

| Default | Example site |
|---|---|
| `posts` (Writing / Post), `projects` (Projects / Project) | `reads`, `papers`, `projects`, `elsewhere` |

If you write `kinds:`, your list replaces the default kinds; it is not added to them. You need at least one kind,
and its name must be lowercase letters, digits or `-` (it is a folder and an address).

| Field | What it does | Default | Accepts |
|---|---|---|---|
| `label` | The list page's title and the home page button. | the name, capitalised | text |
| `singular` | The name of one item. In lower case it starts the page ids (`read:welcome`). | `label` without its last "s" | text |
| `role` | The layout. | `paper` for `papers`, `project` for `projects`, `external` when external, else `read` | `read`, `paper`, `project`, `external` |
| `external` | Entries that live on another site (no body, they open there). | `false` | `true` or `false` |
| `blurb` | The line under the list page's title. | "<label> by <author>." | text |
| `placeholder` | The hint in the list's filter box. | "filter: a word from a title or a topic …" | text |
| `word` | What the list calls its items. | the label in lower case | text |

```yaml
kinds:
  notes: {label: Notes, singular: Note}            # pages are note:<file name>, at /notes/<file name>/
  talks: {label: Talks, singular: Talk, external: true}
```

More in [Theme and customising](../theme.md#kinds-of-pages).

A portfolio-only site keeps just `projects:` here (a site that defines its own kinds replaces the default ones):

```yaml
kinds:
  projects: {label: Projects, singular: Project}
```

## home

The home page. Every field is optional, and a section without its fields is left out. Where each one shows, with
examples, is in [Your portfolio](../home-and-cv.md). For a portfolio, `home:` is most of what you edit: your photo,
role, About, Experience, Education and Contact.

| Key | What it does | Default | Accepts |
|---|---|---|---|
| `home.title` | The home page's `<title>` and share title. Leave your name out: the site name is added after it. | `site.name` | text |
| `home.photo` | A square picture, shown round. | none | a path such as `/static/images/photo.svg` |
| `home.role` | The first line under the photo; also starts the CV page. | none | text |
| `home.working_at` | The second line under the photo. | none | text |
| `home.employer` | The CV page says "role at employer". | none | text |
| `home.tagline` | The big line at the top. | the site name | text |
| `home.statement` | A bold line under the tagline. | none | text |
| `home.lead` | The opening paragraph. | none | text |
| `home.intro` | One more paragraph, in Markdown. | `""` | text |
| `home.about` | The About section. | none | a list of paragraphs (`<b>`, `<i>`, `<a>` allowed) |
| `home.starters`, `home.starters_label` | Small buttons under About that answer back when picked. | none, `"Pick one"` | a list of `{name, mark, say}`; text |
| `home.map_text` | The text of the Explore section. | a sentence about the map | text |
| `home.experience` | The Experience section. | none | a list of `{period, role, org, place, points, pages}` (`pages` are page ids, checked) |
| `home.education` | The Education section. | none | a list of `{degree, school}` |
| `home.courses` | A line folded away under Education. | none | text |
| `home.contact` | The Contact section. | none | `lead`, `areas`, `stack`, `close`, `email_button`, `links_text`, `elsewhere` |
| `home.ask_examples` | Up to four example questions on the Ask page. | made from your pages | a list of questions |
| `home.show` | Checked, but not used by the default theme. | `[latest, series, map]` | a list |

## cv

| Key | What it does | Default | Accepts |
|---|---|---|---|
| `cv.pdf` | Makes the home page's CV button say **Download CV** and open this file (without it, **Read the CV** opens `/cv/`). | `""` | a path such as `/static/cv.pdf`, or a full address |

```yaml
cv:
  pdf: /static/cv.pdf
```

The CV itself is `content/cv.yml`: see [below](#contentcvyml).

## theme

Colours and fonts. More, with the default colours, in [Theme and customising](../theme.md).

| Key | What it does | Default | Example site | Accepts |
|---|---|---|---|---|
| `theme.accent` | Links, the current menu item, read boxes on the map. | `"#3b5bdb"` | `"#0F52BA"` | a hex colour such as `"#0F52BA"` |
| `theme.accent_dark`, `ground`, `paper`, `tint`, `ink`, `ink_2`, `ink_3`, `rule_2`, `rule_3`, `ref`, `alert` | The theme's other colours. What each one colours, and its default, is in [Colours](../theme.md#colours). | `""` (the theme's own colours) | `ground: ""`, `paper: ""` | a hex colour or empty |
| `theme.font_text` | The body text. | `"Source Serif 4"` | `"STIX Two Text"` | a Google Fonts family name |
| `theme.font_code` | Code, and the default theme's labels, menu and buttons. | `"JetBrains Mono"` | `"Courier Prime"` | a Google Fonts family name |
| `theme.font_math` | Equations. | `"STIX Two Math"` | `"STIX Two Math"` | a font with a maths table |
| `theme.font_ui` | Loaded, but not used by the default theme. | `"Inter"` | `"Courier Prime"` | a Google Fonts family name |
| `theme.width` | Checked, but not used by the default theme. | `720` | `720` | a number from 480 to 1200 |
| `theme.mode` | Checked, but not used: the default theme is light only. | `"auto"` | `light` | `auto`, `light` or `dark` |

```yaml
theme:
  accent: "#2E7D32"
  font_text: "Source Serif 4"
```

## features

Turn parts of the site off. Every one is on by default. Remove the matching item from `nav:` as well. A portfolio
with no blog usually turns off `ask`, `explore`, `series` and `feed`.

| Key | When `false` |
|---|---|
| `features.ask` | no Ask page and no Ask button |
| `features.explore` | no map page and no Explore section on the home page |
| `features.series` | no series pages (remove the `series:` lines and the menu item too; see [Series](../writing/series.md)) |
| `features.feed` | no `/feed.xml` |
| `features.llms_txt` | no `/llms.txt` and `/llms-full.txt` |
| `features.credit` | no small "Made with Bazinga" link at the foot of the side rail |

```yaml
features: {ask: true, explore: true, series: true, feed: true, llms_txt: true, credit: false}
```

## llm

Optional: a language model for suggestions and written answers. Without one, everything else works. Setup for each
provider is in [Ask and the wiki](../ask-and-wiki.md#connect-a-model).

| Key | What it does | Default | Accepts |
|---|---|---|---|
| `llm.base_url` | The address of the model's API. | `"https://openrouter.ai/api/v1"` | any OpenAI-compatible address, such as `http://localhost:11434/v1` for Ollama |
| `llm.model` | The model's name. | `""` (no model) | text; several names separated by commas are tried in turn |
| `llm.key_env` | The name of the environment variable that holds the key. | `"LLM_API_KEY"` | a variable name |

```yaml
llm:
  base_url: "https://openrouter.ai/api/v1"
  model: "openai/gpt-4o-mini"
  key_env: "LLM_API_KEY"
```

The key never goes in `site.yml`. See [Environment variables](#environment-variables) and [.env.local](#envlocal).

## ask

Limits for written answers on the Ask page (they need a model and a key on the server).

| Key | What it does | Default | Accepts |
|---|---|---|---|
| `ask.written_answers` | Offer written answers at all. | `true` | `true` or `false` |
| `ask.per_visitor` | Written answers per visitor (by IP address) per day. | `5` | a whole number |
| `ask.daily_cap` | Written answers per day for the whole site. | `300` | a whole number |

## publish

What **Publish** (in the Editor, or `python -m bazinga publish`) does after it builds, on your computer.

| Key | What it does | Default | Accepts |
|---|---|---|---|
| `publish.commit` | `git add` the page and its files, then commit. | `true` | `true` or `false` |
| `publish.push` | `git push`, so your host deploys. | `true` | `true` or `false` |
| `publish.command` | One more command after the push. It runs without a shell. | `""` | a command, such as `"vercel deploy --prod --yes"` |
| `publish.author` | Who the commits are by. | `""` (your git settings) | `"Your Name <you@example.com>"` |

```yaml
publish:
  author: "Ada Example <ada@example.com>"
```

Two things to know:

- **Commits need a name and an email.** If `publish.author` is empty and git has no email set, Publish stops at the
  commit step with `Not committed: git does not know your name and email.` and puts the page back as it was. Fix it
  with `publish.author`, or once with `git config user.name "Your Name"` and
  `git config user.email you@example.com`.
- **The push goes where your branch points.** If your branch tracks a remote branch (for example a local `work`
  that tracks `origin/main`), Publish runs `git push origin HEAD:main`, even when the names differ. With no tracked
  branch it runs `git push -u origin HEAD`.

## Environment variables

Settings read from the environment, not from `site.yml`. Where each one applies:

| Variable | What it does | Applies to |
|---|---|---|
| the one named by `llm.key_env` (default `LLM_API_KEY`) | The model's key. Written answers are on only when it is set, even for a local model (any text works there). The `wiki` commands and the Editor need no key for a `localhost` address. | written answers (`serve`, Vercel), the `wiki` commands, the Editor's suggestions |
| `LLM_KEY_ENV` | Read the key from a variable with another name. | written answers only |
| `LLM_MODEL` | The model, instead of `llm.model`. | written answers only |
| `ASK_MODEL` | The model, when `LLM_MODEL` is not set. | written answers only |
| `LLM_BASE_URL` | The API address, instead of `llm.base_url`. | written answers only |
| `ASK_WRITTEN` | `0`, `false` or `off` turns written answers off. | written answers only |
| `ASK_PER_VISITOR` | Instead of `ask.per_visitor`. | written answers only |
| `ASK_DAILY_CAP` | Instead of `ask.daily_cap`. | written answers only |
| `BAZINGA_ORIGIN` | The site's address for this build, instead of `site.origin` (may have a path). `--origin` wins over it. | `python -m bazinga build` only |
| `SITE_URL` | 1. For `build`: the same as `BAZINGA_ORIGIN`, when that is not set. 2. For `api/ask.py`: where it fetches `/data/passages.json` when the deployment does not include `_site/data/` (default: the request's own address). | `python -m bazinga build`, and Vercel (`api/ask.py`) |
| `BAZINGA_STUDIO_DEV` | Any value makes the Editor rebuild its own app page on every load. Only for working on the Editor itself. | the Editor only |

"Written answers" means `/api/ask/`: `api/ask.py` on Vercel, and the same endpoint under `python -m bazinga serve`.
The `wiki` commands and the Editor take their model and address from `site.yml`; they read only the key from the
environment.

## .env.local

A file in your site folder that holds secrets, one `NAME=value` per line. Git ignores it (it is in `.gitignore`), so
it never reaches your repository.

```text
LLM_API_KEY=your-key-here
```

- `python -m bazinga serve` reads it for written answers, and its values win over the environment.
- The `wiki` commands and the Editor read the key from the environment first, then from `.env.local`.
- On a host, set the same variables in the host's settings instead (for Vercel, the project's Environment
  Variables). The file is never uploaded.

## Page header fields

The block between `---` lines at the top of every page. Step-by-step use is in
[Your first post](../writing/first-post.md#the-header-fields).

**Every kind:**

| Field | What it does | Needed |
|---|---|---|
| `title` | The page's title. | always |
| `date` | `YYYY-MM-DD`. A future date schedules the page. | to publish |
| `status` | `draft` or `published` (default `published`). | no |
| `summary` | Two or three sentences for the top of the page, lists, the map and search. | to publish |
| `topics` | One to four slugs from `content/topics.yml`. | to publish |
| `description` | Up to 155 characters for search engines. | no |
| `builds_on` | Pages to read first, as ids (`read:welcome`). | no |
| `cites` | Citation keys from `content/references.yml`. | no |
| `series` | `{name: "…", part: 2}`. | no |
| `updated` | The date of a real revision. Publishing again sets it. | no |
| `cover` | An image under `static/` for share previews. | no |
| `seo_title` | A different `<title>` for search engines. | no |
| `short` | A short name where space is tight (map pickers, the "Sits under" trail). | no |
| `first_published` | Text such as `"Medium, March 2021"`, shown in the header block of reads and papers. | no |

**Papers:** `explains: [Key]`, the citation key of the paper the page explains.

**Projects:** `type`, `stack`, `tagline`, `lead`, `from`, `github`, `usage`, `limitations`, `credit`, `order`. What
each one shows is in [Project pages](../writing/first-post.md#project-pages).

**External entries** (a kind with `external: true`): `external` (the address it opens, required), `author`,
`publication`. They have no body.

## content/topics.yml

The only topics pages may use. Each topic gets a page at `/topics/<slug>/`; groups only arrange the `/topics/` page.

```yaml
groups:
  - name: Foundations
    topics:
      - {slug: probability, label: Probability, blurb: "Distributions and how uncertainty is measured."}
```

| Field | What it does | Default |
|---|---|---|
| `slug` | What pages write in `topics:`, and the address. | required |
| `label` | The topic's name. | the slug, with spaces and capitals |
| `blurb` | One line about it. | `""` |

More in [The map and topics](../map-and-topics.md).

## content/references.yml

Your citation library. `python -m bazinga cite <arXiv id or DOI>` adds entries for you.

```yaml
Vaswani17:
  title: "Attention Is All You Need"
  authors: [Ashish Vaswani, Noam Shazeer]
  year: 2017
  venue: "NeurIPS"
  arxiv: "1706.03762"
```

Each entry needs `title`, `authors` (a list) and `year`, and at least one of `arxiv`, `doi` or `url`. `venue` is
optional. More in [Citations](../writing/citations.md).

## content/cv.yml

The CV page: `contact`, `experience`, `education`, `patents`, `achievements` and the rest, each with its fields, in
[Your portfolio](../home-and-cv.md#the-cv-page).

## content/series/&lt;slug&gt;.yml

Optional highlights for each part of a series, and an intro. The format is in [Series](../writing/series.md).

## Figure controls

The `CONTROLS` list in a `figures/<name>.py` file. Every control has a `name` (the argument of `compute()`), a
`kind`, a `label` and a starting `value`. Any control may add `group` (a heading; controls with the same group fold
into one panel).

| `kind` | What the reader gets | Other fields |
|---|---|---|
| `slider` | a slider | `min`, `max`, `step`, `value`; `"play": True` adds a Play button |
| `toggle` | two buttons | `options` (exactly two); gives 0 or 1 |
| `steps` | a row of buttons | `options`; gives the position of the chosen one |
| `orbit` | drag the picture to turn a 3-D scene | see [3-D figures](../figures-3d.md) |
| `pad` | drag a point in the picture | see [3-D figures](../figures-3d.md) |
| `hidden` | a value only drags change | see [3-D figures](../figures-3d.md) |

```python
CONTROLS = [
    {"name": "t", "kind": "slider", "label": "Temperature", "min": 0.1, "max": 5, "step": 0.05, "value": 1},
    {"name": "k", "kind": "steps", "label": "Classes", "options": ["3", "5", "8"], "value": 1},
]
```

The rest of a figure file (`TITLE`, `CAPTION`, `REQUIRES`, `PRESETS`, what `compute()` returns) is in
[Interactive figures](../figures.md).

## Host files

| File | What it sets | More |
|---|---|---|
| `vercel.json` | Vercel: install the requirements, run the tests, build into `_site`, and the `api/ask.py` function. | [Deploying](../deploying.md#vercel) |
| `netlify.toml` | Netlify: the same build, Python 3.12, publish `_site`. | [Deploying](../deploying.md#netlify) |
| `.github/workflows/pages.yml` | GitHub Pages: on every push to `main` and once a day, run the tests, build with the address GitHub gives the site (`BAZINGA_ORIGIN`, from `actions/configure-pages`), then deploy `_site`. | [Deploying](../deploying.md#github-pages) |

## A minimal site.yml

```yaml
site:
  name: "Ada Example"
  author: "Ada Example"
  origin: "https://ada.example"
kinds:
  posts: {label: Writing, singular: Post}
nav:
  - {label: Writing, href: /posts/}
  - {label: Ask, href: /ask/}
```

This is for a site of your own, whose pages are all in `content/posts/`. (With the example content still in place it
does not build: the example `content/cv.yml` and posts link to `read:` and `project:` pages, which this file no
longer has.)

**What you should see:** with one published post in `content/posts/` and no `content/cv.yml`,
`python -m bazinga build` prints `Built 1 pages (9 HTML files) into _site/`, and the menu has two items.

## What's next

Next, answers to common problems and questions: [Troubleshooting and FAQ](../troubleshooting.md).

- How each command uses these settings: [Commands](commands.md).
